"""Tests for the core music engine."""

import pytest

from mariachi_music.core.pitch import Pitch
from mariachi_music.core.duration import Duration, DurationValue
from mariachi_music.core.note import Note, Rest
from mariachi_music.core.measure import Measure
from mariachi_music.core.time_signature import TimeSignature
from mariachi_music.core.key_signature import KeySignature
from mariachi_music.core.tempo import Tempo
from mariachi_music.core.instrument import Instrument, INSTRUMENTS
from mariachi_music.core.part import Part
from mariachi_music.core.score import Score


# ── Pitch ────────────────────────────────────────────────────────────────────

def test_pitch_parse_simple():
    p = Pitch.parse("C4")
    assert p.name == "C"
    assert p.accidental == ""
    assert p.octave == 4

def test_pitch_parse_sharp():
    p = Pitch.parse("F#5")
    assert p.name == "F"
    assert p.accidental == "#"
    assert p.octave == 5

def test_pitch_parse_flat():
    p = Pitch.parse("Bb3")
    assert p.name == "B"
    assert p.accidental == "b"
    assert p.octave == 3

def test_pitch_midi_c4():
    assert Pitch.parse("C4").midi_number == 60

def test_pitch_midi_a4():
    assert Pitch.parse("A4").midi_number == 69

def test_pitch_invalid_name():
    with pytest.raises(ValueError):
        Pitch("H", "", 4)

def test_pitch_from_midi():
    p = Pitch.from_midi(60)
    assert p.midi_number == 60

def test_pitch_str():
    assert str(Pitch.parse("C#4")) == "C#4"

def test_pitch_invalid_parse():
    with pytest.raises(ValueError):
        Pitch.parse("X99")


# ── Duration ─────────────────────────────────────────────────────────────────

def test_duration_quarter_beats():
    assert Duration.parse("quarter").beats == 1.0

def test_duration_half_beats():
    assert Duration.parse("half").beats == 2.0

def test_duration_whole_beats():
    assert Duration.parse("whole").beats == 4.0

def test_duration_eighth_beats():
    assert Duration.parse("eighth").beats == 0.5

def test_duration_dotted_quarter():
    assert Duration.parse("dotted_quarter").beats == 1.5

def test_duration_shorthand_q():
    assert Duration.parse("q").beats == 1.0

def test_duration_invalid():
    with pytest.raises(ValueError):
        Duration.parse("foobar")

def test_duration_divisions():
    assert Duration.parse("quarter").divisions == 24
    assert Duration.parse("half").divisions == 48
    assert Duration.parse("whole").divisions == 96


# ── Note and Rest ─────────────────────────────────────────────────────────────

def test_note_from_str():
    n = Note.from_str("C4", "quarter")
    assert n.pitch.midi_number == 60
    assert n.duration.beats == 1.0

def test_note_beats():
    assert Note.from_str("G4", "half").beats == 2.0

def test_note_velocity_default():
    assert Note.from_str("A4", "eighth").velocity == 90

def test_rest_from_str():
    r = Rest.from_str("quarter")
    assert r.beats == 1.0

def test_note_invalid_velocity():
    with pytest.raises(ValueError):
        Note(pitch=Pitch.parse("C4"), duration=Duration.parse("quarter"), velocity=200)


# ── Measure ───────────────────────────────────────────────────────────────────

def test_measure_capacity_4_4():
    m = Measure(time_signature=TimeSignature(4, 4))
    assert m.capacity_beats == 4.0

def test_measure_capacity_3_4():
    m = Measure(time_signature=TimeSignature(3, 4))
    assert m.capacity_beats == 3.0

def test_measure_capacity_6_8():
    m = Measure(time_signature=TimeSignature(6, 8))
    assert m.capacity_beats == 3.0  # 6 * (4/8) = 3 quarter beats

def test_measure_add_notes():
    m = Measure(time_signature=TimeSignature(4, 4))
    m.add(Note.from_str("C4", "quarter"))
    m.add(Note.from_str("D4", "quarter"))
    assert m.used_beats == 2.0

