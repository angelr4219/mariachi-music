"""Audio verification for generated sheet music.

The verifier renders a generated Score to WAV, compares it to the source audio,
and writes candidate audio/report files for iterative improvement.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass, replace
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pretty_midi
import soundfile as sf

from mariachi_music.core.note import Note
from mariachi_music.core.pitch import Pitch
from mariachi_music.core.project_io import score_from_dict, score_to_dict
from mariachi_music.core.score import Score


@dataclass(frozen=True)
class AudioComparison:
    """Feature-level comparison between original and generated audio."""

    score: float
    chroma_similarity: float
    onset_similarity: float
    duration_similarity: float
    original_duration_sec: float
    generated_duration_sec: float
    original_centroid_hz: float
    generated_centroid_hz: float
    pitch_direction: str
    rhythm_status: str
    notes: tuple[str, ...]
    analysis_similarity: float = 0.0


@dataclass(frozen=True)
class VerificationResult:
    """One complete verification run result."""

    best_score: float
    accepted: bool
    best_wav_path: str
    report_path: str
    iterations: tuple[AudioComparison, ...]


def synthesize_score_to_wav(
    score: Score,
    output_path: str | Path,
    sample_rate: int = 22050,
) -> Path:
    """Render a Score to a WAV file using the existing MIDI exporter."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as tmp:
        midi_path = Path(tmp.name)
    try:
        score.export_midi(midi_path)
        midi = pretty_midi.PrettyMIDI(str(midi_path))
        audio = midi.synthesize(fs=sample_rate)
    finally:
        midi_path.unlink(missing_ok=True)

    if audio.size == 0:
        audio = np.zeros(sample_rate, dtype=np.float32)
    peak = float(np.max(np.abs(audio)))
    if peak > 1e-9:
        audio = audio / peak * 0.8
    sf.write(str(output_path), audio.astype(np.float32), sample_rate)
    return output_path


def compare_audio_files(
    original_path: str | Path,
    generated_path: str | Path,
    sample_rate: int = 22050,
) -> AudioComparison:
    """Compare original and generated audio using rough musical features."""
    import librosa

    y_orig, sr = librosa.load(str(original_path), sr=sample_rate, mono=True)
    y_gen, _ = librosa.load(str(generated_path), sr=sample_rate, mono=True)

    if y_orig.size == 0 or y_gen.size == 0:
        return AudioComparison(
            score=0.0,
            chroma_similarity=0.0,
            onset_similarity=0.0,
            duration_similarity=0.0,
            original_duration_sec=float(y_orig.size / sr),
            generated_duration_sec=float(y_gen.size / sr),
            original_centroid_hz=0.0,
            generated_centroid_hz=0.0,
            pitch_direction="unknown",
            rhythm_status="missing_audio",
            notes=("One of the audio files is empty.",),
        )

    chroma = _chroma_similarity(y_orig, y_gen, sr)
    onset = _onset_similarity(y_orig, y_gen, sr)
    dur_orig = y_orig.size / sr
    dur_gen = y_gen.size / sr
    duration = _bounded_similarity(dur_orig, dur_gen)
    cent_orig = _median_centroid(y_orig, sr)
    cent_gen = _median_centroid(y_gen, sr)

    pitch_direction = "ok"
    notes: list[str] = []
    if cent_orig > 1e-6:
        ratio = cent_gen / cent_orig
        if ratio > 1.35:
            pitch_direction = "generated_too_high"
            notes.append("Generated audio is brighter/higher than source; lower treble parts first.")
        elif ratio < 0.74:
            pitch_direction = "generated_too_low"
            notes.append("Generated audio is darker/lower than source; raise melodic parts first.")

    rhythm_status = "ok" if onset >= 0.72 else "mismatch"
    if rhythm_status == "mismatch":
        notes.append("Rhythm/onset pattern differs strongly; regenerate or quantize rhythm before export.")
    if duration < 0.9:
        notes.append("Generated duration differs from source; section lengths or tempo need adjustment.")

    score = 0.45 * chroma + 0.35 * onset + 0.20 * duration
    return AudioComparison(
        score=round(float(score), 4),
        chroma_similarity=round(float(chroma), 4),
        onset_similarity=round(float(onset), 4),
        duration_similarity=round(float(duration), 4),
        original_duration_sec=round(float(dur_orig), 3),
        generated_duration_sec=round(float(dur_gen), 3),
        original_centroid_hz=round(float(cent_orig), 3),
        generated_centroid_hz=round(float(cent_gen), 3),
        pitch_direction=pitch_direction,
        rhythm_status=rhythm_status,
        notes=tuple(notes),
    )


