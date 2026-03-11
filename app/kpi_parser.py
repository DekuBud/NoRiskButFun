from __future__ import annotations
import json
import re
from typing import Any, Optional

# Expanded to handle numbers appearing after significant whitespace, including newlines.
NUMBER_CAPTURE = r"(?:[^\d-]{0,140})([\(\-]?\s*[€$£]?\s*\d[\d.,]*(?:\s*(?:million|mio\.?|mrd\.?|m|billion|bn))?\s*\)?)"
NUMBER_CAPTURE_STRICT = (
    r"(?:[^\d-]{0,140})"
    r"([\(\-]?\s*[€$£]?\s*(?=\d[\d.,]*(?:\s*(?:million|mio\.?|mrd\.?|m|billion|bn)|[.,]))"
    r"\d[\d.,]*(?:\s*(?:million|mio\.?|mrd\.?|m|billion|bn))?\s*\)?)"
)

_FINANCIAL_NUM_RE = re.compile(r"(?<![.\d])(\d+(?:[.,]\d+)+)(?![.\d])")
_METRIC_NUM_RE = re.compile(
    r"(?i)(?<![\d./])"
    r"(" 
    r"(?:[\(\-]?\s*(?:\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+[.,]\d+))"
    r"(?:\s*(?:million|mio\.?|mrd\.?|m|billion|bn))?"
    r"\s*\)?"
    r")"
    r"(?![\d/])"
)
_TURNOVER_LABEL_RE = re.compile(r"(?im)\b(?:Umsatzerlöse|Umsatzerloese|revenue|sales|Bilanzgewinn)\b")
_EBIT_LABELS = [
    "EBIT",
    "Betriebsergebnis",
    "Operatives Ergebnis",
    "Ergebnis vor Zinsen und Steuern",
]
_EBITDA_LABELS = [
    "EBITDA",
    "Ergebnis vor Zinsen, Steuern und Abschreibungen",
    "Ergebnis vor Zinsen und Abschreibungen",
]
_DEPRECIATION_LABELS = [
    "Abschreibungen",
    "Abschreibung",
    "Abschreibungen auf",
]

KPI_PATTERNS: dict[str, list[str]] = {
    "turnover": [
        rf"(?im)\b(?:Umsatzerlöse|Umsatzerloese|revenue|sales)\b{NUMBER_CAPTURE}",
    ],
    "ebitda": [
        rf"(?im)\bebitda\b{NUMBER_CAPTURE_STRICT}",
    ],
    "ebit": [
        # Targets 'Betriebsergebnis' specifically for Ziegler
        rf"(?im)\b(?:ebit|Betriebsergebnis|Operatives Ergebnis)\b(?!da){NUMBER_CAPTURE_STRICT}",
    ],
    "depreciation": [
        # Targets 'Abschreibungen' for EBITDA calculation
        rf"(?im)\b(?:Abschreibungen\s+auf|Abschreibung\s+auf|planmäßige\s+Abschreibungen|depreciation|amortization)\b{NUMBER_CAPTURE_STRICT}",
    ],
    "employees": [
        r"(?im)\b(?:employees|headcount|staff|Mitarbeiter|Beschäftigte)\b[^\d\n]{0,50}([\d.,]+)",
    ],
    "investments": [
        rf"(?im)\b(?:investments?|capex|Investitionen|Anlagevermögen)\b{NUMBER_CAPTURE}",
    ],
}

def parse_kpis(text: str) -> dict[str, Optional[float | int]]:
    # 1. Extraction
    ebit = _find_float(text, KPI_PATTERNS["ebit"]) or _find_metric_in_block(
        text,
        labels=_EBIT_LABELS,
    )
    ebitda = _find_float(text, KPI_PATTERNS["ebitda"]) or _find_metric_in_block(
        text,
        labels=_EBITDA_LABELS,
    )
    depreciation = _find_float(text, KPI_PATTERNS["depreciation"]) or _find_depreciation_in_block(text)

    # 2. CALCULATION LOGIC: If EBITDA is absent (common in HGB), calculate it.
    if ebitda is None and ebit is not None and depreciation is not None:
        print("EBITDA not found, but EBIT and Depreciation are available. Calculating EBITDA as EBIT + Depreciation.")
        ebitda = ebit + depreciation
    if ebit is None and ebitda is not None and depreciation is not None:
        print("EBIT not found, but EBITDA and Depreciation are available. Calculating EBIT as EBITDA - Depreciation.")
        ebit = ebitda - depreciation

    parsed: dict[str, Optional[float | int]] = {
        "turnover": (_find_float(text, KPI_PATTERNS["turnover"]) or _find_turnover_in_table(text)),
        "ebit": ebit,
        "ebitda": ebitda,
        "employees": _find_int(text, KPI_PATTERNS["employees"]),
        "investments": _find_float(text, KPI_PATTERNS["investments"]),
    }
    return parsed

