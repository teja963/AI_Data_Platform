import json

import pandas as pd
import streamlit as st

from core.practical_learning import SOURCE_CATALOG, simulate_ingestion
from core.practice_state import load_practice_state, save_practice_state
from core.lazy_tabs import lazy_tab


SAMPLE_RECORDS = """{"order_id": 1, "customer_id": 101, "amount": 120.5}
{"order_id": 2, "customer_id": 102, "amount": 80.0}
{"order_id": 2, "customer_id": 102, "amount": 80.0}
{"order_id": 3, "customer_id": 103, "amount": 220.0}"""


def render_data_sources():
    username = st.session_state.get("user")
    marker = f"data_sources_loaded::{username}"
    if not st.session_state.get(marker):
        saved = load_practice_state(username, "data_sources") or {}
        if saved.get("ingestion_result"):
            st.session_state["ingestion_result"] = saved["ingestion_result"]
        st.session_state[marker] = True
    st.title("Data Sources & Ingestion")
    selected_view = lazy_tab(
        ["Source Catalog", "Ingestion Simulator", "Patterns", "Interview Practice"],
        "data_sources_active_view",
        "Data source workspace",
    )

    if selected_view == "Source Catalog":
        selected = st.selectbox("Source type", list(SOURCE_CATALOG))
        st.subheader(selected)
        st.write(SOURCE_CATALOG[selected])
        source_details = {
            "PostgreSQL / MySQL / Oracle": [
                "Snapshot using JDBC with partitioned reads.",
                "CDC from WAL/binlog/redo logs.",
                "Track source position and schema changes.",
            ],
            "MongoDB / Document DB": [
                "Preserve nested documents or flatten intentionally.",
                "Use change streams for incremental ingestion.",
                "Handle optional fields and evolving schemas.",
            ],
            "REST / GraphQL API": [
                "Use cursor/page checkpoints and bounded retries.",
                "Respect rate limits and idempotency.",
                "Persist request and response audit metadata.",
            ],
            "Files / S3 / Object Storage": [
                "Prefer Parquet for analytics and partition pruning.",
                "Validate file completeness before processing.",
                "Compact small files and quarantine malformed records.",
            ],
            "Kafka / MSK": [
                "Partition for ordering and parallelism.",
                "Commit offsets only after durable processing.",
                "Monitor consumer lag and replay safely.",
            ],
            "Kinesis": [
                "Choose a high-cardinality partition key.",
                "Scale shards or use on-demand mode.",
                "Track sequence numbers and iterator age.",
            ],
            "DMS / Debezium CDC": [
                "Apply full load before ordered changes.",
                "Preserve insert/update/delete operation metadata.",
                "Detect log-retention gaps before resuming.",
            ],
        }
        for item in source_details[selected]:
            st.markdown(f"- {item}")

    elif selected_view == "Ingestion Simulator":
        with st.form("ingestion_simulator_form"):
            controls = st.columns(3)
            source = controls[0].selectbox("Source", list(SOURCE_CATALOG))
            mode = controls[1].selectbox(
                "Ingestion mode",
                ["Batch snapshot", "Streaming", "CDC"],
            )
            deduplicate = controls[2].checkbox("Deduplicate records", value=True)
            records_text = st.text_area(
                "Source records (JSON Lines)",
                value=SAMPLE_RECORDS,
                height=220,
            )
            execute = st.form_submit_button("Run Ingestion", type="primary")
        if execute:
            try:
                st.session_state["ingestion_result"] = simulate_ingestion(
                    source,
                    mode,
                    records_text,
                    deduplicate,
                )
                save_practice_state(
                    username,
                    "data_sources",
                    {"ingestion_result": st.session_state["ingestion_result"]},
                )
            except ValueError as error:
                st.error(str(error))
        result = st.session_state.get("ingestion_result")
        if result:
            metrics = st.columns(4)
            metrics[0].metric("Input", result["input_count"])
            metrics[1].metric("Written", result["output_count"])
            metrics[2].metric("Duplicates removed", result["duplicates_removed"])
            metrics[3].metric("Checkpoint", result["checkpoint"])
            st.dataframe(
                pd.DataFrame(result["records"]),
                width="stretch",
                hide_index=True,
            )
            st.code(
                json.dumps(
                    {
                        "checkpoint": result["checkpoint"],
                        "status": "COMMITTED",
                        "delivery": "exactly-once simulation",
                    },
                    indent=2,
                ),
                language="json",
            )

    elif selected_view == "Patterns":
        st.subheader("Choose the ingestion pattern")
        rows = [
            {
                "Requirement": "Nightly relational snapshot",
                "Pattern": "Partitioned JDBC extract → object storage",
                "Control": "High-watermark and source reconciliation",
            },
            {
                "Requirement": "Database changes in seconds",
                "Pattern": "WAL/binlog → Debezium/DMS → Kafka/Kinesis",
                "Control": "Source LSN/offset and idempotent sink",
            },
            {
                "Requirement": "High-volume events",
                "Pattern": "Producer → partitions/shards → consumer groups",
                "Control": "Lag, replay, DLQ and schema compatibility",
            },
            {
                "Requirement": "External APIs",
                "Pattern": "Scheduled incremental requests",
                "Control": "Cursor, retry budget and rate-limit checkpoint",
            },
        ]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    else:
        questions = [
            "How do you guarantee that a restarted ingestion job does not duplicate data?",
            "When would you choose CDC instead of timestamp-based incremental extraction?",
            "How do partition keys influence Kafka or Kinesis throughput and ordering?",
            "How do you detect and recover from a source-log retention gap?",
            "How do you handle schema evolution without silently corrupting downstream tables?",
        ]
        for index, question in enumerate(questions, start=1):
            with st.expander(f"{index}. {question}"):
                st.write(
                    "Answer with the source guarantee, checkpoint, idempotency key, "
                    "schema contract, replay procedure, monitoring signal, and failure trade-off."
                )
