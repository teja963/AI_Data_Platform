import json


PROFILE_FIELDS = (
    ("full_name", "Full name"),
    ("email", "Email"),
    ("phone", "Phone"),
    ("current_location", "Current location"),
    ("linkedin_url", "LinkedIn"),
    ("portfolio_url", "Portfolio / GitHub"),
    ("years_experience", "Years of experience"),
    ("notice_period", "Notice period"),
    ("current_company", "Current company"),
    ("current_salary", "Current salary"),
    ("expected_salary", "Expected salary"),
    ("work_authorized", "Authorized to work in target location"),
    ("requires_sponsorship", "Requires visa sponsorship"),
    ("willing_to_relocate", "Willing to relocate"),
)


def profile_completion(profile):
    profile = profile or {}
    completed = sum(bool(str(profile.get(key, "")).strip()) for key, _ in PROFILE_FIELDS)
    return {
        "completed": completed,
        "total": len(PROFILE_FIELDS),
        "percent": round((completed / len(PROFILE_FIELDS)) * 100) if PROFILE_FIELDS else 100,
        "missing": [label for key, label in PROFILE_FIELDS if not str(profile.get(key, "")).strip()],
    }


def build_application_review(job, profile):
    profile = profile or {}
    completion = profile_completion(profile)
    answers = [
        {"field": label, "answer": str(profile.get(key, "")).strip() or "REVIEW REQUIRED"}
        for key, label in PROFILE_FIELDS
    ]
    packet = {
        "job": {
            "company": job.get("company"),
            "title": job.get("title"),
            "location": job.get("location"),
            "official_url": job.get("job_url"),
        },
        "candidate_answers": {item["field"]: item["answer"] for item in answers},
        "review": {
            "completion_percent": completion["percent"],
            "missing_fields": completion["missing"],
            "final_submit_required": True,
            "instruction": "Review every answer on the official careers page and submit manually.",
        },
    }
    return {
        "answers": answers,
        "completion": completion,
        "packet": packet,
        "download": json.dumps(packet, indent=2, ensure_ascii=False),
    }
