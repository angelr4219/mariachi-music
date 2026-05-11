"""Key definitions: which accidentals belong to each key."""

from __future__ import annotations


# Pitches (letter + accidental) that belong to each major key
# Stored in scale order starting from the tonic.
_MAJOR_SCALE_NOTES: dict[str, list[str]] = {
    "C":  ["C", "D", "E", "F", "G", "A", "B"],
    "G":  ["G", "A", "B", "C", "D", "E", "F#"],
    "D":  ["D", "E", "F#", "G", "A", "B", "C#"],
    "A":  ["A", "B", "C#", "D", "E", "F#", "G#"],
    "E":  ["E", "F#", "G#", "A", "B", "C#", "D#"],
    "B":  ["B", "C#", "D#", "E", "F#", "G#", "A#"],
    "F#": ["F#", "G#", "A#", "B", "C#", "D#", "E#"],
    "C#": ["C#", "D#", "E#", "F#", "G#", "A#", "B#"],
    "F":  ["F", "G", "A", "Bb", "C", "D", "E"],
    "Bb": ["Bb", "C", "D", "Eb", "F", "G", "A"],
    "Eb": ["Eb", "F", "G", "Ab", "Bb", "C", "D"],
    "Ab": ["Ab", "Bb", "C", "Db", "Eb", "F", "G"],
    "Db": ["Db", "Eb", "F", "Gb", "Ab", "Bb", "C"],
    "Gb": ["Gb", "Ab", "Bb", "Cb", "Db", "Eb", "F"],
    "Cb": ["Cb", "Db", "Eb", "Fb", "Gb", "Ab", "Bb"],
}

# Natural minor: built from the 6th degree of the relative major
_MINOR_RELATIVE_MAJOR: dict[str, str] = {
    "A": "C", "E": "G", "B": "D",
    "F#": "A", "C#": "E", "G#": "B", "D#": "F#",
    "D": "F", "G": "Bb", "C": "Eb",
    "F": "Ab", "Bb": "Db", "Eb": "Gb",
}

# Semitone intervals that define each mode relative to major
_MODE_INTERVALS: dict[str, list[int]] = {
    "major":      [0, 2, 4, 5, 7, 9, 11],
    "minor":      [0, 2, 3, 5, 7, 8, 10],
    "dorian":     [0, 2, 3, 5, 7, 9, 10],
    "phrygian":   [0, 1, 3, 5, 7, 8, 10],
    "lydian":     [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "locrian":    [0, 1, 3, 5, 6, 8, 10],
    "chromatic":  [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
}


class Key:
    """Music key: provides the scale degree pitches for a root + mode."""

    def __init__(self, root: str, mode: str = "major") -> None:
        self.root = root
        self.mode = mode.lower()
        if self.mode not in _MODE_INTERVALS and self.mode != "natural_minor":
            raise ValueError(f"Unknown mode: {mode!r}.")

    def scale_notes(self) -> list[str]:
        """Return the 7 (or 12 for chromatic) note names in this key's scale."""
        if self.mode == "major" and self.root in _MAJOR_SCALE_NOTES:
            return list(_MAJOR_SCALE_NOTES[self.root])
        if self.mode in ("minor", "natural_minor", "aeolian"):
            rel = _MINOR_RELATIVE_MAJOR.get(self.root)
            if rel and rel in _MAJOR_SCALE_NOTES:
                notes = _MAJOR_SCALE_NOTES[rel]
                # Natural minor starts on the 6th degree (index 5)
                return notes[5:] + notes[:5]
        # Generic: build from semitone intervals using sharps
        _CHROMATIC = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        try:
            root_idx = _CHROMATIC.index(self.root)
        except ValueError:
            raise ValueError(f"Cannot resolve root note: {self.root!r}.")
        intervals = _MODE_INTERVALS.get(self.mode, _MODE_INTERVALS["major"])
        return [_CHROMATIC[(root_idx + i) % 12] for i in intervals]

    def __repr__(self) -> str:
        return f"Key({self.root!r}, {self.mode!r})"
