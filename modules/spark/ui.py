import streamlit as st
import pandas as pd
from core.ai import ask_ai   # ✅ IMPORT LLM INTERFACE
from core.lazy_tabs import lazy_tab


def _render_engine_styles():
    st.markdown(
        """
        <style>
        .engine-node, .spark-node, .flink-node {
            background: var(--secondary-background-color) !important;
            color: var(--text-color) !important;
            border: 1px solid color-mix(in srgb, var(--text-color) 30%, transparent) !important;
            border-radius: .55rem;
            box-sizing: border-box;
            overflow-wrap: anywhere;
        }
        .spark-node {
            padding: .55rem .45rem;
            min-height: 2.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            font-size: .78rem;
            line-height: 1.25;
        }
        .spark-core {
            width: 100%;
            min-height: 6rem;
            padding: .55rem .25rem;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: .35rem;
            font-size: .76rem;
            line-height: 1.2;
        }
        .spark-memory {
            padding: .65rem;
            margin-top: .55rem;
            border: 1px dashed color-mix(in srgb, var(--text-color) 45%, transparent);
            border-radius: .55rem;
        }
        .spark-memory-title {
            color: var(--text-color) !important;
            text-align: center;
            font-size: .75rem;
            font-weight: 700;
            margin-bottom: .5rem;
        }
        .spark-memory-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .4rem;
        }
        .flink-control-plane {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: .65rem;
            margin: .75rem 0;
        }
        .flink-node {
            padding: .75rem;
            min-height: 5rem;
        }
        .flink-node strong, .flink-node small, .flink-operator strong,
        .flink-operator small, .comparison-card strong, .comparison-card small {
            color: var(--text-color) !important;
        }
        .flink-node strong, .flink-operator strong {
            display: block;
            margin-bottom: .25rem;
        }
        .flink-node small, .flink-operator small, .comparison-card small {
            display: block;
            opacity: .82;
            line-height: 1.35;
        }
        .flink-pipeline {
            display: grid;
            grid-template-columns: repeat(9, minmax(0, 1fr));
            align-items: stretch;
            gap: .35rem;
            margin: .8rem 0;
        }
        .flink-operator {
            grid-column: span 1;
            background: color-mix(in srgb, var(--secondary-background-color) 86%, #2563eb 14%);
            color: var(--text-color) !important;
            border: 1px solid #3b82f6;
            border-radius: .55rem;
            padding: .65rem .45rem;
            min-height: 6rem;
            overflow-wrap: anywhere;
        }
        .flink-arrow {
            display: flex;
            align-items: center;
            justify-content: center;
            color: #60a5fa;
            font-size: 1.25rem;
        }
        .flink-workers {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
            gap: .65rem;
        }
        .comparison-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .8rem;
            margin: .7rem 0;
        }
        .comparison-card {
            background: var(--secondary-background-color);
            color: var(--text-color) !important;
            border: 1px solid color-mix(in srgb, var(--text-color) 28%, transparent);
            border-radius: .65rem;
            padding: .85rem;
        }
        .comparison-step {
            margin-top: .45rem;
            padding: .45rem .55rem;
            border-left: 3px solid #3b82f6;
            background: color-mix(in srgb, var(--secondary-background-color) 88%, #3b82f6 12%);
            color: var(--text-color) !important;
            font-size: .8rem;
        }
        @media (max-width: 900px) {
            .flink-control-plane, .comparison-grid { grid-template-columns: 1fr; }
            .flink-pipeline { grid-template-columns: 1fr; }
            .flink-arrow { transform: rotate(90deg); min-height: 1.5rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------- METRICS ----------------
def compute_metrics(state):
    time = 2
    shuffle_score = 0
    status = "Success"

    if state["transform"] == "Wide":
        time += 2
        shuffle_score += 1

    if state["join"] == "Shuffle":
        time += 2
        shuffle_score += 1

    if state["partition"] == "Repartition":
        time += 2
        shuffle_score += 1

    if state["partition"] == "Coalesce":
        time -= 1

    if state["debug"] == "Spill":
        time += 3

    if state["debug"] == "Skew":
        time += 2

    if state["debug"] == "OOM":
        status = "Failed"

    if shuffle_score == 0:
        shuffle = "None"
    elif shuffle_score == 1:
        shuffle = "Low"
    elif shuffle_score == 2:
        shuffle = "Medium"
    else:
        shuffle = "High"

    return max(1, time), shuffle, status


# ---------------- PARTITIONS ----------------
def render_partitions(state, core_id, executor_id):
    symbols = ["★", "#", "●"]

    pattern = symbols[(core_id + executor_id) % 3]
    count = 4

    is_wide = state["transform"] == "Wide"
    is_shuffle = state["join"] == "Shuffle"
    is_repartition = state["partition"] == "Repartition"
    is_coalesce = state["partition"] == "Coalesce"
    is_skew = state["debug"] == "Skew"

    # 🔥 cumulative effect
    if is_wide or is_shuffle or is_repartition:
        pattern = symbols[(core_id + executor_id + count) % 3]
        count += 2

    if is_wide and is_shuffle and is_repartition:
        count += 2

    if is_coalesce:
        count = max(2, count - 3)

    if is_skew:
        if (executor_id % 2 == 0 and core_id == 1):
            count += 3
        else:
            count = max(2, count - 2)

    blocks = ""
    for _ in range(count):
        blocks += f"<span style='font-size:10px;margin:1px'>{pattern}</span>"

    return f"<div>{blocks}</div>"


# ---------------- STAGE PIPELINE ----------------
def render_stage_pipeline(state):
    active = 1
    if state["transform"] == "Wide":
        active = 2
    if state["join"] == "Shuffle":
        active = 3

    def chip(name, idx):
        class_name = "spark-chip-active" if idx == active else "spark-chip-idle"
        return f"<span class='{class_name}' style='padding:3px 8px;border-radius:12px;font-size:11px'>{name}</span>"

    st.markdown(
        f"<div style='text-align:center;margin-top:6px'>{chip('Job',0)} → {chip('S1',1)} → {chip('S2',2)} → {chip('S3',3)}</div>",
        unsafe_allow_html=True
    )


# ---------------- DRIVER ----------------
def render_driver(state):
    with st.container(border=True):
        st.markdown("### Driver")

        components = [
            "SparkSession",
            "SparkContext",
            "Logical Plan",
            "Catalyst",
            "Physical Plan",
            "DAG Scheduler",
        ]

        for i, comp in enumerate(components):
            st.markdown(
                f"<div class='spark-node'>{comp}</div>",
                unsafe_allow_html=True
            )
            if i < len(components) - 1:
                st.markdown("<div style='text-align:center'>↓</div>", unsafe_allow_html=True)

        st.markdown("<div style='text-align:center'>Tasks → Executors</div>", unsafe_allow_html=True)
        render_stage_pipeline(state)


# ---------------- CLUSTER ----------------
def render_cluster():
    with st.container(border=True):
        st.markdown("### Cluster Manager")

        st.markdown(
            "<div class='spark-node'>YARN / Kubernetes / Standalone</div>",
            unsafe_allow_html=True
        )
        st.markdown(
            "<div class='spark-node'>Resources → Launch</div>",
            unsafe_allow_html=True
        )


# ---------------- CORE ----------------
def render_core(core_id, state, executor_id):
    is_skew = state["debug"] == "Skew"
    # Identify the hot core: Executor 2 (or any even index), Core 1
    is_hot = is_skew and (executor_id % 2 == 0 and core_id == 1)
    extra_class = "spark-mem-error" if is_hot else ""

    return f"""
    <div class='spark-node spark-core {extra_class}'>
    <strong>Core {core_id}</strong>
    {render_partitions(state, core_id, executor_id)}
    </div>
    """


# ---------------- EXECUTOR ----------------
def render_executor(idx, state):
    time, shuffle, status = compute_metrics(state)

    is_spill = state["debug"] == "Spill"
    is_oom = state["debug"] == "OOM"

    # Define classes for stateful styling
    mem_class = "spark-mem-error" if (is_spill or is_oom) else ""
    disk_class = "spark-disk-error" if is_oom else "spark-disk-spill" if is_spill else ""

    with st.container(border=True):
        st.markdown(f"Executor {idx}")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(render_core(1, state, idx), unsafe_allow_html=True)
        with c2:
            st.markdown(render_core(2, state, idx), unsafe_allow_html=True)

        st.markdown(f"""
        <div class='spark-memory'>
            <div class='spark-memory-title'>Unified Memory</div>
            <div class='spark-memory-grid'>
                <div class='spark-node {mem_class}'>
                    ⚡ Execution
                </div>
                <div class='spark-node {mem_class}'>
                    💾 Storage
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"<div class='spark-disk-box {disk_class}' style='text-align:center;margin-top:4px;padding:2px;border-radius:4px;'>Disk</div>", unsafe_allow_html=True)

        # ✅ FIXED SOLUTIONS
        if state["debug"] == "Spill":
            st.markdown("⬇ Disk I/O Active")
            st.markdown("Solution: Increase memory / Reduce cache / Tune partitions")

        if state["debug"] == "OOM":
            st.markdown("❌ Memory Exhausted")
            st.markdown("Solution: Increase executor memory / Reduce shuffle / Optimize joins")

        if state["debug"] == "Skew":
            st.markdown("⚙ AQE Skew Split")
            st.markdown("Solution: Enable AQE / Handle skewed keys")

        status_icon = "✔" if status == "Success" else "❌"
        status_class = "text-success" if status == "Success" else "text-error"
        st.markdown(f"""
        <div style='font-size:12px;margin-top:4px;'>
            ⏱ {time}s | 🔀 {shuffle} | <span class='{status_class}' style='font-weight:bold;'>{status_icon}</span>
        </div>
        """, unsafe_allow_html=True)


