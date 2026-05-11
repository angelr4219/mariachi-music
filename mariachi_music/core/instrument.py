"""Instrument definitions: name, clef, MIDI program, range."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    """A musical instrument with notation and MIDI properties.

    Attributes:
        name:           Display name (e.g. 'Violin').
        clef:           'treble', 'bass', 'alto', 'tenor'.
        midi_program:   General MIDI program number (0-indexed).
        midi_min:       Lowest practical MIDI note.
        midi_max:       Highest practical MIDI note.
        transposition:  Semitones to add when written pitch → concert pitch
                        (0 for C instruments, -2 for Bb trumpet, etc.).
        abbreviation:   Short name for score display (e.g. 'Vln.').
    """

    name: str
    clef: str = "treble"
    midi_program: int = 0          # Acoustic Grand Piano default
    midi_min: int = 21             # A0
    midi_max: int = 108            # C8
    transposition: int = 0
    abbreviation: str = ""

    def __post_init__(self) -> None:
        valid_clefs = {"treble", "bass", "alto", "tenor", "percussion"}
        if self.clef not in valid_clefs:
            raise ValueError(f"Invalid clef {self.clef!r}. Valid: {sorted(valid_clefs)}.")
        if not (0 <= self.midi_program <= 127):
            raise ValueError(f"MIDI program must be 0–127, got {self.midi_program}.")

    @classmethod
    def by_name(cls, name: str) -> "Instrument":
        """Look up a preset instrument by name (case-insensitive)."""
        key = name.strip().lower()
        for preset_name, inst in INSTRUMENTS.items():
            if preset_name.lower() == key:
                return inst
        raise ValueError(
            f"Unknown instrument: {name!r}. "
            f"Available: {sorted(INSTRUMENTS.keys())}."
        )

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"Instrument({self.name!r})"


# Preset instrument library
INSTRUMENTS: dict[str, Instrument] = {
    "Violin": Instrument(
        name="Violin", clef="treble", midi_program=40,
        midi_min=55, midi_max=103, abbreviation="Vln.",
    ),
    "Trumpet": Instrument(
        name="Trumpet", clef="treble", midi_program=56,
        midi_min=54, midi_max=94, transposition=-2, abbreviation="Tpt.",
    ),
    "Guitarrón": Instrument(
        name="Guitarrón", clef="bass", midi_program=32,
        midi_min=28, midi_max=64, abbreviation="Gtn.",
    ),
    "Vihuela": Instrument(
        name="Vihuela", clef="treble", midi_program=25,
        midi_min=40, midi_max=88, abbreviation="Vih.",
    ),
    "Guitar": Instrument(
        name="Guitar", clef="treble", midi_program=24,
        midi_min=40, midi_max=88, abbreviation="Gtr.",
    ),
    "Voice": Instrument(
        name="Voice", clef="treble", midi_program=52,
        midi_min=48, midi_max=84, abbreviation="Vox",
    ),
    "Harp": Instrument(
        name="Harp", clef="treble", midi_program=46,
        midi_min=23, midi_max=103, abbreviation="Hrp.",
    ),
    "Piano": Instrument(
        name="Piano", clef="treble", midi_program=0,
        midi_min=21, midi_max=108, abbreviation="Pno.",
    ),
    "Generic Treble": Instrument(
        name="Generic Treble", clef="treble", midi_program=0,
        midi_min=48, midi_max=96, abbreviation="Tr.",
    ),
    "Generic Bass": Instrument(
        name="Generic Bass", clef="bass", midi_program=32,
        midi_min=28, midi_max=64, abbreviation="Bs.",
    ),
}
