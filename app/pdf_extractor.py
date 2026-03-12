# app/pdf_extractor.py
import re
import pdfplumber
import json
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    page_texts = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_texts.append(page.extract_text() or "")
    return "\n".join(page_texts).strip()

def pdf_tables_to_json(pdf_bytes: bytes) -> str:
    """Extract all tables from a PDF as a JSON array of {page, table_id, data} objects.
    Each data row is a dict of header -> value so column identity is preserved.
    """
    all_tables = []
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
    return json.dumps(all_tables, indent=4, ensure_ascii=False)

def identify_supplier_and_year(text: str, filename: str) -> Tuple[Optional[str], Optional[int]]:
    year_match = re.search(r"(?im)(?:jahresabschluss|geschäftsjahr).{0,30}\b(20\d{2})\b", text)
    year = int(year_match.group(1)) if year_match else None
    supplier = None
    for line in text.splitlines()[:15]:
        clean = line.strip(" :\t\r\n")
        if clean and not any(k in clean.lower() for k in ["unternehmensregister", "jahresabschluss", "seite"]):
            supplier = clean
            break
    if not supplier:
        supplier = Path(filename).stem.replace("_", " ")
    return supplier, year