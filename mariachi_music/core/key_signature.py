"""Key signature: root note + mode, sharps/flats count."""

from __future__ import annotations

from dataclasses import dataclass


# Number of sharps (positive) or flats (negative) for each major key
_MAJOR_FIFTHS: dict[str, int] = {
    "Cb": -7, "Gb": -6, "Db": -5, "Ab": -4, "Eb": -3, "Bb": -2, "F": -1,
    "C": 0,
    "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
}

# Natural minor relative key → same fifths as its relative major
_MINOR_ROOTS: dict[str, str] = {
    "A": "C", "E": "G", "B": "D", "F#": "A", "C#": "E", "G#": "B", "D#": "F#",
    "D": "Bb", "G": "Eb", "C": "Ab", "F": "Db", "Bb": "Gb", "Eb": "Cb",
}

_VALID_MODES = {"major", "minor", "dorian", "phrygian", "lydian", "mixolydian", "aeolian", "locrian"}


@dataclass(frozen=True)
class KeySignature:
    """Key signature (root + mode).

    Attributes:
        root: The tonic pitch name (e.g. 'C', 'G', 'Bb', 'F#').
        mode: 'major', 'minor', or one of the other modes.
    """

    root: str
    mode: str = "major"

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", self.mode.lower().strip())
        if self.mode not in _VALID_MODES:
            raise ValueError(f"Unknown mode: {self.mode!r}. Valid modes: {sorted(_VALID_MODES)}.")

    @classmethod
    def parse(cls, text: str, mode: str = "major") -> "KeySignature":
        """Parse 'C major', 'G', 'Bb minor', etc."""
        parts = text.strip().split()
        if len(parts) == 2:
            root, mode = parts[0], parts[1]
        elif len(parts) == 1:
            root = parts[0]
        else:
            raise ValueError(f"Cannot parse key signature: {text!r}.")
        return cls(root=root, mode=mode)

    @property
    def fifths(self) -> int:
        """MusicXML <fifths> value: positive = sharps, negative = flats."""
        if self.mode == "major":
            if self.root not in _MAJOR_FIFTHS:
                raise ValueError(f"Unknown major key root: {self.root!r}.")
            return _MAJOR_FIFTHS[self.root]
        if self.mode in ("minor", "aeolian"):
            rel = _MINOR_ROOTS.get(self.root)
            if rel is None:
                raise ValueError(f"Unknown minor key root: {self.root!r}.")
            return _MAJOR_FIFTHS[rel]
        # For other modes return 0 (C major enharmonic) as a safe default
        return 0

    @property
    def xml_mode(self) -> str:
        """MusicXML <mode> string."""
        return "minor" if self.mode in ("minor", "aeolian") else "major"

    def __str__(self) -> str:
        return f"{self.root} {self.mode}"


# Presets
C_MAJOR = KeySignature("C", "major")
G_MAJOR = KeySignature("G", "major")
D_MAJOR = KeySignature("D", "major")
F_MAJOR = KeySignature("F", "major")
Bb_MAJOR = KeySignature("Bb", "major")
Eb_MAJOR = KeySignature("Eb", "major")
A_MINOR = KeySignature("A", "minor")
E_MINOR = KeySignature("E", "minor")
D_MINOR = KeySignature("D", "minor")
