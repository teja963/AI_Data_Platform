import html
import time
import uuid
from pprint import pformat

import pandas as pd
import streamlit as st

from core.ai import ask_ai
from core.editor import clear_editor_draft, render_code_editor, set_editor_draft
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
from modules.python.engine import preview_python_question, run_python_question

WORKSPACES = ["Practice", "Interview Simulator"]
INTERVIEW_DIFFICULTIES = ["Easy", "Medium"]
INTERVIEW_STATE_KEY = "python_interview_state"
INTERVIEW_REPORT_KEY = "python_interview_report"


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


def format_duration(total_seconds):
    total_seconds = max(int(total_seconds), 0)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def preview_value(value):
    if isinstance(value, pd.DataFrame):
        return value.head(8).to_dict(orient="records")
    return value


def render_wrapped_value(value):
    if isinstance(value, pd.DataFrame):
        st.dataframe(value, use_container_width=True, hide_index=True)
        return

    rendered = pformat(preview_value(value), width=70, sort_dicts=False)
    st.markdown(
        (
            "<div class='coding-io-box' style='padding:10px;'>"
            f"<pre style='white-space:pre-wrap;word-break:break-word;margin:0;font-size:12px;color:inherit;'>"
            f"{html.escape(rendered)}</pre></div>"
        ),
        unsafe_allow_html=True,
    )


def render_result_panel(execution):
    if execution.get("error"):
        st.error(execution["error"])
        return

    results = execution.get("results", [])
    show_expected = any(item.get("expected") is not None for item in results)
    passed_count = sum(1 for item in results if item["passed"])

    if show_expected:
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        metric_col1.metric("Passed", passed_count)
        metric_col2.metric("Failed", len(results) - passed_count)
        metric_col3.metric("Coverage", f"{passed_count}/{len(results)}")
    else:
        metric_col1, metric_col2 = st.columns(2)
        metric_col1.metric("Run Status", "Executed" if passed_count == len(results) else "Execution Error")
        metric_col2.metric("Example Inputs", len(results))

    for item in results:
        with st.container(border=True):
            header_col1, header_col2 = st.columns([1, 4])
            with header_col1:
                if show_expected:
                    badge = "PASS" if item["passed"] else "FAIL"
                else:
                    badge = "RUN" if item["passed"] else "ERROR"
                st.markdown(f"**{badge}**")
            with header_col2:
                st.markdown(f"**{item['test']}**")
                st.caption(item["message"])

            if show_expected:
                detail_col1, detail_col2 = st.columns(2)
                with detail_col1:
                    st.markdown("**Expected**")
                    render_wrapped_value(item["expected"])
                with detail_col2:
                    st.markdown("**Actual**")
                    render_wrapped_value(item["actual"])
            else:
                st.markdown("**Actual Output**")
                render_wrapped_value(item["actual"])

            if item.get("stdout"):
                st.markdown("**Captured Print Output**")
                st.code(item["stdout"], language="text", wrap_lines=True)

    if execution.get("stdout"):
        with st.expander("Captured Output"):
            st.code(execution["stdout"], language="text", wrap_lines=True)


def render_question_content(question, show_solution_note=True):
    st.subheader(question["title"])
    meta = f"`{question['category']}`  |  `{question['difficulty']}`"
    st.caption(meta)

    tags = question.get("tags", [])
    if tags:
        st.caption("Tags: " + " ".join(f"`{tag}`" for tag in tags))

    prompt_tab, examples_tab, evaluator_tab = st.tabs(["Prompt", "Examples", "Evaluator"])

    with prompt_tab:
        st.info(question["submission_mode"])
        if question.get("practice_fixture_paths"):
            st.caption("Sample practice files for local runs:")
            for path in question["practice_fixture_paths"]:
                st.markdown(f"- `{path}`")

        st.markdown("#### Problem")
        st.write(question["description"])

        contract_col1, contract_col2 = st.columns(2)
        with contract_col1:
            st.markdown("#### What To Write")
            render_wrapped_value(f"def {question['signature']}:")
            st.markdown("#### Input Format")
            for item in question["input_format"]:
                st.markdown(f"- {item}")
        with contract_col2:
            st.markdown("#### Output Format")
            st.write(question["output_format"])
            st.markdown("#### Constraints")
            for item in question["constraints"]:
                st.markdown(f"- {item}")

        if show_solution_note:
            st.caption(
                "Submit expects only the function. Use the main-template button only when you want optional local scratch practice."
            )

    with examples_tab:
        for example in question["examples"]:
            with st.container(border=True):
                st.markdown(f"**{example['label']}**")
                if example.get("files"):
                    st.markdown("**Fixture Files**")
                    for path, content in example["files"].items():
                        st.markdown(f"- `{path}`")
                        render_wrapped_value(content)
                example_col1, example_col2 = st.columns(2)
                with example_col1:
                    st.markdown("**Input**")
                    render_wrapped_value(example["inputs"])
                with example_col2:
                    st.markdown("**Expected Output**")
                    render_wrapped_value(example["expected"])

    with evaluator_tab:
        st.markdown(f"- Base regression cases: `{len(question['tests'])}`")
        st.markdown(f"- Function name required: `{question['entry_point']}`")
        st.markdown("- Submission mode: function only")
        st.markdown("- `input()` and `__main__` are not required for submission")
        st.markdown("- `Run` previews your function output on the visible examples")
        st.markdown("- `Submit` validates against the full backend evaluator")
        if any(test.get("files") for test in question["tests"]):
            st.markdown("- File paths are passed into the function by the evaluator")
        if any(isinstance(test["expected"], pd.DataFrame) for test in question["tests"]):
            st.markdown("- Includes pandas-style result validation")