def _find_turnover_in_table(text: str) -> Optional[float]:
    label_match = _TURNOVER_LABEL_RE.search(text)
    if not label_match: return None
    block = text[label_match.start(): label_match.start() + 400]
    candidates = _FINANCIAL_NUM_RE.findall(block)
    financial = [n for n in candidates if not re.fullmatch(r"\d{4}", n) and not re.fullmatch(r"\d{4}[,.]\d{2}", n)]
    return _parse_number(financial[-1]) if financial else None

def _find_metric_in_block(text: str, labels: list[str]) -> Optional[float]:
    for label in labels:
        label_pattern = re.compile(rf"(?im)\b{re.escape(label)}\b")
        for match in label_pattern.finditer(text):
            block = text[match.start(): match.start() + 320]
            candidates = _METRIC_NUM_RE.findall(block)
            for candidate in candidates:
                if re.fullmatch(r"\d{4}", candidate):
                    continue
                if re.fullmatch(r"\d{4}[,.]\d{2}", candidate):
                    continue
                parsed = _parse_number(candidate)
                if parsed is not None:
                    return parsed
    return None

def _find_depreciation_in_block(text: str) -> Optional[float]:
    for label in _DEPRECIATION_LABELS:
        label_pattern = re.compile(rf"(?im)\b{re.escape(label)}\b")
        for match in label_pattern.finditer(text):
            left_context = text[max(0, match.start() - 100): match.start()].lower()
            if "ergebnis vor" in left_context:
                continue

            block = text[match.start(): match.start() + 320]
            first_line = block.splitlines()[0].lower() if block else ""
            if "ergebnis vor" in first_line:
                continue

            candidates = _METRIC_NUM_RE.findall(block)
            for candidate in candidates:
                if re.fullmatch(r"\d{4}", candidate):
                    continue
                if re.fullmatch(r"\d{4}[,.]\d{2}", candidate):
                    continue
                parsed = _parse_number(candidate)
                if parsed is not None:
                    return parsed
    return None

def _find_float(text: str, patterns: list[str]) -> Optional[float]:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match: return _parse_number(match.group(1))
    return None

def _find_int(text: str, patterns: list[str]) -> Optional[int]:
    val = _find_float(text, patterns)
    return int(round(val)) if val is not None else None

def _parse_number(raw_value: str) -> Optional[float]:
    if not raw_value: return None
    value = raw_value.strip().lower().replace("€", "").replace("$", "").replace("£", "")
    negative = value.startswith("(") or value.startswith("-")
    value = value.strip("() ")
    
    multiplier = 1.0
    suffix_match = re.search(r"(mrd\.?|billion|bn|mio\.?|million|m)\s*$", value)
    if suffix_match:
        suffix = suffix_match.group(1).rstrip(".")
        value = value[: suffix_match.start()].strip()
        if suffix in {"mrd", "billion", "bn"}: multiplier = 1e9
        elif suffix in {"mio", "million", "m"}: multiplier = 1e6
    
    # Handle German separators
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".") if value.rfind(",") > value.rfind(".") else value.replace(",", "")
    elif value.count(",") == 1 and len(value.split(",")[-1]) in {1, 2}:
        value = value.replace(",", ".")
    else:
        value = value.replace(",", "")
    
    try:
        number = float(value) * multiplier
        return -number if negative else number
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# JSON-based KPI extraction (output of TestScript.py / pdf_tables_to_json)
# ---------------------------------------------------------------------------

