from core.db import engine
from core.models import Base
from core.progress import _ensure_progress_schema

Base.metadata.create_all(bind=engine)
_ensure_progress_schema()
print("✅ Tables created or updated")