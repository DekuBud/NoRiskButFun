# NoRiskButFun

NoRiskButFun is a minimal FastAPI prototype for automated supplier financial reporting.
It accepts one supplier PDF, extracts raw text, tries to detect the supplier and reporting year, parses a few KPIs, stores supplier-year data in a database, and generates a simple PDF report with historical plots and a short news summary.

## Main workflow

1. Upload one supplier PDF.
2. Extract text with `pdfplumber`.
3. Detect supplier name and reporting year.
4. Parse a small KPI set.
5. Store or update `SupplierYearData` for the detected supplier-year.
6. Calculate a placeholder quick score.
7. Load historical yearly data for the supplier.
8. Generate a PDF report with plots and a short news summary.

## Tech stack

- FastAPI
- SQLAlchemy
- SQLite
- Jinja2
- WeasyPrint
- pdfplumber
- matplotlib
- python-dotenv

## Minimal file structure

- [app/main.py](app/main.py)
- [app/database.py](app/database.py)
- [app/models.py](app/models.py)
- [app/pdf_extractor.py](app/pdf_extractor.py)
- [app/kpi_parser.py](app/kpi_parser.py)
- [app/scoring.py](app/scoring.py)
- [app/plot_generator.py](app/plot_generator.py)
- [app/news_service.py](app/news_service.py)
- [app/report_generator.py](app/report_generator.py)
- [app/templates/report.html](app/templates/report.html)
- [requirements.txt](requirements.txt)
- [.env.example](.env.example)
- [README.md](README.md)
- [docs/setup.md](docs/setup.md)
- [docs/architecture.md](docs/architecture.md)

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 and upload a PDF.

Useful routes:

- `GET /`
- `POST /upload`
- `GET /suppliers/{supplier_id}`
- `GET /suppliers/{supplier_id}/report`

See [docs/setup.md](docs/setup.md) for setup details and [docs/architecture.md](docs/architecture.md) for the architecture overview.
