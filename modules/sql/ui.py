import re
import time
import uuid

import streamlit as st

from core.ai import ask_ai
from core.interview import (
    append_interview_run,
    build_history_entry,
    build_interview_questions,
    calculate_question_score,
    filter_questions,
    load_interview_history,
    summarize_interview,
)
from core.loader import group_by_category, load_questions
from core.progress import clear_progress, load_progress, save_progress
from modules.sql.engine import create_db, is_pyspark_available, run_pyspark_code, run_query
from modules.sql.validator import validate

EDITOR_TRACKS = {
    "SQL": "sql",
    "PySpark": "pyspark",
}

WORKSPACES = ["Practice", "Interview Simulator"]
INTERVIEW_DIFFICULTIES = ["Easy", "Medium", "Hard"]
INTERVIEW_STATE_KEY = "sql_interview_state"
INTERVIEW_REPORT_KEY = "sql_interview_report"


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


def get_filtered_query_list(name, allowed_values, default):
    if name not in st.query_params:
        return list(default)

    raw_value = get_query_param(name, "")
    if raw_value == "":
        return []

    requested = [item.strip() for item in str(raw_value).split(",") if item.strip()]
    filtered = [item for item in requested if item in allowed_values]

    if requested and not filtered:
        return list(default)

    return filtered


def get_int_query_param(name, default, min_value=None, max_value=None):
    if name not in st.query_params:
        return default

    try:
        value = int(get_query_param(name, default))
    except (TypeError, ValueError):
        value = default

    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)

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


def format_duration(total_seconds):
    total_seconds = max(int(total_seconds), 0)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return f"{minutes:02d}:{seconds:02d}"


def render_execution_result(result):
    row_count = len(result.index)
    column_count = len(result.columns)
    st.caption(f"Result: {row_count} rows x {column_count} columns")

    if row_count == 0:
        st.info("Code executed successfully, but the result has no rows.")

    st.dataframe(result, use_container_width=True, hide_index=True)


def get_first_table_name(question):
    return next(iter(question["tables"]), "table_name")


def build_editor_starter(question, editor_mode):
    first_table = get_first_table_name(question)

    if editor_mode == "SQL":
        return f"SELECT *\nFROM {first_table}\nLIMIT 10;"

    return (
        "from pyspark.sql.functions import *\n"
        "from pyspark.sql.window import Window\n\n"
        "result = (\n"
        f"    {first_table}\n"
        ")\n"
    )


def execute_code(question, editor_mode, query):
    if editor_mode == "SQL":
        conn = create_db(question["tables"])
        return run_query(conn, query)

    return run_pyspark_code(question["tables"], query)


def mark_question_solved(editor_mode, question_key):
    progress_track = EDITOR_TRACKS[editor_mode]
    solved = load_progress(progress_track)
    solved.add(question_key)
    save_progress(solved, progress_track)


def get_interview_state():
    return st.session_state.get(INTERVIEW_STATE_KEY)


def clear_interview_state(clear_report=False):
    interview_state = st.session_state.pop(INTERVIEW_STATE_KEY, None)

    if interview_state:
        session_id = interview_state.get("session_id")
        for question in interview_state.get("questions", []):
            question_key = question["progress_key"]
            st.session_state.pop(f"interview_output_{session_id}_{question_key}", None)

    if clear_report:
        st.session_state.pop(INTERVIEW_REPORT_KEY, None)


def start_interview(questions, editor_mode, question_count, categories, difficulties, minutes_per_question):
    selected_questions = build_interview_questions(
        questions,
        question_count=question_count,
        categories=categories,
        difficulties=difficulties,
    )

    clear_interview_state(clear_report=True)

    st.session_state[INTERVIEW_STATE_KEY] = {
        "session_id": uuid.uuid4().hex,
        "editor_mode": editor_mode,
        "categories": list(categories),
        "difficulties": list(difficulties),
        "minutes_per_question": minutes_per_question,
        "questions": selected_questions,
        "started_at": time.time(),
        "total_duration_seconds": len(selected_questions) * minutes_per_question * 60,
        "current_index": 0,
        "question_started_at": time.time(),
        "results": {},
    }


