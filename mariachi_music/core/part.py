"""Part: one instrument's complete music (an ordered list of Measures)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from .instrument import Instrument, INSTRUMENTS
from .measure import Measure
from .note import Note, Rest, NoteOrRest
from .time_signature import TimeSignature
from .duration import Duration


@dataclass
class Part:
    """One instrument part in a Score.

    Attributes:
        instrument:      The instrument this part is written for.
        measures:        Ordered list of Measure objects.
        default_ts:      Default time signature for new measures.
    """

    instrument: Instrument
    default_ts: TimeSignature = field(default_factory=lambda: TimeSignature(4, 4))
    _measures: list[Measure] = field(default_factory=list, repr=False)

    # ------------------------------------------------------------------
    # Measure management
    # ------------------------------------------------------------------

    def new_measure(self, time_signature: TimeSignature | None = None) -> Measure:
        """Append a new empty measure and return it."""
        ts = time_signature or self.default_ts
        m = Measure(time_signature=ts, number=len(self._measures) + 1)
        self._measures.append(m)
        return m

    def add_measure(self, measure: Measure) -> None:
        """Append an already-constructed Measure."""
        measure.number = len(self._measures) + 1
        self._measures.append(measure)

    # ------------------------------------------------------------------
    # High-level note helpers
    # ------------------------------------------------------------------

    def add_notes(
        self,
        pitches: list[str],
        duration: str = "quarter",
        velocity: int = 90,
        time_signature: TimeSignature | None = None,
    ) -> None:
        """Add a flat list of pitch strings as notes, auto-filling measures.

        Notes that would overflow the current measure are pushed to a new one.
        """
        dur = Duration.parse(duration)
        ts = time_signature or self.default_ts

        for pitch_str in pitches:
            note = Note.from_str(pitch_str, duration, velocity)
            if not self._measures or self._measures[-1].is_full:
                self.new_measure(ts)
            current = self._measures[-1]
            if note.beats > current.remaining_beats + 1e-9:
                self.new_measure(ts)
                current = self._measures[-1]
            current.add(note, strict=False)

    def add_note(
        self,
        pitch_str: str,
        duration_str: str = "quarter",
        velocity: int = 90,
    ) -> None:
        """Add a single note, opening a new measure if needed."""
        note = Note.from_str(pitch_str, duration_str, velocity)
        if not self._measures or self._measures[-1].is_full:
            self.new_measure()
        current = self._measures[-1]
        if note.beats > current.remaining_beats + 1e-9:
            self.new_measure()
            current = self._measures[-1]
        current.add(note, strict=False)

    def add_chord(
        self,
        pitch_strings: list[str],
        duration_str: str = "quarter",
        velocity: int = 90,
    ) -> None:
        """Add simultaneous notes as one rhythmic chord event.

        The first note consumes rhythmic time. Remaining notes are marked as
        chord tones and start at the same beat as the first note.
        """
        if not pitch_strings:
            raise ValueError("Chord must contain at least one pitch.")

        notes = [
            Note.from_str(pitch_str, duration_str, velocity)
            for pitch_str in pitch_strings
        ]
        for note in notes[1:]:
            note.chord = True

        if not self._measures or self._measures[-1].is_full:
            self.new_measure()
        current = self._measures[-1]
        if notes[0].beats > current.remaining_beats + 1e-9:
            self.new_measure()
            current = self._measures[-1]
        for note in notes:
            current.add(note, strict=False)

    def add_rest(self, duration_str: str = "quarter") -> None:
        rest = Rest.from_str(duration_str)
        if not self._measures or self._measures[-1].is_full:
            self.new_measure()
        current = self._measures[-1]
        if rest.beats > current.remaining_beats + 1e-9:
            self.new_measure()
            current = self._measures[-1]
        current.add(rest, strict=False)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    @property
    def measures(self) -> list[Measure]:
        return list(self._measures)

    @property
    def all_events(self) -> list[NoteOrRest]:
        events: list[NoteOrRest] = []
        for m in self._measures:
            events.extend(m.events)
        return events

    @property
    def all_notes(self) -> list[Note]:
        return [e for e in self.all_events if isinstance(e, Note)]

    def __iter__(self) -> Iterator[Measure]:
        return iter(self._measures)

    def __len__(self) -> int:
        return len(self._measures)

    def __repr__(self) -> str:
        return f"Part(instrument={self.instrument!r}, measures={len(self._measures)})"
