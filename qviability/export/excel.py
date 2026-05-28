"""Excel export — one row per image, all measurement metrics as columns."""

from __future__ import annotations

import pandas as pd

from ..core.project import Project

COLUMNS = [
    "Filename", "Channel", "Positive pixels", "% above threshold",
]


def build_dataframe(project: Project) -> pd.DataFrame:
    """One row per image, sorted by channel then filename."""
    rows = []
    for e in project.images:
        m = e.measurement
        rows.append({
            "Filename": e.display_name,
            "Channel": e.channel,
            "Positive pixels": m.positive_pixels if m else None,
            "% above threshold": round(m.positive_area_pct, 4) if m else None,
        })
    df = pd.DataFrame(rows, columns=COLUMNS)
    if not df.empty:
        df = df.sort_values(["Channel", "Filename"]).reset_index(drop=True)
    return df


def write_xlsx(project: Project, path: str) -> None:
    """Write the results workbook to *path*."""
    build_dataframe(project).to_excel(path, index=False, engine="openpyxl")
