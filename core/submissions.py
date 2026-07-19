from core.db import Base, SessionLocal, engine
from core.models import CodingSubmission, User

_SUBMISSION_SCHEMA_READY = False

def ensure_submission_schema():
    global _SUBMISSION_SCHEMA_READY
    if _SUBMISSION_SCHEMA_READY:
        return True

    try:
        Base.metadata.create_all(bind=engine, tables=[CodingSubmission.__table__])
        _SUBMISSION_SCHEMA_READY = True
        return True
    except Exception:
        return False


def record_submission(username, track, question_key, question_title, correct, elapsed_ms, code="", result_summary=""):
    if not username:
        return

    if not ensure_submission_schema():
        return
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        submission = CodingSubmission(
            user_id=user.id if user else None,
            username=username,
            track=track,
            question_key=question_key,
            question_title=question_title,
            correct=bool(correct),
            elapsed_ms=int(max(elapsed_ms, 0)),
            code=(code or "")[:8000],
            result_summary=(result_summary or "")[:2000],
        )
        session.add(submission)
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def get_submission_stats(username, track, question_key=None):
    if not ensure_submission_schema():
        return {
            "total": 0,
            "accepted": 0,
            "accuracy": 0.0,
        }
    session = SessionLocal()
    try:
        query = session.query(CodingSubmission).filter_by(username=username, track=track)
        if question_key:
            query = query.filter_by(question_key=question_key)
        rows = query.all()
        total = len(rows)
        accepted = sum(1 for row in rows if row.correct)
        return {
            "total": total,
            "accepted": accepted,
            "accuracy": round((accepted / total) * 100, 1) if total else 0.0,
        }
    finally:
        session.close()


def get_recent_submissions(username, track, question_key=None, limit=10):
    if not ensure_submission_schema():
        return []
    session = SessionLocal()
    try:
        query = session.query(CodingSubmission).filter_by(username=username, track=track)
        if question_key:
            query = query.filter_by(question_key=question_key)
        rows = query.order_by(CodingSubmission.submitted_at.desc()).limit(limit).all()
        return [
            {
                "submitted_at": row.submitted_at,
                "status": "Accepted" if row.correct else "Wrong Answer",
                "runtime_ms": row.elapsed_ms,
                "question": row.question_title,
                "summary": row.result_summary or "",
            }
            for row in rows
        ]
    finally:
        session.close()