def advance_interview_question():
    interview_state = get_interview_state()
    if not interview_state:
        return

    interview_state["current_index"] += 1
    interview_state["question_started_at"] = time.time()
    st.session_state[INTERVIEW_STATE_KEY] = interview_state


def finalize_interview(reason):
    interview_state = get_interview_state()
    if not interview_state:
        return None

    question_results = []
    now = time.time()
    elapsed_seconds = min(
        int(now - interview_state["started_at"]),
        interview_state["total_duration_seconds"],
    )

    for question in interview_state["questions"]:
        question_key = question["progress_key"]
        stored_result = interview_state["results"].get(question_key, {})
        question_results.append({
            "progress_key": question_key,
            "title": question["title"],
            "category": question["category"],
            "difficulty": question["difficulty"],
            "attempts": stored_result.get("attempts", 0),
            "correct": stored_result.get("correct", False),
            "skipped": stored_result.get("skipped", False),
            "time_spent_seconds": int(stored_result.get("time_spent_seconds", 0)),
            "score": stored_result.get("score", 0),
        })

    interview_summary = summarize_interview(question_results)
    history_entry = build_history_entry(
        track=interview_state["editor_mode"],
        categories=interview_state["categories"],
        difficulties=interview_state["difficulties"],
        minutes_per_question=interview_state["minutes_per_question"],
        interview_summary=interview_summary,
        question_results=question_results,
    )
    history_entry["finished_reason"] = reason
    history_entry["elapsed_seconds"] = elapsed_seconds
    append_interview_run(history_entry)

    st.session_state[INTERVIEW_REPORT_KEY] = history_entry
    clear_interview_state(clear_report=False)
    return history_entry


def render_question_content(question, show_expected_output=True):
    st.subheader(question["title"])
    meta = f"`{question['category']}`"
    if "difficulty" in question:
        meta += f"  |  `{question['difficulty']}`"
    st.caption(meta)

    tags = question.get("tags", [])
    if tags:
        st.caption("Tags: " + " ".join(f"`{tag}`" for tag in tags))

    if show_expected_output:
        prompt_tab, tables_tab, output_tab = st.tabs(["Prompt", "Input Tables", "Expected Output"])
    else:
        prompt_tab, tables_tab = st.tabs(["Prompt", "Input Tables"])
        output_tab = None

    with prompt_tab:
        st.write(question["description"])

    with tables_tab:
        for table, data in question["tables"].items():
            st.markdown(f"#### {table}")
            render_compact_table(data)

    if output_tab is not None:
        with output_tab:
            render_compact_table(question["expected_output"])


