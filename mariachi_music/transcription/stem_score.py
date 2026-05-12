"""Create editable draft scores from separated mariachi stems."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from mariachi_music.core.instrument import Instrument
from mariachi_music.core.key_signature import KeySignature
from mariachi_music.core.part import Part
from mariachi_music.core.pitch import Pitch
from mariachi_music.core.score import Score
from mariachi_music.core.tempo import Tempo
from mariachi_music.core.time_signature import TimeSignature
from mariachi_music.theory.chords import chord_by_root


@dataclass(frozen=True)
class StemTranscriptionConfig:
    stem_name: str
    instrument: str
    fmin: str
    fmax: str
    duration: str = "eighth"
    max_notes: int = 96


DEFAULT_STEM_CONFIGS: dict[str, StemTranscriptionConfig] = {
    "guitarron": StemTranscriptionConfig("guitarron", "Guitarrón", "E1", "C4", "quarter", 96),
    "rhythm": StemTranscriptionConfig("rhythm", "Guitar", "E2", "C5", "eighth", 160),
    "violins": StemTranscriptionConfig("violins", "Violin", "G3", "C6", "eighth", 128),
    "bass": StemTranscriptionConfig("bass", "Guitarrón", "E1", "C4", "quarter", 96),
    "mid": StemTranscriptionConfig("mid", "Guitar", "E2", "C5", "eighth", 128),
    "high": StemTranscriptionConfig("high", "Violin", "G3", "C7", "eighth", 128),
}


def create_draft_score_from_stems(
    stems: dict[str, str | Path],
    title: str = "Imported Song Draft",
    key: str = "C",
    tempo: float = 120.0,
    time_signature: str = "4/4",
) -> Score:
    """Create an editable score from stem WAV files.

    This is a rough transcription layer. It extracts a dominant pitch contour
    from each stem and turns it into editable notes so the user can correct it
    in the piano roll/staff views before exporting.
    """
    score = Score(
        title=title,
        composer="",
        tempo=Tempo(float(tempo)),
        key_signature=KeySignature(key, "major"),
        time_signature=TimeSignature.parse(time_signature),
    )

    for stem_name in _ordered_stems(stems):
        path = Path(stems[stem_name])
        config = DEFAULT_STEM_CONFIGS.get(stem_name)
        if config is None:
            continue
        part = _transcribe_stem_to_part(path, config, score.time_signature)
        score.add_part(part)

    return score


def _ordered_stems(stems: dict[str, str | Path]) -> list[str]:
    preferred = ["guitarron", "rhythm", "violins", "bass", "mid", "high"]
    return [name for name in preferred if name in stems] + [
        name for name in stems if name not in preferred
    ]


def _transcribe_stem_to_part(
    path: Path,
    config: StemTranscriptionConfig,
    time_signature: TimeSignature,
) -> Part:
    import librosa

    y, sr = librosa.load(str(path), sr=22050, mono=True)
    part = Part(Instrument.by_name(config.instrument), default_ts=time_signature)
    if y.size == 0 or np.max(np.abs(y)) < 1e-5:
        return part

    if config.stem_name == "rhythm":
        return _transcribe_rhythm_stem_to_part(y, sr, config, time_signature)

    midi = _dominant_midi_track(
        y,
        sr,
        fmin=librosa.note_to_hz(config.fmin),
        fmax=librosa.note_to_hz(config.fmax),
    )
    notes = _group_midi_track(midi, min_frames=3, max_notes=config.max_notes)
    for midi_note in notes:
        part.add_note(str(Pitch.from_midi(int(midi_note))), config.duration)
    return part


def _transcribe_rhythm_stem_to_part(
    y: np.ndarray,
    sr: int,
    config: StemTranscriptionConfig,
    time_signature: TimeSignature,
) -> Part:
    """Create chord-strum events from rhythm stem onsets."""
    import librosa

    part = Part(Instrument.by_name(config.instrument), default_ts=time_signature)
    root = _dominant_chroma_root(y, sr)
    chord = chord_by_root(root, "major")
    pitches = [str(pitch) for pitch in chord.pitches_at_octave(3)]

    onset_frames = librosa.onset.onset_detect(
        y=y,
        sr=sr,
        hop_length=512,
        backtrack=False,
        units="frames",
    )
    if len(onset_frames) == 0:
        # Fallback: steady eighth-note chops for a small editable draft.
        for _ in range(min(config.max_notes, 32)):
            part.add_chord(pitches, config.duration)
        return part

    for _frame in onset_frames[:config.max_notes]:
        part.add_chord(pitches, config.duration)
    return part


def _dominant_chroma_root(y: np.ndarray, sr: int) -> str:
    import librosa

    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    if chroma.size == 0:
        return "C"
    idx = int(np.argmax(np.mean(chroma, axis=1)))
    return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][idx]


def _dominant_midi_track(
    y: np.ndarray,
    sr: int,
    fmin: float,
    fmax: float,
    n_fft: int = 2048,
    hop_length: int = 512,
) -> np.ndarray:
    import librosa

    spectrum = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop_length))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    mask = (freqs >= fmin) & (freqs <= fmax)
    if not np.any(mask) or spectrum.shape[1] == 0:
        return np.array([], dtype=float)

    band = spectrum[mask]
    band_freqs = freqs[mask]
    frame_energy = band.max(axis=0)
    threshold = max(float(np.median(frame_energy) * 0.5), float(frame_energy.max() * 0.02))
    max_indices = np.argmax(band, axis=0)
    hz = band_freqs[max_indices]
    midi = np.rint(librosa.hz_to_midi(hz)).astype(float)
    midi[frame_energy < threshold] = np.nan
    return midi


def _group_midi_track(
    midi: np.ndarray,
    min_frames: int = 3,
    max_notes: int = 128,
) -> list[int]:
    notes: list[int] = []
    current: int | None = None
    count = 0

    for value in midi:
        note = None if np.isnan(value) else int(value)
        if note == current:
            count += 1
            continue
        if current is not None and count >= min_frames:
            notes.append(current)
            if len(notes) >= max_notes:
                return notes
        current = note
        count = 1

    if current is not None and count >= min_frames and len(notes) < max_notes:
        notes.append(current)

    return _collapse_repeats(notes)


def _collapse_repeats(notes: list[int]) -> list[int]:
    collapsed: list[int] = []
    for note in notes:
        if not collapsed or collapsed[-1] != note:
            collapsed.append(note)
    return collapsed
