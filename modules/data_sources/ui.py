import json

import pandas as pd
import streamlit as st

from core.practical_learning import INGESTION_PROFILES, SOURCE_CATALOG, simulate_ingestion
from core.practice_state import load_practice_state, save_practice_state
from core.lazy_tabs import lazy_tab


SAMPLE_RECORDS = """{"order_id": 1, "customer_id": 101, "amount": 120.5}
{"order_id": 2, "customer_id": 102, "amount": 80.0}
{"order_id": 2, "customer_id": 102, "amount": 80.0}
{"order_id": 3, "customer_id": 103, "amount": 220.0}"""

SOURCE_ARCHITECTURES = {
    "PostgreSQL / MySQL / Oracle": ("Application transactions", "Primary + read replica", "JDBC ranges or transaction log", "Object storage / Kafka", "Warehouse tables"),
    "MongoDB / Document DB": ("Application documents", "Replica set / shards", "Cursor or change stream", "Nested raw collection", "Flattened analytical tables"),
    "REST / GraphQL API": ("External service", "Gateway + rate limit", "Paginator / webhook receiver", "Response audit landing", "Contract-normalized tables"),
    "Files / S3 / Object Storage": ("Producer files", "Bucket + partitions", "Manifest scan / object events", "Quarantine + raw zone", "Compacted columnar tables"),
    "Kafka / MSK": ("Event producers", "Topics + partitions", "Consumer group", "Replayable raw topic/lake", "Streaming materialized view"),
    "Kinesis": ("AWS producers", "Shards", "Enhanced fan-out consumer", "Firehose / raw lake", "Real-time serving table"),
    "DMS / Debezium CDC": ("Operational database", "Transaction log", "Connector + schema history", "Ordered change topic", "Upsert/delete target"),
}


def _render_source_styles():
    st.markdown(
        """
        <style>
        .source-flow {
            display:flex;gap:.35rem;
            align-items:stretch;margin:.8rem 0 1rem;
        }
        .source-node {
            background:var(--secondary-background-color);color:var(--text-color)!important;
            border:1px solid color-mix(in srgb,var(--text-color) 30%,transparent);
            border-radius:.55rem;padding:.75rem .55rem;min-height:6rem;
            display:flex;flex:1 1 0;flex-direction:column;justify-content:center;overflow-wrap:anywhere;
        }
        .source-node strong,.source-node small {color:var(--text-color)!important}
        .source-node strong{font-size:.82rem;margin-bottom:.3rem}
        .source-node small{font-size:.72rem;line-height:1.35;opacity:.82}
        .source-arrow{display:flex;flex:0 0 1.5rem;align-items:center;justify-content:center;color:#60a5fa;font-size:1.25rem}
        .source-control-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.6rem;margin:.6rem 0}
        .source-control{background:color-mix(in srgb,var(--secondary-background-color) 88%,#2563eb 12%);
            color:var(--text-color)!important;border-left:3px solid #3b82f6;padding:.65rem;font-size:.76rem}
        @media(max-width:900px){
            .source-flow{flex-direction:column}.source-control-grid{grid-template-columns:1fr}
            .source-arrow{transform:rotate(90deg);min-height:1.5rem}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_source_flow(nodes, details=None):
    details = details or [""] * len(nodes)
    parts = []
    for index, (node, detail) in enumerate(zip(nodes, details)):
        parts.append(f"<div class='source-node'><strong>{node}</strong><small>{detail}</small></div>")
        if index < len(nodes) - 1:
            parts.append("<div class='source-arrow'>→</div>")
    st.markdown(f"<div class='source-flow'>{''.join(parts)}</div>", unsafe_allow_html=True)


def _render_source_architecture(source):
    profile = INGESTION_PROFILES[source]
    nodes = SOURCE_ARCHITECTURES[source]
    details = [
        SOURCE_CATALOG[source],
        f"Partitioning: {profile['partition']}",
        "Batch, streaming and CDC use different capture mechanics.",
        f"Schema: {profile['schema']}",
        "Idempotent publish after checkpoint commit.",
    ]
    _render_source_flow(nodes, details)
    controls = [
        ("Batch", f"{profile['capture']['Batch snapshot']} · checkpoint: {profile['checkpoint']['Batch snapshot']}"),
        ("Streaming", f"{profile['capture']['Streaming']} · checkpoint: {profile['checkpoint']['Streaming']}"),
        ("CDC", f"{profile['capture']['CDC']} · checkpoint: {profile['checkpoint']['CDC']}"),
        ("Primary risk", {
            "PostgreSQL / MySQL / Oracle": "Long snapshots, source load and transaction-log retention.",
            "MongoDB / Document DB": "Schema drift, shard movement and expired resume tokens.",
            "REST / GraphQL API": "Rate limits, cursor expiry and non-idempotent retries.",
            "Files / S3 / Object Storage": "Partial files, duplicate notifications and small-file growth.",
            "Kafka / MSK": "Consumer lag, partition skew and offset loss.",
            "Kinesis": "Hot shards, iterator age and record aggregation.",
            "DMS / Debezium CDC": "Log retention gaps, DDL evolution and out-of-order apply.",
        }[source]),
    ]
    st.markdown(
        "<div class='source-control-grid'>"
        + "".join(f"<div class='source-control'><b>{title}</b><br>{value}</div>" for title, value in controls)
        + "</div>",
        unsafe_allow_html=True,
    )


@st.fragment
def render_data_sources():
    username = st.session_state.get("user")
    _render_source_styles()
    st.title("Data Sources & Ingestion")
    selected_view = lazy_tab(
        ["Source Architectures", "Ingestion Simulator"],
        "data_sources_active_view",
        "Data source workspace",
    )

    if selected_view == "Source Architectures":
        selected = st.selectbox("Source type", list(SOURCE_CATALOG))
        st.subheader(selected)
        _render_source_architecture(selected)

    else:
        marker = f"data_sources_loaded::{username}"
        if not st.session_state.get(marker):
            saved = load_practice_state(username, "data_sources") or {}
            if saved.get("ingestion_result", {}).get("pipeline_stages"):
                st.session_state["ingestion_result"] = saved["ingestion_result"]
            else:
                st.session_state.pop("ingestion_result", None)
            st.session_state[marker] = True
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
            _render_source_flow(
                result["pipeline_stages"],
                [
                    "Selected source",
                    result["capture"],
                    result["partitioning"],
                    "Append-only replay boundary",
                    result["checkpoint_display"],
                    result["delivery"],
                ],
            )
            metrics = st.columns(4)
            metrics[0].metric("Input", result["input_count"])
            metrics[1].metric("Written", result["output_count"])
            metrics[2].metric("Duplicates removed", result["duplicates_removed"])
            metrics[3].metric("Checkpoint", result["checkpoint_display"])
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
                        "capture": result["capture"],
                        "partitioning": result["partitioning"],
                        "schema_control": result["schema_control"],
                        "delivery": result["delivery"],
                    },
                    indent=2,
                ),
                language="json",
            )

