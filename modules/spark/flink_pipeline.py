import math

import pandas as pd
import streamlit as st

from core.lazy_tabs import lazy_tab


def calculate_flink_execution(
    input_rate,
    parallelism,
    transformation,
    exchange,
    checkpoint_seconds,
    failure,
):
    per_subtask_capacity = 4_000
    capacity = parallelism * per_subtask_capacity
    exchange_cost = {
        "Forward": 1.0,
        "KeyBy": 0.82,
        "Rebalance": 0.88,
        "Broadcast": 0.70,
    }[exchange]
    transformation_cost = {
        "Stateless Map / Filter": 1.0,
        "Keyed Aggregation": 0.86,
        "Event-Time Window": 0.76,
        "Async I/O Enrichment": 0.68,
    }[transformation]
    effective_capacity = int(capacity * exchange_cost * transformation_cost)
    if failure == "Slow sink / backpressure":
        effective_capacity = int(effective_capacity * 0.45)
    elif failure == "TaskManager failure":
        effective_capacity = int(
            effective_capacity * max(0, parallelism - 2) / max(1, parallelism)
        )

    processed_rate = min(input_rate, effective_capacity)
    backpressure = max(0, input_rate - processed_rate)
    checkpoint_status = (
        "FAILED" if failure == "Checkpoint timeout" else "COMPLETED"
    )
    job_status = {
        "TaskManager failure": "RECOVERING",
        "Checkpoint timeout": "RUNNING",
    }.get(failure, "RUNNING")
    stateful = transformation in {"Keyed Aggregation", "Event-Time Window"}
    state_size_mib = (
        int((input_rate * checkpoint_seconds / 1_000) * (1.8 if stateful else 0.2))
    )
    task_managers = max(1, math.ceil(parallelism / 4))
    network_pattern = {
        "Forward": "One-to-one local edge; records stay in the same channel.",
        "KeyBy": "Hash partition by key; records cross the network to keyed subtasks.",
        "Rebalance": "Round-robin redistribution across all downstream subtasks.",
        "Broadcast": "Every record is copied to every downstream subtask.",
    }[exchange]
    return {
        "capacity": capacity,
        "effective_capacity": effective_capacity,
        "processed_rate": processed_rate,
        "backpressure": backpressure,
        "checkpoint_status": checkpoint_status,
        "checkpoint_seconds": checkpoint_seconds,
        "job_status": job_status,
        "stateful": stateful,
        "state_size_mib": state_size_mib,
        "task_managers": task_managers,
        "network_pattern": network_pattern,
    }


def _init_flink_runtime():
    if "flink_execution_runtime" not in st.session_state:
        st.session_state["flink_execution_runtime"] = {
            "submitted": False,
            "checkpoint_id": 18,
            "last_successful_checkpoint": 18,
        }
    return st.session_state["flink_execution_runtime"]


def _render_job_manager(snapshot, checkpoint_seconds):
    with st.container(border=True):
        st.markdown("### JobManager")
        st.caption("Flink control plane")
        manager_cols = st.columns(3)
        with manager_cols[0]:
            with st.container(border=True):
                st.markdown("**Dispatcher**")
                st.caption("Accepts the submitted JobGraph")
        with manager_cols[1]:
            with st.container(border=True):
                st.markdown("**ResourceManager**")
                st.caption("Allocates TaskManager slots")
        with manager_cols[2]:
            with st.container(border=True):
                st.markdown("**JobMaster**")
                st.caption("Schedules subtasks and recovery")
        st.divider()
        st.markdown("**Checkpoint Coordinator**")
        st.write(
            f"Injects barriers every {checkpoint_seconds}s · "
            f"latest checkpoint **{snapshot['checkpoint_status']}**"
        )
        st.metric("Job status", snapshot["job_status"])


def _render_operator_graph(
    source,
    transformation,
    exchange,
    sink,
    parallelism,
    snapshot,
):
    st.markdown("### JobGraph → ExecutionGraph")
    graph = st.columns([1, 0.18, 1.2, 0.18, 1.2, 0.18, 1])
    cards = [
        (0, "Source", source, f"{parallelism} source subtasks"),
        (
            2,
            "Transformation",
            transformation,
            "Keyed state" if snapshot["stateful"] else "Operator chain eligible",
        ),
        (
            4,
            "Network exchange",
            exchange,
            snapshot["network_pattern"],
        ),
        (6, "Sink", sink, f"{parallelism} sink subtasks"),
    ]
    for index, heading, value, caption in cards:
        with graph[index]:
            with st.container(border=True):
                st.markdown(f"**{heading}**")
                st.write(value)
                st.caption(caption)
    for index in (1, 3, 5):
        graph[index].markdown(
            "<div style='text-align:center;padding-top:2.6rem;font-size:1.3rem'>→</div>",
            unsafe_allow_html=True,
        )


def _render_task_managers(parallelism, snapshot, failure):
    st.markdown("### TaskManagers and Task Slots")
    columns = st.columns(snapshot["task_managers"])
    remaining = parallelism
    for index, column in enumerate(columns, start=1):
        occupied = min(4, remaining)
        remaining -= occupied
        failed = failure == "TaskManager failure" and index == 1
        with column:
            with st.container(border=True):
                st.markdown(f"**TaskManager {index}**")
                st.caption("RESTARTING" if failed else "RUNNING")
                slots = st.columns(4)
                for slot_index, slot in enumerate(slots, start=1):
                    slot.metric(
                        f"Slot {slot_index}",
                        "●" if slot_index <= occupied and not failed else "○",
                    )
                st.write(
                    f"{0 if failed else occupied}/4 occupied · "
                    "network buffers + managed state"
                )


