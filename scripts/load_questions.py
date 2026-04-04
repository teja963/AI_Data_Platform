import json
import os
import sys

# Ensure project root is on sys.path so `core` imports work when running this script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.db import SessionLocal
from core.models import Question

session = SessionLocal()

DATA_PATH = "data/sql"

for root, dirs, files in os.walk(DATA_PATH):
    for file in files:
        if file.endswith(".json"):
            path = os.path.join(root, file)

            with open(path) as f:
                q = json.load(f)

            question = Question(
                module="sql",
                category=q.get("category", "General"),
                difficulty=q.get("difficulty", "Medium"),
                question=q.get("question"),
                solution=q.get("solution"),
            )

            session.add(question)

session.commit()
print("✅ Questions loaded")
