"""Chord voicing generator — per-instrument rhythmic patterns for a given chord.

Each instrument in mariachi plays a chord differently:

  Guitarrón   Bass role   — plays chord tones on each beat (root, 3rd, 5th)
                            or root + 5th / root + octave depending on pattern
  Vihuela     Rhythm role — strums the full chord (represented as root repeated)
  Guitar      Rhythm role — strums the full chord (same as vihuela)
  Violin      Melody role — plays chord tones as a melodic figure
  Trumpet     Melody role — plays chord tones as a melodic figure

The output is always a Score so it can be exported directly as MusicXML or MIDI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from mariachi_music.core.instrument import Instrument, INSTRUMENTS
from mariachi_music.core.key_signature import KeySignature
from mariachi_music.core.part import Part
from mariachi_music.core.pitch import Pitch
from mariachi_music.core.score import Score
from mariachi_music.core.tempo import Tempo
from mariachi_music.core.time_signature import TimeSignature
from mariachi_music.theory.chords import Chord, chord_by_root, chords_in_key


# ──────────────────────────────────────────────────────────────────────────────
# Voicing patterns
# ──────────────────────────────────────────────────────────────────────────────

def _guitarron_pattern(chord: Chord, time_sig: TimeSignature, octave: int = 2) -> list[str]:
    """Guitarrón: plays chord tones one per beat (bass arpeggiation).

    In 3/4: root (beat 1) → 3rd (beat 2) → 5th (beat 3)
    In 4/4: root → 5th → root → 5th  (bass walking)
    In 6/8: root → root → 5th → root → root → 5th
    """
    tones = chord.pitches_at_octave(octave)
    beats = time_sig.beats_per_measure

    if beats == 3:
        # Classic waltz / son: R – 3 – 5
        pattern = [str(tones[i % len(tones)]) for i in range(3)]
    elif beats == 4:
        # R – 5 – R – 5
        root = str(tones[0])
        fifth = str(tones[2]) if len(tones) >= 3 else root
        pattern = [root, fifth, root, fifth]
    elif beats == 6:
        # 6/8 fast waltz: R R 5 R R 5
        root = str(tones[0])
        fifth = str(tones[2]) if len(tones) >= 3 else root
        pattern = [root, root, fifth, root, root, fifth]
    elif beats == 2:
        root = str(tones[0])
        fifth = str(tones[2]) if len(tones) >= 3 else root
        pattern = [root, fifth]
    else:
        pattern = [str(tones[i % len(tones)]) for i in range(beats)]

    return pattern


def _strum_pattern(chord: Chord, time_sig: TimeSignature, octave: int = 3) -> list[str]:
    """Guitar / Vihuela: strums on every beat.

    Represented as the chord root repeated once per beat.
    In a real score you'd use chord symbols; for now we encode the root
    so MIDI playback at least conveys the rhythm.
    """
    root = chord.pitches_at_octave(octave)[0]
    beats = time_sig.beats_per_measure
    return [str(root)] * beats


def _melody_pattern(chord: Chord, time_sig: TimeSignature, octave: int = 4) -> list[str]:
    """Violin / Trumpet: arpeggiates chord tones upward across the measure."""
    tones = chord.pitches_at_octave(octave)
    beats = time_sig.beats_per_measure
    return [str(tones[i % len(tones)]) for i in range(beats)]


# Map instrument name → (pattern_fn, default_octave)
_PATTERN_MAP: dict[str, tuple[Callable, int]] = {
    "Guitarrón":     (_guitarron_pattern, 2),
    "Bass / Guitarrón": (_guitarron_pattern, 2),
    "Generic Bass":  (_guitarron_pattern, 2),
    "Guitar":        (_strum_pattern,    3),
    "Vihuela":       (_strum_pattern,    3),
    "Violin":        (_melody_pattern,   4),
    "Trumpet":       (_melody_pattern,   4),
    "Voice":         (_melody_pattern,   4),
    "Generic Treble":(_melody_pattern,   4),
}


def _get_pattern(instrument: Instrument, chord: Chord, ts: TimeSignature) -> list[str]:
    """Return the note pattern for one measure of this instrument on this chord."""
    fn, octave = _PATTERN_MAP.get(instrument.name, (_melody_pattern, 4))
    return fn(chord, ts, octave)


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def generate_chord_score(
    chord_root: str,
    chord_quality: str = "major",
    key: str = "C",
    mode: str = "major",
    time_signature: str = "3/4",
    tempo: float = 120.0,
    instruments: list[str] | None = None,
    measures: int = 4,
    duration: str = "quarter",
    title: str = "",
    composer: str = "",
) -> Score:
    """Generate a multi-instrument Score all playing the same chord.

    Each instrument gets its own idiomatic voicing pattern:
      - Guitarrón  → arpeggiated bass (root, 3rd, 5th per beat)
      - Guitar     → strummed root on every beat
      - Vihuela    → strummed root on every beat
      - Violin     → arpeggiated chord tones in upper register
      - Trumpet    → arpeggiated chord tones in upper register

    Args:
        chord_root:    Root of the chord (e.g. 'G').
        chord_quality: Chord quality string ('major', 'minor', 'dominant7', etc.)
        key:           Key signature root (for score metadata, e.g. 'C').
        mode:          Key mode ('major' or 'minor').
        time_signature: Meter string ('3/4', '4/4', '6/8', etc.)
        tempo:         BPM.
        instruments:   List of instrument names (default: Guitarrón, Guitar, Violin).
        measures:      How many measures to generate.
        duration:      Note duration per beat ('quarter' for 3/4 and 4/4, 'eighth' for 6/8).
        title:         Score title (auto-generated if empty).
        composer:      Composer name.

    Returns:
        A Score ready to export.

    Example::

        score = generate_chord_score(
            chord_root='G', chord_quality='major',
            key='C', time_signature='3/4', tempo=120,
            instruments=['Guitarrón', 'Guitar', 'Violin'],
        )
        # Guitarrón: G2 B2 D3 | G2 B2 D3 | ...
        # Guitar:    G3 G3 G3 | G3 G3 G3 | ...
        # Violin:    G4 B4 D5 | G4 B4 D5 | ...
    """
    if instruments is None:
        instruments = ["Guitarrón", "Guitar", "Violin"]

    ts = TimeSignature.parse(time_signature)
    tp = Tempo(bpm=tempo)
    ks = KeySignature(root=key, mode=mode)
    chord = chord_by_root(chord_root, chord_quality)

    auto_title = title or f"{chord.name} chord — {', '.join(instruments)} ({time_signature})"

    score = Score(
        title=auto_title,
        composer=composer,
        tempo=tp,
        key_signature=ks,
        time_signature=ts,
    )

    for inst_name in instruments:
        inst = Instrument.by_name(inst_name)
        part = Part(instrument=inst, default_ts=ts)

        for _ in range(measures):
            pattern = _get_pattern(inst, chord, ts)
            part.add_notes(pattern, duration=duration)

        score.add_part(part)

    return score


def generate_key_chord_progression(
    key_root: str,
    mode: str = "major",
    degrees: list[int] | None = None,
    time_signature: str = "3/4",
    tempo: float = 120.0,
    instruments: list[str] | None = None,
    measures_per_chord: int = 2,
    duration: str = "quarter",
    title: str = "",
    composer: str = "",
) -> Score:
    """Generate a chord progression through scale degrees in a key.

    All instruments play each chord together for `measures_per_chord` measures
    before moving to the next chord.

    Args:
        key_root:          Root of the key (e.g. 'C').
        mode:              'major' or 'minor'.
        degrees:           List of scale degrees 1–7 (default: I–IV–V–I = [1,4,5,1]).
        time_signature:    Meter string.
        tempo:             BPM.
        instruments:       Instrument name list.
        measures_per_chord: How many measures each chord lasts.
        duration:          Note duration per beat.
        title:             Score title.
        composer:          Composer name.

    Example::

        # I–IV–V–I in C major, 3/4 time, Guitarrón + Guitar + Violin
        score = generate_key_chord_progression(
            key_root='C', degrees=[1, 4, 5, 1],
            instruments=['Guitarrón', 'Guitar', 'Violin'],
        )
    """
    if degrees is None:
        degrees = [1, 4, 5, 1]
    if instruments is None:
        instruments = ["Guitarrón", "Guitar", "Violin"]

    ts = TimeSignature.parse(time_signature)
    tp = Tempo(bpm=tempo)
    ks = KeySignature(root=key_root, mode=mode)

    key_chords = chords_in_key(key_root, mode)   # list of (roman, Chord)

    chord_sequence: list[Chord] = []
    roman_sequence: list[str] = []
    for deg in degrees:
        if not 1 <= deg <= 7:
            raise ValueError(f"Degree {deg} out of range 1–7.")
        roman, chord = key_chords[deg - 1]
        chord_sequence.append(chord)
        roman_sequence.append(roman)

    prog_str = " – ".join(roman_sequence)
    auto_title = title or f"{key_root} {mode}: {prog_str} progression ({time_signature})"

    score = Score(
        title=auto_title,
        composer=composer,
        tempo=tp,
        key_signature=ks,
        time_signature=ts,
    )

    for inst_name in instruments:
        inst = Instrument.by_name(inst_name)
        part = Part(instrument=inst, default_ts=ts)

        for chord in chord_sequence:
            for _ in range(measures_per_chord):
                pattern = _get_pattern(inst, chord, ts)
                part.add_notes(pattern, duration=duration)

        score.add_part(part)

    return score
