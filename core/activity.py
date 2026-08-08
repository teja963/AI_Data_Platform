from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import streamlit as st
from sqlalchemy import inspect
from streamlit.runtime.scriptrunner import get_script_run_ctx


MAX_TRACKED_SECONDS = 300
MIN_WRITE_SECONDS = 10
FLUSH_INTERVAL_SECONDS = 300
_ACTIVITY_SCHEMA_READY = False


@st.cache_resource
def _activity_executor():
    return ThreadPoolExecutor(max_workers=1, thread_name_prefix="activity-writer")


def ensure_activity_schema():
    global _ACTIVITY_SCHEMA_READY
    if _ACTIVITY_SCHEMA_READY:
        return

    from core.db import engine
    from core.models import Base

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    required_tables = {
        "user_activity_summary",
        "user_activity_daily",
        "section_performance_daily",
        "query_performance_daily",
    }
    if not required_tables.issubset(tables):
        Base.metadata.create_all(bind=engine)
    from core.section_migrations import migrate_activity_section_labels

    migrate_activity_section_labels()
    _ACTIVITY_SCHEMA_READY = True


def _get_user_id(session, username):
    from core.models import User

    cache_key = f"database_user_id::{username}"
    has_streamlit_context = get_script_run_ctx(suppress_warning=True) is not None
    if has_streamlit_context and cache_key in st.session_state:
        return st.session_state[cache_key]
    user = session.query(User).filter_by(username=username).first()
    user_id = user.id if user else None
    if has_streamlit_context and user_id is not None:
        st.session_state[cache_key] = user_id
    return user_id


def _add_activity_seconds(username, section, elapsed_seconds, count_visit=False):
    if not username or not section or (elapsed_seconds <= 0 and not count_visit):
        return

    try:
        from core.db import SessionLocal
        from core.models import UserActivityDaily, UserActivitySummary

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

            activity_date = now.date().isoformat()
            daily = (
                session.query(UserActivityDaily)
                .filter_by(user_id=user_id, section=section, activity_date=activity_date)
                .first()
            )
            if daily is None:
                daily = UserActivityDaily(
                    user_id=user_id,
                    section=section,
                    activity_date=activity_date,
                    total_seconds=0,
                    visit_count=0,
                    last_seen=now,
                    updated_at=now,
                )
                session.add(daily)

            daily.total_seconds = int(daily.total_seconds or 0) + int(elapsed_seconds)
            daily.visit_count = int(daily.visit_count or 0) + (1 if count_visit else 0)
            daily.last_seen = now
            daily.updated_at = now
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


def _pending_performance():
    if "section_performance_pending" not in st.session_state:
        st.session_state["section_performance_pending"] = {}
    return st.session_state["section_performance_pending"]


def _pending_query_performance():
    if "query_performance_pending" not in st.session_state:
        st.session_state["query_performance_pending"] = {}
    return st.session_state["query_performance_pending"]


def _queue_activity(section, elapsed_seconds=0, visit_count=0):
    pending = _pending_activity()
    item = pending.setdefault(section, {"seconds": 0, "visits": 0})
    item["seconds"] += int(max(elapsed_seconds, 0))
    item["visits"] += int(max(visit_count, 0))


def _queue_section_performance(section, elapsed_ms):
    if not section or elapsed_ms < 0:
        return

    pending = _pending_performance()
    item = pending.setdefault(
        section,
        {"render_count": 0, "total_ms": 0, "max_ms": 0, "last_ms": 0},
    )
    elapsed_ms = int(max(elapsed_ms, 0))
    item["render_count"] += 1
    item["total_ms"] += elapsed_ms
    item["max_ms"] = max(int(item["max_ms"]), elapsed_ms)
    item["last_ms"] = elapsed_ms


def _queue_query_performance(track, elapsed_ms):
    pending = _pending_query_performance()
    item = pending.setdefault(
        track,
        {"run_count": 0, "total_ms": 0, "max_ms": 0, "last_ms": 0},
    )
    elapsed_ms = int(max(elapsed_ms, 0))
    item["run_count"] += 1
    item["total_ms"] += elapsed_ms
    item["max_ms"] = max(int(item["max_ms"]), elapsed_ms)
    item["last_ms"] = elapsed_ms


