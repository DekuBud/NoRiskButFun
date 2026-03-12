# Purpose: Generate realistic demo financial data for one supplier-year and store it in the database.
from __future__ import annotations

import argparse
import random
from datetime import datetime

from app.database import SessionLocal
from app.models import Supplier, SupplierYearData


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate demo data for one supplier and one reporting year."
    )
    parser.add_argument("--supplier-id", type=int, required=True, help="Existing supplier ID")
    parser.add_argument("--year", type=int, required=True, help="Reporting year")
    return parser.parse_args()


def validate_year(year: int) -> None:
    current_year = datetime.utcnow().year
    if year < 1990 or year > current_year + 1:
        raise ValueError(
            f"Invalid reporting year: {year}. Expected a value between 1990 and {current_year + 1}."
        )


def round2(value: float) -> float:
    return round(value, 2)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def generate_demo_values(supplier_id: int, year: int) -> dict[str, float | int | str]:
    # Seed by supplier and year so the same input produces stable demo data.
    rng = random.Random(f"supplier-demo-{supplier_id}-{year}")

    employees = rng.randint(90, 4200)
    revenue_per_employee = rng.uniform(135_000, 380_000)
    turnover = employees * revenue_per_employee * rng.uniform(0.92, 1.12)

    ebit_margin = rng.uniform(0.045, 0.14)
    ebit = turnover * ebit_margin

    depreciation_rate = rng.uniform(0.015, 0.05)
    ebitda = ebit + (turnover * depreciation_rate)

    investments = turnover * rng.uniform(0.025, 0.12)

    equity_ratio = rng.uniform(22.0, 58.0)
    debt_repayment_period = rng.uniform(1.4, 7.8)
    return_on_total_assets = rng.uniform(2.5, 13.5)
    cash_flow_performance_rate = rng.uniform(5.0, 24.0)

    quick_score = clamp(
        42.0
        + (ebit_margin * 210.0)
        + (equity_ratio - 30.0) * 0.45
        - debt_repayment_period * 2.3
        + rng.uniform(-5.0, 5.0),
        0.0,
        100.0,
    )
    financial_stability = clamp(
        35.0 + equity_ratio * 0.9 - debt_repayment_period * 3.1 + rng.uniform(-4.0, 4.0),
        0.0,
        100.0,
    )
    earnings_power = clamp(
        28.0 + (ebit_margin * 260.0) + return_on_total_assets * 1.8 + rng.uniform(-4.0, 4.0),
        0.0,
        100.0,
    )

    return {
        "turnover": round2(turnover),
        "ebit": round2(ebit),
        "ebitda": round2(max(ebitda, ebit)),
        "employees": employees,
        "investments": round2(investments),
        "quick_score": round2(quick_score),
        "equity_ratio": round2(equity_ratio),
        "debt_repayment_period": round2(debt_repayment_period),
        "return_on_total_assets": round2(return_on_total_assets),
        "cash_flow_performance_rate": round2(cash_flow_performance_rate),
        "financial_stability": round2(financial_stability),
        "earnings_power": round2(earnings_power),
        "source_filename": f"demo_seed_supplier_{supplier_id}_{year}.pdf",
    }


def main() -> int:
    args = parse_args()

    try:
        validate_year(args.year)
    except ValueError as exc:
        print(exc)
        return 1

    db = SessionLocal()
    try:
        supplier = db.get(Supplier, args.supplier_id)
        if supplier is None:
            print(f"Supplier with id {args.supplier_id} does not exist.")
            return 1

        values = generate_demo_values(args.supplier_id, args.year)
        existing_row = (
            db.query(SupplierYearData)
            .filter(
                SupplierYearData.supplier_id == args.supplier_id,
                SupplierYearData.year == args.year,
            )
            .one_or_none()
        )

        action = "updated"
        if existing_row is None:
            existing_row = SupplierYearData(supplier_id=args.supplier_id, year=args.year)
            db.add(existing_row)
            action = "created"

        for field_name, field_value in values.items():
            setattr(existing_row, field_name, field_value)

        db.commit()

        print(f"supplier id: {supplier.id}")
        print(f"supplier name: {supplier.name}")
        print(f"year processed: {args.year}")
        print(f"row status: {action}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Failed to seed demo data: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())