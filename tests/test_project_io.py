from pathlib import Path

from mariachi_music.core.instrument import Instrument
from mariachi_music.core.part import Part
from mariachi_music.core.project_io import load_score_project, save_score_project
from mariachi_music.core.score import Score


def test_project_round_trip_preserves_parts_notes_and_chords(tmp_path: Path):
    score = Score(title="Project Test", composer="Angel")

    bass = Part(Instrument.by_name("Generic Bass"))
    bass.add_notes(["C2", "G2"], "quarter")
    score.add_part(bass)

    guitar = Part(Instrument.by_name("Guitar"))
    guitar.add_chord(["G3", "B3", "D4"], "half")
    score.add_part(guitar)

    path = save_score_project(score, tmp_path / "song.mariachi.json")
    loaded = load_score_project(path)

    assert loaded.title == "Project Test"
    assert [part.instrument.name for part in loaded.parts] == ["Generic Bass", "Guitar"]
    assert [str(note.pitch) for note in loaded.parts[0].all_notes] == ["C2", "G2"]

    chord_events = loaded.parts[1].measures[0].events
    assert [str(event.pitch) for event in chord_events] == ["G3", "B3", "D4"]
    assert [event.chord for event in chord_events] == [False, True, True]
    assert loaded.parts[1].measures[0].used_beats == 2