def verify_score_against_audio(
    score: Score,
    original_audio_path: str | Path,
    output_dir: str | Path,
    target_score: float = 0.98,
    max_iterations: int = 3,
) -> VerificationResult:
    """Render, compare, and apply basic octave correction iterations."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    candidate = score_from_dict(score_to_dict(score))
    comparisons: list[AudioComparison] = []
    best_score = -1.0
    best_wav = output_dir / "generated_candidate_1.wav"

    for iteration in range(1, max_iterations + 1):
        wav_path = output_dir / f"generated_candidate_{iteration}.wav"
        synthesize_score_to_wav(candidate, wav_path)
        comparison = compare_audio_files(original_audio_path, wav_path)
        comparison = replace(
            comparison,
            analysis_similarity=_chord_analysis_similarity(
                original_audio_path,
                wav_path,
                score.time_signature.beats_per_measure,
            ),
        )
        comparisons.append(comparison)

        if comparison.score > best_score:
            best_score = comparison.score
            best_wav = wav_path

        if comparison.score >= target_score:
            break

        changed = _apply_basic_correction(candidate, comparison)
        if not changed:
            break

    final_wav = output_dir / "generated_best.wav"
    final_wav.write_bytes(best_wav.read_bytes())
    report_path = output_dir / "verification_report.json"
    report = {
        "target_score": target_score,
        "best_score": round(float(best_score), 4),
        "accepted": best_score >= target_score,
        "best_wav_path": str(final_wav),
        "iterations": [asdict(item) for item in comparisons],
        "next_actions": _next_actions(comparisons[-1] if comparisons else None),
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return VerificationResult(
        best_score=round(float(best_score), 4),
        accepted=best_score >= target_score,
        best_wav_path=str(final_wav),
        report_path=str(report_path),
        iterations=tuple(comparisons),
    )


def _apply_basic_correction(score: Score, comparison: AudioComparison) -> bool:
    if comparison.pitch_direction == "generated_too_high":
        return _transpose_melodic_parts(score, -12)
    if comparison.pitch_direction == "generated_too_low":
        return _transpose_melodic_parts(score, 12)
    return False


def _transpose_melodic_parts(score: Score, semitones: int) -> bool:
    changed = False
    for part in score.parts:
        if part.instrument.clef == "bass":
            continue
        for measure in part.measures:
            for event in measure.events:
                if isinstance(event, Note):
                    midi = max(0, min(127, event.pitch.midi_number + semitones))
                    event.pitch = Pitch.from_midi(midi)
                    changed = True
    return changed


def _next_actions(comparison: AudioComparison | None) -> list[str]:
    if comparison is None:
        return ["No comparison was produced."]
    actions: list[str] = []
    if comparison.pitch_direction == "generated_too_high":
        actions.append("Lower violin/high parts by an octave or tighten high-stem pitch range.")
    elif comparison.pitch_direction == "generated_too_low":
        actions.append("Raise melodic parts or check if the source stem lost high instruments.")
    if comparison.rhythm_status == "mismatch":
        actions.append("Regenerate rhythm from onset/chord analysis; current notes are not matching strums.")
    if comparison.analysis_similarity < 0.6:
        actions.append("Chord and note shape are still off from the source; tighten voicing and progression matching.")
    if comparison.duration_similarity < 0.9:
        actions.append("Match tempo and section length before note-level edits.")
    if not actions:
        actions.append("Manual piano-roll/staff cleanup is the next useful step.")
    return actions


def _chroma_similarity(y_orig: np.ndarray, y_gen: np.ndarray, sr: int) -> float:
    import librosa

    c1 = librosa.feature.chroma_stft(y=y_orig, sr=sr)
    c2 = librosa.feature.chroma_stft(y=y_gen, sr=sr)
    return _matrix_cosine(c1, c2)


def _onset_similarity(y_orig: np.ndarray, y_gen: np.ndarray, sr: int) -> float:
    import librosa

    o1 = librosa.onset.onset_strength(y=y_orig, sr=sr)
    o2 = librosa.onset.onset_strength(y=y_gen, sr=sr)
    return _vector_cosine(_resample_vector(o1, 256), _resample_vector(o2, 256))


def _matrix_cosine(a: np.ndarray, b: np.ndarray) -> float:
    frames = min(a.shape[1], b.shape[1])
    if frames <= 0:
        return 0.0
    return _vector_cosine(a[:, :frames].reshape(-1), b[:, :frames].reshape(-1))


def _vector_cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 1e-9:
        return 0.0
    value = float(np.dot(a, b) / denom)
    return max(0.0, min(1.0, value))


def _resample_vector(values: np.ndarray, size: int) -> np.ndarray:
    if values.size == 0:
        return np.zeros(size)
    x_old = np.linspace(0.0, 1.0, values.size)
    x_new = np.linspace(0.0, 1.0, size)
    return np.interp(x_new, x_old, values)


def _bounded_similarity(a: float, b: float) -> float:
    denom = max(abs(a), abs(b), 1e-9)
    return max(0.0, min(1.0, 1.0 - abs(a - b) / denom))


def _median_centroid(y: np.ndarray, sr: int) -> float:
    import librosa

    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    values = centroid[np.isfinite(centroid)]
    if values.size == 0:
        return 0.0
    return float(np.median(values))


def _chord_analysis_similarity(
    original_path: str | Path,
    generated_path: str | Path,
    beats_per_measure: int,
) -> float:
    """Compare chord sequences detected from the source and generated audio."""
    try:
        from mariachi_music.transcription.chord_detector import analyze_audio
    except Exception:
        return 0.0

    try:
        source = analyze_audio(
            original_path,
            beats_per_measure=beats_per_measure,
            detect_key_automatically=True,
            smooth_chord_sequence=True,
            refine_boundaries=False,
        )
        generated = analyze_audio(
            generated_path,
            beats_per_measure=beats_per_measure,
            detect_key_automatically=True,
            smooth_chord_sequence=True,
            refine_boundaries=False,
        )
    except Exception:
        return 0.0

    src = source.chord_sequence()
    dst = generated.chord_sequence()
    if not src or not dst:
        return 0.0
    return float(SequenceMatcher(None, src, dst).ratio())
