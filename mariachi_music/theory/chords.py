"""Chord definitions and diatonic chord lookup by key.

A Chord knows its root, quality, and the pitch names of its tones.
The module also provides helpers to get all chords in a key (I–VII).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mariachi_music.core.pitch import Pitch


class ChordQuality(str, Enum):
    MAJOR = "major"
    MINOR = "minor"
    DIMINISHED = "diminished"
    AUGMENTED = "augmented"
    DOMINANT7 = "dominant7"
    MAJOR7 = "major7"
    MINOR7 = "minor7"


# Semitone intervals from root for each chord quality
_QUALITY_INTERVALS: dict[ChordQuality, list[int]] = {
    ChordQuality.MAJOR:      [0, 4, 7],
    ChordQuality.MINOR:      [0, 3, 7],
    ChordQuality.DIMINISHED: [0, 3, 6],
    ChordQuality.AUGMENTED:  [0, 4, 8],
    ChordQuality.DOMINANT7:  [0, 4, 7, 10],
    ChordQuality.MAJOR7:     [0, 4, 7, 11],
    ChordQuality.MINOR7:     [0, 3, 7, 10],
}

# Diatonic chord qualities for major key scale degrees I–VII
_MAJOR_KEY_QUALITIES: list[ChordQuality] = [
    ChordQuality.MAJOR,       # I
    ChordQuality.MINOR,       # ii
    ChordQuality.MINOR,       # iii
    ChordQuality.MAJOR,       # IV
    ChordQuality.MAJOR,       # V
    ChordQuality.MINOR,       # vi
    ChordQuality.DIMINISHED,  # vii°
]

# Diatonic qualities for natural minor key degrees I–VII
_MINOR_KEY_QUALITIES: list[ChordQuality] = [
    ChordQuality.MINOR,       # i
    ChordQuality.DIMINISHED,  # ii°
    ChordQuality.MAJOR,       # III
    ChordQuality.MINOR,       # iv
    ChordQuality.MINOR,       # v  (natural minor)
    ChordQuality.MAJOR,       # VI
    ChordQuality.MAJOR,       # VII
]

# Roman numeral labels for display
_ROMAN_MAJOR = ["I", "ii", "iii", "IV", "V", "vi", "vii°"]
_ROMAN_MINOR = ["i", "ii°", "III", "iv", "v", "VI", "VII"]


@dataclass(frozen=True)
class Chord:
    """A chord: root pitch name + quality + the actual pitch names of its tones.

    Attributes:
        root:    Root note name (e.g. 'G').
        quality: ChordQuality enum value.
        tones:   Tuple of pitch names, lowest to highest (e.g. ('G', 'B', 'D')).
    """

    root: str
    quality: ChordQuality
    tones: tuple[str, ...]

    @classmethod
    def build(cls, root: str, quality: ChordQuality) -> "Chord":
        """Build a Chord from a root name and quality."""
        root_pitch = Pitch.from_midi(_root_midi(root))
        intervals = _QUALITY_INTERVALS[quality]
        tones: list[str] = []
        for semitones in intervals:
            p = root_pitch.transpose_semitones(semitones)
            tones.append(f"{p.name}{p.accidental}")
        return cls(root=root, quality=quality, tones=tuple(tones))

    @property
    def name(self) -> str:
        suffix = {
            ChordQuality.MAJOR: "",
            ChordQuality.MINOR: "m",
            ChordQuality.DIMINISHED: "dim",
            ChordQuality.AUGMENTED: "aug",
            ChordQuality.DOMINANT7: "7",
            ChordQuality.MAJOR7: "maj7",
            ChordQuality.MINOR7: "m7",
        }[self.quality]
        return f"{self.root}{suffix}"

    def pitches_at_octave(self, octave: int) -> list[Pitch]:
        """Return the chord tones as Pitch objects starting at the given octave.

        Notes that wrap below the root (within the octave) are bumped up.
        """
        pitches: list[Pitch] = []
        for tone in self.tones:
            if len(tone) == 1:
                p = Pitch(name=tone, accidental="", octave=octave)
            else:
                p = Pitch(name=tone[0], accidental=tone[1:], octave=octave)
            # Keep tones ascending within an octave span
            if pitches and p.midi_number < pitches[-1].midi_number:
                p = Pitch(name=p.name, accidental=p.accidental, octave=p.octave + 1)
            pitches.append(p)
        return pitches

    def __str__(self) -> str:
        return f"{self.name} ({', '.join(self.tones)})"


def _root_midi(root: str) -> int:
    """Return the MIDI number for a note name at octave 4."""
    _MAP = {
        "C": 60, "C#": 61, "Db": 61, "D": 62, "D#": 63, "Eb": 63,
        "E": 64, "F": 65, "F#": 66, "Gb": 66, "G": 67, "G#": 68,
        "Ab": 68, "A": 69, "A#": 70, "Bb": 70, "B": 71,
    }
    if root not in _MAP:
        raise ValueError(f"Unknown root note: {root!r}")
    return _MAP[root]


def chords_in_key(key_root: str, mode: str = "major") -> list[tuple[str, Chord]]:
    """Return all 7 diatonic chords for a key as (roman_numeral, Chord) pairs.

    Args:
        key_root: Root note of the key (e.g. 'C', 'G', 'Bb').
        mode:     'major' or 'minor'.

    Returns:
        List of 7 (roman_numeral, Chord) tuples, one per scale degree.

    Example::

        >>> chords_in_key('C', 'major')
        [('I', Chord C), ('ii', Chord Dm), ('iii', Chord Em), ...]
    """
    from mariachi_music.theory.keys import Key

    key = Key(key_root, mode)
    scale = key.scale_notes()  # 7 note names

    if mode == "major":
        qualities = _MAJOR_KEY_QUALITIES
        roman = _ROMAN_MAJOR
    else:
        qualities = _MINOR_KEY_QUALITIES
        roman = _ROMAN_MINOR

    result: list[tuple[str, Chord]] = []
    for i, (note, quality, rn) in enumerate(zip(scale, qualities, roman)):
        chord = Chord.build(note, quality)
        result.append((rn, chord))
    return result


def chord_by_degree(key_root: str, degree: int, mode: str = "major") -> Chord:
    """Return the diatonic chord at scale degree (1-indexed).

    Args:
        key_root: Key root (e.g. 'C').
        degree:   Scale degree 1–7 (1 = tonic).
        mode:     'major' or 'minor'.
    """
    if not 1 <= degree <= 7:
        raise ValueError(f"Scale degree must be 1–7, got {degree}.")
    pairs = chords_in_key(key_root, mode)
    return pairs[degree - 1][1]


def chord_by_root(root: str, quality: str = "major") -> Chord:
    """Build any chord directly by root and quality name.

    Args:
        root:    Root note name (e.g. 'G', 'Bb', 'F#').
        quality: Quality string: 'major', 'minor', 'diminished', 'dominant7', etc.
    """
    q = ChordQuality(quality.lower())
    return Chord.build(root, q)
