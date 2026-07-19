import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from core.access import default_user_sections, get_allowed_sections, set_allowed_sections
from core.constants import SECTION_ORDER
from core.db import SessionLocal, engine
from core.login_history import ensure_login_history_schema
from core.models import User
from core.activity import ensure_activity_schema
from core.progress import _ensure_progress_schema
from core.runtime import get_app_version, get_deploy_health
from core.views import ensure_reporting_views

IST = timezone(timedelta(hours=5, minutes=30))


def _format_ist_12h(value):
    if pd.isna(value):
        return "Never"
    if not isinstance(value, datetime):
        value = pd.to_datetime(value).to_pydatetime()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")


@st.cache_data(ttl=300, show_spinner=False)
def _read_sql_cached_with_version(query, app_version, params=None):
    return pd.read_sql(query, engine, params=params)


def _read_sql_cached(query, params=None):
    return _read_sql_cached_with_version(query, get_app_version(), params=params)


def render_admin():
    if st.session_state.get("role") != "admin":
        st.error("Unauthorized access.")
        return

    st.title("🛡️ Admin Dashboard")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "👥 User Management",
        "📈 Login Activity",
        "⏱️ Time Analytics",
        "📚 Progress",
        "🔍 SQL Console",
        "🚀 Deploy Health",
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
                active_30_days = sum(
                    1 for u in users
                    if u.last_login and u.last_login >= datetime.utcnow() - timedelta(days=30)
                )
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Users", len(users))
                c2.metric("Approved Users", len([u for u in users if u.is_approved]))
                c3.metric("Active Last 30 Days", active_30_days)

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
                        "Last Login": _format_ist_12h(u.last_login)
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
                    with st.expander(f"{u.username} ({u.email})"):
                        col1, col2, col3 = st.columns(3)

                        if u.is_approved:
                            if col1.button("Revoke Access", key=f"revoke_{u.id}"):
                                u.is_approved = False
                                session.commit()
                                st.warning(f"{u.username} approval revoked")
                                st.rerun()
                        else:
                            if col1.button("Approve Access", key=f"approve2_{u.id}"):
                                u.is_approved = True
                                session.commit()
                                st.success(f"{u.username} approved")
                                st.rerun()

                        if col2.button("Toggle Email Verify", key=f"verify_{u.id}"):
                            u.email_verified = not u.email_verified
                            session.commit()
                            st.info(f"{u.username} verification updated")
                            st.rerun()

                        if col3.button("Delete User", key=f"delete_{u.id}"):
                            session.delete(u)
                            session.commit()
                            st.error(f"{u.username} deleted")
                            st.rerun()

                        if u.role == "admin":
                            st.info("Admin users always have access to every section.")
                        else:
                            current_sections = get_allowed_sections(u.username, u.role)
                            selected_sections = st.multiselect(
                                "Visible Sections For This User",
                                SECTION_ORDER,
                                default=current_sections or default_user_sections(False),
                                key=f"sections_{u.id}",
                            )
                            if st.button("Save Section Access", key=f"save_sections_{u.id}"):
                                set_allowed_sections(u.id, selected_sections)
                                st.success(f"Section access updated for {u.username}")
                                st.rerun()

        finally:
            session.close()

    # =========================
    # 📈 USER ACTIVITY
    # =========================
    with tab2:
        st.subheader("📈 Login History - Last 30 Days")
        ensure_login_history_schema()

        df_activity = _read_sql_cached(
            """
            SELECT
                le.username,
                u.email,
                le.logged_in_at
            FROM login_events le
            LEFT JOIN users u ON u.id = le.user_id
            WHERE le.logged_in_at >= NOW() - INTERVAL '30 days'
            ORDER BY le.logged_in_at DESC
            """,
        )

        if df_activity.empty:
            st.info("No login activity recorded yet.")
        else:
            df_activity["Login Time"] = df_activity["logged_in_at"].apply(_format_ist_12h)
            df_activity = df_activity.rename(columns={"username": "Username", "email": "Email"})
            st.dataframe(df_activity[["Username", "Email", "Login Time"]], width="stretch", hide_index=True)

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
                m1.metric("Tracked Time", f"{round(total_seconds / 60, 1)} min")
                m2.metric("Active Users", active_users)
                m3.metric("Top Section", top_section)

                time_view = df_daily[["username", "section", "total_minutes", "last_seen"]].copy()
                time_view["last_seen"] = time_view["last_seen"].apply(_format_ist_12h)
                time_view = time_view.rename(columns={
                    "username": "Username",
                    "section": "Section",
                    "total_minutes": "Minutes Spent",
                    "last_seen": "Last Seen",
                })
                st.markdown("#### Time Spent By User And Section")
                st.dataframe(time_view, width="stretch", hide_index=True)

                section_summary = (
                    df_daily.groupby("section", as_index=False)
                    .agg(total_seconds=("total_seconds", "sum"), users=("username", "nunique"))
                )
                section_summary["total_minutes"] = (section_summary["total_seconds"] / 60).round(1)
                section_summary = section_summary.sort_values("total_seconds", ascending=False)

                st.markdown("#### Section Summary")
                st.dataframe(section_summary[["section", "users", "total_minutes"]], width="stretch", hide_index=True)

                user_summary = (
                    df_daily.groupby("username", as_index=False)
                    .agg(total_seconds=("total_seconds", "sum"), sections=("section", "nunique"))
                )
                user_summary["total_minutes"] = (user_summary["total_seconds"] / 60).round(1)
                user_summary = user_summary.sort_values("total_seconds", ascending=False)

                st.markdown("#### User Summary")
                st.dataframe(user_summary[["username", "sections", "total_minutes"]], width="stretch", hide_index=True)

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

            df_query_perf = _read_sql_cached(
                """
                SELECT
                    u.username,
                    q.track,
                    q.activity_date,
                    q.run_count,
                    ROUND(q.total_ms::numeric / NULLIF(q.run_count, 0), 1) AS avg_ms,
                    q.max_ms,
                    q.last_ms,
                    q.last_seen
                FROM query_performance_daily q
                JOIN users u ON u.id = q.user_id
                WHERE q.activity_date = %(activity_date)s
                ORDER BY avg_ms DESC, q.max_ms DESC
                """,
                params={"activity_date": date_filter.isoformat()},
            )
            st.markdown("#### Coding Query / Code Run Performance")
            if df_query_perf.empty:
                st.info("No coding execution performance recorded for the selected date yet.")
            else:
                df_query_perf["last_seen"] = df_query_perf["last_seen"].apply(_format_ist_12h)
                st.dataframe(df_query_perf, width="stretch", hide_index=True)
        except Exception as e:
            st.error(f"Time analytics unavailable: {e}")

    # =========================
    # 📚 PROGRESS
    # =========================
    with tab4:
        st.subheader("📚 Coding Progress")
        try:
            _ensure_progress_schema()
            ensure_reporting_views()
            from core.loader import load_questions

            totals = {
                "sql": len(load_questions("sql")),
                "pyspark": len(load_questions("sql")),
                "python": len(load_questions("python")),
            }
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
                df_progress["total_questions"] = df_progress["track"].map(totals).fillna(0).astype(int)
                df_progress["remaining_questions"] = (
                    df_progress["total_questions"] - df_progress["solved_questions"]
                ).clip(lower=0)
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
                normalized_query = query_input.strip().lower()
                if not (normalized_query.startswith("select") or normalized_query.startswith("with")):
                    st.error("Only read-only SELECT/WITH queries are allowed from the admin console.")
                    return

                df_res = pd.read_sql(query_input, engine)

                # Mask sensitive columns
                for col in ['password', 'otp_secret', 'otp_code']:
                    if col in df_res.columns:
                        df_res[col] = "********"

                st.dataframe(df_res, width="stretch")

            except Exception as e:
                st.error(f"SQL Error: {e}")

    with tab6:
        st.subheader("🚀 Deploy Health")
        health = get_deploy_health()

        c1, c2, c3 = st.columns(3)
        c1.metric("Running App Version", health["app_version"])
        c2.metric("Running Commit", (health["running_commit"] or "unknown")[:12])
        c3.metric("GitHub Latest", (health["latest_commit"] or "unknown")[:12])

        t1, t2, t3 = st.columns(3)
        t1.metric("Estimated Redeploy Time", health.get("deploy_latency", "unknown"))
        t2.caption(f"GitHub commit time: `{health.get('latest_committed_at') or 'unknown'}`")
        t3.caption(f"App start time: `{health.get('app_started_at') or 'unknown'}`")

        st.write(f"Repository: `{health['repo']}`")
        st.write(f"Branch: `{health['branch']}`")

        if health["latest_commit"] and health["running_commit"]:
            if health["is_current"]:
                st.success("Streamlit is running the latest GitHub commit.")
                st.caption(
                    "Redeploy time is estimated from GitHub commit timestamp to this Streamlit app process start time. "
                    "Streamlit Cloud does not expose per-stage build timings inside the app."
                )
            else:
                st.error(
                    "GitHub has a newer commit than the running Streamlit app. "
                    "This means Streamlit Cloud has not redeployed the latest push yet."
                )
        else:
            st.warning(
                "Could not compare running commit with GitHub latest commit. "
                "Check Streamlit Cloud repo/branch settings and GitHub access."
            )

        st.info(
            "The `Refresh Latest App/Data` button clears Streamlit data cache only. "
            "It cannot load new Python source code into an already-running Streamlit container. "
            "For source-code changes, Streamlit Cloud must redeploy/reboot the app. "
            "If this tab shows GitHub Latest is newer than Running Commit, reconnect the Streamlit app to the correct GitHub repo/branch or manually trigger redeploy."
        )