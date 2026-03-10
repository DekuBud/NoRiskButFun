# Purpose: Generate simple historical KPI plots and return them as embeddable image data.
from __future__ import annotations

import base64
from io import BytesIO
from typing import Any, Iterable, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def build_historical_plots(records: Iterable[Any]) -> dict[str, Optional[str]]:
    """Create small turnover and employee history charts from sorted yearly data."""
    records = sorted(records, key=lambda item: item.year)

    turnover_points = [(record.year, record.turnover) for record in records if record.turnover is not None]
    employee_points = [(record.year, record.employees) for record in records if record.employees is not None]

    return {
        "turnover": _create_line_plot(turnover_points, "Turnover over time", "Turnover"),
        "employees": _create_line_plot(employee_points, "Employees over time", "Employees"),
    }


def _create_line_plot(
    points: list[tuple[int, float | int]],
    title: str,
    y_label: str,
) -> Optional[str]:
    if not points:
        return None

    years = [year for year, _ in points]
    values = [value for _, value in points]

    fig, ax = plt.subplots(figsize=(6, 3))
    ax.plot(years, values, marker="o", linewidth=2)
    ax.set_title(title)
    ax.set_xlabel("Year")
    ax.set_ylabel(y_label)
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()

    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=150)
    plt.close(fig)

    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"
