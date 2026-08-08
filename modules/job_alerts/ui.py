from datetime import timedelta, timezone

import altair as alt
import pandas as pd
import streamlit as st

from core.job_enrichment import (
    compensation_range_in_inr,
    extract_compensation,
    fetch_company_history,
    fetch_stock_history,
    fetch_stock_quote,
    get_company_metadata,
    get_compensation_reports,
    get_interview_process,
    get_research_links,
    load_priority_companies,
)
from core.application_assist import build_application_review, profile_completion
from core.job_alerts import (
    list_jobs_for_user,
    run_due_company_scans,
    update_job_status,
)
from core.job_sources import load_job_sources, source_key
from core.lazy_tabs import lazy_tab


PAGE_SIZE = 12
STATUS_LABELS = {
    "new": "New",
    "saved": "Saved",
    "applied": "Applied",
    "rejected": "Rejected",
    "not_relevant": "Not Relevant",
}
SECTOR_LABELS = {
    "aerospace": "Aerospace",
    "aviation": "Travel & Aviation",
    "commerce": "Retail & E-commerce",
    "consulting": "Consulting & Services",
    "consumer": "Consumer Internet",
    "consumer-tech": "Consumer Internet",
    "entertainment": "Media & Entertainment",
    "financial-services": "Banking & Financial Services",
    "fintech": "Payments & Fintech",
    "health-tech": "Healthcare Technology",
    "marketplace": "Retail & E-commerce",
    "payments": "Payments & Fintech",
    "remote-talent": "Staffing & Talent Platforms",
    "retail": "Retail & E-commerce",
    "semiconductors": "Chips & Semiconductors",
    "software": "Enterprise Software & Cloud",
    "technology": "Enterprise Software & Cloud",
    "travel": "Travel & Aviation",
}


@st.cache_data(ttl=60, show_spinner=False)
def _load_jobs_cached(username, status_filter):
    return list_jobs_for_user(username, status_filter=status_filter)


def _invalidate_job_cache():
    _load_jobs_cached.clear()


@st.cache_data(show_spinner=False)
def _source_sector_lookup():
    return {
        source_key(source): SECTOR_LABELS.get(
            source.get("category", ""),
            (source.get("category") or "Other").replace("-", " ").title(),
        )
        for source in load_job_sources()
    }


def _job_sector(job):
    fallback = {
        "Microsoft": "Enterprise Software & Cloud",
        "Amazon": "Retail & E-commerce",
    }
    return _source_sector_lookup().get(
        job.get("source"),
        fallback.get(job.get("company"), "Other"),
    )


def _jobs_with_sectors(jobs):
    return [{**job, "sector": _job_sector(job)} for job in jobs]


def _balance_jobs(jobs, max_per_company=None):
    jobs_by_company = {}
    company_order = []
    for job in jobs:
        company = job["company"]
        if company not in jobs_by_company:
            jobs_by_company[company] = []
            company_order.append(company)
        jobs_by_company[company].append(job)

    balanced = []
    largest_company = max((len(items) for items in jobs_by_company.values()), default=0)
    rounds = (
        min(largest_company, max_per_company)
        if max_per_company is not None
        else largest_company
    )
    for index in range(rounds):
        for company in company_order:
            company_jobs = jobs_by_company[company]
            if index < len(company_jobs):
                balanced.append(company_jobs[index])
    return balanced


def _change_job_page(delta):
    st.session_state["job_alert_page"] = max(
        0,
        int(st.session_state.get("job_alert_page", 0)) + delta,
    )


def _display_time(value):
    if not value:
        return "Not available"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    ist = timezone(timedelta(hours=5, minutes=30))
    return value.astimezone(ist).strftime("%d %b %Y, %I:%M %p IST")


def _display_job_time(job, value):
    if not value:
        return "Not available"
    source_platform = (job.get("source") or "").split(":", 1)[0]
    if source_platform in {"amazon", "workday"}:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        ist = timezone(timedelta(hours=5, minutes=30))
        return value.astimezone(ist).strftime("%d %b %Y")
    return _display_time(value)


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
        st.caption("Scans the next six due companies without blocking on every configured source.")
        if st.button("Scan due companies", width="stretch"):
            with st.spinner("Checking the next due career sites…"):
                try:
                    result = run_due_company_scans(batch_size=6)
                except Exception as error:
                    st.error(f"Scan failed: {error}")
                else:
                    message = (
                        f"{result['successful_sources']} sources checked; "
                        f"{result['inserted_count']} new jobs; "
                        f"{result.get('remaining_due_sources', 0)} sources remain due."
                    )
                    if result["status"] == "failed":
                        st.warning(
                            message
                            + " The selected external career sites were unavailable and will retry later."
                        )
                    else:
                        st.success(message)


