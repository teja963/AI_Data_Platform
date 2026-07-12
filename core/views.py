from sqlalchemy import text


def ensure_reporting_views():
    """Create lightweight PostgreSQL views for static/admin reporting reads."""
    try:
        from core.db import engine

        statements = [
            """
            CREATE OR REPLACE VIEW coding_question_catalog_view AS
            SELECT
                id,
                module,
                category,
                difficulty,
                payload
            FROM questions
            """,
            """
            CREATE OR REPLACE VIEW admin_progress_summary_view AS
            SELECT
                u.username,
                p.track,
                COUNT(*) AS solved_questions,
                MAX(p.updated_at) AS last_progress_at
            FROM progress p
            JOIN users u ON u.id = p.user_id
            WHERE p.status = 'solved'
            GROUP BY u.username, p.track
            """,
            """
            CREATE OR REPLACE VIEW admin_user_daily_activity_view AS
            SELECT
                u.username,
                a.section,
                a.activity_date,
                a.total_seconds,
                ROUND(a.total_seconds / 60.0, 1) AS total_minutes,
                a.visit_count,
                a.last_seen
            FROM user_activity_daily a
            JOIN users u ON u.id = a.user_id
            """,
            """
            CREATE OR REPLACE VIEW admin_section_performance_view AS
            SELECT
                u.username,
                p.section,
                p.activity_date,
                p.render_count,
                p.total_ms,
                ROUND(p.total_ms::numeric / NULLIF(p.render_count, 0), 1) AS avg_ms,
                p.max_ms,
                p.last_ms,
                p.last_seen
            FROM section_performance_daily p
            JOIN users u ON u.id = p.user_id
            """,
        ]

        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
    except Exception:
        # Views are an optimization/reporting layer; app runtime should not fail if creation is blocked.
        return