# ---------------- WORKERS ----------------
def render_workers(state):
    with st.container(border=True):
        st.markdown("### Worker Nodes")

        cols = st.columns(state["executors"])
        for i in range(state["executors"]):
            with cols[i]:
                render_executor(i + 1, state)

        if state["transform"] == "Wide":
            st.markdown("🔴 Shuffle → Data movement happening")

        if state["join"] == "Broadcast":
            st.markdown("🟢 Broadcast → No shuffle")

# ---------------- AI CHAT ----------------        
def render_ai_chat():
    st.markdown("---")
    st.subheader("💬 Spark AI Assistant")

    # ---------------- SESSION INIT ----------------
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if "last_processed" not in st.session_state:
        st.session_state.last_processed = ""

    # ---------------- DISPLAY CHAT (TOP DOWN LIKE CHATGPT) ----------------
    for chat in st.session_state.chat_history:
        with st.chat_message("user"):
            st.markdown(chat["user"])

        with st.chat_message("assistant"):
            st.markdown(chat["assistant"])

    # ---------------- INPUT ----------------
    user_input = st.chat_input("Ask anything about Spark...")

    # ---------------- PROCESS ----------------
    if user_input:
        # show user immediately
        with st.chat_message("user"):
            st.markdown(user_input)

        # prevent duplicate processing
        if user_input != st.session_state.last_processed:
            st.session_state.last_processed = user_input

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response = ask_ai(user_input)

                st.markdown(response)

            # save history
            st.session_state.chat_history.append({
                "user": user_input,
                "assistant": response
            })


