from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.progress as progress
import core.submissions as submissions
from core.models import CodingSubmission, Progress, User


def test_submission_and_solved_progress_share_one_write_path(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    User.__table__.create(engine)
    Progress.__table__.create(engine)
    CodingSubmission.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    user = User(username="coder", password="hash")
    session.add(user)
    session.commit()
    session.close()

    monkeypatch.setattr(submissions, "SessionLocal", factory)
    monkeypatch.setattr(submissions, "ensure_submission_schema", lambda: True)
    monkeypatch.setattr(progress, "_ensure_progress_schema", lambda: None)
    monkeypatch.setattr(progress, "cache_question_solved", lambda *_args: None)
    submissions.st.session_state["database_user_id::coder"] = user.id

    submissions.record_submission(
        "coder",
        "sql",
        "sql:business:1",
        "Question",
        True,
        12,
        "SELECT 1",
        "1 row",
        mark_solved=True,
    )

    session = factory()
    try:
        assert session.query(CodingSubmission).count() == 1
        assert session.query(Progress).count() == 1
        assert session.query(Progress).one().question_key == "sql:business:1"
    finally:
        session.close()
