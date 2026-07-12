import streamlit as st
import pandas as pd
from core.db import SessionLocal, engine
from core.models import User
from core.activity import ensure_activity_schema
from core.progress import _ensure_progress_schema
from core.views import ensure_reporting_views


@st.cache_data(ttl=300, show_spinner=False)
def _read_sql_cached(query, params=None):
    return pd.read_sql(query, engine, params=params)


def render_admin():
    if st.session_state.get("role") != "admin":
        st.error("Unauthorized access.")
        return

    st.title("🛡️ Admin Dashboard")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "👥 User Management",
        "📈 Login Activity",
        "⏱️ Time Analytics",
        "📚 Progress",
        "🔍 SQL Console"
    ])

    # =========================
    # 👥 USER MANAGEMENT
    # =========================
    with tab1:
        st.subheader("👥 Manage Users")

        search = st.text_input("🔍 Search by Username or Email", "").lower()

        session = SessionLocal()
        try:
            query = session.query(User)

            if search:
                query = query.filter(
                    (User.username.ilike(f"%{search}%")) |
                    (User.email.ilike(f"%{search}%"))
                )

            users = query.order_by(User.created_at.desc()).all()

            if not users:
                st.info("No users found.")
            else:
                # -------- TABLE VIEW --------
                user_data = []
                for u in users:
                    display_name = u.full_name if u.full_name else u.username

                    user_data.append({
                        "ID": u.id,
                        "Name": display_name,
                        "Username": u.username,
                        "Email": u.email,
                        "Verified": "✅" if u.email_verified else "❌",
                        "Approved": "✅" if u.is_approved else "⏳",
                        "Last Login": u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else "Never"
                    })

                st.dataframe(pd.DataFrame(user_data), width="stretch", hide_index=True)

                st.divider()

                # -------- SUMMARY --------
                st.markdown("### 📊 User Status Summary")
                total_users = len(users)
                pending_count = len([u for u in users if not u.is_approved])
                approved_count = len([u for u in users if u.is_approved])

                st.info(f"Total: {total_users} | Pending: {pending_count} | Approved: {approved_count}")

                st.divider()

                # -------- PENDING --------
                st.markdown("### 🔔 Pending Approvals")

                pending = [u for u in users if not u.is_approved]

                if not pending:
                    st.success("No pending users for approval.")
                else:
                    for u in pending:
                        col1, col2, col3 = st.columns([4, 1, 1])

                        status = "✅ Verified" if u.email_verified else "❌ Not Verified"
                        col1.write(f"**{u.username}** ({u.email}) — {status}")

                        # Approve
                        if col2.button("Approve", key=f"approve_{u.id}"):
                            u.is_approved = True
                            session.commit()
                            st.success(f"{u.username} approved")
                            st.rerun()

                        # Reject/Delete
                        if col3.button("Reject", key=f"reject_{u.id}"):
                            session.delete(u)
                            session.commit()
                            st.warning(f"{u.username} rejected & removed")
                            st.rerun()

                st.divider()

                # -------- ALL USER ACTIONS --------
                st.markdown("### ⚙️ Advanced Controls")

                for u in users:
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

                    col1.write(f"{u.username} ({u.email})")

                    # Toggle approval
                    if u.is_approved:
                        if col2.button("Revoke", key=f"revoke_{u.id}"):
                            u.is_approved = False
                            session.commit()
                            st.warning(f"{u.username} approval revoked")
                            st.rerun()
                    else:
                        if col2.button("Approve", key=f"approve2_{u.id}"):
                            u.is_approved = True
                            session.commit()
                            st.success(f"{u.username} approved")
                            st.rerun()

                    # Toggle verification (debug)
                    if col3.button("Toggle Verify", key=f"verify_{u.id}"):
                        u.email_verified = not u.email_verified
                        session.commit()
                        st.info(f"{u.username} verification updated")
                        st.rerun()

                    # Delete user
                    if col4.button("Delete", key=f"delete_{u.id}"):
                        session.delete(u)
                        session.commit()
                        st.error(f"{u.username} deleted")
                        st.rerun()

        finally:
            session.close()

    # =========================
    # 📈 USER ACTIVITY
    # =========================
    with tab2:
        st.subheader("📈 Recent User Logins")

        df_activity = _read_sql_cached(
            """
            SELECT username, email, last_login, created_at 
            FROM users 
            WHERE last_login IS NOT NULL
            """,
        )

        if df_activity.empty:
            st.info("No login activity recorded yet.")
        else:
            df_activity = df_activity.sort_values("last_login", ascending=False)
            st.dataframe(df_activity.reset_index(drop=True), width="stretch")

    # =========================
    # ⏱️ TIME ANALYTICS
    # =========================
    with tab3:
        st.subheader("⏱️ Platform Time Analytics")
        try:
            ensure_activity_schema()
            ensure_reporting_views()
            date_filter = st.date_input("Select analytics date")
            df_daily = _read_sql_cached(
                """
                SELECT *
                FROM admin_user_daily_activity_view
                WHERE activity_date = %(activity_date)s
                ORDER BY total_seconds DESC, last_seen DESC
                """,
                params={"activity_date": date_filter.isoformat()},
            )
            df_time = _read_sql_cached(
                """
                SELECT
                    u.username,
                    a.section,
                    a.total_seconds,
                    ROUND(a.total_seconds / 60.0, 1) AS total_minutes,
                    a.visit_count,
                    a.last_seen
                FROM user_activity_summary a
                JOIN users u ON u.id = a.user_id
                ORDER BY a.total_seconds DESC, a.last_seen DESC
                """,
            )

            if df_daily.empty:
                st.info("No user activity recorded for the selected date yet.")
            else:
                total_seconds = int(df_daily["total_seconds"].sum())
                active_users = df_daily["username"].nunique()
                top_section = df_daily.groupby("section")["total_seconds"].sum().sort_values(ascending=False).index[0]

                m1, m2, m3 = st.columns(3)
                m1.metric("Tracked Time Today", f"{round(total_seconds / 60, 1)} min")
                m2.metric("Active Users", active_users)
                m3.metric("Top Section", top_section)

                st.markdown("#### Selected Date: Time By User And Section")
                st.dataframe(df_daily, width="stretch", hide_index=True)

                section_summary = (
                    df_daily.groupby("section", as_index=False)
                    .agg(total_seconds=("total_seconds", "sum"), users=("username", "nunique"), visits=("visit_count", "sum"))
                )
                section_summary["total_minutes"] = (section_summary["total_seconds"] / 60).round(1)
                section_summary = section_summary.sort_values("total_seconds", ascending=False)

                st.markdown("#### Selected Date: Section Summary")
                st.dataframe(section_summary, width="stretch", hide_index=True)

                user_summary = (
                    df_daily.groupby("username", as_index=False)
                    .agg(total_seconds=("total_seconds", "sum"), sections=("section", "nunique"), visits=("visit_count", "sum"))
                )
                user_summary["total_minutes"] = (user_summary["total_seconds"] / 60).round(1)
                user_summary = user_summary.sort_values("total_seconds", ascending=False)

                st.markdown("#### Selected Date: User Summary")
                st.dataframe(user_summary, width="stretch", hide_index=True)

            if not df_time.empty:
                with st.expander("Lifetime Summary"):
                    st.dataframe(df_time, width="stretch", hide_index=True)

            df_perf = _read_sql_cached(
                """
                SELECT *
                FROM admin_section_performance_view
                WHERE activity_date = %(activity_date)s
                ORDER BY avg_ms DESC, max_ms DESC
                """,
                params={"activity_date": date_filter.isoformat()},
            )

            st.markdown("#### Selected Date: Section Load Performance")
            if df_perf.empty:
                st.info("No section performance data recorded for the selected date yet.")
            else:
                p1, p2, p3 = st.columns(3)
                p1.metric("Avg Load", f"{round(df_perf['avg_ms'].mean(), 1)} ms")
                p2.metric("Slowest Load", f"{int(df_perf['max_ms'].max())} ms")
                p3.metric("Render Samples", int(df_perf["render_count"].sum()))
                st.dataframe(df_perf, width="stretch", hide_index=True)

                perf_section_summary = (
                    df_perf.groupby("section", as_index=False)
                    .agg(
                        renders=("render_count", "sum"),
                        avg_ms=("avg_ms", "mean"),
                        max_ms=("max_ms", "max"),
                        users=("username", "nunique"),
                    )
                    .sort_values("avg_ms", ascending=False)
                )
                perf_section_summary["avg_ms"] = perf_section_summary["avg_ms"].round(1)
                st.markdown("#### Selected Date: Performance By Section")
                st.dataframe(perf_section_summary, width="stretch", hide_index=True)
        except Exception as e:
            st.error(f"Time analytics unavailable: {e}")

    # =========================
    # 📚 PROGRESS
    # =========================
    with tab4:
        st.subheader("📚 User Question Progress")
        try:
            _ensure_progress_schema()
            ensure_reporting_views()
            df_progress = _read_sql_cached(
                """
                SELECT *
                FROM admin_progress_summary_view
                ORDER BY username, track
                """,
            )
            if df_progress.empty:
                st.info("No solved progress has been saved yet.")
            else:
                st.dataframe(df_progress, width="stretch", hide_index=True)
        except Exception as e:
            st.error(f"Progress summary unavailable: {e}")

    # =========================
    # 🔍 SQL CONSOLE
    # =========================
    with tab5:
        st.subheader("🔍 SQL Explorer")

        query_input = st.text_area(
            "Run read-only queries on users",
            "SELECT * FROM users LIMIT 10;"
        )

        if st.button("Execute Query"):
            try:
                df_res = pd.read_sql(query_input, engine)

                # Mask sensitive columns
                for col in ['password', 'otp_secret', 'otp_code']:
                    if col in df_res.columns:
                        df_res[col] = "********"

                st.dataframe(df_res, width="stretch")

            except Exception as e:
                st.error(f"SQL Error: {e}")