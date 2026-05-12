"""Song profile metadata for imported audio workflows."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SongProfile:
    """User-provided intent for an imported song."""

    title: str = ""
    source: str = ""
    source_type: str = ""
    genre: str = "bolero"
    tempo_bpm: float = 172.0
    time_signature: str = "4/4"
    instruments: tuple[str, ...] = ("Guitarrón", "Guitar", "Violin")
    strum_style: str = "strum_with_chord_on_top"
    section_notes: str = ""
    key: str = "C"
    mode: str = "major"
    beats_per_measure: int = 4
    analysis_seconds: float | None = None
    extra: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["instruments"] = list(self.instruments)
        return data

    def write_json(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

