import uuid

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column, sessionmaker, DeclarativeBase

from app.config import get_settings


def uuid_pk():
    """Primary-key column factory shared by legacy and vNext models."""
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

settings = get_settings()

connect_args = {}
if settings.database_schema:
    connect_args["options"] = f"-c search_path={settings.database_schema}"

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
