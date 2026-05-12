"""Score generation tools: scales, exercises, melodies."""

from .scale_generator import generate_scale_score
from .chord_generator import generate_chord_score, generate_key_chord_progression

__all__ = ["generate_scale_score", "generate_chord_score", "generate_key_chord_progression"]
