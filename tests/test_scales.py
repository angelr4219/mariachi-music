"""Tests for scale generation."""

import pytest
from mariachi_music.theory.scales import Scale, ScaleMode
from mariachi_music.theory.keys import Key
from mariachi_music.generation.scale_generator import generate_scale_score


def test_c_major_pitch_strings():
    scale = Scale.parse("C", "major", octave=4)
    pitches = scale.pitch_strings()
    assert pitches == ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]

def test_g_major_pitch_strings():
    scale = Scale.parse("G", "major", octave=4)
    pitches = scale.pitch_strings()
    assert pitches[0] == "G4"
    assert pitches[-1] == "G5"
    assert "F#4" in pitches or "F#5" in pitches

def test_a_minor_pitch_strings():
    scale = Scale.parse("A", "minor", octave=4)
    pitches = scale.pitch_strings()
    assert pitches[0] == "A4"
    assert pitches[-1] == "A5"

def test_descending_scale():
    scale = Scale.parse("C", "major", octave=4)
    asc = scale.pitch_strings(ascending=True)
    desc = scale.pitch_strings(ascending=False)
    assert desc == list(reversed(asc))

def test_scale_note_count():
    # Major scale has 7 notes + octave = 8
    scale = Scale.parse("D", "major", octave=3)
    assert len(scale.pitches()) == 8

def test_generate_scale_score_returns_score():
    score = generate_scale_score(key="C", mode="major", duration="quarter",
                                  time_signature="4/4", tempo=120, instrument="Violin")
    assert score.part_count == 1
    notes = score.parts[0].all_notes
    assert len(notes) == 8  # C D E F G A B C

def test_generate_scale_score_3_4():
    score = generate_scale_score(key="G", mode="major", duration="quarter",
                                  time_signature="3/4", instrument="Trumpet")
    # 8 quarter notes in 3/4 → ceil(8/3) = 3 measures
    assert len(score.parts[0].measures) >= 2

def test_generate_scale_score_note_names():
    score = generate_scale_score(key="C", mode="major", duration="quarter",
                                  time_signature="4/4", instrument="Violin")
    pitches = [str(n.pitch) for n in score.parts[0].all_notes]
    assert pitches == ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]

def test_f_major_has_bb():
    scale = Scale.parse("F", "major", octave=4)
    pitches = scale.pitch_strings()
    assert "Bb4" in pitches
