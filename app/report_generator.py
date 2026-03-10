# Purpose: Render a basic HTML report and turn it into a PDF document with WeasyPrint.
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from app.plot_generator import build_historical_plots

TEMPLATES_DIR = Path(__file__).parent / "templates"

env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


def generate_supplier_report_pdf(
    supplier_name: str,
    yearly_records: Iterable[object],
    news_summary: str,
    focus_year: Optional[int] = None,
) -> bytes:
    """Render the stored supplier data into a single PDF report."""
    ordered_records = sorted(yearly_records, key=lambda item: item.year)
    if not ordered_records:
        raise ValueError("At least one yearly record is required to build a report.")

    focus_record = _select_focus_record(ordered_records, focus_year)
    plots = build_historical_plots(ordered_records)
    year_range = _format_year_range(ordered_records)

    template = env.get_template("report.html")
    html = template.render(
        supplier_name=supplier_name,
        focus_record=focus_record,
        ordered_records=ordered_records,
        year_range=year_range,
        news_summary=news_summary,
        plots=plots,
    )
    return HTML(string=html, base_url=str(TEMPLATES_DIR)).write_pdf()


def _select_focus_record(records: list[object], focus_year: Optional[int]) -> object:
    if focus_year is None:
        return records[-1]

    for record in records:
        if record.year == focus_year:
            return record

    raise ValueError(f"No yearly record found for year {focus_year}.")


def _format_year_range(records: list[object]) -> str:
    years = [record.year for record in records]
    if len(years) == 1:
        return str(years[0])
    return f"{years[0]} - {years[-1]}"
