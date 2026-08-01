from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import User, UserActivityDaily
from core.section_migrations import _merge_activity_model


def test_cloud_activity_rows_merge_without_losing_history():
    engine = create_engine("sqlite:///:memory:")
    User.__table__.create(engine)
    UserActivityDaily.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    try:
        user = User(username="migration-user", password="hash")
        session.add(user)
        session.flush()
        session.add_all(
            [
                UserActivityDaily(
                    user_id=user.id,
                    section="Cloud",
                    activity_date="2026-08-01",
                    total_seconds=120,
                    visit_count=2,
                ),
                UserActivityDaily(
                    user_id=user.id,
                    section="Cloud Platform",
                    activity_date="2026-08-01",
                    total_seconds=30,
                    visit_count=1,
                ),
            ]
        )
        session.commit()

        _merge_activity_model(
            session,
            UserActivityDaily,
            ("user_id", "activity_date"),
            additive=("total_seconds", "visit_count"),
        )
        session.commit()

        rows = session.query(UserActivityDaily).all()
        assert len(rows) == 1
        assert rows[0].section == "Cloud Platform"
        assert rows[0].total_seconds == 150
        assert rows[0].visit_count == 3
    finally:
        session.close()


def test_spark_activity_rows_migrate_to_spark_flink_label():
    engine = create_engine("sqlite:///:memory:")
    User.__table__.create(engine)
    UserActivityDaily.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    try:
        user = User(username="spark-user", password="hash")
        session.add(user)
        session.flush()
        session.add(
            UserActivityDaily(
                user_id=user.id,
                section="Spark",
                activity_date="2026-08-01",
                total_seconds=75,
                visit_count=1,
            )
        )
        session.commit()

        _merge_activity_model(
            session,
            UserActivityDaily,
            ("user_id", "activity_date"),
            "Spark",
            "Spark / Flink",
            additive=("total_seconds", "visit_count"),
        )
        session.commit()

        row = session.query(UserActivityDaily).one()
        assert row.section == "Spark / Flink"
        assert row.total_seconds == 75
    finally:
        session.close()
