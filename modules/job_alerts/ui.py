from datetime import timedelta, timezone

import pandas as pd
import streamlit as st

from core.job_enrichment import (
    fetch_stock_history,
    fetch_stock_quote,
    get_company_metadata,
    get_compensation_reports,
    get_interview_process,
    get_research_links,
)
from core.job_alerts import (
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


def _role_signals(description):
    text = (description or "").lower()
    signals = {
        "Python": ("python",),
        "SQL": ("sql",),
        "Spark": ("spark", "pyspark"),
        "Databricks": ("databricks",),
        "Snowflake": ("snowflake",),
        "Airflow": ("airflow",),
        "dbt": ("dbt",),
        "AWS": ("aws", "amazon web services"),
        "Azure": ("azure",),
        "GCP": ("gcp", "google cloud"),
        "Kafka": ("kafka",),
        "GenAI": ("generative ai", "genai", "large language model", " llm"),
    }
    return [
        label
        for label, terms in signals.items()
        if any(term in text for term in terms)
    ][:8]


def _render_scan_status(is_admin):
    if not is_admin:
        return
    with st.popover("Admin"):
        if st.button("Scan now", width="stretch"):
            with st.spinner("Checking career sites…"):
                try:
                    result = run_all_company_scans()
                except Exception as error:
                    st.error(f"Scan failed: {error}")
                else:
                    st.success(
                        f"{result['successful_sources']} sources checked; "
                        f"{result['inserted_count']} new jobs."
                    )
                    st.rerun()


def _render_compensation(company_name, job_id):
    reports = get_compensation_reports(company_name)
    if not reports:
        st.caption("No verified salary-review data stored yet.")
        return

    chart_rows = [
        {
            "Source": report["source"],
            "Low": report["minimum_lpa"],
            "High": report["maximum_lpa"],
        }
        for report in reports
    ]
    st.bar_chart(
        pd.DataFrame(chart_rows).set_index("Source"),
        color=["#4C78A8", "#72B7B2"],
        height=240,
    )
    for index, report in enumerate(reports):
        role = report.get("role", "Data Engineer")
        location = report.get("location")
        context = f" · {location}" if location else ""
        st.markdown(
            f"**₹{report['minimum_lpa']:g}L–₹{report['maximum_lpa']:g}L** "
            f"· {role}{context} · "
            f"[{report['source']} ↗]({report['url']})"
        )
        if report.get("caveat"):
            st.caption(report["caveat"])


def _render_stock(company, job_id):
    quote = fetch_stock_quote(company["ticker"])
    if not quote or quote["price"] is None:
        st.caption("Private company or no public market history is available.")
        return

    price_col, change_col = st.columns(2)
    price_col.metric(
        quote["ticker"],
        f"{quote['price']:,.2f} {quote['currency'] or ''}".strip(),
    )
    change_col.metric(
        "Change",
        (
            f"{quote['change_percent']:+.2f}%"
            if quote["change_percent"] is not None
            else "Not available"
        ),
    )
    period_label = st.select_slider(
        "History",
        options=["1M", "3M", "1Y", "5Y", "MAX"],
        value="1Y",
        key=f"stock_period_{job_id}",
    )
    period = {"1M": "1mo", "3M": "3mo", "1Y": "1y", "5Y": "5y", "MAX": "max"}[
        period_label
    ]
    history = fetch_stock_history(company["ticker"], period)
    if history:
        frame = pd.DataFrame(history).set_index("date")
        st.line_chart(frame, y="close", height=260)
    st.caption(
        f"Delayed market data · "
        f"[Yahoo Finance ↗](https://finance.yahoo.com/quote/{quote['ticker']})"
    )


def _render_interview(company_name, role_title):
    interview = get_interview_process(company_name, role_title)
    links = get_research_links(company_name, role_title)
    if interview:
        st.caption(
            f"Candidate-reported evidence · {interview['confidence'].title()} confidence"
        )
        for index, step in enumerate(interview["steps"], start=1):
            st.write(f"{index}. {step}")
        if interview["questions"]:
            st.write("**Questions reported by candidates**")
            for question in interview["questions"]:
                st.write(f"- {question}")
        if interview["question_categories"]:
            st.caption("Topics: " + " · ".join(interview["question_categories"]))
        if interview["note"]:
            st.caption(interview["note"])
        st.markdown(
            " · ".join(
                f"[{source['label']} ↗]({source['url']})"
                for source in interview["sources"]
            )
        )
    else:
        st.caption("No credible company-specific candidate report is stored yet.")
    st.markdown(" · ".join(f"[{label} ↗]({url})" for label, url in links.items()))


def _render_job(username, job):
    with st.container(border=True):
        title_col, status_col = st.columns([5, 1])
        title_col.subheader(job["title"])
        status_col.caption(STATUS_LABELS.get(job["status"], job["status"].title()))

        st.caption(
            f"{job['company']} · {job['location']} · {job['work_mode']} · "
            f"Posted {_display_time(job['posted_at'])}"
        )
        signals = _role_signals(job["description"])
        if signals:
            st.caption("Skills: " + " · ".join(signals))
        company = get_company_metadata(job["source"], job["company"])
        compact_links = [f"[Apply ↗]({job['job_url']})"]
        if company["careers_url"]:
            compact_links.append(f"[Careers ↗]({company['careers_url']})")
        st.markdown(" · ".join(compact_links))

        with st.expander("Salary, stock and interview evidence"):
            salary_tab, stock_tab, interview_tab = st.tabs(
                ["Salary reviews", "Stock", "Interview reports"]
            )
            with salary_tab:
                _render_compensation(job["company"], job["id"])
            with stock_tab:
                _render_stock(company, job["id"])
            with interview_tab:
                _render_interview(job["company"], job["title"])

        save_col, applied_col, reject_col, irrelevant_col = st.columns(4)
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
