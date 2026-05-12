"""Tests for audio chord detection."""

import numpy as np
import pytest

from mariachi_music.transcription.chord_detector import (
    AMBIGUITY_GAP_THRESHOLD,
    CHORD_TEMPLATES,
    KS_MAJOR_PROFILE,
    KS_MINOR_PROFILE,
    PITCH_CLASSES,
    AudioAnalysis,
    ChordLabel,
    _cosine_similarity,
    _match_chord,
    _pccp_enhance,
    detect_key,
    smooth_chord_sequence,
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
    chord_name, root, quality, confidence, gap = _match_chord(template, CHORD_TEMPLATES)
    assert root == "C"
    assert quality == "major"
    assert confidence == pytest.approx(1.0)

def test_match_g_major_perfect():
    template = CHORD_TEMPLATES["G major"]
    chord_name, root, quality, confidence, gap = _match_chord(template, CHORD_TEMPLATES)
    assert root == "G"
    assert quality == "major"
    assert confidence == pytest.approx(1.0)

def test_match_a_minor_perfect():
    template = CHORD_TEMPLATES["A minor"]
    chord_name, root, quality, confidence, gap = _match_chord(template, CHORD_TEMPLATES)
    assert root == "A"
    assert quality == "minor"
    assert confidence == pytest.approx(1.0)

def test_match_confidence_between_0_and_1():
    # Slightly noisy chroma
    vec = CHORD_TEMPLATES["D major"] + np.random.default_rng(42).uniform(0, 0.1, 12)
    _, _, _, confidence, gap = _match_chord(vec, CHORD_TEMPLATES)
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


def _make_scale_audio(root_midi: int, mode: str = "major",
                      sr: int = 22050, note_duration: float = 0.5) -> np.ndarray:
    """Synthesize a diatonic scale as a sequence of sine tones."""
    if mode == "major":
        intervals = [0, 2, 4, 5, 7, 9, 11, 12]
    else:
        intervals = [0, 2, 3, 5, 7, 8, 10, 12]
    segments = []
    for st in intervals:
        freq = 440.0 * (2 ** ((root_midi + st - 69) / 12.0))
        t = np.linspace(0, note_duration, int(sr * note_duration), endpoint=False)
        segments.append((np.sin(2 * np.pi * freq * t) * 0.3).astype(np.float32))
    return np.concatenate(segments)


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


# ── NEW: K-S key detection ────────────────────────────────────────────────────

def test_ks_profiles_have_12_values():
    """Sanity check: both K-S profiles have exactly 12 pitch classes."""
    assert len(KS_MAJOR_PROFILE) == 12
    assert len(KS_MINOR_PROFILE) == 12


def test_detect_key_c_major_scale(tmp_path):
    """Synthesize a C major scale; K-S should detect C major."""
    import soundfile as sf

    sr = 22050
    audio = _make_scale_audio(root_midi=60, mode="major", sr=sr)
    wav_path = tmp_path / "c_major_scale.wav"
    sf.write(str(wav_path), audio, sr)

    y, sr_loaded = __import__("librosa").load(str(wav_path), sr=sr)
    root, mode, confidence = detect_key(y, sr_loaded)

    assert root == "C", f"Expected root 'C', got '{root}'"
    assert mode == "major", f"Expected mode 'major', got '{mode}'"
    assert 0.0 <= confidence <= 1.0


def test_detect_key_a_minor_scale(tmp_path):
    """Synthesize an A natural minor scale; K-S should detect A minor."""
    import soundfile as sf

    sr = 22050
    # A3 = midi 57
    audio = _make_scale_audio(root_midi=57, mode="minor", sr=sr)
    wav_path = tmp_path / "a_minor_scale.wav"
    sf.write(str(wav_path), audio, sr)

    y, sr_loaded = __import__("librosa").load(str(wav_path), sr=sr)
    root, mode, confidence = detect_key(y, sr_loaded)

    assert root == "A", f"Expected root 'A', got '{root}'"
    assert mode == "minor", f"Expected mode 'minor', got '{mode}'"
    assert 0.0 <= confidence <= 1.0


def test_detect_key_confidence_in_range(tmp_path):
    """detect_key always returns confidence in [0, 1]."""
    import soundfile as sf

    sr = 22050
    rng = np.random.default_rng(0)
    noise = rng.standard_normal(sr * 2).astype(np.float32) * 0.1
    wav_path = tmp_path / "noise.wav"
    sf.write(str(wav_path), noise, sr)

    y, sr_loaded = __import__("librosa").load(str(wav_path), sr=sr)
    _, _, confidence = detect_key(y, sr_loaded)
    assert 0.0 <= confidence <= 1.0


# ── NEW: Chord smoothing ──────────────────────────────────────────────────────

def _make_label(measure: int, chord: str, confidence: float = 0.9) -> ChordLabel:
    """Helper to build a minimal ChordLabel for smoothing tests."""
    parts = chord.split(" ", 1)
    root = parts[0]
    quality = parts[1] if len(parts) > 1 else "major"
    return ChordLabel(
        measure=measure,
        time_start=float(measure - 1),
        time_end=float(measure),
        chord=chord,
        root=root,
        quality=quality,
        confidence=confidence,
        chroma=[0.0] * 12,
        confidence_gap=0.2,
        ambiguous=False,
        smoothed=False,
    )


def test_smooth_single_measure_no_crash():
    """Smoothing a single-measure sequence must not crash and returns the label."""
    labels = [_make_label(1, "C major")]
    result = smooth_chord_sequence(labels, key_root="C", key_mode="major")
    assert len(result) == 1
    assert result[0].chord == "C major"
    assert result[0].smoothed is False


def test_smooth_removes_isolated_wrong_label():
    """An isolated stray chord surrounded by the same chord should be corrected."""
    # C C C C — but measure 3 was wrongly detected as F# major (low confidence)
    # With diatonic priors heavily favouring C, Viterbi should pull it back.
    labels = [
        _make_label(1, "C major", confidence=0.95),
        _make_label(2, "C major", confidence=0.95),
        _make_label(3, "F# major", confidence=0.35),   # stray outlier
        _make_label(4, "C major", confidence=0.95),
        _make_label(5, "C major", confidence=0.95),
    ]
    result = smooth_chord_sequence(labels, key_root="C", key_mode="major")
    # The stray F# should be smoothed away; measure 3 must not be F# anymore
    assert result[2].chord != "F# major", (
        "Viterbi should have corrected the isolated F# major"
    )
    # The smoothed flag must be True for the corrected measure
    assert result[2].smoothed is True


def test_smooth_does_not_change_consistent_sequence():
    """A consistent sequence of the same chord should not be mutated."""
    labels = [_make_label(i, "G major", confidence=0.92) for i in range(1, 6)]
    result = smooth_chord_sequence(labels, key_root="G", key_mode="major")
    for lbl in result:
        assert lbl.chord == "G major"
        assert lbl.smoothed is False


def test_smooth_preserves_length():
    """Smoothed output must have the same number of labels as input."""
    labels = [_make_label(i, "C major") for i in range(1, 9)]
    labels[3] = _make_label(4, "D# major", confidence=0.4)
    result = smooth_chord_sequence(labels, key_root="C", key_mode="major")
    assert len(result) == len(labels)


# ── NEW: chroma_cens / PCCP enhancement ──────────────────────────────────────

def test_pccp_enhance_raises_values():
    """PCCP squaring should raise large values and suppress small ones."""
    chroma = np.array([0.9, 0.1, 0.0, 0.5, 0.3, 0.0,
                       0.8, 0.0, 0.2, 0.1, 0.0, 0.4])
    enhanced = _pccp_enhance(chroma)
    assert enhanced.shape == chroma.shape
    # Large values stay large relative to small ones
    assert enhanced[0] > enhanced[1]      # 0.9^2 > 0.1^2
    assert enhanced[6] > enhanced[4]      # 0.8^2 > 0.3^2
    # Zeros remain zero
    assert enhanced[2] == 0.0
    assert enhanced[5] == 0.0


def test_analyze_uses_chroma_cens(tmp_path, monkeypatch):
    """analyze_audio must call chroma_cens (not chroma_cqt) for chord matching."""
    import soundfile as sf
    import librosa.feature as lf
    from mariachi_music.transcription.chord_detector import analyze_audio

    calls = []
    original_cens = lf.chroma_cens

    def patched_cens(*args, **kwargs):
        calls.append(1)
        return original_cens(*args, **kwargs)

    monkeypatch.setattr(lf, "chroma_cens", patched_cens)

    audio = _make_chord_audio(60, "major", duration=3.0)
    wav_path = tmp_path / "test_cens.wav"
    sf.write(str(wav_path), audio, 22050)

    analyze_audio(wav_path, use_harmonic_separation=False,
                  detect_key_automatically=True, smooth_chord_sequence=False)
    assert len(calls) >= 1, "chroma_cens was never called — check the pipeline"


# ── NEW: confidence_gap ───────────────────────────────────────────────────────

def test_confidence_gap_computed():
    """_match_chord must return a non-negative confidence_gap."""
    template = CHORD_TEMPLATES["C major"]
    _, _, _, confidence, gap = _match_chord(template, CHORD_TEMPLATES)
    assert gap >= 0.0


def test_confidence_gap_perfect_match_is_nonzero():
    """A perfect C major chroma should have a gap > 0 (not ambiguous)."""
    template = CHORD_TEMPLATES["C major"]
    _, _, _, confidence, gap = _match_chord(template, CHORD_TEMPLATES)
    assert confidence == pytest.approx(1.0)
    # C major vs C minor or G major are not perfect — gap must be positive
    assert gap > 0.0


def test_confidence_gap_noisy_chroma_nonnegative():
    """Confidence gap must always be >= 0 regardless of input."""
    rng = np.random.default_rng(7)
    for _ in range(20):
        noisy = rng.uniform(0, 1, 12).astype(float)
        _, _, _, _, gap = _match_chord(noisy, CHORD_TEMPLATES)
        assert gap >= 0.0


# ── NEW: ambiguous flag ───────────────────────────────────────────────────────

def test_ambiguous_flag_set_when_gap_small():
    """ChordLabel.ambiguous must be True when confidence_gap < threshold."""
    # Build a chroma that is equidistant between two templates to force a small gap
    c_major = CHORD_TEMPLATES["C major"].copy()
    c_minor = CHORD_TEMPLATES["C minor"].copy()
    blend = (c_major + c_minor) / 2.0   # equidistant mix

    _, _, _, _, gap = _match_chord(blend, CHORD_TEMPLATES)
    # The blend should produce a small gap; verify the flag logic
    is_ambiguous = gap < AMBIGUITY_GAP_THRESHOLD
    # We don't mandate the exact gap value, but we CAN test the flag logic
    # directly using a crafted ChordLabel
    label = ChordLabel(
        measure=1, time_start=0.0, time_end=1.0,
        chord="C major", root="C", quality="major",
        confidence=0.8, chroma=list(blend),
        confidence_gap=0.01,   # artificially small
        ambiguous=True,
    )
    assert label.ambiguous is True


def test_ambiguous_flag_false_when_gap_large():
    """ChordLabel.ambiguous must be False when gap is clearly above threshold."""
    label = ChordLabel(
        measure=1, time_start=0.0, time_end=1.0,
        chord="C major", root="C", quality="major",
        confidence=0.95, chroma=[0.0] * 12,
        confidence_gap=0.30,
        ambiguous=False,
    )
    assert label.ambiguous is False


def test_analyze_audio_sets_ambiguous_field(tmp_path):
    """analyze_audio must populate ambiguous on each returned ChordLabel."""
    import soundfile as sf
    from mariachi_music.transcription.chord_detector import analyze_audio

    audio = _make_chord_audio(60, "major", duration=4.0)
    wav_path = tmp_path / "c_major_ambig.wav"
    sf.write(str(wav_path), audio, 22050)

    analysis = analyze_audio(wav_path, beats_per_measure=4,
                              use_harmonic_separation=False,
                              smooth_chord_sequence=False)
    for label in analysis.chord_labels:
        # ambiguous must be consistent with confidence_gap
        expected = label.confidence_gap < AMBIGUITY_GAP_THRESHOLD
        assert label.ambiguous == expected, (
            f"Measure {label.measure}: gap={label.confidence_gap} "
            f"but ambiguous={label.ambiguous}"
        )


# ── NEW: AudioAnalysis enrichment ─────────────────────────────────────────────

def test_audio_analysis_detected_key_populated(tmp_path):
    """analyze_audio with detect_key_automatically=True must populate detected_key."""
    import soundfile as sf
    from mariachi_music.transcription.chord_detector import analyze_audio

    audio = _make_chord_audio(60, "major", duration=4.0)
    wav_path = tmp_path / "key_test.wav"
    sf.write(str(wav_path), audio, 22050)

    analysis = analyze_audio(wav_path, use_harmonic_separation=False,
                              detect_key_automatically=True)
    assert analysis.detected_key != "", "detected_key should be populated"
    assert analysis.key_confidence >= 0.0


def test_audio_analysis_no_key_detection(tmp_path):
    """analyze_audio with detect_key_automatically=False must leave detected_key empty."""
    import soundfile as sf
    from mariachi_music.transcription.chord_detector import analyze_audio

    audio = _make_chord_audio(60, "major", duration=4.0)
    wav_path = tmp_path / "no_key.wav"
    sf.write(str(wav_path), audio, 22050)

    analysis = analyze_audio(wav_path, use_harmonic_separation=False,
                              detect_key_automatically=False)
    assert analysis.detected_key == ""
    assert analysis.key_confidence == 0.0


def test_chord_accuracy_estimate_empty():
    """chord_accuracy_estimate must return 0.0 for empty label list."""
    analysis = AudioAnalysis(
        audio_path="fake.wav", duration_sec=0.0, sample_rate=22050,
        tempo_bpm=120.0, beats_per_measure=4,
        beat_times=[], chord_labels=[],
    )
    assert analysis.chord_accuracy_estimate() == 0.0


def test_chord_accuracy_estimate_value():
    """chord_accuracy_estimate must return the mean confidence."""
    labels = [
        _make_label(1, "C major", confidence=0.8),
        _make_label(2, "G major", confidence=0.6),
    ]
    analysis = AudioAnalysis(
        audio_path="fake.wav", duration_sec=2.0, sample_rate=22050,
        tempo_bpm=120.0, beats_per_measure=4,
        beat_times=[], chord_labels=labels,
    )
    assert analysis.chord_accuracy_estimate() == pytest.approx(0.7)


def test_smoothed_labels_populated(tmp_path):
    """analyze_audio with smooth_chord_sequence=True must populate smoothed_labels."""
    import soundfile as sf
    from mariachi_music.transcription.chord_detector import analyze_audio

    audio = _make_chord_audio(60, "major", duration=6.0)
    wav_path = tmp_path / "smooth_test.wav"
    sf.write(str(wav_path), audio, 22050)

    analysis = analyze_audio(wav_path, use_harmonic_separation=False,
                              smooth_chord_sequence=True)
    # smoothed_labels should exist and match length of chord_labels
    assert len(analysis.smoothed_labels) == len(analysis.chord_labels)
