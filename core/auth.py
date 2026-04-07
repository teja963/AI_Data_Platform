import bcrypt
import re
import random
import resend
import streamlit as st
import time
from datetime import datetime, timedelta
from core.db import SessionLocal
from core.models import User
import pyotp

# ---------------- VALIDATION ----------------
def validate_email(email):
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))

def validate_phone(phone):
    return bool(re.match(r"^(?:\+91)?[0-9]{10}$", phone))


# ---------------- RATE LIMIT ----------------
def can_send_otp():
    last = st.session_state.get("last_otp_time", 0)
    if time.time() - last < 30:
        return False
    st.session_state["last_otp_time"] = time.time()
    return True


# ---------------- CREATE USER ----------------
def create_user(username, password, full_name, email, phone, role="user", otp_secret=None):
    session = SessionLocal()
    try:
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters.")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters.")

        if session.query(User).filter_by(username=username).first():
            raise ValueError("Username already exists")

        if session.query(User).filter(User.email.ilike(email)).first():
            raise ValueError("Email already registered")

        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        user = User(
            username=username,
            password=hashed,
            full_name=full_name,
            email=email,
            phone_number=phone,
            role=role,
            is_approved=False,
            email_verified=True if role == "admin" else False,
            otp_secret=otp_secret   # ✅ FIX
        )

        session.add(user)
        session.commit()

    finally:
        session.close()


# ---------------- EMAIL SEND ----------------
def send_otp_email(email, otp):
    resend.api_key = st.secrets["RESEND_API_KEY"]

    try:
        response = resend.Emails.send({
            "from": "Panasa Edu <no-reply@panasaedu.in>",  # ✅ your domain
            "to": [email],
            "subject": "Your OTP Code",
            "html": f"<h2>Your OTP is:</h2><h1>{otp}</h1><p>Valid for 10 minutes.</p>"
        })

        return True

    except Exception as e:
        st.error(f"Email error: {e}")
        return False


# ---------------- OTP GENERATE ----------------
def generate_and_store_otp(email):
    if not can_send_otp():
        st.warning("Please wait 30 seconds before requesting another OTP")
        return None

    session = SessionLocal()
    try:
        otp = str(random.randint(100000, 999999))
        expiry = datetime.utcnow() + timedelta(minutes=10)

        user = session.query(User).filter(User.email == email).first()

        if user:
            user.otp_code = otp
            user.otp_expiry = expiry
            session.commit()
        else:
            st.session_state["temp_otp"] = otp
            st.session_state["temp_otp_expiry"] = expiry

        send_otp_email(email, otp)
        return otp

    finally:
        session.close()


# ---------------- OTP VERIFY ----------------
def verify_email_otp(email, code):
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.email == email).first()

        # EXISTING USER
        if user and user.otp_code == code:
            if hasattr(user, "otp_expiry") and user.otp_expiry and user.otp_expiry < datetime.utcnow():
                return False

            user.email_verified = True
            user.otp_code = None
            user.otp_expiry = None
            session.commit()
            return True

        # NEW USER (SIGNUP FLOW)
        if code == st.session_state.get("temp_otp"):
            expiry = st.session_state.get("temp_otp_expiry")
            if expiry and expiry < datetime.utcnow():
                return False
            return True

        return False

    finally:
        session.close()


# ---------------- PASSWORD RESET ----------------
def update_password(email, new_password, otp):
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.email == email).first()

        if not user:
            raise ValueError("User not found")

        if user.otp_code != otp:
            raise ValueError("Invalid OTP")

        if hasattr(user, "otp_expiry") and user.otp_expiry and user.otp_expiry < datetime.utcnow():
            raise ValueError("OTP expired")

        user.password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        user.otp_code = None
        user.otp_expiry = None
        session.commit()

    finally:
        session.close()


# ---------------- LOGIN ----------------
def login_user(username, password):
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()

        if not user:
            return None

        if not user.email_verified and user.role != "admin":
            raise PermissionError("Verify your email first.")

        if not user.is_approved and user.role != "admin":
            raise PermissionError("Pending admin approval.")

        if bcrypt.checkpw(password.encode(), user.password.encode()):
            user.last_login = datetime.utcnow()
            session.commit()

            return type("UserSession", (), {
                "username": user.username,
                "role": user.role
            })()

        return None

    finally:
        session.close()


# ---------------- TOTP VERIFY ----------------
def verify_otp(username, code):
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()

        if not user or not user.otp_secret:
            return False

        totp = pyotp.TOTP(user.otp_secret)
        return totp.verify(code)

    finally:
        session.close()