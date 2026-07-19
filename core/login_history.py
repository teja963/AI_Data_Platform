from datetime import datetime
from functools import lru_cache

from core.db import Base, SessionLocal, engine
from core.models import LoginEvent


@lru_cache(maxsize=1)
def ensure_login_history_schema():
    Base.metadata.create_all(bind=engine, tables=[LoginEvent.__table__])


def record_login(user_id, username):
    ensure_login_history_schema()
    session = SessionLocal()
    try:
        session.add(LoginEvent(user_id=user_id, username=username, logged_in_at=datetime.utcnow()))
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
