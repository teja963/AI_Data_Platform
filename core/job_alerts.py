import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from sqlalchemy import and_, func, or_

from core.db import Base, SessionLocal, engine
from core.job_sources import (
    collect_source_jobs,
    load_job_sources,
    source_key,
)
from core.models import JobPosting, JobScanRun, User, UserJobState


MICROSOFT_SOURCE = "microsoft_careers"
MICROSOFT_COMPANY = "Microsoft"
MICROSOFT_BASE_URL = "https://apply.careers.microsoft.com"
RETENTION_DAYS = 7
SCAN_INTERVAL_HOURS = 12
DEFAULT_SCAN_BATCH_SIZE = 24

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
    "staff",
    "support",
    "lead",
)

_INDIA_LOCATION_TERMS = (
    "india",
    "bengaluru",
    "bangalore",
    "hyderabad",
    "pune",
    "chennai",
    "gurugram",
    "gurgaon",
    "noida",
    "mumbai",
    "new delhi",
    "delhi",
    "kolkata",
)

_GLOBAL_REMOTE_TERMS = (
    "anywhere",
    "global",
    "worldwide",
    "apac",
    "asia",
    "distributed",
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


def is_india_or_eligible_remote(location, work_mode):
    location_text = " ".join((location or "").lower().split())
    work_mode_text = " ".join((work_mode or "").lower().split())
    if any(term in location_text for term in _INDIA_LOCATION_TERMS):
        return True

    is_remote = "remote" in location_text or "remote" in work_mode_text
    if not is_remote:
        return False
    if not location_text or location_text == "remote":
        return True
    return any(term in location_text for term in _GLOBAL_REMOTE_TERMS)


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
                location = " | ".join(position.get("locations") or [])
                if (
                    external_id
                    and match_job_title(position.get("name"))
                    and is_india_or_eligible_remote(
                        location,
                        position.get("workLocationOption"),
                    )
                ):
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


def collect_registered_source_matches(source):
    matches = []
    for item in collect_source_jobs(source):
        title_match = match_job_title(item["title"])
        if not title_match:
            continue
        if not is_india_or_eligible_remote(item.get("location"), item.get("work_mode")):
            continue
        item["match_score"] = title_match["score"]
        item["match_reason"] = title_match["reason"]
        item["raw_payload"] = json.dumps(item.get("raw_payload") or {}, default=str)
        matches.append(item)
    return matches


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


def _deactivate_ineligible_jobs(session):
    active_jobs = session.query(JobPosting).filter(JobPosting.is_active.is_(True)).all()
    for job in active_jobs:
        if (
            not match_job_title(job.title)
            or not is_india_or_eligible_remote(job.location, job.work_mode)
        ):
            job.is_active = False


def _run_source_scan(scan_source, collector):
    ensure_job_schema()
    started_at = datetime.utcnow()
    session = SessionLocal()
    run = JobScanRun(source=scan_source, started_at=started_at, status="running")
    session.add(run)
    session.commit()
    run_id = run.id
    session.close()

    try:
        jobs = collector()
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


def run_microsoft_scan(client=None):
    return _run_source_scan(
        MICROSOFT_SOURCE,
        lambda: collect_microsoft_jobs(client=client),
    )


def run_registered_source_scan(source):
    return _run_source_scan(
        source_key(source),
        lambda: collect_registered_source_matches(source),
    )


def _all_scan_targets():
    sources = load_job_sources()
    return [
        (MICROSOFT_SOURCE, lambda: run_microsoft_scan()),
        *[
            (source_key(source), lambda source=source: run_registered_source_scan(source))
            for source in sources
        ],
    ]


def _execute_scan_targets(scan_targets):
    results = []
    failures = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(run_scan): scan_source
            for scan_source, run_scan in scan_targets
        }
        for future in as_completed(futures):
            scan_source = futures[future]
            try:
                result = future.result()
                result["source"] = scan_source
                results.append(result)
            except Exception as error:
                failures.append({"source": scan_source, "error": str(error)})

    if not results:
        if not failures:
            return {
                "status": "not_due",
                "source_count": 0,
                "successful_sources": 0,
                "failed_sources": 0,
                "matched_count": 0,
                "inserted_count": 0,
                "failures": [],
            }
        failure_summary = "; ".join(
            f"{failure['source']}: {failure['error']}" for failure in failures[:5]
        )
        raise RuntimeError(f"All career-site scans failed. {failure_summary}")

    session = SessionLocal()
    try:
        _expire_old_jobs(session, datetime.utcnow())
        _deactivate_ineligible_jobs(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return {
        "status": "success" if not failures else "partial",
        "source_count": len(scan_targets),
        "successful_sources": len(results),
        "failed_sources": len(failures),
        "matched_count": sum(result["matched_count"] for result in results),
        "inserted_count": sum(result["inserted_count"] for result in results),
        "failures": failures,
    }


def run_all_company_scans():
    return _execute_scan_targets(_all_scan_targets())


def run_due_company_scans(batch_size=DEFAULT_SCAN_BATCH_SIZE):
    ensure_job_schema()
    cutoff = datetime.utcnow() - timedelta(hours=SCAN_INTERVAL_HOURS)
    scan_targets = _all_scan_targets()
    source_order = {source: index for index, (source, _) in enumerate(scan_targets)}
    session = SessionLocal()
    try:
        rows = (
            session.query(JobScanRun)
            .filter(JobScanRun.source.in_(source_order))
            .order_by(JobScanRun.started_at.desc())
            .all()
        )
        latest_by_source = {}
        for row in rows:
            latest_by_source.setdefault(row.source, row)
    finally:
        session.close()

    due_targets = []
    for source, run_scan in scan_targets:
        latest = latest_by_source.get(source)
        completed_at = (latest.finished_at or latest.started_at) if latest else None
        if latest is None or latest.status != "success" or completed_at < cutoff:
            due_targets.append((source, run_scan, completed_at))

    due_targets.sort(
        key=lambda item: (
            item[2] is not None,
            item[2] or datetime.min,
            source_order[item[0]],
        )
    )
    selected = [(source, run_scan) for source, run_scan, _ in due_targets[:batch_size]]
    result = _execute_scan_targets(selected)
    result["due_source_count"] = len(due_targets)
    result["remaining_due_sources"] = max(len(due_targets) - len(selected), 0)
    return result


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


def get_scan_overview():
    ensure_job_schema()
    expected_sources = [
        MICROSOFT_SOURCE,
        *[source_key(source) for source in load_job_sources()],
    ]
    session = SessionLocal()
    try:
        rows = (
            session.query(JobScanRun)
            .filter(JobScanRun.source.in_(expected_sources))
            .order_by(JobScanRun.started_at.desc())
            .all()
        )
        latest_by_source = {}
        for row in rows:
            latest_by_source.setdefault(row.source, row)

        successful = [
            row for row in latest_by_source.values() if row.status == "success"
        ]
        failed = [row for row in latest_by_source.values() if row.status == "failed"]
        last_completed_at = max(
            (
                row.finished_at or row.started_at
                for row in latest_by_source.values()
            ),
            default=None,
        )
        active_companies = (
            session.query(JobPosting.company)
            .filter(JobPosting.is_active.is_(True))
            .distinct()
            .count()
        )
        active_jobs = (
            session.query(JobPosting)
            .filter(JobPosting.is_active.is_(True))
            .count()
        )
        return {
            "configured_sources": len(expected_sources),
            "successful_sources": len(successful),
            "failed_sources": len(failed),
            "not_scanned_sources": len(expected_sources) - len(latest_by_source),
            "last_completed_at": last_completed_at,
            "active_companies": active_companies,
            "active_jobs": active_jobs,
            "recent_failures": [
                {
                    "source": row.source,
                    "error": row.error_message or "Unknown error",
                }
                for row in failed[:10]
            ],
        }
    finally:
        session.close()


def list_source_refresh_status():
    ensure_job_schema()
    registered_sources = load_job_sources()
    source_metadata = {
        MICROSOFT_SOURCE: {
            "company": MICROSOFT_COMPANY,
            "platform": "eightfold",
            "category": "product",
        },
        **{
            source_key(source): {
                "company": source["company"],
                "platform": source["platform"],
                "category": source.get("category", "product"),
            }
            for source in registered_sources
        },
    }
    session = SessionLocal()
    try:
        runs = (
            session.query(JobScanRun)
            .filter(JobScanRun.source.in_(source_metadata))
            .order_by(JobScanRun.started_at.desc())
            .all()
        )
        latest_by_source = {}
        for run in runs:
            latest_by_source.setdefault(run.source, run)

        active_counts = dict(
            session.query(JobPosting.source, func.count(JobPosting.id))
            .filter(JobPosting.is_active.is_(True))
            .group_by(JobPosting.source)
            .all()
        )

        rows = []
        for scan_source, metadata in source_metadata.items():
            latest = latest_by_source.get(scan_source)
            refreshed_at = (latest.finished_at or latest.started_at) if latest else None
            rows.append(
                {
                    "company": metadata["company"],
                    "platform": metadata["platform"],
                    "category": metadata["category"],
                    "source": scan_source,
                    "status": latest.status if latest else "not_scanned",
                    "refreshed_at": refreshed_at,
                    "next_refresh_at": (
                        refreshed_at + timedelta(hours=SCAN_INTERVAL_HOURS)
                        if refreshed_at
                        else None
                    ),
                    "active_jobs": active_counts.get(scan_source, 0),
                    "error": latest.error_message if latest else None,
                }
            )
        return sorted(
            rows,
            key=lambda row: (
                row["refreshed_at"] is not None,
                row["refreshed_at"] or datetime.min,
                row["company"].lower(),
            ),
        )
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
                "source": job.source,
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
                "source": job.source,
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
