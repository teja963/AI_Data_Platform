import os
import sys
import json

# ensure project root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.db import engine, SessionLocal, Base
from core.models import Question


def load_sql_questions(session, data_root="data/sql"):
    for root, dirs, files in os.walk(data_root):
        for file in files:
            if not file.endswith('.json'):
                continue
            path = os.path.join(root, file)
            with open(path) as f:
                q = json.load(f)

            payload = json.dumps(q)
            module = 'sql'
            category = q.get('category', 'General')
            difficulty = q.get('difficulty', 'Medium')
            question_text = q.get('question') or q.get('description') or q.get('title')
            solution = q.get('sql_solution') or q.get('pyspark_solution') or ''

            existing = session.query(Question).filter_by(module=module, payload=payload).first()
            if existing:
                continue

            row = Question(module=module, category=category, difficulty=difficulty, payload=payload, question=question_text, solution=solution)
            session.add(row)


def load_python_bank(session):
    try:
        from modules.python.bank import get_python_questions
    except Exception:
        return
    import pandas as pd
    import numpy as np

    def sanitize(obj):
        # convert common non-serializable types into serializable forms
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize(v) for v in obj]
        if isinstance(obj, tuple):
            return [sanitize(v) for v in obj]
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient="records")
        if isinstance(obj, (pd.Series,)):
            return obj.to_list()
        if isinstance(obj, np.generic):
            return obj.item()
        # fallback: try JSON, else convert to string
        try:
            json.dumps(obj)
            return obj
        except Exception:
            return str(obj)

    for q in get_python_questions():
        sanitized = sanitize(q)
        payload = json.dumps(sanitized)
        module = 'python'
        category = q.get('category', 'General')
        difficulty = q.get('difficulty', 'Medium')
        question_text = q.get('question') or q.get('description') or q.get('title')
        solution = q.get('solution', '')

        existing = session.query(Question).filter_by(module=module, payload=payload).first()
        if existing:
            continue

        row = Question(module=module, category=category, difficulty=difficulty, payload=payload, question=question_text, solution=solution)
        session.add(row)


def migrate(drop_and_recreate=False):
    if drop_and_recreate:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    load_sql_questions(session)
    load_python_bank(session)
    session.commit()
    session.close()
    print('✅ Migration complete')


if __name__ == '__main__':
    migrate(drop_and_recreate=True)
