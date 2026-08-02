"""Database engine, session factory and the FastAPI session dependency."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.conf.config import settings

DATABASE_URL = settings.database_url

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Iterator[Session]:
    """Yield a session per request and always close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Route signatures use this instead of `db: Session = Depends(get_db)`.
DbSession = Annotated[Session, Depends(get_db)]
