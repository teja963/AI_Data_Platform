import json
from pathlib import Path

from core.db import Base, SessionLocal, engine
from core.models import User, VirtualKubernetesLab

LAB_FILE = Path(__file__).resolve().parents[1] / "data" / "kubernetes_labs.json"


def _read_local_labs():
    try:
        if not LAB_FILE.exists():
            return {"users": {}}
        data = json.loads(LAB_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"users": {}}
        data.setdefault("users", {})
        return data
    except (OSError, json.JSONDecodeError):
        return {"users": {}}


def _write_local_labs(data):
    try:
        LAB_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = LAB_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(LAB_FILE)
        return True
    except OSError:
        return False


def _load_local_lab(username):
    state = _read_local_labs()["users"].get(username)
    return state if isinstance(state, dict) and state.get("cluster") else None


def _save_local_lab(username, state):
    data = _read_local_labs()
    data["users"][username] = state
    return _write_local_labs(data)


def _delete_local_lab(username):
    data = _read_local_labs()
    existed = data["users"].pop(username, None) is not None
    _write_local_labs(data)
    return existed


def ensure_kubernetes_lab_schema():
    try:
        Base.metadata.create_all(bind=engine, tables=[VirtualKubernetesLab.__table__])
        return True
    except Exception:
        return False


def load_kubernetes_lab(username):
    if not username:
        return None
    if not ensure_kubernetes_lab_schema():
        return _load_local_lab(username)
    session = SessionLocal()
    try:
        lab = (
            session.query(VirtualKubernetesLab)
            .filter(VirtualKubernetesLab.username == username)
            .first()
        )
        if not lab:
            return _load_local_lab(username)
        state = json.loads(lab.state_json)
        return state if isinstance(state, dict) and state.get("cluster") else None
    except Exception:
        return _load_local_lab(username)
    finally:
        session.close()


def save_kubernetes_lab(username, state):
    if not username or not state:
        return False
    local_saved = _save_local_lab(username, state)
    if not ensure_kubernetes_lab_schema():
        return local_saved
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.username == username).first()
        lab = (
            session.query(VirtualKubernetesLab)
            .filter(VirtualKubernetesLab.username == username)
            .first()
        )
        payload = json.dumps(state)
        if lab:
            lab.state_json = payload
            lab.user_id = user.id if user else lab.user_id
        else:
            lab = VirtualKubernetesLab(
                user_id=user.id if user else None,
                username=username,
                state_json=payload,
            )
            session.add(lab)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return local_saved
    finally:
        session.close()


def delete_kubernetes_lab(username):
    if not username:
        return False
    local_deleted = _delete_local_lab(username)
    if not ensure_kubernetes_lab_schema():
        return local_deleted
    session = SessionLocal()
    try:
        deleted = (
            session.query(VirtualKubernetesLab)
            .filter(VirtualKubernetesLab.username == username)
            .delete()
        )
        session.commit()
        return bool(deleted) or local_deleted
    except Exception:
        session.rollback()
        return local_deleted
    finally:
        session.close()
