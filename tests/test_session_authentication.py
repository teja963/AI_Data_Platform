from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_login_is_not_restored_from_browser_cookies():
    app_source = (ROOT / "app.py").read_text()

    assert "CookieController" not in app_source
    assert "_restore_persistent_login" not in app_source
    assert "_persist_login" not in app_source
    assert "persistent_cookie_user" not in app_source


def test_cookie_controller_dependency_is_removed():
    requirements = (ROOT / "requirements.txt").read_text().lower()

    assert "streamlit-cookies-controller" not in requirements
