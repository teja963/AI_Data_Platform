from core.db import engine
from core.models import Base
from core.activity import ensure_activity_schema
from core.progress import _ensure_progress_schema

Base.metadata.create_all(bind=engine)
_ensure_progress_schema()
ensure_activity_schema()
print("✅ Tables created or updated")