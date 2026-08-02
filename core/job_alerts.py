import json
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from sqlalchemy import and_, or_

from core.db import Base, SessionLocal, engine
from core.models import JobPosting, JobScanRun, User, UserJobState


MICROSOFT_SOURCE = "microsoft_careers"
MICROSOFT_COMPANY = "Microsoft"
MICROSOFT_BASE_URL = "https://apply.careers.microsoft.com"
RETENTION_DAYS = 7
SCAN_INTERVAL_HOURS = 12

TARGET_QUERIES = (
    "AI Data Engineer",
    "Data Engineer",
    "Data Platform Engineer",
    "Big Data Engineer",
    "ETL Engineer",
    "Spark Engineer",
)

_EXCLUDED_TITLE_TERMS = (
    "architect",
    "consultant",
    "director",
    "intern",
    "manager",
    "principal",
    "sales",
    "support",
)

_TITLE_RULES = (
    (re.compile(r"\bai data engineer\b", re.I), 100, "AI Data Engineer title"),
    (re.compile(r"\bdata engineer\b", re.I), 95, "Data Engineer title"),
    (re.compile(r"\bdata (?:platform|infrastructure|research) engineer\b", re.I), 90, "Data platform title"),
    (re.compile(r"\bbig data engineer\b", re.I), 90, "Big Data Engineer title"),
    (re.compile(r"\b(?:etl|spark|analytics) engineer\b", re.I), 88, "Related data engineering title"),
    (
        re.compile(
            r"\bsoftware engineer(?:\s+(?:i{1,3}|[1-3]|senior))?[, -]+"
            r"(?:azure )?data (?:platform|intelligence|engineering)\b",
            re.I,
        ),
        82,
        "Software engineering role explicitly focused on a data platform",
    ),
)

_JOB_SCHEMA_READY = False


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        value = " ".join(data.split())
        if value:
            self.parts.append(value)

    def text(self):
        return " ".join(self.parts)


def ensure_job_schema():
    global _JOB_SCHEMA_READY
    if _JOB_SCHEMA_READY:
        return
    Base.metadata.create_all(
        bind=engine,
        tables=[
            JobPosting.__table__,
            UserJobState.__table__,
            JobScanRun.__table__,
        ],
    )
    _JOB_SCHEMA_READY = True


def _clean_html(value):
    if not value:
        return ""
    parser = _HTMLTextExtractor()
    parser.feed(unescape(value))
    return parser.text()


