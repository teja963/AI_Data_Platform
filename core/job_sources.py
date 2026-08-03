import json
import time
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SOURCE_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "data" / "job_sources.json"
HTTP_TIMEOUT_SECONDS = 25
USER_AGENT = "AI-Data-Engineering-Job-Monitor/1.0"


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


def clean_html(value):
    if not value:
        return ""
    parser = _HTMLTextExtractor()
    parser.feed(unescape(value))
    return parser.text()


def parse_datetime(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(
            timezone.utc
        ).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def load_job_sources():
    payload = json.loads(SOURCE_REGISTRY_PATH.read_text(encoding="utf-8"))
    return [source for source in payload if source.get("enabled", True)]


def source_key(source):
    return f"{source['platform']}:{source['slug']}"


def _get_json(url, retries=2):
    last_error = None
    for attempt in range(retries + 1):
        try:
            request = Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT,
                },
            )
            with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as error:
            last_error = error
            if attempt < retries:
                time.sleep(attempt + 1)
    raise last_error


def _post_json(url, payload, retries=2):
    last_error = None
    encoded = json.dumps(payload).encode("utf-8")
    for attempt in range(retries + 1):
        try:
            request = Request(
                url,
                data=encoded,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": USER_AGENT,
                },
                method="POST",
            )
            with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as error:
            last_error = error
            if attempt < retries:
                time.sleep(attempt + 1)
    raise last_error


def _greenhouse_jobs(source):
    url = (
        "https://boards-api.greenhouse.io/v1/boards/"
        f"{source['slug']}/jobs?content=true"
    )
    payload = _get_json(url)
    jobs = []
    for item in payload.get("jobs", []):
        location = (item.get("location") or {}).get("name") or ""
        jobs.append(
            {
                "external_id": str(item.get("id") or ""),
                "title": item.get("title") or "",
                "location": location,
                "work_mode": "remote" if "remote" in location.lower() else "onsite",
                "department": "",
                "description": clean_html(item.get("content")),
                "job_url": item.get("absolute_url") or "",
                "posted_at": parse_datetime(item.get("updated_at")),
                "raw_payload": item,
            }
        )
    return jobs


def _lever_jobs(source):
    url = f"https://api.lever.co/v0/postings/{source['slug']}?mode=json"
    payload = _get_json(url)
    jobs = []
    for item in payload if isinstance(payload, list) else []:
        categories = item.get("categories") or {}
        location = categories.get("location") or ""
        work_mode = item.get("workplaceType") or ""
        jobs.append(
            {
                "external_id": str(item.get("id") or ""),
                "title": item.get("text") or "",
                "location": location,
                "work_mode": work_mode,
                "department": categories.get("team") or categories.get("department") or "",
                "description": item.get("descriptionPlain") or clean_html(item.get("description")),
                "job_url": item.get("hostedUrl") or item.get("applyUrl") or "",
                "posted_at": parse_datetime(item.get("createdAt")),
                "raw_payload": item,
            }
        )
    return jobs


def _ashby_jobs(source):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{source['slug']}"
    payload = _get_json(url)
    jobs = []
    for item in payload.get("jobs", []):
        location = item.get("location") or ""
        secondary = [
            value.get("location") if isinstance(value, dict) else str(value)
            for value in item.get("secondaryLocations", [])
        ]
        all_locations = [location, *secondary]
        location_text = " | ".join(value for value in all_locations if value)
        external_id = item.get("id") or (item.get("jobUrl") or "").rstrip("/").split("/")[-1]
        jobs.append(
            {
                "external_id": str(external_id or ""),
                "title": item.get("title") or "",
                "location": location_text,
                "work_mode": item.get("workplaceType") or "",
                "department": item.get("department") or item.get("team") or "",
                "description": item.get("descriptionPlain")
                or clean_html(item.get("descriptionHtml")),
                "job_url": item.get("jobUrl") or item.get("applyUrl") or "",
                "posted_at": parse_datetime(item.get("publishedAt")),
                "raw_payload": item,
            }
        )
    return jobs


