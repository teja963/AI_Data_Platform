from pathlib import Path
from textwrap import dedent

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "data" / "python_fixtures"


def _parse_arg_names(signature):
    arg_string = signature.split("(", 1)[1].rsplit(")", 1)[0].strip()
    if not arg_string:
        return []

    args = []
    for part in arg_string.split(","):
        name = part.strip().split("=", 1)[0].strip()
        if ":" in name:
            name = name.split(":", 1)[0].strip()
        if name:
            args.append(name)
    return args


def _describe_value(value):
    if isinstance(value, pd.DataFrame):
        return "pandas.DataFrame"
    if isinstance(value, list):
        if not value:
            return "list"
        if all(isinstance(item, str) and item.startswith("__TMP__/") for item in value):
            return "list[path string]"
        sample = value[0]
        if isinstance(sample, dict):
            return "list[dict]"
        if isinstance(sample, list):
            return "list[list]"
        return f"list[{type(sample).__name__}]"
    if isinstance(value, tuple):
        return "tuple"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, str):
        return "path string" if value.startswith("__TMP__/") else "string"
    if value is None:
        return "None"
    return type(value).__name__


def _build_input_format(signature, tests):
    arg_names = _parse_arg_names(signature)
    if not tests:
        return ["The evaluator passes the function arguments directly."]

    sample_args = tests[0].get("args", ())
    details = []
    for index, arg_name in enumerate(arg_names):
        value = sample_args[index] if index < len(sample_args) else None
        if isinstance(value, str) and value.startswith("__TMP__/"):
            details.append(f"`{arg_name}` is passed as one readable local file path string. Use the provided path exactly as shown.")
        elif isinstance(value, list) and value and all(isinstance(item, str) and item.startswith("__TMP__/") for item in value):
            details.append(f"`{arg_name}` is passed as a list of readable local file path strings. Use the provided paths in the same order.")
        else:
            details.append(f"`{arg_name}` is passed as `{_describe_value(value)}`.")
    return details or ["The evaluator passes the function arguments directly."]


def _build_output_format(tests):
    if not tests:
        return "Return the computed answer."
    return f"Return a value shaped like `{_describe_value(tests[0]['expected'])}`."


def _constraint_for_arg(name, value):
    if isinstance(value, list):
        if value and all(isinstance(item, str) and item.startswith("__TMP__/") for item in value):
            return f"`{name}` is a list of valid readable local file paths provided by the evaluator."
        if value and isinstance(value[0], dict):
            return f"`0 <= len({name}) <= 10^4`; each element is a record dictionary matching the prompt."
        if value and isinstance(value[0], list):
            return f"`0 <= len({name}) <= 10^4`; nested list shape follows the examples."
        if value and isinstance(value[0], str):
            return f"`0 <= len({name}) <= 10^5`; string elements may repeat unless the prompt says otherwise."
        return f"`0 <= len({name}) <= 10^5`."
    if isinstance(value, tuple):
        return f"`{name}` is passed as a tuple-shaped argument exactly as shown in the examples."
    if isinstance(value, dict):
        return f"`{name}` is a dictionary input; preserve required keys and output shape."
    if isinstance(value, str):
        if value.startswith("__TMP__/"):
            return f"`{name}` is a valid readable local file path provided by the evaluator."
        return f"`0 <= len({name}) <= 10^5`."
    if isinstance(value, int):
        if name in {"k", "window", "batch_size", "retries", "threshold_minutes"}:
            return f"`0 <= {name} <= 10^5`."
        return f"`{name}` fits within standard Python integer handling."
    if isinstance(value, float):
        return f"`{name}` is numeric; preserve required precision."
    if isinstance(value, pd.DataFrame):
        columns = ", ".join(f"`{column}`" for column in value.columns)
        return f"`{name}` is a pandas DataFrame containing columns {columns}."
    return f"`{name}` follows the type shown in the examples."


def _default_constraints(signature, tests):
    arg_names = _parse_arg_names(signature)
    sample_args = tests[0].get("args", ()) if tests else ()
    constraints = []

    for index, arg_name in enumerate(arg_names):
        value = sample_args[index] if index < len(sample_args) else None
        constraints.append(_constraint_for_arg(arg_name, value))

    constraints.append("Return exactly the output type and ordering described in the prompt.")
    return constraints


def _default_edge_cases(tests, tags):
    edge_cases = []
    for test in tests:
        for value in test.get("args", ()):
            is_empty = (
                (isinstance(value, (list, tuple, dict, str)) and len(value) == 0)
                or value is None
            )
            if is_empty:
                edge_cases.append("Empty input should still return a valid output.")
                break
        if test.get("files"):
            edge_cases.append("Blank or partially populated file rows should not break the logic.")

    if "dedupe" in tags or "hashmap" in tags:
        edge_cases.append("Repeated keys or duplicate records should be handled deliberately.")
    if "sliding-window" in tags:
        edge_cases.append("Invalid window sizes and very small windows should not crash the solution.")
    if "pandas" in tags:
        edge_cases.append("Sort order and null handling should stay stable in the final result.")
    if "aws" in tags or "pipelines" in tags:
        edge_cases.append("Think about retries, ordering, or partial failures the same way you would in production code.")

    deduped = []
    for item in edge_cases:
        if item not in deduped:
            deduped.append(item)
    return deduped or ["Cover empty or minimal input sizes and preserve the requested output shape."]


def _replace_fixture_placeholders(value, question_id):
    if isinstance(value, str) and value.startswith("__TMP__/"):
        return str(FIXTURE_ROOT / f"question_{question_id}" / value.replace("__TMP__/", "", 1))
    if isinstance(value, list):
        return [_replace_fixture_placeholders(item, question_id) for item in value]
    if isinstance(value, tuple):
        return tuple(_replace_fixture_placeholders(item, question_id) for item in value)
    if isinstance(value, dict):
        return {key: _replace_fixture_placeholders(item, question_id) for key, item in value.items()}
    return value


def _build_examples(question_id, tests):
    examples = []
    for index, test in enumerate(tests[:2], start=1):
        examples.append(
            {
                "label": f"Example {index}",
                "inputs": _replace_fixture_placeholders(test.get("args", ()), question_id),
                "expected": test["expected"],
                "files": test.get("files", {}),
            }
        )
    return examples


def _function_starter(signature):
    return dedent(
        f"""
        def {signature}:
            # Write only this function for submission.
            pass
        """
    ).strip()


def _practice_fixture_paths(question_id, tests):
    files = tests[0].get("files", {}) if tests else {}
    return [str(FIXTURE_ROOT / f"question_{question_id}" / relative_path) for relative_path in files]


def _script_starter(question_id, signature, tests):
    entry_point = signature.split("(", 1)[0]
    sample_args = tests[0].get("args", ()) if tests else ()
    practice_files = _practice_fixture_paths(question_id, tests)

    if any(isinstance(value, pd.DataFrame) for value in sample_args):
        sample_block = "    # Build a small DataFrame here when you want to test locally.\n    print('Create a DataFrame sample, then call the function.')"
    elif practice_files:
        rendered_args = []
        fixture_iter = iter(practice_files)
        for value in sample_args:
            if isinstance(value, str) and value.startswith("__TMP__/"):
                try:
                    replacement = next(fixture_iter)
                except StopIteration:
                    replacement = str(FIXTURE_ROOT / f"question_{question_id}" / value.replace("__TMP__/", "", 1))
                rendered_args.append(repr(replacement))
            else:
                rendered_args.append(repr(value))
        sample_block = f"    print({entry_point}({', '.join(rendered_args)}))"
    else:
        sample_literal = ", ".join(repr(value) for value in sample_args)
        if sample_literal:
            sample_block = f"    print({entry_point}({sample_literal}))"
        else:
            sample_block = f"    print({entry_point}())"

    return dedent(
        f"""
        def {signature}:
            # Use this template only for local scratch practice.
            pass


        if __name__ == "__main__":
            # Replace the sample call with real input parsing if you want scratch-style practice.
{sample_block}
        """
    ).strip()


def _question(
    question_id,
    category,
    title,
    difficulty,
    signature,
    description,
    hint,
    solution,
    tests,
    tags=None,
    constraints=None,
    edge_cases=None,
    input_format=None,
    output_format=None,
    examples=None,
):
    tags = tags or []
    return {
        "id": question_id,
        "category": category,
        "title": title,
        "difficulty": difficulty,
        "signature": signature,
        "entry_point": signature.split("(", 1)[0],
        "description": description,
        "hint": hint,
        "submission_mode": "Write only the function shown below for submission. The evaluator calls your function directly with prepared arguments.",
        "starter_code": _function_starter(signature),
        "script_starter": _script_starter(question_id, signature, tests),
        "solution": dedent(solution).strip(),
        "tests": tests,
        "tags": tags,
        "constraints": constraints or _default_constraints(signature, tests),
        "edge_cases": edge_cases or _default_edge_cases(tests, tags),
        "input_format": input_format or _build_input_format(signature, tests),
        "output_format": output_format or _build_output_format(tests),
        "examples": examples or _build_examples(question_id, tests),
        "practice_fixture_paths": _practice_fixture_paths(question_id, tests),
    }


