"""MIDI exporter for Score objects using pretty_midi."""

from __future__ import annotations

from pathlib import Path

import pretty_midi

from mariachi_music.core.note import Note, Rest
from mariachi_music.core.score import Score


def export_score_midi(score: Score, path: Path) -> Path:
    """Export a Score to a Standard MIDI File.

    Each Part becomes a separate MIDI track/instrument.

    Args:
        score: The Score to export.
        path:  Output file path (should end in .mid).

    Returns:
        The path that was written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    midi = pretty_midi.PrettyMIDI(initial_tempo=float(score.tempo.bpm))

    for part in score.parts:
        instrument = pretty_midi.Instrument(
            program=part.instrument.midi_program,
            is_drum=False,
            name=part.instrument.name,
        )

        cursor_sec = 0.0
        for measure in part.measures:
            for event in measure.events:
                duration_sec = score.tempo.duration_sec(event.beats)
                if isinstance(event, Note):
                    midi_num = event.pitch.midi_number
                    midi_num = max(0, min(127, midi_num))
                    pm_note = pretty_midi.Note(
                        velocity=event.velocity,
                        pitch=midi_num,
                        start=cursor_sec,
                        end=cursor_sec + duration_sec,
                    )
                    instrument.notes.append(pm_note)
                cursor_sec += duration_sec

        midi.instruments.append(instrument)

    midi.write(str(path))
    return path
