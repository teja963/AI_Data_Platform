import builtins
import copy
import io
import json
import math
import os
import re
import tempfile
import traceback
from collections import Counter, defaultdict, deque
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

try:
    import numpy as np
except ImportError:  # pragma: no cover - optional dependency
    np = None


def _build_namespace():
    namespace = {
        "__builtins__": builtins.__dict__,
        "Counter": Counter,
        "defaultdict": defaultdict,
        "deque": deque,
        "date": date,
        "datetime": datetime,
        "timedelta": timedelta,
        "json": json,
        "math": math,
        "os": os,
        "Path": Path,
        "pd": pd,
        "re": re,
    }

    if np is not None:
        namespace["np"] = np

    return namespace


def _write_fixture_file(base_dir, relative_path, content):
    file_path = Path(base_dir) / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(content, (dict, list)):
        file_path.write_text(json.dumps(content, indent=2, sort_keys=True))
    else:
        file_path.write_text(str(content))


def _resolve_placeholders(value, temp_dir):
    if isinstance(value, str) and value.startswith("__TMP__/"):
        return str(Path(temp_dir) / value.replace("__TMP__/", "", 1))
    if isinstance(value, list):
        return [_resolve_placeholders(item, temp_dir) for item in value]
    if isinstance(value, tuple):
        return tuple(_resolve_placeholders(item, temp_dir) for item in value)
    if isinstance(value, dict):
        return {key: _resolve_placeholders(item, temp_dir) for key, item in value.items()}
    return copy.deepcopy(value)


def _normalize_dataframe(df, sort_by=None):
    normalized = df.copy()
    if sort_by:
        normalized = normalized.sort_values(sort_by)
    normalized = normalized.reset_index(drop=True)
    normalized.columns = [str(column) for column in normalized.columns]
    normalized = normalized.reindex(sorted(normalized.columns), axis=1)
    for column in normalized.columns:
        if pd.api.types.is_datetime64_any_dtype(normalized[column]):
            normalized[column] = normalized[column].dt.strftime("%Y-%m-%d %H:%M:%S")
    return normalized


def _compare_values(actual, expected, test):
    tolerance = test.get("tolerance", 1e-9)
    sort_by = test.get("sort_by")

    if isinstance(expected, pd.DataFrame):
        if not isinstance(actual, pd.DataFrame):
            return False, f"Expected DataFrame but got {type(actual).__name__}"
        actual_df = _normalize_dataframe(actual, sort_by)
        expected_df = _normalize_dataframe(expected, sort_by)
        try:
            pd.testing.assert_frame_equal(actual_df, expected_df, check_dtype=False)
        except AssertionError as exc:
            return False, str(exc)
        return True, ""

    if np is not None and isinstance(expected, np.ndarray):
        if not isinstance(actual, np.ndarray):
            return False, f"Expected ndarray but got {type(actual).__name__}"
        if not np.allclose(actual, expected, atol=tolerance, rtol=0):
            return False, f"Expected {expected.tolist()} but got {actual.tolist()}"
        return True, ""

    if isinstance(expected, float):
        if not math.isclose(actual, expected, abs_tol=tolerance, rel_tol=0):
            return False, f"Expected {expected} but got {actual}"
        return True, ""

    if actual != expected:
        return False, f"Expected {expected!r} but got {actual!r}"

    return True, ""


def _check_expected_files(expected_files, temp_dir):
    for relative_path, expected_content in expected_files.items():
        file_path = Path(temp_dir) / relative_path
        if not file_path.exists():
            return False, f"Expected output file {relative_path} was not created."

        if isinstance(expected_content, (dict, list)):
            actual_content = json.loads(file_path.read_text())
            if actual_content != expected_content:
                return False, f"File {relative_path} content mismatch."
        else:
            actual_text = file_path.read_text()
            if actual_text != str(expected_content):
                return False, f"File {relative_path} content mismatch."

    return True, ""


def _preview(value):
    if isinstance(value, pd.DataFrame):
        return value.head(8).to_dict(orient="records")
    if np is not None and isinstance(value, np.ndarray):
        return value.tolist()
    return value


def run_python_question(question, code):
    namespace = _build_namespace()
    stdout_buffer = io.StringIO()

    try:
        with redirect_stdout(stdout_buffer):
            exec(code, namespace, namespace)
    except Exception:
        return {
            "passed": False,
            "error": traceback.format_exc(limit=3),
            "results": [],
            "stdout": stdout_buffer.getvalue(),
        }

    function_name = question["entry_point"]
    function = namespace.get(function_name)
    if not callable(function):
        return {
            "passed": False,
            "error": f"Define a callable function named `{function_name}` before running.",
            "results": [],
            "stdout": stdout_buffer.getvalue(),
        }

    results = []
    all_passed = True

    for index, test in enumerate(question["tests"], start=1):
        with tempfile.TemporaryDirectory() as temp_dir:
            for relative_path, content in test.get("files", {}).items():
                _write_fixture_file(temp_dir, relative_path, content)

            args = _resolve_placeholders(test.get("args", ()), temp_dir)
            kwargs = _resolve_placeholders(test.get("kwargs", {}), temp_dir)

            try:
                actual = function(*copy.deepcopy(args), **copy.deepcopy(kwargs))
                files_ok, files_message = _check_expected_files(test.get("expected_files", {}), temp_dir)
                if not files_ok:
                    passed = False
                    message = files_message
                else:
                    passed, message = _compare_values(actual, test["expected"], test)
            except Exception:
                actual = None
                passed = False
                message = traceback.format_exc(limit=2)

        results.append(
            {
                "test": f"Test {index}",
                "passed": passed,
                "message": message or "Passed",
                "expected": _preview(test["expected"]),
                "actual": _preview(actual),
            }
        )
        all_passed = all_passed and passed

    return {
        "passed": all_passed,
        "error": None,
        "results": results,
        "stdout": stdout_buffer.getvalue(),
    }