def get_python_questions():
    questions = [
        _question(
            1,
            "Arrays & Hashing",
            "Two Sum Indices",
            "Easy",
            "two_sum_indices(nums, target)",
            "Return the first pair of indices whose values add up to target. "
            "If no pair exists, return an empty list.",
            "Use a hashmap from value to index while scanning left to right.",
            """
            def two_sum_indices(nums, target):
                seen = {}
                for idx, value in enumerate(nums):
                    need = target - value
                    if need in seen:
                        return [seen[need], idx]
                    seen[value] = idx
                return []
            """,
            tests=[
                {"args": ([2, 7, 11, 15], 9), "expected": [0, 1]},
                {"args": ([3, 2, 4], 6), "expected": [1, 2]},
                {"args": ([1, 2, 3], 10), "expected": []},
            ],
            tags=["hashmap", "arrays", "interview-basics"],
        ),
        _question(
            2,
            "Arrays & Hashing",
            "Count Event Frequencies",
            "Easy",
            "count_event_frequencies(events)",
            "Return a dictionary counting how many times each event type appears.",
            "A defaultdict(int) or plain dict update is enough here.",
            """
            from collections import defaultdict

            def count_event_frequencies(events):
                counts = defaultdict(int)
                for event in events:
                    counts[event] += 1
                return dict(counts)
            """,
            tests=[
                {
                    "args": (["click", "view", "click", "purchase", "view"],),
                    "expected": {"click": 2, "view": 2, "purchase": 1},
                },
                {"args": ([],), "expected": {}},
            ],
            tags=["defaultdict", "counts", "data-engineering"],
        ),
        _question(
            3,
            "Arrays & Hashing",
            "Top K Frequent Events",
            "Medium",
            "top_k_frequent(items, k)",
            "Return the k most frequent items sorted by frequency descending, then value ascending.",
            "Count first, then sort with a compound key.",
            """
            from collections import Counter

            def top_k_frequent(items, k):
                counts = Counter(items)
                ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
                return [item for item, _ in ranked[:k]]
            """,
            tests=[
                {
                    "args": (["api", "db", "api", "queue", "db", "api"], 2),
                    "expected": ["api", "db"],
                },
                {
                    "args": ([5, 7, 5, 8, 7, 7, 8], 2),
                    "expected": [7, 5],
                },
            ],
            tags=["sorting", "counter", "hashmap"],
        ),
        _question(
            4,
            "Strings & Parsing",
            "Parse Log Line",
            "Easy",
            "parse_log_line(line)",
            "Parse a pipe-delimited log line formatted as `timestamp|level|service|message`.",
            "Split only the first three separators so the message can still contain pipes.",
            """
            def parse_log_line(line):
                timestamp, level, service, message = line.split("|", 3)
                return {
                    "timestamp": timestamp,
                    "level": level,
                    "service": service,
                    "message": message,
                }
            """,
            tests=[
                {
                    "args": ("2024-01-01T10:00:00Z|ERROR|billing|payment failed",),
                    "expected": {
                        "timestamp": "2024-01-01T10:00:00Z",
                        "level": "ERROR",
                        "service": "billing",
                        "message": "payment failed",
                    },
                },
                {
                    "args": ("2024-01-01T10:00:00Z|INFO|auth|token|refresh",),
                    "expected": {
                        "timestamp": "2024-01-01T10:00:00Z",
                        "level": "INFO",
                        "service": "auth",
                        "message": "token|refresh",
                    },
                },
            ],
            tags=["strings", "parsing", "logs"],
        ),
        _question(
            5,
            "Strings & Parsing",
            "Longest Unique Substring",
            "Medium",
            "longest_unique_substring(text)",
            "Return the length of the longest substring without repeating characters.",
            "Use a sliding window with the latest index of each character.",
            """
            def longest_unique_substring(text):
                seen = {}
                left = 0
                best = 0

                for right, char in enumerate(text):
                    if char in seen and seen[char] >= left:
                        left = seen[char] + 1
                    seen[char] = right
                    best = max(best, right - left + 1)

                return best
            """,
            tests=[
                {"args": ("abcabcbb",), "expected": 3},
                {"args": ("bbbbb",), "expected": 1},
                {"args": ("pwwkew",), "expected": 3},
            ],
            tags=["sliding-window", "strings"],
        ),
        _question(
            6,
            "Strings & Parsing",
            "Compress Runs",
            "Easy",
            "compress_runs(text)",
            "Run-length encode a string such as `aaabbc` into `a3b2c1`.",
            "Track the current character and flush its count when it changes.",
            """
            def compress_runs(text):
                if not text:
                    return ""

                parts = []
                current = text[0]
                count = 1

                for char in text[1:]:
                    if char == current:
                        count += 1
                    else:
                        parts.append(f"{current}{count}")
                        current = char
                        count = 1

                parts.append(f"{current}{count}")
                return "".join(parts)
            """,
            tests=[
                {"args": ("aaabbc",), "expected": "a3b2c1"},
                {"args": ("abcd",), "expected": "a1b1c1d1"},
                {"args": ("",), "expected": ""},
            ],
            tags=["strings", "encoding"],
        ),
        _question(
            7,
            "Sliding Window",
            "Maximum Sum Window",
            "Easy",
            "max_sum_window(nums, k)",
            "Return the largest sum of any contiguous window of length k. Return 0 when k is invalid.",
            "Keep a rolling sum instead of recomputing each window from scratch.",
            """
            def max_sum_window(nums, k):
                if k <= 0 or k > len(nums):
                    return 0

                window_sum = sum(nums[:k])
                best = window_sum

                for right in range(k, len(nums)):
                    window_sum += nums[right] - nums[right - k]
                    best = max(best, window_sum)

                return best
            """,
            tests=[
                {"args": ([2, 1, 5, 1, 3, 2], 3), "expected": 9},
                {"args": ([1, 2], 3), "expected": 0},
            ],
            tags=["sliding-window", "arrays"],
        ),
        _question(
            8,
            "Sliding Window",
            "Minimum Window Length",
            "Medium",
            "min_window_length(nums, target)",
            "Return the smallest length of a contiguous subarray whose sum is at least target. Return 0 if none exists.",
            "Expand the right edge, then shrink the left edge while the window still satisfies the target.",
            """
            def min_window_length(nums, target):
                left = 0
                window_sum = 0
                best = float("inf")

                for right, value in enumerate(nums):
                    window_sum += value
                    while window_sum >= target:
                        best = min(best, right - left + 1)
                        window_sum -= nums[left]
                        left += 1

                return 0 if best == float("inf") else best
            """,
            tests=[
                {"args": ([2, 3, 1, 2, 4, 3], 7), "expected": 2},
                {"args": ([1, 1, 1, 1], 10), "expected": 0},
            ],
            tags=["sliding-window", "prefix"],
        ),
        _question(
            9,
            "Sliding Window",
            "Sessionize Events",
            "Medium",
            "sessionize_events(timestamps, max_gap_seconds)",
            "Given sorted event timestamps in seconds, return a list containing the size of each session. "
            "A new session starts when the gap is greater than max_gap_seconds.",
            "Track the current session size and close it when the gap becomes too large.",
            """
            def sessionize_events(timestamps, max_gap_seconds):
                if not timestamps:
                    return []

                sessions = []
                current_size = 1

                for index in range(1, len(timestamps)):
                    if timestamps[index] - timestamps[index - 1] > max_gap_seconds:
                        sessions.append(current_size)
                        current_size = 1
                    else:
                        current_size += 1

                sessions.append(current_size)
                return sessions
            """,
            tests=[
                {"args": ([0, 10, 20, 100, 110, 300], 30), "expected": [3, 2, 1]},
                {"args": ([1, 2, 3], 10), "expected": [3]},
            ],
            tags=["sessions", "streaming", "windows"],
        ),
        _question(
            10,
            "Collections & Recursion",
            "Deduplicate While Preserving Order",
            "Easy",
            "dedupe_preserve_order(items)",
            "Return a list with duplicates removed while keeping the first occurrence order.",
            "A set tracks what you have seen; the output list preserves the order.",
            """
            def dedupe_preserve_order(items):
                seen = set()
                result = []

                for item in items:
                    if item in seen:
                        continue
                    seen.add(item)
                    result.append(item)

                return result
            """,
            tests=[
                {"args": ([3, 1, 3, 2, 1, 4],), "expected": [3, 1, 2, 4]},
                {"args": (["a", "a", "b"],), "expected": ["a", "b"]},
            ],
            tags=["sets", "arrays"],
        ),
        _question(
            11,
            "Collections & Recursion",
            "Balanced Brackets",
            "Easy",
            "is_balanced_brackets(text)",
            "Return True when brackets `()[]{}` are balanced and properly nested.",
            "This is a classic stack problem.",
            """
            def is_balanced_brackets(text):
                pairs = {")": "(", "]": "[", "}": "{"}
                stack = []

                for char in text:
                    if char in pairs.values():
                        stack.append(char)
                    elif char in pairs:
                        if not stack or stack.pop() != pairs[char]:
                            return False

                return not stack
            """,
            tests=[
                {"args": ("([]{})",), "expected": True},
                {"args": ("([)]",), "expected": False},
                {"args": ("(()",), "expected": False},
            ],
            tags=["stack", "strings"],
        ),
        _question(
            12,
            "Collections & Recursion",
            "Flatten Nested Dictionary",
            "Medium",
            "flatten_nested_dict(payload, parent_key='')",
            "Flatten a nested dictionary using dot notation, such as `{'a': {'b': 1}} -> {'a.b': 1}`.",
            "Use recursion and carry the accumulated path into each deeper level.",
            """
            def flatten_nested_dict(payload, parent_key=""):
                result = {}

                for key, value in payload.items():
                    full_key = f"{parent_key}.{key}" if parent_key else key
                    if isinstance(value, dict):
                        result.update(flatten_nested_dict(value, full_key))
                    else:
                        result[full_key] = value

                return result
            """,
            tests=[
                {
                    "args": ({"order": {"id": 1, "meta": {"region": "us"}}},),
                    "expected": {"order.id": 1, "order.meta.region": "us"},
                },
                {
                    "args": ({"a": 1, "b": {"c": 2, "d": 3}},),
                    "expected": {"a": 1, "b.c": 2, "b.d": 3},
                },
            ],
            tags=["recursion", "json"],
        ),
        _question(
            13,
            "Files & JSON",
            "Summarize CSV File",
            "Easy",
            "summarize_csv_file(path)",
            "Read a CSV file with columns `user_id` and `amount`, then return "
            "`{'rows': ..., 'total_amount': ..., 'unique_users': ...}`.",
            "Use csv.DictReader and accumulate totals as you scan the file once.",
            """
            import csv

            def summarize_csv_file(path):
                rows = 0
                total_amount = 0.0
                users = set()

                with open(path, "r", newline="") as file_obj:
                    reader = csv.DictReader(file_obj)
                    for row in reader:
                        rows += 1
                        total_amount += float(row["amount"])
                        users.add(row["user_id"])

                return {
                    "rows": rows,
                    "total_amount": round(total_amount, 2),
                    "unique_users": len(users),
                }
            """,
            tests=[
                {
                    "files": {"input.csv": "user_id,amount\nu1,10\nu2,15.5\nu1,4.5\n"},
                    "args": ("__TMP__/input.csv",),
                    "expected": {"rows": 3, "total_amount": 30.0, "unique_users": 2},
                },
                {
                    "files": {"input.csv": "user_id,amount\n"},
                    "args": ("__TMP__/input.csv",),
                    "expected": {"rows": 0, "total_amount": 0.0, "unique_users": 0},
                },
            ],
            tags=["csv", "files", "io"],
        ),
        _question(
            14,
            "Files & JSON",
            "Merge JSONL Files",
            "Medium",
            "merge_jsonl_files(paths)",
            "Read multiple JSONL files. Merge records by `id` with last-write-wins semantics and return the final list sorted by id.",
            "Store the latest record for each id in a dictionary, then sort the values at the end.",
            """
            import json

            def merge_jsonl_files(paths):
                latest = {}

                for path in paths:
                    with open(path, "r") as file_obj:
                        for line in file_obj:
                            line = line.strip()
                            if not line:
                                continue
                            record = json.loads(line)
                            latest[record["id"]] = record

                return [latest[key] for key in sorted(latest)]
            """,
            tests=[
                {
                    "files": {
                        "a.jsonl": '{"id": 1, "value": "old"}\n{"id": 2, "value": "keep"}\n',
                        "b.jsonl": '{"id": 1, "value": "new"}\n{"id": 3, "value": "add"}\n',
                    },
                    "args": (["__TMP__/a.jsonl", "__TMP__/b.jsonl"],),
                    "expected": [
                        {"id": 1, "value": "new"},
                        {"id": 2, "value": "keep"},
                        {"id": 3, "value": "add"},
                    ],
                }
            ],
            tags=["jsonl", "files", "dedupe"],
        ),
        _question(
            15,
            "Files & JSON",
            "Clean And Write JSON",
            "Medium",
            "clean_and_write_json(input_path, output_path)",
            "Read a JSON array of records. Keep rows whose `name` is non-empty, trim the name, write the cleaned rows to output_path, and return the count.",
            "Filter first, normalize the `name` field, then write the cleaned collection back out.",
            """
            import json

            def clean_and_write_json(input_path, output_path):
                with open(input_path, "r") as file_obj:
                    records = json.load(file_obj)

                cleaned = []
                for record in records:
                    name = str(record.get("name", "")).strip()
                    if not name:
                        continue
                    updated = dict(record)
                    updated["name"] = name
                    cleaned.append(updated)

                with open(output_path, "w") as file_obj:
                    json.dump(cleaned, file_obj, indent=2, sort_keys=True)

                return len(cleaned)
            """,
            tests=[
                {
                    "files": {
                        "input.json": [
                            {"id": 1, "name": " Alice "},
                            {"id": 2, "name": ""},
                            {"id": 3, "name": "Bob"},
                        ]
                    },
                    "args": ("__TMP__/input.json", "__TMP__/output.json"),
                    "expected": 2,
                    "expected_files": {
                        "output.json": [
                            {"id": 1, "name": "Alice"},
                            {"id": 3, "name": "Bob"},
                        ]
                    },
                }
            ],
            tags=["json", "write-files", "cleaning"],
        ),
        _question(
            16,
            "Data Pipelines",
            "Build Retry Schedule",
            "Easy",
            "build_retry_schedule(base_delay, retries, multiplier=2)",
            "Return the retry delays for an exponential backoff schedule.",
            "Start from the base delay and multiply after each retry.",
            """
            def build_retry_schedule(base_delay, retries, multiplier=2):
                delays = []
                current = base_delay
                for _ in range(retries):
                    delays.append(current)
                    current *= multiplier
                return delays
            """,
            tests=[
                {"args": (5, 4), "expected": [5, 10, 20, 40]},
                {"args": (2, 3, 3), "expected": [2, 6, 18]},
            ],
            tags=["backoff", "pipelines"],
        ),
        _question(
            17,
            "Data Pipelines",
            "Batch Records By Size",
            "Medium",
            "batch_records_by_size(records, max_bytes)",
            "Group records into sequential batches so the JSON-encoded size of each batch stays within max_bytes.",
            "Measure each record with json.dumps(..., sort_keys=True) and flush the current batch before it would overflow.",
            """
            import json

            def batch_records_by_size(records, max_bytes):
                batches = []
                current_batch = []
                current_size = 0

                for record in records:
                    record_size = len(json.dumps(record, sort_keys=True))
                    if current_batch and current_size + record_size > max_bytes:
                        batches.append(current_batch)
                        current_batch = []
                        current_size = 0

                    current_batch.append(record)
                    current_size += record_size

                if current_batch:
                    batches.append(current_batch)

                return batches
            """,
            tests=[
                {
                    "args": (
                        [{"id": 1, "v": "aa"}, {"id": 2, "v": "bbb"}, {"id": 3, "v": "cccc"}],
                        44,
                    ),
                    "expected": [
                        [{"id": 1, "v": "aa"}, {"id": 2, "v": "bbb"}],
                        [{"id": 3, "v": "cccc"}],
                    ],
                },
                {
                    "args": ([{"id": 1, "v": "x"}, {"id": 2, "v": "y"}], 80),
                    "expected": [[{"id": 1, "v": "x"}, {"id": 2, "v": "y"}]],
                },
            ],
            tags=["batching", "json", "pipelines"],
        ),
        _question(
            18,
            "Data Pipelines",
            "Apply CDC Events",
            "Medium",
            "apply_cdc_events(snapshot, events)",
            "Apply insert, update, and delete CDC events to a current snapshot. "
            "Return the resulting rows sorted by id.",
            "Load the snapshot into a dictionary keyed by id, then mutate it with each CDC event.",
            """
            def apply_cdc_events(snapshot, events):
                state = {row["id"]: dict(row) for row in snapshot}

                for event in events:
                    event_id = event["id"]
                    op = event["op"]

                    if op == "D":
                        state.pop(event_id, None)
                        continue

                    if op == "I":
                        state[event_id] = {"id": event_id, **event["after"]}
                    elif op == "U" and event_id in state:
                        state[event_id].update(event["after"])

                return [state[key] for key in sorted(state)]
            """,
            tests=[
                {
                    "args": (
                        [{"id": 1, "status": "new"}, {"id": 2, "status": "paid"}],
                        [
                            {"id": 1, "op": "U", "after": {"status": "shipped"}},
                            {"id": 3, "op": "I", "after": {"status": "new"}},
                            {"id": 2, "op": "D", "after": {}},
                        ],
                    ),
                    "expected": [{"id": 1, "status": "shipped"}, {"id": 3, "status": "new"}],
                }
            ],
            tags=["cdc", "merge", "etl"],
        ),
        _question(
            19,
            "Cloud & APIs",
            "Parse SQS Event",
            "Easy",
            "parse_sqs_event(event)",
            "Decode a Lambda-style SQS event whose `body` field contains JSON strings. Return the parsed bodies.",
            "Iterate over `Records` and json.loads each body.",
            """
            import json

            def parse_sqs_event(event):
                records = event.get("Records", [])
                return [json.loads(record["body"]) for record in records]
            """,
            tests=[
                {
                    "args": (
                        {
                            "Records": [
                                {"body": '{"id": 1, "status": "ok"}'},
                                {"body": '{"id": 2, "status": "retry"}'},
                            ]
                        },
                    ),
                    "expected": [{"id": 1, "status": "ok"}, {"id": 2, "status": "retry"}],
                }
            ],
            tags=["aws", "lambda", "json"],
        ),
        _question(
            20,
            "Cloud & APIs",
            "Build S3 Partition Path",
            "Easy",
            "build_s3_partition_path(base_path, event_ts, region)",
            "Build an S3-style partition path ending with `region=.../dt=YYYY-MM-DD/hour=HH/`.",
            "Parse the ISO timestamp and assemble the path carefully after trimming any trailing slash.",
            """
            from datetime import datetime

            def build_s3_partition_path(base_path, event_ts, region):
                parsed = datetime.fromisoformat(event_ts.replace("Z", "+00:00"))
                base = base_path.rstrip("/")
                return (
                    f"{base}/region={region}/dt={parsed:%Y-%m-%d}/hour={parsed:%H}/"
                )
            """,
            tests=[
                {
                    "args": ("s3://bucket/events", "2024-03-01T09:15:00Z", "apac"),
                    "expected": "s3://bucket/events/region=apac/dt=2024-03-01/hour=09/",
                },
                {
                    "args": ("s3://bucket/events/", "2024-03-01T23:59:00Z", "us"),
                    "expected": "s3://bucket/events/region=us/dt=2024-03-01/hour=23/",
                },
            ],
            tags=["aws", "s3", "partitions"],
        ),
        _question(
            21,
            "Cloud & APIs",
            "Estimate Kinesis Shards",
            "Medium",
            "estimate_kinesis_shards(records_per_second, avg_record_kb, headroom=1.2)",
            "Estimate the number of Kinesis shards needed using both throughput (1 MB/sec) and record rate (1000 records/sec) limits.",
            "Compute both constraints with headroom, then take the ceiling of the larger one.",
            """
            import math

            def estimate_kinesis_shards(records_per_second, avg_record_kb, headroom=1.2):
                throughput_shards = (records_per_second * avg_record_kb / 1024) * headroom
                record_shards = (records_per_second / 1000) * headroom
                return math.ceil(max(throughput_shards, record_shards))
            """,
            tests=[
                {"args": (1500, 0.5), "expected": 2},
                {"args": (4000, 1.0), "expected": 5},
            ],
            tags=["aws", "sizing", "throughput"],
        ),
        _question(
            22,
            "Pandas & NumPy",
            "Latest Record Per Entity",
            "Medium",
            "latest_record_per_entity(df)",
            "Given a DataFrame with `entity_id`, `updated_at`, and `value`, keep only the latest row per entity_id and return the result sorted by entity_id.",
            "Convert the timestamp column, sort by entity and timestamp, then take the last row of each group.",
            """
            import pandas as pd

            def latest_record_per_entity(df):
                result = df.copy()
                result["updated_at"] = pd.to_datetime(result["updated_at"])
                result = result.sort_values(["entity_id", "updated_at"])
                result = result.groupby("entity_id", as_index=False).tail(1)
                return result.sort_values("entity_id").reset_index(drop=True)
            """,
            tests=[
                {
                    "args": (
                        pd.DataFrame(
                            [
                                {"entity_id": 1, "updated_at": "2024-01-01 10:00", "value": 10},
                                {"entity_id": 1, "updated_at": "2024-01-01 11:00", "value": 12},
                                {"entity_id": 2, "updated_at": "2024-01-01 09:00", "value": 7},
                            ]
                        ),
                    ),
                    "expected": pd.DataFrame(
                        [
                            {"entity_id": 1, "updated_at": "2024-01-01 11:00:00", "value": 12},
                            {"entity_id": 2, "updated_at": "2024-01-01 09:00:00", "value": 7},
                        ]
                    ),
                    "sort_by": ["entity_id"],
                }
            ],
            tags=["pandas", "dedupe", "latest-record"],
        ),
        _question(
            23,
            "Pandas & NumPy",
            "Hourly Event Counts",
            "Easy",
            "hourly_event_counts(df)",
            "Aggregate a DataFrame with `event_ts` and `device_id` into hourly counts per device.",
            "Floor the timestamp to the hour, then group by hour and device_id.",
            """
            import pandas as pd

            def hourly_event_counts(df):
                result = df.copy()
                result["event_ts"] = pd.to_datetime(result["event_ts"])
                result["hour"] = result["event_ts"].dt.floor("h")
                result = (
                    result.groupby(["hour", "device_id"], as_index=False)
                    .size()
                    .rename(columns={"size": "event_count"})
                )
                return result.sort_values(["hour", "device_id"]).reset_index(drop=True)
            """,
            tests=[
                {
                    "args": (
                        pd.DataFrame(
                            [
                                {"event_ts": "2024-01-01 10:01:00", "device_id": "d1"},
                                {"event_ts": "2024-01-01 10:20:00", "device_id": "d1"},
                                {"event_ts": "2024-01-01 11:00:00", "device_id": "d2"},
                            ]
                        ),
                    ),
                    "expected": pd.DataFrame(
                        [
                            {"hour": "2024-01-01 10:00:00", "device_id": "d1", "event_count": 2},
                            {"hour": "2024-01-01 11:00:00", "device_id": "d2", "event_count": 1},
                        ]
                    ),
                    "sort_by": ["hour", "device_id"],
                }
            ],
            tags=["pandas", "groupby", "time-series"],
        ),
        _question(
            24,
            "Pandas & NumPy",
            "Fill Missing Metrics By Group",
            "Medium",
            "fill_missing_metrics(df)",
            "Sort by group and ts, then forward-fill the metric column within each group.",
            "Group by the partition key and use ffill after sorting.",
            """
            import pandas as pd

            def fill_missing_metrics(df):
                result = df.copy()
                result["ts"] = pd.to_datetime(result["ts"])
                result = result.sort_values(["group", "ts"])
                result["metric"] = result.groupby("group")["metric"].ffill()
                return result.reset_index(drop=True)
            """,
            tests=[
                {
                    "args": (
                        pd.DataFrame(
                            [
                                {"group": "a", "ts": "2024-01-01 10:00:00", "metric": 1.0},
                                {"group": "a", "ts": "2024-01-01 11:00:00", "metric": None},
                                {"group": "b", "ts": "2024-01-01 10:00:00", "metric": None},
                                {"group": "b", "ts": "2024-01-01 12:00:00", "metric": 5.0},
                            ]
                        ),
                    ),
                    "expected": pd.DataFrame(
                        [
                            {"group": "a", "ts": "2024-01-01 10:00:00", "metric": 1.0},
                            {"group": "a", "ts": "2024-01-01 11:00:00", "metric": 1.0},
                            {"group": "b", "ts": "2024-01-01 10:00:00", "metric": None},
                            {"group": "b", "ts": "2024-01-01 12:00:00", "metric": 5.0},
                        ]
                    ),
                    "sort_by": ["group", "ts"],
                }
            ],
            tags=["pandas", "ffill", "data-cleaning"],
        ),
        _question(
            25,
            "Pandas & NumPy",
            "Moving Average Window",
            "Easy",
            "moving_average(values, window)",
            "Return the moving average for each complete window. Round each value to 4 decimal places.",
            "Use a rolling sum and subtract the element leaving the window.",
            """
            def moving_average(values, window):
                if window <= 0 or window > len(values):
                    return []

                result = []
                rolling_sum = sum(values[:window])
                result.append(round(rolling_sum / window, 4))

                for index in range(window, len(values)):
                    rolling_sum += values[index] - values[index - window]
                    result.append(round(rolling_sum / window, 4))

                return result
            """,
            tests=[
                {"args": ([1, 2, 3, 4, 5], 3), "expected": [2.0, 3.0, 4.0]},
                {"args": ([10, 20], 3), "expected": []},
            ],
            tags=["numpy-style", "windows"],
        ),
        _question(
            26,
            "Pandas & NumPy",
            "Detect Outlier Indices",
            "Medium",
            "detect_outlier_indices(values, threshold=2.0)",
            "Return the indices whose absolute z-score is at least threshold. Use population standard deviation.",
            "Compute the mean and standard deviation first, then scan for large z-scores.",
            """
            import math

            def detect_outlier_indices(values, threshold=2.0):
                if not values:
                    return []

                mean = sum(values) / len(values)
                variance = sum((value - mean) ** 2 for value in values) / len(values)
                std = math.sqrt(variance)

                if std == 0:
                    return []

                result = []
                for index, value in enumerate(values):
                    z_score = abs((value - mean) / std)
                    if z_score >= threshold:
                        result.append(index)

                return result
            """,
            tests=[
                {"args": ([10, 11, 9, 10, 100], 1.9), "expected": [4]},
                {"args": ([5, 5, 5],), "expected": []},
            ],
            tags=["analytics", "statistics", "numpy-style"],
        ),
        _question(
            27,
            "Interview Patterns",
            "Merge Intervals",
            "Medium",
            "merge_intervals(intervals)",
            "Merge overlapping intervals and return them sorted by start time.",
            "Sort first, then merge against the last interval in the result.",
            """
            def merge_intervals(intervals):
                if not intervals:
                    return []

                intervals = sorted(intervals)
                merged = [intervals[0][:]]

                for start, end in intervals[1:]:
                    last = merged[-1]
                    if start <= last[1]:
                        last[1] = max(last[1], end)
                    else:
                        merged.append([start, end])

                return merged
            """,
            tests=[
                {"args": ([[1, 3], [2, 6], [8, 10], [9, 12]],), "expected": [[1, 6], [8, 12]]},
                {"args": ([[1, 2]],), "expected": [[1, 2]]},
            ],
            tags=["intervals", "sorting"],
        ),
        _question(
            28,
            "Interview Patterns",
            "Group Anagrams",
            "Medium",
            "group_anagrams(words)",
            "Group anagrams together. Sort the words inside each group and sort groups by their first element.",
            "The sorted character signature is the natural hashmap key.",
            """
            from collections import defaultdict

            def group_anagrams(words):
                groups = defaultdict(list)
                for word in words:
                    groups["".join(sorted(word))].append(word)

                result = [sorted(group) for group in groups.values()]
                return sorted(result, key=lambda group: group[0])
            """,
            tests=[
                {
                    "args": (["eat", "tea", "tan", "ate", "nat", "bat"],),
                    "expected": [["ate", "eat", "tea"], ["bat"], ["nat", "tan"]],
                }
            ],
            tags=["hashmap", "strings"],
        ),
        _question(
            29,
            "Interview Patterns",
            "Freshness Summary",
            "Easy",
            "freshness_summary(events, now_ts, threshold_minutes)",
            "Given event timestamps in ISO format, return a summary with total, fresh, stale, and max_lag_minutes.",
            "Convert everything to datetimes and compare each event age with the freshness threshold.",
            """
            from datetime import datetime

            def freshness_summary(events, now_ts, threshold_minutes):
                now = datetime.fromisoformat(now_ts.replace("Z", "+00:00"))
                fresh = 0
                stale = 0
                max_lag_minutes = 0

                for event_ts in events:
                    event_time = datetime.fromisoformat(event_ts.replace("Z", "+00:00"))
                    lag_minutes = int((now - event_time).total_seconds() // 60)
                    max_lag_minutes = max(max_lag_minutes, lag_minutes)
                    if lag_minutes <= threshold_minutes:
                        fresh += 1
                    else:
                        stale += 1

                return {
                    "total": len(events),
                    "fresh": fresh,
                    "stale": stale,
                    "max_lag_minutes": max_lag_minutes,
                }
            """,
            tests=[
                {
                    "args": (
                        ["2024-01-01T10:55:00Z", "2024-01-01T10:40:00Z"],
                        "2024-01-01T11:00:00Z",
                        10,
                    ),
                    "expected": {"total": 2, "fresh": 1, "stale": 1, "max_lag_minutes": 20},
                }
            ],
            tags=["sla", "freshness", "monitoring"],
        ),
        _question(
            30,
            "Interview Patterns",
            "Validate Schema Evolution",
            "Medium",
            "validate_schema_evolution(old_schema, new_schema)",
            "Return a sorted list of compatibility issues. Report removed columns, type changes, and new non-nullable columns. "
            "Return `['compatible']` when there are no issues.",
            "Index the old and new schemas by column name so you can compare fields directly.",
            """
            def validate_schema_evolution(old_schema, new_schema):
                old_index = {field["name"]: field for field in old_schema}
                new_index = {field["name"]: field for field in new_schema}
                issues = []

                for name, old_field in old_index.items():
                    if name not in new_index:
                        issues.append(f"removed:{name}")
                        continue

                    new_field = new_index[name]
                    if old_field["type"] != new_field["type"]:
                        issues.append(f"type_changed:{name}")
                    if old_field.get("nullable", True) and not new_field.get("nullable", True):
                        issues.append(f"tightened_nullability:{name}")

                for name, new_field in new_index.items():
                    if name not in old_index and not new_field.get("nullable", True):
                        issues.append(f"new_required:{name}")

                return sorted(issues) or ["compatible"]
            """,
            tests=[
                {
                    "args": (
                        [
                            {"name": "id", "type": "int", "nullable": False},
                            {"name": "status", "type": "string", "nullable": True},
                        ],
                        [
                            {"name": "id", "type": "int", "nullable": False},
                            {"name": "status", "type": "string", "nullable": False},
                            {"name": "region", "type": "string", "nullable": False},
                        ],
                    ),
                    "expected": ["new_required:region", "tightened_nullability:status"],
                },
                {
                    "args": (
                        [{"name": "id", "type": "int", "nullable": False}],
                        [{"name": "id", "type": "int", "nullable": False}],
                    ),
                    "expected": ["compatible"],
                },
            ],
            tags=["schema", "compatibility", "data-engineering"],
        ),
    ]
    return questions + get_additional_python_questions()


