"""Tempo: beats per minute and related conversions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tempo:
    """Beats per minute (BPM).

    Attributes:
        bpm: Beats per minute, must be positive.
        text_mark: Optional Italian tempo marking (e.g. 'Allegro').
    """

    bpm: float
    text_mark: str = ""

    def __post_init__(self) -> None:
        if self.bpm <= 0:
            raise ValueError(f"BPM must be positive, got {self.bpm}.")

    @property
    def beat_duration_sec(self) -> float:
        """Duration of one quarter-note beat in seconds."""
        return 60.0 / self.bpm

    @property
    def microseconds_per_beat(self) -> int:
        """MIDI tempo value: microseconds per quarter note."""
        return int(60_000_000 / self.bpm)

    def duration_sec(self, beats: float) -> float:
        """Convert a beat count to seconds at this tempo."""
        return beats * self.beat_duration_sec

    def __str__(self) -> str:
        mark = f" ({self.text_mark})" if self.text_mark else ""
        return f"♩ = {self.bpm:.0f}{mark}"

    def __repr__(self) -> str:
        return f"Tempo(bpm={self.bpm})"
