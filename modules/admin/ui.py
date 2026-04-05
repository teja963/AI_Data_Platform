import streamlit as st
from core.db import SessionLocal
from core.models import User
from core.auth import create_user
import pyotp

def render_admin():
    if st.session_state.get("role") != "admin":
        st.error("Unauthorized access.")
        return

    st.title("🛡️ Admin Dashboard")
    
    tab1, tab2 = st.tabs(["User Management", "System Health"])

    with tab1:
        st.subheader("Manage Users")
        session = SessionLocal()
        try:
            users = session.query(User).order_by(User.created_at.desc()).all()
            
            if not users:
                st.info("No users found.")
            else:
                # Display users in a clean table-like structure
                for u in users:
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
                        with c1:
                            st.markdown(f"**{u.full_name}** (@{u.username})")
                            st.caption(f"📧 {u.email} | 📱 {u.phone_number}")
                            last_active = u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else "Never"
                            st.markdown(f"🕒 Last Login: `{last_active}`")
                        with c2:
                            status = "✅ Approved" if u.is_approved else "⏳ Pending"
                            st.markdown(f"Status: {status}")
                            st.caption(f"Role: {u.role.upper()}")
                        with c3:
                            if not u.is_approved:
                                if st.button("Approve", key=f"app_{u.id}"):
                                    u.is_approved = True
                                    session.commit()
                                    st.rerun()
                        with c4:
                            if u.username != st.session_state["user"]: # Prevent self-deletion
                                if st.button("Delete", key=f"del_{u.id}", type="secondary"):
                                    session.delete(u)
                                    session.commit()
                                    st.rerun()
        finally:
            session.close()

    with tab2:
        st.subheader("System Statistics")
        st.write("Placeholder for server monitoring and traffic logs.")