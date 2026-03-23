import streamlit as st

st.set_page_config(layout="wide")

PRACTICE_MODULE_LABEL = "SQL + PySpark"

# 🔥 READ FROM URL
query_params = st.query_params

if "module" not in query_params:
    st.query_params["module"] = PRACTICE_MODULE_LABEL

selected_module = st.query_params.get("module", PRACTICE_MODULE_LABEL)
if selected_module == "SQL":
    selected_module = PRACTICE_MODULE_LABEL

module = st.sidebar.selectbox(
    "Choose Section",
    [PRACTICE_MODULE_LABEL, "Dashboard"],
    index=[PRACTICE_MODULE_LABEL, "Dashboard"].index(selected_module)
)

# 🔥 SAVE TO URL (PERSISTS AFTER REFRESH)
st.query_params["module"] = module


# ---------------- SQL ----------------
if module == PRACTICE_MODULE_LABEL:
    from modules.sql.ui import render_sql
    render_sql()

# ---------------- DASHBOARD ----------------
elif module == "Dashboard":
    import matplotlib.pyplot as plt
    from core.loader import load_questions
    from core.progress import load_progress

    st.title("📊 Dashboard")

    modules = [
        {"label": "SQL", "question_module": "sql", "progress_track": "sql"},
        {"label": "PySpark", "question_module": "sql", "progress_track": "pyspark"},
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
