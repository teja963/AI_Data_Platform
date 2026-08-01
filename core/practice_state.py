import json
from pathlib import Path

from core.db import Base, SessionLocal, engine
from core.models import PracticeLabState, User


STATE_FILE = Path(__file__).resolve().parents[1] / "data" / "practice_lab_states.json"
_PRACTICE_SCHEMA_READY = False


def ensure_practice_state_schema():
    global _PRACTICE_SCHEMA_READY
    if _PRACTICE_SCHEMA_READY:
        return True
    try:
        Base.metadata.create_all(bind=engine, tables=[PracticeLabState.__table__])
        _PRACTICE_SCHEMA_READY = True
        return True
    except Exception:
        return False


def _read_local():
    try:
        if not STATE_FILE.exists():
            return {}
        value = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_local(value):
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = STATE_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
        temporary.replace(STATE_FILE)
        return True
    except OSError:
        return False


def _local_key(username, lab_key):
    return f"{username}::{lab_key}"


def load_practice_state(username, lab_key):
    if not username or not lab_key:
        return None
    fallback = _read_local().get(_local_key(username, lab_key))
    if not ensure_practice_state_schema():
        return fallback
    session = SessionLocal()
    try:
        row = (
            session.query(PracticeLabState)
            .filter_by(username=username, lab_key=lab_key)
            .first()
        )
        if not row:
            return fallback
        value = json.loads(row.state_json)
        return value if isinstance(value, dict) else fallback
    except Exception:
        return fallback
    finally:
        session.close()


def save_practice_state(username, lab_key, state):
    if not username or not lab_key or not isinstance(state, dict):
        return False
    local = _read_local()
    local[_local_key(username, lab_key)] = state
    local_saved = _write_local(local)
    if not ensure_practice_state_schema():
        return local_saved
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        row = (
            session.query(PracticeLabState)
            .filter_by(username=username, lab_key=lab_key)
            .first()
        )
        payload = json.dumps(state)
        if row:
            row.state_json = payload
            row.user_id = user.id if user else row.user_id
        else:
            session.add(
                PracticeLabState(
                    user_id=user.id if user else None,
                    username=username,
                    lab_key=lab_key,
                    state_json=payload,
                )
            )
        session.commit()
        return True
    except Exception:
        session.rollback()
        return local_saved
    finally:
        session.close()
