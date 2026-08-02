from datetime import timedelta, timezone

import streamlit as st

from core.job_enrichment import (
    extract_compensation,
    fetch_stock_quote,
    get_company_metadata,
    get_interview_process,
)
from core.job_alerts import (
    get_scan_overview,
    is_scan_due,
    list_source_refresh_status,
    list_jobs_for_user,
    run_all_company_scans,
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
    overview = get_scan_overview()
    st.info(
        f"Latest career-site refresh: {_display_time(overview['last_completed_at'])}. "
        "Sources are staggered in hourly batches and each is refreshed about every 12 hours."
    )
    last_col, coverage_col, company_col, job_col = st.columns(4)
    last_col.metric("Latest source refresh", _display_time(overview["last_completed_at"]))
    coverage_col.metric(
        "Sources healthy",
        f"{overview['successful_sources']} / {overview['configured_sources']}",
    )
    company_col.metric("Companies with matches", overview["active_companies"])
    job_col.metric("Active matches", overview["active_jobs"])

    if overview["failed_sources"]:
        with st.expander(f"{overview['failed_sources']} sources need attention"):
            for failure in overview["recent_failures"]:
                st.caption(f"{failure['source']}: {failure['error']}")
    elif is_scan_due():
        st.info("The next 12-hour scan is due.")

    with st.expander("Company refresh schedule"):
        refresh_rows = list_source_refresh_status()
        st.dataframe(
            [
                {
                    "Company": row["company"],
                    "Category": row["category"].replace("-", " ").title(),
                    "Career platform": row["platform"].title(),
                    "Last refreshed": _display_time(row["refreshed_at"]),
                    "Next due": _display_time(row["next_refresh_at"]),
                    "Status": row["status"].replace("_", " ").title(),
                    "Active matches": row["active_jobs"],
                }
                for row in refresh_rows
            ],
            width="stretch",
            hide_index=True,
        )

    if is_admin and st.button("Scan all companies now", width="content"):
        with st.spinner("Checking all configured career sites…"):
            try:
                result = run_all_company_scans()
            except Exception as error:
                st.error(f"Scan failed: {error}")
            else:
                st.success(
                    f"Scan complete: {result['successful_sources']} sources checked, "
                    f"{result['matched_count']} matched, {result['inserted_count']} new."
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

        with st.expander("Company, compensation, stock and interview details"):
            company = get_company_metadata(job["source"], job["company"])
            company_col, category_col, source_col = st.columns(3)
            company_col.metric("Company", company["company"])
            category_col.metric("Category", company["category"])
            source_col.metric("Career platform", company["platform"])
            if company["careers_url"]:
                st.link_button(
                    "Open company careers page",
                    company["careers_url"],
                    key=f"company_careers_{job['id']}",
                )

            st.markdown("#### Compensation disclosed in this posting")
            compensation = extract_compensation(job["description"])
            if compensation["published_ranges"]:
                for pay_range in compensation["published_ranges"]:
                    st.write(f"- Base-pay range: **{pay_range}**")
            else:
                st.caption("The official posting does not publish a base-pay range.")
            compensation_facts = [
                "Equity/stock mentioned" if compensation["equity_mentioned"] else None,
                "Bonus mentioned" if compensation["bonus_mentioned"] else None,
                *compensation["benefits"],
            ]
            compensation_facts = [fact for fact in compensation_facts if fact]
            if compensation_facts:
                st.caption(" · ".join(compensation_facts))
            st.caption(
                "Compensation varies by location and level. Only information explicitly "
                "published in the official posting is shown."
            )

            st.markdown("#### Public stock")
            quote = fetch_stock_quote(company["ticker"])
            if quote and quote["price"] is not None:
                price_col, change_col, exchange_col = st.columns(3)
                price_col.metric(
                    quote["ticker"],
                    f"{quote['price']:,.2f} {quote['currency'] or ''}".strip(),
                )
                change_col.metric(
                    "Recent change",
                    (
                        f"{quote['change_percent']:+.2f}%"
                        if quote["change_percent"] is not None
                        else "Not available"
                    ),
                )
                exchange_col.metric("Exchange", quote["exchange"] or "Not available")
                st.caption("Delayed market quote; not investment advice.")
                st.link_button(
                    "Open market data source",
                    f"https://finance.yahoo.com/quote/{quote['ticker']}",
                    key=f"market_source_{job['id']}",
                )
            elif company["ticker"]:
                st.caption(f"Ticker {company['ticker']} is mapped, but a quote is unavailable.")
            else:
                st.caption("No public stock ticker is mapped for this company.")

            st.markdown("#### Interview process")
            interview = get_interview_process(job["company"], job["title"])
            st.write(
                f"**Evidence:** {'Company-specific reports' if interview['is_company_verified'] else 'Typical role pattern'} "
                f"· **Confidence:** {interview['confidence'].title()}"
            )
            st.caption(interview["note"])
            for index, step in enumerate(interview["steps"], start=1):
                st.write(f"{index}. {step}")
            if interview["question_categories"]:
                st.caption(
                    "Reported question areas: "
                    + " · ".join(interview["question_categories"])
                )
            for index, source in enumerate(interview["sources"], start=1):
                st.link_button(
                    source["label"],
                    source["url"],
                    key=f"interview_source_{job['id']}_{index}",
                )

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
        "India and India-eligible remote AI Data Engineer and related roles. "
        "Configured product-company career sites are checked every 12 hours."
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
