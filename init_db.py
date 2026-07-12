from core.db import engine
from core.models import Base
from core.activity import ensure_activity_schema
from core.progress import _ensure_progress_schema
from core.views import ensure_reporting_views

Base.metadata.create_all(bind=engine)
_ensure_progress_schema()
ensure_activity_schema()
ensure_reporting_views()
print("✅ Tables created or updated without deleting existing data")
