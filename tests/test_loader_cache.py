from core import loader


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
