from core.application_assist import build_application_review, profile_completion
from modules.job_alerts.ui import _balance_jobs


def test_application_review_requires_manual_submit_and_marks_missing_fields():
    profile = {
        "full_name": "Candidate",
        "email": "candidate@example.com",
        "work_authorized": "Yes",
    }
    job = {
        "id": 1,
        "company": "Example",
        "title": "Data Engineer",
        "location": "Bengaluru",
        "job_url": "https://example.com/apply",
    }

    review = build_application_review(job, profile)

    assert review["packet"]["review"]["final_submit_required"] is True
    assert review["completion"]["percent"] < 100
    assert "Phone" in review["completion"]["missing"]
    assert "candidate@example.com" in review["download"]


def test_complete_application_profile_reports_full_completion():
    profile = {
        key: "No" if key == "requires_sponsorship" else "Yes"
        for key in (
            "full_name",
            "email",
            "phone",
            "current_location",
            "linkedin_url",
            "portfolio_url",
            "years_experience",
            "notice_period",
            "current_company",
            "current_salary",
            "expected_salary",
            "work_authorized",
            "requires_sponsorship",
            "willing_to_relocate",
        )
    }
    assert profile_completion(profile)["percent"] == 100


def test_balanced_job_feed_limits_each_company_without_changing_order():
    jobs = [
        {"id": 1, "company": "Amazon"},
        {"id": 2, "company": "Amazon"},
        {"id": 3, "company": "Amazon"},
        {"id": 4, "company": "Amazon"},
        {"id": 5, "company": "Microsoft"},
    ]

    balanced = _balance_jobs(jobs, max_per_company=2)

    assert [job["id"] for job in balanced] == [1, 5, 2]
