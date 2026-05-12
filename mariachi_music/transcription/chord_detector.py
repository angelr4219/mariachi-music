"""Audio chord detection using chromagram template matching.

Pipeline:
    1. Load audio (any format librosa supports: WAV, MP3, M4A, FLAC…)
    2. Separate harmonic layer (HPSS) — removes drums, which would blur chroma
    3. Estimate tempo + beat positions (librosa beat tracker)
    4. Segment audio into measures using beat positions
    5. Compute a CQT chromagram for each measure
    6. Match chroma vector against 24 major/minor chord templates (cosine similarity)
    7. Return a list of ChordLabel objects — one per measure

This is not perfect source separation. It works best on:
    - Clear harmonic recordings (guitar, piano, clean mariachi)
    - Moderate tempos (60–180 BPM)
    - Music with clear harmonic rhythm (chord changes on downbeats)

For dense, very reverberant, or heavily distorted audio, expect lower confidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

import librosa
import numpy as np


# ──────────────────────────────────────────────────────────────────────────────
# Pitch class and chord template definitions
# ──────────────────────────────────────────────────────────────────────────────

# 12 chroma bins in librosa order: C, C#, D, D#, E, F, F#, G, G#, A, A#, B
PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Intervals from root (in semitones) for each chord quality
_TEMPLATE_INTERVALS: dict[str, list[int]] = {
    "major":      [0, 4, 7],
    "minor":      [0, 3, 7],
    "diminished": [0, 3, 6],
    "augmented":  [0, 4, 8],
    "dominant7":  [0, 4, 7, 10],
    "major7":     [0, 4, 7, 11],
    "minor7":     [0, 3, 7, 10],
    "sus2":       [0, 2, 7],
    "sus4":       [0, 5, 7],
}


def _build_templates(qualities: list[str] | None = None) -> dict[str, np.ndarray]:
    """Build chroma templates for all roots × requested qualities."""
    if qualities is None:
        qualities = ["major", "minor"]  # default: triads only

    templates: dict[str, np.ndarray] = {}
    for root_idx, root in enumerate(PITCH_CLASSES):
        for quality in qualities:
            intervals = _TEMPLATE_INTERVALS[quality]
            vec = np.zeros(12)
            for semitone in intervals:
                vec[(root_idx + semitone) % 12] = 1.0
            name = f"{root} {quality}" if quality != "major" else root
            # Also store with explicit "major" suffix for lookups
            templates[f"{root} {quality}"] = vec
    return templates


# Pre-built templates for major + minor triads (fast path)
CHORD_TEMPLATES: dict[str, np.ndarray] = _build_templates(["major", "minor"])

# Extended templates (triads + 7ths) — used when extended=True
CHORD_TEMPLATES_EXTENDED: dict[str, np.ndarray] = _build_templates(
    ["major", "minor", "diminished", "dominant7", "major7", "minor7"]
)


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ChordLabel:
    """A single chord label covering one measure of music.

    Attributes:
        measure:     1-based measure number.
        time_start:  Start time in seconds.
        time_end:    End time in seconds.
        chord:       Full chord name e.g. 'G major', 'D minor'.
        root:        Root note e.g. 'G'.
        quality:     Quality string e.g. 'major', 'minor'.
        confidence:  Cosine similarity to best-matching template (0–1).
        chroma:      12-element chroma vector for this measure.
    """
    measure: int
    time_start: float
    time_end: float
    chord: str
    root: str
    quality: str
    confidence: float
    chroma: list[float]

    @property
    def duration(self) -> float:
        return self.time_end - self.time_start

    def __str__(self) -> str:
        bar = "█" * int(self.confidence * 10)
        return (
            f"  Measure {self.measure:3d} | "
            f"{self.time_start:6.2f}s – {self.time_end:6.2f}s | "
            f"{self.chord:12s} | "
            f"confidence {self.confidence:.2f} {bar}"
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["duration"] = self.duration
        return d


@dataclass
class AudioAnalysis:
    """Full analysis result for one audio file."""
    audio_path: str
    duration_sec: float
    sample_rate: int
    tempo_bpm: float
    beats_per_measure: int
    beat_times: list[float]
    chord_labels: list[ChordLabel]

    @property
    def measure_count(self) -> int:
        return len(self.chord_labels)

    def summary(self) -> str:
        lines = [
            f"Audio   : {self.audio_path}",
            f"Duration: {self.duration_sec:.1f}s",
            f"Tempo   : {self.tempo_bpm:.1f} BPM",
            f"Meter   : {self.beats_per_measure}/4",
            f"Measures: {self.measure_count}",
            "",
            "Chord map:",
        ]
        for label in self.chord_labels:
            lines.append(str(label))
        return "\n".join(lines)

    def chord_sequence(self) -> list[str]:
        """Compact chord names in measure order."""
        return [label.chord for label in self.chord_labels]

    def to_json(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "audio_path": self.audio_path,
            "duration_sec": self.duration_sec,
            "sample_rate": self.sample_rate,
            "tempo_bpm": self.tempo_bpm,
            "beats_per_measure": self.beats_per_measure,
            "beat_times": self.beat_times,
            "chord_labels": [label.to_dict() for label in self.chord_labels],
        }
        path.write_text(json.dumps(data, indent=2))
        return path


# ──────────────────────────────────────────────────────────────────────────────
# Core detection
# ──────────────────────────────────────────────────────────────────────────────

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _match_chord(
    chroma: np.ndarray,
    templates: dict[str, np.ndarray],
) -> tuple[str, str, str, float]:
    """Return (chord_name, root, quality, confidence) for the best-matching template."""
    best_name = "unknown"
    best_sim = -1.0
    for name, template in templates.items():
        sim = _cosine_similarity(chroma, template)
        if sim > best_sim:
            best_sim = sim
            best_name = name

    # Parse root and quality from name like "G major" or "D minor"
    parts = best_name.split(" ", 1)
    root = parts[0]
    quality = parts[1] if len(parts) > 1 else "major"
    return best_name, root, quality, max(0.0, best_sim)


def analyze_audio(
    audio_path: str | Path,
    beats_per_measure: int = 4,
    sample_rate: int = 22_050,
    use_harmonic_separation: bool = True,
    extended_chords: bool = False,
    min_confidence: float = 0.0,
    max_duration_sec: float | None = None,
) -> AudioAnalysis:
    """Analyze an audio file: detect tempo, measure boundaries, and chord per measure.

    Args:
        audio_path:               Path to any audio file (WAV, MP3, M4A, FLAC…).
        beats_per_measure:        Beats per measure — 4 for 4/4, 3 for 3/4, etc.
        sample_rate:              Working sample rate (downsample for speed).
        use_harmonic_separation:  Apply HPSS to isolate harmonic content before
                                  computing chroma (strongly recommended).
        extended_chords:          If True, also consider 7th chords in matching.
        min_confidence:           Discard labels below this confidence threshold.
        max_duration_sec:         Analyze only the first N seconds (useful for
                                  quick previews of long files).

    Returns:
        AudioAnalysis with per-measure ChordLabel objects.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # ── 1. Load audio ──────────────────────────────────────────────────────
    duration = max_duration_sec  # None = full file
    y, sr = librosa.load(str(audio_path), sr=sample_rate, mono=True, duration=duration)
    total_sec = float(len(y)) / sr

    # ── 2. Harmonic / percussive separation ────────────────────────────────
    if use_harmonic_separation:
        y_harm, _ = librosa.effects.hpss(y, margin=3.0)
    else:
        y_harm = y

    # ── 3. Tempo + beat tracking ───────────────────────────────────────────
    tempo_raw, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
    if isinstance(tempo_raw, np.ndarray):
        tempo_bpm = float(tempo_raw.ravel()[0]) if tempo_raw.size else 120.0
    else:
        tempo_bpm = float(tempo_raw)
    if not np.isfinite(tempo_bpm) or tempo_bpm <= 0:
        tempo_bpm = 120.0

    beat_times_raw = librosa.frames_to_time(beat_frames, sr=sr).tolist()

    # ── 4. Segment into measures ───────────────────────────────────────────
    # Group consecutive beat_times into measures of `beats_per_measure` beats.
    # Fallback: if beat tracking found no beats (e.g. pure sine, very short clip),
    # generate uniform beats from the estimated tempo.
    bpm_int = max(1, beats_per_measure)
    beat_duration = 60.0 / tempo_bpm

    if len(beat_times_raw) < 2:
        # No reliable beat track — fall back to uniform grid
        beat_times_raw = [
            round(i * beat_duration, 4)
            for i in range(int(total_sec / beat_duration) + 1)
            if i * beat_duration <= total_sec
        ]

    beat_times = beat_times_raw
    measure_boundaries: list[tuple[float, float]] = []
    n_beats = len(beat_times)

    i = 0
    while i < n_beats:
        start = beat_times[i]
        end_idx = min(i + bpm_int, n_beats - 1)
        end = beat_times[end_idx] if end_idx < n_beats else total_sec
        if end <= start:
            end = start + (60.0 / tempo_bpm) * bpm_int
        measure_boundaries.append((start, end))
        i += bpm_int

    # ── 5. Chroma extraction + chord matching ──────────────────────────────
    templates = CHORD_TEMPLATES_EXTENDED if extended_chords else CHORD_TEMPLATES

    # Full-file CQT chroma (constant-Q transform gives better pitch accuracy)
    hop = 512
    chroma_full = librosa.feature.chroma_cqt(y=y_harm, sr=sr, hop_length=hop, bins_per_octave=36)

    labels: list[ChordLabel] = []
    for m_idx, (t_start, t_end) in enumerate(measure_boundaries):
        frame_start = int(librosa.time_to_frames(t_start, sr=sr, hop_length=hop))
        frame_end = int(librosa.time_to_frames(t_end, sr=sr, hop_length=hop))
        frame_end = max(frame_end, frame_start + 1)
        frame_end = min(frame_end, chroma_full.shape[1])

        segment_chroma = chroma_full[:, frame_start:frame_end]
        if segment_chroma.shape[1] == 0:
            continue

        # Mean chroma across the measure, then normalize
        mean_chroma = np.mean(segment_chroma, axis=1)

        chord_name, root, quality, confidence = _match_chord(mean_chroma, templates)

        if confidence < min_confidence:
            continue

        labels.append(ChordLabel(
            measure=m_idx + 1,
            time_start=round(t_start, 3),
            time_end=round(t_end, 3),
            chord=chord_name,
            root=root,
            quality=quality,
            confidence=round(confidence, 4),
            chroma=[round(float(v), 4) for v in mean_chroma],
        ))

    return AudioAnalysis(
        audio_path=str(audio_path),
        duration_sec=round(total_sec, 3),
        sample_rate=sr,
        tempo_bpm=round(tempo_bpm, 2),
        beats_per_measure=beats_per_measure,
        beat_times=[round(t, 3) for t in beat_times],
        chord_labels=labels,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Score conversion
# ──────────────────────────────────────────────────────────────────────────────

def analysis_to_score(
    analysis: AudioAnalysis,
    instruments: list[str] | None = None,
    key_root: str = "C",
    mode: str = "major",
) -> "Score":  # type: ignore[name-defined]
    """Convert a chord analysis into a Score object with instrument voicings.

    Each detected chord becomes a measure, with each instrument playing
    its idiomatic pattern for that chord.

    Args:
        analysis:    The AudioAnalysis result from analyze_audio().
        instruments: Instrument names to include (default: Guitarrón, Guitar, Violin).
        key_root:    Key signature root for the score header.
        mode:        Key mode for the score header.

    Returns:
        A Score ready to export as MusicXML or MIDI.
    """
    from mariachi_music.core.instrument import Instrument
    from mariachi_music.core.key_signature import KeySignature
    from mariachi_music.core.part import Part
    from mariachi_music.core.score import Score
    from mariachi_music.core.tempo import Tempo
    from mariachi_music.core.time_signature import TimeSignature
    from mariachi_music.generation.chord_generator import _get_pattern
    from mariachi_music.theory.chords import chord_by_root

    if instruments is None:
        instruments = ["Guitarrón", "Guitar", "Violin"]

    ts = TimeSignature(analysis.beats_per_measure, 4)
    tp = Tempo(bpm=analysis.tempo_bpm)
    ks = KeySignature(root=key_root, mode=mode)

    score = Score(
        title=f"Chord analysis — {Path(analysis.audio_path).name}",
        tempo=tp,
        key_signature=ks,
        time_signature=ts,
    )

    for inst_name in instruments:
        inst = Instrument.by_name(inst_name)
        part = Part(instrument=inst, default_ts=ts)
        for label in analysis.chord_labels:
            try:
                chord = chord_by_root(label.root, label.quality
                                      if label.quality in ("major", "minor",
                                                           "diminished", "dominant7",
                                                           "major7", "minor7")
                                      else "major")
                pattern = _get_pattern(inst, chord, ts)
                part.add_notes(pattern, duration="quarter")
            except Exception:
                # If a chord can't be voiced, fill with a rest measure
                for _ in range(analysis.beats_per_measure):
                    part.add_rest("quarter")
        score.add_part(part)

    return score
