"""Excel export — one row per image, all measurement metrics as columns."""

from __future__ import annotations

import pandas as pd

from ..core.project import Project

COLUMNS = [
    "filename", "channel", "bit_depth", "threshold", "threshold_method",
    "background_subtracted", "positive_pixels", "positive_area_pct",
    "mean_intensity_positive", "integrated_intensity",
    "image_width", "image_height",
]


def build_dataframe(project: Project) -> pd.DataFrame:
    """One row per image, sorted by channel then filename."""
    rows = []
    for e in project.images:
        m = e.measurement
        rows.append({
            "filename": e.display_name,
            "channel": e.channel,
            "bit_depth": e.bit_depth,
            "threshold": e.threshold,
            "threshold_method": (m.method if m else e.auto_method),
            "background_subtracted": project.subtract_background,
            "positive_pixels": m.positive_pixels if m else None,
            "positive_area_pct": round(m.positive_area_pct, 4) if m else None,
            "mean_intensity_positive": (round(m.mean_intensity_positive, 4)
                                        if m else None),
            "integrated_intensity": m.integrated_intensity if m else None,
            "image_width": e.width,
            "image_height": e.height,
        })
    df = pd.DataFrame(rows, columns=COLUMNS)
    if not df.empty:
        df = df.sort_values(["channel", "filename"]).reset_index(drop=True)
    return df


def write_xlsx(project: Project, path: str) -> None:
    """Write the results workbook to *path*."""
    build_dataframe(project).to_excel(path, index=False, engine="openpyxl")
