import bcrypt
import pyotp
import re
from core.db import SessionLocal
from core.models import User

def validate_email(email):
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))

def validate_phone(phone):
    # Validates exactly 10 digits or +91 followed by 10 digits
    return bool(re.match(r"^(?:\+91)?[0-9]{10}$", phone))

def create_user(username, password, full_name=None, email=None, phone=None, role="user", otp_secret=None):
    session = SessionLocal()
    try:
        # 1. Basic field validation
        if not username or len(username.strip()) < 3:
            raise ValueError("Username must be at least 3 characters.")
        if not password or len(password.strip()) < 6:
            raise ValueError("Password must be at least 6 characters.")
        if not full_name or len(full_name.strip()) < 2:
            raise ValueError("Full Name is required.")
            
        # 2. Credential format validation
        if email and not validate_email(email):
            raise ValueError("Invalid email format (e.g., name@domain.com).")
        if phone and not validate_phone(phone):
            raise ValueError("Invalid phone format. Enter 10 digits or start with +91.")

        # Default to India country code (+91) if only 10 digits provided
        if phone and len(phone) == 10:
            phone = "+91" + phone

        # 3. Duplicate checks
        # Prevent duplicates before they hit the DB constraint
        existing = session.query(User).filter_by(username=username).first()
        if existing:
            raise ValueError("Username already exists. Please choose another one.")
        
        if email:
            existing_email = session.query(User).filter(User.email.ilike(email)).first()
            if existing_email:
                raise ValueError("Email already registered.")

        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        # is_approved is False by default for new users (Admin must approve)
        user = User(
            username=username, 
            password=hashed, 
            otp_secret=otp_secret,
            full_name=full_name, 
            email=email,
            phone_number=phone, 
            role=role, 
            is_approved=False
        )
        session.add(user)
        session.commit()
    finally:
        session.close()

def login_user(username, password):
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()

        if not user:
            return None

        if not user.is_approved and user.role != "admin":
            raise PermissionError("Your account is pending admin approval.")

        if bcrypt.checkpw(password.encode(), user.password.encode()):
            return user

        return None
    finally:
        session.close()

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