def mark_question_solved(question_key):
    solved = load_progress("python")
    solved.add(question_key)
    save_progress(solved, "python")


def render_ai_tools(question, code, button_prefix):
    st.markdown("### AI Tools")
    col1, col2 = st.columns(2)
    hint = col1.button("Hint", key=f"{button_prefix}_hint")
    explain = col2.button("Explain", key=f"{button_prefix}_explain")

    if hint:
        st.info(question["hint"])
    elif explain:
        if not code.strip():
            st.warning("Write some code first so the explanation has something to inspect.")
        else:
            preview = preview_python_question(question, code)
            preview_lines = []
            if preview.get("error"):
                preview_lines.append(f"Execution error: {preview['error']}")
            else:
                for item in preview.get("results", []):
                    preview_lines.append(
                        f"{item['test']}: status={item['message']} actual={preview_value(item.get('actual'))!r}"
                    )
            st.write(
                ask_ai(
                    (
                        f"Question:\n{question['description']}\n\n"
                        f"Candidate code:\n```python\n{code}\n```\n\n"
                        f"Observed execution summary:\n" + "\n".join(preview_lines)
                    ),
                    system_prompt=(
                        "You are a Python interview coach for a data engineering candidate. "
                        "Explain only what the candidate's current code does, what mistakes or runtime errors it has, "
                        "and whether it matches the prompt. Do not provide replacement code, corrected code, "
                        "pseudocode, or the full solution. Keep the explanation concise and code-free."
                    ),
                )
            )

    with st.expander("Show Solution"):
        st.code(question["solution"], language="python", wrap_lines=True)


