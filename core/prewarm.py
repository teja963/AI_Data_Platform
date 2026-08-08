import importlib
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache


SAFE_PREWARM_MODULES = (
    "pandas",
    "altair",
)

_PREWARM_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="section-prewarm")


def _import_section_modules():
    failures = {}
    for module_name in SAFE_PREWARM_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as error:  # pragma: no cover - defensive startup isolation
            failures[module_name] = str(error)
    return failures


@lru_cache(maxsize=1)
def prewarm_section_modules():
    """Warm heavy libraries without importing Streamlit components off-thread."""
    return _PREWARM_EXECUTOR.submit(_import_section_modules)
