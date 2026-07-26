from functools import lru_cache

from sqlalchemy import inspect, text

from core.db import Base, SessionLocal, engine
from core.models import ArchitectureDiagram, User


@lru_cache(maxsize=1)
def ensure_architecture_schema():
    Base.metadata.create_all(bind=engine, tables=[ArchitectureDiagram.__table__])
    columns = {column["name"] for column in inspect(engine).get_columns("architecture_diagrams")}
    if "source_url" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE architecture_diagrams ADD COLUMN source_url VARCHAR"))


def get_architecture_diagrams(include_inactive=False):
    ensure_architecture_schema()
    session = SessionLocal()
    try:
        query = session.query(ArchitectureDiagram)
        if not include_inactive:
            query = query.filter(ArchitectureDiagram.is_active.is_(True))
        return query.order_by(ArchitectureDiagram.created_at.desc()).all()
    finally:
        session.close()


def add_architecture_diagram(username, title, description, file_name, content_type, file_data):
    ensure_architecture_schema()
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        diagram = ArchitectureDiagram(
            title=title,
            description=description,
            file_name=file_name,
            content_type=content_type,
            file_data=file_data,
            uploaded_by=user.id if user else None,
            is_active=True,
        )
        session.add(diagram)
        session.commit()
    finally:
        session.close()


def add_github_architecture_diagram(username, title, description, file_name, source_url):
    ensure_architecture_schema()
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        diagram = ArchitectureDiagram(
            title=title,
            description=description,
            file_name=file_name,
            content_type="application/xml",
            file_data=b"",
            source_url=source_url,
            uploaded_by=user.id if user else None,
            is_active=True,
        )
        session.add(diagram)
        session.commit()
    finally:
        session.close()


def delete_architecture_diagram(diagram_id):
    ensure_architecture_schema()
    session = SessionLocal()
    try:
        diagram = session.query(ArchitectureDiagram).filter_by(id=diagram_id).first()
        if diagram:
            session.delete(diagram)
            session.commit()
    finally:
        session.close()
