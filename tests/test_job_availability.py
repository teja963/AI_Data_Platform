from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.job_alerts as job_alerts
from core.models import JobPosting, JobScanRun, User, UserJobState


def _job(external_id, last_seen_at, title="Data Engineer"):
    return JobPosting(
        source="greenhouse:example",
        external_id=external_id,
        company="Example",
        title=title,
        location="Bengaluru, India",
        work_mode="onsite",
        description="Build data pipelines.",
        job_url=f"https://example.com/{external_id}",
        first_seen_at=last_seen_at,
        last_seen_at=last_seen_at,
        is_active=True,
        match_score=100,
    )


def test_expiry_uses_last_seen_instead_of_first_seen():
    engine = create_engine("sqlite:///:memory:")
    JobPosting.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    now = datetime.utcnow()
    session = factory()
    old_but_verified = _job("verified", now - timedelta(days=1))
    old_but_verified.first_seen_at = now - timedelta(days=30)
    stale = _job("stale", now - timedelta(days=10))
    session.add_all([old_but_verified, stale])
    session.commit()

    job_alerts._expire_old_jobs(session, now)
    session.commit()

    assert session.query(JobPosting).filter_by(external_id="verified").one().is_active
    assert not session.query(JobPosting).filter_by(external_id="stale").one().is_active
    session.close()


def test_successful_source_scan_deactivates_only_missing_posts(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    JobPosting.__table__.create(engine)
    JobScanRun.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    old = datetime.utcnow() - timedelta(days=1)
    session.add_all([_job("present", old), _job("removed", old)])
    session.commit()
    session.close()

    monkeypatch.setattr(job_alerts, "SessionLocal", factory)
    monkeypatch.setattr(job_alerts, "ensure_job_schema", lambda: None)
    current = {
        "source": "greenhouse:example",
        "external_id": "present",
        "company": "Example",
        "title": "Data Engineer",
        "location": "Bengaluru, India",
        "work_mode": "onsite",
        "department": "Data",
        "description": "Build current data pipelines.",
        "job_url": "https://example.com/present",
        "posted_at": datetime.utcnow(),
        "match_score": 100,
        "match_reason": "data engineer",
        "raw_payload": "{}",
    }

    job_alerts._run_source_scan("greenhouse:example", lambda: [current])

    session = factory()
    try:
        assert session.query(JobPosting).filter_by(external_id="present").one().is_active
        assert not session.query(JobPosting).filter_by(external_id="removed").one().is_active
    finally:
        session.close()


def test_jobs_are_ordered_by_posting_time_with_discovery_fallback(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    for table in (User.__table__, JobPosting.__table__, UserJobState.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.utcnow()
    session = factory()
    session.add(User(username="reader", password="unused"))
    older = _job("older", now)
    older.posted_at = now - timedelta(days=2)
    newer = _job("newer", now - timedelta(days=3))
    newer.posted_at = now - timedelta(hours=1)
    discovered = _job("discovered", now - timedelta(days=1))
    discovered.posted_at = None
    session.add_all([older, newer, discovered])
    session.commit()
    session.close()

    monkeypatch.setattr(job_alerts, "SessionLocal", factory)
    monkeypatch.setattr(job_alerts, "ensure_job_schema", lambda: None)

    jobs = job_alerts.list_jobs_for_user("reader")

    assert [job["job_url"].rsplit("/", 1)[-1] for job in jobs] == [
        "newer",
        "discovered",
        "older",
    ]
