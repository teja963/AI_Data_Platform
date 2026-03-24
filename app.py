import streamlit as st

st.set_page_config(layout="wide")

DASHBOARD_SECTION_LABEL = "Dashboard"
CONCEPTS_SECTION_LABEL = "Concepts"
CODING_SECTION_LABEL = "Coding"
SPARK_SECTION_LABEL = "Spark"
SECTION_ORDER = [
    DASHBOARD_SECTION_LABEL,
    CONCEPTS_SECTION_LABEL,
    CODING_SECTION_LABEL,
    SPARK_SECTION_LABEL,
]

# 🔥 READ FROM URL
query_params = st.query_params

if "module" not in query_params:
    st.query_params["module"] = DASHBOARD_SECTION_LABEL

selected_module = st.query_params.get("module", DASHBOARD_SECTION_LABEL)
legacy_module_map = {
    "SQL": CODING_SECTION_LABEL,
    "SQL + PySpark": CODING_SECTION_LABEL,
    "PySpark": SPARK_SECTION_LABEL,
}
selected_module = legacy_module_map.get(selected_module, selected_module)

if selected_module not in SECTION_ORDER:
    selected_module = DASHBOARD_SECTION_LABEL

module = st.sidebar.selectbox(
    "Choose Section",
    SECTION_ORDER,
    index=SECTION_ORDER.index(selected_module),
)

# 🔥 SAVE TO URL (PERSISTS AFTER REFRESH)
st.query_params["module"] = module


# ---------------- CODING ----------------
if module == CODING_SECTION_LABEL:
    from modules.sql.ui import render_sql
    render_sql()

# ---------------- CONCEPTS ----------------
elif module == CONCEPTS_SECTION_LABEL:
    from modules.concepts.ui import render_concepts
    render_concepts()

# ---------------- SPARK ----------------
elif module == SPARK_SECTION_LABEL:
    from modules.pyspark.ui import render_spark
    render_spark()

# ---------------- DASHBOARD ----------------
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
        st.info("No interview runs yet. Start one from the Interview Simulator workspace.")
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
