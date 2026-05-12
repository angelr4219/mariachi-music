from pathlib import Path

import pretty_midi

from mariachi_music.generation.chord_sequence_generator import (
    generate_chord_sequence_score,
    parse_chord_sequence,
)


def test_parse_major_chord_sequence_defaults_to_major():
    chords = parse_chord_sequence("g, a, d, c", octave=4)

    assert [item.symbol for item in chords] == ["g", "a", "d", "c"]
    assert chords[0].pitches == ("G4", "B4", "D5")
    assert chords[1].pitches == ("A4", "C#5", "E5")
    assert chords[2].pitches == ("D4", "F#4", "A4")
    assert chords[3].pitches == ("C4", "E4", "G4")


def test_chord_sequence_score_uses_simultaneous_chord_tones():
    score = generate_chord_sequence_score(
        "G, A, D, C",
        octave=4,
        duration="quarter",
        time_signature="4/4",
        instrument="Piano",
    )

    measure = score.parts[0].measures[0]
    assert measure.used_beats == 4
    assert [event.chord for event in measure.events[:6]] == [False, True, True, False, True, True]
    assert score.note_table()[1]["beat"] == 1
    assert score.note_table()[1]["type"] == "chord tone"


def test_chord_sequence_exports_musicxml_and_midi(tmp_path: Path):
    score = generate_chord_sequence_score("G, A", octave=4, instrument="Piano")

    xml_path = score.export_musicxml(tmp_path / "chords.musicxml")
    midi_path = score.export_midi(tmp_path / "chords.mid")

    assert "<chord/>" in xml_path.read_text()

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    starts = sorted(round(note.start, 6) for note in midi.instruments[0].notes[:3])
    assert starts == [0.0, 0.0, 0.0]
