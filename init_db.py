from core.db import engine
from core.models import Base

# Drop tables first to ensure schema is synced with new columns (full_name, email, etc.)
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print("✅ Tables recreated with new schema")