def test_measure_overflow_raises():
    m = Measure(time_signature=TimeSignature(4, 4))
    m.add(Note.from_str("C4", "whole"))
    with pytest.raises(OverflowError):
        m.add(Note.from_str("D4", "quarter"))

def test_measure_full_after_4_quarters():
    m = Measure(time_signature=TimeSignature(4, 4))
    for pitch in ["C4", "D4", "E4", "F4"]:
        m.add_note(pitch, "quarter")
    assert m.is_full


# ── TimeSignature ─────────────────────────────────────────────────────────────

def test_time_signature_parse():
    ts = TimeSignature.parse("4/4")
    assert ts.beats_per_measure == 4
    assert ts.beat_unit == 4

def test_time_signature_str():
    assert str(TimeSignature(3, 4)) == "3/4"

def test_time_signature_invalid():
    with pytest.raises(ValueError):
        TimeSignature.parse("5/7")


# ── KeySignature ──────────────────────────────────────────────────────────────

def test_key_c_major_fifths():
    ks = KeySignature("C", "major")
    assert ks.fifths == 0

def test_key_g_major_fifths():
    assert KeySignature("G", "major").fifths == 1

def test_key_f_major_fifths():
    assert KeySignature("F", "major").fifths == -1

def test_key_a_minor_fifths():
    assert KeySignature("A", "minor").fifths == 0  # relative of C major

def test_key_str():
    assert str(KeySignature("G", "major")) == "G major"


# ── Tempo ─────────────────────────────────────────────────────────────────────

def test_tempo_beat_duration():
    t = Tempo(120)
    assert t.beat_duration_sec == pytest.approx(0.5)

def test_tempo_microseconds():
    t = Tempo(120)
    assert t.microseconds_per_beat == 500_000

def test_tempo_invalid():
    with pytest.raises(ValueError):
        Tempo(-10)


# ── Instrument ────────────────────────────────────────────────────────────────

def test_instrument_by_name():
    v = Instrument.by_name("Violin")
    assert v.clef == "treble"
    assert v.midi_program == 40

def test_instrument_guitarron_clef():
    g = Instrument.by_name("Guitarrón")
    assert g.clef == "bass"

def test_instrument_unknown():
    with pytest.raises(ValueError):
        Instrument.by_name("Kazoo")


# ── Part ─────────────────────────────────────────────────────────────────────

def test_part_add_notes_auto_measures():
    inst = Instrument.by_name("Violin")
    part = Part(instrument=inst, default_ts=TimeSignature(4, 4))
    # 8 quarter notes should fill 2 measures of 4/4
    part.add_notes(["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"], duration="quarter")
    assert len(part.measures) == 2

def test_part_all_notes_count():
    inst = Instrument.by_name("Trumpet")
    part = Part(instrument=inst)
    part.add_notes(["C4", "D4", "E4"], duration="quarter")
    assert len(part.all_notes) == 3


# ── Score ─────────────────────────────────────────────────────────────────────

def test_score_basic():
    score = Score(title="Test", composer="Angel")
    assert score.title == "Test"
    assert score.part_count == 0

def test_score_add_part():
    score = Score()
    part = score.new_part("Violin")
    part.add_notes(["C4", "D4", "E4", "F4"], duration="quarter")
    assert score.part_count == 1
    assert len(score.parts[0].all_notes) == 4

def test_score_note_table():
    score = Score()
    part = score.new_part("Violin")
    part.add_notes(["C4", "D4"], duration="quarter")
    table = score.note_table()
    assert len(table) == 2
    assert table[0]["pitch"] == "C4"
    assert table[1]["pitch"] == "D4"

def test_score_multi_part():
    score = Score()
    v = score.new_part("Violin")
    v.add_notes(["C4", "D4", "E4", "F4"], duration="quarter")
    t = score.new_part("Trumpet")
    t.add_notes(["G4", "A4", "B4", "C5"], duration="quarter")
    assert score.part_count == 2
