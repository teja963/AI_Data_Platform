import pandas as pd
import streamlit as st

from core.practical_learning import simulate_dag
from core.practice_state import load_practice_state, save_practice_state
from core.lazy_tabs import lazy_tab


AIRFLOW_TEMPLATE = """from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

with DAG(
    dag_id="orders_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule="0 * * * *",
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
) as dag:
    extract = PythonOperator(task_id="extract", python_callable=extract_orders)
    transform = PythonOperator(task_id="transform", python_callable=transform_orders)
    quality = PythonOperator(task_id="quality", python_callable=check_quality)
    load = PythonOperator(task_id="load", python_callable=load_warehouse)

    extract >> transform >> quality >> load
"""

EXERCISES = {
    "Batch ETL": (
        "extract,transform,quality,load",
        "extract>transform,transform>quality,quality>load",
    ),
    "CDC with parallel checks": (
        "wait_for_cdc,consume,quality,schema_check,publish",
        "wait_for_cdc>consume,consume>quality,consume>schema_check,quality>publish,schema_check>publish",
    ),
    "Lakehouse maintenance": (
        "wait_for_partition,compact,expire_snapshots,refresh_catalog",
        "wait_for_partition>compact,compact>expire_snapshots,expire_snapshots>refresh_catalog",
    ),
}


def _dag_graph(task_text, dependency_text, rows):
    statuses = {row["Task"]: row["Status"] for row in rows}
    colors = {
        "SUCCESS": "#22c55e",
        "FAILED": "#ef4444",
        "UPSTREAM_FAILED": "#f59e0b",
    }
    tasks = [item.strip() for item in task_text.split(",") if item.strip()]
    lines = ["digraph DAG {", "rankdir=LR;", 'node [shape=box style="rounded,filled" fontcolor=white];']
    for task in tasks:
        safe = task.replace('"', "")
        color = colors.get(statuses.get(task), "#64748b")
        lines.append(f'"{safe}" [fillcolor="{color}"];')
    for item in dependency_text.split(","):
        if ">" in item:
            upstream, downstream = (part.strip().replace('"', "") for part in item.split(">", 1))
            lines.append(f'"{upstream}" -> "{downstream}";')
    lines.append("}")
    return "\n".join(lines)


