"""LilyPond export: convert a Score to a .ly file."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from mariachi_music.core.duration import DurationValue
from mariachi_music.core.note import Note, Rest
from mariachi_music.core.score import Score


# ---------------------------------------------------------------------------
# Pitch encoding
# ---------------------------------------------------------------------------

# LilyPond note names are always lowercase
_PITCH_NAME: dict[str, str] = {
    "C": "c", "D": "d", "E": "e", "F": "f",
    "G": "g", "A": "a", "B": "b",
}

# Accidental suffixes in LilyPond
_ACCIDENTAL_SUFFIX: dict[str, str] = {
    "":   "",
    "#":  "is",
    "##": "isis",
    "b":  "es",
    "bb": "eses",
    "n":  "",   # natural — no suffix needed
}

# Special-case flat names that LilyPond spells differently
_FLAT_SPECIAL: dict[str, str] = {
    "Eb": "ees",
    "Ab": "aes",
    "Bb": "bes",
}


def _pitch_to_lily(pitch) -> str:  # pitch: Pitch
    """Convert a Pitch to its LilyPond token (e.g. Pitch('F','#',5) → 'fis\\'\\''). """
    key = f"{pitch.name}{pitch.accidental}"
    if pitch.accidental == "b" and key in _FLAT_SPECIAL:
        note_name = _FLAT_SPECIAL[key]
    else:
        base = _PITCH_NAME[pitch.name]
        note_name = base + _ACCIDENTAL_SUFFIX.get(pitch.accidental, "")

    # Octave marks: C4 = c' (middle C), C5 = c'', C3 = c, C2 = c,
    octave = pitch.octave
    if octave >= 4:
        marks = "'" * (octave - 3)
    elif octave == 3:
        marks = ""
    else:
        marks = "," * (3 - octave)

    return note_name + marks


# ---------------------------------------------------------------------------
# Duration encoding
# ---------------------------------------------------------------------------

_BASE_LILY_DURATION: dict[DurationValue, str] = {
    DurationValue.WHOLE:        "1",
    DurationValue.HALF:         "2",
    DurationValue.QUARTER:      "4",
    DurationValue.EIGHTH:       "8",
    DurationValue.SIXTEENTH:    "16",
    DurationValue.THIRTY_SECOND: "32",
    DurationValue.DOTTED_WHOLE:  "1.",
    DurationValue.DOTTED_HALF:   "2.",
    DurationValue.DOTTED_QUARTER: "4.",
    DurationValue.DOTTED_EIGHTH:  "8.",
}


def _duration_to_lily(duration) -> str:  # duration: Duration
    """Return LilyPond duration string (e.g. '4', '2.', '8')."""
    return _BASE_LILY_DURATION[duration.value]


# ---------------------------------------------------------------------------
# Key signature encoding
# ---------------------------------------------------------------------------

# Map (fifths, mode) → (root_token, mode_token)
# mode_token is \major or \minor in LilyPond
_MAJOR_KEYS: dict[int, str] = {
    -7: "ces", -6: "ges", -5: "des", -4: "aes", -3: "ees",
    -2: "bes", -1: "f",
     0: "c",
     1: "g",   2: "d",   3: "a",   4: "e",   5: "b",
     6: "fis",  7: "cis",
}

# Relative minors share the same fifths value as their relative major
_MINOR_KEYS: dict[int, str] = {
    -7: "aes", -6: "ees", -5: "bes", -4: "f",  -3: "c",
    -2: "g",   -1: "d",
     0: "a",
     1: "e",   2: "b",   3: "fis",  4: "cis", 5: "gis",
     6: "dis",  7: "ais",
}


def _key_to_lily(key_signature) -> str:  # key_signature: KeySignature
    """Return LilyPond \\key statement (without leading backslash or newline).

    Returns e.g. r'\\key g \\major'.
    """
    fifths = key_signature.fifths
    mode = key_signature.mode.lower()

    if mode in ("major", "lydian", "mixolydian", "dorian", "phrygian", "locrian"):
        # Use major key map for reference (accidentals are identical)
        root_token = _MAJOR_KEYS.get(fifths, "c")
        lily_mode = "major"
    elif mode in ("minor", "aeolian"):
        root_token = _MINOR_KEYS.get(fifths, "a")
        lily_mode = "minor"
    else:
        root_token = _MAJOR_KEYS.get(fifths, "c")
        lily_mode = "major"

    return rf"\key {root_token} \{lily_mode}"


# ---------------------------------------------------------------------------
# Transposing-instrument wrapper
# ---------------------------------------------------------------------------

def _transpose_token(semitones: int) -> tuple[str, str]:
    """Return (open_token, close_token) for a \\transpose wrapper, or ('', '').

    LilyPond \\transpose from to { ... } shifts pitches by the interval
    between *from* and *to*.  For a Bb trumpet (written pitch sounds -2 ST),
    we need concert pitch, so we write:
        \\transpose bes c { ... }
    meaning "what was written as bes now sounds as c", raising by 2 ST.

    We map semitones (instrument.transposition, negative for flat transposers)
    to appropriate from/to pitches using middle C octave.
    """
    if semitones == 0:
        return "", ""

    # \\transpose from to: sounding = written + interval(from→to)
    # We want sounding = written + semitones.
    # So interval(from→to) = semitones, meaning to = from + semitones.
    # Pick from = c' (midi 60), compute to.
    from mariachi_music.core.pitch import Pitch

    from_midi = 60  # c'
    to_midi = from_midi + semitones
    to_pitch = Pitch.from_midi(to_midi)
    to_token = _pitch_to_lily(to_pitch)

    open_tok = rf"\transpose c' {to_token} {{"
    close_tok = "}"
    return open_tok, close_tok


# ---------------------------------------------------------------------------
# Event encoding
# ---------------------------------------------------------------------------

def _event_to_lily(event) -> str:  # event: Note | Rest
    """Encode a single Note or Rest as a LilyPond token."""
    dur = _duration_to_lily(event.duration)
    if isinstance(event, Rest):
        return f"r{dur}"
    # Note
    p = _pitch_to_lily(event.pitch)
    token = f"{p}{dur}"
    if event.tie_start:
        token += "~"
    return token


# ---------------------------------------------------------------------------
# Part → LilyPond staff block
# ---------------------------------------------------------------------------

def _part_to_lily_staff(part, key_signature=None) -> str:  # part: Part
    """Render one Part as a \\new Staff { ... } block.

    Args:
        part:          The Part to render.
        key_signature: Score-level KeySignature to emit at the start of the staff.
                       If None, no \\key directive is emitted.
    """
    inst = part.instrument
    lines: list[str] = []

    lines.append(r"    \new Staff {")
    lines.append(f'      \\set Staff.instrumentName = "{inst.name}"')
    lines.append(f'      \\set Staff.shortInstrumentName = "{inst.abbreviation or inst.name[:3]}"')

    # Clef
    clef = inst.clef
    if clef == "bass":
        lines.append(r'      \clef "bass"')
    elif clef in ("alto", "tenor"):
        lines.append(rf'      \clef "{clef}"')
    else:
        lines.append(r'      \clef "treble"')

    # Transposition wrapper open
    trans_open, trans_close = _transpose_token(inst.transposition)
    if trans_open:
        lines.append(f"      {trans_open}")

    lines.append("      {")

    for idx, measure in enumerate(part.measures):
        ts = measure.time_signature
        time_token = rf"\time {ts.beats_per_measure}/{ts.beat_unit}"

        event_tokens = [_event_to_lily(e) for e in measure.events]
        measure_body = " ".join(event_tokens)
        if idx == 0:
            # First measure: emit key + time before notes
            prefix_tokens = []
            if key_signature is not None:
                prefix_tokens.append(_key_to_lily(key_signature))
            prefix_tokens.append(time_token)
            prefix = " ".join(prefix_tokens)
            lines.append(f"        {prefix} {measure_body} |")
        else:
            lines.append(f"        {measure_body} |")

    lines.append("      }")

    if trans_close:
        lines.append(f"      {trans_close}")

    lines.append("    }")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main export function
# ---------------------------------------------------------------------------

def export_score_lilypond(score: Score, path: Path) -> Path:
    """Export a Score as a LilyPond .ly file.  Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() != ".ly":
        path = path.with_suffix(".ly")

    bpm = int(round(score.tempo.bpm))

    # Build the file as a list of lines
    lines: list[str] = []
    lines.append(r'\version "2.24.0"')
    lines.append("")

    # Header block
    lines.append(r"\header {")
    title_escaped = score.title.replace('"', r'\"')
    composer_escaped = score.composer.replace('"', r'\"')
    lines.append(f'  title = "{title_escaped}"')
    if score.composer:
        lines.append(f'  composer = "{composer_escaped}"')
    lines.append('  tagline = ""')
    lines.append("}")
    lines.append("")

    # Score block
    lines.append(r"\score {")
    lines.append("  <<")

    if score.parts:
        for part in score.parts:
            lines.append(_part_to_lily_staff(part, key_signature=score.key_signature))
    else:
        # Emit an empty treble staff so the file is valid LilyPond
        lines.append(r"    \new Staff { }")

    lines.append("  >>")

    # Global key / time / tempo as a separate context (applied to all staves)
    lines.append("")
    lines.append("  \\layout { }")
    lines.append("")
    lines.append("  \\midi {")
    lines.append(f"    \\tempo 4 = {bpm}")
    lines.append("  }")
    lines.append("}")
    lines.append("")

    content = "\n".join(lines)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# PDF rendering helper
# ---------------------------------------------------------------------------

def render_lilypond_pdf(ly_path: Path) -> "Path | None":
    """Run the lilypond CLI on *ly_path* to produce a PDF.

    Returns the PDF path on success, or None if lilypond is not installed or
    the render fails.
    """
    ly_path = Path(ly_path)
    if not shutil.which("lilypond"):
        return None

    try:
        result = subprocess.run(
            ["lilypond", "--pdf", "-o", str(ly_path.with_suffix("")), str(ly_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None

    if result.returncode != 0:
        return None

    pdf_path = ly_path.with_suffix(".pdf")
    return pdf_path if pdf_path.exists() else None
