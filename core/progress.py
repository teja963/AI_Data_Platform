import json
import os
from datetime import datetime

import streamlit as st
from sqlalchemy import inspect, text

PROGRESS_FILE = "data/progress.json"


def _current_username():
    return st.session_state.get("user") or "local"


def _ensure_progress_schema():
    """Add progress columns for existing deployments without dropping data."""
    from core.db import engine

    inspector = inspect(engine)
    if "progress" not in inspector.get_table_names():
        from core.models import Base

        Base.metadata.create_all(bind=engine)
        return

    existing_columns = {column["name"] for column in inspector.get_columns("progress")}
    statements = []

    if "track" not in existing_columns:
        statements.append("ALTER TABLE progress ADD COLUMN track VARCHAR DEFAULT 'sql'")
    if "question_key" not in existing_columns:
        statements.append("ALTER TABLE progress ADD COLUMN question_key VARCHAR")
    if "updated_at" not in existing_columns:
        statements.append("ALTER TABLE progress ADD COLUMN updated_at TIMESTAMP")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        connection.execute(
            text("UPDATE progress SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
        )


def _get_current_user_id(session):
    from core.models import User

    username = st.session_state.get("user")
    if not username:
        return None

    user = session.query(User).filter_by(username=username).first()
    return user.id if user else None


def _db_available():
    return bool(st.session_state.get("user"))


def _normalize_progress_data(data):
    tracks = data.get("tracks", {})
    users = data.get("users", {})

    if not isinstance(tracks, dict):
        tracks = {}
    if not isinstance(users, dict):
        users = {}

    # Backward compatibility for the older single-track format.
    legacy_solved = data.get("solved", [])
    if legacy_solved and "sql" not in tracks:
        tracks["sql"] = legacy_solved

    normalized_tracks = {}
    for track, solved in tracks.items():
        normalized_tracks[track] = sorted(set(solved), key=str)

    normalized_users = {}
    for username, user_data in users.items():
        user_tracks = user_data.get("tracks", {}) if isinstance(user_data, dict) else {}
        normalized_users[username] = {
            "tracks": {
                track: sorted(set(solved), key=str)
                for track, solved in user_tracks.items()
            }
        }

    return {
        "tracks": normalized_tracks,
        "solved": normalized_tracks.get("sql", []),
        "users": normalized_users,
    }


def _read_progress_data():
    if not os.path.exists(PROGRESS_FILE):
        return _normalize_progress_data({})

    with open(PROGRESS_FILE, "r") as f:
        data = json.load(f)

    return _normalize_progress_data(data)


def _write_progress_data(data):
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, "w") as f:
        json.dump(_normalize_progress_data(data), f, indent=4)


def _load_local_progress(track):
    data = _read_progress_data()
    username = _current_username()
    user_tracks = data["users"].get(username, {}).get("tracks", {})

    if username == "local" and not user_tracks:
        return set(data["tracks"].get(track, []))

    return set(user_tracks.get(track, []))


def _save_local_progress(solved_set, track):
    data = _read_progress_data()
    username = _current_username()
    data["users"].setdefault(username, {"tracks": {}})
    data["users"][username]["tracks"][track] = sorted(set(solved_set), key=str)

    if username == "local":
        data["tracks"][track] = sorted(set(solved_set), key=str)

    _write_progress_data(data)


def _clear_local_progress(track=None):
    data = _read_progress_data()
    username = _current_username()

    if username == "local":
        if track is None:
            data["tracks"] = {}
        else:
            data["tracks"].pop(track, None)

    data["users"].setdefault(username, {"tracks": {}})
    if track is None:
        data["users"][username]["tracks"] = {}
    else:
        data["users"][username]["tracks"].pop(track, None)

    _write_progress_data(data)


def load_progress(track="sql"):
    if _db_available():
        try:
            from core.db import SessionLocal
            from core.models import Progress

            _ensure_progress_schema()
            session = SessionLocal()
            try:
                user_id = _get_current_user_id(session)
                if user_id is None:
                    return _load_local_progress(track)

                rows = (
                    session.query(Progress.question_key)
                    .filter_by(user_id=user_id, track=track, status="solved")
                    .all()
                )
                return {row[0] for row in rows if row[0]}
            finally:
                session.close()
        except Exception:
            return _load_local_progress(track)

    return _load_local_progress(track)


def save_progress(solved_set, track="sql"):
    solved_set = set(solved_set)

    if _db_available():
        try:
            from core.db import SessionLocal
            from core.models import Progress

            _ensure_progress_schema()
            session = SessionLocal()
            try:
                user_id = _get_current_user_id(session)
                if user_id is None:
                    _save_local_progress(solved_set, track)
                    return

                existing_rows = (
                    session.query(Progress)
                    .filter_by(user_id=user_id, track=track, status="solved")
                    .all()
                )
                existing_keys = {row.question_key for row in existing_rows if row.question_key}
                keys_to_add = sorted(solved_set - existing_keys, key=str)
                now = datetime.utcnow()
                for question_key in keys_to_add:
                    session.add(
                        Progress(
                            user_id=user_id,
                            track=track,
                            question_key=question_key,
                            status="solved",
                            attempts=1,
                            updated_at=now,
                        )
                    )
                session.commit()
                _save_local_progress(existing_keys | solved_set, track)
                return
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        except Exception:
            _save_local_progress(solved_set, track)
            return

    _save_local_progress(solved_set, track)


def clear_progress(track=None):
    if _db_available():
        try:
            from core.db import SessionLocal
            from core.models import Progress

            _ensure_progress_schema()
            session = SessionLocal()
            try:
                user_id = _get_current_user_id(session)
                if user_id is not None:
                    query = session.query(Progress).filter_by(user_id=user_id)
                    if track is not None:
                        query = query.filter_by(track=track)
                    query.delete()
                    session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        except Exception:
            pass

    _clear_local_progress(track)