def _render_checkpoint_detail(snapshot, runtime, failure):
    checkpoint_id = runtime["checkpoint_id"]
    rows = []
    for current in range(max(1, checkpoint_id - 3), checkpoint_id + 1):
        latest = current == checkpoint_id
        status = snapshot["checkpoint_status"] if latest else "COMPLETED"
        rows.append(
            {
                "Checkpoint": current,
                "Barrier alignment": (
                    "TIMEOUT"
                    if latest and failure == "Checkpoint timeout"
                    else "ALIGNED"
                ),
                "Operator state": f"{snapshot['state_size_mib']:,} MiB",
                "Source position": f"offset-{current * 10_000}",
                "Sink transaction": "ABORTED" if status == "FAILED" else "COMMITTED",
                "Status": status,
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if snapshot["checkpoint_status"] == "COMPLETED":
        runtime["last_successful_checkpoint"] = checkpoint_id
        st.success(
            f"Checkpoint {checkpoint_id} captured source position, operator state, "
            "timers and sink transaction consistently."
        )
    else:
        st.error(
            f"Checkpoint {checkpoint_id} failed. Recovery uses checkpoint "
            f"{runtime['last_successful_checkpoint']} and replays subsequent records."
        )


def _render_execution_details(snapshot, runtime, transformation, exchange, failure):
    detail = lazy_tab(
        ["Transformation effect", "Checkpoint & recovery", "Backpressure", "Flink SQL"],
        "flink_execution_detail",
        "Flink execution detail",
    )
    if detail == "Transformation effect":
        if transformation == "Stateless Map / Filter":
            st.success(
                "Stateless operators can chain in one task and avoid materialized state."
            )
        elif transformation == "Keyed Aggregation":
            st.info(
                "KeyBy routes equal keys to the same subtask. Each subtask maintains "
                "isolated keyed state that checkpoints independently."
            )
        elif transformation == "Event-Time Window":
            st.info(
                "Watermarks advance event time. Window state and timers remain until "
                "the watermark closes the window."
            )
        else:
            st.warning(
                "Async requests increase in-flight work. Ordered mode can propagate "
                "latency; unordered mode improves throughput when ordering is unnecessary."
            )
        st.write(f"Exchange effect: **{snapshot['network_pattern']}**")
        st.metric("Estimated managed state", f"{snapshot['state_size_mib']:,} MiB")
    elif detail == "Checkpoint & recovery":
        _render_checkpoint_detail(snapshot, runtime, failure)
    elif detail == "Backpressure":
        if snapshot["backpressure"]:
            st.error(
                f"Backpressure: {snapshot['backpressure']:,} records/sec cannot leave "
                "the current operator chain. Upstream network buffers fill and source "
                "consumption slows."
            )
        else:
            st.success("No backpressure. Every operator keeps pace with the source.")
        st.progress(
            min(
                1.0,
                snapshot["processed_rate"] / max(1, snapshot["effective_capacity"]),
            )
        )
        st.write(
            f"Processed **{snapshot['processed_rate']:,}/sec** from effective capacity "
            f"**{snapshot['effective_capacity']:,}/sec**."
        )
    else:
        partition_sql = {
            "Forward": "",
            "KeyBy": "GROUP BY customer_id",
            "Rebalance": "/* rebalance before the next operator */",
            "Broadcast": "/* broadcast reference stream */",
        }[exchange]
        st.code(
            f"""CREATE TABLE source_stream (...) WITH (
  'connector' = '<selected source connector>'
);

CREATE TABLE sink_stream (...) WITH (
  'connector' = '<selected sink connector>'
);

INSERT INTO sink_stream
SELECT customer_id, COUNT(*) AS event_count
FROM source_stream
{partition_sql};""",
            language="sql",
        )


def render_flink_execution_simulator():
    st.subheader("Apache Flink Execution Simulator")
    st.caption(
        "The source and sink are interchangeable. This view focuses strictly on "
        "how Flink builds, partitions, executes, checkpoints and recovers the job."
    )
    controls = st.columns(6)
    source = controls[0].selectbox(
        "Source",
        ["Kafka", "PostgreSQL CDC", "Streaming API", "File / Object Store"],
    )
    transformation = controls[1].selectbox(
        "Transformation",
        [
            "Stateless Map / Filter",
            "Keyed Aggregation",
            "Event-Time Window",
            "Async I/O Enrichment",
        ],
    )
    exchange = controls[2].selectbox(
        "Partition / exchange",
        ["Forward", "KeyBy", "Rebalance", "Broadcast"],
    )
    sink = controls[3].selectbox(
        "Sink",
        ["Database", "Kafka", "Lakehouse Table", "REST API"],
    )
    parallelism = controls[4].slider("Parallelism", 1, 16, 4)
    failure = controls[5].selectbox(
        "Runtime condition",
        [
            "Normal",
            "Slow sink / backpressure",
            "TaskManager failure",
            "Checkpoint timeout",
        ],
    )
    execution_controls = st.columns(2)
    input_rate = execution_controls[0].slider(
        "Input records/sec",
        1_000,
        100_000,
        20_000,
        1_000,
    )
    checkpoint_seconds = execution_controls[1].slider(
        "Checkpoint interval (seconds)",
        5,
        120,
        30,
        5,
    )

    runtime = _init_flink_runtime()
    actions = st.columns(3)
    if actions[0].button("Submit Flink job", width="stretch"):
        runtime["submitted"] = True
    if actions[1].button(
        "Trigger checkpoint",
        width="stretch",
        disabled=not runtime["submitted"],
    ):
        runtime["checkpoint_id"] += 1
    if actions[2].button(
        "Restore last checkpoint",
        width="stretch",
        disabled=not runtime["submitted"],
    ):
        runtime["checkpoint_id"] = runtime["last_successful_checkpoint"]
    if not runtime["submitted"]:
        st.info("Submit the job to activate checkpoint and recovery controls.")

    snapshot = calculate_flink_execution(
        input_rate,
        parallelism,
        transformation,
        exchange,
        checkpoint_seconds,
        failure,
    )
    metrics = st.columns(5)
    metrics[0].metric("Job", snapshot["job_status"])
    metrics[1].metric("Processed", f"{snapshot['processed_rate']:,}/sec")
    metrics[2].metric("Backpressure", f"{snapshot['backpressure']:,}/sec")
    metrics[3].metric("Checkpoint", snapshot["checkpoint_status"])
    metrics[4].metric("TaskManagers", snapshot["task_managers"])

    _render_job_manager(snapshot, checkpoint_seconds)
    _render_operator_graph(
        source,
        transformation,
        exchange,
        sink,
        parallelism,
        snapshot,
    )
    _render_task_managers(parallelism, snapshot, failure)
    _render_execution_details(
        snapshot,
        runtime,
        transformation,
        exchange,
        failure,
    )


def compact_flink_diagram_html(processing, runtime_effect, parallel_tasks):
    operation = {
        "Simple transform": "Map / Filter",
        "Group by key": "KeyBy + State",
        "Time window": "Window + Timer",
    }[processing]
    effect_class = {
        "Normal flow": "flink-compact-normal",
        "Backpressure": "flink-compact-slow",
        "Task failure": "flink-compact-failed",
        "Checkpoint failure": "flink-compact-checkpoint-failed",
    }[runtime_effect]
    effect_text = {
        "Normal flow": "Records move continuously; checkpoints complete.",
        "Backpressure": "The sink is slow, so record movement slows back toward the source.",
        "Task failure": "The failed task restarts and restores its latest successful checkpoint.",
        "Checkpoint failure": "Records continue, but state remains protected by the previous checkpoint.",
    }[runtime_effect]
    return f"""
    <style>
      .flink-compact {{
        display:grid;
        grid-template-columns:12% 5% 16% 5% 45% 5% 12%;
        align-items:stretch;
        gap:.25rem;
        width:100%;
        padding:.65rem;
        color:var(--text-color);
        background:var(--secondary-background-color);
        border:1.5px solid #64748b;
        border-radius:.65rem;
        box-sizing:border-box;
      }}
      .flink-compact-box {{
        min-width:0;
        padding:.55rem .35rem;
        display:flex;
        flex-direction:column;
        align-items:center;
        justify-content:center;
        text-align:center;
        background:var(--background-color);
        border:1.5px solid #64748b;
        border-radius:.45rem;
        font-size:.72rem;
        line-height:1.25;
        box-sizing:border-box;
      }}
      .flink-compact-box strong {{font-size:.78rem;margin-bottom:.2rem}}
      .flink-compact-arrow {{
        position:relative;
        display:flex;
        align-items:center;
        justify-content:center;
        color:#2563eb;
        font-size:1.25rem;
        overflow:hidden;
      }}
      .flink-compact-arrow::after {{
        content:"";
        position:absolute;
        width:.48rem;
        height:.48rem;
        border-radius:50%;
        background:#2563eb;
        animation:flink-record 1.6s linear infinite;
      }}
      .flink-compact-task {{
        min-width:0;
        padding:.45rem;
        background:var(--background-color);
        border:2px solid #64748b;
        border-radius:.5rem;
        box-sizing:border-box;
      }}
      .flink-task-title {{
        margin-bottom:.35rem;
        text-align:center;
        font-size:.76rem;
        font-weight:800;
      }}
      .flink-task-flow {{
        display:grid;
        grid-template-columns:repeat(7,minmax(0,1fr));
        align-items:center;
        gap:.2rem;
      }}
      .flink-task-step {{
        min-width:0;
        padding:.4rem .2rem;
        text-align:center;
        background:var(--secondary-background-color);
        border:1px solid #64748b;
        border-radius:.35rem;
        font-size:.65rem;
        line-height:1.15;
        overflow-wrap:anywhere;
      }}
      .flink-mini-arrow {{text-align:center;color:#2563eb;font-weight:900}}
      .flink-checkpoint-strip {{
        margin-top:.4rem;
        padding:.3rem;
        text-align:center;
        background:var(--secondary-background-color);
        border:1px dashed #16a34a;
        border-radius:.35rem;
        font-size:.64rem;
        line-height:1.2;
      }}
      .flink-compact-note {{
        grid-column:1/-1;
        margin-top:.15rem;
        text-align:center;
        font-size:.69rem;
        font-weight:650;
      }}
      .flink-compact-slow .flink-compact-arrow::after {{
        background:#f59e0b;
        animation-duration:4s;
        animation-direction:alternate;
      }}
      .flink-compact-failed .flink-compact-task {{border-color:#dc2626}}
      .flink-compact-failed .flink-compact-arrow::after {{
        background:#dc2626;
        animation:none;
      }}
      .flink-compact-checkpoint-failed .flink-checkpoint-strip {{
        color:#dc2626;
        border-color:#dc2626;
      }}
      @keyframes flink-record {{
        from {{transform:translateX(-1.2rem)}}
        to {{transform:translateX(1.2rem)}}
      }}
      @media(max-width:850px) {{
        .flink-compact {{grid-template-columns:1fr}}
        .flink-compact-arrow {{min-height:1.5rem;transform:rotate(90deg)}}
        .flink-compact-note {{grid-column:auto}}
      }}
    </style>
    <div class="flink-compact {effect_class}">
      <div class="flink-compact-box">
        <strong>Input + Job</strong>
        <span>records arrive<br>job is submitted</span>
      </div>
      <div class="flink-compact-arrow">→</div>
      <div class="flink-compact-box">
        <strong>JobManager</strong>
        <span>schedules tasks<br>coordinates recovery</span>
      </div>
      <div class="flink-compact-arrow">→</div>
      <div class="flink-compact-task">
        <div class="flink-task-title">TaskManagers · {parallel_tasks} parallel task(s)</div>
        <div class="flink-task-flow">
          <div class="flink-task-step">Source<br>reads records</div>
          <div class="flink-mini-arrow">→</div>
          <div class="flink-task-step">{operation}</div>
          <div class="flink-mini-arrow">→</div>
          <div class="flink-task-step">Managed State<br>when needed</div>
          <div class="flink-mini-arrow">→</div>
          <div class="flink-task-step">Sink<br>writes result</div>
        </div>
        <div class="flink-checkpoint-strip">
          Checkpoint barriers snapshot source position + operator state + sink progress
        </div>
      </div>
      <div class="flink-compact-arrow">→</div>
      <div class="flink-compact-box">
        <strong>Output</strong>
        <span>processed result<br>continues downstream</span>
      </div>
      <div class="flink-compact-note">{effect_text}</div>
    </div>
    """


def matrix_flink_diagram_html(processing, runtime_effect, parallel_tasks):
    operation = {
        "Simple transform": "Map / Filter",
        "Group by key": "KeyBy + State",
        "Time window": "Window + Timer",
    }[processing]
    effect_class = {
        "Normal flow": "flink-matrix-normal",
        "Backpressure": "flink-matrix-slow",
        "Task failure": "flink-matrix-failed",
        "Checkpoint failure": "flink-matrix-checkpoint-failed",
    }[runtime_effect]
    effect_text = {
        "Normal flow": "Records cross Source → Transform → Sink continuously.",
        "Backpressure": "A slow sink pushes pressure backward through the TaskManager flow.",
        "Task failure": "Task execution pauses, then restores state from the latest checkpoint.",
        "Checkpoint failure": "Processing continues using the previous successful state snapshot.",
    }[runtime_effect]
    return f"""
    <style>
      .flink-matrix-flow {{
        display:grid;
        grid-template-columns:16% 5% 58% 5% 16%;
        align-items:stretch;
        gap:.3rem;
        width:100%;
        padding:.6rem;
        color:var(--text-color);
        background:var(--secondary-background-color);
        border:1.5px solid #64748b;
        border-radius:.65rem;
        box-sizing:border-box;
      }}
      .flink-side-stack {{
        display:grid;
        grid-template-rows:repeat(3,1fr);
        gap:.35rem;
      }}
      .flink-matrix-card {{
        min-width:0;
        padding:.45rem .3rem;
        display:flex;
        align-items:center;
        justify-content:center;
        text-align:center;
        background:var(--background-color);
        border:1.5px solid #64748b;
        border-radius:.4rem;
        font-size:.68rem;
        font-weight:700;
        line-height:1.2;
        box-sizing:border-box;
      }}
      .flink-outer-arrow {{
        position:relative;
        display:flex;
        align-items:center;
        justify-content:center;
        color:#64748b;
        font-size:1.25rem;
        overflow:hidden;
      }}
      .flink-outer-arrow::after,.flink-data-arrow::after {{
        content:"";
        position:absolute;
        width:.42rem;
        height:.42rem;
        border-radius:50%;
        background:#2563eb;
        animation:flink-matrix-record 1.5s linear infinite;
      }}
      .flink-cluster-board {{
        min-width:0;
        padding:.45rem;
        display:grid;
        grid-template-columns:30% 70%;
        grid-template-rows:auto 1fr;
        gap:.4rem;
        background:var(--background-color);
        border:2px solid #2563eb;
        border-radius:.55rem;
        box-sizing:border-box;
      }}
      .flink-cluster-title {{
        grid-column:1/-1;
        text-align:center;
        font-size:.76rem;
        font-weight:850;
      }}
      .flink-control-column {{
        display:grid;
        grid-template-rows:repeat(3,1fr);
        gap:.3rem;
      }}
      .flink-control-box {{
        min-width:0;
        padding:.4rem .25rem;
        display:flex;
        flex-direction:column;
        justify-content:center;
        text-align:center;
        background:var(--secondary-background-color);
        border:1.5px solid #d97706;
        border-radius:.35rem;
        font-size:.64rem;
        line-height:1.15;
      }}
      .flink-control-box strong {{font-size:.69rem;margin-bottom:.12rem}}
      .flink-taskmanager-board {{
        min-width:0;
        padding:.4rem;
        display:grid;
        grid-template-rows:auto 1fr auto;
        gap:.35rem;
        background:var(--secondary-background-color);
        border:2px solid #16a34a;
        border-radius:.4rem;
        box-sizing:border-box;
      }}
      .flink-taskmanager-title {{
        text-align:center;
        font-size:.7rem;
        font-weight:850;
      }}
      .flink-data-path {{
        display:grid;
        grid-template-columns:1fr .22fr 1fr .22fr 1fr;
        align-items:stretch;
        gap:.18rem;
      }}
      .flink-data-step {{
        min-width:0;
        padding:.45rem .2rem;
        display:flex;
        flex-direction:column;
        align-items:center;
        justify-content:center;
        text-align:center;
        background:var(--background-color);
        border:1.5px solid #64748b;
        border-radius:.35rem;
        font-size:.62rem;
        line-height:1.15;
        overflow-wrap:anywhere;
      }}
      .flink-data-step strong {{font-size:.68rem;margin-bottom:.12rem}}
      .flink-data-arrow {{
        position:relative;
        display:flex;
        align-items:center;
        justify-content:center;
        color:#2563eb;
        font-size:1rem;
        overflow:hidden;
      }}
      .flink-taskmanager-footer {{
        display:grid;
        grid-template-columns:1fr 1fr;
        gap:.3rem;
      }}
      .flink-taskmanager-footer span {{
        padding:.25rem;
        text-align:center;
        background:var(--background-color);
        border:1px dashed #64748b;
        border-radius:.3rem;
        font-size:.59rem;
        line-height:1.15;
      }}
      .flink-matrix-note {{
        grid-column:1/-1;
        text-align:center;
        font-size:.67rem;
        font-weight:650;
      }}
      .flink-matrix-slow .flink-outer-arrow::after,
      .flink-matrix-slow .flink-data-arrow::after {{
        background:#f59e0b;
        animation-duration:4s;
        animation-direction:alternate;
      }}
      .flink-matrix-failed .flink-taskmanager-board {{border-color:#dc2626}}
      .flink-matrix-failed .flink-data-arrow::after {{
        background:#dc2626;
        animation:none;
      }}
      .flink-matrix-checkpoint-failed .flink-control-box:last-child {{
        color:#dc2626;
        border-color:#dc2626;
      }}
      @keyframes flink-matrix-record {{
        from {{transform:translateX(-1rem)}}
        to {{transform:translateX(1rem)}}
      }}
      @media(max-width:850px) {{
        .flink-matrix-flow {{grid-template-columns:1fr}}
        .flink-outer-arrow {{min-height:1.4rem;transform:rotate(90deg)}}
        .flink-matrix-note {{grid-column:auto}}
      }}
    </style>
    <div class="flink-matrix-flow {effect_class}">
      <div class="flink-side-stack">
        <div class="flink-matrix-card">Kafka / Event Stream</div>
        <div class="flink-matrix-card">Database / CDC</div>
        <div class="flink-matrix-card">API / Files / Other</div>
      </div>
      <div class="flink-outer-arrow">→</div>
      <div class="flink-cluster-board">
        <div class="flink-cluster-title">Apache Flink Cluster</div>
        <div class="flink-control-column">
          <div class="flink-control-box">
            <strong>JobManager</strong>
            schedules the submitted job
          </div>
          <div class="flink-control-box">
            <strong>Checkpoint Coordinator</strong>
            sends barriers to tasks
          </div>
          <div class="flink-control-box">
            <strong>Checkpoint State</strong>
            latest successful snapshot
          </div>
        </div>
        <div class="flink-taskmanager-board">
          <div class="flink-taskmanager-title">
            TaskManager · {parallel_tasks} parallel task(s)
          </div>
          <div class="flink-data-path">
            <div class="flink-data-step">
              <strong>Source Records</strong>
              deserializes incoming data
            </div>
            <div class="flink-data-arrow">→</div>
            <div class="flink-data-step">
              <strong>{operation}</strong>
              executes user logic
            </div>
            <div class="flink-data-arrow">→</div>
            <div class="flink-data-step">
              <strong>Sink</strong>
              emits processed records
            </div>
          </div>
          <div class="flink-taskmanager-footer">
            <span>Task Slots<br>{parallel_tasks} active</span>
            <span>Managed State<br>included in checkpoints</span>
          </div>
        </div>
      </div>
      <div class="flink-outer-arrow">→</div>
      <div class="flink-side-stack">
        <div class="flink-matrix-card">Database / Warehouse</div>
        <div class="flink-matrix-card">Kafka / Event Stream</div>
        <div class="flink-matrix-card">API / Lakehouse / Other</div>
      </div>
      <div class="flink-matrix-note">{effect_text}</div>
    </div>
    """


def drawio_flink_cluster_html(processing, runtime_effect, parallel_tasks):
    operation = {
        "Simple transform": ("Map / Filter", "Forward flow · no keyed state"),
        "Group by key": ("KeyBy + State", "Hash exchange · aggregate by key"),
        "Time window": ("Window + Timer", "Watermark · window state"),
    }[processing]
    effect_class = {
        "Normal flow": "flink-drawio-normal",
        "Backpressure": "flink-drawio-backpressure",
        "Data skew": "flink-drawio-data-skew",
        "Slot exhaustion": "flink-drawio-slot-exhaustion",
        "Network congestion": "flink-drawio-network-congestion",
        "JVM heap pressure": "flink-drawio-heap-pressure",
        "State growth": "flink-drawio-state-growth",
        "Late events": "flink-drawio-late-events",
        "Task failure": "flink-drawio-task-failure",
        "Checkpoint failure": "flink-drawio-checkpoint-failure",
    }[runtime_effect]
    processing_class = {
        "Simple transform": "flink-processing-simple",
        "Group by key": "flink-processing-keyed",
        "Time window": "flink-processing-window",
    }[processing]
    effect_text = {
        "Normal flow": "Records and checkpoint barriers advance normally.",
        "Backpressure": "The sink slows; pressure propagates backward through the operator chain.",
        "Data skew": "One keyed subtask receives more records and becomes the bottleneck.",
        "Slot exhaustion": "Requested parallel subtasks wait because no execution slots are free.",
        "Network congestion": "Record exchange slows while network buffers remain occupied.",
        "JVM heap pressure": "Operator objects consume heap and trigger long garbage-collection pauses.",
        "State growth": "Keyed or window state grows faster than checkpoints can persist it.",
        "Late events": "Delayed watermarks keep event-time windows open longer than expected.",
        "Task failure": "TaskManager processing stops and restores from the latest successful checkpoint.",
        "Checkpoint failure": "The failed barrier is discarded; the previous checkpoint remains recoverable.",
    }[runtime_effect]
    cause, solution = {
        "Normal flow": (
            "Input rate remains below effective operator and sink capacity.",
            "No intervention required; continue monitoring throughput and checkpoint duration.",
        ),
        "Backpressure": (
            "A slow sink or expensive downstream operator cannot consume records fast enough.",
            "Scale the bottleneck, batch sink writes, tune async I/O, or reduce upstream rate.",
        ),
        "Data skew": (
            "A few hot keys route most records to one keyed subtask.",
            "Salt hot keys, use a two-stage aggregation, or redesign the partition key.",
        ),
        "Slot exhaustion": (
            "Configured parallelism exceeds the slots available from TaskManagers.",
            "Add TaskManagers or slots, reduce parallelism, or enable reactive/adaptive scaling.",
        ),
        "Network congestion": (
            "KeyBy, rebalance, or large records saturate shuffle channels and network buffers.",
            "Increase network memory, reduce record size, tune buffers, or colocate chained operators.",
        ),
        "JVM heap pressure": (
            "Large objects, serialization buffers, or heap-backed state consume TaskManager heap.",
            "Remove object churn, tune heap/direct memory, or move large state to RocksDB.",
        ),
        "State growth": (
            "Unbounded keys, long windows, or missing state TTL continuously retain state.",
            "Configure state TTL, shorten windows, clean timers, and use incremental checkpoints.",
        ),
        "Late events": (
            "An idle or delayed partition holds back the minimum watermark.",
            "Configure idleness, review watermark delay, and route acceptable late data separately.",
        ),
        "Task failure": (
            "A TaskManager process, host, or operator task stopped unexpectedly.",
            "Fix the underlying exception and let Flink restore all affected tasks from a checkpoint.",
        ),
        "Checkpoint failure": (
            "Barrier alignment or durable-state upload exceeded the checkpoint timeout.",
            "Use unaligned/incremental checkpoints, tune timeout, and remove downstream backpressure.",
        ),
    }[runtime_effect]
    subtask_rows = {
        label: "".join(
            f'<span class="flink-subtask">{label}{index}</span>'
            for index in range(1, parallel_tasks + 1)
        )
        for label in ("S", "T", "K")
    }
    arrow_symbol = {
        "Simple transform": "➜",
        "Group by key": "#➜",
        "Time window": "⏱➜",
    }[processing]
    arrow_tracks = "".join(
        f'<span style="animation-delay:-{index * 0.22:.2f}s">{arrow_symbol}</span>'
        for index in range(parallel_tasks)
    )
    return f"""
    <style>
      .flink-drawio {{
        width:100%;
        padding:.8rem;
        color:var(--text-color);
        background:var(--secondary-background-color);
        border:1px solid rgba(100,116,139,.42);
        border-radius:0;
        box-sizing:border-box;
      }}
      .flink-operator-bar {{
        width:62%;
        margin:0 auto .6rem;
        padding:.55rem;
        text-align:center;
        background:var(--background-color);
        border:1px solid rgba(100,116,139,.42);
        border-radius:0;
        font-size:.82rem;
        font-weight:800;
      }}
      .flink-control-arrows {{
        margin:-.05rem 0 .35rem;
        text-align:center;
        color:#64748b;
        font-size:.76rem;
        font-weight:750;
      }}
      .flink-drawio-grid {{
        display:grid;
        grid-template-columns:30% 70%;
        gap:.75rem;
        align-items:stretch;
      }}
      .flink-jobmanager {{
        min-width:0;
        padding:.65rem;
        display:grid;
        grid-template-rows:auto 1fr;
        gap:.5rem;
        background:var(--background-color);
        border:1px solid rgba(100,116,139,.42);
        border-radius:0;
        box-sizing:border-box;
      }}
      .flink-board-title {{
        text-align:center;
        font-size:.9rem;
        font-weight:850;
      }}
      .flink-checkpoint-coordinator {{
        min-height:6rem;
        padding:.65rem;
        display:flex;
        flex-direction:column;
        justify-content:center;
        text-align:center;
        background:var(--secondary-background-color);
        border:1px solid rgba(100,116,139,.42);
        border-radius:0;
        font-size:.72rem;
        line-height:1.3;
      }}
      .flink-checkpoint-coordinator strong {{font-size:.8rem;margin-bottom:.2rem}}
      .flink-checkpoint-state {{
        position:relative;
        padding:.32rem;
        text-align:center;
        background:var(--secondary-background-color);
        border:1.5px dashed #64748b;
        border-radius:0;
        font-size:.6rem;
        line-height:1.15;
        overflow:hidden;
      }}
      .flink-checkpoint-state::after {{
        content:"║";
        position:absolute;
        left:0;
        bottom:0;
        width:auto;
        height:auto;
        color:#475569;
        background:transparent;
        font-weight:900;
        animation:flink-checkpoint-move 2s linear infinite;
      }}
      .flink-taskmanager {{
        min-width:0;
        padding:.65rem;
        display:grid;
        grid-template-rows:auto auto 1fr auto;
        gap:.5rem;
        background:var(--background-color);
        border:1px solid rgba(100,116,139,.42);
        border-radius:0;
        box-sizing:border-box;
      }}
      .flink-job-box {{
        padding:.45rem;
        text-align:center;
        background:var(--secondary-background-color);
        border:1px solid rgba(100,116,139,.42);
        border-radius:0;
        font-size:.72rem;
        font-weight:750;
      }}
      .flink-sequence {{
        display:grid;
        grid-template-columns:1fr .16fr 1fr .16fr 1fr;
        gap:.28rem;
        align-items:stretch;
      }}
      .flink-sequence-step {{
        min-width:0;
        min-height:5.2rem;
        padding:.75rem .4rem;
        display:flex;
        flex-direction:column;
        align-items:center;
        justify-content:center;
        text-align:center;
        background:var(--secondary-background-color);
        border:1px solid rgba(100,116,139,.42);
        border-radius:0;
        font-size:.68rem;
        line-height:1.25;
        overflow-wrap:anywhere;
      }}
      .flink-sequence-number {{
        width:1.35rem;
        height:1.35rem;
        margin-bottom:.24rem;
        display:flex;
        align-items:center;
        justify-content:center;
        color:white;
        background:#475569;
        border-radius:0;
        font-size:.7rem;
        font-weight:850;
      }}
      .flink-sequence-step strong {{font-size:.76rem;margin-bottom:.14rem}}
      .flink-subtasks {{
        width:100%;
        margin-top:.35rem;
        display:grid;
        grid-template-columns:repeat({parallel_tasks},minmax(0,1fr));
        gap:.18rem;
      }}
      .flink-subtask {{
        padding:.14rem .08rem;
        text-align:center;
        background:var(--background-color);
        border:1px solid rgba(100,116,139,.42);
        font-size:.56rem;
        font-weight:800;
      }}
      .flink-record-arrow {{
        position:relative;
        display:flex;
        flex-direction:column;
        gap:.08rem;
        align-items:center;
        justify-content:center;
        color:#475569;
        font-size:.68rem;
        overflow:hidden;
      }}
      .flink-record-arrow span {{
        display:block;
        color:#475569;
        font-weight:900;
        animation:flink-record-move 1.45s linear infinite;
      }}
      .flink-runtime-row {{
        display:grid;
        grid-template-columns:repeat(4,1fr);
        gap:.35rem;
      }}
      .flink-runtime-cell {{
        min-width:0;
        padding:.45rem .25rem;
        text-align:center;
        background:var(--secondary-background-color);
        border:1px solid rgba(100,116,139,.42);
        border-radius:0;
        font-size:.64rem;
        line-height:1.2;
        overflow-wrap:anywhere;
      }}
      .flink-barrier {{
        position:relative;
        grid-column:1/-1;
        margin-top:.6rem;
        padding:.45rem;
        text-align:center;
        border:1px dashed rgba(100,116,139,.48);
        border-radius:0;
        font-size:.66rem;
        font-weight:700;
        overflow:hidden;
      }}
      .flink-barrier::after {{
        content:"║";
        position:absolute;
        top:.18rem;
        left:0;
        color:#475569;
        font-size:.8rem;
        font-weight:900;
        animation:flink-barrier-move 2.4s linear infinite;
      }}
      .flink-effect-note {{
        margin-top:.5rem;
        text-align:center;
        font-size:.7rem;
        font-weight:700;
      }}
      .flink-drawio-backpressure .flink-record-arrow span {{
        color:#991b1b;
        animation-duration:3.8s;
        animation-direction:alternate-reverse;
      }}
      .flink-drawio-backpressure .flink-sequence-step:last-child {{
        color:#991b1b;
        border-color:#991b1b;
        box-shadow:0 0 0 2px rgba(153,27,27,.12);
      }}
      .flink-processing-keyed .flink-sequence-step:nth-child(3),
      .flink-processing-keyed .flink-runtime-cell:nth-child(2) {{
        border:2px solid #475569;
        box-shadow:0 0 0 2px rgba(71,85,105,.12);
      }}
      .flink-processing-window .flink-sequence-step:nth-child(3),
      .flink-processing-window .flink-runtime-cell:nth-child(2),
      .flink-processing-window .flink-barrier {{
        border:2px dashed #475569;
        box-shadow:0 0 0 2px rgba(71,85,105,.1);
      }}
      .flink-processing-keyed .flink-record-arrow span {{animation-duration:1.8s}}
      .flink-processing-window .flink-record-arrow span {{animation-duration:2s}}
      .flink-drawio-data-skew .flink-sequence-step:nth-child(3),
      .flink-drawio-data-skew .flink-runtime-cell:nth-child(2),
      .flink-drawio-data-skew .flink-sequence-step:nth-child(3) .flink-subtask:last-child {{
        border:2px solid #78350f;
        box-shadow:0 0 0 2px rgba(120,53,15,.1);
      }}
      .flink-drawio-slot-exhaustion .flink-runtime-cell:first-child,
      .flink-drawio-slot-exhaustion .flink-subtask:last-child {{
        color:#78350f;
        border:2px dashed #78350f;
      }}
      .flink-drawio-network-congestion .flink-runtime-cell:nth-child(3) {{
        color:#78350f;
        border:2px solid #78350f;
      }}
      .flink-drawio-network-congestion .flink-record-arrow span {{
        color:#78350f;
        animation-duration:4.5s;
      }}
      .flink-drawio-heap-pressure .flink-runtime-cell:nth-child(4) {{
        color:#991b1b;
        border:2px solid #991b1b;
      }}
      .flink-drawio-state-growth .flink-runtime-cell:nth-child(2),
      .flink-drawio-state-growth .flink-barrier {{
        color:#78350f;
        border:2px solid #78350f;
      }}
      .flink-drawio-late-events .flink-sequence-step:nth-child(3),
      .flink-drawio-late-events .flink-barrier {{
        color:#78350f;
        border:2px dashed #78350f;
      }}
      .flink-drawio-task-failure .flink-taskmanager {{
        border-color:#991b1b;
        box-shadow:0 0 0 2px rgba(153,27,27,.14);
      }}
      .flink-drawio-task-failure .flink-record-arrow span {{
        color:#991b1b;
        animation:none;
      }}
      .flink-drawio-checkpoint-failure .flink-checkpoint-coordinator,
      .flink-drawio-checkpoint-failure .flink-checkpoint-state,
      .flink-drawio-checkpoint-failure .flink-barrier {{
        color:#991b1b;
        border-color:#991b1b;
        box-shadow:0 0 0 2px rgba(153,27,27,.12);
      }}
      .flink-drawio-checkpoint-failure .flink-barrier::after {{
        color:#991b1b;
        animation:none;
        left:48%;
      }}
      .flink-diagnosis {{
        margin-top:.65rem;
        display:grid;
        grid-template-columns:1fr 1fr;
        gap:.55rem;
      }}
      .flink-diagnosis-item {{
        padding:.55rem .65rem;
        background:var(--background-color);
        border:1px solid rgba(100,116,139,.42);
        font-size:.68rem;
        line-height:1.3;
      }}
      .flink-diagnosis-item strong {{
        display:block;
        margin-bottom:.18rem;
        font-size:.73rem;
      }}
      @keyframes flink-record-move {{
        from {{transform:translateX(-1rem)}}
        to {{transform:translateX(1rem)}}
      }}
      @keyframes flink-checkpoint-move {{
        from {{left:0}}
        to {{left:calc(100% - .42rem)}}
      }}
      @keyframes flink-barrier-move {{
        from {{left:0}}
        to {{left:calc(100% - .6rem)}}
      }}
      @media(max-width:850px) {{
        .flink-operator-bar {{width:100%}}
        .flink-drawio-grid {{grid-template-columns:1fr}}
        .flink-diagnosis {{grid-template-columns:1fr}}
      }}
    </style>
    <div class="flink-drawio {effect_class} {processing_class}">
      <div class="flink-operator-bar">
        ⚙ Flink Operator · deploys · upgrades · restarts · monitors
      </div>
      <div class="flink-control-arrows">↓ control ↓</div>
      <div class="flink-drawio-grid">
        <div class="flink-jobmanager">
          <div class="flink-board-title">◆ JobManager</div>
          <div class="flink-checkpoint-coordinator">
            <strong>⟳ Checkpoint Coordinator</strong>
            Job ID starts checkpoints<br>
            injects barriers · tracks acknowledgements
          </div>
        </div>
        <div class="flink-taskmanager">
          <div class="flink-board-title">
            ▦ TaskManager · {parallel_tasks} parallel task(s)
          </div>
          <div class="flink-job-box">
            Flink Job · Source → Transform → Sink execution
          </div>
          <div class="flink-sequence">
            <div class="flink-sequence-step">
              <span class="flink-sequence-number">1</span>
              <strong>● ● ● Source Records</strong>
              deserialize incoming records
              <div class="flink-subtasks">{subtask_rows["S"]}</div>
            </div>
            <div class="flink-record-arrow">{arrow_tracks}</div>
            <div class="flink-sequence-step">
              <span class="flink-sequence-number">2</span>
              <strong>↻ {operation[0]}</strong>
              {operation[1]}
              <div class="flink-subtasks">{subtask_rows["T"]}</div>
            </div>
            <div class="flink-record-arrow">{arrow_tracks}</div>
            <div class="flink-sequence-step">
              <span class="flink-sequence-number">3</span>
              <strong>⇥ Sink</strong>
              writes processed records
              <div class="flink-subtasks">{subtask_rows["K"]}</div>
            </div>
          </div>
          <div class="flink-runtime-row">
            <div class="flink-runtime-cell">□ Task Slots<br>{parallel_tasks} active</div>
            <div class="flink-runtime-cell">▣ Managed State<br>keys / windows</div>
            <div class="flink-runtime-cell">⇄ Network Buffers<br>direct memory</div>
            <div class="flink-runtime-cell">▤ JVM Heap<br>operators / objects</div>
          </div>
        </div>
        <div class="flink-barrier">
          ║ Checkpoint barrier follows Sequence 1 → 2 → 3 ·
          ▣ durable checkpoint storage keeps source position + TaskManager state
        </div>
      </div>
      <div class="flink-effect-note">{effect_text}</div>
      <div class="flink-diagnosis">
        <div class="flink-diagnosis-item"><strong>Why it happens</strong>{cause}</div>
        <div class="flink-diagnosis-item"><strong>Recommended solution</strong>{solution}</div>
      </div>
    </div>
    """


def render_compact_flink_simulator():
    st.subheader("Apache Flink Data-Flow Simulator")
    controls = st.columns(3)
    processing = controls[0].selectbox(
        "Processing",
        ["Simple transform", "Group by key", "Time window"],
    )
    runtime_effect = controls[1].selectbox(
        "Runtime effect",
        [
            "Normal flow",
            "Backpressure",
            "Data skew",
            "Slot exhaustion",
            "Network congestion",
            "JVM heap pressure",
            "State growth",
            "Late events",
            "Task failure",
            "Checkpoint failure",
        ],
    )
    parallel_tasks = controls[2].selectbox("Parallel tasks", [1, 2, 3, 4], index=1)
    st.html(drawio_flink_cluster_html(processing, runtime_effect, parallel_tasks))
    explanation = {
        "Simple transform": (
            "Each record is processed independently. Flink can chain Source, Map/Filter "
            "and Sink in the same task for low overhead."
        ),
        "Group by key": (
            "Equal keys are routed to the same parallel task. That task owns the key's "
            "state, and checkpoints make the state recoverable."
        ),
        "Time window": (
            "Records are grouped by event time. Watermarks close windows; timers and "
            "window state are included in checkpoints."
        ),
    }[processing]
    st.caption(explanation)


DECISION_RULES = {
    "Finite batch ETL": (
        "Spark",
        "Bounded data and throughput-oriented SQL/ETL favor Spark.",
    ),
    "Continuous event stream": (
        "Flink",
        "Event-at-a-time execution and continuous checkpoints favor Flink.",
    ),
    "Large lakehouse backfill": (
        "Spark",
        "Large finite scans, joins and file rewrites fit Spark's batch model.",
    ),
    "Stateful event-time processing": (
        "Flink",
        "Watermarks, timers and durable keyed state are Flink-native.",
    ),
    "Batch feature engineering": (
        "Spark",
        "DataFrames, SQL and the batch ML ecosystem fit finite feature preparation.",
    ),
    "Continuous CDC": (
        "Flink",
        "Long-running offsets, state and sink transactions need continuous recovery.",
    ),
}


def render_engine_decision_guide():
    st.subheader("When to use Spark and when to use Flink")
    workload = st.selectbox("Workload", list(DECISION_RULES))
    bounded = st.radio(
        "Input lifecycle",
        ["Bounded — it finishes", "Unbounded — it keeps arriving"],
        horizontal=True,
    )
    latency = st.selectbox(
        "Required latency",
        ["Milliseconds", "Seconds", "Minutes", "Hours"],
    )
    stateful = st.checkbox("Requires keyed state, timers, watermarks or CDC offsets")

    recommendation, reason = DECISION_RULES[workload]
    if bounded.startswith("Unbounded") and (
        latency in {"Milliseconds", "Seconds"} or stateful
    ):
        recommendation = "Flink"
        reason = (
            "The unbounded input requires continuous low-latency execution and "
            "recoverable state."
        )
    elif bounded.startswith("Bounded") and latency in {"Minutes", "Hours"}:
        recommendation = "Spark"
        reason = "The finite input and relaxed latency favor efficient batch execution."

    spark_col, flink_col = st.columns(2)
    with spark_col:
        with st.container(border=True):
            st.markdown("#### Spark")
            st.write("Use for bounded ETL, backfills, large SQL and batch ML.")
            st.write("Execution: job → stages separated by shuffle → tasks.")
            st.write("Recovery: task retry and lineage recomputation.")
            st.warning("Not the first choice for per-event millisecond processing.")
    with flink_col:
        with st.container(border=True):
            st.markdown("#### Flink")
            st.write("Use for continuous streams, CDC, event time and keyed state.")
            st.write("Execution: JobGraph → operators → parallel subtasks.")
            st.write("Recovery: checkpointed offsets, state, timers and sink commits.")
            st.warning("Unnecessary when a straightforward finite batch job is enough.")

    st.success(f"Recommendation: {recommendation}. {reason}")
