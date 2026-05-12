"""Score generation tools: scales, exercises, melodies, and rhythm patterns."""

from .scale_generator import generate_scale_score
from .chord_generator import generate_chord_score, generate_key_chord_progression
from .rhythm_engine import (
    RhythmPattern,
    generate_rhythm_score,
    generate_song_structure,
)

__all__ = [
    "generate_scale_score",
    "generate_chord_score",
    "generate_key_chord_progression",
    "RhythmPattern",
    "generate_rhythm_score",
    "generate_song_structure",
]
