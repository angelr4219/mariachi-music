"""Audio chord detection using chromagram template matching.

Pipeline:
    1. Load audio (any format librosa supports: WAV, MP3, M4A, FLAC…)
    2. Separate harmonic layer (HPSS) — removes drums, which would blur chroma
    3. Estimate tempo + beat positions (librosa beat tracker)
    4. Segment audio into measures using beat positions
    5. Compute a chroma_cens feature for each measure (PCCP-enhanced)
    6. Match chroma vector against chord templates (cosine similarity)
    7. Detect global key via Krumhansl-Schmuckler algorithm
    8. Smooth chord sequence with Viterbi HMM pass
    9. Return AudioAnalysis with per-measure ChordLabel objects

This is not perfect source separation. It works best on:
    - Clear harmonic recordings (guitar, piano, clean mariachi)
    - Moderate tempos (60–180 BPM)
    - Music with clear harmonic rhythm (chord changes on downbeats)

For dense, very reverberant, or heavily distorted audio, expect lower confidence.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, asdict, field
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

# ──────────────────────────────────────────────────────────────────────────────
# Krumhansl-Schmuckler key profiles (published, standard values)
# ──────────────────────────────────────────────────────────────────────────────

# Major probe-tone profile (Krumhansl & Kessler 1982 ratings for C major,
# ordered C, C#, D, D#, E, F, F#, G, G#, A, A#, B)
KS_MAJOR_PROFILE = np.array([
    6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
    2.52, 5.19, 2.39, 3.66, 2.29, 2.88,
], dtype=float)

# Minor probe-tone profile (natural minor / Aeolian)
KS_MINOR_PROFILE = np.array([
    6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
    2.54, 4.75, 3.98, 2.69, 3.34, 3.17,
], dtype=float)

# Normalise profiles once (zero-mean, unit variance) for Pearson correlation
def _normalise(v: np.ndarray) -> np.ndarray:
    v = v - v.mean()
    std = v.std()
    return v / std if std > 1e-9 else v

_KS_MAJOR_NORM = _normalise(KS_MAJOR_PROFILE)
_KS_MINOR_NORM = _normalise(KS_MINOR_PROFILE)

# Ambiguity threshold for confidence_gap
AMBIGUITY_GAP_THRESHOLD = 0.05


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
        measure:          1-based measure number.
        time_start:       Start time in seconds.
        time_end:         End time in seconds.
        chord:            Full chord name e.g. 'G major', 'D minor'.
        root:             Root note e.g. 'G'.
        quality:          Quality string e.g. 'major', 'minor'.
        confidence:       Cosine similarity to best-matching template (0–1).
        confidence_gap:   Difference between best and second-best similarity.
        ambiguous:        True when confidence_gap < AMBIGUITY_GAP_THRESHOLD.
        smoothed:         True when HMM smoothing changed this label from the
                          raw per-measure detection.
        chroma:           12-element chroma vector for this measure.
    """
    measure: int
    time_start: float
    time_end: float
    chord: str
    root: str
    quality: str
    confidence: float
    chroma: list[float]
    confidence_gap: float = 0.0
    ambiguous: bool = False
    smoothed: bool = False

    @property
    def duration(self) -> float:
        return self.time_end - self.time_start

    def __str__(self) -> str:
        bar = "█" * int(self.confidence * 10)
        flags = ""
        if self.ambiguous:
            flags += " [?]"
        if self.smoothed:
            flags += " [~]"
        return (
            f"  Measure {self.measure:3d} | "
            f"{self.time_start:6.2f}s – {self.time_end:6.2f}s | "
            f"{self.chord:12s} | "
            f"confidence {self.confidence:.2f} {bar}{flags}"
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
    detected_key: str = ""
    key_confidence: float = 0.0
    smoothed_labels: list[ChordLabel] = field(default_factory=list)

    @property
    def measure_count(self) -> int:
        return len(self.chord_labels)

    def chord_accuracy_estimate(self) -> float:
        """Return the mean confidence of all chord labels as an accuracy proxy."""
        if not self.chord_labels:
            return 0.0
        return float(np.mean([label.confidence for label in self.chord_labels]))

    def summary(self) -> str:
        lines = [
            f"Audio   : {self.audio_path}",
            f"Duration: {self.duration_sec:.1f}s",
            f"Tempo   : {self.tempo_bpm:.1f} BPM",
            f"Meter   : {self.beats_per_measure}/4",
            f"Measures: {self.measure_count}",
        ]
        if self.detected_key:
            lines.append(f"Key     : {self.detected_key} (confidence {self.key_confidence:.2f})")
        lines += ["", "Chord map:"]
        display_labels = self.smoothed_labels if self.smoothed_labels else self.chord_labels
        for label in display_labels:
            lines.append(str(label))
        return "\n".join(lines)

    def chord_sequence(self) -> list[str]:
        """Compact chord names in measure order (from smoothed labels if available)."""
        labels = self.smoothed_labels if self.smoothed_labels else self.chord_labels
        return [label.chord for label in labels]

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
            "detected_key": self.detected_key,
            "key_confidence": self.key_confidence,
            "chord_labels": [label.to_dict() for label in self.chord_labels],
            "smoothed_labels": [label.to_dict() for label in self.smoothed_labels],
        }
        path.write_text(json.dumps(data, indent=2))
        return path


