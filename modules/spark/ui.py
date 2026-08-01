import streamlit as st
import pandas as pd
from core.ai import ask_ai   # ✅ IMPORT LLM INTERFACE
from core.lazy_tabs import lazy_tab


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
                f"<div class='dm-box' style='text-align:center;padding:5px;margin:2px;border-radius:5px;font-size:12px;'>{comp}</div>",
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
            "<div class='dm-box' style='text-align:center;padding:5px;border-radius:5px;'>YARN / Kubernetes / Standalone</div>",
            unsafe_allow_html=True
        )
        st.markdown(
            "<div class='dm-box' style='text-align:center;padding:5px;border-radius:5px;'>Resources → Launch</div>",
            unsafe_allow_html=True
        )


# ---------------- CORE ----------------
def render_core(core_id, state, executor_id):
    is_skew = state["debug"] == "Skew"
    # Identify the hot core: Executor 2 (or any even index), Core 1
    is_hot = is_skew and (executor_id % 2 == 0 and core_id == 1)
    extra_class = "spark-mem-error" if is_hot else ""

    return f"""
    <div class='dm-box {extra_class}' style='width:65px;height:75px;
    border:1px solid #ccc;border-radius:6px;
    display:flex;flex-direction:column;align-items:center;justify-content:center;
    font-size:12px;'>
    Core {core_id}
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
        <div style='border:1px dashed #999;padding:8px;border-radius:8px;margin-top:8px;'>
            <div style='text-align:center;font-weight:bold;margin-bottom:8px;font-size:12px;'>Unified Memory</div>
            <div style='display:flex;gap:6px;'>
                <div class='dm-box {mem_class}' style='flex:1;text-align:center;font-size:10px;padding:6px;border-radius:6px;min-height:45px;display:flex;align-items:center;justify-content:center;font-weight:bold;'>
                    ⚡ Execution
                </div>
                <div class='dm-box {mem_class}' style='flex:1;text-align:center;font-size:10px;padding:6px;border-radius:6px;min-height:45px;display:flex;align-items:center;justify-content:center;font-weight:bold;'>
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


def _render_flink_simulator():
    st.subheader("Apache Flink Streaming Simulator")
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

    metrics = st.columns(5)
    metrics[0].metric("Job status", status)
    metrics[1].metric("Processing capacity", f"{capacity:,}/sec")
    metrics[2].metric("Utilization", f"{utilization:.1f}%")
    metrics[3].metric("Backpressure", f"{backpressure:,.0f}/sec")
    metrics[4].metric("TaskManagers", max(1, (parallelism + task_slots - 1) // task_slots))

    operators = ["Kafka Source", "Parse + Validate", "KeyBy", "Event-Time Window", "Warehouse Sink"]
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

    code_tab, checkpoints_tab, recovery_tab = st.tabs(
        ["Flink SQL", "Checkpoints & State", "Failure Recovery"]
    )
    with code_tab:
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
    with checkpoints_tab:
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
    with recovery_tab:
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


def render_spark():
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
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Area": "Primary execution",
                        "Spark": "Batch and micro-batch",
                        "Flink": "Native continuous streaming",
                    },
                    {
                        "Area": "State",
                        "Spark": "Dataset/cache and streaming state store",
                        "Flink": "Operator keyed state with checkpoints",
                    },
                    {
                        "Area": "Latency",
                        "Spark": "Seconds to minutes",
                        "Flink": "Milliseconds to seconds",
                    },
                    {
                        "Area": "Recovery",
                        "Spark": "Stage/task retry and lineage recomputation",
                        "Flink": "Checkpoint/savepoint restore",
                    },
                    {
                        "Area": "Best fit",
                        "Spark": "Large ETL, SQL, ML and unified batch",
                        "Flink": "Event-time, stateful, low-latency pipelines",
                    },
                ]
            ),
            width="stretch",
            hide_index=True,
        )