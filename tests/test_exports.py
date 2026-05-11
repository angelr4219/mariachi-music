"""Tests for MusicXML and MIDI export."""

import pytest
from pathlib import Path
from mariachi_music.generation.scale_generator import generate_scale_score


def test_musicxml_export_creates_file(tmp_path):
    score = generate_scale_score(key="C", mode="major", duration="quarter",
                                  time_signature="4/4", instrument="Violin")
    out = tmp_path / "test_scale.musicxml"
    result = score.export_musicxml(out)
    assert result.exists()
    assert result.suffix == ".musicxml"
    content = result.read_text(encoding="utf-8")
    assert "score-partwise" in content
    assert "C major" in content or "C4" in content or "C</step>" in content


def test_musicxml_contains_title(tmp_path):
    score = generate_scale_score(key="G", mode="major", duration="quarter",
                                  instrument="Trumpet", title="My Test Scale")
    out = tmp_path / "titled.musicxml"
    score.export_musicxml(out)
    content = out.read_text(encoding="utf-8")
    assert "My Test Scale" in content


def test_musicxml_multi_part(tmp_path):
    from mariachi_music.core.score import Score
    from mariachi_music.core.tempo import Tempo
    score = Score(title="Multi", tempo=Tempo(120))
    v = score.new_part("Violin")
    v.add_notes(["C4", "D4", "E4", "F4"], duration="quarter")
    t = score.new_part("Trumpet")
    t.add_notes(["G4", "A4", "B4", "C5"], duration="quarter")
    out = tmp_path / "multi.musicxml"
    score.export_musicxml(out)
    content = out.read_text(encoding="utf-8")
    assert "Violin" in content
    assert "Trumpet" in content


def test_midi_export_creates_file(tmp_path):
    score = generate_scale_score(key="C", mode="major", duration="quarter",
                                  instrument="Violin")
    out = tmp_path / "test_scale.mid"
    result = score.export_midi(out)
    assert result.exists()
    assert result.stat().st_size > 100  # non-trivial MIDI file


def test_midi_multi_instrument(tmp_path):
    from mariachi_music.core.score import Score
    from mariachi_music.core.tempo import Tempo
    score = Score(title="Multi MIDI", tempo=Tempo(140))
    for inst in ["Violin", "Guitarrón"]:
        p = score.new_part(inst)
        p.add_notes(["C4", "E4", "G4", "C5"], duration="quarter")
    out = tmp_path / "multi.mid"
    score.export_midi(out)
    assert out.exists()
