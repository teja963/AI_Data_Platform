import streamlit as st


# ---------------- METRICS ENGINE ----------------
def compute_metrics(state):
    time = 2
    shuffle = "Low"
    status = "Success"

    if state["transform"] == "Wide":
        time += 2
        shuffle = "High"

    if state["join"] == "Shuffle":
        time += 2
        shuffle = "High"

    if state["partition"] == "Repartition":
        time += 3
        shuffle = "Very High"

    if state["partition"] == "Coalesce":
        time -= 1
        shuffle = "None"

    if state["debug"] == "Spill":
        time += 3

    if state["debug"] == "Skew":
        time += 2

    if state["debug"] == "OOM":
        status = "Failed"

    return time, shuffle, status


# ---------------- DRIVER ----------------
def render_driver():
    with st.container(border=True):
        st.markdown("### Driver")

        st.markdown("**Job**")

        components = [
            "SparkSession",
            "SparkContext",
            "Logical Plan",
            "Catalyst",
            "Physical Plan",
            "DAG Scheduler (Stages)",
        ]

        for i, comp in enumerate(components):
            html = f"<div style='display:flex;justify-content:center'><div style='border:1px solid #cbd5e1;padding:6px 10px;border-radius:6px;background:#f8fafc;font-size:14px;font-weight:500'>{comp}</div></div>"
            st.markdown(html, unsafe_allow_html=True)

            if i < len(components) - 1:
                st.markdown("<div style='text-align:center;font-size:12px'>↓</div>", unsafe_allow_html=True)

        st.markdown("<div style='text-align:center;font-size:12px'>Tasks → Executors</div>", unsafe_allow_html=True)


# ---------------- CLUSTER ----------------
def render_cluster():
    with st.container(border=True):
        st.markdown("### Cluster Manager")

        items = ["YARN / K8s", "Resource Allocation", "Executor Launch"]

        for item in items:
            html = f"<div style='display:flex;justify-content:center'><div style='padding:6px 10px;font-size:14px;background:#fef3c7;border-radius:6px;margin:4px'>{item}</div></div>"
            st.markdown(html, unsafe_allow_html=True)


# ---------------- CORE ----------------
def render_core(core_id, state, highlight=False):
    is_skew = state["debug"] == "Skew"

    if is_skew:
        if highlight:
            color = "#fecaca"
            opacity = 1
        else:
            color = "#f1f5f9"
            opacity = 0.4
    else:
        color = "#f1f5f9"
        opacity = 1

    partitions = 2
    if state["partition"] == "Repartition":
        partitions = 4
    elif state["partition"] == "Coalesce":
        partitions = 1

    parts = "".join(
        ["<div style='width:8px;height:8px;background:#64748b;margin:1px;border-radius:2px'></div>" for _ in range(partitions)]
    )

    return f"<div style='width:80px;height:70px;background:{color};opacity:{opacity};border:1px solid #cbd5e1;border-radius:6px;display:flex;flex-direction:column;align-items:center;justify-content:center;margin:4px;font-size:13px;font-weight:600'>Core {core_id}<div style='display:flex;flex-wrap:wrap;width:35px;justify-content:center'>{parts}</div></div>"


# ---------------- EXECUTOR ----------------
def render_executor(idx, state):
    is_spill = state["debug"] == "Spill"
    is_oom = state["debug"] == "OOM"

    mem_color = "#fecaca" if (is_spill or is_oom) else "#f8fafc"

    disk_color = "#e5e7eb"
    if is_spill:
        disk_color = "#bbf7d0"
    if is_oom:
        disk_color = "#fecaca"

    time, shuffle, status = compute_metrics(state)

    with st.container(border=True):
        st.markdown(f"**Executor {idx}**")

        # ONLY 2 CORES
        core_html = "".join([
            render_core(1, state, highlight=(idx == 1)),
            render_core(2, state)
        ])

        st.markdown(f"<div style='display:flex;justify-content:center'>{core_html}</div>", unsafe_allow_html=True)

        # MEMORY
        mem_html = f"<div style='border:2px dashed #9ca3af;border-radius:8px;padding:6px;margin-top:6px;background:{mem_color}'>"
        mem_html += "<div style='text-align:center;font-size:13px;font-weight:600'>Unified Memory</div>"
        mem_html += "<div style='display:flex;gap:5px;margin-top:4px'>"
        mem_html += "<div style='flex:1;background:#dbeafe;text-align:center;font-size:12px;padding:6px'>Compute</div>"
        mem_html += "<div style='flex:1;background:#dcfce7;text-align:center;font-size:12px;padding:6px'>Cache</div>"
        mem_html += "</div></div>"

        st.markdown(mem_html, unsafe_allow_html=True)

        # DISK
        st.markdown(f"<div style='margin-top:6px;padding:6px;background:{disk_color};text-align:center;font-size:13px;border-radius:6px'>Disk</div>", unsafe_allow_html=True)

        # METRICS (DYNAMIC)
        st.markdown(f"<div style='font-size:12px'>⏱ {time}s &nbsp;&nbsp; 🔀 {shuffle} &nbsp;&nbsp; {'✔ Success' if status=='Success' else '❌ Failed'}</div>", unsafe_allow_html=True)


# ---------------- WORKERS ----------------
def render_workers(state):
    with st.container(border=True):
        st.markdown("### Worker Nodes")

        n = state["executors"]
        rows = [n] if n <= 2 else [2, n - 2]

        idx = 0
        for row in rows:
            cols = st.columns(row)
            for i in range(row):
                with cols[i]:
                    render_executor(idx + 1, state)
                    idx += 1

        if state["transform"] == "Wide":
            st.markdown("<div style='text-align:center;color:red;font-size:13px'>Shuffle Occurs</div>", unsafe_allow_html=True)

        if state["join"] == "Broadcast":
            st.markdown("<div style='text-align:center;color:teal;font-size:13px'>Broadcast Join</div>", unsafe_allow_html=True)


# ---------------- MAIN ----------------
def render_architecture_simulator(state):
    col1, col_arrow1, col2, col_arrow2, col3 = st.columns([1, 0.2, 1, 0.2, 4])

    with col1:
        render_driver()

    with col_arrow1:
        st.markdown("<div style='text-align:center;font-size:14px'>→</div>", unsafe_allow_html=True)

    with col2:
        render_cluster()

    with col_arrow2:
        st.markdown("<div style='text-align:center;font-size:14px'>→</div>", unsafe_allow_html=True)

    with col3:
        render_workers(state)


# ---------------- ENTRY ----------------
def render_spark():
    st.title("Spark Simulator")

    c1, c2, c3, c4, c5 = st.columns(5)

    state = {
        "transform": c1.selectbox("Transform", ["Narrow", "Wide"]),
        "debug": c2.selectbox("Debug", ["Normal", "Spill", "OOM", "Skew"]),
        "join": c3.selectbox("Join", ["Broadcast", "Shuffle"]),
        "partition": c4.selectbox("Partition", ["None", "Repartition", "Coalesce"]),
        "executors": c5.slider("Executors", 1, 4, 2),
    }

    st.markdown("---")

    render_architecture_simulator(state)