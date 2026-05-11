"""Pitch representation: note name + octave + accidental."""

from __future__ import annotations

import re
from dataclasses import dataclass

PITCH_NAMES = ["C", "D", "E", "F", "G", "A", "B"]

# Semitone offsets from C within an octave
_SEMITONE: dict[str, int] = {
    "C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11,
}

ENHARMONIC_MAP: dict[str, str] = {
    "C#": "Db", "D#": "Eb", "F#": "Gb", "G#": "Ab", "A#": "Bb",
    "Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#",
}

_VALID_ACCIDENTALS = {"", "#", "b", "##", "bb", "n"}

_PITCH_RE = re.compile(r"^([A-Ga-g])(#{1,2}|b{1,2}|n)?(-?\d+)$")


@dataclass(frozen=True)
class Pitch:
    """A specific pitch: letter name, optional accidental, and octave number.

    Examples: Pitch("C", "", 4) → C4, Pitch("F", "#", 5) → F#5.
    Convenience: Pitch.parse("C#4") or Pitch.parse("Bb3").
    """

    name: str       # A–G, uppercase
    accidental: str # "", "#", "b", "##", "bb", "n"
    octave: int     # scientific pitch notation: middle C = C4

    def __post_init__(self) -> None:
        if self.name.upper() not in PITCH_NAMES:
            raise ValueError(f"Invalid pitch name: {self.name!r}. Must be one of {PITCH_NAMES}.")
        if self.accidental not in _VALID_ACCIDENTALS:
            raise ValueError(f"Invalid accidental: {self.accidental!r}.")
        object.__setattr__(self, "name", self.name.upper())

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def parse(cls, text: str) -> "Pitch":
        """Parse a string like 'C4', 'F#5', 'Bb3', 'D##2'."""
        m = _PITCH_RE.match(text.strip())
        if not m:
            raise ValueError(
                f"Cannot parse pitch {text!r}. "
                "Expected format: letter + optional accidental + octave, e.g. 'C4', 'F#5', 'Bb3'."
            )
        name, acc, octave = m.group(1).upper(), m.group(2) or "", int(m.group(3))
        return cls(name=name, accidental=acc, octave=octave)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def full_name(self) -> str:
        return f"{self.name}{self.accidental}{self.octave}"

    @property
    def step(self) -> str:
        """Letter name only, uppercase."""
        return self.name

    @property
    def midi_number(self) -> int:
        """MIDI note number (C4 = 60)."""
        semi = _SEMITONE[self.name]
        if self.accidental == "#":
            semi += 1
        elif self.accidental == "b":
            semi -= 1
        elif self.accidental == "##":
            semi += 2
        elif self.accidental == "bb":
            semi -= 2
        # 'n' (natural) is no change
        return (self.octave + 1) * 12 + semi

    @property
    def enharmonic(self) -> "Pitch | None":
        """Return the enharmonic equivalent pitch, or None if none exists."""
        key = f"{self.name}{self.accidental}"
        equiv = ENHARMONIC_MAP.get(key)
        if equiv is None:
            return None
        return Pitch.parse(f"{equiv}{self.octave}")

    # ------------------------------------------------------------------
    # Arithmetic
    # ------------------------------------------------------------------

    def transpose_semitones(self, semitones: int) -> "Pitch":
        """Return a new Pitch shifted by the given number of semitones."""
        return Pitch.from_midi(self.midi_number + semitones)

    @classmethod
    def from_midi(cls, midi: int) -> "Pitch":
        """Convert a MIDI number to a Pitch using sharps for black keys."""
        _MIDI_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = midi // 12 - 1
        name_acc = _MIDI_NAMES[midi % 12]
        if len(name_acc) == 1:
            return cls(name=name_acc, accidental="", octave=octave)
        return cls(name=name_acc[0], accidental=name_acc[1], octave=octave)

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        return self.full_name

    def __lt__(self, other: "Pitch") -> bool:
        return self.midi_number < other.midi_number

    def __le__(self, other: "Pitch") -> bool:
        return self.midi_number <= other.midi_number
