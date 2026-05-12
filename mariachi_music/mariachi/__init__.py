"""Mariachi-specific form, context, arrangement, and recognition helpers."""

from .arranger import ArrangementResult, MariachiSongRequest, generate_mariachi_arrangement
from .genre_classifier import GenreGuess, classify_audio_genre, classify_features
from .forms import GENRE_TEMPLATES, MariachiFormTemplate
from .contexts import CONTEXT_RULES, ContextRule

__all__ = [
    "ArrangementResult",
    "CONTEXT_RULES",
    "ContextRule",
    "GENRE_TEMPLATES",
    "GenreGuess",
    "MariachiFormTemplate",
    "MariachiSongRequest",
    "classify_audio_genre",
    "classify_features",
    "generate_mariachi_arrangement",
]
