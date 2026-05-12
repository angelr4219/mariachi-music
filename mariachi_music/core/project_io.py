"""JSON project save/load for Score objects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mariachi_music.core.duration import Duration
from mariachi_music.core.instrument import Instrument
from mariachi_music.core.key_signature import KeySignature
from mariachi_music.core.measure import Measure
from mariachi_music.core.note import Note, Rest
from mariachi_music.core.part import Part
from mariachi_music.core.pitch import Pitch
from mariachi_music.core.score import Score
from mariachi_music.core.tempo import Tempo
from mariachi_music.core.time_signature import TimeSignature


PROJECT_VERSION = 1


def score_to_dict(score: Score) -> dict[str, Any]:
    """Serialize a Score to plain JSON-compatible data."""
    return {
        "version": PROJECT_VERSION,
        "title": score.title,
        "composer": score.composer,
        "tempo": score.tempo.bpm,
        "key_signature": {
            "root": score.key_signature.root,
            "mode": score.key_signature.mode,
        },
        "time_signature": {
            "beats_per_measure": score.time_signature.beats_per_measure,
            "beat_unit": score.time_signature.beat_unit,
        },
        "parts": [
            {
                "instrument": part.instrument.name,
                "measures": [
                    {
                        "time_signature": {
                            "beats_per_measure": measure.time_signature.beats_per_measure,
                            "beat_unit": measure.time_signature.beat_unit,
                        },
                        "events": [_event_to_dict(event) for event in measure.events],
                    }
                    for measure in part.measures
                ],
            }
            for part in score.parts
        ],
    }


def score_from_dict(data: dict[str, Any]) -> Score:
    """Deserialize a Score from project JSON data."""
    ts_data = data["time_signature"]
    ts = TimeSignature(
        int(ts_data["beats_per_measure"]),
        int(ts_data["beat_unit"]),
    )
    ks_data = data["key_signature"]
    score = Score(
        title=str(data.get("title", "Untitled")),
        composer=str(data.get("composer", "")),
        tempo=Tempo(float(data.get("tempo", 120))),
        key_signature=KeySignature(str(ks_data["root"]), str(ks_data["mode"])),
        time_signature=ts,
    )

    for part_data in data.get("parts", []):
        part = Part(
            instrument=Instrument.by_name(str(part_data["instrument"])),
            default_ts=ts,
        )
        for measure_data in part_data.get("measures", []):
            mts_data = measure_data.get("time_signature", ts_data)
            measure = Measure(
                time_signature=TimeSignature(
                    int(mts_data["beats_per_measure"]),
                    int(mts_data["beat_unit"]),
                )
            )
            for event_data in measure_data.get("events", []):
                measure.add(_event_from_dict(event_data), strict=False)
            part.add_measure(measure)
        score.add_part(part)

    return score


def save_score_project(score: Score, path: str | Path) -> Path:
    """Save a Score to a .mariachi.json project file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(score_to_dict(score), indent=2), encoding="utf-8")
    return path


def load_score_project(path: str | Path) -> Score:
    """Load a Score from a .mariachi.json project file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return score_from_dict(data)


def _event_to_dict(event: Note | Rest) -> dict[str, Any]:
    if isinstance(event, Rest):
        return {
            "type": "rest",
            "duration": str(event.duration),
        }

    return {
        "type": "note",
        "pitch": event.pitch.full_name,
        "duration": str(event.duration),
        "velocity": event.velocity,
        "chord": event.chord,
        "tie_start": event.tie_start,
        "tie_end": event.tie_end,
        "lyrics": event.lyrics,
    }


def _event_from_dict(data: dict[str, Any]) -> Note | Rest:
    duration = Duration.parse(str(data["duration"]))
    if data["type"] == "rest":
        return Rest(duration=duration)

    return Note(
        pitch=Pitch.parse(str(data["pitch"])),
        duration=duration,
        velocity=int(data.get("velocity", 90)),
        chord=bool(data.get("chord", False)),
        tie_start=bool(data.get("tie_start", False)),
        tie_end=bool(data.get("tie_end", False)),
        lyrics=str(data.get("lyrics", "")),
    )
