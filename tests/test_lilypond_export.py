"""Tests for the LilyPond export backend.

Run with:
    pytest tests/test_lilypond_export.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mariachi_music.core.duration import Duration, DurationValue
from mariachi_music.core.instrument import Instrument
from mariachi_music.core.key_signature import KeySignature
from mariachi_music.core.measure import Measure
from mariachi_music.core.note import Note, Rest
from mariachi_music.core.part import Part
from mariachi_music.core.pitch import Pitch
from mariachi_music.core.score import Score
from mariachi_music.core.tempo import Tempo
from mariachi_music.core.time_signature import TimeSignature
from mariachi_music.export.lilypond_export import (
    _duration_to_lily,
    _key_to_lily,
    _pitch_to_lily,
    export_score_lilypond,
    render_lilypond_pdf,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _c_major_scale_score(title: str = "C Major Scale") -> Score:
    """Build a minimal one-part score: C major scale in 4/4, quarter notes."""
    score = Score(
        title=title,
        composer="Test Suite",
        tempo=Tempo(120),
        key_signature=KeySignature("C", "major"),
        time_signature=TimeSignature(4, 4),
    )
    part = score.new_part("Violin")
    part.add_notes(["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"], duration="quarter")
    return score


def _export_and_read(score: Score, dest: Path) -> str:
    """Export *score* and return the file contents as a string.

    *dest* may be a directory (in which case 'test_score.ly' is used) or a
    direct .ly file path.
    """
    if dest.suffix.lower() == ".ly":
        out_path = dest
    else:
        out_path = dest / "test_score.ly"
    out = export_score_lilypond(score, out_path)
    return out.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Unit tests for pitch encoding
# ---------------------------------------------------------------------------

class TestPitchEncoding:
    def test_middle_c(self):
        assert _pitch_to_lily(Pitch("C", "", 4)) == "c'"

    def test_c5_double_prime(self):
        assert _pitch_to_lily(Pitch("C", "", 5)) == "c''"

    def test_c3_no_marks(self):
        assert _pitch_to_lily(Pitch("C", "", 3)) == "c"

    def test_c2_comma(self):
        assert _pitch_to_lily(Pitch("C", "", 2)) == "c,"

    def test_c1_double_comma(self):
        assert _pitch_to_lily(Pitch("C", "", 1)) == "c,,"

    def test_sharp(self):
        assert _pitch_to_lily(Pitch("F", "#", 4)) == "fis'"

    def test_flat_e(self):
        # Eb → ees (special case)
        assert _pitch_to_lily(Pitch("E", "b", 4)) == "ees'"

    def test_flat_a(self):
        # Ab → aes (special case)
        assert _pitch_to_lily(Pitch("A", "b", 4)) == "aes'"

    def test_flat_b(self):
        # Bb → bes (special case)
        assert _pitch_to_lily(Pitch("B", "b", 4)) == "bes'"

    def test_flat_d(self):
        # Db → des (regular es suffix)
        assert _pitch_to_lily(Pitch("D", "b", 4)) == "des'"

    def test_double_sharp(self):
        assert _pitch_to_lily(Pitch("G", "##", 4)) == "gisis'"


# ---------------------------------------------------------------------------
# Unit tests for duration encoding
# ---------------------------------------------------------------------------

class TestDurationEncoding:
    def test_whole(self):
        assert _duration_to_lily(Duration(DurationValue.WHOLE)) == "1"

    def test_half(self):
        assert _duration_to_lily(Duration(DurationValue.HALF)) == "2"

    def test_quarter(self):
        assert _duration_to_lily(Duration(DurationValue.QUARTER)) == "4"

    def test_eighth(self):
        assert _duration_to_lily(Duration(DurationValue.EIGHTH)) == "8"

    def test_sixteenth(self):
        assert _duration_to_lily(Duration(DurationValue.SIXTEENTH)) == "16"

    def test_dotted_quarter(self):
        assert _duration_to_lily(Duration(DurationValue.DOTTED_QUARTER)) == "4."

    def test_dotted_half(self):
        assert _duration_to_lily(Duration(DurationValue.DOTTED_HALF)) == "2."

    def test_dotted_eighth(self):
        assert _duration_to_lily(Duration(DurationValue.DOTTED_EIGHTH)) == "8."

    def test_dotted_whole(self):
        assert _duration_to_lily(Duration(DurationValue.DOTTED_WHOLE)) == "1."


# ---------------------------------------------------------------------------
# Unit tests for key signature encoding
# ---------------------------------------------------------------------------

class TestKeySignatureEncoding:
    @pytest.mark.parametrize("root,mode,expected", [
        ("C",  "major", r"\key c \major"),
        ("G",  "major", r"\key g \major"),
        ("D",  "major", r"\key d \major"),
        ("A",  "major", r"\key a \major"),
        ("E",  "major", r"\key e \major"),
        ("B",  "major", r"\key b \major"),
        ("F#", "major", r"\key fis \major"),
        ("C#", "major", r"\key cis \major"),
        ("F",  "major", r"\key f \major"),
        ("Bb", "major", r"\key bes \major"),
        ("Eb", "major", r"\key ees \major"),
        ("Ab", "major", r"\key aes \major"),
        ("Db", "major", r"\key des \major"),
        ("Gb", "major", r"\key ges \major"),
        ("Cb", "major", r"\key ces \major"),
        ("A",  "minor", r"\key a \minor"),
        ("E",  "minor", r"\key e \minor"),
        ("D",  "minor", r"\key d \minor"),
    ])
    def test_key_mapping(self, root, mode, expected):
        ks = KeySignature(root, mode)
        assert _key_to_lily(ks) == expected


# ---------------------------------------------------------------------------
# Test 1: C major scale exports valid LilyPond syntax
# ---------------------------------------------------------------------------

def test_c_major_scale_exports_valid_lilypond(tmp_path):
    score = _c_major_scale_score()
    content = _export_and_read(score, tmp_path)

    assert r'\version "2.24.0"' in content
    assert r'\header' in content
    assert r'\score' in content
    assert r'\layout' in content
    assert r'\midi' in content
    # C major notes should appear
    assert "c'" in content
    assert "d'" in content
    assert "e'" in content
    # Bar check markers
    assert "|" in content


# ---------------------------------------------------------------------------
# Test 2: Multi-part score has multiple staves
# ---------------------------------------------------------------------------

def test_multi_part_score_has_multiple_staves(tmp_path):
    score = Score(
        title="Multi Part",
        composer="Tester",
        tempo=Tempo(100),
        key_signature=KeySignature("C", "major"),
        time_signature=TimeSignature(4, 4),
    )
    violin = score.new_part("Violin")
    violin.add_notes(["C4", "E4", "G4", "C5"], duration="quarter")

    bass = score.new_part("Guitarrón")
    bass.add_notes(["C3", "G3", "E3", "C2"], duration="quarter")

    content = _export_and_read(score, tmp_path)

    # Should have two Staff blocks
    assert content.count(r"\new Staff") == 2
    assert "Violin" in content
    assert "Guitarrón" in content


# ---------------------------------------------------------------------------
# Test 3: Key signature mapping
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("root,mode,lily_key", [
    ("C",  "major", r"\key c \major"),
    ("G",  "major", r"\key g \major"),
    ("F",  "major", r"\key f \major"),
    ("Bb", "major", r"\key bes \major"),
    ("Eb", "major", r"\key ees \major"),
    ("D",  "major", r"\key d \major"),
    ("A",  "major", r"\key a \major"),
])
def test_key_signature_in_output(tmp_path, root, mode, lily_key):
    score = Score(
        title="Key Test",
        key_signature=KeySignature(root, mode),
        time_signature=TimeSignature(4, 4),
    )
    part = score.new_part("Violin")
    part.add_notes(["C4", "D4", "E4", "F4"], duration="quarter")
    content = _export_and_read(score, tmp_path / f"key_{root}_{mode}.ly")
    assert lily_key in content


# ---------------------------------------------------------------------------
# Test 4: Time signatures
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("beats,unit", [
    (4, 4),
    (3, 4),
    (6, 8),
])
def test_time_signature_in_output(tmp_path, beats, unit):
    ts = TimeSignature(beats, unit)
    score = Score(
        title="Time Sig Test",
        time_signature=ts,
    )
    part = score.new_part("Violin")
    # add enough notes to fill the measure
    beat_count = ts.beats_per_measure_in_quarters
    per_note = 0.5  # eighth notes
    n = int(beat_count / per_note)
    pitches = (["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"] * 4)[:n]
    part.add_notes(pitches, duration="eighth")

    content = _export_and_read(score, tmp_path / f"ts_{beats}_{unit}.ly")
    assert rf"\time {beats}/{unit}" in content


# ---------------------------------------------------------------------------
# Test 5: Dotted notes export correctly
# ---------------------------------------------------------------------------

def test_dotted_notes_export(tmp_path):
    score = Score(title="Dotted Note Test", time_signature=TimeSignature(3, 4))
    part = score.new_part("Violin")
    m = part.new_measure()
    m.add(Note(Pitch("C", "", 4), Duration(DurationValue.DOTTED_HALF)), strict=False)

    content = _export_and_read(score, tmp_path)
    assert "2." in content   # dotted half = 2.


def test_dotted_quarter_export(tmp_path):
    score = Score(title="Dotted Quarter Test", time_signature=TimeSignature(4, 4))
    part = score.new_part("Violin")
    m = part.new_measure()
    m.add(Note(Pitch("G", "", 4), Duration(DurationValue.DOTTED_QUARTER)), strict=False)
    m.add(Note(Pitch("A", "", 4), Duration(DurationValue.EIGHTH)), strict=False)
    m.add(Note(Pitch("B", "", 4), Duration(DurationValue.DOTTED_QUARTER)), strict=False)
    m.add(Note(Pitch("C", "", 5), Duration(DurationValue.EIGHTH)), strict=False)

    content = _export_and_read(score, tmp_path)
    assert "4." in content


# ---------------------------------------------------------------------------
# Test 6: Rests export correctly
# ---------------------------------------------------------------------------

def test_rests_export(tmp_path):
    score = Score(title="Rest Test", time_signature=TimeSignature(4, 4))
    part = score.new_part("Violin")
    m = part.new_measure()
    m.add(Note(Pitch("C", "", 4), Duration(DurationValue.QUARTER)), strict=False)
    m.add(Rest(Duration(DurationValue.QUARTER)), strict=False)
    m.add(Rest(Duration(DurationValue.HALF)), strict=False)

    content = _export_and_read(score, tmp_path)
    assert "r4" in content   # quarter rest
    assert "r2" in content   # half rest


def test_whole_rest_export(tmp_path):
    score = Score(title="Whole Rest", time_signature=TimeSignature(4, 4))
    part = score.new_part("Violin")
    m = part.new_measure()
    m.add(Rest(Duration(DurationValue.WHOLE)), strict=False)

    content = _export_and_read(score, tmp_path)
    assert "r1" in content


# ---------------------------------------------------------------------------
# Test 7: Bass clef instruments get \clef "bass"
# ---------------------------------------------------------------------------

def test_bass_clef_instrument(tmp_path):
    score = Score(title="Bass Clef Test", time_signature=TimeSignature(4, 4))
    part = score.new_part("Guitarrón")
    part.add_notes(["C2", "D2", "E2", "F2"], duration="quarter")

    content = _export_and_read(score, tmp_path)
    assert r'\clef "bass"' in content


def test_treble_clef_instrument(tmp_path):
    score = Score(title="Treble Clef Test", time_signature=TimeSignature(4, 4))
    part = score.new_part("Violin")
    part.add_notes(["C4", "D4", "E4", "F4"], duration="quarter")

    content = _export_and_read(score, tmp_path)
    assert r'\clef "treble"' in content


# ---------------------------------------------------------------------------
# Test 8: Title and composer appear in \header
# ---------------------------------------------------------------------------

def test_title_and_composer_in_header(tmp_path):
    score = Score(
        title="La Negra",
        composer="Silvestre Vargas",
        time_signature=TimeSignature(3, 4),
    )
    part = score.new_part("Violin")
    part.add_notes(["C4", "E4", "G4"], duration="quarter")

    content = _export_and_read(score, tmp_path)

    assert r'\header' in content
    assert 'title = "La Negra"' in content
    assert 'composer = "Silvestre Vargas"' in content
    assert 'tagline = ""' in content


def test_title_only_no_composer_key(tmp_path):
    """When composer is empty, the composer line should be omitted."""
    score = Score(title="Anonymous Piece", composer="", time_signature=TimeSignature(4, 4))
    part = score.new_part("Violin")
    part.add_notes(["C4", "D4", "E4", "F4"], duration="quarter")

    content = _export_and_read(score, tmp_path)
    assert 'title = "Anonymous Piece"' in content
    assert "composer" not in content


# ---------------------------------------------------------------------------
# Test 9: Tempo marking appears in \midi block
# ---------------------------------------------------------------------------

def test_tempo_in_midi_block(tmp_path):
    score = Score(title="Tempo Test", tempo=Tempo(144))
    part = score.new_part("Violin")
    part.add_notes(["C4", "D4", "E4", "F4"], duration="quarter")

    content = _export_and_read(score, tmp_path)
    assert r"\tempo 4 = 144" in content


# ---------------------------------------------------------------------------
# Test 10: score.export_lilypond() convenience method
# ---------------------------------------------------------------------------

def test_score_export_lilypond_method(tmp_path):
    score = _c_major_scale_score("Method Test")
    out = score.export_lilypond(tmp_path / "method_test.ly")
    assert out.exists()
    assert out.suffix == ".ly"
    content = out.read_text(encoding="utf-8")
    assert r'\version "2.24.0"' in content


# ---------------------------------------------------------------------------
# Test 11: Transposing instrument wrapping (Trumpet, -2 semitones)
# ---------------------------------------------------------------------------

def test_transposing_instrument_has_transpose_block(tmp_path):
    score = Score(title="Trumpet Test", time_signature=TimeSignature(4, 4))
    part = score.new_part("Trumpet")
    part.add_notes(["C5", "D5", "E5", "F5"], duration="quarter")

    content = _export_and_read(score, tmp_path)
    assert r"\transpose" in content


# ---------------------------------------------------------------------------
# Test 12: render_lilypond_pdf returns None when lilypond is not available
# ---------------------------------------------------------------------------

def test_render_pdf_returns_none_when_not_installed(tmp_path, monkeypatch):
    """If lilypond binary is not present, render_lilypond_pdf must return None."""
    import shutil as _shutil
    monkeypatch.setattr(_shutil, "which", lambda _: None)

    dummy = tmp_path / "dummy.ly"
    dummy.write_text(r'\version "2.24.0"' + "\n", encoding="utf-8")
    result = render_lilypond_pdf(dummy)
    assert result is None


# ---------------------------------------------------------------------------
# Test 13: Bar check markers present for each measure
# ---------------------------------------------------------------------------

def test_bar_check_markers(tmp_path):
    """Each measure should produce at least one | bar-check token."""
    score = Score(title="Bar Check", time_signature=TimeSignature(4, 4))
    part = score.new_part("Violin")
    # 8 quarter notes → 2 measures of 4/4
    part.add_notes(["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"], duration="quarter")

    content = _export_and_read(score, tmp_path)
    bar_count = content.count("|")
    assert bar_count >= 2


# ---------------------------------------------------------------------------
# Test 14: Output file path has .ly suffix added automatically
# ---------------------------------------------------------------------------

def test_output_path_gets_ly_suffix(tmp_path):
    score = _c_major_scale_score()
    # Pass a path without .ly extension
    out = export_score_lilypond(score, tmp_path / "no_extension")
    assert out.suffix == ".ly"
    assert out.exists()


# ---------------------------------------------------------------------------
# Test 15: Empty score (no parts) produces valid skeleton
# ---------------------------------------------------------------------------

def test_empty_score_produces_valid_skeleton(tmp_path):
    score = Score(title="Empty", composer="Nobody")
    content = _export_and_read(score, tmp_path)
    assert r'\version "2.24.0"' in content
    assert r'\header' in content
    assert r'\score' in content
