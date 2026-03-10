# Purpose: Calculate a small placeholder quick score from the KPIs that were extracted.
from __future__ import annotations

from typing import Optional


def calculate_quick_score(
    turnover: Optional[float],
    ebit: Optional[float],
    ebitda: Optional[float],
    employees: Optional[int],
    investments: Optional[float],
) -> Optional[float]:
    """Return a simple score between 0 and 100 based on available KPI signals."""
    score = 50.0
    has_signal = False

    if turnover is not None:
        has_signal = True
        score += 10 if turnover > 0 else -15

    if ebit is not None:
        has_signal = True
        score += 15 if ebit > 0 else -20

    if ebitda is not None:
        has_signal = True
        score += 15 if ebitda > 0 else -15

    if employees is not None:
        has_signal = True
        score += 5 if employees > 0 else -5

    if investments is not None:
        has_signal = True
        score += 5 if investments >= 0 else -5

    if not has_signal:
        return None

    # TODO: Replace this placeholder with a business-approved scoring model.
    return round(max(0.0, min(100.0, score)), 2)
