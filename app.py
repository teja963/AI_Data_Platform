import streamlit as st

st.set_page_config(layout="wide")

# 🔥 READ FROM URL
query_params = st.query_params

if "module" not in query_params:
    st.query_params["module"] = "SQL"

module = st.sidebar.selectbox(
    "Choose Module",
    ["SQL", "Dashboard"],
    index=["SQL", "Dashboard"].index(st.query_params.get("module", "SQL"))
)

# 🔥 SAVE TO URL (PERSISTS AFTER REFRESH)
st.query_params["module"] = module


# ---------------- SQL ----------------
if module == "SQL":
    from modules.sql.ui import render_sql
    render_sql()

# ---------------- DASHBOARD ----------------
elif module == "Dashboard":
    import matplotlib.pyplot as plt
    from core.loader import load_questions

    st.title("📊 Dashboard")

    modules = ["sql", "pyspark", "python"]

    cols = st.columns(3)

    for i, module_name in enumerate(modules):
        with cols[i % 3]:

            try:
                questions = load_questions(module_name)
            except:
                questions = []

            total = len(questions)

            if "solved" not in st.session_state:
                st.session_state.solved = set()

            solved = len([q for q in questions if q["id"] in st.session_state.solved])
            unsolved = total - solved

            st.markdown(f"### 📘 {module_name.upper()}")

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