def render_orchestration():
    username = st.session_state.get("user")
    marker = f"orchestration_loaded::{username}"
    if not st.session_state.get(marker):
        saved = load_practice_state(username, "orchestration") or {}
        for key in ("dag_result", "dag_schedule", "dag_definition", "dag_runtime"):
            if key in saved:
                st.session_state[key] = saved[key]
        st.session_state[marker] = True
    st.title("Orchestration")
    selected_view = lazy_tab(
        ["Airflow Fundamentals", "DAG Simulator", "Dagster & Prefect", "Troubleshoot & Interview"],
        "orchestration_active_view",
        "Orchestration workspace",
    )

    if selected_view == "Airflow Fundamentals":
        st.subheader("Apache Airflow")
        st.write(
            "Airflow schedules and monitors workflows. The scheduler creates task instances, "
            "the executor sends work to workers, and the metadata database stores state."
        )
        concepts = [
            {"Concept": "DAG", "Practical meaning": "A versioned dependency graph, not the data-processing engine."},
            {"Concept": "Task", "Practical meaning": "One idempotent unit of work with explicit retries and timeout."},
            {"Concept": "Sensor", "Practical meaning": "Waits for an external condition; deferrable sensors release worker capacity."},
            {"Concept": "XCom", "Practical meaning": "Small metadata exchange—not a channel for large datasets."},
            {"Concept": "Pool", "Practical meaning": "Limits concurrency against constrained downstream systems."},
            {"Concept": "Backfill", "Practical meaning": "Runs historical logical intervals with controlled parallelism."},
        ]
        st.dataframe(pd.DataFrame(concepts), width="stretch", hide_index=True)
        st.code(AIRFLOW_TEMPLATE, language="python")

    elif selected_view == "DAG Simulator":
        exercise = st.selectbox("ETL exercise", list(EXERCISES))
        default_tasks, default_dependencies = EXERCISES[exercise]
        with st.form("orchestration_dag_form"):
            tasks = st.text_input(
                "Tasks",
                value=default_tasks,
                help="Comma-separated task IDs.",
            )
            dependencies = st.text_input(
                "Dependencies",
                value=default_dependencies,
                help="Comma-separated upstream>downstream relationships.",
            )
            controls = st.columns(3)
            schedule = controls[0].text_input("Schedule", value="0 * * * *")
            retries = controls[1].number_input("Retries", min_value=0, max_value=10, value=2)
            task_options = ["No failure", *[item.strip() for item in tasks.split(",") if item.strip()]]
            fail_task = controls[2].selectbox("Failure injection", task_options)
            with st.expander("Advanced scheduling and runtime"):
                advanced = st.columns(3)
                catchup = advanced[0].checkbox("Catchup")
                backfill_runs = advanced[1].number_input(
                    "Backfill intervals",
                    min_value=0,
                    max_value=100,
                    value=0,
                )
                pool_slots = advanced[2].number_input(
                    "Pool slots",
                    min_value=1,
                    max_value=100,
                    value=4,
                )
                sensor_task = st.text_input(
                    "Sensor task (optional)",
                    placeholder="wait_for_partition",
                )
                xcom_value = st.text_input(
                    "XCom metadata (optional)",
                    placeholder='{"source_rows": 1000}',
                )
            execute = st.form_submit_button("Run DAG", type="primary")
        if execute:
            try:
                st.session_state["dag_result"] = simulate_dag(
                    tasks,
                    dependencies,
                    None if fail_task == "No failure" else fail_task,
                    retries,
                )
                st.session_state["dag_schedule"] = schedule
                st.session_state["dag_definition"] = (tasks, dependencies)
                st.session_state["dag_runtime"] = {
                    "Catchup": catchup,
                    "Backfill intervals": backfill_runs,
                    "Pool slots": pool_slots,
                    "Sensor": sensor_task or "None",
                    "XCom": xcom_value or "None",
                }
                save_practice_state(
                    username,
                    "orchestration",
                    {
                        key: st.session_state[key]
                        for key in ("dag_result", "dag_schedule", "dag_definition", "dag_runtime")
                    },
                )
            except ValueError as error:
                st.error(str(error))
        rows = st.session_state.get("dag_result")
        if rows:
            graph_tasks, graph_dependencies = st.session_state.get(
                "dag_definition",
                (tasks, dependencies),
            )
            st.graphviz_chart(
                _dag_graph(graph_tasks, graph_dependencies, rows),
                width="stretch",
            )
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            runtime = st.session_state.get("dag_runtime")
            if runtime:
                st.dataframe(
                    pd.DataFrame(
                        [{"Runtime control": key, "Value": value} for key, value in runtime.items()]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            if any(row["Status"] == "FAILED" for row in rows):
                st.error("DAG run failed. Downstream tasks are marked UPSTREAM_FAILED.")
            else:
                st.success(
                    f"DAG run succeeded for schedule {st.session_state.get('dag_schedule')}."
                )
            st.code("\n".join(row["Log"] for row in rows), language="text")

    elif selected_view == "Dagster & Prefect":
        comparison = [
            {
                "Framework": "Airflow",
                "Model": "DAG and task-instance scheduling",
                "Best fit": "Broad ecosystem, scheduled batch, managed MWAA/Composer",
                "Practical focus": "Operators, scheduler, executor, metadata DB, sensors",
            },
            {
                "Framework": "Dagster",
                "Model": "Software-defined assets",
                "Best fit": "Asset lineage, typed data assets, testable Python definitions",
                "Practical focus": "Assets, resources, partitions, sensors, materializations",
            },
            {
                "Framework": "Prefect",
                "Model": "Python-native flows and tasks",
                "Best fit": "Dynamic workflows and lightweight developer experience",
                "Practical focus": "Flows, deployments, work pools, states, retries",
            },
            {
                "Framework": "AWS Step Functions",
                "Model": "Managed state machine",
                "Best fit": "AWS service orchestration and event-driven workflows",
                "Practical focus": "Retry, Catch, Choice, Map, Parallel, callback tokens",
            },
        ]
        st.dataframe(pd.DataFrame(comparison), width="stretch", hide_index=True)

    else:
        scenarios = {
            "Scheduler is healthy but tasks never start": "Inspect executor queues, worker capacity, pools, concurrency limits, and task dependencies.",
            "Backfill overloads the warehouse": "Use pools, max_active_runs, task concurrency, and staged date ranges.",
            "Sensor consumes every worker": "Use deferrable/reschedule mode and an asynchronous trigger.",
            "Task succeeds but data is duplicated": "Make processing idempotent and bind output to the logical data interval.",
            "Dynamic DAG parsing is slow": "Remove network/database work from top-level DAG import code.",
        }
        scenario = st.selectbox("Operational scenario", list(scenarios))
        st.warning(scenarios[scenario])
        st.write(
            "Interview answers should separate orchestration state from processing state, "
            "then cover retries, idempotency, observability, backfill, and recovery."
        )
