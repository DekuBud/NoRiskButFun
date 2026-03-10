# Architecture

## Folder structure

- [app/main.py](app/main.py) — FastAPI routes and supplier-year upsert flow
- [app/database.py](app/database.py) — SQLAlchemy engine, session, and table creation
- [app/models.py](app/models.py) — `Supplier` and `SupplierYearData`
- [app/pdf_extractor.py](app/pdf_extractor.py) — PDF text extraction and simple supplier/year detection
- [app/kpi_parser.py](app/kpi_parser.py) — simple KPI parsing rules
- [app/scoring.py](app/scoring.py) — placeholder quick score
- [app/plot_generator.py](app/plot_generator.py) — historical plots as embedded images
- [app/news_service.py](app/news_service.py) — replaceable news service wrapper
- [app/report_generator.py](app/report_generator.py) — Jinja2 + WeasyPrint report generation
- [app/templates/report.html](app/templates/report.html) — report template

## Data flow

1. A PDF is uploaded through `POST /upload`.
2. [app/pdf_extractor.py](app/pdf_extractor.py) extracts raw text and tries to identify supplier name and reporting year.
3. [app/kpi_parser.py](app/kpi_parser.py) parses a small KPI set.
4. [app/scoring.py](app/scoring.py) calculates a placeholder quick score.
5. [app/main.py](app/main.py) stores data in `Supplier` and `SupplierYearData`.
6. `GET /suppliers/{supplier_id}` loads all yearly rows sorted by year ascending.
7. `GET /suppliers/{supplier_id}/report` builds a PDF report from stored history.

## Data model

### `Supplier`

- `id`
- `name`

### `SupplierYearData`

- `id`
- `supplier_id`
- `year`
- `turnover`
- `ebit`
- `ebitda`
- `employees`
- `investments`
- `quick_score`
- `source_filename`
- `created_at`
- `updated_at`

There is a unique constraint on `supplier_id` + `year`.

## Duplicate handling for supplier-year uploads

The app uses a simple upsert flow in [app/main.py](app/main.py):

1. Find or create the supplier by name.
2. Look for an existing `SupplierYearData` row with the same `supplier_id` and `year`.
3. If no row exists, create one.
4. If a row already exists, update that row with the newly extracted values.

This keeps duplicate handling easy to understand for version 1 and avoids storing multiple rows for the same supplier-year.

## Historical yearly comparison

Historical comparison loads all rows for one supplier ordered by `year ASC`.
That sorted list is used for:

- API responses
- report generation
- turnover-over-time plotting
- employees-over-time plotting
- future trend analysis

The business code works with supplier-year records, not a single supplier snapshot.

## Plot generation

[app/plot_generator.py](app/plot_generator.py) creates two simple matplotlib line charts from stored yearly data:

- turnover over time
- employees over time

The plots are converted into base64 image strings and embedded directly into the PDF report HTML.
This keeps version 1 small because no static file storage is required.

## News service design

[app/news_service.py](app/news_service.py) keeps the news logic separate from routes and report generation.
Version 1 uses a mock provider, but the same service can later call:

- a news API
- a web search API
- Reuters-like providers or similar business news sources

The route code only calls `get_summary()`, so the provider can be swapped without changing the rest of the app.

## Database portability

The database connection is configured through `DATABASE_URL` in [app/database.py](app/database.py).
The default value uses SQLite:

```text
sqlite:///./noriskbutfun.db
```

To switch later, change `DATABASE_URL` to a PostgreSQL-compatible URL such as:

```text
postgresql+psycopg://user:password@localhost:5432/noriskbutfun
```

The business code does not contain SQLite-specific queries.
Only the engine setup adds the standard SQLite `check_same_thread` option when needed.
That keeps a later migration to PostgreSQL or Supabase simple.

## Placeholder logic in version 1

These parts are intentionally simple and marked for later improvement:

- supplier name detection heuristics
- reporting year detection heuristics
- regex-based KPI parsing
- quick score calculation
- news summary provider integration

These placeholders are enough for a runnable prototype but should be reviewed before production use.
