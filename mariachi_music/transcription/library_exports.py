"""Library export helpers for imported-song draft scores."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from mariachi_music.core.part import Part
from mariachi_music.core.project_io import save_score_project
from mariachi_music.core.score import Score
from mariachi_music.transcription.audio_verification import synthesize_score_to_wav


@dataclass(frozen=True)
class LibraryExportResult:
    full_score_dir: str
    part_dirs: dict[str, str]


def export_score_library(score: Score, song_dir: str | Path) -> LibraryExportResult:
    """Write full-score and per-part files under an imported song folder.

    Layout:
        song_dir/
          score/
            full_score.musicxml
            full_score.mid
            full_score.wav
            full_score.mariachi.json
          parts/
            guitar/
              guitar.musicxml
              guitar.mid
              guitar.wav
              guitar.mariachi.json
    """
    song_dir = Path(song_dir)
    score_dir = song_dir / "score"
    parts_root = song_dir / "parts"
    score_dir.mkdir(parents=True, exist_ok=True)
    parts_root.mkdir(parents=True, exist_ok=True)

    save_score_project(score, score_dir / "full_score.mariachi.json")
    score.export_musicxml(score_dir / "full_score.musicxml")
    score.export_midi(score_dir / "full_score.mid")
    synthesize_score_to_wav(score, score_dir / "full_score.wav")

    part_dirs: dict[str, str] = {}
    seen: dict[str, int] = {}
    for part in score.parts:
        part_score = _score_for_part(score, part)
        slug = _unique_slug(_slugify(part.instrument.name), seen)
        part_dir = parts_root / slug
        part_dir.mkdir(parents=True, exist_ok=True)

        save_score_project(part_score, part_dir / f"{slug}.mariachi.json")
        part_score.export_musicxml(part_dir / f"{slug}.musicxml")
        part_score.export_midi(part_dir / f"{slug}.mid")
        synthesize_score_to_wav(part_score, part_dir / f"{slug}.wav")
        part_dirs[slug] = str(part_dir)

    return LibraryExportResult(full_score_dir=str(score_dir), part_dirs=part_dirs)


def _score_for_part(source: Score, part: Part) -> Score:
    score = Score(
        title=f"{source.title} - {part.instrument.name}",
        composer=source.composer,
        tempo=source.tempo,
        key_signature=source.key_signature,
        time_signature=source.time_signature,
    )
    score.add_part(part)
    return score


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", text.strip().lower())
    return slug.strip("_") or "part"


def _unique_slug(slug: str, seen: dict[str, int]) -> str:
    count = seen.get(slug, 0) + 1
    seen[slug] = count
    return slug if count == 1 else f"{slug}_{count}"
