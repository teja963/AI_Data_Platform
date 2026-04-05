import sys
import os
import getpass
import pyotp

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.auth import create_user
from core.db import SessionLocal
from core.models import User

def make_admin(username, password, full_name, email, phone, otp_secret):
    try:
        print(f"Creating admin user: {username}...")
        create_user(username, password, full_name, email, phone, role="admin", otp_secret=otp_secret)
        
        # Manually approve the root admin
        session = SessionLocal()
        user = session.query(User).filter_by(username=username).first()
        if user:
            user.is_approved = True
            session.commit()
            print("✅ Root admin created and approved.")
            print(f"\n--- AUTHENTICATOR SETUP ---")
            print(f"Your Secret Key: {otp_secret}")
            print(f"Provisioning URI (Enter this in your app or use as a QR source):")
            print(pyotp.totp.TOTP(otp_secret).provisioning_uri(name=email, issuer_name="AI_Data_Engg"))
            print("---------------------------\n")
        session.close()
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    print("--- Root Admin Creation Tool ---")
    username = input("Enter admin username: ")
    password = getpass.getpass("Enter admin password (will not be shown): ")
    full_name = input("Enter full name: ")
    email = input("Enter email: ")
    phone = input("Enter phone number (10 digits for India +91): ")
    otp_secret = pyotp.random_base32()
    
    make_admin(username, password, full_name, email, phone, otp_secret)