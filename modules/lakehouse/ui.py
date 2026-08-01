import pandas as pd
import streamlit as st

from core.practical_learning import (
    LAKEHOUSE_FORMATS,
    apply_lakehouse_operation,
    new_lakehouse_state,
)
from core.practice_state import load_practice_state, save_practice_state
from core.lazy_tabs import lazy_tab
from modules.architecture.ui import render_diagram_collection


def _render_lakehouse_lab():
    username = st.session_state.get("user")
    state_key = f"lakehouse_state::{username or 'local'}"
    if state_key not in st.session_state:
        saved = load_practice_state(username, "lakehouse") or {}
        st.session_state[state_key] = saved.get("state", new_lakehouse_state())
    state = st.session_state[state_key]

    format_name = st.selectbox(
        "Table format",
        list(LAKEHOUSE_FORMATS),
        index=list(LAKEHOUSE_FORMATS).index(
            state["format"] if state["format"] in LAKEHOUSE_FORMATS else "Apache Iceberg"
        ),
    )
    state["format"] = format_name
    selected_view = lazy_tab(
        ["Learn", "Table Operations", "Snapshots & Files", "Troubleshoot & Interview"],
        "lakehouse_lab_active_view",
        "Lakehouse lab view",
    )

    if selected_view == "Learn":
        st.subheader(format_name)
        st.write(LAKEHOUSE_FORMATS[format_name])
        concepts = [
            {
                "Concept": "Atomic commit",
                "Meaning": "Readers see either the old snapshot or the complete new snapshot.",
            },
            {
                "Concept": "Schema evolution",
                "Meaning": "Columns can evolve with format-specific compatibility rules.",
            },
            {
                "Concept": "Partition evolution",
                "Meaning": "New layouts can be introduced without rewriting every historical file.",
            },
            {
                "Concept": "Time travel",
                "Meaning": "Queries and rollback can target an earlier committed snapshot.",
            },
            {
                "Concept": "Compaction",
                "Meaning": "Many small files are rewritten into fewer efficient files.",
            },
        ]
        st.dataframe(pd.DataFrame(concepts), width="stretch", hide_index=True)

    elif selected_view == "Table Operations":
        operation = st.selectbox(
            "Operation",
            [
                "Append",
                "MERGE / Upsert",
                "Delete",
                "Schema Evolution",
                "Compact Files",
                "Rollback",
            ],
        )
        payload = {}
        fields = st.columns(3)
        if operation in {"MERGE / Upsert", "Delete"}:
            payload["order_id"] = fields[0].number_input("Order ID", min_value=1, value=1)
        if operation in {"Append", "MERGE / Upsert"}:
            payload["status"] = fields[1].text_input("Status", value="PROCESSED")
            payload["amount"] = fields[2].number_input("Amount", value=150.0)
        elif operation == "Schema Evolution":
            payload["column"] = fields[0].text_input("New column", value="source")
            payload["type"] = fields[1].selectbox(
                "Column type",
                ["string", "long", "double", "timestamp"],
            )
        elif operation == "Rollback":
            payload["snapshot_id"] = fields[0].number_input(
                "Snapshot ID",
                min_value=1,
                value=1,
            )
        if st.button("Commit Lakehouse Operation", type="primary"):
            try:
                st.session_state[state_key] = apply_lakehouse_operation(
                    state,
                    operation,
                    payload,
                )
                save_practice_state(
                    username,
                    "lakehouse",
                    {"state": st.session_state[state_key]},
                )
                st.rerun()
            except ValueError as error:
                st.error(str(error))
        st.dataframe(
            pd.DataFrame(st.session_state[state_key]["rows"]),
            width="stretch",
            hide_index=True,
        )

    elif selected_view == "Snapshots & Files":
        current = st.session_state[state_key]
        metrics = st.columns(3)
        metrics[0].metric("Current snapshot", current["snapshots"][-1]["id"])
        metrics[1].metric("Data files", current["files"])
        metrics[2].metric("Rows", len(current["rows"]))
        st.json(current["schema"], expanded=False)
        snapshot_rows = [
            {
                "Snapshot": item["id"],
                "Operation": item["operation"],
                "Rows": len(item["rows"]),
            }
            for item in reversed(current["snapshots"])
        ]
        st.dataframe(pd.DataFrame(snapshot_rows), width="stretch", hide_index=True)

    else:
        st.markdown("**Common production problems**")
        problems = [
            "Small files increase metadata and planning overhead.",
            "Concurrent writers require compatible commit and retry behavior.",
            "Long snapshot retention prevents orphan-file cleanup.",
            "Incorrect MERGE keys create duplicate logical records.",
            "Catalog and object-storage permissions must agree.",
        ]
        for problem in problems:
            st.markdown(f"- {problem}")
        st.markdown("**Compare formats**")
        st.write(
            "Discuss engine compatibility, catalog choice, update frequency, streaming integration, "
            "partition evolution, operational tooling, and vendor independence—not only feature lists."
        )


def render_lakehouse():
    st.title("Lakehouse & Table Formats")
    selected = lazy_tab(
        ["Practical Lab", "Architecture Diagrams"],
        "lakehouse_active_workspace",
        "Lakehouse workspace",
    )
    if selected == "Practical Lab":
        _render_lakehouse_lab()
    else:
        render_diagram_collection(
            title="Lakehouse Architecture Diagrams",
            collection="lakehouse",
            description=(
                "Read-only Iceberg, Delta Lake, Hudi, catalog, object-storage, "
                "streaming, and query-engine Draw.io architectures synchronized from GitHub."
            ),
            key_prefix="lakehouse",
            access_checked=True,
        )
