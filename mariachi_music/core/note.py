"""Note and Rest — the atomic elements of a score."""

from __future__ import annotations

from dataclasses import dataclass, field

from .pitch import Pitch
from .duration import Duration, DurationValue


@dataclass
class Note:
    """A sounding note with pitch, duration, and performance attributes.

    Attributes:
        pitch:      The sounding pitch (e.g. Pitch("C", "", 4) for C4).
        duration:   How long the note lasts.
        velocity:   MIDI velocity 0–127 (default 90).
        chord:      True when this note starts at the same time as the previous
                    note in the measure.
        tie_start:  True if this note is tied into the next note.
        tie_end:    True if this note is tied from the previous note.
        lyrics:     Optional lyric syllable for vocal parts.
    """

    pitch: Pitch
    duration: Duration
    velocity: int = 90
    chord: bool = False
    tie_start: bool = False
    tie_end: bool = False
    lyrics: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.pitch, Pitch):
            raise TypeError(f"pitch must be a Pitch instance, got {type(self.pitch).__name__}.")
        if not isinstance(self.duration, Duration):
            raise TypeError(f"duration must be a Duration instance, got {type(self.duration).__name__}.")
        if not (0 <= self.velocity <= 127):
            raise ValueError(f"velocity must be 0–127, got {self.velocity}.")

    @classmethod
    def from_str(cls, pitch_str: str, duration_str: str, velocity: int = 90) -> "Note":
        """Convenience constructor: Note.from_str('C4', 'quarter')."""
        return cls(
            pitch=Pitch.parse(pitch_str),
            duration=Duration.parse(duration_str),
            velocity=velocity,
        )

    @property
    def beats(self) -> float:
        return self.duration.beats

    @property
    def midi_number(self) -> int:
        return self.pitch.midi_number

    def __str__(self) -> str:
        return f"{self.pitch} ({self.duration})"

    def __repr__(self) -> str:
        return f"Note(pitch={self.pitch!r}, duration={self.duration!r})"


@dataclass
class Rest:
    """A silent rest with a duration.

    Attributes:
        duration: How long the rest lasts.
    """

    duration: Duration

    def __post_init__(self) -> None:
        if not isinstance(self.duration, Duration):
            raise TypeError(f"duration must be a Duration instance, got {type(self.duration).__name__}.")

    @classmethod
    def from_str(cls, duration_str: str) -> "Rest":
        return cls(duration=Duration.parse(duration_str))

    @property
    def beats(self) -> float:
        return self.duration.beats

    def __str__(self) -> str:
        return f"Rest ({self.duration})"

    def __repr__(self) -> str:
        return f"Rest(duration={self.duration!r})"


# Type alias used throughout the project
NoteOrRest = Note | Rest
