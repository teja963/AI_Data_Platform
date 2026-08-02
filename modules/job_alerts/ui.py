from datetime import timedelta, timezone

import streamlit as st

from core.job_alerts import (
    get_latest_scan,
    is_scan_due,
    list_jobs_for_user,
    run_microsoft_scan,
    update_job_status,
)


STATUS_OPTIONS = ("Active", "Saved", "Applied", "Rejected", "Not Relevant", "All")
STATUS_LABELS = {
    "new": "New",
    "saved": "Saved",
    "applied": "Applied",
    "rejected": "Rejected",
    "not_relevant": "Not Relevant",
}


def _display_time(value):
    if not value:
        return "Not available"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    ist = timezone(timedelta(hours=5, minutes=30))
    return value.astimezone(ist).strftime("%d %b %Y, %I:%M %p IST")


def _short_description(value, limit=520):
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit].rsplit(' ', 1)[0]}…"


def _render_scan_status(is_admin):
    latest = get_latest_scan()
    left, middle, right = st.columns([2, 2, 1])
    if latest:
        left.metric("Last scan", _display_time(latest["finished_at"] or latest["started_at"]))
        middle.metric("New jobs in last scan", latest["inserted_count"])
        if latest["status"] == "failed":
            st.error(f"Microsoft scan failed: {latest['error_message']}")
        elif is_scan_due():
            st.info("The next 12-hour scan is due.")
    else:
        left.metric("Last scan", "Not run")
        middle.metric("New jobs in last scan", "—")

    if is_admin and right.button("Scan Microsoft now", width="stretch"):
        with st.spinner("Checking Microsoft Careers…"):
            try:
                result = run_microsoft_scan()
            except Exception as error:
                st.error(f"Scan failed: {error}")
            else:
                st.success(
                    f"Scan complete: {result['matched_count']} matched, "
                    f"{result['inserted_count']} new."
                )
                st.rerun()


def _render_job(username, job):
    with st.container(border=True):
        title_col, status_col = st.columns([5, 1])
        title_col.subheader(job["title"])
        status_col.caption(STATUS_LABELS.get(job["status"], job["status"].title()))

        st.caption(
            f"{job['company']} · {job['location']} · {job['work_mode']} · "
            f"Posted {_display_time(job['posted_at'])}"
        )
        st.write(_short_description(job["description"]) or "No description was provided.")
        st.caption(f"Match: {job['match_score']}% · {job['match_reason']}")

        apply_col, save_col, applied_col, reject_col, irrelevant_col = st.columns(5)
        apply_col.link_button("Open application", job["job_url"], width="stretch")
        if save_col.button("Save", key=f"save_job_{job['id']}", width="stretch"):
            update_job_status(username, job["id"], "saved")
            st.rerun()
        if applied_col.button("Applied", key=f"apply_job_{job['id']}", width="stretch"):
            update_job_status(username, job["id"], "applied")
            st.rerun()
        if reject_col.button("Reject", key=f"reject_job_{job['id']}", width="stretch"):
            update_job_status(username, job["id"], "rejected")
            st.rerun()
        if irrelevant_col.button(
            "Not relevant",
            key=f"irrelevant_job_{job['id']}",
            width="stretch",
        ):
            update_job_status(username, job["id"], "not_relevant")
            st.rerun()


def render_job_alerts():
    username = st.session_state.get("user")
    role = st.session_state.get("role", "user")

    st.title("Job Alerts")
    st.caption(
        "Global and remote AI Data Engineer and related roles. "
        "Microsoft Careers is checked every 12 hours."
    )

    _render_scan_status(is_admin=role == "admin")

    selected_status = st.selectbox(
        "Show jobs",
        STATUS_OPTIONS,
        key="job_alert_status_filter",
    )
    jobs = list_jobs_for_user(username, status_filter=selected_status)

    if not jobs:
        st.info("No matching jobs are available in this view yet.")
        return

    st.caption(f"{len(jobs)} job{'s' if len(jobs) != 1 else ''}")
    for job in jobs:
        _render_job(username, job)
