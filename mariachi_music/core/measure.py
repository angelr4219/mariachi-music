"""Measure: an ordered list of notes/rests that fits a time signature."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from .note import Note, Rest, NoteOrRest
from .time_signature import TimeSignature


@dataclass
class Measure:
    """One measure of music.

    Attributes:
        time_signature: The meter governing this measure.
        number:         1-based measure number (set by Part when appended).
        _events:        Ordered notes and rests (do not set directly).
    """

    time_signature: TimeSignature
    number: int = 1
    _events: list[NoteOrRest] = field(default_factory=list, repr=False)

    # ------------------------------------------------------------------
    # Beat accounting
    # ------------------------------------------------------------------

    @property
    def capacity_beats(self) -> float:
        """Total quarter-note beats this measure can hold."""
        return self.time_signature.beats_per_measure_in_quarters

    @property
    def used_beats(self) -> float:
        return sum(e.beats for e in self._events)

    @property
    def remaining_beats(self) -> float:
        return self.capacity_beats - self.used_beats

    @property
    def is_full(self) -> bool:
        return abs(self.remaining_beats) < 1e-9

    @property
    def is_overfull(self) -> bool:
        return self.used_beats > self.capacity_beats + 1e-9

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, event: NoteOrRest, strict: bool = True) -> None:
        """Append a note or rest.

        Args:
            event:  Note or Rest to add.
            strict: If True, raise an error when the event would overflow the measure.
        """
        if not isinstance(event, (Note, Rest)):
            raise TypeError(f"Expected Note or Rest, got {type(event).__name__}.")
        if strict and event.beats > self.remaining_beats + 1e-9:
            raise OverflowError(
                f"Adding {event} ({event.beats:.3f} beats) would overflow measure {self.number} "
                f"({self.used_beats:.3f}/{self.capacity_beats:.3f} beats used)."
            )
        self._events.append(event)

    def add_note(self, pitch_str: str, duration_str: str, velocity: int = 90, strict: bool = True) -> None:
        """Convenience: Measure.add_note('C4', 'quarter')."""
        self.add(Note.from_str(pitch_str, duration_str, velocity), strict=strict)

    def add_rest(self, duration_str: str, strict: bool = True) -> None:
        """Convenience: Measure.add_rest('quarter')."""
        self.add(Rest.from_str(duration_str), strict=strict)

    def clear(self) -> None:
        self._events.clear()

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    @property
    def events(self) -> list[NoteOrRest]:
        return list(self._events)

    @property
    def notes(self) -> list[Note]:
        return [e for e in self._events if isinstance(e, Note)]

    @property
    def rests(self) -> list[Rest]:
        return [e for e in self._events if isinstance(e, Rest)]

    def __iter__(self) -> Iterator[NoteOrRest]:
        return iter(self._events)

    def __len__(self) -> int:
        return len(self._events)

    def __repr__(self) -> str:
        return (
            f"Measure(number={self.number}, "
            f"time_sig={self.time_signature}, "
            f"events={len(self._events)}, "
            f"beats={self.used_beats:.2f}/{self.capacity_beats:.2f})"
        )
