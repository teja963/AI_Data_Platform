from core import loader
import pandas as pd


def _contains_type(value, expected_type):
    if isinstance(value, expected_type):
        return True
    if isinstance(value, dict):
        return any(_contains_type(item, expected_type) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_type(item, expected_type) for item in value)
    return False


def test_sql_questions_load_locally_without_postgresql(monkeypatch):
    loader._load_questions_cached.clear()
    monkeypatch.setattr(
        "core.views.ensure_reporting_views",
        lambda: (_ for _ in ()).throw(AssertionError("database path should not run")),
    )
    questions = loader._load_questions_cached("sql", "local-first-test")
    assert len(questions) >= 60


def test_warm_question_catalog_does_not_read_files_again(monkeypatch):
    loader._load_questions_cached.clear()
    first = loader._load_questions_cached("sql", "cache-test")
    monkeypatch.setattr(
        loader,
        "_load_local_questions",
        lambda _module: (_ for _ in ()).throw(AssertionError("cache miss")),
    )
    second = loader._load_questions_cached("sql", "cache-test")
    assert second == first


def test_python_questions_use_static_catalog_and_restore_runtime_types(monkeypatch):
    loader._load_questions_cached.clear()
    monkeypatch.setattr(
        loader,
        "load_question_bank",
        lambda _module: (_ for _ in ()).throw(AssertionError("bank fallback should not run")),
    )

    questions = loader._load_questions_cached("python", "static-python-catalog-test")
    assert len(questions) == 60
    assert _contains_type(questions, tuple)
    assert _contains_type(questions, pd.DataFrame)
