import streamlit as st
from modules.sql.engine import create_db, run_query
from modules.sql.validator import validate
from core.loader import load_questions, group_by_category
from core.ai import ask_ai
from core.progress import load_progress, save_progress

def render_sql():
    st.set_page_config(layout="wide")

    questions = load_questions("sql")

    if not questions:
        st.error("❌ No SQL questions found.")
        return

    # 🔥 Load progress
    if "solved" not in st.session_state:
        st.session_state.solved = load_progress()

    # 🔥 Persist selected category/module
    if "category" not in st.session_state:
        st.session_state.category = None

    if "selected_question" not in st.session_state:
        st.session_state.selected_question = None

    # 🔥 Group by category
    grouped = group_by_category(questions)

    st.sidebar.title("SQL Practice")

    # ---------------- CATEGORY ----------------
    categories = list(grouped.keys())

    selected_category = st.sidebar.selectbox(
        "📂 Select Category",
        categories,
        index=categories.index(st.session_state.category)
        if st.session_state.category in categories else 0
    )

    st.session_state.category = selected_category

    modules = grouped[selected_category]

    # ---------------- MODULE ----------------
    selected_q = st.sidebar.selectbox(
        "📘 Select Module",
        modules,
        format_func=lambda x: f"{x['id']}. {x['title']}",
        index=modules.index(st.session_state.selected_question)
        if st.session_state.selected_question in modules else 0
    )

    st.session_state.selected_question = selected_q

    q = selected_q

    show_ai = st.sidebar.checkbox("Show AI Assistant", value=True)

    # 🔥 60:40 layout
    col1, col2 = st.columns([3, 2])

    # ---------------- LEFT PANEL ----------------
    with col1:
        st.header(q.get("title", ""))

        # Tags
        tags = q.get("tags", [])
        if tags:
            st.markdown("**Tags:** " + " | ".join([f"`{t}`" for t in tags]))

        st.write(q.get("description", ""))

        st.markdown("### 📊 Input Tables")
        for table, data in q.get("tables", {}).items():
            st.markdown(f"#### 🟦 {table}")
            st.dataframe(data, use_container_width=True, hide_index=True)

        st.markdown("### 📤 Expected Output")
        st.dataframe(q.get("expected_output", []), use_container_width=True, hide_index=True)

    # ---------------- RIGHT PANEL ----------------
    with col2:
        st.subheader("💻 SQL Editor")

        query = st.text_area(
            "Write your SQL query",
            height=500,
            placeholder="SELECT * FROM Customers;",
            key=f"query_{q['id']}"
        )

        col_run, col_submit = st.columns(2)

        result = None

        with col_run:
            run_clicked = st.button("▶️ Run")

        with col_submit:
            submit_clicked = st.button("✅ Submit")

        if run_clicked or submit_clicked:
            if not query.strip():
                st.warning("⚠️ Please write a query")
            else:
                with st.spinner("Running..."):
                    conn = create_db(q["tables"])
                    result, error = run_query(conn, query)

                if error:
                    st.error(error)
                else:
                    st.markdown("### 📊 Output")
                    st.dataframe(result, use_container_width=True, hide_index=True)

                    if submit_clicked:
                        if validate(result, q["expected_output"]):
                            st.success("✅ Correct Answer!")
                            st.session_state.solved.add(q["id"])
                            save_progress(st.session_state.solved)
                        else:
                            st.error("❌ Incorrect Answer")

        # ---------------- AI ----------------
        if show_ai:
            st.markdown("---")
            st.subheader("🤖 AI Assistant")

            col1, col2, col3 = st.columns(3)

            explain = col1.button("Explain")
            debug = col2.button("Debug")
            hint = col3.button("Hint")

            if explain and query.strip():
                st.write(ask_ai(f"""
Explain this SQL:

{query}

Focus:
- Query flow
- Joins
- Filters
- Output

Be concise.
"""))

            elif debug and query.strip():
                st.write(ask_ai(f"""
Debug this SQL:

{query}

Provide:
1. Mistake
2. Correct query
3. Why

Be precise.
"""))

            elif hint:
                st.write(ask_ai(f"""
Question:
{q['description']}

Give a hint only.
Do NOT give full solution.
"""))

        # ---------------- SOLUTION ----------------
        st.markdown("---")
        with st.expander("💡 Show Solution"):
            st.code(q.get("solution", ""), language="sql")