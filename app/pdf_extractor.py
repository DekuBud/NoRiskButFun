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
ABSCHLUSS_KEYWORD_PATTERN = re.compile(r"(?im)(jahresabschluss|gesch[ä]ftsjahr|year|abschluss)")
YEAR_VALUE_PATTERN = re.compile(r"\b(20\d{2})\b")

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    page_texts: list[str] = []
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_texts.append(page.extract_text() or "")
    except Exception as exc:
        raise ValueError("Could not read the uploaded PDF.") from exc
    return "\n".join(page_texts).strip()

def identify_supplier_name(text: str, fallback_filename: Optional[str] = None) -> Optional[str]:
    for pattern in SUPPLIER_LABEL_PATTERNS:
        match = pattern.search(text)
        if match: return _clean_supplier_name(match.group(1))
    
    # Logic for Ziegler: Skip the 'UNTERNEHMENSREGISTER' and 'ZZ' headers
    for line in text.splitlines()[:15]:
        c = _clean_supplier_name(line)
        if c and not any(k in c.lower() for k in ["unternehmensregister", "jahresabschluss", "seite", "zieglergroup"]):
            return c
    return _supplier_name_from_filename(fallback_filename) if fallback_filename else None

def identify_reporting_year(text: str) -> Optional[int]:
    for line in text.splitlines():
        if ABSCHLUSS_KEYWORD_PATTERN.search(line):
            years = [int(y) for y in YEAR_VALUE_PATTERN.findall(line)]
            if years: return min(years)
    all_years = [int(y) for y in YEAR_VALUE_PATTERN.findall(text)]
    return max(all_years) if all_years else None

def identify_supplier_and_year(text: str, fallback_filename: Optional[str] = None) -> tuple[Optional[str], Optional[int]]:
    return identify_supplier_name(text, fallback_filename), identify_reporting_year(text)

def _supplier_name_from_filename(filename: str) -> Optional[str]:
    stem = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
    return _clean_supplier_name(stem.title()) if stem else None


def pdf_tables_to_json(pdf_bytes: bytes) -> str:
    """Extract all tables from a PDF (supplied as raw bytes) and return them as
    a JSON string in the format produced by TestScript.py.

    Each element of the returned array has the shape::

        {"page": <int>, "table_id": <int>, "data": [{...}, ...]}
    """
    import json
    all_tables: list[dict] = []
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                for table_index, table in enumerate(tables):
                    if len(table) > 1:
                        headers = [
                            str(h).replace("\n", " ") if h else f"Col_{i}"
                            for i, h in enumerate(table[0])
                        ]
                        rows = table[1:]
                        table_data = [
                            {
                                headers[i]: (
                                    str(row[i]).replace("\n", " ") if i < len(row) else None
                                )
                                for i in range(len(headers))
                            }
                            for row in rows
                        ]
                        all_tables.append(
                            {"page": page_num, "table_id": table_index + 1, "data": table_data}
                        )
    except Exception as exc:
        raise ValueError("Could not read the uploaded PDF.") from exc
    return json.dumps(all_tables, indent=4, ensure_ascii=False)

def _clean_supplier_name(value: str) -> Optional[str]:
    cleaned = re.sub(r"\s+", " ", value).strip(" :\t\r\n")
    return cleaned[:255] if cleaned else None