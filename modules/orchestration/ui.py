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

ORCHESTRATOR_RUNTIME = {
    "Airflow · KubernetesExecutor": {
        "control": ["Webserver / API", "Scheduler", "Triggerer", "Metadata PostgreSQL"],
        "launcher": "KubernetesExecutor submits one worker pod per runnable task",
        "worker": "Ephemeral task pod",
        "state": "TaskInstance state + XCom in metadata DB",
        "logs": "Remote logs in S3/GCS plus pod logs",
    },
    "Dagster": {
        "control": ["Dagster Webserver", "Daemon", "Run Coordinator", "Event Log Storage"],
        "launcher": "Run launcher starts a run worker; executor launches step processes/pods",
        "worker": "Run worker + asset step",
        "state": "Asset materializations and run events",
        "logs": "Structured event log + compute logs",
    },
    "Prefect": {
        "control": ["Prefect API/UI", "Scheduler", "Work Pool", "Database"],
        "launcher": "Worker polls the work pool and creates flow-run infrastructure",
        "worker": "Flow-run process / Kubernetes job",
        "state": "Flow and task states in Prefect API",
        "logs": "Worker and flow-run logs",
    },
}


def _render_orchestration_styles():
    st.markdown(
        """
        <style>
        .orch-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:.35rem;align-items:stretch;margin:.8rem 0}
        .orch-node{background:var(--secondary-background-color);color:var(--text-color)!important;
            border:1px solid color-mix(in srgb,var(--text-color) 30%,transparent);border-radius:.55rem;
            padding:.7rem .5rem;min-height:5.5rem;overflow-wrap:anywhere}
        .orch-node strong,.orch-node small{display:block;color:var(--text-color)!important}
        .orch-node strong{font-size:.8rem;margin-bottom:.25rem}.orch-node small{font-size:.7rem;line-height:1.35;opacity:.82}
        .orch-arrow{display:flex;align-items:center;justify-content:center;color:#60a5fa;font-size:1.2rem}
        .orch-pods{display:grid;grid-template-columns:repeat(auto-fit,minmax(11rem,1fr));gap:.55rem;margin:.55rem 0}
        .orch-pod{background:color-mix(in srgb,var(--secondary-background-color) 88%,#2563eb 12%);
            color:var(--text-color)!important;border-left:3px solid #3b82f6;padding:.65rem;font-size:.74rem}
        @media(max-width:900px){.orch-grid{grid-template-columns:1fr}.orch-arrow{transform:rotate(90deg);min-height:1.5rem}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_runtime_flow(orchestrator, tasks=None, rows=None):
    runtime = ORCHESTRATOR_RUNTIME[orchestrator]
    control = " + ".join(runtime["control"])
    nodes = [
        ("Definition", "DAG / assets / flow parsed into executable units"),
        (control, runtime["state"]),
        ("Launcher", runtime["launcher"]),
        (runtime["worker"], runtime["logs"]),
    ]
    parts = []
    for index, (title, detail) in enumerate(nodes):
        parts.append(f"<div class='orch-node'><strong>{title}</strong><small>{detail}</small></div>")
        if index < len(nodes) - 1:
            parts.append("<div class='orch-arrow'>→</div>")
    st.markdown(f"<div class='orch-grid'>{''.join(parts)}</div>", unsafe_allow_html=True)
    if tasks:
        statuses = {row["Task"]: row["Status"] for row in rows or []}
        pods = "".join(
            f"<div class='orch-pod'><b>{runtime['worker']}: {task}</b><br>"
            f"State: {statuses.get(task, 'QUEUED')}<br>{runtime['state']}</div>"
            for task in tasks
        )
        st.markdown(f"<div class='orch-pods'>{pods}</div>", unsafe_allow_html=True)


def _render_airflow_kubernetes_architecture():
    st.markdown("#### Airflow on Kubernetes: control plane and task pods")
    _render_runtime_flow("Airflow · KubernetesExecutor")
    components = [
        {"Component": "Webserver / API", "Runs as": "Deployment pod(s)", "Responsibility": "UI, auth and REST requests"},
        {"Component": "Scheduler", "Runs as": "HA scheduler pod(s)", "Responsibility": "Parses DAGs and creates runnable TaskInstances"},
        {"Component": "Triggerer", "Runs as": "Deployment pod(s)", "Responsibility": "Holds async/deferrable sensors without worker slots"},
        {"Component": "Metadata DB", "Runs as": "Managed PostgreSQL / StatefulSet", "Responsibility": "DAG runs, task state, connections and small XComs"},
        {"Component": "KubernetesExecutor", "Runs as": "Inside scheduler", "Responsibility": "Submits a Kubernetes pod for each task instance"},
        {"Component": "Task worker", "Runs as": "Ephemeral pod", "Responsibility": "Executes one task, reports state, then terminates"},
        {"Component": "DAG distribution", "Runs as": "Git sync / image / object storage", "Responsibility": "Makes identical DAG code available to all components"},
        {"Component": "Remote logging", "Runs as": "S3/GCS/Elastic", "Responsibility": "Preserves logs after task pods disappear"},
    ]
    st.dataframe(pd.DataFrame(components), width="stretch", hide_index=True)


def _enrich_runtime_rows(rows, orchestrator):
    runtime = ORCHESTRATOR_RUNTIME[orchestrator]
    enriched = []
    for index, row in enumerate(rows, start=1):
        if orchestrator.startswith("Airflow"):
            runtime_id = f"pod/{row['Task'].replace('_', '-')}-run-{index:03d}"
            queue_event = "Scheduler → KubernetesExecutor → API server"
        elif orchestrator == "Dagster":
            runtime_id = f"run-worker/step-{row['Task']}-{index:03d}"
            queue_event = "Run coordinator → run launcher → step executor"
        else:
            runtime_id = f"flow-run/task-{row['Task']}-{index:03d}"
            queue_event = "Work pool → worker poll → flow infrastructure"
        enriched.append(
            {
                **row,
                "Runtime unit": runtime_id,
                "Queue transition": queue_event,
                "State backend": runtime["state"],
                "Duration": "—" if row["Status"] == "UPSTREAM_FAILED" else f"{index * 3 + row['Attempts']}s",
                "Log": f"{runtime_id}: {row['Log']}",
            }
        )
    return enriched


def _dag_graph(task_text, dependency_text, rows):
    statuses = {row["Task"]: row["Status"] for row in rows}
    colors = {
        "SUCCESS": "#22c55e",
        "FAILED": "#ef4444",
        "UPSTREAM_FAILED": "#f59e0b",
    }
    tasks = [item.strip() for item in task_text.split(",") if item.strip()]
    lines = [
        "digraph DAG {",
        "rankdir=LR;",
        'graph [bgcolor="transparent" pad="0.2"];',
        'edge [color="#94a3b8" penwidth=1.5];',
        'node [shape=box style="rounded,filled" fontcolor=white color="#cbd5e1"];',
    ]
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


@st.fragment
def render_orchestration():
    username = st.session_state.get("user")
    _render_orchestration_styles()
    st.title("Orchestration")
    selected_view = lazy_tab(
        ["Airflow Fundamentals", "Workflow Execution Simulator", "Failure Operations"],
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
        _render_airflow_kubernetes_architecture()
        st.code(AIRFLOW_TEMPLATE, language="python")

    elif selected_view == "Workflow Execution Simulator":
        marker = f"orchestration_loaded::{username}"
        if not st.session_state.get(marker):
            saved = load_practice_state(username, "orchestration") or {}
            for key in ("dag_result", "dag_schedule", "dag_definition", "dag_runtime", "dag_orchestrator"):
                if key in saved:
                    st.session_state[key] = saved[key]
            st.session_state[marker] = True
        orchestrator = st.selectbox("Execution engine", list(ORCHESTRATOR_RUNTIME))
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
                st.session_state["dag_result"] = _enrich_runtime_rows(
                    simulate_dag(
                        tasks,
                        dependencies,
                        None if fail_task == "No failure" else fail_task,
                        retries,
                    ),
                    orchestrator,
                )
                st.session_state["dag_schedule"] = schedule
                st.session_state["dag_definition"] = (tasks, dependencies)
                st.session_state["dag_orchestrator"] = orchestrator
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
                        for key in ("dag_result", "dag_schedule", "dag_definition", "dag_runtime", "dag_orchestrator")
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
            active_orchestrator = st.session_state.get("dag_orchestrator", orchestrator)
            _render_runtime_flow(
                active_orchestrator,
                [item.strip() for item in graph_tasks.split(",") if item.strip()],
                rows,
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
