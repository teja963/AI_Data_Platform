import streamlit as st
import pandas as pd
from core.db import SessionLocal, engine
from core.models import User

def render_admin():
    if st.session_state.get("role") != "admin":
        st.error("Unauthorized access.")
        return

    st.title("🛡️ Admin Dashboard")

    tab1, tab2, tab3 = st.tabs([
        "👥 User Management",
        "📈 User Activity",
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
    # 🔍 SQL CONSOLE
    # =========================
    with tab3:
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