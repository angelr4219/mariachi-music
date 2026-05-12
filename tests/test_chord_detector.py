"""Tests for audio chord detection."""

import numpy as np
import pytest

from mariachi_music.transcription.chord_detector import (
    CHORD_TEMPLATES,
    PITCH_CLASSES,
    _cosine_similarity,
    _match_chord,
    AudioAnalysis,
    ChordLabel,
)


# ── Template sanity ───────────────────────────────────────────────────────────

def test_templates_cover_all_roots():
    roots = set()
    for key in CHORD_TEMPLATES:
        roots.add(key.split()[0])
    assert roots == set(PITCH_CLASSES)

def test_c_major_template_correct():
    template = CHORD_TEMPLATES["C major"]
    # C=0, E=4, G=7
    assert template[0] == 1.0   # C
    assert template[4] == 1.0   # E
    assert template[7] == 1.0   # G
    assert np.sum(template) == 3.0

def test_g_major_template_correct():
    template = CHORD_TEMPLATES["G major"]
    # G=7, B=11, D=2
    assert template[7] == 1.0   # G
    assert template[11] == 1.0  # B
    assert template[2] == 1.0   # D

def test_a_minor_template_correct():
    template = CHORD_TEMPLATES["A minor"]
    # A=9, C=0, E=4
    assert template[9] == 1.0   # A
    assert template[0] == 1.0   # C
    assert template[4] == 1.0   # E


# ── Cosine similarity ─────────────────────────────────────────────────────────

def test_cosine_same_vector():
    v = np.array([1.0, 0, 0, 0, 1.0, 0, 0, 1.0, 0, 0, 0, 0])
    assert _cosine_similarity(v, v) == pytest.approx(1.0)

def test_cosine_orthogonal():
    a = np.array([1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    b = np.array([0.0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    assert _cosine_similarity(a, b) == pytest.approx(0.0)

def test_cosine_zero_vector():
    a = np.zeros(12)
    b = CHORD_TEMPLATES["C major"]
    assert _cosine_similarity(a, b) == 0.0


# ── Match chord ───────────────────────────────────────────────────────────────

def test_match_c_major_perfect():
    template = CHORD_TEMPLATES["C major"]
    chord_name, root, quality, confidence = _match_chord(template, CHORD_TEMPLATES)
    assert root == "C"
    assert quality == "major"
    assert confidence == pytest.approx(1.0)

def test_match_g_major_perfect():
    template = CHORD_TEMPLATES["G major"]
    chord_name, root, quality, confidence = _match_chord(template, CHORD_TEMPLATES)
    assert root == "G"
    assert quality == "major"
    assert confidence == pytest.approx(1.0)

def test_match_a_minor_perfect():
    template = CHORD_TEMPLATES["A minor"]
    chord_name, root, quality, confidence = _match_chord(template, CHORD_TEMPLATES)
    assert root == "A"
    assert quality == "minor"
    assert confidence == pytest.approx(1.0)

def test_match_confidence_between_0_and_1():
    # Slightly noisy chroma
    vec = CHORD_TEMPLATES["D major"] + np.random.default_rng(42).uniform(0, 0.1, 12)
    _, _, _, confidence = _match_chord(vec, CHORD_TEMPLATES)
    assert 0.0 <= confidence <= 1.0


# ── Synthetic audio analysis ──────────────────────────────────────────────────

def _make_chord_audio(root_midi: int, quality: str = "major",
                      sr: int = 22050, duration: float = 2.0) -> np.ndarray:
    """Synthesize a simple additive sine-wave chord for testing."""
    intervals = {"major": [0, 4, 7], "minor": [0, 3, 7]}[quality]
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = np.zeros_like(t)
    for semitone in intervals:
        freq = 440.0 * (2 ** ((root_midi + semitone - 69) / 12.0))
        audio += np.sin(2 * np.pi * freq * t) * 0.3
    return audio.astype(np.float32)


def test_analyze_synthetic_c_major(tmp_path):
    """A pure C major tone cluster should match C major."""
    import soundfile as sf
    from mariachi_music.transcription.chord_detector import analyze_audio

    audio = _make_chord_audio(60, "major", duration=4.0)  # C4 major
    wav_path = tmp_path / "c_major_test.wav"
    sf.write(str(wav_path), audio, 22050)

    analysis = analyze_audio(wav_path, beats_per_measure=4,
                              use_harmonic_separation=False)
    assert analysis.measure_count >= 1
    # The best match should at least find C as dominant
    roots = [label.root for label in analysis.chord_labels]
    assert "C" in roots


def test_analysis_to_score():
    from mariachi_music.transcription.chord_detector import analysis_to_score

    fake_label = ChordLabel(
        measure=1, time_start=0.0, time_end=2.0,
        chord="G major", root="G", quality="major",
        confidence=0.9, chroma=[0.0] * 12,
    )
    analysis = AudioAnalysis(
        audio_path="test.wav", duration_sec=2.0, sample_rate=22050,
        tempo_bpm=120.0, beats_per_measure=3,
        beat_times=[0.0, 0.5, 1.0, 1.5, 2.0],
        chord_labels=[fake_label],
    )
    score = analysis_to_score(analysis, instruments=["Guitarrón", "Guitar"])
    assert score.part_count == 2
    # Guitarrón should have 3 notes for one measure of 3/4
    assert len(score.parts[0].all_notes) == 3
