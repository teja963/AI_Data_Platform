import streamlit as st
import pandas as pd
from core.db import SessionLocal, engine
from core.models import User
from core.activity import ensure_activity_schema
from core.progress import _ensure_progress_schema

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

                st.dataframe(pd.DataFrame(user_data), use_container_width=True, hide_index=True)

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

        df_activity = pd.read_sql(
            """
            SELECT username, email, last_login, created_at 
            FROM users 
            WHERE last_login IS NOT NULL
            """,
            engine
        )

        if df_activity.empty:
            st.info("No login activity recorded yet.")
        else:
            df_activity = df_activity.sort_values("last_login", ascending=False)
            st.dataframe(df_activity.reset_index(drop=True), use_container_width=True)

    # =========================
    # ⏱️ TIME ANALYTICS
    # =========================
    with tab3:
        st.subheader("⏱️ Platform Time Analytics")
        try:
            ensure_activity_schema()
            df_time = pd.read_sql(
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
                engine,
            )

            if df_time.empty:
                st.info("No section time has been recorded yet. Analytics starts collecting after users navigate the app with this version.")
            else:
                total_seconds = int(df_time["total_seconds"].sum())
                active_users = df_time["username"].nunique()
                top_section = df_time.groupby("section")["total_seconds"].sum().sort_values(ascending=False).index[0]

                m1, m2, m3 = st.columns(3)
                m1.metric("Tracked Time", f"{round(total_seconds / 60, 1)} min")
                m2.metric("Active Users", active_users)
                m3.metric("Top Section", top_section)

                st.markdown("#### Time By User And Section")
                st.dataframe(df_time, use_container_width=True, hide_index=True)

                section_summary = (
                    df_time.groupby("section", as_index=False)
                    .agg(total_seconds=("total_seconds", "sum"), users=("username", "nunique"), visits=("visit_count", "sum"))
                )
                section_summary["total_minutes"] = (section_summary["total_seconds"] / 60).round(1)
                section_summary = section_summary.sort_values("total_seconds", ascending=False)

                st.markdown("#### Section Summary")
                st.dataframe(section_summary, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Time analytics unavailable: {e}")

    # =========================
    # 📚 PROGRESS
    # =========================
    with tab4:
        st.subheader("📚 User Question Progress")
        try:
            _ensure_progress_schema()
            df_progress = pd.read_sql(
                """
                SELECT
                    u.username,
                    p.track,
                    COUNT(*) AS solved_questions,
                    MAX(p.updated_at) AS last_progress_at
                FROM progress p
                JOIN users u ON u.id = p.user_id
                WHERE p.status = 'solved'
                GROUP BY u.username, p.track
                ORDER BY u.username, p.track
                """,
                engine,
            )
            if df_progress.empty:
                st.info("No solved progress has been saved yet.")
            else:
                st.dataframe(df_progress, use_container_width=True, hide_index=True)
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

                st.dataframe(df_res, use_container_width=True)

            except Exception as e:
                st.error(f"SQL Error: {e}")