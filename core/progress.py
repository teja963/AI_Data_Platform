import json
import os

PROGRESS_FILE = "data/progress.json"

def load_progress():
    if not os.path.exists(PROGRESS_FILE):
        return set()

    try:
        with open(PROGRESS_FILE, "r") as f:
            data = json.load(f)
            return set(data.get("solved", []))
    except:
        return set()

def save_progress(solved_set):
    os.makedirs("data", exist_ok=True)

    with open(PROGRESS_FILE, "w") as f:
        json.dump({"solved": list(solved_set)}, f)