from cryptography.fernet import Fernet

from core.application_agent import (
    _custom_profile_value,
    _field_key,
    _profile_value,
    worker_paths,
)
from core.application_workflow import (
    _decrypt_json,
    _encrypt_json,
    _site_host,
    encryption_configured,
)


def test_application_profile_encryption_round_trip(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    profile = {"full_name": "Candidate Name", "email": "candidate@example.com"}

    encrypted = _encrypt_json(profile)

    assert b"candidate@example.com" not in encrypted
    assert _decrypt_json(encrypted) == profile
    assert encryption_configured() is True


def test_field_mapping_uses_only_known_profile_answers():
    assert _field_key("Candidate email address") == "email"
    assert _field_key("Will you now or later require visa sponsorship?") == (
        "requires_sponsorship"
    )
    assert _field_key("Voluntary self identification") is None


def test_name_is_split_for_separate_first_and_last_name_fields():
    profile = {"full_name": "Ada Lovelace"}

    assert _profile_value(profile, "first_name") == "Ada"
    assert _profile_value(profile, "last_name") == "Lovelace"


def test_explicit_custom_answer_matches_question_fragment_only():
    profile = {
        "custom_answers": (
            "Highest degree = Bachelor of Technology\n"
            "Are you at least 18 years old = Yes"
        )
    }

    assert (
        _custom_profile_value(profile, "What is your highest degree?")
        == "Bachelor of Technology"
    )
    assert _custom_profile_value(profile, "Voluntary disability status") == ""


def test_site_credentials_are_scoped_to_exact_hostname():
    assert (
        _site_host("https://company.wd5.myworkdayjobs.com/jobs/123")
        == "company.wd5.myworkdayjobs.com"
    )


def test_worker_paths_separate_browser_state_and_artifacts(monkeypatch, tmp_path):
    monkeypatch.setenv("PLAYWRIGHT_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("PLAYWRIGHT_STATE_DIR", str(tmp_path / "state"))

    paths = worker_paths(42, "user/1", "greenhouse:example")

    assert paths["artifact_dir"].name == "draft-42"
    assert paths["screenshot_path"].name == "review.png"
    assert paths["browser_state_dir"].is_dir()
