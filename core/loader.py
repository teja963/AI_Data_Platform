import json
import os

import streamlit as st
from sqlalchemy import text

from core.runtime import get_app_version


def _format_category_name(category_name):
    return category_name.replace("_", " ").replace("-", " ").title()


def _normalize_category_key(category_name):
    return category_name.strip().lower().replace(" ", "_")


def build_question_key(module, question):
    category = question.get("category", "Others")
    return f"{module}:{_normalize_category_key(category)}:{question.get('id')}"


def _decode_static_value(value):
    if isinstance(value, list):
        return [_decode_static_value(item) for item in value]
    if not isinstance(value, dict):
        return value

    value_type = value.get("__python_type__")
    if value_type == "tuple":
        return tuple(_decode_static_value(item) for item in value["items"])
    if value_type == "dataframe":
        import pandas as pd

        return pd.DataFrame(value["data"], columns=value["columns"])
    return {key: _decode_static_value(item) for key, item in value.items()}


def _load_question_file(file_path, module, category=None):
    with open(file_path) as f:
        payload = _decode_static_value(json.load(f))

    questions = payload if isinstance(payload, list) else [payload]
    normalized_questions = []
    for question in questions:
        normalized = dict(question)
        if category:
            normalized["category"] = normalized.get("category", category)
        else:
            normalized["category"] = normalized.get("category", "Others")

        normalized["progress_key"] = build_question_key(module, normalized)
        normalized_questions.append(normalized)
    return normalized_questions


def _load_local_questions(module):
    nested_path = os.path.join("data", module)
    legacy_path = os.path.join("data", f"{module}_questions")
    questions = []
    if os.path.isdir(nested_path):
        for root, dirs, files in os.walk(nested_path):
            dirs.sort()
            for file_name in sorted(files):
                if not file_name.endswith(".json"):
                    continue
                file_path = os.path.join(root, file_name)
                relative_dir = os.path.relpath(root, nested_path)
                category = (
                    _format_category_name(os.path.basename(relative_dir))
                    if relative_dir != "."
                    else None
                )
                questions.extend(_load_question_file(file_path, module, category))
        return questions
    if os.path.isdir(legacy_path):
        for file_name in sorted(os.listdir(legacy_path)):
            if file_name.endswith(".json"):
                questions.extend(
                    _load_question_file(
                        os.path.join(legacy_path, file_name),
                        module,
                    )
                )
        return questions
    return []


def load_questions(module):
    return _load_questions_cached(module, get_app_version())


@st.cache_data(ttl=86400, show_spinner=False)
def _load_questions_cached(module, app_version):
    # Static question catalogs are local-first so normal coding navigation never waits on PostgreSQL.
    local_questions = _load_local_questions(module)
    if local_questions:
        return local_questions
    # PostgreSQL remains a fallback for deployments whose question catalog is DB-only.
    session = None
    if module != "python":
        try:
            from core.db import SessionLocal
            from core.models import Question
            from core.views import ensure_reporting_views

            ensure_reporting_views()
            session = SessionLocal()
            try:
                db_rows = session.execute(
                    text(
                        """
                        SELECT id, category, difficulty, payload
                        FROM coding_question_catalog_view
                        WHERE module = :module
                        ORDER BY category, id
                        """
                    ),
                    {"module": module},
                ).fetchall()
            except Exception:
                db_rows = []

            if not db_rows:
                db_rows = session.query(Question).filter_by(module=module).all()

            if db_rows:
                questions = []
                for r in db_rows:
                    try:
                        payload = json.loads(getattr(r, "payload", "{}"))
                    except Exception:
                        payload = {}

                    # ensure compatibility with existing UI keys
                    payload["category"] = payload.get("category", getattr(r, "category", "Others"))
                    payload["difficulty"] = payload.get("difficulty", getattr(r, "difficulty", "Medium"))
                    payload["id"] = payload.get("id", getattr(r, "id", None))
                    payload["progress_key"] = build_question_key(module, payload)
                    questions.append(payload)

                return questions
        except Exception:
            # DB not available or error — fall back to filesystem loader
            pass
        finally:
            if session is not None:
                session.close()

    return load_question_bank(module)


def load_question_bank(module):
    if module != "python":
        return []

    from modules.python.bank import get_python_questions

    questions = []
    for question in get_python_questions():
        normalized = dict(question)
        normalized["category"] = normalized.get("category", "Others")
        normalized["progress_key"] = build_question_key(module, normalized)
        questions.append(normalized)

    return questions


@st.cache_data(show_spinner=False)
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