def render_practice_workspace(questions):
    grouped = group_by_category(questions)
    categories = list(grouped.keys())
    difficulty_rank = {"Medium": 0, "Easy": 1, "Hard": 2}

    initial_category = get_query_param("py_category", categories[0])
    if initial_category not in grouped:
        initial_category = categories[0]

    if "python_category" not in st.session_state or st.session_state.python_category not in grouped:
        st.session_state.python_category = initial_category

    solved = load_progress("python")

    if st.sidebar.button("Reset Python Progress"):
        clear_progress("python")
        solved = set()
        st.sidebar.success("Python progress cleared.")

    selected_category = st.sidebar.selectbox("Category", categories, key="python_category")
    st.query_params["py_category"] = selected_category

    category_questions = sorted(
        grouped[selected_category],
        key=lambda question: (difficulty_rank.get(question.get("difficulty", "Medium"), 9), question["id"]),
    )
    category_keys = {question["progress_key"] for question in category_questions}

    selected_question_key = get_query_param("py_question", category_questions[0]["progress_key"])
    if selected_question_key not in category_keys:
        selected_question_key = category_questions[0]["progress_key"]
    st.query_params["py_question"] = selected_question_key

    solved_in_category = sum(1 for question in category_questions if question["progress_key"] in solved)
    progress_ratio = solved_in_category / len(category_questions) if category_questions else 0.0
    st.sidebar.progress(progress_ratio)
    st.sidebar.caption(
        f"{solved_in_category}/{len(category_questions)} solved in {selected_category}  |  "
        f"{len(solved)}/{len(questions)} overall"
    )

    st.sidebar.markdown("### Questions")
    for question in category_questions:
        question_key = question["progress_key"]
        label = f"{question['id']}. {question['title']} ({question['difficulty']})"
        if question_key == selected_question_key:
            label = "▶ " + label
        if question_key in solved:
            label = "✅ " + label
        if st.sidebar.button(label, key=f"python_q_{question_key}"):
            st.query_params["py_question"] = question_key
            st.rerun()

    question = next(item for item in category_questions if item["progress_key"] == selected_question_key)
    result_key = f"python_result_{selected_question_key}"
    draft_key = f"python_practice::{selected_question_key}"
    starter = question["starter_code"]

    left_col, right_col = st.columns([3, 4])

    with left_col:
        render_question_content(question)

    with right_col:
        st.subheader("Editor")
        st.caption("Tab inserts indentation. The editor syncs live, so Run always uses the latest code on screen and drafts stay preserved.")
        helper_col1, helper_col2, helper_col3 = st.columns(3)
        if helper_col1.button("Function Template", key=f"{selected_question_key}_starter"):
            set_editor_draft(draft_key, starter)
            st.rerun()
        if helper_col2.button("Main Template", key=f"{selected_question_key}_script_starter"):
            set_editor_draft(draft_key, question["script_starter"])
            st.rerun()
        if helper_col3.button("Clear Draft", key=f"{selected_question_key}_clear"):
            clear_editor_draft(draft_key)
            st.rerun()

        code = render_code_editor(
            draft_key=draft_key,
            language="python",
            starter=starter,
            height=520,
            placeholder=starter,
        )

        button_col1, button_col2 = st.columns(2)
        run = button_col1.button("Run", key=f"{selected_question_key}_run")
        submit = button_col2.button("Submit", key=f"{selected_question_key}_submit")

        if run or submit:
            if not code.strip():
                st.warning("Write a Python function before running.")
            else:
                execution = preview_python_question(question, code) if run else run_python_question(question, code)
                st.session_state[result_key] = {
                    "mode": "preview" if run else "submit",
                    "execution": execution,
                }
                render_result_panel(execution)

                if submit:
                    if execution["passed"]:
                        mark_question_solved(selected_question_key)
                        st.success("All tests passed. Progress saved.")
                    else:
                        st.error("Some tests are still failing. Refine the solution and submit again.")
        elif result_key in st.session_state:
            stored_result = st.session_state[result_key]
            render_result_panel(stored_result.get("execution", stored_result))

        render_ai_tools(question, code, f"practice_{selected_question_key}")


def get_interview_state():
    return st.session_state.get(INTERVIEW_STATE_KEY)


def clear_interview_state(clear_report=False):
    interview_state = st.session_state.pop(INTERVIEW_STATE_KEY, None)
    if interview_state:
        session_id = interview_state.get("session_id")
        for question in interview_state.get("questions", []):
            question_key = question["progress_key"]
            st.session_state.pop(f"python_interview_result_{session_id}_{question_key}", None)
    if clear_report:
        st.session_state.pop(INTERVIEW_REPORT_KEY, None)


