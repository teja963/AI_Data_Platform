from core.constants import CLOUD_SECTION_LABEL, SPARK_SECTION_LABEL
from core.db import SessionLocal


SECTION_LABEL_MIGRATIONS = (
    ("Cloud", CLOUD_SECTION_LABEL),
    ("Spark", SPARK_SECTION_LABEL),
)


def _latest(left, right):
    values = [value for value in (left, right) if value is not None]
    return max(values) if values else None


def migrate_access_section_labels():
    from core.models import UserSectionAccess

    session = SessionLocal()
    try:
        for legacy_label, current_label in SECTION_LABEL_MIGRATIONS:
            if legacy_label == current_label:
                continue
            legacy_rows = (
                session.query(UserSectionAccess)
                .filter_by(section=legacy_label)
                .all()
            )
            for legacy in legacy_rows:
                current = (
                    session.query(UserSectionAccess)
                    .filter_by(user_id=legacy.user_id, section=current_label)
                    .first()
                )
                if current:
                    current.allowed = bool(current.allowed or legacy.allowed)
                    current.updated_at = _latest(current.updated_at, legacy.updated_at)
                    session.delete(legacy)
                else:
                    legacy.section = current_label
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def migrate_activity_section_labels():
    from core.models import (
        SectionPerformanceDaily,
        UserActivityDaily,
        UserActivitySummary,
    )

    session = SessionLocal()
    try:
        for legacy_label, current_label in SECTION_LABEL_MIGRATIONS:
            if legacy_label == current_label:
                continue
            _merge_activity_model(
                session,
                UserActivitySummary,
                ("user_id",),
                legacy_label,
                current_label,
                additive=("total_seconds", "visit_count"),
            )
            _merge_activity_model(
                session,
                UserActivityDaily,
                ("user_id", "activity_date"),
                legacy_label,
                current_label,
                additive=("total_seconds", "visit_count"),
            )
            _merge_activity_model(
                session,
                SectionPerformanceDaily,
                ("user_id", "activity_date"),
                legacy_label,
                current_label,
                additive=("render_count", "total_ms"),
                maximum=("max_ms",),
                latest_value=("last_ms",),
            )
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def _merge_activity_model(
    session,
    model,
    key_fields,
    legacy_label="Cloud",
    current_label=CLOUD_SECTION_LABEL,
    additive=(),
    maximum=(),
    latest_value=(),
):
    legacy_rows = session.query(model).filter_by(section=legacy_label).all()
    for legacy in legacy_rows:
        key = {field: getattr(legacy, field) for field in key_fields}
        current = (
            session.query(model)
            .filter_by(section=current_label, **key)
            .first()
        )
        if not current:
            legacy.section = current_label
            continue
        for field in additive:
            setattr(
                current,
                field,
                int(getattr(current, field) or 0) + int(getattr(legacy, field) or 0),
            )
        for field in maximum:
            setattr(
                current,
                field,
                max(int(getattr(current, field) or 0), int(getattr(legacy, field) or 0)),
            )
        if _latest(current.last_seen, legacy.last_seen) == legacy.last_seen:
            for field in latest_value:
                setattr(current, field, getattr(legacy, field))
        current.last_seen = _latest(current.last_seen, legacy.last_seen)
        current.updated_at = _latest(current.updated_at, legacy.updated_at)
        session.delete(legacy)
