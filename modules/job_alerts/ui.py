from datetime import timedelta, timezone

import altair as alt
import pandas as pd
import streamlit as st

from core.job_enrichment import (
    fetch_stock_history,
    fetch_stock_quote,
    get_company_metadata,
    get_compensation_reports,
    get_interview_process,
    get_research_links,
    load_priority_companies,
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

    period_label = st.segmented_control(
        "Stock range",
        options=["1M", "3M", "1Y", "5Y", "MAX"],
        default="1Y",
        key=f"stock_period_{job_id}",
        label_visibility="collapsed",
    )
    period = {"1M": "1mo", "3M": "3mo", "1Y": "1y", "5Y": "5y", "MAX": "max"}[
        period_label or "1Y"
    ]
    history = fetch_stock_history(company["ticker"], period)
    if history:
        frame = pd.DataFrame(history)
        frame["date"] = pd.to_datetime(frame["date"])
        first_close = float(frame.iloc[0]["close"])
        last_close = float(frame.iloc[-1]["close"])
        change = last_close - first_close
        change_percent = (change / first_close) * 100 if first_close else 0
        chart_color = "#137333" if change >= 0 else "#a50e0e"

        st.markdown(
            f"### {last_close:,.2f} {quote['currency'] or ''}  "
            f"<span style='color:{chart_color};font-size:0.9rem'>"
            f"{change:+,.2f} ({change_percent:+.2f}%) · {period_label or '1Y'}</span>",
            unsafe_allow_html=True,
        )

        base = alt.Chart(frame).encode(
            x=alt.X("date:T", title=None, axis=alt.Axis(grid=False)),
            y=alt.Y(
                "close:Q",
                title=None,
                scale=alt.Scale(zero=False),
                axis=alt.Axis(grid=True, orient="right"),
            ),
        )
        nearest = alt.selection_point(
            nearest=True,
            on="pointerover",
            fields=["date"],
            empty=False,
        )
        area = base.mark_area(
            color=chart_color,
            opacity=0.10,
            line=False,
        )
        line = base.mark_line(color=chart_color, strokeWidth=2)
        selectors = base.mark_point(opacity=0).add_params(nearest)
        points = base.mark_point(color=chart_color, size=55).encode(
            opacity=alt.condition(nearest, alt.value(1), alt.value(0)),
            tooltip=[
                alt.Tooltip("date:T", title="Date", format="%d %b %Y"),
                alt.Tooltip("close:Q", title="Close", format=",.2f"),
            ],
        )
        rule = base.mark_rule(color="#9aa0a6").encode(
            opacity=alt.condition(nearest, alt.value(0.7), alt.value(0))
        )
        chart = (area + line + selectors + points + rule).properties(height=300)
        st.altair_chart(chart, width="stretch")
    else:
        st.caption("Historical market data is temporarily unavailable.")
    st.caption(
        f"{quote['ticker']} · {quote['exchange'] or 'Exchange unavailable'} · "
        "Delayed market data · "
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


def _render_priority_companies(companies, jobs):
    active_counts = {}
    remote_counts = {}
    for job in jobs:
        company_name = job["company"]
        active_counts[company_name] = active_counts.get(company_name, 0) + 1
        location_text = f"{job['location']} {job['work_mode']}".lower()
        if "remote" in location_text:
            remote_counts[company_name] = remote_counts.get(company_name, 0) + 1

    query = st.text_input(
        "Search priority companies",
        placeholder="Company, role or interview status",
        key="priority_company_search",
    ).strip().lower()
    visible = [
        company
        for company in companies
        if not query
        or query
        in " ".join(
            str(company.get(field, ""))
            for field in ("company", "target_role", "status", "process")
        ).lower()
    ]

    rows = [
        {
            "Company": company["company"],
            "Target role": company["target_role"],
            "Coverage": (
                f"Automatic · {company['scan_platform']}"
                if company["scan_platform"]
                else "Career link"
            ),
            "Jobs": active_counts.get(company["company"], 0),
            "Remote": remote_counts.get(company["company"], 0),
            "Interview status": company.get("status") or "Not started",
            "Careers": company["career_url"],
        }
        for company in visible
    ]
    st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
        column_config={
            "Careers": st.column_config.LinkColumn("Careers", display_text="Open ↗"),
            "Jobs": st.column_config.NumberColumn("Jobs", format="%d"),
            "Remote": st.column_config.NumberColumn("Remote", format="%d"),
        },
    )

    if not visible:
        return
    selected_name = st.selectbox(
        "Company details",
        [company["company"] for company in visible],
        key="priority_company_details",
    )
    selected = next(
        company for company in visible if company["company"] == selected_name
    )
    with st.container(border=True):
        title_col, link_col = st.columns([5, 1])
        title_col.subheader(selected["company"])
        link_col.link_button("Careers ↗", selected["career_url"], width="stretch")
        st.caption(
            f"{selected['target_role']} · "
            + (
                f"Automatically scanned through {selected['scan_platform']}"
                if selected["scan_platform"]
                else "Career link tracked; automated adapter pending"
            )
        )
        if selected.get("status"):
            st.write(f"**Status:** {selected['status']}")
        if selected.get("process"):
            st.write(f"**Process:** {selected['process']}")
        rounds = [
            (label, selected.get(field))
            for label, field in (
                ("Round 1", "round1"),
                ("Round 2", "round2"),
                ("Round 3", "round3"),
            )
            if selected.get(field)
        ]
        for label, value in rounds:
            st.write(f"**{label}:** {value}")
        if selected.get("mistakes"):
            st.warning(selected["mistakes"])

        if selected.get("ticker"):
            with st.expander("Stock performance"):
                _render_stock(selected, f"priority_{selected['company']}")


def _filter_jobs(jobs, location_scope, search_query, priority_names):
    filtered = []
    search_query = search_query.strip().lower()
    for job in jobs:
        location_text = f"{job['location']} {job['work_mode']}".lower()
        if location_scope == "Remote" and "remote" not in location_text:
            continue
        if location_scope == "India" and not any(
            term in location_text
            for term in ("india", "bengaluru", "bangalore", "hyderabad", "pune", "chennai")
        ):
            continue
        if location_scope == "Priority companies" and job["company"] not in priority_names:
            continue
        if search_query and search_query not in (
            f"{job['company']} {job['title']} {job['location']} "
            f"{job['description']}"
        ).lower():
            continue
        filtered.append(job)
    return filtered


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
    priority_companies = load_priority_companies()
    priority_names = {company["company"] for company in priority_companies}
    active_jobs = list_jobs_for_user(username, status_filter="Active")

    jobs_tab, companies_tab = st.tabs(["Jobs", "Priority companies"])
    with jobs_tab:
        status_col, location_col = st.columns([1, 2])
        selected_status = status_col.selectbox(
            "Status",
            STATUS_OPTIONS,
            key="job_alert_status_filter",
        )
        location_scope = location_col.segmented_control(
            "Location",
            ["All jobs", "Remote", "India", "Priority companies"],
            default="All jobs",
            key="job_alert_location_filter",
        )
        search_query = st.text_input(
            "Search jobs",
            placeholder="Company, title, location or skill",
            key="job_alert_search",
        )
        jobs = (
            active_jobs
            if selected_status == "Active"
            else list_jobs_for_user(username, status_filter=selected_status)
        )
        jobs = _filter_jobs(
            jobs,
            location_scope or "All jobs",
            search_query,
            priority_names,
        )

        if not jobs:
            st.info("No jobs match these filters.")
        else:
            st.caption(f"{len(jobs)} job{'s' if len(jobs) != 1 else ''}")
            for job in jobs:
                _render_job(username, job)

    with companies_tab:
        _render_priority_companies(priority_companies, active_jobs)
