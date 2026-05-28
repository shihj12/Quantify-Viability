"""Project data model and JSON session persistence.

A *project* is the full state of one quantification run: the two source
folders, every image with its tuned threshold and measurement, and progress.
It serializes to a single JSON session file (no pixel data) so a run can be
closed and resumed.
"""

from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = 2
SESSION_SUFFIX = ".qviability.json"

DEFAULT_BG_RADIUS = 50          # rolling-ball radius (ImageJ "Subtract Background" default)


class Channel:
    """Channel name constants (plain strings — JSON-friendly)."""
    GREEN = "Green"
    RED = "Red"


@dataclass
class Measurement:
    """Result of thresholding one image at a chosen threshold."""
    threshold: int
    positive_pixels: int
    total_pixels: int
    positive_area_pct: float
    mean_intensity_positive: float
    integrated_intensity: float
    method: str = "Manual"


@dataclass
class ImageEntry:
    """One image in the project and everything tuned for it."""
    path: str
    display_name: str
    channel: str                       # Channel.GREEN / Channel.RED
    bit_depth: int = 8
    max_value: int = 255
    width: int = 0
    height: int = 0
    threshold: int | None = None       # None until first tuned
    auto_method: str = "MaxEntropy"
    brightness: float = 0.0            # display-only
    contrast: float = 1.0              # display-only
    done: bool = False
    missing: bool = False              # file vanished since session was saved
    exclusions: list = field(default_factory=list)   # [x, y, w, h] rectangles
    measurement: Measurement | None = None


@dataclass
class Project:
    """A full quantification run."""
    green_folder: str | None = None
    red_folder: str | None = None
    images: list[ImageEntry] = field(default_factory=list)
    current_index: int = 0
    fine_step: int = 1
    coarse_step: int = 10
    output_folder: str | None = None
    subtract_background: bool = False        # rolling-ball background subtraction
    green_bg_radius: int = DEFAULT_BG_RADIUS  # rolling-ball radius for green/GFP
    red_bg_radius: int = DEFAULT_BG_RADIUS    # rolling-ball radius for red/RFP
    schema_version: int = SCHEMA_VERSION

    # --- progress helpers -------------------------------------------------
    def radius_for(self, channel: str) -> int:
        """Rolling-ball radius to use for an image in *channel*."""
        return self.red_bg_radius if channel == Channel.RED else self.green_bg_radius

    def done_count(self) -> int:
        return sum(1 for e in self.images if e.done)

    def all_done(self) -> bool:
        return bool(self.images) and all(e.done for e in self.images)

    def first_unfinished(self) -> int:
        for i, e in enumerate(self.images):
            if not e.done:
                return i
        return 0


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
def _filter_fields(cls, data: dict) -> dict:
    """Keep only keys that are real fields of dataclass *cls*."""
    names = {f.name for f in dataclasses.fields(cls)}
    return {k: v for k, v in data.items() if k in names}


def default_session_path(project: Project) -> str | None:
    """Where the session file lives: inside the green folder, else the red."""
    folder = project.green_folder or project.red_folder
    if not folder:
        return None
    name = Path(folder).name or "session"
    return str(Path(folder) / f"{name}{SESSION_SUFFIX}")


def find_session(folder: str) -> str | None:
    """Return an existing ``*.qviability.json`` in *folder*, if any."""
    p = Path(folder)
    if not p.is_dir():
        return None
    for f in p.iterdir():
        if f.is_file() and f.name.endswith(SESSION_SUFFIX):
            return str(f)
    return None


def save_project(project: Project, path: str) -> None:
    """Write *project* to *path* atomically (temp file + os.replace)."""
    data = dataclasses.asdict(project)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)


def load_project(path: str) -> Project:
    """Load a Project from a JSON session file."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    images: list[ImageEntry] = []
    for raw in data.get("images", []):
        meas_raw = raw.get("measurement")
        measurement = (Measurement(**_filter_fields(Measurement, meas_raw))
                       if meas_raw else None)
        entry_data = _filter_fields(ImageEntry, raw)
        entry_data["measurement"] = measurement
        images.append(ImageEntry(**entry_data))

    proj_data = _filter_fields(Project, data)
    proj_data["images"] = images
    return Project(**proj_data)
