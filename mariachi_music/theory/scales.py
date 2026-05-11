"""Scale definitions and pitch-list generation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .keys import Key
from mariachi_music.core.pitch import Pitch


class ScaleMode(str, Enum):
    MAJOR = "major"
    MINOR = "minor"
    DORIAN = "dorian"
    PHRYGIAN = "phrygian"
    LYDIAN = "lydian"
    MIXOLYDIAN = "mixolydian"
    LOCRIAN = "locrian"
    CHROMATIC = "chromatic"


@dataclass(frozen=True)
class Scale:
    """A musical scale: key + mode + starting octave.

    Attributes:
        root:    Tonic note letter (e.g. 'C', 'G', 'Bb').
        mode:    ScaleMode (major, minor, chromatic, etc.).
        octave:  Octave number for the first note.
    """

    root: str
    mode: ScaleMode = ScaleMode.MAJOR
    octave: int = 4

    @classmethod
    def parse(cls, root: str, mode: str = "major", octave: int = 4) -> "Scale":
        m = ScaleMode(mode.lower())
        return cls(root=root, mode=m, octave=octave)

    def pitches(self, ascending: bool = True) -> list[Pitch]:
        """Return the Pitch objects for this scale (one octave + the octave note).

        Args:
            ascending: If True, return ascending scale; if False, descending.
        """
        key = Key(self.root, self.mode.value)
        note_names = key.scale_notes()   # e.g. ['C', 'D', 'E', 'F', 'G', 'A', 'B']

        pitches: list[Pitch] = []
        current_octave = self.octave

        for i, name in enumerate(note_names):
            # Parse name which may include accidental (e.g. 'F#', 'Bb')
            if len(name) == 1:
                p = Pitch(name=name, accidental="", octave=current_octave)
            else:
                p = Pitch(name=name[0], accidental=name[1:], octave=current_octave)
            pitches.append(p)

            # Advance octave when we cross from B to C (or any note wraps below previous)
            if i < len(note_names) - 1:
                next_name = note_names[i + 1]
                next_letter = next_name[0]
                if _letter_index(next_letter) <= _letter_index(name[0]):
                    current_octave += 1

        # Append the octave-higher tonic to complete the scale.
        # The tonic always wraps above the last note, so bump the octave if the
        # last note's letter is >= the tonic letter (e.g. B → C crosses an octave).
        tonic_name = note_names[0]
        last_letter = note_names[-1][0]
        tonic_letter = tonic_name[0]
        if _letter_index(last_letter) >= _letter_index(tonic_letter):
            current_octave += 1
        if len(tonic_name) == 1:
            pitches.append(Pitch(name=tonic_name, accidental="", octave=current_octave))
        else:
            pitches.append(Pitch(name=tonic_name[0], accidental=tonic_name[1:], octave=current_octave))

        if not ascending:
            pitches = list(reversed(pitches))
        return pitches

    def pitch_strings(self, ascending: bool = True) -> list[str]:
        """Return scale pitches as strings like ['C4', 'D4', ..., 'C5']."""
        return [str(p) for p in self.pitches(ascending=ascending)]

    def __str__(self) -> str:
        return f"{self.root} {self.mode.value} (octave {self.octave})"


_LETTER_ORDER = ["C", "D", "E", "F", "G", "A", "B"]


def _letter_index(letter: str) -> int:
    try:
        return _LETTER_ORDER.index(letter.upper())
    except ValueError:
        return 0