def render_practice_workspace(questions):
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

    solved = load_progress(EDITOR_TRACKS[st.session_state.editor_mode])

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
    solved_in_submodule = sum(1 for question in sub_qs if question["progress_key"] in solved)
    solved_overall = sum(1 for question in questions if question["progress_key"] in solved)
    progress_ratio = solved_in_submodule / len(sub_qs) if sub_qs else 0.0

    st.sidebar.progress(progress_ratio)
    st.sidebar.caption(
        f"{solved_in_submodule}/{len(sub_qs)} solved in {selected_submodule}  |  "
        f"{solved_overall}/{len(questions)} overall for {st.session_state.editor_mode}"
    )

    selected_question_key = get_query_param("question", sub_qs[0]["progress_key"])

    if selected_question_key not in sub_q_keys:
        selected_question_key = sub_qs[0]["progress_key"]

    st.query_params["question"] = selected_question_key

    st.sidebar.markdown("### Questions")
    st.sidebar.caption(f"Progress view: {st.session_state.editor_mode}")

    for question in sub_qs:
        question_key = question["progress_key"]
        label = f"{question['id']}. {question['title']}"

        if question_key == selected_question_key:
            label = "▶ " + label
        if question_key in solved:
            label = "✅ " + label

        if st.sidebar.button(label, key=f"q_{question_key}"):
            st.query_params["question"] = question_key
            st.rerun()

    question = next(item for item in sub_qs if item["progress_key"] == selected_question_key)
    question_key = selected_question_key

    col1, col2 = st.columns([2, 3])

    with col1:
        render_question_content(question)

    with col2:
        st.subheader("Editor")

        editor_mode = st.radio(
            "Mode",
            ["SQL", "PySpark"],
            horizontal=True,
            key="editor_mode",
        )
        st.query_params["editor_mode"] = editor_mode

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

        query_key = f"query_{question_key}_{editor_mode.lower()}"
        starter_template = build_editor_starter(question, editor_mode)

        helper_col1, helper_col2 = st.columns(2)
        if helper_col1.button("Load Starter", key=f"practice_starter_{question_key}_{editor_mode}"):
            st.session_state[query_key] = starter_template
        if helper_col2.button("Clear Draft", key=f"practice_clear_{question_key}_{editor_mode}"):
            st.session_state[query_key] = ""

        query = st.text_area(
            f"Write {editor_mode}",
            height=500,
            key=query_key,
            placeholder=starter_template,
        )

        c1, c2 = st.columns(2)
        run = c1.button("Run", key=f"practice_run_{question_key}_{editor_mode}")
        submit = c2.button("Submit", key=f"practice_submit_{question_key}_{editor_mode}")

        if run or submit:
            if not query.strip():
                st.warning(f"Write {editor_mode} code")
            else:
                result, error = execute_code(question, editor_mode, query)

                if error:
                    st.error(error)
                else:
                    render_execution_result(result)

                    if submit:
                        if validate(result, question["expected_output"]):
                            mark_question_solved(editor_mode, question_key)
                            st.success("Correct")
                        else:
                            st.error("Incorrect")

        st.markdown("### AI Tools")

        c_a, c_b = st.columns(2)
        hint = c_a.button("Hint", key=f"practice_hint_{question_key}_{editor_mode}")
        explain = c_b.button("Explain", key=f"practice_explain_{question_key}_{editor_mode}")

        if hint:
            st.write(ask_ai(f"Hint for {editor_mode}:\n{question['description']}"))
        elif explain and query.strip():
            st.write(ask_ai(f"Explain this {editor_mode} code:\n{query}"))

        with st.expander("Show Solution"):
            sql_tab, pyspark_tab = st.tabs(["SQL", "PySpark"])

            with sql_tab:
                st.code(format_sql_vertical(question.get("sql_solution", "")), language="sql")

            with pyspark_tab:
                st.code(question.get("pyspark_solution", ""), language="python")