# ---------------- MAIN ----------------
def render_architecture_simulator(state):
    c1, c2, c3 = st.columns([1, 1, 3])

    with c1:
        render_driver(state)

    with c2:
        render_cluster()

    with c3:
        render_workers(state)


# ---------------- ENTRY ----------------
def _render_spark_simulator():
    # ---------------- CONTROLS ----------------
    c1, c2, c3, c4, c5 = st.columns(5)

    state = {
        "transform": c1.selectbox(
            "Transform",
            ["Narrow", "Wide"],
            key="transform_select"
        ),
        "partition": c2.selectbox(
            "Partition",
            ["None", "Repartition", "Coalesce"],
            key="partition_select"
        ),
        "join": c3.selectbox(
            "Join",
            ["Broadcast", "Shuffle"],
            key="join_select"
        ),
        "debug": c4.selectbox(
            "Debug",
            ["Normal", "Spill", "OOM", "Skew"],
            key="debug_select"
        ),
        "executors": c5.slider(
            "Executors",
            1, 4, 2,
            key="executor_slider"
        ),
    }

    st.markdown("---")

    # ---------------- SPARK ARCHITECTURE ----------------
    render_architecture_simulator(state)

    # ---------------- AI CHAT (ADD-ON ONLY) ----------------
    render_ai_chat()


