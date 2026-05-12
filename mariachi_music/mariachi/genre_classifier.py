"""First-pass mariachi genre recognition from audio features."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class GenreGuess:
    """Result from the heuristic genre classifier."""

    genre: str
    confidence: float
    tempo_bpm: float
    meter_hint: str
    reasoning: tuple[str, ...]


def classify_audio_genre(path: str | Path, sample_rate: int = 22050, duration: float | None = 90.0) -> GenreGuess:
    """Classify likely mariachi genre from an audio file.

    This is a v0 heuristic, not a trained classifier. It estimates tempo and a
    coarse compound-vs-simple meter hint, then maps those features to son,
    bolero, or ranchera.
    """
    import librosa

    y, sr = librosa.load(str(path), sr=sample_rate, mono=True, duration=duration)
    if y.size == 0:
        raise ValueError(f"Audio file is empty or unreadable: {path}")

    onset = librosa.onset.onset_strength(y=y, sr=sr)
    tempo_raw, beats = librosa.beat.beat_track(onset_envelope=onset, sr=sr)
    tempo = float(np.atleast_1d(tempo_raw)[0])

    meter_hint = _estimate_meter_hint(onset, beats)
    return classify_features(tempo_bpm=tempo, meter_hint=meter_hint)


def classify_features(tempo_bpm: float, meter_hint: str = "unknown") -> GenreGuess:
    """Classify genre from precomputed features.

    Useful for tests and for future transcription modules that already computed
    tempo/meter.
    """
    tempo = float(tempo_bpm)
    meter = meter_hint.strip().lower()
    reasoning: list[str] = []

    scores = {"son": 0.0, "bolero": 0.0, "ranchera": 0.0}

    if tempo <= 92:
        scores["bolero"] += 0.55
        reasoning.append("slow tempo favors bolero")
    elif tempo >= 118:
        scores["son"] += 0.35
        scores["ranchera"] += 0.25
        reasoning.append("medium-fast tempo favors son or ranchera")
    else:
        scores["ranchera"] += 0.35
        reasoning.append("middle tempo favors ranchera")

    if meter in {"6/8", "compound", "compound_duple"}:
        scores["son"] += 0.55
        reasoning.append("compound meter favors son")
    elif meter in {"3/4", "waltz"}:
        scores["ranchera"] += 0.55
        reasoning.append("3/4 meter favors ranchera")
    elif meter in {"4/4", "simple_quadruple"}:
        scores["bolero"] += 0.4
        reasoning.append("4/4 meter favors bolero")
    elif meter in {"2/4", "polka"}:
        scores["ranchera"] += 0.45
        reasoning.append("2/4/polka meter favors polca ranchera")
    else:
        reasoning.append("meter unknown, using tempo-heavy estimate")

    genre = max(scores, key=scores.get)
    total = sum(scores.values()) or 1.0
    confidence = max(0.05, min(0.95, scores[genre] / total))
    return GenreGuess(
        genre=genre,
        confidence=round(confidence, 3),
        tempo_bpm=round(tempo, 3),
        meter_hint=meter or "unknown",
        reasoning=tuple(reasoning),
    )


def _estimate_meter_hint(onset: np.ndarray, beats: np.ndarray) -> str:
    """Very coarse meter hint from beat spacing and onset accent pattern."""
    if beats.size < 8:
        return "unknown"

    beat_strength = onset[np.clip(beats.astype(int), 0, len(onset) - 1)]
    if beat_strength.size < 8:
        return "unknown"

    def periodic_score(period: int) -> float:
        buckets = [beat_strength[i::period].mean() for i in range(period)]
        return float(max(buckets) - np.mean(buckets))

    score_2 = periodic_score(2)
    score_3 = periodic_score(3)
    score_4 = periodic_score(4)
    score_6 = periodic_score(6)

    best = max({2: score_2, 3: score_3, 4: score_4, 6: score_6}, key=lambda k: {2: score_2, 3: score_3, 4: score_4, 6: score_6}[k])
    if best == 6 or (score_2 > 0 and score_3 > 0 and abs(score_2 - score_3) < max(score_2, score_3) * 0.35):
        return "6/8"
    if best == 3:
        return "3/4"
    if best == 2:
        return "2/4"
    if best == 4:
        return "4/4"
    return "unknown"
