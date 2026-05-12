"""Import existing songs into local analysis folders.

This module stores local working assets for songs the user is allowed to
analyze. It does not ship or redistribute copyrighted recordings.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from importlib.util import find_spec
from pathlib import Path

import soundfile as sf

from mariachi_music.transcription.chord_detector import analyze_audio, analysis_to_score
from mariachi_music.transcription.song_profile import SongProfile
from mariachi_music.transcription.stem_separation import separate_mariachi_edit_stems


DEFAULT_IMPORT_ROOT = Path("outputs/imported_songs")


@dataclass(frozen=True)
class ImportedSong:
    """Paths created by an import job."""

    title: str
    source: str
    source_type: str
    genre: str
    tempo_bpm: float
    time_signature: str
    instruments: tuple[str, ...]
    strum_style: str
    section_notes: str
    key: str
    mode: str
    song_dir: str
    wav_path: str
    stems_dir: str
    stems: dict[str, str]
    profile_path: str
    analysis_path: str
    analysis_score_path: str
    manifest_path: str
    draft_score_path: str
    rights_note: str


def import_local_audio(
    input_path: str | Path,
    title: str = "",
    output_root: str | Path = DEFAULT_IMPORT_ROOT,
    create_stems: bool = True,
    genre: str = "bolero",
    tempo_bpm: float = 172.0,
    time_signature: str = "4/4",
    instruments: tuple[str, ...] = ("Guitarrón", "Guitar", "Violin"),
    strum_style: str = "strum_with_chord_on_top",
    section_notes: str = "",
    key: str = "C",
    mode: str = "major",
) -> ImportedSong:
    """Copy/convert a local audio file to WAV and optionally create stems."""
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Audio file does not exist: {input_path}")

    song_title = title.strip() or input_path.stem
    song_dir = _unique_song_dir(output_root, song_title)
    song_dir.mkdir(parents=True, exist_ok=True)

    wav_path = song_dir / "source.wav"
    _convert_to_wav(input_path, wav_path)
    return _finish_import(
        title=song_title,
        source=str(input_path),
        source_type="local_file",
        genre=genre,
        tempo_bpm=tempo_bpm,
        time_signature=time_signature,
        instruments=instruments,
        strum_style=strum_style,
        section_notes=section_notes,
        key=key,
        mode=mode,
        song_dir=song_dir,
        wav_path=wav_path,
        create_stems=create_stems,
    )


def import_youtube_audio(
    url: str,
    title: str = "",
    output_root: str | Path = DEFAULT_IMPORT_ROOT,
    create_stems: bool = True,
    genre: str = "bolero",
    tempo_bpm: float = 172.0,
    time_signature: str = "4/4",
    instruments: tuple[str, ...] = ("Guitarrón", "Guitar", "Violin"),
    strum_style: str = "strum_with_chord_on_top",
    section_notes: str = "",
    key: str = "C",
    mode: str = "major",
) -> ImportedSong:
    """Download a YouTube audio track as WAV and optionally create stems.

    Requires `yt-dlp` and an ffmpeg executable on PATH.
    """
    if not url.strip():
        raise ValueError("YouTube URL is required.")
    yt_dlp_cmd = _yt_dlp_command()

    song_title = title.strip() or "youtube_import"
    song_dir = _unique_song_dir(output_root, song_title)
    song_dir.mkdir(parents=True, exist_ok=True)
    wav_path = song_dir / "source.wav"

    cmd = [
        *yt_dlp_cmd,
        "--extract-audio",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "--no-playlist",
        "--output", str(song_dir / "download.%(ext)s"),
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp failed:\n{proc.stderr.strip() or proc.stdout.strip()}")

    downloaded = song_dir / "download.wav"
    if not downloaded.exists():
        matches = list(song_dir.glob("download.*"))
        if not matches:
            raise RuntimeError("yt-dlp completed but no downloaded audio file was found.")
        _convert_to_wav(matches[0], wav_path)
    else:
        downloaded.replace(wav_path)

    return _finish_import(
        title=song_title,
        source=url,
        source_type="youtube_url",
        genre=genre,
        tempo_bpm=tempo_bpm,
        time_signature=time_signature,
        instruments=instruments,
        strum_style=strum_style,
        section_notes=section_notes,
        key=key,
        mode=mode,
        song_dir=song_dir,
        wav_path=wav_path,
        create_stems=create_stems,
    )


def _finish_import(
    title: str,
    source: str,
    source_type: str,
    genre: str,
    tempo_bpm: float,
    time_signature: str,
    instruments: tuple[str, ...],
    strum_style: str,
    section_notes: str,
    key: str,
    mode: str,
    song_dir: Path,
    wav_path: Path,
    create_stems: bool,
) -> ImportedSong:
    stems_dir = song_dir / "stems"
    stems: dict[str, str] = {}
    if create_stems:
        separated = separate_mariachi_edit_stems(wav_path, stems_dir)
        stems = {name: str(path) for name, path in separated.items()}
    else:
        stems_dir.mkdir(parents=True, exist_ok=True)

    beats_per_measure = _beats_per_measure_from_time_signature(time_signature, genre)
    profile = SongProfile(
        title=title,
        source=source,
        source_type=source_type,
        genre=genre,
        tempo_bpm=float(tempo_bpm),
        time_signature=time_signature,
        instruments=instruments,
        strum_style=strum_style,
        section_notes=section_notes,
        key=key,
        mode=mode,
        beats_per_measure=beats_per_measure,
    )
    profile_path = profile.write_json(song_dir / "song_profile.json")

    analysis_dir = song_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    analysis_path = analysis_dir / "source_analysis.json"
    analysis_score_path = analysis_dir / "source_analysis.musicxml"

    try:
        analysis = analyze_audio(
            wav_path,
            beats_per_measure=beats_per_measure,
            max_duration_sec=profile.analysis_seconds,
            detect_key_automatically=True,
            smooth_chord_sequence=True,
            refine_boundaries=True,
        )
        analysis_path = analysis.to_json(analysis_path)
        source_score = analysis_to_score(
            analysis,
            instruments=list(instruments) if instruments else None,
            key_root=key,
            mode=mode,
        )
        source_score.export_musicxml(analysis_score_path)
        source_score.export_midi(analysis_dir / "source_analysis.mid")
    except Exception:
        analysis_path.write_text(json.dumps({"status": "analysis_failed"}), encoding="utf-8")

    result = ImportedSong(
        title=title,
        source=source,
        source_type=source_type,
        genre=genre,
        tempo_bpm=float(tempo_bpm),
        time_signature=time_signature,
        instruments=instruments,
        strum_style=strum_style,
        section_notes=section_notes,
        key=key,
        mode=mode,
        song_dir=str(song_dir),
        wav_path=str(wav_path),
        stems_dir=str(stems_dir),
        stems=stems,
        profile_path=str(profile_path),
        analysis_path=str(analysis_path),
        analysis_score_path=str(analysis_score_path),
        manifest_path=str(song_dir / "song_manifest.json"),
        draft_score_path=str(song_dir / "draft_score.mariachi.json"),
        rights_note=(
            "Store and analyze only music you own, created, licensed, or have "
            "permission to use. Do not redistribute copyrighted recordings."
        ),
    )
    manifest_path = Path(result.manifest_path)
    manifest_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    return result


def _convert_to_wav(input_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        audio, sr = sf.read(str(input_path), always_2d=False)
        sf.write(str(output_path), audio, sr)
        return
    except Exception:
        pass

    try:
        import librosa

        audio, sr = librosa.load(str(input_path), sr=None, mono=False)
        if audio.ndim == 2:
            audio = audio.T
        sf.write(str(output_path), audio, sr)
    except Exception as exc:
        raise RuntimeError(f"Could not convert {input_path} to WAV: {exc}") from exc


def _unique_song_dir(output_root: str | Path, title: str) -> Path:
    root = Path(output_root)
    slug = _slugify(title) or "song"
    candidate = root / slug
    i = 2
    while candidate.exists():
        candidate = root / f"{slug}_{i}"
        i += 1
    return candidate


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _beats_per_measure_from_time_signature(time_signature: str, genre: str) -> int:
    if "/" in time_signature:
        head = time_signature.split("/", 1)[0]
        if head.isdigit():
            return max(1, int(head))
    genre = genre.lower().strip()
    if genre == "son":
        return 6
    return 4


def _yt_dlp_command() -> list[str]:
    """Return the preferred yt-dlp command.

    Prefer the Python package because PATH may point at an older Homebrew or
    system binary while the active Python environment has a newer yt-dlp.
    """
    if find_spec("yt_dlp") is not None:
        return [sys.executable, "-m", "yt_dlp"]
    binary = shutil.which("yt-dlp")
    if binary:
        return [binary]
    raise RuntimeError("yt-dlp is not installed. Install optional transcription dependencies first.")
