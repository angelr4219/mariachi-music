"""Tests for chord theory and chord score generation."""

import pytest
from mariachi_music.theory.chords import (
    Chord, ChordQuality, chord_by_root, chord_by_degree, chords_in_key
)
from mariachi_music.generation.chord_generator import (
    generate_chord_score, generate_key_chord_progression
)


# ── Chord building ────────────────────────────────────────────────────────────

def test_g_major_tones():
    c = chord_by_root("G", "major")
    assert c.tones == ("G", "B", "D")

def test_c_major_tones():
    c = chord_by_root("C", "major")
    assert c.tones == ("C", "E", "G")

def test_f_major_tones():
    c = chord_by_root("F", "major")
    assert c.tones == ("F", "A", "C")

def test_d_minor_tones():
    c = chord_by_root("D", "minor")
    assert c.tones == ("D", "F", "A")

def test_b_diminished_tones():
    c = chord_by_root("B", "diminished")
    assert c.tones == ("B", "D", "F")

def test_g7_tones():
    c = chord_by_root("G", "dominant7")
    assert len(c.tones) == 4
    assert c.tones[0] == "G"

def test_chord_name_major():
    assert chord_by_root("G", "major").name == "G"

def test_chord_name_minor():
    assert chord_by_root("A", "minor").name == "Am"

def test_chord_name_dim():
    assert chord_by_root("B", "diminished").name == "Bdim"


# ── Diatonic chords in key ────────────────────────────────────────────────────

def test_c_major_key_has_7_chords():
    chords = chords_in_key("C", "major")
    assert len(chords) == 7

def test_c_major_i_is_c_major():
    roman, chord = chords_in_key("C", "major")[0]
    assert roman == "I"
    assert chord.root == "C"
    assert chord.quality == ChordQuality.MAJOR

def test_c_major_v_is_g_major():
    roman, chord = chords_in_key("C", "major")[4]
    assert roman == "V"
    assert chord.root == "G"
    assert chord.quality == ChordQuality.MAJOR

def test_c_major_ii_is_d_minor():
    roman, chord = chords_in_key("C", "major")[1]
    assert roman == "ii"
    assert chord.root == "D"
    assert chord.quality == ChordQuality.MINOR

def test_c_major_vii_is_b_dim():
    roman, chord = chords_in_key("C", "major")[6]
    assert "°" in roman
    assert chord.quality == ChordQuality.DIMINISHED

def test_chord_by_degree_v_in_c():
    chord = chord_by_degree("C", 5, "major")
    assert chord.root == "G"
    assert chord.quality == ChordQuality.MAJOR

def test_chord_by_degree_iv_in_g():
    chord = chord_by_degree("G", 4, "major")
    assert chord.root == "C"


# ── Pitches at octave ─────────────────────────────────────────────────────────

def test_g_major_pitches_ascending():
    chord = chord_by_root("G", "major")
    pitches = chord.pitches_at_octave(2)
    midis = [p.midi_number for p in pitches]
    assert midis == sorted(midis), "Chord tones should be ascending"

def test_g_major_octave2_root():
    chord = chord_by_root("G", "major")
    pitches = chord.pitches_at_octave(2)
    assert str(pitches[0]) == "G2"


# ── Chord score generation ────────────────────────────────────────────────────

def test_generate_chord_score_g_3_4():
    score = generate_chord_score(
        chord_root="G", chord_quality="major",
        key="C", time_signature="3/4", tempo=120,
        instruments=["Guitarrón", "Guitar", "Violin"],
        measures=2,
    )
    assert score.part_count == 3

def test_guitarron_plays_root_third_fifth_in_3_4():
    score = generate_chord_score(
        chord_root="G", chord_quality="major",
        key="C", time_signature="3/4",
        instruments=["Guitarrón"], measures=1,
    )
    notes = score.parts[0].all_notes
    assert len(notes) == 3   # one per beat in 3/4
    # Root should be G
    assert notes[0].pitch.name == "G"

def test_guitar_plays_root_repeated_in_3_4():
    score = generate_chord_score(
        chord_root="G", chord_quality="major",
        key="C", time_signature="3/4",
        instruments=["Guitar"], measures=1,
    )
    notes = score.parts[0].all_notes
    assert len(notes) == 3
    # All notes should be G (strummed root)
    assert all(n.pitch.name == "G" for n in notes)

def test_guitarron_4_4_has_4_notes():
    score = generate_chord_score(
        chord_root="C", chord_quality="major",
        key="C", time_signature="4/4",
        instruments=["Guitarrón"], measures=1,
    )
    notes = score.parts[0].all_notes
    assert len(notes) == 4

def test_chord_score_multi_measures():
    score = generate_chord_score(
        chord_root="G", chord_quality="major",
        key="C", time_signature="3/4",
        instruments=["Guitarrón"], measures=4,
    )
    assert len(score.parts[0].measures) == 4


# ── Progression generation ────────────────────────────────────────────────────

def test_progression_1_4_5_1_in_c():
    score = generate_key_chord_progression(
        key_root="C", mode="major",
        degrees=[1, 4, 5, 1],
        instruments=["Guitarrón"],
        time_signature="3/4",
        measures_per_chord=1,
    )
    # 4 chords × 3 beats = 12 notes
    notes = score.parts[0].all_notes
    assert len(notes) == 12

def test_progression_chord_roots_correct():
    score = generate_key_chord_progression(
        key_root="C", mode="major",
        degrees=[1, 4, 5],
        instruments=["Guitarrón"],
        time_signature="3/4",
        measures_per_chord=1,
    )
    notes = score.parts[0].all_notes
    # Chord I → root C, Chord IV → root F, Chord V → root G
    assert notes[0].pitch.name == "C"  # I  root
    assert notes[3].pitch.name == "F"  # IV root
    assert notes[6].pitch.name == "G"  # V  root