def _render_compensation(job):
    company_name = job["company"]
    reports = get_compensation_reports(company_name)
    extracted = extract_compensation(job.get("description", ""))

    if reports:
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
        for report in reports:
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
    else:
        st.caption("No curated company salary band is stored for this role.")

    if extracted["published_ranges"]:
        st.write("**Compensation published in this job description (INR)**")
        rates = None
        for value in extracted["published_ranges"]:
            converted = compensation_range_in_inr(value, rates)
            if converted:
                st.write(f"- **{converted}**")
                st.caption(f"Original employer amount: {value}")
            else:
                st.write(f"- {value}")
    reward_signals = []
    if extracted["equity_mentioned"]:
        reward_signals.append("Equity/RSU mentioned")
    if extracted["bonus_mentioned"]:
        reward_signals.append("Bonus mentioned")
    reward_signals.extend(extracted["benefits"])
    if reward_signals:
        st.caption(" · ".join(reward_signals))

    links = get_research_links(company_name, job["title"])
    st.markdown(f"[Search Glassdoor, AmbitionBox and Levels.fyi ↗]({links['Salary reviews']})")
    st.caption(
        "External salary reviews are candidate-reported and may vary by level, location and date."
    )


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
            f"Source-backed candidate experience · {interview['confidence'].title()} confidence"
        )
        st.write("**Candidate-report sources**")
        for source in interview["sources"]:
            st.markdown(f"- [{source['label']} ↗]({source['url']})")
        if interview["steps"]:
            st.write("**Rounds described in those reports**")
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
    else:
        st.warning(
            "No sourced company-specific candidate experience is stored yet. "
            "A generalized interview process is intentionally not shown."
        )
        st.markdown(
            "Find candidate reports: "
            + " · ".join(f"[{label} ↗]({url})" for label, url in links.items())
        )


def _render_company_history(company_name):
    history = fetch_company_history(company_name)
    if not history:
        st.caption("A reliable brief company history is not available.")
        return
    st.write(history["summary"])
    if history.get("url"):
        st.markdown(f"[Source: {history['source']} ↗]({history['url']})")


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


def _render_application_profile():
    st.subheader("Application Profile")
    st.caption(
        "Saved only in this signed-in browser session. It is not written to PostgreSQL. "
        "The portal prepares answers for review but never submits an application."
    )
    profile = st.session_state.get("job_application_profile", {})
    with st.form("job_application_profile_form"):
        identity = st.columns(3)
        full_name = identity[0].text_input("Full name", value=profile.get("full_name", ""))
        email = identity[1].text_input("Email", value=profile.get("email", ""))
        phone = identity[2].text_input("Phone", value=profile.get("phone", ""))
        links = st.columns(3)
        current_location = links[0].text_input(
            "Current location",
            value=profile.get("current_location", ""),
        )
        linkedin_url = links[1].text_input(
            "LinkedIn URL",
            value=profile.get("linkedin_url", ""),
        )
        portfolio_url = links[2].text_input(
            "Portfolio / GitHub URL",
            value=profile.get("portfolio_url", ""),
        )
        work = st.columns(4)
        years_experience = work[0].text_input(
            "Years of experience",
            value=profile.get("years_experience", ""),
        )
        notice_period = work[1].text_input(
            "Notice period",
            value=profile.get("notice_period", ""),
        )
        current_company = work[2].text_input(
            "Current company",
            value=profile.get("current_company", ""),
        )
        expected_salary = work[3].text_input(
            "Expected salary",
            value=profile.get("expected_salary", ""),
        )
        current_salary = st.text_input(
            "Current salary",
            value=profile.get("current_salary", ""),
        )
        eligibility = st.columns(3)
        work_authorized = eligibility[0].selectbox(
            "Authorized to work in target location?",
            ["", "Yes", "No"],
            index=["", "Yes", "No"].index(profile.get("work_authorized", "")),
        )
        requires_sponsorship = eligibility[1].selectbox(
            "Require visa sponsorship?",
            ["", "Yes", "No"],
            index=["", "Yes", "No"].index(profile.get("requires_sponsorship", "")),
        )
        willing_to_relocate = eligibility[2].selectbox(
            "Willing to relocate?",
            ["", "Yes", "No"],
            index=["", "Yes", "No"].index(profile.get("willing_to_relocate", "")),
        )
        save_profile = st.form_submit_button("Save profile for this session", type="primary")
    if save_profile:
        st.session_state["job_application_profile"] = {
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "current_location": current_location,
            "linkedin_url": linkedin_url,
            "portfolio_url": portfolio_url,
            "years_experience": years_experience,
            "notice_period": notice_period,
            "current_company": current_company,
            "current_salary": current_salary,
            "expected_salary": expected_salary,
            "work_authorized": work_authorized,
            "requires_sponsorship": requires_sponsorship,
            "willing_to_relocate": willing_to_relocate,
        }
        profile = st.session_state["job_application_profile"]
        st.success("Application profile is ready for review packets.")

    completion = profile_completion(profile)
    st.progress(completion["percent"] / 100, text=f"{completion['percent']}% complete")
    if completion["missing"]:
        st.caption("Missing: " + " · ".join(completion["missing"]))


