#!/usr/bin/env python3
import argparse
import os
import sys
import time
from datetime import datetime, timezone


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.job_alerts import (
    SCAN_INTERVAL_HOURS,
    run_all_company_scans,
    run_due_company_scans,
)


def _write_github_summary(result):
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    failures = result.get("failures") or []
    with open(summary_path, "a", encoding="utf-8") as summary:
        summary.write("### Career-site scan\n\n")
        summary.write(
            f"- Status: **{result['status']}**\n"
            f"- Sources checked: **{result['source_count']}**\n"
            f"- Successful: **{result['successful_sources']}**\n"
            f"- Failed external sources: **{result['failed_sources']}**\n"
            f"- Matching jobs: **{result['matched_count']}**\n"
            f"- New jobs: **{result['inserted_count']}**\n"
        )
        if failures:
            summary.write("\nExternal source warnings:\n")
            for failure in failures[:20]:
                error = str(failure["error"]).replace("\n", " ")[:300]
                summary.write(f"- `{failure['source']}`: {error}\n")


def _report_source_failures(result):
    for failure in result.get("failures") or []:
        error = str(failure["error"]).replace("\n", " ")[:500]
        print(
            f"::warning title=Career source unavailable::{failure['source']}: {error}",
            flush=True,
        )


def _run_once(scan_all=False):
    started = datetime.now(timezone.utc).isoformat()
    scan_mode = "full" if scan_all else "staggered due-source"
    print(f"[{started}] Starting {scan_mode} career-site scan", flush=True)
    result = run_all_company_scans() if scan_all else run_due_company_scans()
    finished = datetime.now(timezone.utc).isoformat()
    if result["status"] == "not_due":
        print(f"[{finished}] No career sources are due for refresh", flush=True)
        _write_github_summary(result)
        return
    _report_source_failures(result)
    print(
        f"[{finished}] Scan complete: {result['successful_sources']}/"
        f"{result['source_count']} sources, {result['matched_count']} matched, "
        f"{result['inserted_count']} new, {result['failed_sources']} failed",
        flush=True,
    )
    _write_github_summary(result)


def main():
    parser = argparse.ArgumentParser(description="Scan public career sites for matching jobs.")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Continue scanning at the configured interval instead of running once.",
    )
    parser.add_argument(
        "--interval-hours",
        type=float,
        default=SCAN_INTERVAL_HOURS,
        help=f"Hours between scans in loop mode (default: {SCAN_INTERVAL_HOURS}).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scan every configured company instead of only the staggered due batch.",
    )
    args = parser.parse_args()

    if args.interval_hours <= 0:
        parser.error("--interval-hours must be greater than zero")

    while True:
        try:
            _run_once(scan_all=args.all)
        except Exception as error:
            failed = datetime.now(timezone.utc).isoformat()
            print(f"[{failed}] Scan failed: {error}", file=sys.stderr, flush=True)
            if not args.loop:
                raise

        if not args.loop:
            return
        time.sleep(args.interval_hours * 60 * 60)


if __name__ == "__main__":
    main()