def render_interview_setup(questions):
    st.title("Interview Simulator")
    st.write("Run a timed interview set with random questions, per-question scoring, and a final report.")

    available_categories = sorted({question["category"] for question in questions})

    if "interview_editor_mode" not in st.session_state:
        st.session_state.interview_editor_mode = get_query_param("interview_track", "SQL")

    if st.session_state.interview_editor_mode not in EDITOR_TRACKS:
        st.session_state.interview_editor_mode = "SQL"

    if "interview_categories" not in st.session_state:
        st.session_state.interview_categories = get_filtered_query_list(
            "interview_categories",
            available_categories,
            available_categories,
        )

    if "interview_difficulties" not in st.session_state:
        st.session_state.interview_difficulties = get_filtered_query_list(
            "interview_difficulties",
            INTERVIEW_DIFFICULTIES,
            INTERVIEW_DIFFICULTIES,
        )

    filtered_questions = filter_questions(
        questions,
        categories=st.session_state.interview_categories,
        difficulties=st.session_state.interview_difficulties,
    )
    available_count = len(filtered_questions)

    if "interview_question_count" not in st.session_state:
        st.session_state.interview_question_count = get_int_query_param(
            "interview_questions",
            min(5, max(available_count, 1)),
            min_value=1,
            max_value=max(1, min(10, available_count)),
        )

    if "interview_minutes_per_question" not in st.session_state:
        st.session_state.interview_minutes_per_question = get_int_query_param(
            "interview_minutes",
            8,
            min_value=3,
            max_value=20,
        )

    max_questions = max(1, min(10, available_count))
    if st.session_state.interview_question_count > max_questions:
        st.session_state.interview_question_count = max_questions

    setup_col, summary_col = st.columns([2, 1])

    with setup_col:
        st.subheader("Setup")

        editor_mode = st.selectbox(
            "Interview Track",
            ["SQL", "PySpark"],
            key="interview_editor_mode",
        )

        st.multiselect(
            "Categories",
            available_categories,
            key="interview_categories",
        )
        st.multiselect(
            "Difficulty",
            INTERVIEW_DIFFICULTIES,
            key="interview_difficulties",
        )

        filtered_questions = filter_questions(
            questions,
            categories=st.session_state.interview_categories,
            difficulties=st.session_state.interview_difficulties,
        )
        available_count = len(filtered_questions)
        max_questions = max(1, min(10, available_count))

        if st.session_state.interview_question_count > max_questions:
            st.session_state.interview_question_count = max_questions

        st.slider(
            "Questions",
            min_value=1,
            max_value=max_questions,
            key="interview_question_count",
        )
        st.slider(
            "Minutes Per Question",
            min_value=3,
            max_value=20,
            key="interview_minutes_per_question",
        )

        st.query_params["interview_track"] = editor_mode
        st.query_params["interview_categories"] = ",".join(st.session_state.interview_categories)
        st.query_params["interview_difficulties"] = ",".join(st.session_state.interview_difficulties)
        st.query_params["interview_questions"] = str(st.session_state.interview_question_count)
        st.query_params["interview_minutes"] = str(st.session_state.interview_minutes_per_question)

        total_minutes = st.session_state.interview_question_count * st.session_state.interview_minutes_per_question
        st.caption(
            "Scoring per question: 70 correctness + 20 time-budget credit + 10 attempts. "
            "A first correct submission within the question budget earns 100. "
            f"Current total time: {total_minutes} minutes."
        )

        pyspark_blocked = editor_mode == "PySpark" and not is_pyspark_available()
        if pyspark_blocked:
            st.warning("PySpark interviews require Streamlit to run from your virtual environment.")

        if available_count == 0:
            st.warning("No questions match the selected filters. Adjust category or difficulty to continue.")

        if st.button(
            "Start Interview",
            disabled=available_count == 0 or pyspark_blocked,
            key="start_interview",
        ):
            start_interview(
                questions=questions,
                editor_mode=editor_mode,
                question_count=st.session_state.interview_question_count,
                categories=st.session_state.interview_categories,
                difficulties=st.session_state.interview_difficulties,
                minutes_per_question=st.session_state.interview_minutes_per_question,
            )
            st.rerun()

    with summary_col:
        st.subheader("Preview")
        st.metric("Available Questions", available_count)
        st.metric("Selected Questions", st.session_state.interview_question_count)
        st.metric("Total Interview Time", f"{total_minutes} min")

    history = load_interview_history()
    if history:
        st.markdown("### Recent Interview Runs")
        recent_rows = []
        for run in reversed(history[-5:]):
            recent_rows.append({
                "finished_at": run["finished_at"],
                "track": run["track"],
                "score": f"{run['total_score']} / {run['max_score']}",
                "accuracy": f"{run['correct_count']} / {run['total_questions']}",
                "time_used": format_duration(run.get("elapsed_seconds", 0)),
            })

        st.dataframe(recent_rows, use_container_width=True, hide_index=True)


def render_interview_report(report):
    st.title("Interview Report")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Score", f"{report['total_score']} / {report['max_score']}")
    col2.metric("Accuracy", f"{report['correct_count']} / {report['total_questions']}")
    col3.metric("Score %", f"{report['score_percent']}%")
    col4.metric("Time Used", format_duration(report.get("elapsed_seconds", 0)))

    detail_col1, detail_col2, detail_col3 = st.columns(3)
    detail_col1.caption(f"Track: {report['track']}")
    detail_col2.caption(f"Finished: {report['finished_reason'].replace('_', ' ').title()}")
    detail_col3.caption(f"Ended At: {report['finished_at']}")

    rows = []
    for item in report["questions"]:
        status = "Correct"
        if item.get("skipped"):
            status = "Skipped"
        elif not item["correct"]:
            status = "Incorrect"

        rows.append({
            "title": item["title"],
            "category": item["category"],
            "difficulty": item["difficulty"],
            "status": status,
            "attempts": item["attempts"],
            "score": f"{item['score']} / 100",
            "time_spent": format_duration(item["time_spent_seconds"]),
        })

    st.markdown("### Question Breakdown")
    st.dataframe(rows, use_container_width=True, hide_index=True)

    if st.button("Start New Interview", key="restart_interview"):
        clear_interview_state(clear_report=True)
        st.rerun()


