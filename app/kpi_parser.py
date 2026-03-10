# Purpose: Parse a small set of financial KPIs from extracted PDF text using simple regex rules.
from __future__ import annotations

import re
from typing import Optional

NUMBER_CAPTURE = r"([\(\-]?\s*[€$£]?\s*[\d.,]+(?:\s*(?:million|m|billion|bn))?\s*\)?)"
KPI_PATTERNS: dict[str, list[str]] = {
    "turnover": [
        rf"(?im)\b(?:turnover|revenue|sales)\b[^\d\n]{{0,25}}{NUMBER_CAPTURE}",
    ],
    "ebitda": [
        rf"(?im)\bebitda\b[^\d\n]{{0,25}}{NUMBER_CAPTURE}",
    ],
    "ebit": [
        rf"(?im)\bebit\b(?!da)[^\d\n]{{0,25}}{NUMBER_CAPTURE}",
    ],
    "employees": [
        r"(?im)\b(?:employees|headcount|staff)\b[^\d\n]{0,25}([\d.,]+)",
    ],
    "investments": [
        rf"(?im)\b(?:investments?|capex|capital expenditure)\b[^\d\n]{{0,25}}{NUMBER_CAPTURE}",
    ],
}


def parse_kpis(text: str) -> dict[str, Optional[float | int]]:
    """Return a small KPI dictionary with missing values left as None."""
    parsed: dict[str, Optional[float | int]] = {
        "turnover": _find_float(text, KPI_PATTERNS["turnover"]),
        "ebit": _find_float(text, KPI_PATTERNS["ebit"]),
        "ebitda": _find_float(text, KPI_PATTERNS["ebitda"]),
        "employees": _find_int(text, KPI_PATTERNS["employees"]),
        "investments": _find_float(text, KPI_PATTERNS["investments"]),
    }
    return parsed


def _find_float(text: str, patterns: list[str]) -> Optional[float]:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _parse_number(match.group(1))
    return None


def _find_int(text: str, patterns: list[str]) -> Optional[int]:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            number = _parse_number(match.group(1))
            if number is None:
                return None
            return int(round(number))
    return None


def _parse_number(raw_value: str) -> Optional[float]:
    value = raw_value.strip().lower().replace("€", "").replace("$", "").replace("£", "")
    negative = value.startswith("(") or value.startswith("-")
    value = value.strip("() ")

    multiplier = 1.0
    if value.endswith("billion"):
        value = value.removesuffix("billion").strip()
        multiplier = 1_000_000_000.0
    elif value.endswith("bn"):
        value = value.removesuffix("bn").strip()
        multiplier = 1_000_000_000.0
    elif value.endswith("million"):
        value = value.removesuffix("million").strip()
        multiplier = 1_000_000.0
    elif value.endswith("m"):
        value = value.removesuffix("m").strip()
        multiplier = 1_000_000.0

    # Handle common decimal/thousand separator combinations in a simple way.
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif value.count(",") == 1 and len(value.split(",")[-1]) in {1, 2}:
        value = value.replace(",", ".")
    else:
        value = value.replace(",", "")

    try:
        number = float(value) * multiplier
    except ValueError:
        return None

    return -number if negative else number
