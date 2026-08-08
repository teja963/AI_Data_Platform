from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from urllib.parse import urlparse

try:
    import streamlit as st
except ImportError:  # Standalone scanners only require DATABASE_URL.
    st = None


# GitHub Actions and standalone workers provide DATABASE_URL directly. Check it
# before touching st.secrets because Streamlit raises when no secrets file exists.
if os.getenv("DATABASE_URL"):
    DATABASE_URL = os.getenv("DATABASE_URL")
elif st is not None and "database" in st.secrets:
    db_config = st.secrets["database"]
    if "url" in db_config:
        DATABASE_URL = db_config["url"]
    else:
        DATABASE_URL = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
else:
    # Local development default
    DATABASE_URL = "postgresql://localhost/ai_data_engg"

# Bound connection/query waits so background jobs fail and retry instead of
# hanging until the GitHub Actions timeout.
engine_options = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_timeout": 10,
}
if DATABASE_URL.startswith(("postgresql://", "postgresql+psycopg2://")):
    engine_options["connect_args"] = {
        "connect_timeout": 10,
        "options": "-c statement_timeout=60000",
    }
engine = create_engine(DATABASE_URL, **engine_options)
# expire_on_commit=False prevents attributes from being wiped after a commit,
# which helps avoid DetachedInstanceErrors when accessing data after session close.
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

Base = declarative_base()


def get_database_host():
    try:
        return urlparse(DATABASE_URL).hostname
    except Exception:
        return None