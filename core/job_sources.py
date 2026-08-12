import json
import re
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from functools import lru_cache
from http.cookiejar import CookieJar
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


SOURCE_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "data" / "job_sources.json"
PRIORITY_COMPANIES_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "priority_companies.json"
)
HTTP_TIMEOUT_SECONDS = 25
USER_AGENT = "AI-Data-Engineering-Job-Monitor/1.0"
REMOTE_WORK_TERMS = (
    "remote",
    "work from home",
    "work-from-home",
    "wfh",
    "home based",
    "home-based",
    "distributed",
    "work from anywhere",
    "worldwide",
)
HYBRID_WORK_TERMS = ("hybrid", "flexible workplace")


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
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError):
        pass
    for date_format in (
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y-%m-%d",
        "%d %B %Y",
        "%d %b %Y",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(text, date_format)
        except ValueError:
            continue
    return None


def parse_relative_posted_datetime(value, now=None):
    parsed = parse_datetime(value)
    if parsed is not None:
        return parsed
    text = " ".join(str(value or "").strip().lower().split())
    text = re.sub(r"^posted\s+", "", text)
    reference = now or datetime.now(timezone.utc).replace(tzinfo=None)
    if text == "today":
        return reference.replace(hour=0, minute=0, second=0, microsecond=0)
    if text == "yesterday":
        return (reference - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    match = re.fullmatch(
        r"(\d+)\+?\s+(hour|day|week|month)s?\s+ago",
        text,
    )
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    delta = {
        "hour": timedelta(hours=amount),
        "day": timedelta(days=amount),
        "week": timedelta(weeks=amount),
        "month": timedelta(days=amount * 30),
    }[unit]
    return reference - delta


def normalize_work_mode(location="", work_mode="", description="", remote_flag=None):
    text = " ".join(
        str(value or "").casefold()
        for value in (location, work_mode, description)
    )
    if remote_flag is True or any(term in text for term in REMOTE_WORK_TERMS):
        return "remote"
    if any(term in text for term in HYBRID_WORK_TERMS):
        return "hybrid"
    if any(term in text for term in ("onsite", "on-site", "in office", "in-office")):
        return "onsite"
    normalized = " ".join(str(work_mode or "").strip().lower().split())
    return normalized or "onsite"


def is_remote_work(location="", work_mode="", description=""):
    return normalize_work_mode(location, work_mode, description) == "remote"


@lru_cache(maxsize=1)
def _load_job_sources_cached():
    payload = json.loads(SOURCE_REGISTRY_PATH.read_text(encoding="utf-8"))
    return tuple(source for source in payload if source.get("enabled", True))


def load_job_sources():
    return [dict(source) for source in _load_job_sources_cached()]


def load_priority_company_names():
    payload = json.loads(PRIORITY_COMPANIES_PATH.read_text(encoding="utf-8"))
    return {company["company"].casefold() for company in payload}


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


def _get_text(url, retries=2, accept="text/html,application/xhtml+xml"):
    last_error = None
    for attempt in range(retries + 1):
        try:
            request = Request(
                url,
                headers={
                    "Accept": accept,
                    "User-Agent": USER_AGENT,
                },
            )
            with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                return response.read().decode("utf-8")
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
                "work_mode": normalize_work_mode(
                    location,
                    description=clean_html(item.get("content")),
                ),
                "department": "",
                "description": clean_html(item.get("content")),
                "job_url": item.get("absolute_url") or "",
                "posted_at": parse_datetime(
                    item.get("first_published")
                    or item.get("published_at")
                    or item.get("created_at")
                ),
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
                "work_mode": normalize_work_mode(
                    location,
                    work_mode,
                    item.get("descriptionPlain") or clean_html(item.get("description")),
                ),
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
                "work_mode": normalize_work_mode(
                    location_text,
                    item.get("workplaceType"),
                    item.get("descriptionPlain") or clean_html(item.get("descriptionHtml")),
                    remote_flag=item.get("isRemote"),
                ),
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
                    "work_mode": normalize_work_mode(
                        location,
                        remote_flag=remote,
                    ),
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
                    "posted_at": parse_relative_posted_datetime(
                        item.get("postedOn")
                    ),
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


def _oracle_hcm_jobs(source):
    domain = source["domain"]
    site_number = source["site_number"]
    site_path = source.get("site_path") or site_number
    queries = source.get("queries") or ["data engineer", "AI data", "data platform"]
    jobs_by_id = {}
    for query in queries:
        offset = 0
        while offset < 100:
            finder = (
                f"findReqs;siteNumber={site_number},keyword={quote(query)},"
                f"limit=20,offset={offset}"
            )
            url = (
                f"https://{domain}/hcmRestApi/resources/latest/"
                f"recruitingCEJobRequisitions?finder={finder}"
                "&expand=requisitionList&onlyData=true"
            )
            payload = _get_json(url)
            search = (payload.get("items") or [{}])[0]
            postings = search.get("requisitionList") or []
            for item in postings:
                external_id = str(item.get("Id") or "")
                if not external_id:
                    continue
                location = item.get("PrimaryLocation") or ""
                workplace = item.get("WorkplaceType") or ""
                jobs_by_id[external_id] = {
                    "external_id": external_id,
                    "title": item.get("Title") or "",
                    "location": location,
                    "work_mode": (
                        workplace
                        or ("remote" if "remote" in location.lower() else "onsite")
                    ),
                    "department": item.get("JobFamily") or item.get("JobFunction") or "",
                    "description": item.get("ShortDescriptionStr") or "",
                    "job_url": (
                        f"https://{domain}/hcmUI/CandidateExperience/en/sites/"
                        f"{site_path}/job/{external_id}"
                    ),
                    "posted_at": parse_datetime(item.get("PostedDate")),
                    "raw_payload": item,
                }
            offset += len(postings)
            total = int(search.get("TotalJobsCount") or 0)
            if not postings or offset >= total:
                break
    return list(jobs_by_id.values())


def _apple_jobs(source):
    queries = source.get("queries") or ["data engineer", "AI platform", "data platform"]
    jobs_by_id = {}
    hydration_pattern = re.compile(
        r"window\.__staticRouterHydrationData\s*=\s*"
        r'JSON\.parse\(("(?:\\.|[^"\\])*")\)'
    )
    for query in queries:
        for page in range(1, 4):
            params = urlencode({"search": query, "page": page})
            html = _get_text(f"https://jobs.apple.com/en-us/search?{params}")
            match = hydration_pattern.search(html)
            if not match:
                raise RuntimeError("Apple Careers search payload was not found")
            hydration = json.loads(json.loads(match.group(1)))
            search = (hydration.get("loaderData") or {}).get("search") or {}
            postings = search.get("searchResults") or []
            for item in postings:
                external_id = str(item.get("positionId") or item.get("id") or "")
                if not external_id:
                    continue
                locations = item.get("locations") or []
                location = " | ".join(
                    value
                    for value in (
                        (entry.get("name") or entry.get("countryName") or "")
                        for entry in locations
                        if isinstance(entry, dict)
                    )
                    if value
                )
                slug = item.get("transformedPostingTitle") or ""
                jobs_by_id[external_id] = {
                    "external_id": external_id,
                    "title": item.get("postingTitle") or "",
                    "location": location,
                    "work_mode": "remote" if item.get("homeOffice") else "onsite",
                    "department": (item.get("team") or {}).get("teamName") or "",
                    "description": item.get("jobSummary") or "",
                    "job_url": (
                        f"https://jobs.apple.com/en-us/details/{external_id}/{slug}"
                    ).rstrip("/"),
                    "posted_at": parse_datetime(
                        item.get("postDateInGMT") or item.get("postingDate")
                    ),
                    "raw_payload": item,
                }
            total = int(search.get("totalRecords") or 0)
            if not postings or page * len(postings) >= total:
                break
    return list(jobs_by_id.values())


def _eightfold_jobs(source):
    base_url = source["base_url"].rstrip("/")
    domain = source["domain"]
    queries = source.get("queries") or ["data engineer", "AI platform", "data platform"]
    locations = source.get("locations") or ["India", ""]
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    bootstrap = Request(
        f"{base_url}/careers?{urlencode({'domain': domain})}",
        headers={"User-Agent": USER_AGENT},
    )
    with opener.open(bootstrap, timeout=HTTP_TIMEOUT_SECONDS):
        pass

    jobs_by_id = {}
    for query in queries:
        for location in locations:
            for start in (0, 10):
                params = urlencode(
                    {
                        "domain": domain,
                        "query": query,
                        "location": location,
                        "start": start,
                        "sort_by": "timestamp",
                    }
                )
                request = Request(
                    f"{base_url}/api/pcsx/search?{params}",
                    headers={"Accept": "application/json", "User-Agent": USER_AGENT},
                )
                with opener.open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                data = payload.get("data") if payload.get("status") == 200 else payload
                for item in (data or {}).get("positions", []):
                    external_id = str(item.get("id") or "")
                    if not external_id:
                        continue
                    location_values = item.get("locations") or []
                    location_text = " | ".join(location_values)
                    position_url = item.get("positionUrl") or f"/careers/job/{external_id}"
                    jobs_by_id[external_id] = {
                        "external_id": external_id,
                        "title": item.get("name") or "",
                        "location": location_text,
                        "work_mode": item.get("workLocationOption") or "",
                        "department": item.get("department") or "",
                        "description": clean_html(
                            item.get("jobDescription") or item.get("description")
                        ),
                        "job_url": (
                            position_url
                            if position_url.startswith("http")
                            else f"{base_url}{position_url}"
                        ),
                        "posted_at": parse_datetime(item.get("postedTs")),
                        "raw_payload": item,
                    }
    return list(jobs_by_id.values())


def _google_jobs(source):
    queries = source.get("queries") or ["data engineer", "AI platform", "data platform"]
    locations = source.get("locations") or ["India"]
    jobs_by_id = {}
    for query in queries:
        for location in locations:
            for page in range(1, 4):
                params = urlencode({"q": query, "location": location, "page": page})
                html = _get_text(
                    "https://www.google.com/about/careers/applications/jobs/results?"
                    f"{params}"
                )
                chunks = html.split('<li class="lLd3Je"')[1:]
                if not chunks and page == 1:
                    raise RuntimeError("Google Careers job cards were not found")
                for chunk in chunks:
                    title_match = re.search(
                        r'<h3 class="QJPWVe">(.*?)</h3>', chunk, re.DOTALL
                    )
                    link_match = re.search(
                        r'href="(jobs/results/(\d+)[^"]*)"', chunk
                    )
                    if not title_match or not link_match:
                        continue
                    location_match = re.search(
                        r'<span class="r0wTof[^"]*">(.*?)</span>',
                        chunk,
                        re.DOTALL,
                    )
                    external_id = link_match.group(2)
                    location_text = clean_html(
                        location_match.group(1) if location_match else ""
                    )
                    relative_url = unescape(link_match.group(1))
                    jobs_by_id[external_id] = {
                        "external_id": external_id,
                        "title": clean_html(title_match.group(1)),
                        "location": location_text,
                        "work_mode": (
                            "remote" if "remote" in location_text.lower() else "onsite"
                        ),
                        "department": "",
                        "description": clean_html(chunk[:20_000]),
                        "job_url": (
                            "https://www.google.com/about/careers/applications/"
                            f"{relative_url}"
                        ),
                        "posted_at": None,
                        "raw_payload": {
                            "query": query,
                            "location": location,
                            "page": page,
                        },
                    }
                if not chunks:
                    break
    return list(jobs_by_id.values())


def _walmart_jobs(source):
    query_id = source["query_id"]
    populations = source["populations"]
    queries = source.get("queries") or ["data engineer", "AI platform", "data platform"]
    jobs_by_id = {}
    for query in queries:
        for offset in (0, 10, 20):
            payload = _post_json(
                "https://careers.walmart.com/api/graphql",
                {
                    "queryId": query_id,
                    "variables": {
                        "jobSearchRequest": {
                            "searchString": query,
                            "population": populations,
                            "latitude": None,
                            "longitude": None,
                            "from": offset,
                            "size": 10,
                            "filters": None,
                            "sortBy": None,
                        }
                    },
                },
            )
            search = ((payload.get("data") or {}).get("jobSearch") or {})
            postings = search.get("searchResults") or []
            for item in postings:
                external_id = str(item.get("jobId") or "")
                if not external_id:
                    continue
                locations = item.get("location") or []
                location = " | ".join(
                    entry.get("storeName") or ""
                    for entry in locations
                    if isinstance(entry, dict) and entry.get("storeName")
                )
                jobs_by_id[external_id] = {
                    "external_id": external_id,
                    "title": item.get("jobTitle") or "",
                    "location": location,
                    "work_mode": (
                        "remote" if "remote" in location.lower() else "onsite"
                    ),
                    "department": item.get("brand") or "",
                    "description": "",
                    "job_url": f"https://careers.walmart.com/us/en/jobs/{external_id}",
                    "posted_at": None,
                    "raw_payload": item,
                }
            if not postings:
                break
    return list(jobs_by_id.values())


def _successfactors_rss_jobs(source):
    root = ET.fromstring(
        _get_text(source["feed_url"], accept="application/rss+xml,application/xml")
    )
    jobs = []
    for item in root.findall("./channel/item"):
        title_text = item.findtext("title") or ""
        link = item.findtext("link") or ""
        id_match = re.search(r"/(\d+)/?(?:\?|$)", link)
        if not id_match:
            continue
        location_match = re.search(r"\(([^()]*)\)\s*$", title_text)
        location = location_match.group(1) if location_match else ""
        title = (
            title_text[: location_match.start()].strip()
            if location_match
            else title_text
        )
        published = None
        try:
            published_value = parsedate_to_datetime(item.findtext("pubDate") or "")
            published = published_value.astimezone(timezone.utc).replace(tzinfo=None)
        except (TypeError, ValueError):
            pass
        jobs.append(
            {
                "external_id": id_match.group(1),
                "title": title,
                "location": location,
                "work_mode": normalize_work_mode(
                    location,
                    description=clean_html(item.findtext("description")),
                ),
                "department": "",
                "description": clean_html(item.findtext("description")),
                "job_url": link,
                "posted_at": published,
                "raw_payload": {
                    "title": title_text,
                    "pubDate": item.findtext("pubDate"),
                },
            }
        )
    return jobs


def _generic_rss_jobs(source):
    root = ET.fromstring(
        _get_text(source["feed_url"], accept="application/rss+xml,application/xml")
    )
    jobs = []
    for item in root.findall("./channel/item"):
        link = (item.findtext("link") or item.findtext("guid") or "").strip()
        external_id_match = re.search(r"/(\d+)/?(?:\?|$)", link)
        external_id = (
            external_id_match.group(1)
            if external_id_match
            else (item.findtext("guid") or link).strip()
        )
        title = (item.findtext("title") or "").strip()
        if not external_id or not title or not link:
            continue
        description = clean_html(item.findtext("description"))
        location = source.get("default_location", "")
        published = None
        try:
            published_value = parsedate_to_datetime(item.findtext("pubDate") or "")
            published = published_value.astimezone(timezone.utc).replace(tzinfo=None)
        except (TypeError, ValueError):
            pass
        jobs.append(
            {
                "external_id": external_id,
                "title": title,
                "location": location,
                "work_mode": normalize_work_mode(
                    location,
                    description=description,
                ),
                "department": "",
                "description": description,
                "job_url": link,
                "posted_at": published,
                "raw_payload": {
                    "title": title,
                    "pubDate": item.findtext("pubDate"),
                },
            }
        )
    return jobs


def _phenom_jobs(source):
    base_url = source["base_url"].rstrip("/")
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    bootstrap = Request(
        f"{base_url}{source['search_path']}",
        headers={"User-Agent": USER_AGENT},
    )
    with opener.open(bootstrap, timeout=HTTP_TIMEOUT_SECONDS):
        pass

    queries = source.get("queries") or ["data engineer", "AI platform", "data platform"]
    countries = source.get("countries") or []
    filter_sets = [{"country": [country]} for country in countries] + [{}]
    jobs_by_id = {}
    for query in queries:
        for selected_fields in filter_sets:
            for offset in (0, 10, 20):
                payload = {
                    "lang": source.get("lang", "en_global"),
                    "deviceType": "desktop",
                    "country": source.get("country", "global"),
                    "pageName": "search-results",
                    "size": 10,
                    "from": offset,
                    "jobs": True,
                    "counts": True,
                    "all_fields": ["category", "country", "city", "type"],
                    "clearAll": False,
                    "jdsource": "facets",
                    "isSliderEnable": False,
                    "pageId": "page20",
                    "siteType": "external",
                    "keywords": query,
                    "global": True,
                    "selected_fields": selected_fields,
                    "sort": {"order": "desc", "field": "postedDate"},
                    "locationData": {},
                    "refNum": source["ref_num"],
                    "ddoKey": "refineSearch",
                }
                request = Request(
                    f"{base_url}/widgets",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "User-Agent": USER_AGENT,
                    },
                    method="POST",
                )
                with opener.open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                    response_payload = json.loads(response.read().decode("utf-8"))
                search = response_payload.get("refineSearch") or {}
                postings = ((search.get("data") or {}).get("jobs") or [])
                for item in postings:
                    external_id = str(item.get("jobId") or item.get("reqId") or "")
                    if not external_id:
                        continue
                    location = (
                        item.get("location")
                        or item.get("cityStateCountry")
                        or item.get("city")
                        or ""
                    )
                    jobs_by_id[external_id] = {
                        "external_id": external_id,
                        "title": item.get("title") or "",
                        "location": location,
                        "work_mode": item.get("RemoteType") or (
                            "remote" if "remote" in location.lower() else "onsite"
                        ),
                        "department": item.get("category") or "",
                        "description": item.get("descriptionTeaser") or "",
                        "job_url": item.get("applyUrl") or "",
                        "posted_at": parse_datetime(
                            item.get("postedDate") or item.get("dateCreated")
                        ),
                        "raw_payload": item,
                    }
                if not postings:
                    break
    return list(jobs_by_id.values())


def _avature_jobs(source):
    base_url = source["base_url"].rstrip("/")
    queries = source.get("queries") or ["data engineer", "AI platform", "data platform"]
    links = {}
    for query in queries:
        html = _get_text(f"{base_url}/SearchJobs?{urlencode({'search': query})}")
        for link in re.findall(r'href=["\']([^"\']*JobDetail[^"\']*)["\']', html):
            absolute_link = link if link.startswith("http") else f"{base_url}/{link.lstrip('/')}"
            id_match = re.search(r"/(\d+)/?$", absolute_link)
            if id_match:
                links[id_match.group(1)] = absolute_link

    jobs = []
    for external_id, link in links.items():
        html = _get_text(link)
        title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL | re.IGNORECASE)
        location_match = re.search(
            r">\s*Location\s*</div>\s*"
            r'<div class="article__content__view__field__value">\s*(.*?)\s*</div>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        title = clean_html(title_match.group(1) if title_match else "")
        if not title:
            title = link.rstrip("/").split("/")[-2].replace("-", " ")
        location = clean_html(location_match.group(1) if location_match else "")
        jobs.append(
            {
                "external_id": external_id,
                "title": title,
                "location": location,
                "work_mode": "remote" if "remote" in location.lower() else "onsite",
                "department": "",
                "description": clean_html(html),
                "job_url": link,
                "posted_at": None,
                "raw_payload": {"detail_url": link},
            }
        )
    return jobs


def _deshaw_jobs(source):
    base_url = "https://www.deshaw.com"
    html = _get_text(f"{base_url}/careers")
    links = {}
    for path in re.findall(r'href=["\'](/careers/[^"\']+-\d+)["\']', html):
        external_id = path.rsplit("-", 1)[-1]
        links[external_id] = path
    jobs = []
    for external_id, path in links.items():
        slug = path.rsplit("/", 1)[-1].rsplit("-", 1)[0]
        title = slug.replace("-", " ").title()
        if not any(term in title.lower() for term in ("data", "ai ", "platform")):
            continue
        detail_html = _get_text(f"{base_url}{path}")
        location_match = re.search(
            r"(?:Location|Office)</[^>]+>\s*<[^>]+>(.*?)</",
            detail_html,
            re.DOTALL | re.IGNORECASE,
        )
        location = clean_html(location_match.group(1) if location_match else "")
        jobs.append(
            {
                "external_id": external_id,
                "title": title,
                "location": location,
                "work_mode": "remote" if "remote" in location.lower() else "onsite",
                "department": "",
                "description": clean_html(detail_html),
                "job_url": f"{base_url}{path}",
                "posted_at": None,
                "raw_payload": {"detail_path": path},
            }
        )
    return jobs


def _radancy_jobs(source):
    base_url = source["base_url"].rstrip("/")
    queries = source.get("queries") or ["data engineer", "AI platform", "data platform"]
    jobs_by_id = {}
    card_pattern = re.compile(
        r'<a href="([^"]+)" data-job-id="([^"]+)"[^>]*>'
        r"<strong>(.*?)</strong></a>\s*"
        r'<p class="job-location">(.*?)</p>',
        re.DOTALL | re.IGNORECASE,
    )
    for query in queries:
        slug = quote(query.replace(" ", "-"))
        for page in range(1, 4):
            html = _get_text(
                f"{base_url}/search-jobs/{slug}/{source['site_id']}/{page}"
            )
            matches = card_pattern.findall(html)
            for path, external_id, title_html, location_html in matches:
                link = path if path.startswith("http") else f"{base_url}{path}"
                location = clean_html(location_html)
                jobs_by_id[external_id] = {
                    "external_id": external_id,
                    "title": clean_html(title_html),
                    "location": location,
                    "work_mode": (
                        "remote" if "remote" in location.lower() else "onsite"
                    ),
                    "department": "",
                    "description": "",
                    "job_url": link,
                    "posted_at": None,
                    "raw_payload": {"search_query": query, "page": page},
                }
            if not matches:
                break
    return list(jobs_by_id.values())


def _tiktok_jobs(source):
    endpoint = "https://api.lifeattiktok.com/api/v1/public/supplier/search/job/posts"
    queries = source.get("queries") or ["data engineer", "AI platform", "data platform"]
    jobs_by_id = {}
    for query in queries:
        payload = {
            "limit": 100,
            "offset": 0,
            "keyword": query,
            "category_id_list": [],
            "subject_id_list": [],
            "location_code_list": [],
            "job_function_id_list": [],
        }
        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "*/*",
                "Content-Type": "application/json",
                "website-path": "tiktok",
                "Origin": "https://lifeattiktok.com",
                "Referer": "https://lifeattiktok.com/",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        postings = ((response_payload.get("data") or {}).get("job_post_list") or [])
        for item in postings:
            external_id = str(item.get("id") or "")
            if not external_id:
                continue
            city = item.get("city_info") or {}
            location_parts = []
            while isinstance(city, dict) and city:
                label = city.get("en_name") or city.get("i18n_name")
                if label:
                    location_parts.append(label)
                city = city.get("parent")
            location = ", ".join(location_parts)
            category = item.get("job_category") or {}
            description = "\n\n".join(
                value
                for value in (item.get("description"), item.get("requirement"))
                if value
            )
            jobs_by_id[external_id] = {
                "external_id": external_id,
                "title": item.get("title") or "",
                "location": location,
                "work_mode": "remote" if "remote" in location.lower() else "onsite",
                "department": category.get("en_name") or "",
                "description": description,
                "job_url": f"https://lifeattiktok.com/search/{external_id}",
                "posted_at": parse_datetime(
                    item.get("publish_time") or item.get("post_time")
                ),
                "raw_payload": item,
            }
    return list(jobs_by_id.values())


def _icims_jobs(source):
    base_url = source["base_url"].rstrip("/")
    queries = source.get("queries") or ["data engineer", "AI platform", "data platform"]
    jobs_by_id = {}
    for query in queries:
        request_params = {"limit": 100, "offset": 0, "search": query}
        request_params.update(source.get("params") or {})
        params = urlencode(request_params)
        payload = _get_json(f"{base_url}/api/jobs?{params}")
        for wrapper in payload.get("jobs", []):
            item = wrapper.get("data") or wrapper
            external_id = str(item.get("req_id") or item.get("slug") or "")
            if not external_id:
                continue
            location = (
                item.get("full_location")
                or item.get("location_name")
                or ", ".join(
                    value
                    for value in (item.get("city"), item.get("state"), item.get("country"))
                    if value
                )
            )
            jobs_by_id[external_id] = {
                "external_id": external_id,
                "title": item.get("title") or "",
                "location": location,
                "work_mode": (
                    "remote"
                    if "remote" in f"{location} {item.get('location_type')}".lower()
                    else "onsite"
                ),
                "department": item.get("department") or item.get("category") or "",
                "description": clean_html(item.get("description")),
                "job_url": item.get("apply_url") or "",
                "posted_at": parse_datetime(
                    item.get("posted_date") or item.get("create_date")
                ),
                "raw_payload": item,
            }
    return list(jobs_by_id.values())


def _bank_of_america_jobs(source):
    base_url = "https://careers.bankofamerica.com"
    jobs_by_id = {}
    for offset in (0, 20, 40, 60):
        params = urlencode(
            {
                "country": "India",
                "start": offset,
                "rows": 20,
                "search": "jobsByCountry",
            }
        )
        payload = _get_json(f"{base_url}/services/jobssearchservlet?{params}")
        postings = payload.get("jobsList") or []
        for item in postings:
            external_id = str(item.get("jobRequisitionId") or "")
            if not external_id:
                continue
            path = item.get("jcrURL") or ""
            jobs_by_id[external_id] = {
                "external_id": external_id,
                "title": item.get("postingTitle") or "",
                "location": item.get("location") or item.get("primaryLocation") or "",
                "work_mode": "onsite",
                "department": item.get("area") or item.get("division") or "",
                "description": item.get("jobDescriptionExternal") or "",
                "job_url": path if path.startswith("http") else f"{base_url}{path}",
                "posted_at": parse_datetime(item.get("postedDate")),
                "raw_payload": item,
            }
        if len(postings) < 20:
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
        "oraclehcm": _oracle_hcm_jobs,
        "apple": _apple_jobs,
        "eightfold": _eightfold_jobs,
        "google": _google_jobs,
        "walmart": _walmart_jobs,
        "successfactors_rss": _successfactors_rss_jobs,
        "generic_rss": _generic_rss_jobs,
        "phenom": _phenom_jobs,
        "avature": _avature_jobs,
        "deshaw": _deshaw_jobs,
        "radancy": _radancy_jobs,
        "tiktok": _tiktok_jobs,
        "icims": _icims_jobs,
        "bankofamerica": _bank_of_america_jobs,
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