def _render_application_review(job):
    profile = st.session_state.get("job_application_profile", {})
    review = build_application_review(job, profile)
    completion = review["completion"]
    if not profile:
        st.info("Complete the Application Profile tab once to prepare reusable answers.")
        return
    st.caption(
        f"{completion['completed']}/{completion['total']} standard fields ready. "
        "Review every answer before continuing to the official portal."
    )
    st.dataframe(review["answers"], width="stretch", hide_index=True)
    st.download_button(
        "Download review packet",
        data=review["download"],
        file_name=f"{job['company']}-{job['id']}-application-review.json",
        mime="application/json",
        key=f"download_application_review_{job['id']}",
    )
    st.link_button(
        "Open official application for final review ↗",
        job["job_url"],
        width="stretch",
    )
    st.warning(
        "The portal does not press Submit. External ATS forms, CAPTCHA and legal declarations "
        "must be reviewed and completed by you."
    )


def _filter_jobs(
    jobs,
    location_scope,
    sector_scope,
    company_scope,
    search_query,
    priority_names,
):
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
        if sector_scope != "All sectors" and job["sector"] != sector_scope:
            continue
        if company_scope != "All companies" and job["company"] != company_scope:
            continue
        if search_query and search_query not in (
            f"{job['company']} {job['title']} {job['location']} "
            f"{job['description']}"
        ).lower():
            continue
        filtered.append(job)
    return filtered


def _render_sector_demand(jobs):
    if not jobs:
        st.info("No active jobs are available for sector analysis.")
        return
    rows = []
    for sector in sorted({job["sector"] for job in jobs}):
        sector_jobs = [job for job in jobs if job["sector"] == sector]
        rows.append(
            {
                "Sector": sector,
                "Active jobs": len(sector_jobs),
                "Companies": len({job["company"] for job in sector_jobs}),
            }
        )
    demand = pd.DataFrame(rows).sort_values(
        ["Active jobs", "Companies"],
        ascending=False,
    )
    leader = demand.iloc[0]
    st.metric(
        "Highest demand sector",
        leader["Sector"],
        f"{int(leader['Active jobs'])} active matching jobs",
    )
    st.caption(
        "Demand is measured from currently active matching postings in official company feeds."
    )
    st.bar_chart(demand.set_index("Sector")["Active jobs"])
    st.dataframe(demand, hide_index=True, width="stretch")

    st.subheader("Companies by sector")
    for sector in demand["Sector"]:
        sector_jobs = [job for job in jobs if job["sector"] == sector]
        company_counts = {}
        for job in sector_jobs:
            company_counts[job["company"]] = company_counts.get(job["company"], 0) + 1
        companies = sorted(
            company_counts.items(),
            key=lambda item: (-item[1], item[0].lower()),
        )
        with st.expander(f"{sector} · {len(sector_jobs)} jobs · {len(companies)} companies"):
            st.write(" · ".join(f"{company} ({count})" for company, count in companies))


@st.fragment
def _render_job(username, job):
    with st.container(border=True):
        header_slot = st.empty()
        current_status = st.session_state.get(
            f"job_status_override::{job['id']}",
            job["status"],
        )
        posted_value = job.get("posted_at") or job.get("first_seen_at")
        posted_label = "Posted" if job.get("posted_at") else "First discovered"
        st.caption(
            f"{job['company']} · {job['location']} · {job['work_mode']} · "
            f"{posted_label} {_display_job_time(job, posted_value)}"
        )
        if job.get("last_seen_at"):
            st.caption(f"Verified in official feed {_display_time(job['last_seen_at'])}")
        if not job.get("is_active", True):
            st.warning("This saved/applied posting is no longer present in the latest official feed.")
        signals = _role_signals(job["description"])
        if signals:
            st.caption("Skills: " + " · ".join(signals))
        company = get_company_metadata(job["source"], job["company"])
        compact_links = [f"[Apply ↗]({job['job_url']})"]
        if company["careers_url"]:
            compact_links.append(f"[Careers ↗]({company['careers_url']})")
        st.markdown(" · ".join(compact_links))

        if st.toggle(
            "Evidence",
            key=f"evidence_job_{job['id']}",
            help="Show salary reviews, stock performance and interview reports for this company.",
        ):
            selected_evidence = lazy_tab(
                ["Salary reviews", "Stock", "Interview reports", "Company history"],
                f"job_evidence_{job['id']}",
                "Evidence view",
            )
            if selected_evidence == "Salary reviews":
                _render_compensation(job)
            elif selected_evidence == "Stock":
                _render_stock(company, job["id"])
            elif selected_evidence == "Interview reports":
                _render_interview(job["company"], job["title"])
            else:
                _render_company_history(job["company"])

        if current_status == "applied":
            st.success("Applied")
        elif st.button(
            "Mark as applied",
            key=f"apply_job_{job['id']}",
            width="stretch",
            help="Record that you applied on the employer's official website.",
        ):
            if update_job_status(username, job["id"], "applied"):
                current_status = "applied"

        if current_status != job["status"]:
            st.session_state[f"job_status_override::{job['id']}"] = current_status
            _invalidate_job_cache()
            st.toast(f"Job marked {STATUS_LABELS[current_status]}.")

        with header_slot.container():
            title_col, status_col = st.columns([5, 1])
            title_col.subheader(job["title"])
            status_col.caption(
                STATUS_LABELS.get(current_status, current_status.title())
            )


