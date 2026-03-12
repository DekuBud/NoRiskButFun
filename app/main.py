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
          input[type="file"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; box-sizing: border-box; }
          input[type="file"]:focus { outline: none; border-color: #0066cc; box-shadow: 0 0 0 3px rgba(0,102,204,0.1); }
          button { background: #0066cc; color: white; padding: 12px 24px; border: none; border-radius: 4px; font-size: 16px; font-weight: 600; cursor: pointer; width: 100%; }
          button:hover { background: #0052a3; }
          button:disabled { background: #7aaedd; cursor: not-allowed; }
          .info { background: #f0f8ff; padding: 15px; border-left: 4px solid #0066cc; margin-top: 20px; color: #333; }
          code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; }

          /* Loading overlay */
          #loading-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(245, 245, 245, 0.92);
            z-index: 1000;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 24px;
          }
          #loading-overlay.active { display: flex; }
          .spinner {
            width: 56px; height: 56px;
            border: 5px solid #d0e4f7;
            border-top-color: #0066cc;
            border-radius: 50%;
            animation: spin 0.9s linear infinite;
          }
          @keyframes spin { to { transform: rotate(360deg); } }
          .loading-text { font-size: 1.1rem; color: #333; font-weight: 500; }
          .loading-sub { font-size: 0.85rem; color: #666; }
        </style>
      </head>
      <body>
        <!-- Loading overlay -->
        <div id="loading-overlay">
          <div class="spinner"></div>
          <div class="loading-text">Extracting KPIs&hellip;</div>
          <div class="loading-sub">This may take a few seconds. Please wait.</div>
        </div>

        <h1>NoRiskButFun</h1>
        <div class="form-card">
          <h2 style="font-size:1.1rem;margin-top:0">Table-based extraction</h2>
          <p>Extracts company name, year, turnover and employees directly from PDF tables.</p>
          <form id="upload-form" action="/upload-tables" enctype="multipart/form-data" method="post">
            <div class="form-group">
              <label for="file">PDF File *</label>
              <input id="file" name="file" type="file" accept="application/pdf" required />
            </div>
            <button type="submit" id="submit-btn">Upload &amp; Extract KPIs</button>
          </form>
        </div>
        <div class="info">
          <p><strong>Next steps:</strong></p>
          <p>After upload, access the supplier history at <code>/suppliers/{supplier_id}</code><br/>or generate a PDF report at <code>/suppliers/{supplier_id}/report</code></p>
        </div>

        <script>
          document.getElementById('upload-form').addEventListener('submit', function() {
            document.getElementById('submit-btn').disabled = true;
            document.getElementById('loading-overlay').classList.add('active');
          });
        </script>
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
    # Pflichtfelder Prüfen

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
def upload_supplier_pdf_tables(  # noqa: C901
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Upload a PDF, extract KPIs from its tables (structured JSON), store and return results."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    pdf_bytes = file.file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="The uploaded PDF is empty.")

    # tables_json = pdf_tables_to_json(pdf_bytes)
    # kpis = parse_kpis_from_json(tables_json)

    raw_text = extract_text_from_pdf_bytes(pdf_bytes)
    tables_json = pdf_tables_to_json(pdf_bytes)

    # The parser now uses text as a fallback to identify the year
    # kpis = parse_kpis_from_json(tables_json, raw_text=raw_text)
    kpis = parse_kpis(raw_text)

    company_name: str = kpis.get("name") or (file.filename or "Unknown Supplier")
    reporting_year: Optional[int] = kpis.get("year")
    if reporting_year is None:
        print("Warning: Reporting year could not be identified from tables, falling back to text extraction.")
        #raise HTTPException(status_code=422, detail="Could not identify the reporting year from the PDF tables.")

    turnover = _to_optional_float(kpis.get("turnover"))
    ebit = _to_optional_float(kpis.get("ebit"))
    ebitda = _to_optional_float(kpis.get("ebitda"))
    employees = _to_optional_int(kpis.get("employees"))
    investments = _to_optional_float(kpis.get("investments"))
    quick_score = calculate_quick_score(
        turnover=turnover,
        ebit=ebit,
        ebitda=ebitda,
        employees=employees,
        investments=investments,
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
            investments=investments,
            quick_score=quick_score,
        )
        db.commit()
        db.refresh(supplier)
        db.refresh(yearly_record)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to store extracted supplier data.") from exc

    def _fmt(value: object, suffix: str = "") -> str:
        return f"{value:,.2f}{suffix}" if isinstance(value, float) else (str(value) if value is not None else "n/a")

    action_label = "Created new record" if action == "created" else "Updated existing record"
    score_color = "#1a7f37" if (quick_score or 0) >= 60 else ("#d97706" if (quick_score or 0) >= 30 else "#cf222e")

    html = f"""
    <html>
        <head>
            <title>Extraction Result – NoRiskButFun</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 640px; margin: 40px auto; padding: 20px; background: #f5f5f5; }}
                h1 {{ color: #333; margin-bottom: 4px; }}
                .sub {{ color: #666; margin-bottom: 28px; font-size: 0.9rem; }}
                .card {{ background: white; border-radius: 8px; padding: 24px 28px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
                .card h2 {{ font-size: 1rem; color: #0066cc; margin: 0 0 16px; text-transform: uppercase; letter-spacing: .05em; }}
                table {{ width: 100%; border-collapse: collapse; }}
                td {{ padding: 8px 6px; border-bottom: 1px solid #f0f0f0; font-size: 0.92rem; }}
                td:first-child {{ color: #555; width: 48%; }}
                td:last-child {{ font-weight: 600; color: #222; }}
                .badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 0.78rem; font-weight: 600; }}
                .badge-created {{ background: #dafbe1; color: #1a7f37; }}
                .badge-updated {{ background: #ddf4ff; color: #0066cc; }}
                .score {{ font-size: 1.6rem; font-weight: 700; color: {score_color}; }}
                .back {{ display: inline-block; margin-top: 8px; padding: 10px 20px; background: #0066cc; color: white; border-radius: 4px; text-decoration: none; font-weight: 600; font-size: 0.9rem; }}
                .back:hover {{ background: #0052a3; }}
            </style>
        </head>
        <body>
            <h1>Extraction Result</h1>
            <p class="sub">File: <strong>{file.filename}</strong> &nbsp;·&nbsp; <span class="badge {'badge-created' if action == 'created' else 'badge-updated'}">{action_label}</span></p>

            <div class="card">
                <h2>Supplier</h2>
                <table>
                    <tr><td>Name</td><td>{company_name}</td></tr>
                    <tr><td>Supplier ID</td><td>{supplier.id}</td></tr>
                    <tr><td>Reporting Year</td><td>{reporting_year if reporting_year is not None else "n/a"}</td></tr>
                </table>
            </div>

            <div class="card">
                <h2>Extracted KPIs</h2>
                <table>
                    <tr><td>Turnover</td><td>{_fmt(turnover, " €")}</td></tr>
                    <tr><td>EBIT</td><td>{_fmt(ebit, " €")}</td></tr>
                    <tr><td>EBITDA</td><td>{_fmt(ebitda, " €")}</td></tr>
                    <tr><td>Employees</td><td>{employees if employees is not None else "n/a"}</td></tr>
                    <tr><td>Investments</td><td>{_fmt(investments, " €")}</td></tr>
                </table>
            </div>

            <div class="card">
                <h2>Quick Score</h2>
                <p class="score">{_fmt(quick_score)} <span style="font-size:1rem;font-weight:400;color:#666;">/ 100</span></p>
            </div>

            <a class="back" href="/">&#8592; Upload another PDF</a>
        </body>
    </html>
    """
    return HTMLResponse(content=html)


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
