from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import streamlit as st
import os

# Use Streamlit secrets if available (for Cloud deployment), 
# then check environment variables (for terminal migrations),
# otherwise fallback to local postgres
if "database" in st.secrets:
    db_config = st.secrets["database"]
    if "url" in db_config:
        DATABASE_URL = db_config["url"]
    else:
        DATABASE_URL = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
elif os.getenv("DATABASE_URL"):
    DATABASE_URL = os.getenv("DATABASE_URL")
else:
    # Local development default
    DATABASE_URL = "postgresql://localhost/ai_data_engg"

# pool_pre_ping=True fixes the "SSL connection closed unexpectedly" error
# pool_recycle ensures connections are refreshed before the server drops them
engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True, 
    pool_recycle=300
)
# expire_on_commit=False prevents attributes from being wiped after a commit,
# which helps avoid DetachedInstanceErrors when accessing data after session close.
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

Base = declarative_base()