def _add_section_performance(username, section, values):
    if not username or not section or not values:
        return

    try:
        from core.db import SessionLocal
        from core.models import SectionPerformanceDaily

        ensure_activity_schema()
        session = SessionLocal()
        try:
            user_id = _get_user_id(session, username)
            if user_id is None:
                return

            now = datetime.utcnow()
            activity_date = now.date().isoformat()
            perf = (
                session.query(SectionPerformanceDaily)
                .filter_by(user_id=user_id, section=section, activity_date=activity_date)
                .first()
            )
            if perf is None:
                perf = SectionPerformanceDaily(
                    user_id=user_id,
                    section=section,
                    activity_date=activity_date,
                    render_count=0,
                    total_ms=0,
                    max_ms=0,
                    last_ms=0,
                    last_seen=now,
                    updated_at=now,
                )
                session.add(perf)

            perf.render_count = int(perf.render_count or 0) + int(values.get("render_count", 0))
            perf.total_ms = int(perf.total_ms or 0) + int(values.get("total_ms", 0))
            perf.max_ms = max(int(perf.max_ms or 0), int(values.get("max_ms", 0)))
            perf.last_ms = int(values.get("last_ms", 0))
            perf.last_seen = now
            perf.updated_at = now
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
    except Exception:
        return


def _write_activity_payload(username, pending, pending_perf, pending_queries):
    for section, values in pending.items():
        seconds = int(values.get("seconds", 0))
        visits = int(values.get("visits", 0))
        if seconds > 0:
            _add_activity_seconds(username, section, seconds)
        for _ in range(visits):
            _add_activity_seconds(username, section, 0, count_visit=True)

    for section, values in pending_perf.items():
        _add_section_performance(username, section, values)

    for track, values in pending_queries.items():
        _add_query_performance(username, track, values)


def _flush_pending_activity(username, background=False):
    pending = st.session_state.get("activity_pending", {})
    pending_perf = st.session_state.get("section_performance_pending", {})
    pending_queries = st.session_state.get("query_performance_pending", {})
    if not pending and not pending_perf and not pending_queries:
        return

    st.session_state["activity_pending"] = {}
    st.session_state["section_performance_pending"] = {}
    st.session_state["query_performance_pending"] = {}
    st.session_state["activity_last_flush_ts"] = datetime.utcnow()
    payload = (
        dict(pending),
        dict(pending_perf),
        dict(pending_queries),
    )
    if background:
        _activity_executor().submit(_write_activity_payload, username, *payload)
    else:
        _write_activity_payload(username, *payload)


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
        _flush_pending_activity(username, background=True)


def track_section_render(username, section, elapsed_ms):
    _queue_section_performance(section, elapsed_ms)
    now = datetime.utcnow()
    last_flush_ts = st.session_state.get("activity_last_flush_ts")
    should_flush = (
        last_flush_ts is None
        or int((now - last_flush_ts).total_seconds()) >= FLUSH_INTERVAL_SECONDS
    )
    if should_flush:
        _flush_pending_activity(username, background=True)


def _add_query_performance(username, track, values):
    if not username or not track or not values:
        return

    try:
        from core.db import SessionLocal
        from core.models import QueryPerformanceDaily

        ensure_activity_schema()
        session = SessionLocal()
        try:
            user_id = _get_user_id(session, username)
            if user_id is None:
                return

            now = datetime.utcnow()
            activity_date = now.date().isoformat()
            perf = (
                session.query(QueryPerformanceDaily)
                .filter_by(user_id=user_id, track=track, activity_date=activity_date)
                .first()
            )
            if perf is None:
                perf = QueryPerformanceDaily(
                    user_id=user_id,
                    track=track,
                    activity_date=activity_date,
                    run_count=0,
                    total_ms=0,
                    max_ms=0,
                    last_ms=0,
                    last_seen=now,
                    updated_at=now,
                )
                session.add(perf)

            perf.run_count = int(perf.run_count or 0) + int(values.get("run_count", 0))
            perf.total_ms = int(perf.total_ms or 0) + int(values.get("total_ms", 0))
            perf.max_ms = max(int(perf.max_ms or 0), int(values.get("max_ms", 0)))
            perf.last_ms = int(values.get("last_ms", 0))
            perf.last_seen = now
            perf.updated_at = now
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
    except Exception:
        return


def track_query_execution(username, track, elapsed_ms):
    if not username or not track or elapsed_ms < 0:
        return
    _queue_query_performance(track, elapsed_ms)


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