def _render_flink_topology(
    operators,
    status,
    parallelism,
    task_slots,
    task_managers,
    checkpoint_seconds,
    backpressure,
    failure,
):
    coordinator_status = "Checkpoint retry" if failure == "Checkpoint timeout" else "Coordinating"
    st.markdown(
        f"""
        <div class="flink-control-plane">
          <div class="flink-node">
            <strong>Dispatcher / REST API</strong>
            <small>Accepts the submitted job and starts a JobManager.</small>
          </div>
          <div class="flink-node">
            <strong>JobManager · {status}</strong>
            <small>Builds the JobGraph, schedules operators and coordinates recovery.</small>
          </div>
          <div class="flink-node">
            <strong>Checkpoint Coordinator</strong>
            <small>{coordinator_status} · every {checkpoint_seconds}s · exactly-once barriers</small>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    operator_cards = []
    for index, operator in enumerate(operators):
        operator_status = status
        pressure = "High backpressure" if backpressure and index >= 3 else "Healthy"
        if failure == "Sink slowdown" and operator == "Warehouse Sink":
            operator_status = "DEGRADED"
            pressure = "Sink is throttling upstream operators"
        operator_cards.append(
            f"""
            <div class="flink-operator">
              <strong>{operator}</strong>
              <small>Parallel subtasks: {parallelism}</small>
              <small>{operator_status} · {pressure}</small>
            </div>
            """
        )
        if index < len(operators) - 1:
            operator_cards.append('<div class="flink-arrow">→</div>')
    st.markdown(
        f'<div class="flink-pipeline">{"".join(operator_cards)}</div>',
        unsafe_allow_html=True,
    )

    workers = []
    remaining_subtasks = parallelism
    for index in range(task_managers):
        occupied = min(task_slots, remaining_subtasks)
        remaining_subtasks = max(0, remaining_subtasks - occupied)
        worker_status = "RESTARTING" if failure == "TaskManager failure" and index == 0 else "RUNNING"
        slots = " ".join("●" if slot < occupied else "○" for slot in range(task_slots))
        workers.append(
            f'<div class="flink-node">'
            f"<strong>TaskManager {index + 1} · {worker_status}</strong>"
            f"<small>Slots: {slots}</small>"
            f"<small>{occupied}/{task_slots} occupied · managed keyed state</small>"
            f"</div>"
        )
    st.markdown(
        f'<div class="flink-workers">{"".join(workers)}</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Checkpoint barriers flow with records through every operator. "
        "On failure, source offsets and keyed state restore together from the latest completed checkpoint."
    )


def _render_flink_simulator():
    st.subheader("Apache Flink Streaming Runtime")
    controls = st.columns(5)
    source_rate = controls[0].number_input(
        "Input events/sec",
        min_value=100,
        max_value=10_000_000,
        value=25_000,
        step=1000,
    )
    parallelism = controls[1].slider("Parallelism", 1, 64, 8)
    task_slots = controls[2].slider("Task slots", 1, 16, 4)
    checkpoint_seconds = controls[3].number_input(
        "Checkpoint interval (sec)",
        min_value=5,
        max_value=600,
        value=30,
    )
    failure = controls[4].selectbox(
        "Failure injection",
        ["None", "TaskManager failure", "Sink slowdown", "Checkpoint timeout"],
    )

    capacity = parallelism * 4_000
    utilization = min(100.0, source_rate / capacity * 100)
    backpressure = max(0.0, source_rate - capacity)
    status = "RUNNING"
    if failure == "Checkpoint timeout":
        status = "RESTARTING"
    elif failure == "TaskManager failure":
        status = "RECOVERING"

    task_managers = max(1, (parallelism + task_slots - 1) // task_slots)
    metrics = st.columns(5)
    metrics[0].metric("Job status", status)
    metrics[1].metric("Processing capacity", f"{capacity:,}/sec")
    metrics[2].metric("Utilization", f"{utilization:.1f}%")
    metrics[3].metric("Backpressure", f"{backpressure:,.0f}/sec")
    metrics[4].metric("TaskManagers", task_managers)

    operators = ["Kafka Source", "Parse + Validate", "KeyBy", "Event-Time Window", "Warehouse Sink"]
    _render_flink_topology(
        operators,
        status,
        parallelism,
        task_slots,
        task_managers,
        checkpoint_seconds,
        backpressure,
        failure,
    )

    operator_rows = []
    for index, operator in enumerate(operators):
        operator_status = status
        pressure = "HIGH" if backpressure and index >= 3 else "LOW"
        if failure == "Sink slowdown" and operator == "Warehouse Sink":
            operator_status = "DEGRADED"
            pressure = "HIGH"
        operator_rows.append(
            {
                "Operator": operator,
                "Parallelism": parallelism,
                "Status": operator_status,
                "Backpressure": pressure,
                "Watermark lag": f"{max(0, int(backpressure / 1000) + index)}s",
            }
        )
    st.dataframe(pd.DataFrame(operator_rows), width="stretch", hide_index=True)

    selected_detail = lazy_tab(
        ["Flink SQL", "Checkpoints & State", "Failure Recovery"],
        "flink_active_detail",
        "Flink detail",
    )
    if selected_detail == "Flink SQL":
        st.code(
            """CREATE TABLE orders_source (
  order_id BIGINT,
  customer_id BIGINT,
  amount DECIMAL(12,2),
  event_time TIMESTAMP(3),
  WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
) WITH ('connector'='kafka', 'topic'='orders');

SELECT
  customer_id,
  window_start,
  SUM(amount) AS revenue
FROM TABLE(
  TUMBLE(TABLE orders_source, DESCRIPTOR(event_time), INTERVAL '5' MINUTES)
)
GROUP BY customer_id, window_start;""",
            language="sql",
        )
    elif selected_detail == "Checkpoints & State":
        checkpoint_rows = [
            {
                "Checkpoint": index,
                "Status": "FAILED" if failure == "Checkpoint timeout" and index == 3 else "COMPLETED",
                "Duration": f"{1.2 + index * 0.3:.1f}s",
                "State size": f"{2.5 + index * 0.8:.1f} GiB",
                "Interval": f"{checkpoint_seconds}s",
            }
            for index in range(1, 5)
        ]
        st.dataframe(pd.DataFrame(checkpoint_rows), width="stretch", hide_index=True)
    else:
        st.write(
            "Flink restores operator state and source offsets from the latest completed checkpoint. "
            "Exactly-once sinks commit only after a successful checkpoint."
        )
        if failure == "None":
            st.success("No failure injected. Select a failure to inspect recovery behavior.")
        else:
            st.warning(
                f"{failure}: cancel affected tasks → restore checkpoint → reconnect source/sink → "
                "resume from stored offsets."
            )


COMPARISON_SCENARIOS = {
    "Nightly lakehouse ETL": {
        "records": 750_000_000,
        "spark_plan": [
            "Read partitioned object-store files",
            "Whole-stage code generation + adaptive shuffle",
            "Write optimized Iceberg files and commit snapshot",
        ],
        "flink_plan": [
            "Bounded source enumerates all files",
            "Pipelined operators process the bounded stream",
            "Final checkpoint commits the sink",
        ],
        "recommendation": "Spark",
        "reason": "Its SQL optimizer, mature batch ecosystem and adaptive execution fit a finite large ETL run.",
    },
    "Fraud detection stream": {
        "records": 120_000,
        "spark_plan": [
            "Collect events into a micro-batch trigger",
            "Update streaming state store",
            "Commit one output batch",
        ],
        "flink_plan": [
            "Process each event continuously",
            "Update keyed customer state and event-time timers",
            "Emit alert without waiting for a batch boundary",
        ],
        "recommendation": "Flink",
        "reason": "Native event-at-a-time processing and timers provide predictable low latency.",
    },
    "CDC materialized view": {
        "records": 45_000,
        "spark_plan": [
            "Read available CDC records per trigger",
            "Merge the micro-batch into the target",
            "Checkpoint source offsets",
        ],
        "flink_plan": [
            "Consume ordered change events continuously",
            "Maintain keyed table state",
            "Checkpoint source offsets and two-phase sink commits",
        ],
        "recommendation": "Flink",
        "reason": "Continuous stateful processing handles changelogs and exactly-once sinks naturally.",
    },
    "Feature engineering and ML": {
        "records": 300_000_000,
        "spark_plan": [
            "Read training history into DataFrames",
            "Apply distributed feature transforms",
            "Train/evaluate using the integrated ML ecosystem",
        ],
        "flink_plan": [
            "Treat history as a bounded stream",
            "Compute online features in operators",
            "Export features to an external training system",
        ],
        "recommendation": "Spark",
        "reason": "Unified SQL, DataFrame and ML libraries reduce the number of systems required.",
    },
}


def _render_execution_plan(title, engine, steps, runtime, recovery):
    step_html = "".join(
        f'<div class="comparison-step">{index}. {step}</div>'
        for index, step in enumerate(steps, start=1)
    )
    return (
        f'<div class="comparison-card">'
        f"<strong>{title}</strong>"
        f"<small>{engine} execution plan</small>"
        f"{step_html}"
        f'<div class="comparison-step"><b>Estimated behavior:</b> {runtime}</div>'
        f'<div class="comparison-step"><b>Failure recovery:</b> {recovery}</div>'
        f"</div>"
    )


def _render_spark_flink_comparison():
    st.subheader("Workload Decision & Failure Simulator")
    controls = st.columns(4)
    scenario_name = controls[0].selectbox("Workload", list(COMPARISON_SCENARIOS))
    latency_target = controls[1].selectbox(
        "Required latency",
        ["Under 100 ms", "Under 5 seconds", "Minutes", "Hours"],
    )
    state_size = controls[2].select_slider(
        "State size",
        ["Stateless", "Small", "Large", "Very large"],
        value="Large",
    )
    failure = controls[3].selectbox(
        "Failure test",
        ["Executor / TaskManager loss", "Driver / JobManager loss", "Sink outage", "No failure"],
    )
    scenario = COMPARISON_SCENARIOS[scenario_name]
    throughput = scenario["records"]
    spark_trigger_ms = 1000 if "second" in latency_target else 5000
    spark_runtime = (
        f"{throughput:,} records per batch run"
        if "ETL" in scenario_name or "ML" in scenario_name
        else f"micro-batches every {spark_trigger_ms / 1000:g}s"
    )
    flink_runtime = (
        f"continuous processing at approximately {throughput:,} events/sec"
        if "ETL" not in scenario_name and "ML" not in scenario_name
        else f"bounded streaming over {throughput:,} records"
    )
    spark_recovery = {
        "Executor / TaskManager loss": "Retry lost tasks; recompute missing partitions from lineage.",
        "Driver / JobManager loss": "Restart the query/job from checkpoint metadata.",
        "Sink outage": "Retry the failed stage or micro-batch; idempotent sink is required.",
        "No failure": "Stages complete and output commits after successful tasks.",
    }[failure]
    flink_recovery = {
        "Executor / TaskManager loss": "Restart affected region and restore keyed state from checkpoint.",
        "Driver / JobManager loss": "HA JobManager recovers JobGraph and latest checkpoint.",
        "Sink outage": "Backpressure propagates; two-phase sink transaction waits or rolls back.",
        "No failure": "Checkpoint barriers snapshot state while records continue flowing.",
    }[failure]
    st.markdown(
        '<div class="comparison-grid">'
        + _render_execution_plan("Spark", "DAG / stages / tasks", scenario["spark_plan"], spark_runtime, spark_recovery)
        + _render_execution_plan("Flink", "JobGraph / operators / subtasks", scenario["flink_plan"], flink_runtime, flink_recovery)
        + "</div>",
        unsafe_allow_html=True,
    )

    recommendation = scenario["recommendation"]
    recommendation_reason = scenario["reason"]
    if latency_target == "Under 100 ms":
        recommendation = "Flink"
        recommendation_reason = "The latency target requires continuous event-at-a-time execution."
    elif latency_target in {"Minutes", "Hours"} and state_size in {"Stateless", "Small"}:
        recommendation = "Spark"
        recommendation_reason = "The relaxed latency target favors Spark's batch efficiency and broader SQL ecosystem."
    st.success(f"Recommended engine: {recommendation}. {recommendation_reason}")

    selected_detail = lazy_tab(
        ["Runtime mechanics", "State & correctness", "Operational trade-offs"],
        "spark_flink_comparison_detail",
        "Comparison detail",
    )
    detail_rows = {
        "Runtime mechanics": [
            {"Concern": "Scheduling unit", "Spark": "Job → stages → tasks", "Flink": "JobGraph → operators → subtasks"},
            {"Concern": "Data exchange", "Spark": "Shuffle boundaries create stages", "Flink": "Records flow through pipelined network edges"},
            {"Concern": "Latency model", "Spark": "Batch or micro-batch trigger", "Flink": "Continuous event-at-a-time"},
        ],
        "State & correctness": [
            {"Concern": "State placement", "Spark": "Executor state store / cache", "Flink": "Operator keyed or broadcast state"},
            {"Concern": "Consistency", "Spark": "Offset + batch commit logs", "Flink": "Distributed checkpoint barriers"},
            {"Concern": "Late events", "Spark": "Watermark cleans state by trigger", "Flink": "Watermarks, timers and allowed lateness"},
        ],
        "Operational trade-offs": [
            {"Concern": "Scaling", "Spark": "Dynamic allocation between task waves", "Flink": "Rescale with savepoint and redistributed state"},
            {"Concern": "Upgrade", "Spark": "Restart job/query from checkpoint", "Flink": "Stop with savepoint, upgrade, restore"},
            {"Concern": "Best operations fit", "Spark": "Finite ETL and broad analytics", "Flink": "Always-on, stateful event processing"},
        ],
    }
    st.dataframe(pd.DataFrame(detail_rows[selected_detail]), width="stretch", hide_index=True)


@st.fragment
def render_spark():
    _render_engine_styles()
    st.title("Spark / Flink")
    selected = lazy_tab(
        ["Spark Batch Simulator", "Flink Streaming Simulator", "Spark vs Flink"],
        "spark_flink_active_workspace",
        "Processing engine workspace",
    )
    if selected == "Spark Batch Simulator":
        _render_spark_simulator()
    elif selected == "Flink Streaming Simulator":
        _render_flink_simulator()
    else:
        _render_spark_flink_comparison()