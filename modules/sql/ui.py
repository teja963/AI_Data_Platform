import streamlit as st
from modules.sql.engine import create_db, is_pyspark_available, run_pyspark_code, run_query
from modules.sql.validator import validate
from core.loader import load_questions, group_by_category
from core.ai import ask_ai
from core.progress import load_progress, save_progress, clear_progress
import re

EDITOR_TRACKS = {
    "SQL": "sql",
    "PySpark": "pyspark",
}


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


def get_query_param(name, default):
    value = st.query_params.get(name, default)

    if isinstance(value, list):
        return value[0] if value else default

    return value


def render_compact_table(data):
    row_count = len(data) if hasattr(data, "__len__") else 0
    table_height = min(max(100, 35 * (row_count + 1)), 220)
    st.dataframe(
        data,
        use_container_width=True,
        hide_index=True,
        height=table_height,
    )


def render_sql():

    questions = load_questions("sql")

    if not questions:
        st.error("No SQL questions found.")
        return

    grouped = group_by_category(questions)
    submodules = list(grouped.keys())

    initial_submodule = get_query_param("submodule", submodules[0])
    if initial_submodule not in grouped:
        initial_submodule = submodules[0]

    if "sql_selected_submodule" not in st.session_state:
        st.session_state.sql_selected_submodule = initial_submodule
    elif st.session_state.sql_selected_submodule not in grouped:
        st.session_state.sql_selected_submodule = submodules[0]

    initial_editor_mode = get_query_param("editor_mode", "SQL")
    if initial_editor_mode not in EDITOR_TRACKS:
        initial_editor_mode = "SQL"

    if "editor_mode" not in st.session_state or st.session_state.editor_mode not in EDITOR_TRACKS:
        st.session_state.editor_mode = initial_editor_mode

    progress_track = EDITOR_TRACKS[st.session_state.editor_mode]
    solved = load_progress(progress_track)

    # ---------- SIDEBAR ----------
    st.sidebar.title("SQL + PySpark Coding Questions")

    if st.sidebar.button("Reset All Progress"):
        clear_progress()
        solved = set()
        st.sidebar.success("SQL and PySpark progress cleared.")

    selected_submodule = st.sidebar.selectbox(
        "Submodule",
        submodules,
        key="sql_selected_submodule",
    )
    st.query_params["submodule"] = selected_submodule

    sub_qs = grouped[selected_submodule]
    sub_q_keys = {question["progress_key"] for question in sub_qs}
    selected_question_key = get_query_param("question", sub_qs[0]["progress_key"])

    if selected_question_key not in sub_q_keys:
        selected_question_key = sub_qs[0]["progress_key"]

    st.query_params["question"] = selected_question_key

    st.sidebar.markdown("### Questions")
    st.sidebar.caption(f"Progress view: {st.session_state.editor_mode}")

    for q in sub_qs:
        question_key = q["progress_key"]
        label = f"{q['id']}. {q['title']}"

        if question_key == selected_question_key:
            label = "▶ " + label
        if question_key in solved:
            label = "✅ " + label

        if st.sidebar.button(label, key=f"q_{question_key}"):
            st.query_params["question"] = question_key
            st.rerun()

    q = next(question for question in sub_qs if question["progress_key"] == selected_question_key)
    question_key = selected_question_key

    # ---------- LAYOUT ----------
    col1, col2 = st.columns([2, 3])

    # ---------- QUESTION ----------
    with col1:
        st.subheader(q["title"])
        st.write(q["description"])

        st.markdown("### Input Tables")
        for table, data in q["tables"].items():
            st.markdown(f"#### {table}")
            render_compact_table(data)

        st.markdown("### Expected Output")
        render_compact_table(q["expected_output"])

    # ---------- EDITOR ----------
    with col2:
        st.subheader("Editor")

        editor_mode = st.radio(
            "Mode",
            ["SQL", "PySpark"],
            horizontal=True,
            key="editor_mode",
        )
        st.query_params["editor_mode"] = editor_mode
        progress_track = EDITOR_TRACKS[editor_mode]

        if editor_mode == "PySpark":
            st.caption(
                "Write DataFrame API code. The app will display `result` if you assign it, "
                "or the last DataFrame variable you create."
            )

            if not is_pyspark_available():
                st.warning(
                    "PySpark is not available in the interpreter currently running this app. "
                    "Restart Streamlit from your virtual environment and try again."
                )

        query = st.text_area(
            f"Write {editor_mode}",
            height=420,
            key=f"query_{question_key}_{editor_mode.lower()}"
        )

        c1, c2 = st.columns(2)
        run = c1.button("Run")
        submit = c2.button("Submit")

        if run or submit:
            if not query.strip():
                st.warning(f"Write {editor_mode} code")
            else:
                if editor_mode == "SQL":
                    conn = create_db(q["tables"])
                    result, error = run_query(conn, query)
                else:
                    result, error = run_pyspark_code(q["tables"], query)

                if error:
                    st.error(error)
                else:
                    st.dataframe(result, use_container_width=True, hide_index=True)

                    if submit:
                        if validate(result, q["expected_output"]):
                            solved = load_progress(progress_track)
                            solved.add(question_key)
                            save_progress(solved, progress_track)
                            st.success("Correct")
                        else:
                            st.error("Incorrect")

        # ---------- AI ----------
        st.markdown("### AI Tools")

        cA, cB = st.columns(2)
        hint = cA.button("Hint")
        explain = cB.button("Explain")

        if hint:
            st.write(ask_ai(f"Hint for {editor_mode}:\n{q['description']}"))

        elif explain and query.strip():
            st.write(ask_ai(f"Explain this {editor_mode} code:\n{query}"))

        with st.expander("Show Solution"):
            sql_tab, pyspark_tab = st.tabs(["SQL", "PySpark"])

            with sql_tab:
                st.code(format_sql_vertical(q.get("sql_solution", q.get("solution", ""))), language="sql")

            with pyspark_tab:
                st.code(q.get("pyspark_solution", ""), language="python")
