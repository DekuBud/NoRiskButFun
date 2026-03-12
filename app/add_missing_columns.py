"""
use with:
  python -m app.add_missing_columns
"""
from __future__ import annotations

from typing import List, Tuple

from sqlalchemy import Float, inspect, text

from app.database import engine

TARGET_TABLE = "supplier_year_data"

# Liste der (spaltenname, sqlalchemy_type, nullable)
COLUMNS: List[Tuple[str, object, bool]] = [
    ("equity_ratio", Float, True),
    ("debt_repayment_period", Float, True),
    ("return_on_total_assets", Float, True),
    ("cash_flow_performance_rate", Float, True),
    ("financial_stability", Float, True),
    ("earnings_power", Float, True),
]


def add_missing_columns(engine, table_name: str, columns: List[Tuple[str, object, bool]]) -> None:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        print(f"Tabelle '{table_name}' nicht gefunden in DB.")
        return

    existing = {c["name"] for c in inspector.get_columns(table_name)}
    to_add = [c for c in columns if c[0] not in existing]
    if not to_add:
        print("Keine fehlenden Spalten gefunden. DB ist aktuell.")
        return

    dialect = engine.dialect.name
    if dialect == "sqlite":
        sql_type = "FLOAT"
    elif dialect == "postgresql":
        sql_type = "DOUBLE PRECISION"
    elif dialect == "mysql":
        sql_type = "DOUBLE"
    else:
        sql_type = "FLOAT"

    with engine.begin() as conn:
        for name, typ, nullable in to_add:
            stmt = f'ALTER TABLE "{table_name}" ADD COLUMN "{name}" {sql_type}'
            print(f"Füge Spalte hinzu: {name} ({sql_type})")
            conn.execute(text(stmt))

    print("Fertig. Fehlende Spalten wurden hinzugefügt.")


if __name__ == "__main__":
    add_missing_columns(engine, TARGET_TABLE, COLUMNS)
