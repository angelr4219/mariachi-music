"""Frequency-band stem separation — splits audio into rough instrument groups.

This is a first-pass, filter-based implementation using scipy.
It is not source separation in the deep-learning sense; it is a frequency
partitioning that gives each band a useful starting point for transcription.

Bands (approximate):
    bass     : 40 – 250 Hz   → Guitarrón
    mid      : 250 – 2000 Hz → Vihuela / Guitar / Voice
    high     : 2000 – 8000 Hz → Violin / Trumpet

Later this module can be replaced with Demucs, Spleeter, or Open-Unmix
while keeping the same public interface.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt


# ──────────────────────────────────────────────────────────────────────────────
# Stem band definitions
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StemBand:
    name: str
    low_hz: float | None   # None = no high-pass (pass everything below high_hz)
    high_hz: float | None  # None = no low-pass  (pass everything above low_hz)
    likely_instruments: tuple[str, ...]

    @property
    def display_range(self) -> str:
        lo = f"{self.low_hz:.0f} Hz" if self.low_hz else "DC"
        hi = f"{self.high_hz:.0f} Hz" if self.high_hz else "∞"
        return f"{lo} – {hi}"


STEM_BANDS: list[StemBand] = [
    StemBand("bass",  low_hz=40.0,   high_hz=250.0,  likely_instruments=("Guitarrón",)),
    StemBand("mid",   low_hz=250.0,  high_hz=2000.0, likely_instruments=("Vihuela", "Guitar", "Voice")),
    StemBand("high",  low_hz=2000.0, high_hz=8000.0, likely_instruments=("Violin", "Trumpet")),
]

MARIACHI_EDIT_BANDS: list[StemBand] = [
    StemBand("guitarron", low_hz=40.0, high_hz=180.0, likely_instruments=("Guitarrón",)),
    StemBand("rhythm", low_hz=180.0, high_hz=1200.0, likely_instruments=("Vihuela", "Guitar")),
    StemBand("violins", low_hz=500.0, high_hz=6000.0, likely_instruments=("Violin", "Trumpet")),
]


def print_stem_plan() -> None:
    """Print the configured stem bands."""
    print("Stem separation plan:")
    for band in STEM_BANDS:
        insts = ", ".join(band.likely_instruments) or "unknown"
        print(f"  {band.name:6s}  {band.display_range:20s}  → {insts}")


# ──────────────────────────────────────────────────────────────────────────────
# Filtering helpers
# ──────────────────────────────────────────────────────────────────────────────

def _bandpass(audio: np.ndarray, sr: int, low_hz: float, high_hz: float, order: int = 4) -> np.ndarray:
    nyq = sr / 2.0
    low = max(low_hz / nyq, 1e-4)
    high = min(high_hz / nyq, 1.0 - 1e-4)
    sos = butter(order, [low, high], btype="band", output="sos")
    if audio.ndim == 1:
        return sosfilt(sos, audio)
    return np.stack([sosfilt(sos, audio[:, ch]) for ch in range(audio.shape[1])], axis=1)


def _lowpass(audio: np.ndarray, sr: int, high_hz: float, order: int = 4) -> np.ndarray:
    nyq = sr / 2.0
    high = min(high_hz / nyq, 1.0 - 1e-4)
    sos = butter(order, high, btype="low", output="sos")
    if audio.ndim == 1:
        return sosfilt(sos, audio)
    return np.stack([sosfilt(sos, audio[:, ch]) for ch in range(audio.shape[1])], axis=1)


def _highpass(audio: np.ndarray, sr: int, low_hz: float, order: int = 4) -> np.ndarray:
    nyq = sr / 2.0
    low = max(low_hz / nyq, 1e-4)
    sos = butter(order, low, btype="high", output="sos")
    if audio.ndim == 1:
        return sosfilt(sos, audio)
    return np.stack([sosfilt(sos, audio[:, ch]) for ch in range(audio.shape[1])], axis=1)


def _apply_band(audio: np.ndarray, sr: int, band: StemBand) -> np.ndarray:
    if band.low_hz and band.high_hz:
        return _bandpass(audio, sr, band.low_hz, band.high_hz)
    if band.low_hz:
        return _highpass(audio, sr, band.low_hz)
    if band.high_hz:
        return _lowpass(audio, sr, band.high_hz)
    return audio.copy()


def _normalize(audio: np.ndarray) -> np.ndarray:
    peak = np.max(np.abs(audio))
    return audio / peak if peak > 1e-9 else audio


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def separate_frequency_stems(
    input_audio_path: str | Path,
    output_dir: str | Path,
    normalize: bool = True,
    overwrite: bool = True,
) -> dict[str, Path]:
    """Separate an audio file into rough frequency-band stems.

    Args:
        input_audio_path: Path to the source WAV (or any soundfile-readable format).
        output_dir:       Directory where stem WAV files will be written.
        normalize:        Whether to peak-normalize each stem before saving.
        overwrite:        Whether to overwrite existing stem files.

    Returns:
        A dict mapping stem name → output Path.
        Example: {'bass': Path('output/bass.wav'), 'mid': ..., 'high': ...}
    """
    return _separate_bands(input_audio_path, output_dir, STEM_BANDS, normalize, overwrite)


def separate_mariachi_edit_stems(
    input_audio_path: str | Path,
    output_dir: str | Path,
    normalize: bool = True,
    overwrite: bool = True,
) -> dict[str, Path]:
    """Separate audio into editable mariachi role stems.

    The bands are intentionally tuned for editing workflows:
      - guitarron: low bass fundamentals
      - rhythm: vihuela/guitar body and strums
      - violins: upper melodic instruments
    """
    return _separate_bands(input_audio_path, output_dir, MARIACHI_EDIT_BANDS, normalize, overwrite)


def _separate_bands(
    input_audio_path: str | Path,
    output_dir: str | Path,
    bands: list[StemBand],
    normalize: bool,
    overwrite: bool,
) -> dict[str, Path]:
    input_audio_path = Path(input_audio_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    audio, sr = sf.read(str(input_audio_path), always_2d=False)

    saved: dict[str, Path] = {}
    manifest: dict[str, object] = {
        "source": str(input_audio_path),
        "sample_rate": sr,
        "stems": {},
    }

    for band in bands:
        out_path = output_dir / f"{band.name}.wav"
        if out_path.exists() and not overwrite:
            saved[band.name] = out_path
            continue

        filtered = _apply_band(audio, sr, band)
        if normalize:
            filtered = _normalize(filtered)

        sf.write(str(out_path), filtered, sr)
        saved[band.name] = out_path
        manifest["stems"][band.name] = {  # type: ignore[index]
            "path": str(out_path),
            "low_hz": band.low_hz,
            "high_hz": band.high_hz,
            "likely_instruments": list(band.likely_instruments),
        }

    manifest_path = output_dir / "stems_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    return saved
