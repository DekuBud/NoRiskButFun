# Purpose: Configure the SQLAlchemy engine, session factory, and shared database helpers.
from __future__ import annotations

import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

DEFAULT_DATABASE_URL = "sqlite:///./noriskbutfun.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

# Keep engine creation generic. Only the SQLite driver needs a small connect arg.
engine_options: dict[str, object] = {"future": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Shared SQLAlchemy base class."""


def get_db() -> Generator[Session, None, None]:
    """Yield one database session per request and close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_db_and_tables() -> None:
    """Create database tables for local development and first startup."""
    from app import models  # noqa: F401  # Import registers model metadata.

    Base.metadata.create_all(bind=engine)
