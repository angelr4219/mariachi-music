"""Music theory: scales, intervals, keys, chords."""

from .intervals import Interval, SEMITONE_MAP
from .keys import Key
from .scales import Scale, ScaleMode
from .chords import Chord, ChordQuality, chord_by_root, chord_by_degree, chords_in_key

__all__ = [
    "Interval", "SEMITONE_MAP",
    "Key",
    "Scale", "ScaleMode",
    "Chord", "ChordQuality", "chord_by_root", "chord_by_degree", "chords_in_key",
]
