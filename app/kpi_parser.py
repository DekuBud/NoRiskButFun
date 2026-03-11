from __future__ import annotations
import re
from typing import Optional

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