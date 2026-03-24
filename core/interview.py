import json
import os
import random
from datetime import datetime

INTERVIEW_HISTORY_FILE = "data/interview_history.json"

DIFFICULTY_BY_CATEGORY = {
    "Aggregation": "Easy",
    "Date": "Easy",
    "Joins": "Easy",
    "Business": "Medium",
    "Subquery": "Medium",
    "Window": "Medium",
    "Advanced": "Hard",
    "DeepComposite": "Hard",
}


def get_question_difficulty(question):
    return DIFFICULTY_BY_CATEGORY.get(question.get("category", ""), "Medium")


def enrich_question(question):
    enriched = dict(question)
    enriched["difficulty"] = get_question_difficulty(question)
    return enriched


def filter_questions(questions, categories=None, difficulties=None):
    categories = set(categories or [])
    difficulties = set(difficulties or [])
    filtered = []

    for question in questions:
        enriched = enrich_question(question)

        if categories and enriched["category"] not in categories:
            continue

        if difficulties and enriched["difficulty"] not in difficulties:
            continue

        filtered.append(enriched)

    return filtered


def build_interview_questions(
    questions,
    question_count,
    categories=None,
    difficulties=None,
):
    filtered = filter_questions(
        questions,
        categories=categories,
        difficulties=difficulties,
    )

    if question_count > len(filtered):
        raise ValueError("Not enough questions available for the selected filters.")

    shuffled = filtered[:]
    random.shuffle(shuffled)
    return shuffled[:question_count]


def calculate_question_score(correct, time_spent_seconds, attempts, minutes_per_question):
    if not correct:
        return 0

    time_budget_seconds = max(int(minutes_per_question * 60), 1)
    if time_spent_seconds <= time_budget_seconds:
        speed_points = 20
    else:
        overtime_ratio = min(
            (time_spent_seconds - time_budget_seconds) / time_budget_seconds,
            1.0,
        )
        speed_points = round(20 * (1 - overtime_ratio))

    attempt_points = max(0, 10 - (max(attempts, 1) - 1) * 2)
    return 70 + speed_points + attempt_points


def summarize_interview(question_results):
    total_questions = len(question_results)
    correct_count = sum(1 for result in question_results if result.get("correct"))
    attempted_count = sum(1 for result in question_results if result.get("attempts", 0) > 0)
    total_score = sum(result.get("score", 0) for result in question_results)
    max_score = total_questions * 100
    score_percent = round((total_score / max_score) * 100, 1) if max_score else 0.0

    return {
        "total_questions": total_questions,
        "correct_count": correct_count,
        "attempted_count": attempted_count,
        "total_score": total_score,
        "max_score": max_score,
        "score_percent": score_percent,
    }


def load_interview_history():
    if not os.path.exists(INTERVIEW_HISTORY_FILE):
        return []

    with open(INTERVIEW_HISTORY_FILE, "r") as file_obj:
        data = json.load(file_obj)

    return data.get("runs", [])


def save_interview_history(runs):
    os.makedirs(os.path.dirname(INTERVIEW_HISTORY_FILE), exist_ok=True)

    with open(INTERVIEW_HISTORY_FILE, "w") as file_obj:
        json.dump({"runs": runs[-50:]}, file_obj, indent=2)


def append_interview_run(run_data):
    runs = load_interview_history()
    runs.append(run_data)
    save_interview_history(runs)


def build_history_entry(
    track,
    categories,
    difficulties,
    minutes_per_question,
    interview_summary,
    question_results,
):
    return {
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "track": track,
        "categories": list(categories),
        "difficulties": list(difficulties),
        "minutes_per_question": minutes_per_question,
        **interview_summary,
        "questions": question_results,
    }