def get_additional_python_questions():
    return [
        _question(
            31,
            "Arrays & Hashing",
            "Contains Duplicate Within K",
            "Easy",
            "contains_duplicate_within_k(nums, k)",
            "Return True if the same value appears again within k indices, otherwise return False.",
            "Track the latest index for each value and compare the current index against it.",
            """
            def contains_duplicate_within_k(nums, k):
                latest = {}
                for index, value in enumerate(nums):
                    if value in latest and index - latest[value] <= k:
                        return True
                    latest[value] = index
                return False
            """,
            tests=[
                {"args": ([1, 2, 3, 1], 3), "expected": True},
                {"args": ([1, 2, 3, 1, 2, 3], 2), "expected": False},
            ],
            tags=["hashmap", "arrays", "duplicates"],
        ),
        _question(
            32,
            "Arrays & Hashing",
            "Longest Consecutive Span",
            "Medium",
            "longest_consecutive_span(nums)",
            "Return the length of the longest consecutive integer sequence in the array.",
            "Use a set and only start counting from values that do not have a predecessor.",
            """
            def longest_consecutive_span(nums):
                values = set(nums)
                best = 0

                for value in values:
                    if value - 1 in values:
                        continue

                    length = 1
                    current = value
                    while current + 1 in values:
                        current += 1
                        length += 1

                    best = max(best, length)

                return best
            """,
            tests=[
                {"args": ([100, 4, 200, 1, 3, 2],), "expected": 4},
                {"args": ([0, 3, 7, 2, 5, 8, 4, 6, 0, 1],), "expected": 9},
            ],
            tags=["hashmap", "arrays", "sequence"],
        ),
        _question(
            33,
            "Arrays & Hashing",
            "Majority Element",
            "Easy",
            "majority_element(nums)",
            "Return the element that appears more than half the time in the input list.",
            "Boyer-Moore majority vote gives a clean linear-time answer.",
            """
            def majority_element(nums):
                candidate = None
                count = 0

                for value in nums:
                    if count == 0:
                        candidate = value
                    count += 1 if value == candidate else -1

                return candidate
            """,
            tests=[
                {"args": ([3, 2, 3],), "expected": 3},
                {"args": ([2, 2, 1, 1, 1, 2, 2],), "expected": 2},
            ],
            tags=["arrays", "voting", "interview-basics"],
        ),
        _question(
            34,
            "Strings & Parsing",
            "Valid Palindrome After Cleanup",
            "Easy",
            "is_valid_palindrome(text)",
            "Ignore non-alphanumeric characters and letter casing, then return whether the cleaned string is a palindrome.",
            "Two pointers work well after filtering the relevant characters.",
            """
            def is_valid_palindrome(text):
                cleaned = [char.lower() for char in text if char.isalnum()]
                left, right = 0, len(cleaned) - 1

                while left < right:
                    if cleaned[left] != cleaned[right]:
                        return False
                    left += 1
                    right -= 1

                return True
            """,
            tests=[
                {"args": ("A man, a plan, a canal: Panama",), "expected": True},
                {"args": ("race a car",), "expected": False},
            ],
            tags=["strings", "two-pointers"],
        ),
        _question(
            35,
            "Strings & Parsing",
            "Normalize Email Address",
            "Easy",
            "normalize_email_address(email)",
            "Normalize an email by trimming spaces, lowercasing it, and removing any `+suffix` before the `@` symbol.",
            "Split local and domain parts first, then clean only the local side before rebuilding.",
            """
            def normalize_email_address(email):
                email = email.strip().lower()
                local, domain = email.split("@", 1)
                local = local.split("+", 1)[0]
                return f"{local}@{domain}"
            """,
            tests=[
                {"args": ("  Alice+promo@Example.com ",), "expected": "alice@example.com"},
                {"args": ("bob@test.io",), "expected": "bob@test.io"},
            ],
            tags=["strings", "parsing", "cleanup"],
        ),
        _question(
            36,
            "Strings & Parsing",
            "Parse Key Value Payload",
            "Medium",
            "parse_key_value_payload(payload)",
            "Parse a semicolon-delimited payload like `a=1;b=2;c=3` into a dictionary. Skip malformed segments.",
            "Split on semicolons first, then keep only segments that still contain one equals sign.",
            """
            def parse_key_value_payload(payload):
                result = {}
                for segment in payload.split(";"):
                    if "=" not in segment:
                        continue
                    key, value = segment.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if key:
                        result[key] = value
                return result
            """,
            tests=[
                {"args": ("a=1;b=2;c=3",), "expected": {"a": "1", "b": "2", "c": "3"}},
                {"args": ("region=us;bad;env=prod",), "expected": {"region": "us", "env": "prod"}},
            ],
            tags=["strings", "parsing", "logs"],
        ),
        _question(
            37,
            "Sliding Window",
            "Longest Ones After Flips",
            "Medium",
            "longest_ones_after_flips(nums, k)",
            "You may flip at most k zeroes to ones. Return the maximum length of a contiguous block of ones you can achieve.",
            "Use a sliding window and count how many zeroes are currently inside it.",
            """
            def longest_ones_after_flips(nums, k):
                left = 0
                zeroes = 0
                best = 0

                for right, value in enumerate(nums):
                    if value == 0:
                        zeroes += 1
                    while zeroes > k:
                        if nums[left] == 0:
                            zeroes -= 1
                        left += 1
                    best = max(best, right - left + 1)

                return best
            """,
            tests=[
                {"args": ([1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 0], 2), "expected": 6},
                {"args": ([0, 0, 1, 1, 1, 0, 0], 0), "expected": 3},
            ],
            tags=["sliding-window", "arrays", "binary"],
        ),
        _question(
            38,
            "Sliding Window",
            "Max Vowels In Window",
            "Easy",
            "max_vowels_in_window(text, k)",
            "Return the maximum number of vowels found in any substring of length k.",
            "Track the current vowel count as the window moves forward.",
            """
            def max_vowels_in_window(text, k):
                vowels = set("aeiou")
                current = sum(1 for char in text[:k] if char in vowels)
                best = current

                for index in range(k, len(text)):
                    if text[index] in vowels:
                        current += 1
                    if text[index - k] in vowels:
                        current -= 1
                    best = max(best, current)

                return best
            """,
            tests=[
                {"args": ("abciiidef", 3), "expected": 3},
                {"args": ("aeiou", 2), "expected": 2},
            ],
            tags=["sliding-window", "strings"],
        ),
        _question(
            39,
            "Sliding Window",
            "Count Distinct In Windows",
            "Medium",
            "count_distinct_in_windows(nums, k)",
            "Return a list containing the number of distinct values in every window of size k.",
            "Maintain a frequency dictionary and remove keys when their count drops to zero.",
            """
            def count_distinct_in_windows(nums, k):
                if k <= 0 or k > len(nums):
                    return []

                counts = {}
                result = []

                for index, value in enumerate(nums):
                    counts[value] = counts.get(value, 0) + 1

                    if index >= k:
                        old = nums[index - k]
                        counts[old] -= 1
                        if counts[old] == 0:
                            del counts[old]

                    if index >= k - 1:
                        result.append(len(counts))

                return result
            """,
            tests=[
                {"args": ([1, 2, 1, 3, 4, 2, 3], 4), "expected": [3, 4, 4, 3]},
                {"args": ([1, 1, 1], 2), "expected": [1, 1]},
            ],
            tags=["sliding-window", "hashmap"],
        ),
        _question(
            40,
            "Collections & Recursion",
            "Evaluate Reverse Polish Notation",
            "Medium",
            "evaluate_rpn(tokens)",
            "Evaluate an expression written in Reverse Polish Notation and return the integer result.",
            "Use a stack. When you see an operator, pop the last two values and push the result.",
            """
            def evaluate_rpn(tokens):
                stack = []

                for token in tokens:
                    if token not in {"+", "-", "*", "/"}:
                        stack.append(int(token))
                        continue

                    right = stack.pop()
                    left = stack.pop()

                    if token == "+":
                        stack.append(left + right)
                    elif token == "-":
                        stack.append(left - right)
                    elif token == "*":
                        stack.append(left * right)
                    else:
                        stack.append(int(left / right))

                return stack[-1]
            """,
            tests=[
                {"args": (["2", "1", "+", "3", "*"],), "expected": 9},
                {"args": (["4", "13", "5", "/", "+"],), "expected": 6},
            ],
            tags=["stack", "math", "interview"],
        ),
        _question(
            41,
            "Collections & Recursion",
            "Max Nested Depth",
            "Medium",
            "max_nested_depth(payload)",
            "Given a nested dictionary or list structure, return the maximum nesting depth. Scalars have depth 0.",
            "Use recursion and add one level whenever you step into a list or dictionary.",
            """
            def max_nested_depth(payload):
                if isinstance(payload, dict):
                    if not payload:
                        return 1
                    return 1 + max(max_nested_depth(value) for value in payload.values())
                if isinstance(payload, list):
                    if not payload:
                        return 1
                    return 1 + max(max_nested_depth(value) for value in payload)
                return 0
            """,
            tests=[
                {"args": ({"a": {"b": {"c": 1}}},), "expected": 3},
                {"args": ([1, [2, [3]]],), "expected": 3},
            ],
            tags=["recursion", "json"],
        ),
        _question(
            42,
            "Collections & Recursion",
            "Merge Sorted Streams",
            "Easy",
            "merge_sorted_streams(left_stream, right_stream)",
            "Merge two sorted lists into one sorted list.",
            "Walk both lists with two pointers and append the smaller current value each time.",
            """
            def merge_sorted_streams(left_stream, right_stream):
                left = right = 0
                result = []

                while left < len(left_stream) and right < len(right_stream):
                    if left_stream[left] <= right_stream[right]:
                        result.append(left_stream[left])
                        left += 1
                    else:
                        result.append(right_stream[right])
                        right += 1

                result.extend(left_stream[left:])
                result.extend(right_stream[right:])
                return result
            """,
            tests=[
                {"args": ([1, 3, 5], [2, 4, 6]), "expected": [1, 2, 3, 4, 5, 6]},
                {"args": ([], [1, 2]), "expected": [1, 2]},
            ],
            tags=["merge", "arrays", "pointers"],
        ),
        _question(
            43,
            "Files & JSON",
            "Find Failed Jobs In JSONL",
            "Easy",
            "find_failed_jobs(path)",
            "Read a JSONL file of job runs and return the sorted list of `job_id` values whose status is `FAILED`.",
            "Read the file line by line and collect only the failed records.",
            """
            import json

            def find_failed_jobs(path):
                failed = []
                with open(path, "r") as file_obj:
                    for line in file_obj:
                        line = line.strip()
                        if not line:
                            continue
                        record = json.loads(line)
                        if record.get("status") == "FAILED":
                            failed.append(record["job_id"])
                return sorted(failed)
            """,
            tests=[
                {
                    "files": {
                        "jobs.jsonl": '{"job_id": "a", "status": "SUCCESS"}\n{"job_id": "b", "status": "FAILED"}\n{"job_id": "c", "status": "FAILED"}\n'
                    },
                    "args": ("__TMP__/jobs.jsonl",),
                    "expected": ["b", "c"],
                }
            ],
            tags=["files", "jsonl", "monitoring"],
        ),
        _question(
            44,
            "Files & JSON",
            "Append JSONL Record",
            "Easy",
            "append_jsonl_record(path, record)",
            "Append one JSON record to a JSONL file and return the new line count.",
            "Write the record as one line of JSON, then count how many non-empty lines the file contains.",
            """
            import json

            def append_jsonl_record(path, record):
                with open(path, "a") as file_obj:
                    file_obj.write(json.dumps(record, sort_keys=True) + "\\n")

                with open(path, "r") as file_obj:
                    return sum(1 for line in file_obj if line.strip())
            """,
            tests=[
                {
                    "files": {"records.jsonl": '{"id": 1}\n'},
                    "args": ("__TMP__/records.jsonl", {"id": 2}),
                    "expected": 2,
                }
            ],
            tags=["files", "jsonl", "write-files"],
        ),
        _question(
            45,
            "Files & JSON",
            "Build Partition Manifest",
            "Medium",
            "build_partition_manifest(paths)",
            "Given a list of partitioned file paths like `s3://bucket/dt=2024-01-01/hour=10/file.parquet`, "
            "return a dictionary counting how many files belong to each `dt=.../hour=...` partition.",
            "Extract the dt and hour segments from each path and count them with a dictionary.",
            """
            def build_partition_manifest(paths):
                manifest = {}
                for path in paths:
                    parts = path.split("/")
                    dt = next(part for part in parts if part.startswith("dt="))
                    hour = next(part for part in parts if part.startswith("hour="))
                    key = f"{dt}/{hour}"
                    manifest[key] = manifest.get(key, 0) + 1
                return manifest
            """,
            tests=[
                {
                    "args": (
                        [
                            "s3://bucket/dt=2024-01-01/hour=10/a.parquet",
                            "s3://bucket/dt=2024-01-01/hour=10/b.parquet",
                            "s3://bucket/dt=2024-01-01/hour=11/c.parquet",
                        ],
                    ),
                    "expected": {"dt=2024-01-01/hour=10": 2, "dt=2024-01-01/hour=11": 1},
                }
            ],
            tags=["files", "partitions", "s3"],
        ),
        _question(
            46,
            "Files & JSON",
            "Summarize Nested JSON Orders",
            "Medium",
            "summarize_nested_json_orders(path)",
            "Read a JSON file containing an array of orders with nested items. Return total_orders, total_items, and total_amount.",
            "Loop through each order and accumulate both order-level and nested-item metrics.",
            """
            import json

            def summarize_nested_json_orders(path):
                with open(path, "r") as file_obj:
                    orders = json.load(file_obj)

                total_items = 0
                total_amount = 0.0
                for order in orders:
                    items = order.get("items", [])
                    total_items += len(items)
                    for item in items:
                        total_amount += float(item.get("amount", 0))

                return {
                    "total_orders": len(orders),
                    "total_items": total_items,
                    "total_amount": round(total_amount, 2),
                }
            """,
            tests=[
                {
                    "files": {
                        "orders.json": [
                            {"id": 1, "items": [{"amount": 10}, {"amount": 5.5}]},
                            {"id": 2, "items": [{"amount": 3}]},
                        ]
                    },
                    "args": ("__TMP__/orders.json",),
                    "expected": {"total_orders": 2, "total_items": 3, "total_amount": 18.5},
                }
            ],
            tags=["json", "files", "nested-data"],
        ),
        _question(
            47,
            "Data Pipelines",
            "Deduplicate By Latest Timestamp",
            "Medium",
            "dedupe_by_latest_timestamp(records)",
            "Keep only the latest record per `id` based on `updated_at`. Return the surviving rows sorted by id.",
            "Store the best row per id and replace it only when a later timestamp appears.",
            """
            def dedupe_by_latest_timestamp(records):
                latest = {}
                for record in records:
                    record_id = record["id"]
                    if record_id not in latest or record["updated_at"] > latest[record_id]["updated_at"]:
                        latest[record_id] = dict(record)
                return [latest[key] for key in sorted(latest)]
            """,
            tests=[
                {
                    "args": (
                        [
                            {"id": 1, "updated_at": "2024-01-01T10:00:00", "value": 10},
                            {"id": 1, "updated_at": "2024-01-01T11:00:00", "value": 12},
                            {"id": 2, "updated_at": "2024-01-01T09:00:00", "value": 7},
                        ],
                    ),
                    "expected": [
                        {"id": 1, "updated_at": "2024-01-01T11:00:00", "value": 12},
                        {"id": 2, "updated_at": "2024-01-01T09:00:00", "value": 7},
                    ],
                }
            ],
            tags=["pipelines", "dedupe", "latest-record"],
        ),
        _question(
            48,
            "Data Pipelines",
            "Partition Records By Day",
            "Easy",
            "partition_records_by_day(records)",
            "Group records into a dictionary keyed by the `YYYY-MM-DD` day extracted from `event_ts`.",
            "Build the partition key from the first 10 characters of the timestamp.",
            """
            def partition_records_by_day(records):
                result = {}
                for record in records:
                    day = record["event_ts"][:10]
                    result.setdefault(day, []).append(record)
                return result
            """,
            tests=[
                {
                    "args": (
                        [
                            {"event_ts": "2024-01-01T10:00:00", "id": 1},
                            {"event_ts": "2024-01-01T11:00:00", "id": 2},
                            {"event_ts": "2024-01-02T09:00:00", "id": 3},
                        ],
                    ),
                    "expected": {
                        "2024-01-01": [
                            {"event_ts": "2024-01-01T10:00:00", "id": 1},
                            {"event_ts": "2024-01-01T11:00:00", "id": 2},
                        ],
                        "2024-01-02": [{"event_ts": "2024-01-02T09:00:00", "id": 3}],
                    },
                }
            ],
            tags=["pipelines", "partitioning", "etl"],
        ),
        _question(
            49,
            "Data Pipelines",
            "Compute Event Watermark",
            "Easy",
            "compute_event_watermark(events, allowed_lateness_minutes)",
            "Return the watermark timestamp, defined as the maximum event_ts minus the allowed lateness.",
            "Find the latest timestamp first, then subtract the lateness window.",
            """
            from datetime import datetime, timedelta

            def compute_event_watermark(events, allowed_lateness_minutes):
                latest = max(datetime.fromisoformat(event["event_ts"]) for event in events)
                watermark = latest - timedelta(minutes=allowed_lateness_minutes)
                return watermark.isoformat()
            """,
            tests=[
                {
                    "args": (
                        [
                            {"event_ts": "2024-01-01T10:00:00"},
                            {"event_ts": "2024-01-01T10:05:00"},
                        ],
                        2,
                    ),
                    "expected": "2024-01-01T10:03:00",
                }
            ],
            tags=["pipelines", "streaming", "watermark"],
        ),
        _question(
            50,
            "Data Pipelines",
            "Compact Small Files Plan",
            "Medium",
            "compact_small_files_plan(file_sizes_mb, target_size_mb)",
            "Given a list of file sizes, return how many compaction groups are needed if each group should stay under target_size_mb.",
            "Greedily fill the current group until the next file would exceed the target, then start a new group.",
            """
            def compact_small_files_plan(file_sizes_mb, target_size_mb):
                if not file_sizes_mb:
                    return 0

                groups = 1
                current = 0
                for size in file_sizes_mb:
                    if current and current + size > target_size_mb:
                        groups += 1
                        current = 0
                    current += size
                return groups
            """,
            tests=[
                {"args": ([50, 40, 30, 120], 128), "expected": 2},
                {"args": ([10, 10, 10], 64), "expected": 1},
            ],
            tags=["pipelines", "storage", "files"],
        ),
        _question(
            51,
            "Cloud & APIs",
            "Build Lambda Response",
            "Easy",
            "build_lambda_response(status_code, body)",
            "Return an AWS Lambda proxy-style response dictionary with a JSON body string and a content-type header.",
            "Serialize the body with json.dumps and include the standard JSON header.",
            """
            import json

            def build_lambda_response(status_code, body):
                return {
                    "statusCode": status_code,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps(body, sort_keys=True),
                }
            """,
            tests=[
                {
                    "args": (200, {"message": "ok"}),
                    "expected": {
                        "statusCode": 200,
                        "headers": {"Content-Type": "application/json"},
                        "body": '{"message": "ok"}',
                    },
                }
            ],
            tags=["aws", "lambda", "api"],
        ),
        _question(
            52,
            "Cloud & APIs",
            "Chunk S3 Keys",
            "Easy",
            "chunk_s3_keys(keys, batch_size)",
            "Split a list of S3 keys into sequential batches of size batch_size.",
            "A simple range step loop is enough here.",
            """
            def chunk_s3_keys(keys, batch_size):
                if batch_size <= 0:
                    return []
                return [keys[index:index + batch_size] for index in range(0, len(keys), batch_size)]
            """,
            tests=[
                {"args": (["a", "b", "c", "d", "e"], 2), "expected": [["a", "b"], ["c", "d"], ["e"]]},
                {"args": (["a"], 0), "expected": []},
            ],
            tags=["aws", "s3", "batching"],
        ),
        _question(
            53,
            "Cloud & APIs",
            "Athena Scan Cost",
            "Easy",
            "athena_scan_cost(scanned_tb, price_per_tb=5.0)",
            "Return the estimated Athena query cost rounded to 2 decimals.",
            "Multiply scanned terabytes by the price per TB and round the result.",
            """
            def athena_scan_cost(scanned_tb, price_per_tb=5.0):
                return round(scanned_tb * price_per_tb, 2)
            """,
            tests=[
                {"args": (2.5,), "expected": 12.5},
                {"args": (0.37, 6.25), "expected": 2.31},
            ],
            tags=["aws", "athena", "cost"],
        ),
        _question(
            54,
            "Cloud & APIs",
            "Build API Retry Plan",
            "Medium",
            "build_api_retry_plan(status_codes)",
            "Return a list of booleans telling whether each HTTP status code should be retried. Retry 429 and all 5xx statuses only.",
            "Map each code to a retry decision with a simple condition.",
            """
            def build_api_retry_plan(status_codes):
                result = []
                for code in status_codes:
                    result.append(code == 429 or 500 <= code <= 599)
                return result
            """,
            tests=[
                {"args": ([200, 429, 503, 404],), "expected": [False, True, True, False]},
                {"args": ([500, 501],), "expected": [True, True]},
            ],
            tags=["aws", "api", "retries"],
        ),
        _question(
            55,
            "Pandas & NumPy",
            "Daily Revenue Totals",
            "Easy",
            "daily_revenue_totals(df)",
            "Return a DataFrame with one row per date and the total revenue for that date.",
            "Convert to date first, then group and sum.",
            """
            import pandas as pd

            def daily_revenue_totals(df):
                result = df.copy()
                result["dt"] = pd.to_datetime(result["event_ts"]).dt.date.astype(str)
                result = result.groupby("dt", as_index=False)["amount"].sum()
                return result.rename(columns={"amount": "total_amount"}).sort_values("dt").reset_index(drop=True)
            """,
            tests=[
                {
                    "args": (
                        pd.DataFrame(
                            [
                                {"event_ts": "2024-01-01 10:00:00", "amount": 10},
                                {"event_ts": "2024-01-01 12:00:00", "amount": 5},
                                {"event_ts": "2024-01-02 09:00:00", "amount": 7},
                            ]
                        ),
                    ),
                    "expected": pd.DataFrame(
                        [
                            {"dt": "2024-01-01", "total_amount": 15},
                            {"dt": "2024-01-02", "total_amount": 7},
                        ]
                    ),
                    "sort_by": ["dt"],
                }
            ],
            tags=["pandas", "groupby", "dates"],
        ),
        _question(
            56,
            "Pandas & NumPy",
            "Explode Tags Column",
            "Medium",
            "explode_tags_column(df)",
            "The `tags` column stores a list of strings. Explode it so each tag becomes its own row.",
            "Use explode and keep the row order stable.",
            """
            import pandas as pd

            def explode_tags_column(df):
                result = df.copy()
                result = result.explode("tags").reset_index(drop=True)
                return result
            """,
            tests=[
                {
                    "args": (
                        pd.DataFrame(
                            [
                                {"id": 1, "tags": ["a", "b"]},
                                {"id": 2, "tags": ["c"]},
                            ]
                        ),
                    ),
                    "expected": pd.DataFrame(
                        [
                            {"id": 1, "tags": "a"},
                            {"id": 1, "tags": "b"},
                            {"id": 2, "tags": "c"},
                        ]
                    ),
                }
            ],
            tags=["pandas", "explode", "nested-data"],
        ),
        _question(
            57,
            "Pandas & NumPy",
            "Fill Missing Calendar Dates",
            "Medium",
            "fill_missing_calendar_dates(df)",
            "Given a DataFrame with columns `dt` and `value`, fill missing calendar dates between the min and max date with value 0.",
            "Create a full date range and left-join the existing data into it.",
            """
            import pandas as pd

            def fill_missing_calendar_dates(df):
                result = df.copy()
                result["dt"] = pd.to_datetime(result["dt"])
                full_range = pd.DataFrame({"dt": pd.date_range(result["dt"].min(), result["dt"].max(), freq="D")})
                result = full_range.merge(result, on="dt", how="left").fillna({"value": 0})
                result["dt"] = result["dt"].dt.strftime("%Y-%m-%d")
                result["value"] = result["value"].astype(int)
                return result
            """,
            tests=[
                {
                    "args": (
                        pd.DataFrame(
                            [
                                {"dt": "2024-01-01", "value": 10},
                                {"dt": "2024-01-03", "value": 7},
                            ]
                        ),
                    ),
                    "expected": pd.DataFrame(
                        [
                            {"dt": "2024-01-01", "value": 10},
                            {"dt": "2024-01-02", "value": 0},
                            {"dt": "2024-01-03", "value": 7},
                        ]
                    ),
                    "sort_by": ["dt"],
                }
            ],
            tags=["pandas", "dates", "fillna"],
        ),
        _question(
            58,
            "Pandas & NumPy",
            "Normalize Feature Vector",
            "Easy",
            "normalize_feature_vector(values)",
            "Normalize a numeric list to the range [0, 1]. If all values are equal, return a list of zeroes.",
            "Min-max normalization uses `(value - min_value) / (max_value - min_value)`.",
            """
            def normalize_feature_vector(values):
                if not values:
                    return []
                min_value = min(values)
                max_value = max(values)
                if min_value == max_value:
                    return [0 for _ in values]
                return [round((value - min_value) / (max_value - min_value), 4) for value in values]
            """,
            tests=[
                {"args": ([10, 20, 30],), "expected": [0.0, 0.5, 1.0]},
                {"args": ([5, 5, 5],), "expected": [0, 0, 0]},
            ],
            tags=["numpy-style", "normalization", "features"],
        ),
        _question(
            59,
            "Interview Patterns",
            "Binary Search First Greater Or Equal",
            "Easy",
            "first_greater_or_equal(nums, target)",
            "Return the index of the first value greater than or equal to target in a sorted list. Return -1 if none exists.",
            "Classic binary search with the answer pushed left whenever the condition is satisfied.",
            """
            def first_greater_or_equal(nums, target):
                left, right = 0, len(nums) - 1
                answer = -1

                while left <= right:
                    mid = (left + right) // 2
                    if nums[mid] >= target:
                        answer = mid
                        right = mid - 1
                    else:
                        left = mid + 1

                return answer
            """,
            tests=[
                {"args": ([1, 3, 5, 7], 4), "expected": 2},
                {"args": ([1, 2, 3], 10), "expected": -1},
            ],
            tags=["binary-search", "sorted-array"],
        ),
        _question(
            60,
            "Interview Patterns",
            "K Closest Numbers",
            "Medium",
            "k_closest_numbers(nums, target, k)",
            "Return the k numbers closest to target, sorted by absolute distance then value.",
            "Sort using a compound key of distance and value, then take the first k items.",
            """
            def k_closest_numbers(nums, target, k):
                ordered = sorted(nums, key=lambda value: (abs(value - target), value))
                return ordered[:k]
            """,
            tests=[
                {"args": ([1, 2, 3, 4, 5], 3, 4), "expected": [3, 2, 4, 1]},
                {"args": ([10, 20, 30], 25, 2), "expected": [20, 30]},
            ],
            tags=["sorting", "distance", "interview"],
        ),
    ]
