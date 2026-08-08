from streamlit.testing.v1 import AppTest


SAMPLE_JOB = """{
    "id": 1,
    "source": "greenhouse:example",
    "company": "Example",
    "title": "Data Engineer",
    "location": "Bengaluru, India",
    "work_mode": "onsite",
    "department": "Data",
    "description": "Build Python and SQL pipelines. USD 100,000 - 120,000 per year.",
    "job_url": "https://example.com/apply",
    "posted_at": None,
    "first_seen_at": None,
    "last_seen_at": None,
    "expires_at": None,
    "is_active": True,
    "match_score": 100,
    "match_reason": "data engineer",
    "status": "new",
}"""


def _run_job_app(workspace):
    app = AppTest.from_string(
        f"""
import streamlit as st
from modules.job_alerts import ui
st.session_state["user"] = "candidate"
st.session_state["role"] = "user"
st.session_state["job_alert_workspace"] = {workspace!r}
ui._load_jobs_cached = lambda username, status: [{SAMPLE_JOB}]
ui.load_priority_companies = lambda: []
ui.get_company_metadata = lambda source, company: {{
    "company": company,
    "category": "Product company",
    "platform": "Greenhouse",
    "careers_url": "https://example.com/careers",
    "ticker": None,
}}
ui.render_job_alerts()
"""
    )
    app.run(timeout=10)
    return app


def test_job_feed_renders_paginated_card_without_exception():
    app = _run_job_app("Jobs")
    assert not app.exception
    assert app.title[0].value == "Job Alerts"
    assert any(item.value == "Data Engineer" for item in app.subheader)


def test_application_profile_renders_without_database_query():
    app = _run_job_app("Application Profile")
    assert not app.exception
    assert any(item.value == "Application Profile" for item in app.subheader)
