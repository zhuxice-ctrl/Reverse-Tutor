from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExtractResult:
    extracted_text: str
    structure: dict[str, Any]
    detected_kps: list[str]


def extract_from_image(path: str | Path) -> ExtractResult:
    """Mock-able image extraction boundary.

    The default local implementation stores no image-derived claims beyond an
    unknown placeholder. Tests monkeypatch this function; live vision can be
    wired here later without changing the HTTP/data contract.
    """
    return ExtractResult(
        extracted_text="",
        structure={"kind": "unknown", "stem": None, "options": [], "hints": []},
        detected_kps=[],
    )