def render_job_alerts():
    username = st.session_state.get("user")
    role = st.session_state.get("role", "user")

    st.title("Job Alerts")

    _render_scan_status(is_admin=role == "admin")
    selected_workspace = lazy_tab(
        ["Jobs", "Applied", "Sector demand", "Priority companies", "Application Profile"],
        "job_alert_workspace",
        "Job workspace",
    )

    if selected_workspace == "Jobs":
        priority_names = {
            company["company"] for company in load_priority_companies()
        }
        sector_options = ["All sectors"] + sorted(
            set(_source_sector_lookup().values())
            | {"Enterprise Software & Cloud", "Retail & E-commerce"}
        )
        company_options = ["All companies"] + sorted(
            {source["company"] for source in load_job_sources()}
            | {"Microsoft"}
        )
        with st.form("job_alert_filters"):
            location_col, sector_col, company_col = st.columns(3)
            location_scope = location_col.selectbox(
                "Location",
                ["All jobs", "Remote", "India", "Priority companies"],
                key="job_alert_location_filter",
            )
            sector_scope = sector_col.selectbox(
                "Sector",
                sector_options,
                key="job_alert_sector_filter",
            )
            company_scope = company_col.selectbox(
                "Company",
                company_options,
                key="job_alert_company_filter",
            )
            search_query = st.text_input(
                "Search jobs",
                placeholder="Company, title, location or skill",
                key="job_alert_search",
            )
            apply_filters = st.form_submit_button("Apply filters")
        if apply_filters:
            st.session_state["job_alert_page"] = 0

        jobs = _jobs_with_sectors(_load_jobs_cached(username, "Active"))
        filtered_jobs = _filter_jobs(
            jobs,
            location_scope,
            sector_scope,
            company_scope,
            search_query,
            priority_names,
        )
        company_count = len({job["company"] for job in filtered_jobs})
        jobs = _balance_jobs(filtered_jobs)

        if not jobs:
            st.info(
                "No jobs match these filters. Change the filters or check Priority companies "
                "for direct official career links."
            )
            return

        total_pages = max(1, (len(jobs) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(
            int(st.session_state.get("job_alert_page", 0)),
            total_pages - 1,
        )
        st.session_state["job_alert_page"] = page
        start = page * PAGE_SIZE
        page_jobs = jobs[start : start + PAGE_SIZE]

        summary = (
            f"{len(filtered_jobs)} matching jobs from {company_count} companies"
            " · company-diverse order, newest within each organization"
        )
        st.caption(summary)
        previous_col, page_col, next_col = st.columns([1, 3, 1])
        previous_col.button(
            "← Previous",
            disabled=page == 0,
            on_click=_change_job_page,
            args=(-1,),
            width="stretch",
        )
        page_col.markdown(
            f"<div style='text-align:center;padding:.4rem'>Page {page + 1} of {total_pages}</div>",
            unsafe_allow_html=True,
        )
        next_col.button(
            "Next →",
            disabled=page >= total_pages - 1,
            on_click=_change_job_page,
            args=(1,),
            width="stretch",
        )
        for job in page_jobs:
            _render_job(username, job)

    elif selected_workspace == "Applied":
        applied_jobs = _jobs_with_sectors(_load_jobs_cached(username, "Applied"))
        if not applied_jobs:
            st.info("Jobs you mark as applied will appear here.")
        else:
            st.caption(f"{len(applied_jobs)} applied jobs")
            for job in applied_jobs:
                _render_job(username, job)
    elif selected_workspace == "Sector demand":
        active_jobs = _jobs_with_sectors(_load_jobs_cached(username, "Active"))
        _render_sector_demand(active_jobs)
    elif selected_workspace == "Priority companies":
        priority_companies = load_priority_companies()
        active_jobs = _load_jobs_cached(username, "Active")
        _render_priority_companies(priority_companies, active_jobs)
    else:
        _render_application_profile()
