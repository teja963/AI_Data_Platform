from functools import lru_cache

from core.constants import (
    ADMIN_SECTION_LABEL,
    ARCHITECTURE_SECTION_LABEL,
    CLOUD_SECTION_LABEL,
    DEVOPS_SECTION_LABEL,
    PROJECTS_SECTION_LABEL,
    SECTION_ORDER,
)
from core.db import Base, SessionLocal, engine
from core.models import User, UserSectionAccess


@lru_cache(maxsize=1)
def ensure_access_schema():
    Base.metadata.create_all(bind=engine, tables=[UserSectionAccess.__table__])
    from core.section_migrations import migrate_access_section_labels

    migrate_access_section_labels()


def default_user_sections(is_admin=False):
    if is_admin:
        return list(SECTION_ORDER)
    hidden_by_default = {
        ADMIN_SECTION_LABEL,
        ARCHITECTURE_SECTION_LABEL,
        CLOUD_SECTION_LABEL,
        DEVOPS_SECTION_LABEL,
        PROJECTS_SECTION_LABEL,
    }
    return [section for section in SECTION_ORDER if section not in hidden_by_default]


def _normalized_identity(value):
    return "".join(character for character in (value or "").lower() if character.isalnum())


def can_view_architecture(username, role="user", full_name=None):
    if role == "admin":
        return True
    allowed_identities = {"harika", "harikapriya", "haripriya"}
    return bool(
        {
            _normalized_identity(username),
            _normalized_identity(full_name),
        }
        & allowed_identities
    )


def user_can_view_architecture(username, role="user"):
    if role == "admin":
        return True
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        return bool(user and can_view_architecture(user.username, role, user.full_name))
    finally:
        session.close()


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

        restricted_sections_allowed = can_view_architecture(user.username, role, user.full_name)
        restricted_sections = {
            ARCHITECTURE_SECTION_LABEL,
            CLOUD_SECTION_LABEL,
            DEVOPS_SECTION_LABEL,
        }
        rows = session.query(UserSectionAccess).filter_by(user_id=user.id).all()
        if not rows:
            allowed = set(default_user_sections(is_admin=False))
            if restricted_sections_allowed:
                allowed.update(restricted_sections)
            return [section for section in SECTION_ORDER if section in allowed]

        allowed = {row.section for row in rows if row.allowed}
        if restricted_sections_allowed:
            allowed.update(restricted_sections)
        else:
            allowed.difference_update(restricted_sections)
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