def parse_kpis_from_json(json_input: str | list) -> dict[str, Any]:
    """Extract structured KPIs from the JSON produced by pdf_tables_to_json.

    Returns a dict with keys: company_name, year, turnover, ebit, ebitda, employees.
    Values are None when not found.
    """
    tables: list[dict] = json.loads(json_input) if isinstance(json_input, str) else json_input

    company_name: Optional[str] = None
    year: Optional[int] = None
    turnover: Optional[float] = None
    ebit: Optional[float] = None
    ebitda: Optional[float] = None
    employees: Optional[float] = None

    result_after_taxes: Optional[float] = None
    taxes: Optional[float] = None
    interest_expense: Optional[float] = None
    depreciation: Optional[float] = None

    for table in tables:
        data: list[dict] = table.get("data", [])
        if not data:
            continue

        # --- Company name -------------------------------------------------
        # Page 10, table 1: the first row has two keys; the one that is NOT
        # "Firmenname laut Registergericht:" is the company name.
        if company_name is None:
            first_row = data[0]
            keys = list(first_row.keys())
            name_key = next(
                (k for k in keys if k != "Firmenname laut Registergericht:"), None
            )
            if name_key and "Firmenname laut Registergericht:" in first_row:
                company_name = name_key

        # --- Year ---------------------------------------------------------
        # Look for a value matching "Jahresergebnis <YYYY>" pattern
        if year is None:
            for row in data:
                for v in row.values():
                    if isinstance(v, str):
                        m = re.search(r"Jahresergebnis\s+(\d{4})", v)
                        if m:
                            year = int(m.group(1))
                            break
                if year:
                    break

        # --- Turnover -----------------------------------------------------
        # Row where Col_0 starts with "1. Umsatzerlöse" (or variant); use Col_2
        if turnover is None:
            for row in data:
                col0 = row.get("Col_0", "") or ""
                if re.search(r"(?i)umsatzerlöse|umsatzerl[oö]se|1\.\s*umsatz", col0):
                    raw = row.get("Col_2") or row.get("Geschäftsjahr") or row.get("Col_1")
                    if raw and isinstance(raw, str) and re.search(r"\d", raw):
                        turnover = _parse_number(raw)
                        break

        # --- EBIT / EBITDA components ------------------------------------
        # EBIT = Ergebnis nach Steuern + Steuern vom Einkommen + Zinsen u. ähnliche Aufwendungen
        # EBITDA = EBIT + Abschreibungen
        for idx, row in enumerate(data):
            col0 = (row.get("Col_0") or "") if isinstance(row, dict) else ""
            if not isinstance(col0, str):
                continue
            raw = row.get("Col_2") or row.get("Geschäftsjahr") or row.get("Col_1")
            if not isinstance(raw, str) or not re.search(r"\d", raw):
                parsed_value = None
            else:
                parsed_value = _parse_number(raw)

            col0_norm = col0.lower()
            if result_after_taxes is None and "ergebnis nach steuern" in col0_norm and parsed_value is not None:
                result_after_taxes = parsed_value
            elif taxes is None and "steuern vom einkommen" in col0_norm and parsed_value is not None:
                taxes = parsed_value
            elif interest_expense is None and "zinsen" in col0_norm and "aufwendungen" in col0_norm and parsed_value is not None:
                interest_expense = parsed_value
            elif depreciation is None and "abschreib" in col0_norm:
                if parsed_value is not None:
                    depreciation = parsed_value
                else:
                    for follow_row in data[idx + 1 : idx + 5]:
                        next_raw = (
                            follow_row.get("Col_2")
                            or follow_row.get("Geschäftsjahr")
                            or follow_row.get("Col_1")
                        )
                        if not isinstance(next_raw, str) or not re.search(r"\d", next_raw):
                            continue
                        next_value = _parse_number(next_raw)
                        if next_value is not None:
                            depreciation = next_value
                            break

        # --- Employees ----------------------------------------------------
        # Table with "Gewerbliche Arbeiter" column; last row (empty label) holds total
        if employees is None and "Gewerbliche Arbeiter" in (data[0] if data else {}):
            for row in data:
                if row.get("Gewerbliche Arbeiter") == "":
                    # The total is the value of the second key
                    keys = list(row.keys())
                    if len(keys) >= 2:
                        raw = row[keys[1]]
                        if raw and isinstance(raw, str):
                            employees = _parse_number(raw)
                    break

    if ebit is None and result_after_taxes is not None and taxes is not None and interest_expense is not None:
        ebit = result_after_taxes + taxes + interest_expense

    if ebitda is None and ebit is not None and depreciation is not None:
        ebitda = ebit + depreciation

    return {
        "company_name": company_name,
        "year": year,
        "turnover": turnover,
        "ebit": ebit,
        "ebitda": ebitda,
        "employees": int(round(employees)) if employees is not None else None,
    }
