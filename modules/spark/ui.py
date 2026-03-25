import streamlit as st
from core.ai import ask_ai   # ✅ IMPORT LLM INTERFACE
from groq import Groq


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
        bg = "#2563eb" if idx == active else "#e5e7eb"
        color = "white" if idx == active else "black"
        return f"<span style='padding:3px 8px;border-radius:12px;background:{bg};color:{color};font-size:11px'>{name}</span>"

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
                f"<div style='text-align:center;border:1px solid #ccc;padding:5px;margin:2px;border-radius:5px'>{comp}</div>",
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
            "<div style='text-align:center;background:#fef3c7;padding:5px;border-radius:5px'>YARN / Kubernetes / Standalone</div>",
            unsafe_allow_html=True
        )
        st.markdown(
            "<div style='text-align:center;background:#fef3c7;padding:5px;border-radius:5px'>Resources → Launch</div>",
            unsafe_allow_html=True
        )


# ---------------- CORE ----------------
def render_core(core_id, state, executor_id):
    return f"""
    <div style='width:65px;height:75px;background:#f1f5f9;
    border:1px solid #ccc;border-radius:6px;
    display:flex;flex-direction:column;align-items:center;justify-content:center;
    font-size:12px'>
    Core {core_id}
    {render_partitions(state, core_id, executor_id)}
    </div>
    """


# ---------------- EXECUTOR ----------------
def render_executor(idx, state):
    time, shuffle, status = compute_metrics(state)

    is_spill = state["debug"] == "Spill"
    is_oom = state["debug"] == "OOM"

    mem_color = "#fee2e2" if (is_spill or is_oom) else "#f8fafc"
    disk_color = "#fecaca" if is_oom else "#bbf7d0" if is_spill else "#e5e7eb"

    with st.container(border=True):
        st.markdown(f"Executor {idx}")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(render_core(1, state, idx), unsafe_allow_html=True)
        with c2:
            st.markdown(render_core(2, state, idx), unsafe_allow_html=True)

        st.markdown(f"""
        <div style='border:1px dashed #999;padding:5px;border-radius:6px;background:{mem_color}'>
            <div style='text-align:center'>Unified Memory</div>
            <div style='display:flex'>
                <div style='flex:1;background:#dbeafe;text-align:center'>⚡ Execution</div>
                <div style='flex:1;background:#dcfce7;text-align:center'>💾 Storage</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"<div style='background:{disk_color};text-align:center;margin-top:4px'>Disk</div>", unsafe_allow_html=True)

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

        st.markdown(f"⏱ {time}s | 🔀 {shuffle} | {'✔' if status=='Success' else '❌'}")


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
def render_spark():
    st.title("Spark Simulator")

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