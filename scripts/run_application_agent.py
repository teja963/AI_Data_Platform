#!/usr/bin/env python3
import argparse
import os
import sys
import tempfile
import time
from pathlib import Path


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.application_agent import prepare_application, worker_paths
from core.application_workflow import (
    claim_next_application_draft,
    complete_application_draft,
    fail_application_draft,
    get_draft_worker_payload,
)


def _env_bool(name, default=True):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def process_draft(draft_id, action="prepare"):
    payload = get_draft_worker_payload(draft_id)
    paths = worker_paths(draft_id, payload["username_key"], payload["source"])
    resume_path = None
    try:
        if payload["resume_bytes"]:
            suffix = Path(payload["resume_filename"] or "resume.pdf").suffix or ".pdf"
            handle = tempfile.NamedTemporaryFile(
                prefix=f"application-{draft_id}-",
                suffix=suffix,
                delete=False,
            )
            try:
                handle.write(payload["resume_bytes"])
                resume_path = Path(handle.name)
            finally:
                handle.close()

        result = prepare_application(
            official_url=payload["official_url"],
            profile=payload["profile"],
            site_credential=payload["site_credential"],
            submit_approved=action == "submit",
            resume_path=resume_path,
            screenshot_path=paths["screenshot_path"],
            browser_state_dir=paths["browser_state_dir"],
            headless=_env_bool("PLAYWRIGHT_HEADLESS", True),
        )
        complete_application_draft(
            draft_id,
            result,
            artifact_dir=str(paths["artifact_dir"]),
        )
        print(
            f"Draft {draft_id} {action} finished: {len(result['filled_fields'])} fields, "
            f"{len(result['blockers'])} blockers",
            flush=True,
        )
    except Exception as error:
        fail_application_draft(draft_id, error)
        raise
    finally:
        if resume_path:
            resume_path.unlink(missing_ok=True)


def run_once():
    claimed = claim_next_application_draft()
    if claimed is None:
        return False
    process_draft(claimed["id"], action=claimed["action"])
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Prepare queued job applications with Playwright without submitting."
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Wait for and process application drafts continuously.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=float(os.getenv("APPLICATION_AGENT_POLL_SECONDS", "5")),
        help="Seconds between queue checks in loop mode.",
    )
    parser.add_argument(
        "--draft-id",
        type=int,
        help="Process one specific draft instead of claiming the next queued draft.",
    )
    args = parser.parse_args()
    if args.poll_seconds <= 0:
        parser.error("--poll-seconds must be greater than zero")

    if args.draft_id is not None:
        process_draft(args.draft_id)
        return

    while True:
        try:
            processed = run_once()
        except Exception as error:
            print(f"Application preparation failed: {error}", file=sys.stderr, flush=True)
            processed = True
            if not args.loop:
                raise
        if not args.loop:
            return
        if not processed:
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