def render_active_interview():
    interview_state = get_interview_state()
    if not interview_state:
        return

    now = time.time()
    remaining_seconds = interview_state["total_duration_seconds"] - int(now - interview_state["started_at"])
    if remaining_seconds <= 0:
        finalize_interview("time_up")
        st.rerun()

    current_question = interview_state["questions"][interview_state["current_index"]]
    question_key = current_question["progress_key"]
    session_id = interview_state["session_id"]
    output_key = f"interview_output_{session_id}_{question_key}"
    current_result = interview_state["results"].get(question_key, {})
    is_locked = current_result.get("correct", False) or current_result.get("skipped", False)

    answered_count = sum(
        1 for result in interview_state["results"].values()
        if result.get("correct") or result.get("skipped")
    )
    running_score = sum(result.get("score", 0) for result in interview_state["results"].values())
    question_elapsed_seconds = int(now - interview_state["question_started_at"])
    question_budget_seconds = interview_state["minutes_per_question"] * 60
    question_progress = min(question_elapsed_seconds / max(question_budget_seconds, 1), 1.0)

    st.title("Interview Simulator")

    top_col1, top_col2, top_col3, top_col4 = st.columns(4)
    top_col1.metric(
        "Question",
        f"{interview_state['current_index'] + 1} / {len(interview_state['questions'])}",
    )
    top_col2.metric("Track", interview_state["editor_mode"])
    top_col3.metric("Question Time", format_duration(question_elapsed_seconds))
    top_col4.metric("Time Remaining", format_duration(remaining_seconds))
    st.caption(
        f"Answered: {answered_count} / {len(interview_state['questions'])}  |  "
        f"Current score: {running_score} / {len(interview_state['questions']) * 100}"
    )
    st.progress(
        question_progress,
        text=(
            f"Question budget: {format_duration(question_elapsed_seconds)} elapsed "
            f"out of {format_duration(question_budget_seconds)}"
        ),
    )

    col1, col2 = st.columns([2, 3])

    with col1:
        render_question_content(current_question)

    with col2:
        st.subheader(f"{interview_state['editor_mode']} Editor")
        st.caption(
            "Run your code as many times as you want. Scoring uses only correctness, time spent, and the "
            "number of submit attempts."
        )

        if interview_state["editor_mode"] == "PySpark":
            st.caption(
                "Write DataFrame API code. The app will display `result` if you assign it, "
                "or the last DataFrame variable you create."
            )

        query_key = f"interview_query_{session_id}_{question_key}_{interview_state['editor_mode'].lower()}"
        starter_template = build_editor_starter(current_question, interview_state["editor_mode"])

        helper_col1, helper_col2 = st.columns(2)
        if helper_col1.button("Load Starter", key=f"interview_starter_{question_key}", disabled=is_locked):
            st.session_state[query_key] = starter_template
        if helper_col2.button("Clear Draft", key=f"interview_clear_{question_key}", disabled=is_locked):
            st.session_state[query_key] = ""

        query = st.text_area(
            f"Write {interview_state['editor_mode']}",
            height=500,
            key=query_key,
            disabled=is_locked,
            placeholder=starter_template,
        )

        button_col1, button_col2, button_col3 = st.columns(3)
        run = button_col1.button("Run Code", key=f"run_{question_key}", disabled=is_locked)
        submit = button_col2.button("Submit Answer", key=f"submit_{question_key}", disabled=is_locked)
        skip = button_col3.button("Skip Question", key=f"skip_{question_key}", disabled=is_locked)

        if run or submit:
            if not query.strip():
                st.warning(f"Write {interview_state['editor_mode']} code")
            else:
                result, error = execute_code(current_question, interview_state["editor_mode"], query)
                st.session_state[output_key] = {
                    "result": result,
                    "error": error,
                }

                if error:
                    st.error(error)
                else:
                    render_execution_result(result)

                    if submit:
                        attempts = current_result.get("attempts", 0) + 1
                        time_spent_seconds = int(time.time() - interview_state["question_started_at"])

                        if validate(result, current_question["expected_output"]):
                            score = calculate_question_score(
                                correct=True,
                                time_spent_seconds=time_spent_seconds,
                                attempts=attempts,
                                minutes_per_question=interview_state["minutes_per_question"],
                            )
                            interview_state["results"][question_key] = {
                                "attempts": attempts,
                                "correct": True,
                                "skipped": False,
                                "time_spent_seconds": time_spent_seconds,
                                "score": score,
                            }
                            st.session_state[INTERVIEW_STATE_KEY] = interview_state
                            mark_question_solved(interview_state["editor_mode"], question_key)
                            st.success(f"Correct. You earned {score} points on this question.")
                            st.rerun()

                        interview_state["results"][question_key] = {
                            "attempts": attempts,
                            "correct": False,
                            "skipped": False,
                            "time_spent_seconds": time_spent_seconds,
                            "score": 0,
                        }
                        st.session_state[INTERVIEW_STATE_KEY] = interview_state
                        current_result = interview_state["results"][question_key]
                        st.error("Incorrect. Update your answer and submit again.")

        stored_output = st.session_state.get(output_key)
        if stored_output and not (run or submit):
            if stored_output.get("error"):
                st.error(stored_output["error"])
            elif stored_output.get("result") is not None:
                render_execution_result(stored_output["result"])

        if skip:
            interview_state["results"][question_key] = {
                "attempts": current_result.get("attempts", 0),
                "correct": False,
                "skipped": True,
                "time_spent_seconds": int(time.time() - interview_state["question_started_at"]),
                "score": 0,
            }
            st.session_state[INTERVIEW_STATE_KEY] = interview_state
            st.rerun()

        st.markdown("### Status")
        status_col1, status_col2, status_col3 = st.columns(3)
        status_col1.metric("Attempts", current_result.get("attempts", 0))
        status_col2.metric("Question Time", format_duration(question_elapsed_seconds))
        status_col3.metric(
            "Score Earned",
            f"{current_result.get('score', 0)} / 100" if is_locked else "-- / 100",
        )
        if current_result.get("correct"):
            st.success("Question completed. Move to the next one when you're ready.")
        elif current_result.get("skipped"):
            st.info("Question skipped. Move to the next one or finish the interview.")
        else:
            st.caption(
                "A first correct submission within the question budget earns full speed credit. "
                "Extra submits reduce only the attempts portion of the score."
            )

        next_label = "Finish Interview" if interview_state["current_index"] == len(interview_state["questions"]) - 1 else "Next Question"
        next_disabled = not is_locked
        if st.button(next_label, key=f"next_{question_key}", disabled=next_disabled):
            if interview_state["current_index"] == len(interview_state["questions"]) - 1:
                finalize_interview("completed")
            else:
                advance_interview_question()
            st.rerun()

        if st.button("End Interview Early", key="finish_interview_now"):
            finalize_interview("ended_early")
            st.rerun()


def render_interview_workspace(questions):
    if get_interview_state():
        render_active_interview()
        return

    report = st.session_state.get(INTERVIEW_REPORT_KEY)
    if report:
        render_interview_report(report)
        return

    render_interview_setup(questions)


def render_sql():
    questions = load_questions("sql")

    if not questions:
        st.error("No SQL questions found.")
        return

    st.sidebar.title("Coding Workspace")

    initial_workspace = get_query_param("workspace", WORKSPACES[0])
    if initial_workspace not in WORKSPACES:
        initial_workspace = WORKSPACES[0]

    if "sql_workspace" not in st.session_state or st.session_state.sql_workspace not in WORKSPACES:
        st.session_state.sql_workspace = initial_workspace

    workspace = st.sidebar.radio(
        "Workspace",
        WORKSPACES,
        key="sql_workspace",
    )
    st.query_params["workspace"] = workspace

    if workspace == "Practice":
        render_practice_workspace(questions)
    else:
        render_interview_workspace(questions)
