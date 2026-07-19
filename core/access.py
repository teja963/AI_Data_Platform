from functools import lru_cache

from core.constants import ADMIN_SECTION_LABEL, PROJECTS_SECTION_LABEL, SECTION_ORDER
from core.db import Base, SessionLocal, engine
from core.models import User, UserSectionAccess


@lru_cache(maxsize=1)
def ensure_access_schema():
    Base.metadata.create_all(bind=engine, tables=[UserSectionAccess.__table__])


def default_user_sections(is_admin=False):
    if is_admin:
        return list(SECTION_ORDER)
    hidden_by_default = {ADMIN_SECTION_LABEL, PROJECTS_SECTION_LABEL}
    return [section for section in SECTION_ORDER if section not in hidden_by_default]


def get_allowed_sections(username, role="user"):
    is_admin = role == "admin"
    if is_admin:
        return default_user_sections(is_admin=True)

    ensure_access_schema()
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            return default_user_sections(is_admin=False)

        rows = session.query(UserSectionAccess).filter_by(user_id=user.id).all()
        if not rows:
            return default_user_sections(is_admin=False)

        allowed = {row.section for row in rows if row.allowed}
        return [section for section in SECTION_ORDER if section in allowed]
    finally:
        session.close()


def set_allowed_sections(user_id, sections):
    ensure_access_schema()
    allowed = set(sections)
    session = SessionLocal()
    try:
        existing = {
            row.section: row
            for row in session.query(UserSectionAccess).filter_by(user_id=user_id).all()
        }
        for section in SECTION_ORDER:
            row = existing.get(section)
            if row is None:
                row = UserSectionAccess(user_id=user_id, section=section)
                session.add(row)
            row.allowed = section in allowed
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