def _utc_from_timestamp(value):
    try:
        return datetime.fromtimestamp(int(value), timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def match_job_title(title):
    normalized_title = " ".join((title or "").split())
    lowered = normalized_title.lower()
    if any(term in lowered for term in _EXCLUDED_TITLE_TERMS):
        return None
    for pattern, score, reason in _TITLE_RULES:
        if pattern.search(normalized_title):
            return {"score": score, "reason": reason}
    return None


class MicrosoftCareersClient:
    def __init__(self, timeout=20):
        self.timeout = timeout
        self.headers = {
            "Accept": "application/json",
            "Referer": f"{MICROSOFT_BASE_URL}/careers",
            "User-Agent": "AI-Data-Engineering-Job-Monitor/1.0",
        }

    def _get_json(self, path, params):
        url = f"{MICROSOFT_BASE_URL}{path}?{urlencode(params)}"
        request = Request(url, headers=self.headers)
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("status") != 200:
            message = payload.get("error", {}).get("message") or "Microsoft Careers request failed"
            raise RuntimeError(message)
        return payload.get("data") or {}

    def search(self, query, start=0, sort_by=None):
        params = {
            "domain": "microsoft.com",
            "query": query,
            "location": "",
            "start": start,
        }
        if sort_by:
            params["sort_by"] = sort_by
        return self._get_json("/api/pcsx/search", params)

    def details(self, position_id):
        return self._get_json(
            "/api/pcsx/position_details",
            {
                "domain": "microsoft.com",
                "position_id": position_id,
            },
        )


def collect_microsoft_jobs(client=None):
    client = client or MicrosoftCareersClient()
    candidates = {}

    for query in TARGET_QUERIES:
        searches = ((0, None), (10, None), (0, "timestamp"))
        for start, sort_by in searches:
            result = client.search(query=query, start=start, sort_by=sort_by)
            for position in result.get("positions", []):
                external_id = str(position.get("id") or "")
                if external_id and match_job_title(position.get("name")):
                    candidates[external_id] = position

    collected = []
    for external_id, summary in candidates.items():
        match = match_job_title(summary.get("name"))
        if not match:
            continue
        try:
            details = client.details(external_id)
        except Exception:
            details = {}

        raw_description = details.get("jobDescription") or ""
        description = _clean_html(raw_description)
        location_values = details.get("locations") or summary.get("locations") or []
        position_url = details.get("positionUrl") or summary.get("positionUrl")
        collected.append(
            {
                "source": MICROSOFT_SOURCE,
                "external_id": external_id,
                "company": MICROSOFT_COMPANY,
                "title": details.get("name") or summary.get("name") or "Untitled role",
                "location": " | ".join(location_values),
                "work_mode": details.get("workLocationOption") or summary.get("workLocationOption"),
                "department": details.get("department") or summary.get("department"),
                "description": description,
                "job_url": urljoin(MICROSOFT_BASE_URL, position_url or f"/careers/job/{external_id}"),
                "posted_at": _utc_from_timestamp(details.get("postedTs") or summary.get("postedTs")),
                "match_score": match["score"],
                "match_reason": match["reason"],
                "raw_payload": json.dumps(summary, default=str),
            }
        )

    return collected


def _expire_old_jobs(session, now):
    cutoff = now - timedelta(days=RETENTION_DAYS)
    expired = (
        session.query(JobPosting)
        .filter(
            JobPosting.is_active.is_(True),
            JobPosting.first_seen_at < cutoff,
        )
        .all()
    )
    for job in expired:
        job.is_active = False


def run_microsoft_scan(client=None):
    ensure_job_schema()
    started_at = datetime.utcnow()
    session = SessionLocal()
    run = JobScanRun(source=MICROSOFT_SOURCE, started_at=started_at, status="running")
    session.add(run)
    session.commit()
    run_id = run.id
    session.close()

    try:
        jobs = collect_microsoft_jobs(client=client)
        session = SessionLocal()
        inserted_count = 0
        try:
            now = datetime.utcnow()
            for item in jobs:
                row = (
                    session.query(JobPosting)
                    .filter_by(source=item["source"], external_id=item["external_id"])
                    .first()
                )
                if row is None:
                    row = JobPosting(
                        **item,
                        first_seen_at=now,
                        last_seen_at=now,
                        expires_at=now + timedelta(days=RETENTION_DAYS),
                        is_active=True,
                    )
                    session.add(row)
                    inserted_count += 1
                else:
                    for field, value in item.items():
                        setattr(row, field, value)
                    row.last_seen_at = now
                    row.is_active = True

            _expire_old_jobs(session, now)
            run = session.query(JobScanRun).filter_by(id=run_id).first()
            run.finished_at = now
            run.status = "success"
            run.discovered_count = len(jobs)
            run.matched_count = len(jobs)
            run.inserted_count = inserted_count
            session.commit()
            return {
                "status": "success",
                "discovered_count": len(jobs),
                "matched_count": len(jobs),
                "inserted_count": inserted_count,
            }
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as error:
        session = SessionLocal()
        try:
            run = session.query(JobScanRun).filter_by(id=run_id).first()
            if run:
                run.finished_at = datetime.utcnow()
                run.status = "failed"
                run.error_message = str(error)[:2000]
                session.commit()
        finally:
            session.close()
        raise


def get_latest_scan():
    ensure_job_schema()
    session = SessionLocal()
    try:
        row = (
            session.query(JobScanRun)
            .filter_by(source=MICROSOFT_SOURCE)
            .order_by(JobScanRun.started_at.desc())
            .first()
        )
        if not row:
            return None
        return {
            "status": row.status,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "matched_count": row.matched_count,
            "inserted_count": row.inserted_count,
            "error_message": row.error_message,
        }
    finally:
        session.close()


def is_scan_due():
    latest = get_latest_scan()
    if not latest or latest["status"] != "success":
        return True
    completed_at = latest["finished_at"] or latest["started_at"]
    return completed_at < datetime.utcnow() - timedelta(hours=SCAN_INTERVAL_HOURS)


def claim_new_job_notifications(username, limit=8):
    ensure_job_schema()
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            return []
        cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
        rows = (
            session.query(JobPosting)
            .outerjoin(
                UserJobState,
                and_(UserJobState.job_id == JobPosting.id, UserJobState.user_id == user.id),
            )
            .filter(
                JobPosting.is_active.is_(True),
                JobPosting.first_seen_at >= cutoff,
                UserJobState.id.is_(None),
            )
            .order_by(JobPosting.first_seen_at.desc())
            .limit(limit)
            .all()
        )
        now = datetime.utcnow()
        for job in rows:
            session.add(
                UserJobState(
                    user_id=user.id,
                    job_id=job.id,
                    status="new",
                    first_notified_at=now,
                    last_viewed_at=now,
                )
            )
        session.commit()
        return [
            {
                "id": job.id,
                "company": job.company,
                "title": job.title,
                "job_url": job.job_url,
            }
            for job in rows
        ]
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def list_jobs_for_user(username, status_filter="Active"):
    ensure_job_schema()
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            return []
        query = (
            session.query(JobPosting, UserJobState)
            .outerjoin(
                UserJobState,
                and_(UserJobState.job_id == JobPosting.id, UserJobState.user_id == user.id),
            )
        )
        if status_filter == "Active":
            query = query.filter(JobPosting.is_active.is_(True))
        elif status_filter != "All":
            normalized_status = status_filter.lower().replace(" ", "_")
            query = query.filter(UserJobState.status == normalized_status)
            if normalized_status not in {"saved", "applied"}:
                query = query.filter(JobPosting.is_active.is_(True))
        else:
            query = query.filter(
                or_(
                    JobPosting.is_active.is_(True),
                    UserJobState.status.in_(("saved", "applied")),
                )
            )

        rows = query.order_by(JobPosting.posted_at.desc(), JobPosting.first_seen_at.desc()).all()
        return [
            {
                "id": job.id,
                "company": job.company,
                "title": job.title,
                "location": job.location or "Location not listed",
                "work_mode": job.work_mode or "Not specified",
                "department": job.department or "Not specified",
                "description": job.description or "",
                "job_url": job.job_url,
                "posted_at": job.posted_at,
                "first_seen_at": job.first_seen_at,
                "expires_at": job.expires_at,
                "match_score": job.match_score,
                "match_reason": job.match_reason or "",
                "status": state.status if state else "new",
            }
            for job, state in rows
        ]
    finally:
        session.close()


def update_job_status(username, job_id, status):
    allowed_statuses = {"new", "saved", "applied", "rejected", "not_relevant"}
    if status not in allowed_statuses:
        raise ValueError("Unsupported job status")
    ensure_job_schema()
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        job = session.query(JobPosting).filter_by(id=job_id).first()
        if not user or not job:
            return False
        state = session.query(UserJobState).filter_by(user_id=user.id, job_id=job.id).first()
        if state is None:
            state = UserJobState(user_id=user.id, job_id=job.id)
            session.add(state)
        state.status = status
        state.last_viewed_at = datetime.utcnow()
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
