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

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()