def start_interview(questions, question_count, categories, difficulties, minutes_per_question):
    selected_questions = build_interview_questions(
        questions,
        question_count=question_count,
        categories=categories,
        difficulties=difficulties,
    )

    clear_interview_state(clear_report=True)
    st.session_state[INTERVIEW_STATE_KEY] = {
        "session_id": uuid.uuid4().hex,
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
        question_results.append(
            {
                "progress_key": question_key,
                "title": question["title"],
                "category": question["category"],
                "difficulty": question["difficulty"],
                "attempts": stored_result.get("attempts", 0),
                "correct": stored_result.get("correct", False),
                "skipped": stored_result.get("skipped", False),
                "time_spent_seconds": int(stored_result.get("time_spent_seconds", 0)),
                "score": stored_result.get("score", 0),
            }
        )

    interview_summary = summarize_interview(question_results)
    history_entry = build_history_entry(
        track="Python",
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


def render_interview_setup(questions):
    st.title("Python Interview Simulator")
    st.write("Run a timed set of Python questions covering DSA, files, APIs, pandas, and data-engineering patterns.")

    available_categories = sorted({question["category"] for question in questions})

    if "python_interview_categories" not in st.session_state:
        st.session_state.python_interview_categories = get_filtered_query_list(
            "python_interview_categories",
            available_categories,
            available_categories,
        )

    if "python_interview_difficulties" not in st.session_state:
        st.session_state.python_interview_difficulties = get_filtered_query_list(
            "python_interview_difficulties",
            INTERVIEW_DIFFICULTIES,
            INTERVIEW_DIFFICULTIES,
        )

    filtered_questions = filter_questions(
        questions,
        categories=st.session_state.python_interview_categories,
        difficulties=st.session_state.python_interview_difficulties,
    )
    available_count = len(filtered_questions)

    if "python_interview_question_count" not in st.session_state:
        st.session_state.python_interview_question_count = get_int_query_param(
            "python_interview_questions",
            min(5, max(available_count, 1)),
            min_value=1,
            max_value=max(1, min(10, available_count)),
        )

    if "python_interview_minutes" not in st.session_state:
        st.session_state.python_interview_minutes = get_int_query_param(
            "python_interview_minutes",
            8,
            min_value=3,
            max_value=20,
        )

    max_questions = max(1, min(10, available_count))
    if st.session_state.python_interview_question_count > max_questions:
        st.session_state.python_interview_question_count = max_questions

    setup_col, summary_col = st.columns([2, 1])

    with setup_col:
        st.subheader("Setup")
        st.multiselect("Categories", available_categories, key="python_interview_categories")
        st.multiselect("Difficulty", INTERVIEW_DIFFICULTIES, key="python_interview_difficulties")

        filtered_questions = filter_questions(
            questions,
            categories=st.session_state.python_interview_categories,
            difficulties=st.session_state.python_interview_difficulties,
        )
        available_count = len(filtered_questions)
        max_questions = max(1, min(10, available_count))

        st.slider(
            "Question Count",
            min_value=1,
            max_value=max_questions,
            key="python_interview_question_count",
        )
        st.slider(
            "Minutes Per Question",
            min_value=3,
            max_value=20,
            key="python_interview_minutes",
        )

        st.query_params["python_interview_categories"] = ",".join(st.session_state.python_interview_categories)
        st.query_params["python_interview_difficulties"] = ",".join(st.session_state.python_interview_difficulties)
        st.query_params["python_interview_questions"] = st.session_state.python_interview_question_count
        st.query_params["python_interview_minutes"] = st.session_state.python_interview_minutes

        if not filtered_questions:
            st.warning("No questions match the current filter set.")
        elif st.button("Start Interview", type="primary"):
            start_interview(
                questions,
                question_count=st.session_state.python_interview_question_count,
                categories=st.session_state.python_interview_categories,
                difficulties=st.session_state.python_interview_difficulties,
                minutes_per_question=st.session_state.python_interview_minutes,
            )
            st.rerun()

    with summary_col:
        st.subheader("Coverage")
        st.metric("Available Questions", available_count)
        st.metric("Categories", len(st.session_state.python_interview_categories))
        st.metric("Minutes / Question", st.session_state.python_interview_minutes)
        st.caption("The evaluator uses the same test harness as practice mode, so correctness is judged consistently.")

        python_runs = [run for run in load_interview_history() if run.get("track") == "Python"]
        if python_runs:
            latest = python_runs[-1]
            st.markdown("#### Latest Python Run")
            st.write(
                f"Score: **{latest['score_percent']}%**\n\n"
                f"Correct: **{latest['correct_count']} / {latest['total_questions']}**"
            )


def render_interview_report(report):
    st.title("Python Interview Report")

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Score", f"{report['score_percent']}%")
    metric_col2.metric("Correct", f"{report['correct_count']} / {report['total_questions']}")
    metric_col3.metric("Attempted", report["attempted_count"])
    metric_col4.metric("Elapsed", format_duration(report.get("elapsed_seconds", 0)))

    rows = []
    for question in report["questions"]:
        rows.append(
            {
                "Question": question["title"],
                "Category": question["category"],
                "Difficulty": question["difficulty"],
                "Attempts": question["attempts"],
                "Correct": "Yes" if question["correct"] else "No",
                "Skipped": "Yes" if question["skipped"] else "No",
                "Score": question["score"],
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)

    if st.button("New Interview"):
        st.session_state.pop(INTERVIEW_REPORT_KEY, None)
        st.rerun()


def render_active_interview():
    interview_state = get_interview_state()
    if not interview_state:
        return

    question = interview_state["questions"][interview_state["current_index"]]
    question_key = question["progress_key"]
    session_id = interview_state["session_id"]
    result_key = f"python_interview_result_{session_id}_{question_key}"
    draft_key = f"python_interview::{session_id}::{question_key}"

    total_elapsed = int(time.time() - interview_state["started_at"])
    remaining_total = max(interview_state["total_duration_seconds"] - total_elapsed, 0)
    question_elapsed = int(time.time() - interview_state["question_started_at"])
    current_result = interview_state["results"].get(question_key, {})
    is_locked = current_result.get("correct") or current_result.get("skipped")

    st.title("Python Interview In Progress")
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Question", f"{interview_state['current_index'] + 1}/{len(interview_state['questions'])}")
    metric_col2.metric("Total Time Left", format_duration(remaining_total))
    metric_col3.metric("Question Time", format_duration(question_elapsed))
    metric_col4.metric("Attempts", current_result.get("attempts", 0))

    if remaining_total <= 0:
        finalize_interview("time_limit")
        st.rerun()

    left_col, right_col = st.columns([2, 3])

    with left_col:
        render_question_content(question, show_solution_note=False)

    with right_col:
        st.subheader("Editor")
        st.caption("Tab inserts indentation. The editor syncs live, so Run uses the latest code on screen and drafts stay preserved.")
        code = render_code_editor(
            draft_key=draft_key,
            language="python",
            starter=question["starter_code"],
            height=520,
            placeholder=question["starter_code"],
            disabled=is_locked,
        )

        button_col1, button_col2, button_col3 = st.columns(3)
        run = button_col1.button("Run", key=f"run_{question_key}", disabled=is_locked)
        submit = button_col2.button("Submit", key=f"submit_{question_key}", disabled=is_locked)
        skip = button_col3.button("Skip", key=f"skip_{question_key}", disabled=is_locked)

        if run or submit:
            if not code.strip():
                st.warning("Write a Python function before running.")
            else:
                execution = preview_python_question(question, code) if run else run_python_question(question, code)
                st.session_state[result_key] = {
                    "mode": "preview" if run else "submit",
                    "execution": execution,
                }
                render_result_panel(execution)

                attempts = current_result.get("attempts", 0) + 1
                time_spent_seconds = int(time.time() - interview_state["question_started_at"])

                if submit:
                    if execution["passed"]:
                        score = calculate_question_score(
                            True,
                            time_spent_seconds,
                            attempts,
                            interview_state["minutes_per_question"],
                        )
                        interview_state["results"][question_key] = {
                            "attempts": attempts,
                            "correct": True,
                            "skipped": False,
                            "time_spent_seconds": time_spent_seconds,
                            "score": score,
                        }
                        st.session_state[INTERVIEW_STATE_KEY] = interview_state
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
                    st.error("Some tests are still failing. Keep refining the answer.")

        stored_result = st.session_state.get(result_key)
        if stored_result and not (run or submit):
            render_result_panel(stored_result.get("execution", stored_result))

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
        status_col2.metric("Question Time", format_duration(question_elapsed))
        status_col3.metric("Score Earned", f"{current_result.get('score', 0)} / 100" if is_locked else "-- / 100")

        if current_result.get("correct"):
            st.success("Question completed. Move on when you are ready.")
        elif current_result.get("skipped"):
            st.info("Question skipped. You can continue or finish the interview.")
        else:
            st.caption("A fully correct submission earns the points. Extra attempts reduce only the attempts portion of the score.")

        next_label = "Finish Interview" if interview_state["current_index"] == len(interview_state["questions"]) - 1 else "Next Question"
        if st.button(next_label, key=f"next_{question_key}", disabled=not is_locked):
            if interview_state["current_index"] == len(interview_state["questions"]) - 1:
                finalize_interview("completed")
            else:
                advance_interview_question()
            st.rerun()

        if st.button("End Interview Early", key="python_finish_early"):
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


def render_python(show_sidebar_title=True):
    questions = load_questions("python")
    if not questions:
        st.error("No Python questions found.")
        return

    if show_sidebar_title:
        st.sidebar.title("Python Workspace")

    initial_workspace = get_query_param("py_workspace", WORKSPACES[0])
    if initial_workspace not in WORKSPACES:
        initial_workspace = WORKSPACES[0]

    if "python_workspace" not in st.session_state or st.session_state.python_workspace not in WORKSPACES:
        st.session_state.python_workspace = initial_workspace

    workspace = st.sidebar.radio("Workspace", WORKSPACES, key="python_workspace")
    st.query_params["py_workspace"] = workspace

    if workspace == "Practice":
        render_practice_workspace(questions)
    else:
        render_interview_workspace(questions)
