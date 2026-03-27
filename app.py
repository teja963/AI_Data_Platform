import streamlit as st

st.set_page_config(layout="wide")

# ---------------- SECTION LABELS ----------------
DASHBOARD_SECTION_LABEL = "Dashboard"
CONCEPTS_SECTION_LABEL = "Concepts"
CODING_SECTION_LABEL = "Coding"
PYTHON_SECTION_LABEL = "Python"
SPARK_SECTION_LABEL = "Spark"
DATA_MODELING_SECTION_LABEL = "Data Modelling"
PROJECTS_SECTION_LABEL = "Projects"

SECTION_ORDER = [
    DASHBOARD_SECTION_LABEL,
    CONCEPTS_SECTION_LABEL,
    CODING_SECTION_LABEL,
    PYTHON_SECTION_LABEL,
    SPARK_SECTION_LABEL,
    DATA_MODELING_SECTION_LABEL,
    PROJECTS_SECTION_LABEL,
]

# ---------------- URL PARAM HANDLING ----------------
query_params = st.query_params

# ✅ STEP 1: Initialize session FIRST (source of truth)
if "module" not in st.session_state:
    st.session_state["module"] = DASHBOARD_SECTION_LABEL

# ✅ STEP 2: If URL has module → override session
if "module" in query_params:
    st.session_state["module"] = query_params["module"]

# ✅ STEP 3: Use session as final value
selected_module = st.session_state["module"]

# ---------------- LEGACY MAP ----------------
legacy_module_map = {
    "SQL": CODING_SECTION_LABEL,
    "SQL + PySpark": CODING_SECTION_LABEL,
    "PySpark": SPARK_SECTION_LABEL,
}

selected_module = legacy_module_map.get(selected_module, selected_module)

if selected_module not in SECTION_ORDER:
    selected_module = DASHBOARD_SECTION_LABEL

# ---------------- SIDEBAR ----------------
module = st.sidebar.selectbox(
    "Choose Section",
    SECTION_ORDER,
    index=SECTION_ORDER.index(selected_module),
)

# ✅ STEP 4: Sync BOTH (CRITICAL)
st.session_state["module"] = module
st.query_params["module"] = module


# =========================================================
# ---------------- ROUTING ----------------
# =========================================================

if module == CODING_SECTION_LABEL:
    from modules.sql.ui import render_sql
    render_sql()

elif module == PYTHON_SECTION_LABEL:
    from modules.python.ui import render_python
    render_python()

elif module == CONCEPTS_SECTION_LABEL:
    from modules.concepts.ui import render_concepts
    render_concepts()

elif module == SPARK_SECTION_LABEL:
    from modules.spark.ui import render_spark
    render_spark()

elif module == DATA_MODELING_SECTION_LABEL:
    from modules.datamodeling.ui import render_datamodeling
    render_datamodeling()

elif module == PROJECTS_SECTION_LABEL:
    from modules.projects.ui import render_projects
    render_projects()

elif module == DASHBOARD_SECTION_LABEL:
    import matplotlib.pyplot as plt
    from core.interview import load_interview_history
    from core.loader import load_questions
    from core.progress import load_progress

    st.title("📊 Dashboard")

    modules = [
        {"label": "SQL", "question_module": "sql", "progress_track": "sql"},
        {"label": "Spark", "question_module": "sql", "progress_track": "pyspark"},
        {"label": "Python", "question_module": "python", "progress_track": "python"},
    ]

    cols = st.columns(3)

    for i, module_config in enumerate(modules):
        with cols[i % 3]:

            try:
                questions = load_questions(module_config["question_module"])
            except:
                questions = []

            total = len(questions)
            solved_keys = load_progress(module_config["progress_track"])
            solved = len([q for q in questions if q["progress_key"] in solved_keys])
            unsolved = total - solved

            st.markdown(f"### 📘 {module_config['label'].upper()}")

            if total == 0:
                st.info("No questions yet")
                continue

            fig, ax = plt.subplots(figsize=(2.5, 2.5))

            ax.pie(
                [solved, unsolved],
                labels=["✔", "✖"],
                autopct="%1.0f%%",
                textprops={'fontsize': 8}
            )

            ax.axis("equal")

            st.pyplot(fig)

            st.markdown(
                f"""
                <div style="text-align:center;">
                    <b>{solved} / {total}</b><br>
                    <small>Solved</small>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.markdown("---")
    st.subheader("Interview Simulator")

    history = load_interview_history()

    if not history:
        st.info("No interview runs yet.")
    else:
        latest_run = history[-1]
        best_run = max(history, key=lambda run: run.get("score_percent", 0))
        average_score = round(
            sum(run.get("score_percent", 0) for run in history) / len(history),
            1,
        )

        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        metric_col1.metric("Runs", len(history))
        metric_col2.metric("Latest Score", f"{latest_run['score_percent']}%")
        metric_col3.metric("Best Score", f"{best_run['score_percent']}%")
        metric_col4.metric("Average Score", f"{average_score}%")

        recent_runs = []
        for run in reversed(history[-5:]):
            recent_runs.append({
                "finished_at": run["finished_at"],
                "track": run["track"],
                "score": f"{run['total_score']} / {run['max_score']}",
                "accuracy": f"{run['correct_count']} / {run['total_questions']}",
                "time_used": f"{run.get('elapsed_seconds', 0)}s",
                "reason": run.get("finished_reason", "completed").replace("_", " ").title(),
            })

        st.dataframe(recent_runs, use_container_width=True, hide_index=True)
