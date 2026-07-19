import hashlib
import os
from pathlib import Path

import streamlit as st


_VERSION_ENV_KEYS = (
    "APP_VERSION",
    "GIT_COMMIT",
    "SOURCE_VERSION",
    "STREAMLIT_GIT_COMMIT",
    "COMMIT_SHA",
)


def get_app_version():
    for key in _VERSION_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            return value[:12]

    root = Path(__file__).resolve().parents[1]
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
