import json
import os

def load_questions(module):
    path = f"data/{module}_questions"

    if not os.path.exists(path):
        return []

    questions = []

    for file in sorted(os.listdir(path)):
        if file.endswith(".json"):
            with open(os.path.join(path, file)) as f:
                questions.append(json.load(f))

    return questions


def group_by_category(questions):
    grouped = {}

    for q in questions:
        category = q.get("category", "Others")

        if category not in grouped:
            grouped[category] = []

        grouped[category].append(q)

    return grouped