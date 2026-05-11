"""Generate a complete Score containing a scale for a given instrument."""

from __future__ import annotations

from mariachi_music.core.instrument import Instrument, INSTRUMENTS
from mariachi_music.core.key_signature import KeySignature
from mariachi_music.core.part import Part
from mariachi_music.core.score import Score
from mariachi_music.core.tempo import Tempo
from mariachi_music.core.time_signature import TimeSignature
from mariachi_music.theory.scales import Scale, ScaleMode


def generate_scale_score(
    key: str = "C",
    mode: str = "major",
    octave: int = 4,
    duration: str = "quarter",
    time_signature: str = "4/4",
    tempo: float = 120.0,
    instrument: str | Instrument = "Violin",
    ascending: bool = True,
    title: str = "",
    composer: str = "",
) -> Score:
    """Build a Score containing one instrument part playing a scale.

    Args:
        key:            Root note of the scale ('C', 'G', 'Bb', etc.).
        mode:           Scale mode ('major', 'minor', 'chromatic', etc.).
        octave:         Starting octave for the scale (default 4 = middle C area).
        duration:       Note duration string ('whole', 'half', 'quarter', 'eighth').
        time_signature: Meter string like '4/4', '3/4', '6/8'.
        tempo:          Beats per minute.
        instrument:     Instrument name string or Instrument object.
        ascending:      True for ascending scale, False for descending.
        title:          Score title (auto-generated if empty).
        composer:       Composer name.

    Returns:
        A Score ready to export as MusicXML or MIDI.

    Example::

        score = generate_scale_score(key='C', mode='major', duration='quarter',
                                     instrument='Violin')
        score.export_musicxml('outputs/c_major_scale.musicxml')
    """
    if isinstance(instrument, str):
        instrument = Instrument.by_name(instrument)

    ts = TimeSignature.parse(time_signature)
    tp = Tempo(bpm=tempo)
    ks = KeySignature(root=key, mode=mode)

    direction = "Ascending" if ascending else "Descending"
    auto_title = title or f"{key} {mode.capitalize()} Scale — {instrument.name} ({direction})"

    score = Score(
        title=auto_title,
        composer=composer,
        tempo=tp,
        key_signature=ks,
        time_signature=ts,
    )

    scale = Scale.parse(root=key, mode=mode, octave=octave)
    pitch_strings = scale.pitch_strings(ascending=ascending)

    part = Part(instrument=instrument, default_ts=ts)
    part.add_notes(pitch_strings, duration=duration)
    score.add_part(part)

    return score
