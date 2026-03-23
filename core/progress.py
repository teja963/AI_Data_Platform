import json
import os

PROGRESS_FILE = "data/progress.json"


def _normalize_progress_data(data):
    tracks = data.get("tracks", {})

    if not isinstance(tracks, dict):
        tracks = {}

    # Backward compatibility for the older single-track format.
    legacy_solved = data.get("solved", [])
    if legacy_solved and "sql" not in tracks:
        tracks["sql"] = legacy_solved

    normalized_tracks = {}
    for track, solved in tracks.items():
        normalized_tracks[track] = sorted(set(solved), key=str)

    return {
        "tracks": normalized_tracks,
        "solved": normalized_tracks.get("sql", []),
    }


def _read_progress_data():
    if not os.path.exists(PROGRESS_FILE):
        return _normalize_progress_data({})

    with open(PROGRESS_FILE, "r") as f:
        data = json.load(f)

    return _normalize_progress_data(data)


def load_progress(track="sql"):
    data = _read_progress_data()
    return set(data["tracks"].get(track, []))


def save_progress(solved_set, track="sql"):
    data = _read_progress_data()
    data["tracks"][track] = sorted(set(solved_set), key=str)
    data = _normalize_progress_data(data)

    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=4)


def clear_progress(track=None):
    data = _read_progress_data()

    if track is None:
        data = _normalize_progress_data({})
    else:
        data["tracks"].pop(track, None)
        data = _normalize_progress_data(data)

    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=4)
