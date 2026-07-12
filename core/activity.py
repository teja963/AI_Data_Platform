from datetime import datetime

import streamlit as st
from sqlalchemy import inspect


MAX_TRACKED_SECONDS = 300
MIN_WRITE_SECONDS = 10
FLUSH_INTERVAL_SECONDS = 60


def ensure_activity_schema():
    from core.db import engine
    from core.models import Base

    inspector = inspect(engine)
    if "user_activity_summary" not in inspector.get_table_names():
        Base.metadata.create_all(bind=engine)


def _get_user_id(session, username):
    from core.models import User

    user = session.query(User).filter_by(username=username).first()
    return user.id if user else None


def _add_activity_seconds(username, section, elapsed_seconds, count_visit=False):
    if not username or not section or (elapsed_seconds <= 0 and not count_visit):
        return

    try:
        from core.db import SessionLocal
        from core.models import UserActivitySummary

        ensure_activity_schema()
        session = SessionLocal()
        try:
            user_id = _get_user_id(session, username)
            if user_id is None:
                return

            now = datetime.utcnow()
            summary = (
                session.query(UserActivitySummary)
                .filter_by(user_id=user_id, section=section)
                .first()
            )
            if summary is None:
                summary = UserActivitySummary(
                    user_id=user_id,
                    section=section,
                    total_seconds=0,
                    visit_count=0,
                    last_seen=now,
                    updated_at=now,
                )
                session.add(summary)

            summary.total_seconds = int(summary.total_seconds or 0) + int(elapsed_seconds)
            summary.visit_count = int(summary.visit_count or 0) + (1 if count_visit else 0)
            summary.last_seen = now
            summary.updated_at = now
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
    except Exception:
        # Analytics must never block the learning app.
        return


def _pending_activity():
    if "activity_pending" not in st.session_state:
        st.session_state["activity_pending"] = {}
    return st.session_state["activity_pending"]


def _queue_activity(section, elapsed_seconds=0, visit_count=0):
    pending = _pending_activity()
    item = pending.setdefault(section, {"seconds": 0, "visits": 0})
    item["seconds"] += int(max(elapsed_seconds, 0))
    item["visits"] += int(max(visit_count, 0))


def _flush_pending_activity(username):
    pending = st.session_state.get("activity_pending", {})
    if not pending:
        return

    for section, values in list(pending.items()):
        seconds = int(values.get("seconds", 0))
        visits = int(values.get("visits", 0))
        if seconds > 0:
            _add_activity_seconds(username, section, seconds)
        for _ in range(visits):
            _add_activity_seconds(username, section, 0, count_visit=True)

    st.session_state["activity_pending"] = {}
    st.session_state["activity_last_flush_ts"] = datetime.utcnow()


def track_section_activity(username, section):
    now = datetime.utcnow()
    last_section = st.session_state.get("activity_last_section")
    last_ts = st.session_state.get("activity_last_ts")
    last_flush_ts = st.session_state.get("activity_last_flush_ts")

    if last_section is None:
        st.session_state["activity_last_section"] = section
        st.session_state["activity_last_ts"] = now
        st.session_state["activity_last_flush_ts"] = now
        _queue_activity(section, visit_count=1)
        return

    elapsed = int((now - last_ts).total_seconds()) if last_ts else 0
    elapsed = min(max(elapsed, 0), MAX_TRACKED_SECONDS)
    section_changed = section != last_section

    if elapsed >= MIN_WRITE_SECONDS or section_changed:
        _queue_activity(last_section, elapsed_seconds=elapsed)
        st.session_state["activity_last_section"] = section
        st.session_state["activity_last_ts"] = now
        if section_changed:
            _queue_activity(section, visit_count=1)

    should_flush = (
        last_flush_ts is None
        or int((now - last_flush_ts).total_seconds()) >= FLUSH_INTERVAL_SECONDS
    )
    if should_flush:
        _flush_pending_activity(username)


def flush_section_activity(username):
    last_section = st.session_state.get("activity_last_section")
    last_ts = st.session_state.get("activity_last_ts")
    if not last_section or not last_ts:
        return

    elapsed = min(max(int((datetime.utcnow() - last_ts).total_seconds()), 0), MAX_TRACKED_SECONDS)
    if elapsed > 0:
        _queue_activity(last_section, elapsed_seconds=elapsed)

    _flush_pending_activity(username)

    st.session_state.pop("activity_last_section", None)
    st.session_state.pop("activity_last_ts", None)
