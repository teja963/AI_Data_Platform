import bcrypt
import re
import random
import resend
import streamlit as st
from datetime import datetime, timedelta
from core.db import SessionLocal
from core.models import User
import pyotp

# ---------------- VALIDATION ----------------
def validate_email(email):
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))

def validate_phone(phone):
    return bool(re.match(r"^(?:\+91)?[0-9]{10}$", phone))

# ---------------- CREATE USER ----------------
def create_user(username, password, full_name, email, phone, role="user"):
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
            email_verified=False
        )

        session.add(user)
        session.commit()

    finally:
        session.close()


# ---------------- EMAIL SEND ----------------
def send_otp_email(email, otp):
    resend.api_key = st.secrets["RESEND_API_KEY"]

    try:
        resend.emails.send({
            "from": "Panasa Edu <no-reply@panasaedu.in>",
            "to": [email],
            "subject": "Your OTP Code",
            "html": f"""
            <div style="font-family:Arial">
                <h2>Your Verification Code</h2>
                <h1>{otp}</h1>
                <p>This code expires in 10 minutes.</p>
            </div>
            """
        })
        return True
    except Exception as e:
        print("Email error:", e)
        return False


# ---------------- OTP GENERATE ----------------
def generate_and_store_otp(email):
    session = SessionLocal()
    try:
        otp = str(random.randint(100000, 999999))
        expiry = datetime.utcnow() + timedelta(minutes=10)

        user = session.query(User).filter(User.email == email).first()

        if user:
            user.otp_code = otp
            user.otp_expiry = expiry
        else:
            # temp storage for signup
            st.session_state["temp_otp"] = otp
            st.session_state["temp_otp_expiry"] = expiry

        session.commit()
        send_otp_email(email, otp)
        return otp

    finally:
        session.close()


# ---------------- OTP VERIFY ----------------
def verify_email_otp(email, code):
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.email == email).first()

        # existing user
        if user and user.otp_code == code:
            if user.otp_expiry and user.otp_expiry < datetime.utcnow():
                return False

            user.email_verified = True
            user.otp_code = None
            session.commit()
            return True

        # new user (signup)
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

        if user.otp_expiry < datetime.utcnow():
            raise ValueError("OTP expired")

        user.password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        user.otp_code = None
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

        if not user.email_verified:
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

# ---------------- OTP VERIFY ----------------
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