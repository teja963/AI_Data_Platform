import streamlit as st
import pandas as pd
from core.db import SessionLocal, engine
from core.models import User
from core.auth import create_user
import pyotp

def render_admin():
    if st.session_state.get("role") != "admin":
        st.error("Unauthorized access.")
        return

    st.title("🛡️ Admin Dashboard")
    
    tab1, tab2, tab3 = st.tabs(["👥 User Management", "📈 User Activity", "🔍 SQL Console"])

    with tab1:
        st.subheader("👥 Manage Users")
        search = st.text_input("Search by Username or Email", "").lower()
        
        session = SessionLocal()
        try:
            query = session.query(User)
            if search:
                query = query.filter((User.username.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%")))
            
            users = query.order_by(User.created_at.desc()).all()

            if not users:
                st.info("No users found.")
            else:
                user_data = []
                for u in users:
                    # Ensure full_name is not None for display
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
                st.markdown("### Pending Approvals")
                pending = [u for u in users if not u.is_approved and u.email_verified] # Only show verified users for approval
                for p_user in pending:
                    col1, col2 = st.columns([3, 1])
                    col1.write(f"Approve **{p_user.username}** ({p_user.email})?")
                    if col2.button("Approve", key=f"app_{p_user.id}"):
                        p_user.is_approved = True
                        session.commit()
                        st.rerun()
        finally:
            session.close()

    with tab2:
        st.subheader("📈 Recent User Logins")
        df_activity = pd.read_sql("SELECT username, last_login, created_at FROM users WHERE last_login IS NOT NULL", engine)
        if not df_activity.empty:
            st.write("Recent Active Users")
            st.dataframe(df_activity.sort_values("last_login", ascending=False).reset_index(drop=True), use_container_width=True)
        else:
            st.info("No login activity recorded yet.")

    with tab3:
        st.subheader("🔍 SQL Explorer")
        query_input = st.text_area("Run read-only queries on users", "SELECT * FROM users LIMIT 10;")
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