def _smartrecruiters_jobs(source):
    jobs = []
    offset = 0
    while True:
        params = urlencode({"limit": 100, "offset": offset})
        url = (
            "https://api.smartrecruiters.com/v1/companies/"
            f"{source['slug']}/postings?{params}"
        )
        payload = _get_json(url)
        content = payload.get("content", [])
        for item in content:
            location_data = item.get("location") or {}
            location = ", ".join(
                value
                for value in (
                    location_data.get("city"),
                    location_data.get("region"),
                    location_data.get("country"),
                )
                if value
            )
            remote = location_data.get("remote")
            jobs.append(
                {
                    "external_id": str(item.get("id") or item.get("uuid") or ""),
                    "title": item.get("name") or "",
                    "location": location or ("Remote" if remote else ""),
                    "work_mode": "remote" if remote else "onsite",
                    "department": (item.get("department") or {}).get("label") or "",
                    "description": "",
                    "job_url": item.get("ref") or "",
                    "posted_at": parse_datetime(item.get("releasedDate")),
                    "raw_payload": item,
                }
            )
        offset += len(content)
        if not content or offset >= int(payload.get("totalFound") or 0):
            break
    return jobs


def _workday_jobs(source):
    host = source["host"]
    tenant = source["tenant"]
    site = source["site"]
    api_base = f"https://{host}/wday/cxs/{tenant}/{site}"
    public_base = f"https://{host}/en-US/{site}"
    queries = source.get("queries") or ["data engineer", "AI data", "data platform"]
    jobs_by_path = {}
    for query in queries:
        offset = 0
        while offset < 100:
            payload = _post_json(
                f"{api_base}/jobs",
                {
                    "appliedFacets": {},
                    "limit": 20,
                    "offset": offset,
                    "searchText": query,
                },
            )
            postings = payload.get("jobPostings") or []
            for item in postings:
                external_path = item.get("externalPath") or ""
                if not external_path:
                    continue
                jobs_by_path[external_path] = {
                    "external_id": external_path.rstrip("/").split("/")[-1],
                    "title": item.get("title") or "",
                    "location": item.get("locationsText") or "",
                    "work_mode": (
                        "remote"
                        if "remote" in (item.get("locationsText") or "").lower()
                        else "onsite"
                    ),
                    "department": "",
                    "description": "",
                    "job_url": f"{public_base}{external_path}",
                    "posted_at": None,
                    "raw_payload": item,
                }
            offset += len(postings)
            if not postings or offset >= int(payload.get("total") or 0):
                break
    return list(jobs_by_path.values())


def _amazon_jobs(source):
    jobs_by_id = {}
    queries = source.get("queries") or ["data engineer", "AI platform engineer"]
    for query in queries:
        offset = 0
        while offset < 100:
            params = urlencode(
                {
                    "base_query": query,
                    "loc_query": "",
                    "offset": offset,
                    "result_limit": 50,
                }
            )
            payload = _get_json(f"https://www.amazon.jobs/en/search.json?{params}")
            postings = payload.get("jobs") or []
            for item in postings:
                external_id = str(item.get("id_icims") or item.get("id") or "")
                if not external_id:
                    continue
                location = item.get("location") or item.get("normalized_location") or ""
                job_path = item.get("job_path") or ""
                jobs_by_id[external_id] = {
                    "external_id": external_id,
                    "title": item.get("title") or "",
                    "location": location,
                    "work_mode": (
                        "remote" if "remote" in location.lower() else "onsite"
                    ),
                    "department": item.get("business_category") or "",
                    "description": clean_html(
                        item.get("description") or item.get("description_short")
                    ),
                    "job_url": (
                        f"https://www.amazon.jobs{job_path}"
                        if job_path.startswith("/")
                        else item.get("url_next_step") or job_path
                    ),
                    "posted_at": parse_datetime(item.get("posted_date")),
                    "raw_payload": item,
                }
            offset += len(postings)
            if not postings or offset >= int(payload.get("hits") or 0):
                break
    return list(jobs_by_id.values())


def collect_source_jobs(source):
    platform = source["platform"]
    collectors = {
        "greenhouse": _greenhouse_jobs,
        "lever": _lever_jobs,
        "ashby": _ashby_jobs,
        "smartrecruiters": _smartrecruiters_jobs,
        "workday": _workday_jobs,
        "amazon": _amazon_jobs,
    }
    if platform not in collectors:
        raise ValueError(f"Unsupported job source platform: {platform}")

    normalized = []
    for item in collectors[platform](source):
        if not item["external_id"] or not item["title"] or not item["job_url"]:
            continue
        item.update(
            {
                "source": source_key(source),
                "company": source["company"],
            }
        )
        normalized.append(item)
    return normalized
