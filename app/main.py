# Purpose: Expose the FastAPI routes for PDF upload, storage, history loading, and PDF report generation.
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import create_db_and_tables, get_db
from app.kpi_parser import parse_kpis, parse_kpis_from_json
from app.models import Supplier, SupplierYearData
from app.news_service import build_news_service_from_env
from app.pdf_extractor import extract_text_from_pdf_bytes, identify_supplier_and_year, pdf_tables_to_json
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
      <head>
        <title>NoRiskButFun</title>
        <style>
          body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; background: #f5f5f5; }
          h1 { color: #333; }
          .form-card { background: white; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
          .form-group { margin-bottom: 20px; }
          label { display: block; margin-bottom: 8px; font-weight: 500; color: #333; }
          input[type="text"], input[type="file"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; box-sizing: border-box; }
          input[type="text"]:focus, input[type="file"]:focus { outline: none; border-color: #0066cc; box-shadow: 0 0 0 3px rgba(0,102,204,0.1); }
          button { background: #0066cc; color: white; padding: 12px 24px; border: none; border-radius: 4px; font-size: 16px; font-weight: 600; cursor: pointer; width: 100%; }
          button:hover { background: #0052a3; }
          .info { background: #f0f8ff; padding: 15px; border-left: 4px solid #0066cc; margin-top: 20px; color: #333; }
          code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; }
        </style>
      </head>
      <body>
        <h1>NoRiskButFun</h1>
        <div class="form-card">
          <p>Upload a supplier PDF and provide the supplier name to extract KPIs and store financial data.</p>
          <form action="/upload" enctype="multipart/form-data" method="post">
            <div class="form-group">
              <label for="supplier_name">Supplier Name *</label>
              <input id="supplier_name" name="supplier_name" type="text" placeholder="e.g., Acme Corp" required />
            </div>
            <div class="form-group">
              <label for="file">PDF File *</label>
              <input id="file" name="file" type="file" accept="application/pdf" required />
            </div>
                        <button type="submit">Upload & Extract KPIs (text)</button>
          </form>
        </div>
                <div class="form-card" style="margin-top:24px">
                    <h2 style="font-size:1.1rem;margin-top:0">Table-based extraction</h2>
                    <p>Extracts company name, year, turnover and employees directly from PDF tables.</p>
                    <form action="/upload-tables" enctype="multipart/form-data" method="post">
                        <div class="form-group">
                            <label for="file2">PDF File *</label>
                            <input id="file2" name="file" type="file" accept="application/pdf" required />
                        </div>
                        <button type="submit">Upload & Extract KPIs (tables)</button>
                    </form>
                </div>
        <div class="info">
          <p><strong>Next steps:</strong></p>
          <p>After upload, access the supplier history at <code>/suppliers/{supplier_id}</code><br/>or generate a PDF report at <code>/suppliers/{supplier_id}/report</code></p>
        </div>
      </body>
    </html>
    """


@app.post("/upload")
def upload_supplier_pdf(
    supplier_name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """Upload one PDF with manual supplier name, extract KPIs, and store supplier-year record."""
    if not supplier_name or not supplier_name.strip():
        raise HTTPException(status_code=400, detail="Supplier name is required.")
    supplier_name = supplier_name.strip()

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    pdf_bytes = file.file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="The uploaded PDF is empty.")

    raw_text = extract_text_from_pdf_bytes(pdf_bytes)
    if not raw_text:
        raise HTTPException(status_code=422, detail="No readable text could be extracted from the PDF.")

    _, reporting_year = identify_supplier_and_year(raw_text, file.filename)
    if reporting_year is None:
        raise HTTPException(status_code=422, detail="Could not identify the reporting year.")

    kpis = parse_kpis(raw_text)
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


@app.post("/upload-tables")
def upload_supplier_pdf_tables(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """Upload a PDF, extract KPIs from its tables (structured JSON), store and return results."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    pdf_bytes = file.file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="The uploaded PDF is empty.")

    tables_json = pdf_tables_to_json(pdf_bytes)
    kpis = parse_kpis_from_json(tables_json)

    company_name: str = kpis.get("company_name") or (file.filename or "Unknown Supplier")
    reporting_year: Optional[int] = kpis.get("year")
    if reporting_year is None:
        raise HTTPException(status_code=422, detail="Could not identify the reporting year from the PDF tables.")

    turnover = _to_optional_float(kpis.get("turnover"))
    ebit = _to_optional_float(kpis.get("ebit"))
    ebitda = _to_optional_float(kpis.get("ebitda"))
    employees = _to_optional_int(kpis.get("employees"))
    quick_score = calculate_quick_score(
        turnover=turnover,
        ebit=ebit,
        ebitda=ebitda,
        employees=employees,
        investments=None,
    )

    try:
        supplier = _get_or_create_supplier(db, company_name)
        yearly_record, action = _upsert_supplier_year_data(
            db=db,
            supplier=supplier,
            year=reporting_year,
            source_filename=file.filename,
            turnover=turnover,
            ebit=ebit,
            ebitda=ebitda,
            employees=employees,
            investments=None,
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
            "company_name": company_name,
            "reporting_year": reporting_year,
            "kpis": {
                "turnover": turnover,
                "ebit": ebit,
                "ebitda": ebitda,
                "employees": employees,
            },
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
