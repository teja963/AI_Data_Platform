from core.db import engine
from core.models import Base

Base.metadata.create_all(bind=engine)
print("✅ Tables created")