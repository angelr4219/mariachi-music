import json
from pathlib import Path

import numpy as np
import soundfile as sf

from mariachi_music.transcription.song_importer import import_local_audio
from mariachi_music.transcription.song_importer import _yt_dlp_command
from mariachi_music.transcription.stem_score import create_draft_score_from_stems
from mariachi_music.transcription.audio_verification import (
    compare_audio_files,
    synthesize_score_to_wav,
    verify_score_against_audio,
)
from mariachi_music.transcription.library_exports import export_score_library


def test_import_local_audio_writes_wav_stems_and_manifest(tmp_path: Path):
    sr = 22050
    t = np.linspace(0, 1.0, sr, endpoint=False)
    audio = (
        0.25 * np.sin(2 * np.pi * 110 * t)
        + 0.15 * np.sin(2 * np.pi * 880 * t)
        + 0.1 * np.sin(2 * np.pi * 3000 * t)
    ).astype(np.float32)
    source = tmp_path / "source.wav"
    sf.write(source, audio, sr)

    result = import_local_audio(source, title="Amor Eterno Study", output_root=tmp_path / "library")

    assert Path(result.wav_path).exists()
    assert Path(result.manifest_path).exists()
    assert Path(result.profile_path).exists()
    assert Path(result.analysis_path).exists()
    assert set(result.stems) == {"guitarron", "rhythm", "violins"}
    for path in result.stems.values():
        assert Path(path).exists()

    manifest = json.loads(Path(result.manifest_path).read_text())
    assert manifest["title"] == "Amor Eterno Study"
    assert manifest["source_type"] == "local_file"
    assert manifest["genre"] == "bolero"
    assert "permission" in manifest["rights_note"]
    assert manifest["draft_score_path"].endswith("draft_score.mariachi.json")
    assert manifest["profile_path"].endswith("song_profile.json")


def test_create_draft_score_from_imported_stems(tmp_path: Path):
    sr = 22050
    t = np.linspace(0, 1.2, int(sr * 1.2), endpoint=False)
    audio = (
        0.3 * np.sin(2 * np.pi * 98 * t)
        + 0.2 * np.sin(2 * np.pi * 440 * t)
        + 0.2 * np.sin(2 * np.pi * 1760 * t)
    ).astype(np.float32)
    source = tmp_path / "song.wav"
    sf.write(source, audio, sr)

    imported = import_local_audio(source, title="Stem Draft", output_root=tmp_path / "library")
    score = create_draft_score_from_stems(imported.stems, title="Stem Draft Score")

    assert [part.instrument.name for part in score.parts] == ["Guitarrón", "Guitar", "Violin"]
    assert score.title == "Stem Draft Score"
    assert sum(len(part.all_notes) for part in score.parts) > 0
    rhythm_events = score.parts[1].measures[0].events
    assert any(getattr(event, "chord", False) for event in rhythm_events)


def test_verification_writes_generated_audio_and_report(tmp_path: Path):
    sr = 22050
    t = np.linspace(0, 1.0, sr, endpoint=False)
    audio = (0.25 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    original = tmp_path / "original.wav"
    sf.write(original, audio, sr)

    imported = import_local_audio(original, title="Verify Draft", output_root=tmp_path / "library")
    score = create_draft_score_from_stems(imported.stems, title="Verify Score")
    generated = synthesize_score_to_wav(score, tmp_path / "generated.wav")
    comparison = compare_audio_files(original, generated)
    result = verify_score_against_audio(score, original, tmp_path / "verification", max_iterations=2)

    assert generated.exists()
    assert 0.0 <= comparison.score <= 1.0
    assert Path(result.best_wav_path).exists()
    assert Path(result.report_path).exists()


def test_export_score_library_writes_full_score_and_parts(tmp_path: Path):
    sr = 22050
    t = np.linspace(0, 1.0, sr, endpoint=False)
    audio = (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    source = tmp_path / "source.wav"
    sf.write(source, audio, sr)

    imported = import_local_audio(source, title="Library Export", output_root=tmp_path / "library")
    score = create_draft_score_from_stems(imported.stems, title="Library Score")
    result = export_score_library(score, imported.song_dir)

    score_dir = Path(result.full_score_dir)
    assert (score_dir / "full_score.musicxml").exists()
    assert (score_dir / "full_score.mid").exists()
    assert (score_dir / "full_score.wav").exists()
    assert (score_dir / "full_score.mariachi.json").exists()

    assert {"guitarron", "guitar", "violin"}.issubset(set(result.part_dirs))
    for slug, part_dir_text in result.part_dirs.items():
        part_dir = Path(part_dir_text)
        assert (part_dir / f"{slug}.musicxml").exists()
        assert (part_dir / f"{slug}.mid").exists()
        assert (part_dir / f"{slug}.wav").exists()
        assert (part_dir / f"{slug}.mariachi.json").exists()


def test_yt_dlp_command_prefers_python_module_when_available():
    cmd = _yt_dlp_command()

    assert cmd[:2] == [__import__("sys").executable, "-m"]
    assert cmd[2] == "yt_dlp"


def test_import_local_audio_uses_profile_fields(tmp_path: Path):
    sr = 22050
    t = np.linspace(0, 1.0, sr, endpoint=False)
    audio = (0.2 * np.sin(2 * np.pi * 196 * t)).astype(np.float32)
    source = tmp_path / "source.wav"
    sf.write(source, audio, sr)

    result = import_local_audio(
        source,
        title="Amor Eterno",
        output_root=tmp_path / "library",
        genre="bolero",
        tempo_bpm=172,
        time_signature="4/4",
        instruments=("Guitarrón", "Guitar", "Violin"),
        strum_style="strum_with_chord_on_top",
        section_notes="Intro, verse, chorus, ending.",
    )

    manifest = json.loads(Path(result.manifest_path).read_text())
    profile = json.loads(Path(result.profile_path).read_text())
    assert manifest["genre"] == "bolero"
    assert manifest["tempo_bpm"] == 172.0
    assert profile["strum_style"] == "strum_with_chord_on_top"
    assert profile["instruments"] == ["Guitarrón", "Guitar", "Violin"]
