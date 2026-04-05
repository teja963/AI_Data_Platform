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
    
    tab1, tab2 = st.tabs(["User Management", "Add New User"])

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
                        c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
                        with c1:
                            st.markdown(f"**{u.full_name}** (@{u.username})")
                            st.caption(f"📧 {u.email} | 📱 {u.phone_number}")
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
        st.subheader("Create Authorized Account")
        st.info("Accounts created here are automatically approved.")
        
        with st.form("admin_create_user", clear_on_submit=True):
            new_full_name = st.text_input("Full Name")
            new_username = st.text_input("Username")
            new_email = st.text_input("Email")
            new_phone = st.text_input("Phone Number")
            new_password = st.text_input("Initial Password", type="password")
            new_role = st.selectbox("Role", ["user", "admin"])
            
            submit = st.form_submit_button("Create & Approve User", use_container_width=True)
            
            if submit:
                try:
                    # Generate OTP secret if the new user is an admin
                    generated_otp_secret = pyotp.random_base32() if new_role == "admin" else None
                    
                    # Create user via auth helper
                    create_user(
                        username=new_username,
                        password=new_password,
                        full_name=new_full_name,
                        email=new_email,
                        phone=new_phone,
                        role=new_role,
                        otp_secret=generated_otp_secret
                    )
                    
                    # Auto-approve since admin created it
                    session = SessionLocal()
                    db_user = session.query(User).filter_by(username=new_username).first()
                    if db_user:
                        db_user.is_approved = True
                        session.commit()
                    session.close()
                    
                    st.success(f"User {new_username} created and approved successfully!")
                    
                    if new_role == "admin":
                        st.warning("⚠️ **IMPORTANT**: Copy this Secret Key and give it to the user for their Authenticator app:")
                        st.code(generated_otp_secret)
                        st.caption("This key will not be shown again.")
                        
                except Exception as e:
                    st.error(f"Error: {str(e)}")