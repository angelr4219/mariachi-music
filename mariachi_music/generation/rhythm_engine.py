"""Mariachi rhythm engine — authentic per-style, per-instrument rhythmic patterns.

Supported styles
----------------
son     6/8  compound duple, fast driving feel (100–160 bpm)
bolero  4/4  slow romantic feel (60–90 bpm)
waltz   3/4  the most common mariachi meter (80–120 bpm)
jarabe  6/8  fast festive, more syncopated (140–200 bpm)
cumbia  4/4  cumbia norteña groove (100–130 bpm)

Each style encodes idiomatic note/rest sequences for every instrument in the
standard mariachi band:
    Guitarrón — bass role
    Vihuela   — rhythmic chop role
    Guitar    — harmonic/rhythmic role
    Violin    — melodic role
    Trumpet   — melodic role
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from mariachi_music.core.instrument import Instrument
from mariachi_music.core.key_signature import KeySignature
from mariachi_music.core.note import Note, Rest
from mariachi_music.core.part import Part
from mariachi_music.core.score import Score
from mariachi_music.core.tempo import Tempo
from mariachi_music.core.time_signature import TimeSignature
from mariachi_music.theory.chords import Chord, chord_by_root, chords_in_key

# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

_FULL_MARIACHI_BAND: list[str] = [
    "Guitarrón",
    "Vihuela",
    "Guitar",
    "Violin",
    "Trumpet",
]

# Default tempo (BPM) for each style when the caller passes tempo=None
_DEFAULT_TEMPO: dict[str, float] = {
    "son":    132.0,
    "bolero":  72.0,
    "waltz":  100.0,
    "jarabe": 168.0,
    "cumbia": 116.0,
}

_TYPICAL_TEMPO_RANGE: dict[str, tuple[int, int]] = {
    "son":    (100, 160),
    "bolero": (60,  90),
    "waltz":  (80,  120),
    "jarabe": (140, 200),
    "cumbia": (100, 130),
}

_TIME_SIGNATURE: dict[str, str] = {
    "son":    "6/8",
    "bolero": "4/4",
    "waltz":  "3/4",
    "jarabe": "6/8",
    "cumbia": "4/4",
}


def _pitch_str(chord: Chord, tone_index: int, octave: int) -> str:
    """Return the pitch string for a chord tone, clamped to valid octave range."""
    tones = chord.pitches_at_octave(octave)
    p = tones[tone_index % len(tones)]
    return str(p)


def _root_str(chord: Chord, octave: int) -> str:
    return _pitch_str(chord, 0, octave)


def _third_str(chord: Chord, octave: int) -> str:
    return _pitch_str(chord, 1, octave)


def _fifth_str(chord: Chord, octave: int) -> str:
    return _pitch_str(chord, 2 if len(chord.tones) >= 3 else 0, octave)


# ──────────────────────────────────────────────────────────────────────────────
# Event builder: returns list[tuple[str|None, str]]
#   str|None = pitch (None → rest)
#   str      = duration name
# ──────────────────────────────────────────────────────────────────────────────

EventList = list[tuple[str | None, str]]  # (pitch_str_or_None, duration_str)


def _add_events_to_part(part: Part, events: EventList) -> None:
    """Add a list of (pitch|None, duration) pairs to a part, one event at a time."""
    ts = part.default_ts
    for pitch_str, dur_str in events:
        if not part._measures or part._measures[-1].is_full:
            part.new_measure(ts)
        current = part._measures[-1]
        if pitch_str is None:
            rest = Rest.from_str(dur_str)
            if rest.beats > current.remaining_beats + 1e-9:
                part.new_measure(ts)
                current = part._measures[-1]
            current.add(rest, strict=False)
        else:
            note = Note.from_str(pitch_str, dur_str)
            if note.beats > current.remaining_beats + 1e-9:
                part.new_measure(ts)
                current = part._measures[-1]
            current.add(note, strict=False)


# ──────────────────────────────────────────────────────────────────────────────
# Style × instrument pattern generators
# ──────────────────────────────────────────────────────────────────────────────

# Each generator signature: (chord, octave) -> EventList for ONE measure.
PatternFn = Callable[[Chord, int], EventList]


# ─── SON (6/8) ────────────────────────────────────────────────────────────────

def _son_guitarron(chord: Chord, octave: int = 2) -> EventList:
    """Guitarrón son: LOW ROOT on beat 1, HIGH ROOT+5TH hit on beat 4.
    6/8 eighth-note grid: [root_low, rest, rest, root_high, 5th, rest]
    """
    root_low  = _root_str(chord, octave)
    root_high = _root_str(chord, octave + 1)
    fifth     = _fifth_str(chord, octave + 1)
    return [
        (root_low,  "eighth"),   # beat 1
        (None,      "eighth"),   # beat 2 rest
        (None,      "eighth"),   # beat 3 rest
        (root_high, "eighth"),   # beat 4
        (fifth,     "eighth"),   # beat 5
        (None,      "eighth"),   # beat 6 rest
    ]


def _son_vihuela(chord: Chord, octave: int = 3) -> EventList:
    """Vihuela son: classic "bump-ba-bump" strum pattern.
    [strum, rest, strum, strum, rest, strum]
    """
    root = _root_str(chord, octave)
    S, R = root, None
    return [
        (S, "eighth"),   # beat 1 — down strum
        (R, "eighth"),   # beat 2
        (S, "eighth"),   # beat 3
        (S, "eighth"),   # beat 4
        (R, "eighth"),   # beat 5
        (S, "eighth"),   # beat 6
    ]


def _son_guitar(chord: Chord, octave: int = 3) -> EventList:
    """Guitar son: bass note on beat 1, chord chops on 3, 4, 6."""
    root  = _root_str(chord, octave - 1)
    chord_note = _root_str(chord, octave)
    return [
        (root,       "eighth"),  # beat 1 — bass
        (None,       "eighth"),  # beat 2
        (chord_note, "eighth"),  # beat 3
        (chord_note, "eighth"),  # beat 4
        (None,       "eighth"),  # beat 5
        (chord_note, "eighth"),  # beat 6
    ]


def _son_melody(chord: Chord, octave: int = 4) -> EventList:
    """Violin/Trumpet son: arpeggiate upward across the 6 eighth-note grid."""
    tones = chord.pitches_at_octave(octave)
    notes: EventList = []
    for i in range(6):
        p = tones[i % len(tones)]
        notes.append((str(p), "eighth"))
    return notes


# ─── BOLERO (4/4) ────────────────────────────────────────────────────────────

def _bolero_guitarron(chord: Chord, octave: int = 2) -> EventList:
    """Guitarrón bolero: root-5th-root_high-5th in quarter notes."""
    root     = _root_str(chord, octave)
    fifth    = _fifth_str(chord, octave)
    root_hi  = _root_str(chord, octave + 1)
    return [
        (root,    "quarter"),   # beat 1
        (fifth,   "quarter"),   # beat 2
        (root_hi, "quarter"),   # beat 3
        (fifth,   "quarter"),   # beat 4
    ]


def _bolero_vihuela(chord: Chord, octave: int = 3) -> EventList:
    """Vihuela/Guitar bolero: arp on 1+3, chop on 2+4.
    We represent the arpeggio as a root+5th pair of eighth notes and the
    chop as a single quarter-note strum.
    """
    root  = _root_str(chord, octave)
    fifth = _fifth_str(chord, octave)
    return [
        (root,  "eighth"),   # beat 1a — arp begin
        (fifth, "eighth"),   # beat 1b — arp end
        (root,  "quarter"),  # beat 2 — chop
        (root,  "eighth"),   # beat 3a — arp begin
        (fifth, "eighth"),   # beat 3b — arp end
        (root,  "quarter"),  # beat 4 — chop
    ]


def _bolero_guitar(chord: Chord, octave: int = 3) -> EventList:
    """Guitar bolero: slightly fuller than vihuela, bass on 1, chop on 2, 4."""
    bass  = _root_str(chord, octave - 1)
    root  = _root_str(chord, octave)
    fifth = _fifth_str(chord, octave)
    return [
        (bass,  "quarter"),  # beat 1
        (root,  "quarter"),  # beat 2
        (fifth, "quarter"),  # beat 3
        (root,  "quarter"),  # beat 4
    ]


def _bolero_melody(chord: Chord, octave: int = 4) -> EventList:
    """Violin/Trumpet bolero: long lyrical line, holds on 1 and 3."""
    root  = _root_str(chord, octave)
    third = _third_str(chord, octave)
    fifth = _fifth_str(chord, octave)
    return [
        (root,  "dotted_quarter"),  # beat 1 (dotted = 1.5 beats)
        (third, "eighth"),          # beat 2 (upbeat feel)
        (fifth, "half"),            # beats 3-4 (held tone)
    ]


# ─── WALTZ / VALS (3/4) ───────────────────────────────────────────────────────

def _waltz_guitarron(chord: Chord, octave: int = 2) -> EventList:
    """Guitarrón waltz: classic low-mid-mid.
    Beat 1: low root (strong), Beat 2: 5th (mid), Beat 3: root (mid).
    """
    root_low = _root_str(chord, octave)       # low octave
    fifth    = _fifth_str(chord, octave + 1)  # mid octave
    root_mid = _root_str(chord, octave + 1)   # mid octave
    return [
        (root_low, "quarter"),   # beat 1 — strong bass
        (fifth,    "quarter"),   # beat 2
        (root_mid, "quarter"),   # beat 3
    ]


def _waltz_vihuela(chord: Chord, octave: int = 3) -> EventList:
    """Vihuela waltz: bass-chord note on beat 1, chops on 2 and 3."""
    bass = _root_str(chord, octave - 1)
    root = _root_str(chord, octave)
    return [
        (bass, "quarter"),   # beat 1 — bass + chord
        (root, "quarter"),   # beat 2 — chop
        (root, "quarter"),   # beat 3 — chop
    ]


def _waltz_guitar(chord: Chord, octave: int = 3) -> EventList:
    """Guitar waltz: bass on 1, chords on 2-3 (same feel as vihuela)."""
    bass = _root_str(chord, octave - 1)
    root = _root_str(chord, octave)
    fifth = _fifth_str(chord, octave)
    return [
        (bass,  "quarter"),   # beat 1
        (root,  "quarter"),   # beat 2
        (fifth, "quarter"),   # beat 3
    ]


def _waltz_melody(chord: Chord, octave: int = 4) -> EventList:
    """Violin/Trumpet waltz: long note on beat 1, pickup on beat 3."""
    root  = _root_str(chord, octave)
    third = _third_str(chord, octave)
    fifth = _fifth_str(chord, octave)
    return [
        (root,  "half"),     # beats 1-2 tied
        (fifth, "quarter"),  # beat 3 — pickup / decoration
    ]


# ─── JARABE (fast 6/8) ────────────────────────────────────────────────────────

def _jarabe_guitarron(chord: Chord, octave: int = 2) -> EventList:
    """Guitarrón jarabe: root-root-5th rapid triplet feel across 6 eighths."""
    root  = _root_str(chord, octave)
    fifth = _fifth_str(chord, octave + 1)
    return [
        (root,  "eighth"),
        (root,  "eighth"),
        (fifth, "eighth"),
        (root,  "eighth"),
        (root,  "eighth"),
        (fifth, "eighth"),
    ]


def _jarabe_vihuela(chord: Chord, octave: int = 3) -> EventList:
    """Vihuela jarabe: rapid continuous strumming across all 6 eighths."""
    root = _root_str(chord, octave)
    return [(root, "eighth")] * 6


def _jarabe_guitar(chord: Chord, octave: int = 3) -> EventList:
    """Guitar jarabe: same rapid strumming as vihuela."""
    root = _root_str(chord, octave)
    return [(root, "eighth")] * 6


def _jarabe_melody(chord: Chord, octave: int = 4) -> EventList:
    """Violin/Trumpet jarabe: fast syncopated arpeggio, beat 2 and 4 accented."""
    tones = chord.pitches_at_octave(octave)
    notes: EventList = []
    for i in range(6):
        p = tones[i % len(tones)]
        notes.append((str(p), "eighth"))
    return notes


# ─── CUMBIA NORTEÑA (4/4) ────────────────────────────────────────────────────

def _cumbia_guitarron(chord: Chord, octave: int = 2) -> EventList:
    """Guitarrón cumbia norteña: root on 1, staccato hits on 2 and 4."""
    root  = _root_str(chord, octave)
    fifth = _fifth_str(chord, octave)
    return [
        (root,  "quarter"),   # beat 1 — strong
        (fifth, "eighth"),    # beat 2a — staccato
        (None,  "eighth"),    # beat 2b — rest
        (root,  "eighth"),    # beat 3a
        (None,  "eighth"),    # beat 3b
        (fifth, "quarter"),   # beat 4 — staccato
    ]


def _cumbia_vihuela(chord: Chord, octave: int = 3) -> EventList:
    """Vihuela cumbia: syncopated chop pattern."""
    root  = _root_str(chord, octave)
    fifth = _fifth_str(chord, octave)
    return [
        (None,  "eighth"),   # beat 1a  rest
        (root,  "eighth"),   # beat 1b  chop
        (root,  "quarter"),  # beat 2
        (None,  "eighth"),   # beat 3a  rest
        (fifth, "eighth"),   # beat 3b  chop
        (root,  "quarter"),  # beat 4
    ]


def _cumbia_guitar(chord: Chord, octave: int = 3) -> EventList:
    """Guitar cumbia: bass on 1, chords on 2-4."""
    bass = _root_str(chord, octave - 1)
    root = _root_str(chord, octave)
    return [
        (bass, "quarter"),
        (root, "quarter"),
        (root, "quarter"),
        (root, "quarter"),
    ]


def _cumbia_melody(chord: Chord, octave: int = 4) -> EventList:
    """Violin/Trumpet cumbia: syncopated melodic line."""
    root  = _root_str(chord, octave)
    third = _third_str(chord, octave)
    fifth = _fifth_str(chord, octave)
    return [
        (root,  "eighth"),
        (third, "eighth"),
        (fifth, "quarter"),
        (third, "eighth"),
        (root,  "eighth"),
        (None,  "quarter"),
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Pattern dispatch table
# structure: style -> instrument_name -> (pattern_fn, default_octave)
# ──────────────────────────────────────────────────────────────────────────────

_PATTERNS: dict[str, dict[str, tuple[PatternFn, int]]] = {
    "son": {
        "Guitarrón": (_son_guitarron,  2),
        "Vihuela":   (_son_vihuela,    3),
        "Guitar":    (_son_guitar,     3),
        "Violin":    (_son_melody,     4),
        "Trumpet":   (_son_melody,     4),
    },
    "bolero": {
        "Guitarrón": (_bolero_guitarron, 2),
        "Vihuela":   (_bolero_vihuela,   3),
        "Guitar":    (_bolero_guitar,    3),
        "Violin":    (_bolero_melody,    4),
        "Trumpet":   (_bolero_melody,    4),
    },
    "waltz": {
        "Guitarrón": (_waltz_guitarron, 2),
        "Vihuela":   (_waltz_vihuela,   3),
        "Guitar":    (_waltz_guitar,    3),
        "Violin":    (_waltz_melody,    4),
        "Trumpet":   (_waltz_melody,    4),
    },
    "jarabe": {
        "Guitarrón": (_jarabe_guitarron, 2),
        "Vihuela":   (_jarabe_vihuela,   3),
        "Guitar":    (_jarabe_guitar,    3),
        "Violin":    (_jarabe_melody,    4),
        "Trumpet":   (_jarabe_melody,    4),
    },
    "cumbia": {
        "Guitarrón": (_cumbia_guitarron, 2),
        "Vihuela":   (_cumbia_vihuela,   3),
        "Guitar":    (_cumbia_guitar,    3),
        "Violin":    (_cumbia_melody,    4),
        "Trumpet":   (_cumbia_melody,    4),
    },
}

# Fallback patterns when an instrument is not explicitly listed in the table
_FALLBACK_PATTERNS: dict[str, tuple[PatternFn, int]] = {
    "son":    (_son_melody,     4),
    "bolero": (_bolero_melody,  4),
    "waltz":  (_waltz_melody,   4),
    "jarabe": (_jarabe_melody,  4),
    "cumbia": (_cumbia_melody,  4),
}


# ──────────────────────────────────────────────────────────────────────────────
# RhythmPattern dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RhythmPattern:
    """Encapsulates a complete mariachi rhythm style with its musical parameters.

    Attributes:
        name:           Style identifier: "son", "bolero", "waltz", "jarabe", "cumbia".
        time_signature: Meter string (e.g. "6/8", "4/4", "3/4").
        tempo_range:    Typical (min_bpm, max_bpm) for this style.
    """

    name: str
    time_signature: str
    tempo_range: tuple[int, int]

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_name(cls, name: str) -> "RhythmPattern":
        """Build a RhythmPattern for a named style.

        Args:
            name: One of "son", "bolero", "waltz", "jarabe", "cumbia".

        Raises:
            ValueError: If the style name is unrecognised.
        """
        key = name.strip().lower()
        if key not in _TIME_SIGNATURE:
            raise ValueError(
                f"Unknown rhythm style: {name!r}. "
                f"Available: {sorted(_TIME_SIGNATURE.keys())}."
            )
        return cls(
            name=key,
            time_signature=_TIME_SIGNATURE[key],
            tempo_range=_TYPICAL_TEMPO_RANGE[key],
        )

    # ------------------------------------------------------------------
    # Core method
    # ------------------------------------------------------------------

    def get_notes_for_instrument(
        self,
        chord: Chord,
        instrument: Instrument,
        octave: int | None = None,
    ) -> list[tuple[str | None, str]]:
        """Return the rhythmic event sequence for one measure of this pattern.

        Args:
            chord:      The Chord to voice.
            instrument: The Instrument playing the pattern.
            octave:     Override the default octave for the instrument; None
                        means use the style's idiomatic default.

        Returns:
            A list of ``(pitch_str_or_None, duration_str)`` tuples — one per
            rhythmic event in the measure. ``None`` pitch indicates a rest.
        """
        style_table = _PATTERNS.get(self.name, {})
        if instrument.name in style_table:
            fn, default_oct = style_table[instrument.name]
        else:
            fn, default_oct = _FALLBACK_PATTERNS.get(self.name, (_waltz_melody, 4))

        oct_to_use = octave if octave is not None else default_oct
        return fn(chord, oct_to_use)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def time_sig(self) -> TimeSignature:
        """Parse and return the TimeSignature object for this pattern."""
        return TimeSignature.parse(self.time_signature)

    @property
    def default_tempo(self) -> float:
        """Return the idiomatic default tempo (BPM) for this style."""
        return _DEFAULT_TEMPO.get(self.name, 120.0)

    def __str__(self) -> str:
        lo, hi = self.tempo_range
        return f"RhythmPattern({self.name!r}, {self.time_signature}, {lo}–{hi} bpm)"


# ──────────────────────────────────────────────────────────────────────────────
# Public generator: single chord
# ──────────────────────────────────────────────────────────────────────────────

def generate_rhythm_score(
    chord_root: str,
    chord_quality: str = "major",
    rhythm: str = "waltz",
    key: str = "C",
    instruments: list[str] | None = None,
    measures: int = 8,
    tempo: float | None = None,
    title: str = "",
    composer: str = "",
) -> Score:
    """Generate a multi-instrument Score using an authentic mariachi rhythm style.

    All instruments repeat the same chord for *measures* measures, each playing
    its idiomatic rhythmic pattern for the chosen style.

    Args:
        chord_root:    Root of the chord (e.g. 'G', 'Bb').
        chord_quality: Chord quality ('major', 'minor', 'dominant7', etc.).
        rhythm:        Style name: 'son', 'bolero', 'waltz', 'jarabe', 'cumbia'.
        key:           Key signature root for score metadata.
        instruments:   Instrument names to include.  Defaults to the full
                       5-piece mariachi band.
        measures:      Number of measures to generate per instrument.
        tempo:         BPM.  None → idiomatic default for the chosen style.
        title:         Score title (auto-generated if empty).
        composer:      Composer name.

    Returns:
        A :class:`~mariachi_music.core.score.Score` ready for export.

    Example::

        score = generate_rhythm_score(
            chord_root='G', rhythm='waltz', key='C', measures=8,
        )
        score.export_musicxml('outputs/waltz_g.musicxml')
        score.export_midi('outputs/waltz_g.mid')
    """
    if instruments is None:
        instruments = list(_FULL_MARIACHI_BAND)

    pattern = RhythmPattern.from_name(rhythm)
    chord   = chord_by_root(chord_root, chord_quality)
    ts      = pattern.time_sig
    tp      = Tempo(bpm=tempo if tempo is not None else pattern.default_tempo)
    ks      = KeySignature(root=key, mode="major")

    auto_title = (
        title or
        f"{chord.name} — {rhythm.capitalize()} ({ts}) | "
        + ", ".join(instruments)
    )

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
            events = pattern.get_notes_for_instrument(chord, inst)
            _add_events_to_part(part, events)

        score.add_part(part)

    return score


# ──────────────────────────────────────────────────────────────────────────────
# Public generator: chord progression
# ──────────────────────────────────────────────────────────────────────────────

def generate_song_structure(
    key: str,
    chord_progression: list[int],
    rhythm: str = "waltz",
    measures_per_chord: int = 4,
    instruments: list[str] | None = None,
    repetitions: int = 2,
    tempo: float | None = None,
    title: str = "",
    composer: str = "",
) -> Score:
    """Generate a complete multi-instrument song structure from a chord progression.

    The progression is repeated *repetitions* times so the output resembles a
    verse/chorus loop.  Each chord is sustained for *measures_per_chord* measures.

    Args:
        key:               Key root (e.g. 'C', 'G', 'D').
        chord_progression: Scale degrees 1–7 (e.g. [1, 4, 5, 1]).
        rhythm:            Style name: 'son', 'bolero', 'waltz', 'jarabe', 'cumbia'.
        measures_per_chord: Measures each chord is held before moving to the next.
        instruments:       Instrument names.  Defaults to the full 5-piece band.
        repetitions:       How many times the whole progression repeats.
        tempo:             BPM.  None → idiomatic default for the style.
        title:             Score title (auto-generated if empty).
        composer:          Composer name.

    Returns:
        A :class:`~mariachi_music.core.score.Score` ready for export.

    Example::

        score = generate_song_structure(
            key='C', chord_progression=[1, 4, 5, 1],
            rhythm='son', measures_per_chord=4, repetitions=2,
        )
    """
    if instruments is None:
        instruments = list(_FULL_MARIACHI_BAND)

    pattern    = RhythmPattern.from_name(rhythm)
    ts         = pattern.time_sig
    tp         = Tempo(bpm=tempo if tempo is not None else pattern.default_tempo)
    ks         = KeySignature(root=key, mode="major")
    key_chords = chords_in_key(key, "major")  # list of (roman, Chord)

    # Resolve degrees → chords
    chord_sequence: list[tuple[str, Chord]] = []
    for deg in chord_progression:
        if not 1 <= deg <= 7:
            raise ValueError(f"Scale degree {deg} is out of range 1–7.")
        roman, chord = key_chords[deg - 1]
        chord_sequence.append((roman, chord))

    roman_str  = " – ".join(r for r, _ in chord_sequence)
    auto_title = (
        title or
        f"{key} {rhythm.capitalize()}: {roman_str} (×{repetitions})"
    )

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

        for _ in range(repetitions):
            for _roman, chord in chord_sequence:
                for _ in range(measures_per_chord):
                    events = pattern.get_notes_for_instrument(chord, inst)
                    _add_events_to_part(part, events)

        score.add_part(part)

    return score
