import bcrypt
from core.db import SessionLocal
from core.models import User


def create_user(username, password):
    session = SessionLocal()
    try:
        # Prevent duplicates before they hit the DB constraint
        existing = session.query(User).filter_by(username=username).first()
        if existing:
            raise ValueError("Username already exists. Please choose another one.")

        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(username=username, password=hashed)
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

        if bcrypt.checkpw(password.encode(), user.password.encode()):
            return user

        return None
    finally:
        session.close()