# ──────────────────────────────────────────────────────────────────────────────
# Core detection helpers
# ──────────────────────────────────────────────────────────────────────────────

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _pccp_enhance(chroma: np.ndarray) -> np.ndarray:
    """Pitch Class Profile enhancement: raise chroma values to power 2.

    Suppresses weak harmonics and sharpens dominant pitch classes before
    template matching.
    """
    return chroma ** 2


def _match_chord(
    chroma: np.ndarray,
    templates: dict[str, np.ndarray],
) -> tuple[str, str, str, float, float]:
    """Return (chord_name, root, quality, confidence, confidence_gap).

    confidence_gap is the difference between the best and second-best cosine
    similarity scores. A small gap indicates ambiguity.
    """
    scores: list[tuple[float, str]] = []
    for name, template in templates.items():
        sim = _cosine_similarity(chroma, template)
        scores.append((sim, name))

    scores.sort(key=lambda x: x[0], reverse=True)
    best_sim, best_name = scores[0]
    second_sim = scores[1][0] if len(scores) > 1 else best_sim
    gap = max(0.0, best_sim - second_sim)

    parts = best_name.split(" ", 1)
    root = parts[0]
    quality = parts[1] if len(parts) > 1 else "major"
    return best_name, root, quality, max(0.0, best_sim), gap


# ──────────────────────────────────────────────────────────────────────────────
# Key detection — Krumhansl-Schmuckler algorithm
# ──────────────────────────────────────────────────────────────────────────────

def detect_key(y: np.ndarray, sr: int) -> tuple[str, str, float]:
    """Detect the global key of an audio file.

    Uses the Krumhansl-Schmuckler key-finding algorithm:
      1. Compute full-file mean chroma vector (chroma_cens for robustness).
      2. Correlate against K-S major and minor profiles for all 12 rotations.
      3. Return the key (root, mode) with highest Pearson correlation.

    Args:
        y:  Audio time series (mono float32/float64).
        sr: Sample rate of y.

    Returns:
        Tuple of (root, mode, confidence) e.g. ('G', 'major', 0.87).
        confidence is the normalised Pearson correlation in [0, 1].
    """
    # Compute full-file chroma energy normalized statistics
    chroma = librosa.feature.chroma_cens(y=y, sr=sr)
    mean_chroma = np.mean(chroma, axis=1)  # shape (12,)

    # Normalise observed chroma for correlation
    chroma_norm = _normalise(mean_chroma)

    best_corr = -np.inf
    best_root = "C"
    best_mode = "major"

    for root_idx in range(12):
        # Rotate profile so that root_idx corresponds to the key root
        rotated_major = np.roll(_KS_MAJOR_NORM, root_idx)
        rotated_minor = np.roll(_KS_MINOR_NORM, root_idx)

        corr_major = float(np.dot(chroma_norm, rotated_major)) / 12.0
        corr_minor = float(np.dot(chroma_norm, rotated_minor)) / 12.0

        if corr_major > best_corr:
            best_corr = corr_major
            best_root = PITCH_CLASSES[root_idx]
            best_mode = "major"

        if corr_minor > best_corr:
            best_corr = corr_minor
            best_root = PITCH_CLASSES[root_idx]
            best_mode = "minor"

    # Map raw Pearson-like correlation (typically 0.5–1.0 for good match)
    # to a 0–1 confidence by clipping and re-scaling
    confidence = float(np.clip(best_corr, 0.0, 1.0))
    return best_root, best_mode, round(confidence, 4)


