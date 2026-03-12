# Purpose: Configure the SQLAlchemy engine, session factory, and shared database helpers.
from __future__ import annotations

import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
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
    _ensure_supplier_year_data_columns()


def _ensure_supplier_year_data_columns() -> None:
    """Backfill columns that may be missing in older SQLite databases."""
    table_name = "supplier_year_data"
    missing_column_statements = {
        "equity_ratio": 'ALTER TABLE "supplier_year_data" ADD COLUMN "equity_ratio" FLOAT',
        "debt_repayment_period": 'ALTER TABLE "supplier_year_data" ADD COLUMN "debt_repayment_period" FLOAT',
        "return_on_total_assets": 'ALTER TABLE "supplier_year_data" ADD COLUMN "return_on_total_assets" FLOAT',
        "cash_flow_performance_rate": 'ALTER TABLE "supplier_year_data" ADD COLUMN "cash_flow_performance_rate" FLOAT',
        "financial_stability": 'ALTER TABLE "supplier_year_data" ADD COLUMN "financial_stability" FLOAT',
        "earnings_power": 'ALTER TABLE "supplier_year_data" ADD COLUMN "earnings_power" FLOAT',
    }

    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    with engine.begin() as conn:
        for column_name, statement in missing_column_statements.items():
            if column_name not in existing_columns:
                conn.execute(text(statement))
