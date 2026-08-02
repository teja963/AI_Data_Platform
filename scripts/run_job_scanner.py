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


def _run_once(scan_all=False):
    started = datetime.now(timezone.utc).isoformat()
    scan_mode = "full" if scan_all else "staggered due-source"
    print(f"[{started}] Starting {scan_mode} career-site scan", flush=True)
    result = run_all_company_scans() if scan_all else run_due_company_scans()
    finished = datetime.now(timezone.utc).isoformat()
    if result["status"] == "not_due":
        print(f"[{finished}] No career sources are due for refresh", flush=True)
        return
    print(
        f"[{finished}] Scan complete: {result['successful_sources']}/"
        f"{result['source_count']} sources, {result['matched_count']} matched, "
        f"{result['inserted_count']} new, {result['failed_sources']} failed",
        flush=True,
    )


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