# ──────────────────────────────────────────────────────────────────────────────
# HMM chord smoothing — Viterbi pass
# ──────────────────────────────────────────────────────────────────────────────

def _build_transition_matrix(
    chord_names: list[str],
    key_root: str = "C",
    key_mode: str = "major",
    diatonic_boost: float = 4.0,
    self_transition: float = 8.0,
) -> np.ndarray:
    """Build a chord-to-chord log-probability transition matrix.

    Diatonic neighbours (I→IV, I→V, etc.) get higher probability.
    The matrix is (N x N) where N = len(chord_names).
    """
    n = len(chord_names)
    if n == 0:
        return np.zeros((0, 0))

    # Diatonic scale degrees in semitones relative to root
    if key_mode == "major":
        diatonic_semitones = {0, 2, 4, 5, 7, 9, 11}
    else:
        diatonic_semitones = {0, 2, 3, 5, 7, 8, 10}

    root_idx = PITCH_CLASSES.index(key_root) if key_root in PITCH_CLASSES else 0

    # Index chord roots
    def _root_semitone(name: str) -> int:
        root = name.split()[0]
        return PITCH_CLASSES.index(root) if root in PITCH_CLASSES else 0

    # Build unnormalised count matrix with priors
    mat = np.ones((n, n), dtype=float)

    for i, src in enumerate(chord_names):
        for j, dst in enumerate(chord_names):
            src_st = _root_semitone(src)
            dst_st = _root_semitone(dst)

            if i == j:
                mat[i, j] = self_transition
                continue

            # Check if destination root is diatonic to the key
            relative = (dst_st - root_idx) % 12
            if relative in diatonic_semitones:
                mat[i, j] = diatonic_boost
            else:
                mat[i, j] = 1.0

    # Row-normalise to get probabilities, then take log
    row_sums = mat.sum(axis=1, keepdims=True)
    mat = mat / row_sums
    return np.log(mat + 1e-12)


def _viterbi_smooth(
    observations: list[int],
    log_emission: np.ndarray,
    log_transition: np.ndarray,
    log_init: np.ndarray,
) -> list[int]:
    """Standard Viterbi algorithm for sequence decoding.

    Args:
        observations:   List of observed state indices (length T).
        log_emission:   (N, N) log-emission matrix: log P(obs=j | state=i).
                        Here we treat the matched chord index as both obs and state,
                        so emission is an identity-like softmax over similarities.
        log_transition: (N, N) log-transition matrix from _build_transition_matrix.
        log_init:       (N,) log initial state probabilities.

    Returns:
        List of decoded state indices (length T).
    """
    T = len(observations)
    N = log_transition.shape[0]

    if T == 0 or N == 0:
        return observations

    # Viterbi trellis
    viterbi = np.full((T, N), -np.inf)
    backpointer = np.zeros((T, N), dtype=int)

    # Initialise
    viterbi[0] = log_init + log_emission[:, observations[0]]
    backpointer[0] = 0

    # Recursion
    for t in range(1, T):
        for s in range(N):
            trans_prob = viterbi[t - 1] + log_transition[:, s]
            best_prev = int(np.argmax(trans_prob))
            viterbi[t, s] = trans_prob[best_prev] + log_emission[s, observations[t]]
            backpointer[t, s] = best_prev

    # Traceback
    path = [0] * T
    path[T - 1] = int(np.argmax(viterbi[T - 1]))
    for t in range(T - 2, -1, -1):
        path[t] = backpointer[t + 1, path[t + 1]]

    return path


