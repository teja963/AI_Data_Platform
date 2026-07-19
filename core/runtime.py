import hashlib
import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import streamlit as st

APP_STARTED_AT = datetime.now(timezone.utc)


_VERSION_ENV_KEYS = (
    "APP_VERSION",
    "GIT_COMMIT",
    "SOURCE_VERSION",
    "STREAMLIT_GIT_COMMIT",
    "COMMIT_SHA",
)


def _repo_root():
    return Path(__file__).resolve().parents[1]


def _read_text(path):
    try:
        return path.read_text().strip()
    except Exception:
        return ""


def get_git_repo():
    explicit_repo = os.environ.get("GITHUB_REPOSITORY")
    if explicit_repo:
        return explicit_repo

    config = _read_text(_repo_root() / ".git" / "config")
    for line in config.splitlines():
        line = line.strip()
        if not line.startswith("url ="):
            continue
        url = line.split("=", 1)[1].strip()
        if "github.com" not in url:
            continue
        repo = url.rstrip("/").removesuffix(".git")
        if repo.startswith("git@github.com:"):
            repo = repo.split(":", 1)[1]
        elif "github.com/" in repo:
            repo = repo.split("github.com/", 1)[1]
        return repo

    return "teja963/AI_Data_Platform"


def get_git_branch():
    return (
        os.environ.get("GITHUB_REF_NAME")
        or os.environ.get("BRANCH")
        or os.environ.get("STREAMLIT_BRANCH")
        or _read_text(_repo_root() / ".git" / "HEAD").removeprefix("ref: refs/heads/")
        or "main"
    )


def get_running_commit():
    for key in _VERSION_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            return value

    root = _repo_root()
    head = _read_text(root / ".git" / "HEAD")
    if not head:
        return ""

    if head.startswith("ref: "):
        ref = head.removeprefix("ref: ").strip()
        commit = _read_text(root / ".git" / ref)
        if commit:
            return commit

        packed_refs = _read_text(root / ".git" / "packed-refs")
        for line in packed_refs.splitlines():
            if line and not line.startswith("#") and line.endswith(ref):
                return line.split()[0]
        return ""

    return head


def _format_duration(seconds):
    if seconds is None:
        return "unknown"

    seconds = max(int(seconds), 0)
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {sec}s"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def _format_datetime_ist(value):
    if value is None:
        return "unknown"

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    ist = timezone(timedelta(hours=5, minutes=30))
    return value.astimezone(ist).strftime("%Y-%m-%d %I:%M:%S %p IST")


def _parse_github_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def get_latest_github_commit_info(repo, branch):
    try:
        request = Request(
            f"https://api.github.com/repos/{repo}/commits/{branch}",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "ai-data-engg-platform"},
        )
        with urlopen(request, timeout=5) as response:
            payload = response.read().decode("utf-8", errors="ignore")
    except (OSError, URLError):
        return {"sha": "", "committed_at": None}

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {"sha": "", "committed_at": None}

    committed_at = (
        data.get("commit", {})
        .get("committer", {})
        .get("date")
    )
    return {
        "sha": data.get("sha", ""),
        "committed_at": _parse_github_datetime(committed_at),
    }


def get_latest_github_commit(repo, branch):
    return get_latest_github_commit_info(repo, branch).get("sha", "")


def get_app_version():
    running_commit = get_running_commit()
    if running_commit:
        return running_commit[:12]

    root = _repo_root()
    source_files = [
        root / "app.py",
        root / "requirements.txt",
        root / "packages.txt",
        root / "runtime.txt",
    ]
    source_files.extend(sorted((root / "core").glob("*.py")))
    source_files.extend(sorted((root / "modules").glob("*/*.py")))

    digest = hashlib.sha256()
    for path in source_files:
        if not path.exists():
            continue
        stat = path.stat()
        digest.update(str(path.relative_to(root)).encode())
        digest.update(str(stat.st_mtime_ns).encode())
        digest.update(str(stat.st_size).encode())

    return digest.hexdigest()[:12]


def ensure_fresh_runtime():
    current_version = get_app_version()
    previous_version = st.session_state.get("app_version")

    if previous_version and previous_version != current_version:
        st.cache_data.clear()

    st.session_state["app_version"] = current_version
    return current_version


def clear_cached_runtime_data():
    st.cache_data.clear()
    for key in list(st.session_state.keys()):
        if key.startswith("progress_cache::"):
            st.session_state.pop(key, None)


def get_deploy_health():
    repo = get_git_repo()
    branch = get_git_branch()
    running_commit = get_running_commit()
    latest_info = get_latest_github_commit_info(repo, branch)
    latest_commit = latest_info.get("sha", "")
    latest_committed_at = latest_info.get("committed_at")
    is_current = bool(running_commit and latest_commit and running_commit[:12] == latest_commit[:12])
    deploy_latency_seconds = None
    if latest_committed_at and is_current:
        deploy_latency_seconds = (APP_STARTED_AT - latest_committed_at).total_seconds()
    now = datetime.now(timezone.utc)

    return {
        "repo": repo,
        "branch": branch,
        "running_commit": running_commit,
        "latest_commit": latest_commit,
        "latest_committed_at": latest_committed_at,
        "app_started_at": APP_STARTED_AT,
        "server_now": now,
        "latest_committed_at_display": _format_datetime_ist(latest_committed_at),
        "app_started_at_display": _format_datetime_ist(APP_STARTED_AT),
        "server_now_display": _format_datetime_ist(now),
        "deploy_latency_seconds": deploy_latency_seconds,
        "deploy_latency": _format_duration(deploy_latency_seconds),
        "is_current": is_current,
        "app_version": get_app_version(),
    }
