"""Score: the root container for a complete piece of music."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .instrument import Instrument
from .key_signature import KeySignature, C_MAJOR
from .part import Part
from .tempo import Tempo
from .time_signature import TimeSignature, FOUR_FOUR

if TYPE_CHECKING:
    pass


@dataclass
class Score:
    """A complete musical score.

    Attributes:
        title:          Score title.
        composer:       Composer name.
        tempo:          Global BPM / tempo marking.
        key_signature:  Global key signature (can be overridden per measure later).
        time_signature: Global time signature (can be overridden per measure later).
        parts:          Ordered list of instrument parts.
    """

    title: str = "Untitled"
    composer: str = ""
    tempo: Tempo = field(default_factory=lambda: Tempo(120))
    key_signature: KeySignature = field(default_factory=lambda: C_MAJOR)
    time_signature: TimeSignature = field(default_factory=lambda: FOUR_FOUR)
    _parts: list[Part] = field(default_factory=list, repr=False)

    # ------------------------------------------------------------------
    # Part management
    # ------------------------------------------------------------------

    def add_part(self, part: Part) -> Part:
        """Append an instrument part and return it."""
        self._parts.append(part)
        return part

    def new_part(self, instrument: Instrument | str) -> Part:
        """Create, register, and return a new Part for the given instrument."""
        if isinstance(instrument, str):
            instrument = Instrument.by_name(instrument)
        part = Part(instrument=instrument, default_ts=self.time_signature)
        self._parts.append(part)
        return part

    def remove_part(self, index: int) -> Part:
        """Remove and return a part by zero-based index."""
        if not 0 <= index < len(self._parts):
            raise IndexError(f"Part index out of range: {index}.")
        return self._parts.pop(index)

    @property
    def parts(self) -> list[Part]:
        return list(self._parts)

    @property
    def part_count(self) -> int:
        return len(self._parts)

    # ------------------------------------------------------------------
    # Export shortcuts
    # ------------------------------------------------------------------

    def export_musicxml(self, path: str | Path) -> Path:
        """Export this score as MusicXML."""
        from mariachi_music.export.musicxml_export import export_score_musicxml
        return export_score_musicxml(self, Path(path))

    def export_midi(self, path: str | Path) -> Path:
        """Export this score as a MIDI file."""
        from mariachi_music.export.midi_export import export_score_midi
        return export_score_midi(self, Path(path))

    def export_lilypond(self, path: str | Path) -> Path:
        """Export this score as a LilyPond .ly file."""
        from mariachi_music.export.lilypond_export import export_score_lilypond
        return export_score_lilypond(self, Path(path))

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a human-readable summary of the score contents."""
        lines = [
            f"Score: {self.title}",
            f"  Composer : {self.composer or '(none)'}",
            f"  Tempo    : {self.tempo}",
            f"  Key      : {self.key_signature}",
            f"  Time sig : {self.time_signature}",
            f"  Parts    : {len(self._parts)}",
        ]
        for i, part in enumerate(self._parts, 1):
            notes = part.all_notes
            lines.append(
                f"    {i}. {part.instrument.name} — {len(part.measures)} measures, {len(notes)} notes"
            )
        return "\n".join(lines)

    def note_table(self) -> list[dict]:
        """Return a flat list of dicts for tabular display in the GUI."""
        rows: list[dict] = []
        for part in self._parts:
            for measure in part.measures:
                beat_cursor = 0.0
                last_beat = beat_cursor
                for event in measure.events:
                    is_chord_tone = getattr(event, "chord", False)
                    display_beat = last_beat if is_chord_tone else beat_cursor
                    row = {
                        "measure": measure.number,
                        "beat": round(display_beat + 1, 3),
                        "instrument": part.instrument.name,
                        "type": "chord tone" if is_chord_tone else ("note" if hasattr(event, "pitch") else "rest"),
                        "pitch": str(event.pitch) if hasattr(event, "pitch") else "—",
                        "duration": str(event.duration),
                    }
                    rows.append(row)
                    if not is_chord_tone:
                        last_beat = beat_cursor
                        beat_cursor += event.beats
        return rows

    def __repr__(self) -> str:
        return (
            f"Score(title={self.title!r}, parts={len(self._parts)}, "
            f"tempo={self.tempo.bpm} bpm, key={self.key_signature})"
        )