def smooth_chord_sequence(
    labels: list[ChordLabel],
    key_root: str = "C",
    key_mode: str = "major",
) -> list[ChordLabel]:
    """Apply HMM Viterbi smoothing to a list of ChordLabel objects.

    For single-measure inputs, returns a copy with smoothed=False (no-op).
    Each ChordLabel in the returned list has smoothed=True if the label
    was changed from the raw detection.

    Args:
        labels:    Per-measure chord labels from raw detection.
        key_root:  Tonic root for building diatonic transition priors.
        key_mode:  'major' or 'minor'.

    Returns:
        New list of ChordLabel with smoothed field set appropriately.
    """
    if len(labels) <= 1:
        # Nothing to smooth
        result = []
        for lbl in labels:
            new_lbl = copy.copy(lbl)
            new_lbl.smoothed = False
            result.append(new_lbl)
        return result

    # Build ordered list of all unique chord names encountered
    all_chord_names = list({lbl.chord for lbl in labels})
    all_chord_names.sort()
    chord_to_idx = {name: i for i, name in enumerate(all_chord_names)}
    n_states = len(all_chord_names)

    # Observed sequence: index of the raw-best chord per measure
    obs_seq = [chord_to_idx[lbl.chord] for lbl in labels]

    # Log-transition matrix
    log_trans = _build_transition_matrix(all_chord_names, key_root, key_mode)

    # Emission: use per-measure confidence as a soft signal.
    # State s emitting observation o: high prob when s == o, scaled by confidence.
    # Shape: (n_states, n_states) where log_emission[s, o]
    log_emission = np.full((n_states, n_states), np.log(0.05 / max(n_states - 1, 1) + 1e-12))
    for lbl in labels:
        s = chord_to_idx[lbl.chord]
        # Self-emission probability proportional to confidence
        log_emission[s, s] = np.log(max(lbl.confidence, 1e-6))

    # Uniform initial distribution
    log_init = np.full(n_states, -np.log(n_states))

    # Viterbi decode
    decoded = _viterbi_smooth(obs_seq, log_emission, log_trans, log_init)

    # Build output labels
    result: list[ChordLabel] = []
    for t, (lbl, decoded_idx) in enumerate(zip(labels, decoded)):
        new_chord_name = all_chord_names[decoded_idx]
        new_lbl = copy.copy(lbl)
        if new_chord_name != lbl.chord:
            new_lbl.chord = new_chord_name
            parts = new_chord_name.split(" ", 1)
            new_lbl.root = parts[0]
            new_lbl.quality = parts[1] if len(parts) > 1 else "major"
            new_lbl.smoothed = True
        else:
            new_lbl.smoothed = False
        result.append(new_lbl)

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Measure boundary refinement
# ──────────────────────────────────────────────────────────────────────────────

def _refine_measure_boundary(
    y_harm: np.ndarray,
    sr: int,
    t_start: float,
    t_end: float,
    hop: int = 512,
) -> tuple[float, float]:
    """Refine a measure boundary using onset strength peaks.

    Within the window [t_start, t_end], find the onset strength peak and snap
    the start of the measure to it.  If no clear peak is found, returns the
    original boundaries unchanged.

    Args:
        y_harm:   Harmonic audio signal.
        sr:       Sample rate.
        t_start:  Nominal measure start in seconds.
        t_end:    Nominal measure end in seconds.
        hop:      Hop length for onset detection.

    Returns:
        Refined (t_start, t_end) pair.
    """
    sample_start = int(t_start * sr)
    sample_end = min(int(t_end * sr), len(y_harm))
    if sample_end <= sample_start:
        return t_start, t_end

    segment = y_harm[sample_start:sample_end]
    if len(segment) < hop * 2:
        return t_start, t_end

    onset_env = librosa.onset.onset_strength(y=segment, sr=sr, hop_length=hop)
    if onset_env.size == 0:
        return t_start, t_end

    peak_frame = int(np.argmax(onset_env))
    refined_start = t_start + librosa.frames_to_time(peak_frame, sr=sr, hop_length=hop)

    # Only accept refinement if it moves the start by less than half the measure
    measure_dur = t_end - t_start
    if abs(refined_start - t_start) > measure_dur * 0.5:
        return t_start, t_end

    return refined_start, t_end


# ──────────────────────────────────────────────────────────────────────────────
# Main analysis entry point
# ──────────────────────────────────────────────────────────────────────────────

