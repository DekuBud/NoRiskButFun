# Purpose: Expose the FastAPI routes for PDF upload, storage, history loading, and PDF report generation.
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import create_db_and_tables, get_db
from app.kpi_parser import parse_kpis
from app.models import Supplier, SupplierYearData
from app.news_service import build_news_service_from_env
from app.pdf_extractor import extract_text_from_pdf_bytes, identify_supplier_and_year
from app.report_generator import generate_supplier_report_pdf
from app.scoring import calculate_quick_score


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(
    title="NoRiskButFun",
    description="Minimal prototype for automated supplier financial reporting.",
    lifespan=lifespan,
)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    """Show one small upload form for local testing."""
    return """
    <html>
      <head><title>NoRiskButFun</title></head>
      <body>
        <h1>NoRiskButFun</h1>
        <p>Upload one supplier PDF to extract KPIs and store supplier-year data.</p>
        <form action="/upload" enctype="multipart/form-data" method="post">
          <input name="file" type="file" accept="application/pdf" required />
          <button type="submit">Upload PDF</button>
        </form>
        <p>Then open <code>/suppliers/{supplier_id}</code> or <code>/suppliers/{supplier_id}/report</code>.</p>
      </body>
    </html>
    """


@app.post("/upload")
def upload_supplier_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    """Upload one PDF, extract data, and create or update one supplier-year record."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    pdf_bytes = file.file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="The uploaded PDF is empty.")

    raw_text = extract_text_from_pdf_bytes(pdf_bytes)
    if not raw_text:
        raise HTTPException(status_code=422, detail="No readable text could be extracted from the PDF.")

    supplier_name, reporting_year = identify_supplier_and_year(raw_text, file.filename)
    if not supplier_name:
        raise HTTPException(status_code=422, detail="Could not identify the supplier name.")
    if reporting_year is None:
        raise HTTPException(status_code=422, detail="Could not identify the reporting year.")

    kpis = parse_kpis(raw_text)
    # Pflichtfelder Prüfen
    """
    if not kpis.get("netprofit"):
        raise HTTPException(status_code=422, detail="Could not identify the net-profit.")
    if not kpis.get("depreciation"):
        raise HTTPException(status_code=422, detail="Could not identify the deprecation.")
    if not kpis.get("equity"):
        raise HTTPException(status_code=422, detail="Could not identify the equity.")
    if not kpis.get("totalCapital"):
        raise HTTPException(status_code=422, detail="Could not identify the total-capital.")
    if not kpis.get("interestExpense"):
        raise HTTPException(status_code=422, detail="Could not identify the interest-expense.")
    if not kpis.get("revenue"):
        raise HTTPException(status_code=422, detail="Could not identify the revenue.")

    result = calculate_quick_score(
        _to_optional_float(kpis.get("netprofit")),
        _to_optional_float(kpis.get("depreciation")),
        _to_optional_float(kpis.get("provisionsForSeverancePaymentsCurrent")),
        _to_optional_float(kpis.get("provisionsForSeverancePaymentsPast")),
        _to_optional_float(kpis.get("provisionsForPensionCurrent")),
        _to_optional_float(kpis.get("provisionsForPensionPast")),
        _to_optional_float(kpis.get("bookValueOfDisposedAssets")),
        _to_optional_float(kpis.get("equity")),
        _to_optional_float(kpis.get("totalCapital")),
        _to_optional_float(kpis.get("cash")),
        _to_optional_float(kpis.get("stocks")),
        _to_optional_float(kpis.get("egt")),
        _to_optional_float(kpis.get("interestExpense")),
        _to_optional_float(kpis.get("revenue")),
        _to_optional_float(kpis.get("changeInInvertory")),
        _to_optional_float(kpis.get("capitalizedOwnWork"))
    )
    """

    quick_score = calculate_quick_score(
        turnover=_to_optional_float(kpis.get("turnover")),
        ebit=_to_optional_float(kpis.get("ebit")),
        ebitda=_to_optional_float(kpis.get("ebitda")),
        employees=_to_optional_int(kpis.get("employees")),
        investments=_to_optional_float(kpis.get("investments")),
    )

    try:
        supplier = _get_or_create_supplier(db, supplier_name)
        yearly_record, action = _upsert_supplier_year_data(
            db=db,
            supplier=supplier,
            year=reporting_year,
            source_filename=file.filename,
            turnover=_to_optional_float(kpis.get("turnover")),
            ebit=_to_optional_float(kpis.get("ebit")),
            ebitda=_to_optional_float(kpis.get("ebitda")),
            employees=_to_optional_int(kpis.get("employees")),
            investments=_to_optional_float(kpis.get("investments")),
            quick_score=quick_score,
        )
        db.commit()
        db.refresh(supplier)
        db.refresh(yearly_record)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to store extracted supplier data.") from exc

    return {
        "message": f"Upload processed successfully ({action}).",
        "supplier": {"id": supplier.id, "name": supplier.name},
        "year_data": _serialize_year_data(yearly_record),
        "extraction": {
            "supplier_name": supplier_name,
            "reporting_year": reporting_year,
            "kpis": kpis,
            "quick_score": quick_score,
        },
    }


@app.get("/suppliers/{supplier_id}")
def get_supplier_history(supplier_id: int, db: Session = Depends(get_db)) -> dict:
    """Return one supplier with all stored yearly entries sorted by year."""
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")

    yearly_records = _load_supplier_years(db, supplier_id)
    return {
        "supplier": {"id": supplier.id, "name": supplier.name},
        "years": [_serialize_year_data(record) for record in yearly_records],
    }


@app.get("/suppliers/{supplier_id}/report")
def generate_supplier_report(
    supplier_id: int,
    year: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    """Create a basic PDF report from stored supplier history."""
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")

    yearly_records = _load_supplier_years(db, supplier_id)
    if not yearly_records:
        raise HTTPException(status_code=404, detail="No yearly data exists for this supplier.")

    news_summary = build_news_service_from_env().get_summary(supplier.name)

    try:
        pdf_bytes = generate_supplier_report_pdf(
            supplier_name=supplier.name,
            yearly_records=yearly_records,
            news_summary=news_summary,
            focus_year=year,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    filename = f"supplier-report-{supplier.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


def _get_or_create_supplier(db: Session, supplier_name: str) -> Supplier:
    """Find the supplier case-insensitively or create it when missing."""
    existing_supplier = db.scalar(
        select(Supplier).where(func.lower(Supplier.name) == supplier_name.lower())
    )
    if existing_supplier:
        return existing_supplier

    supplier = Supplier(name=supplier_name)
    db.add(supplier)
    db.flush()
    return supplier


def _upsert_supplier_year_data(
    db: Session,
    supplier: Supplier,
    year: int,
    source_filename: str,
    turnover: Optional[float],
    ebit: Optional[float],
    ebitda: Optional[float],
    employees: Optional[int],
    investments: Optional[float],
    quick_score: Optional[float],
) -> tuple[SupplierYearData, str]:
    """Keep duplicate handling simple: update the same supplier-year row when it already exists."""
    yearly_record = db.scalar(
        select(SupplierYearData).where(
            SupplierYearData.supplier_id == supplier.id,
            SupplierYearData.year == year,
        )
    )

    if yearly_record is None:
        yearly_record = SupplierYearData(supplier_id=supplier.id, year=year)
        db.add(yearly_record)
        action = "created"
    else:
        action = "updated"

    # Missing KPI values stay as NULL in the database for version 1.
    yearly_record.turnover = turnover
    yearly_record.ebit = ebit
    yearly_record.ebitda = ebitda
    yearly_record.employees = employees
    yearly_record.investments = investments
    yearly_record.quick_score = quick_score
    yearly_record.source_filename = source_filename

    db.flush()
    return yearly_record, action


def _load_supplier_years(db: Session, supplier_id: int) -> list[SupplierYearData]:
    """Load all stored years so historical comparisons can use sorted data."""
    return list(
        db.scalars(
            select(SupplierYearData)
            .where(SupplierYearData.supplier_id == supplier_id)
            .order_by(SupplierYearData.year.asc())
        )
    )


def _serialize_year_data(record: SupplierYearData) -> dict:
    return {
        "id": record.id,
        "supplier_id": record.supplier_id,
        "year": record.year,
        "turnover": record.turnover,
        "ebit": record.ebit,
        "ebitda": record.ebitda,
        "employees": record.employees,
        "investments": record.investments,
        "quick_score": record.quick_score,
        "source_filename": record.source_filename,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def _to_optional_float(value: object) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _to_optional_int(value: object) -> Optional[int]:
    if value is None:
        return None
    return int(value)
