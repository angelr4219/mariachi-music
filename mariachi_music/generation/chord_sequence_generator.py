"""Generate simple written chord progressions as real simultaneous notes."""

from __future__ import annotations

from dataclasses import dataclass

from mariachi_music.core.instrument import Instrument
from mariachi_music.core.key_signature import KeySignature
from mariachi_music.core.part import Part
from mariachi_music.core.score import Score
from mariachi_music.core.tempo import Tempo
from mariachi_music.core.time_signature import TimeSignature
from mariachi_music.theory.chords import Chord, chord_by_root


_ROOTS = ("C#", "Db", "D#", "Eb", "F#", "Gb", "G#", "Ab", "A#", "Bb", "C", "D", "E", "F", "G", "A", "B")
_QUALITY_ALIASES = {
    "": "major",
    "maj": "major",
    "major": "major",
    "m": "minor",
    "min": "minor",
    "minor": "minor",
    "dim": "diminished",
    "aug": "augmented",
    "7": "dominant7",
    "dom7": "dominant7",
    "maj7": "major7",
    "m7": "minor7",
    "min7": "minor7",
}


@dataclass(frozen=True)
class WrittenChord:
    """A parsed chord symbol and its concrete pitch spellings."""

    symbol: str
    chord: Chord
    pitches: tuple[str, ...]


def _normalise_root(root: str) -> str:
    root = root.strip()
    if not root:
        raise ValueError("Missing chord root.")
    return root[0].upper() + root[1:]


def parse_chord_symbol(symbol: str, octave: int = 4) -> WrittenChord:
    """Parse chord symbols like G, Am, D7, Bbmaj7 into written pitches."""
    raw = symbol.strip()
    if not raw:
        raise ValueError("Empty chord symbol.")

    root = ""
    suffix = ""
    for candidate in _ROOTS:
        if raw.lower().startswith(candidate.lower()):
            root = _normalise_root(raw[:len(candidate)])
            suffix = raw[len(candidate):].strip().lower()
            break
    if not root:
        raise ValueError(f"Could not parse chord root from {symbol!r}.")

    quality = _QUALITY_ALIASES.get(suffix)
    if quality is None:
        valid = ", ".join(sorted(k or "major/no suffix" for k in _QUALITY_ALIASES))
        raise ValueError(f"Unknown chord quality {suffix!r} in {symbol!r}. Valid: {valid}.")

    chord = chord_by_root(root, quality)
    pitches = tuple(str(pitch) for pitch in chord.pitches_at_octave(octave))
    return WrittenChord(symbol=raw, chord=chord, pitches=pitches)


def parse_chord_sequence(text: str, octave: int = 4) -> list[WrittenChord]:
    """Parse comma or space separated chord symbols."""
    symbols = [item.strip() for chunk in text.split(",") for item in chunk.split()]
    return [parse_chord_symbol(symbol, octave=octave) for symbol in symbols if symbol]


def generate_chord_sequence_score(
    chords: str | list[str],
    key: str = "C",
    mode: str = "major",
    octave: int = 4,
    duration: str = "quarter",
    time_signature: str = "4/4",
    tempo: float = 120.0,
    instrument: str = "Piano",
    title: str = "",
    composer: str = "",
) -> Score:
    """Generate a one-part score from chord symbols.

    Example:
        ``G, A, D, C`` becomes ``G-B-D``, ``A-C#-E``, ``D-F#-A``, ``C-E-G``.
    """
    chord_text = ", ".join(chords) if isinstance(chords, list) else chords
    written = parse_chord_sequence(chord_text, octave=octave)
    if not written:
        raise ValueError("No chord symbols were provided.")

    ts = TimeSignature.parse(time_signature)
    score = Score(
        title=title or f"Chord Sequence: {', '.join(item.symbol for item in written)}",
        composer=composer,
        tempo=Tempo(tempo),
        key_signature=KeySignature(key, mode),
        time_signature=ts,
    )

    part = Part(instrument=Instrument.by_name(instrument), default_ts=ts)
    for item in written:
        part.add_chord(list(item.pitches), duration)
    score.add_part(part)
    return score