def analyze_audio(
    audio_path,
    beats_per_measure: int = 4,
    sample_rate: int = 22_050,
    use_harmonic_separation: bool = True,
    extended_chords: bool = False,
    min_confidence: float = 0.0,
    max_duration_sec: float | None = None,
    detect_key_automatically: bool = True,
    smooth_chord_sequence: bool = True,
    refine_boundaries: bool = False,
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
        detect_key_automatically: Run Krumhansl-Schmuckler key detection and
                                  store result in AudioAnalysis.detected_key.
        smooth_chord_sequence:    Apply Viterbi HMM smoothing to reduce isolated
                                  wrong chord labels between adjacent measures.
        refine_boundaries:        If True, snap each measure boundary to the
                                  nearest onset strength peak within the window.

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
    bpm_int = max(1, beats_per_measure)
    beat_duration = 60.0 / tempo_bpm

    if len(beat_times_raw) < 2:
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

    # ── 4b. Optional boundary refinement via onset peaks ──────────────────
    hop = 512
    if refine_boundaries:
        refined = []
        for t_start, t_end in measure_boundaries:
            r_start, r_end = _refine_measure_boundary(y_harm, sr, t_start, t_end, hop)
            refined.append((r_start, r_end))
        measure_boundaries = refined

    # ── 5. Key detection ──────────────────────────────────────────────────
    detected_key_str = ""
    key_root_detected = "C"
    key_mode_detected = "major"
    key_confidence_val = 0.0

    if detect_key_automatically:
        key_root_detected, key_mode_detected, key_confidence_val = detect_key(y_harm, sr)
        detected_key_str = f"{key_root_detected} {key_mode_detected}"

    # ── 6. Chroma extraction ───────────────────────────────────────────────
    # Use chroma_cens for robustness to timbre and dynamics
    chroma_full = librosa.feature.chroma_cens(y=y_harm, sr=sr, hop_length=hop)

    # ── 7. Per-measure chord matching ─────────────────────────────────────
    templates = CHORD_TEMPLATES_EXTENDED if extended_chords else CHORD_TEMPLATES

    labels: list[ChordLabel] = []
    for m_idx, (t_start, t_end) in enumerate(measure_boundaries):
        frame_start = int(librosa.time_to_frames(t_start, sr=sr, hop_length=hop))
        frame_end = int(librosa.time_to_frames(t_end, sr=sr, hop_length=hop))
        frame_end = max(frame_end, frame_start + 1)
        frame_end = min(frame_end, chroma_full.shape[1])

        segment_chroma = chroma_full[:, frame_start:frame_end]
        if segment_chroma.shape[1] == 0:
            continue

        # Mean chroma across the measure
        mean_chroma = np.mean(segment_chroma, axis=1)

        # PCCP enhancement: raise to power 2 to suppress weak harmonics
        enhanced_chroma = _pccp_enhance(mean_chroma)

        chord_name, root, quality, confidence, gap = _match_chord(enhanced_chroma, templates)

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
            confidence_gap=round(gap, 4),
            ambiguous=(gap < AMBIGUITY_GAP_THRESHOLD),
            smoothed=False,
        ))

    # ── 8. HMM smoothing ──────────────────────────────────────────────────
    smoothed: list[ChordLabel] = []
    if smooth_chord_sequence and len(labels) >= 1:
        smoothed = _smooth_chord_sequence(
            labels,
            key_root=key_root_detected,
            key_mode=key_mode_detected,
        )

    return AudioAnalysis(
        audio_path=str(audio_path),
        duration_sec=round(total_sec, 3),
        sample_rate=sr,
        tempo_bpm=round(tempo_bpm, 2),
        beats_per_measure=beats_per_measure,
        beat_times=[round(t, 3) for t in beat_times],
        chord_labels=labels,
        detected_key=detected_key_str,
        key_confidence=key_confidence_val,
        smoothed_labels=smoothed,
    )


# Internal alias so the module-level name doesn't shadow the parameter
_smooth_chord_sequence = smooth_chord_sequence


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

    If smoothed_labels are available in the analysis, those are used
    (post-HMM sequence) for score generation.

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

    # Use detected key if available and caller did not explicitly provide one
    effective_key_root = key_root
    effective_mode = mode
    if analysis.detected_key and key_root == "C" and mode == "major":
        parts = analysis.detected_key.split()
        if len(parts) == 2:
            effective_key_root = parts[0]
            effective_mode = parts[1]

    ks = KeySignature(root=effective_key_root, mode=effective_mode)

    score = Score(
        title=f"Chord analysis — {Path(analysis.audio_path).name}",
        tempo=tp,
        key_signature=ks,
        time_signature=ts,
    )

    # Prefer smoothed labels for score generation
    source_labels = analysis.smoothed_labels if analysis.smoothed_labels else analysis.chord_labels

    for inst_name in instruments:
        inst = Instrument.by_name(inst_name)
        part = Part(instrument=inst, default_ts=ts)
        for label in source_labels:
            try:
                chord = chord_by_root(label.root, label.quality
                                      if label.quality in ("major", "minor",
                                                           "diminished", "dominant7",
                                                           "major7", "minor7")
                                      else "major")
                pattern = _get_pattern(inst, chord, ts)
                part.add_notes(pattern, duration="quarter")
            except Exception:
                for _ in range(analysis.beats_per_measure):
                    part.add_rest("quarter")
        score.add_part(part)

    return score
