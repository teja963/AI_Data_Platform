import json
import os


def _format_category_name(category_name):
    return category_name.replace("_", " ").replace("-", " ").title()


def _normalize_category_key(category_name):
    return category_name.strip().lower().replace(" ", "_")


def build_question_key(module, question):
    category = question.get("category", "Others")
    return f"{module}:{_normalize_category_key(category)}:{question.get('id')}"


def _load_question_file(file_path, module, category=None):
    with open(file_path) as f:
        question = json.load(f)

    if category:
        question["category"] = question.get("category", category)
    else:
        question["category"] = question.get("category", "Others")

    question["progress_key"] = build_question_key(module, question)
    return question


def load_questions(module):
    nested_path = os.path.join("data", module)
    legacy_path = os.path.join("data", f"{module}_questions")

    if os.path.isdir(nested_path):
        questions = []

        for root, dirs, files in os.walk(nested_path):
            dirs.sort()

            for file_name in sorted(files):
                if not file_name.endswith(".json"):
                    continue

                file_path = os.path.join(root, file_name)
                relative_dir = os.path.relpath(root, nested_path)
                category = None

                if relative_dir != ".":
                    category = _format_category_name(os.path.basename(relative_dir))

                questions.append(_load_question_file(file_path, module, category))

        return questions

    if not os.path.isdir(legacy_path):
        return []

    questions = []

    for file_name in sorted(os.listdir(legacy_path)):
        if file_name.endswith(".json"):
            file_path = os.path.join(legacy_path, file_name)
            questions.append(_load_question_file(file_path, module))

    return questions


def group_by_category(questions):
    grouped = {}

    def sort_key(question):
        question_id = question.get("id", 0)

        try:
            question_id = int(question_id)
        except (TypeError, ValueError):
            pass

        return (question.get("category", "Others"), question_id, question.get("title", ""))

    for q in sorted(questions, key=sort_key):
        category = q.get("category", "Others")

        if category not in grouped:
            grouped[category] = []

        grouped[category].append(q)

    return grouped
