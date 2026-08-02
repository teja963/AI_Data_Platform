#!/usr/bin/env python3
import argparse
import os
import sys
import time
from datetime import datetime, timezone


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.job_alerts import SCAN_INTERVAL_HOURS, run_microsoft_scan


def _run_once():
    started = datetime.now(timezone.utc).isoformat()
    print(f"[{started}] Starting Microsoft Careers scan", flush=True)
    result = run_microsoft_scan()
    finished = datetime.now(timezone.utc).isoformat()
    print(
        f"[{finished}] Scan complete: {result['matched_count']} matched, "
        f"{result['inserted_count']} new",
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
    args = parser.parse_args()

    if args.interval_hours <= 0:
        parser.error("--interval-hours must be greater than zero")

    while True:
        try:
            _run_once()
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
