import streamlit as st
from modules.sql.engine import create_db, run_query
from modules.sql.validator import validate
from core.loader import load_questions, group_by_category
from core.ai import ask_ai
from core.progress import load_progress, save_progress
import re

# ---------- FORMAT SQL ----------
def format_sql_vertical(sql):
    keywords = [
        "SELECT", "FROM", "JOIN", "LEFT JOIN", "RIGHT JOIN",
        "INNER JOIN", "WHERE", "GROUP BY", "HAVING",
        "ORDER BY", "LIMIT", "ON"
    ]
    for kw in keywords:
        sql = re.sub(rf"\b{kw}\b", f"\n{kw}", sql, flags=re.IGNORECASE)
    return sql.strip()


def render_sql():

    questions = load_questions("sql")

    if not questions:
        st.error("No SQL questions found.")
        return

    if "solved" not in st.session_state:
        st.session_state.solved = load_progress()

    grouped = group_by_category(questions)

    # ---------- SIDEBAR ----------
    st.sidebar.title("SQL Practice")

    selected_submodule = st.sidebar.selectbox(
        "Submodule",
        list(grouped.keys())
    )

    sub_qs = grouped[selected_submodule]

    st.sidebar.markdown("### Questions")

    for q in sub_qs:
        if st.sidebar.button(
            f"{q['id']}. {q['title']}",
            key=f"q_{q['id']}"
        ):
            st.session_state.selected_question = q

    if "selected_question" not in st.session_state:
        st.session_state.selected_question = sub_qs[0]

    q = st.session_state.selected_question

    # 🔥 KEY FIX → FORCE RENDER START
    st.empty()

    # ---------- LAYOUT ----------
    col1, col2 = st.columns([3, 1.5])

    # ---------- QUESTION ----------
    with col1:
        st.subheader(q["title"])
        st.write(q["description"])

        st.markdown("### Input Tables")
        for table, data in q["tables"].items():
            st.markdown(f"#### {table}")
            st.dataframe(data, use_container_width=True, hide_index=True)

        st.markdown("### Expected Output")
        st.dataframe(q["expected_output"], use_container_width=True, hide_index=True)

    # ---------- EDITOR ----------
    with col2:
        st.subheader("SQL Editor")

        query = st.text_area(
            "Write SQL",
            height=250,
            key=f"query_{q['id']}"
        )

        c1, c2 = st.columns(2)
        run = c1.button("Run")
        submit = c2.button("Submit")

        if run or submit:
            if not query.strip():
                st.warning("Write a query")
            else:
                conn = create_db(q["tables"])
                result, error = run_query(conn, query)

                if error:
                    st.error(error)
                else:
                    st.dataframe(result, use_container_width=True, hide_index=True)

                    if submit:
                        if validate(result, q["expected_output"]):
                            st.success("Correct")
                            st.session_state.solved.add(q["id"])
                            save_progress(st.session_state.solved)
                        else:
                            st.error("Incorrect")

        # ---------- AI ----------
        st.markdown("### AI Tools")

        cA, cB = st.columns(2)
        hint = cA.button("Hint")
        explain = cB.button("Explain")

        if hint:
            st.write(ask_ai(f"Hint:\n{q['description']}"))

        elif explain and query.strip():
            st.write(ask_ai(f"Explain:\n{query}"))

        with st.expander("Show Solution"):
            st.code(format_sql_vertical(q["solution"]), language="sql")