import importlib
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache


SECTION_MODULES = (
    "modules.job_alerts.ui",
    "modules.coding.ui",
    "modules.sql.ui",
    "modules.python.ui",
    "modules.concepts.ui",
    "modules.genai.ui",
    "modules.spark.ui",
    "modules.datamodeling.ui",
    "modules.data_sources.ui",
    "modules.orchestration.ui",
    "modules.warehouses.ui",
    "modules.lakehouse.ui",
    "modules.architecture.ui",
    "modules.devops.ui",
    "modules.cloud.ui",
    "modules.projects.ui",
    "modules.admin.ui",
)

_PREWARM_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="section-prewarm")


def _import_section_modules():
    failures = {}
    for module_name in SECTION_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as error:  # pragma: no cover - defensive startup isolation
            failures[module_name] = str(error)
    return failures


@lru_cache(maxsize=1)
def prewarm_section_modules():
    """Import routed sections off the navigation path once per app process."""
    return _PREWARM_EXECUTOR.submit(_import_section_modules)
