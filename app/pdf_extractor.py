# Purpose: Extract raw PDF text and apply simple heuristics for supplier and year detection.
from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Optional

import pdfplumber

SUPPLIER_LABEL_PATTERNS = [
    re.compile(r"(?im)^(?:supplier|company|entity)\s*[:\-]\s*(.+)$"),
    re.compile(r"(?im)^(?:name)\s*[:\-]\s*(.+)$"),
]
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from all PDF pages and join it into one plain text string."""
    page_texts: list[str] = []

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_texts.append(page.extract_text() or "")
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        raise ValueError("Could not read the uploaded PDF.") from exc

    return "\n".join(page_texts).strip()


def identify_supplier_name(text: str, fallback_filename: Optional[str] = None) -> Optional[str]:
    """Try a few readable heuristics before falling back to the filename."""
    for pattern in SUPPLIER_LABEL_PATTERNS:
        match = pattern.search(text)
        if match:
            return _clean_supplier_name(match.group(1))

    for line in text.splitlines():
        cleaned_line = _clean_supplier_name(line)
        if cleaned_line and len(cleaned_line.split()) <= 8:
            return cleaned_line

    if fallback_filename:
        return _supplier_name_from_filename(fallback_filename)

    return None


def identify_reporting_year(text: str) -> Optional[int]:
    """Return the newest year found in the document text."""
    years = [int(year) for year in YEAR_PATTERN.findall(text)]
    if not years:
        return None
    return max(years)


def identify_supplier_and_year(text: str, fallback_filename: Optional[str] = None) -> tuple[Optional[str], Optional[int]]:
    """Return both detected values in one small helper."""
    return identify_supplier_name(text, fallback_filename), identify_reporting_year(text)


def _supplier_name_from_filename(filename: str) -> Optional[str]:
    stem = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
    if not stem:
        return None
    return _clean_supplier_name(stem.title())


def _clean_supplier_name(value: str) -> Optional[str]:
    cleaned = re.sub(r"\s+", " ", value).strip(" :\t\r\n")
    if not cleaned:
        return None
    # TODO: Replace this heuristic with a more reliable supplier extraction step.
    return cleaned[:255]
