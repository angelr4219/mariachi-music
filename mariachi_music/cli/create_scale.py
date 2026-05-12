"""CLI: generate a scale as MusicXML + MIDI.

Usage::

    python -m mariachi_music.cli.create_scale \\
        --key C --mode major --octave 4 --duration quarter \\
        --time-signature 4/4 --tempo 120 --instrument Violin \\
        --output outputs/c_major_scale

This creates:
    outputs/c_major_scale.musicxml
    outputs/c_major_scale.mid
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mariachi_music.core.instrument import INSTRUMENTS
from mariachi_music.generation.scale_generator import generate_scale_score


_VALID_DURATIONS = ["whole", "half", "quarter", "eighth", "sixteenth",
                    "dotted_half", "dotted_quarter", "dotted_eighth"]
_VALID_MODES = ["major", "minor", "dorian", "phrygian", "lydian",
                "mixolydian", "locrian", "chromatic"]


def _instrument_name(value: str) -> str:
    """Return the canonical instrument name for case-insensitive CLI input."""
    key = value.strip().lower()
    for name in INSTRUMENTS:
        if name.lower() == key:
            return name
    valid = ", ".join(sorted(INSTRUMENTS))
    raise argparse.ArgumentTypeError(f"invalid instrument {value!r}; choose from: {valid}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mariachi-scale",
        description="Generate a musical scale as MusicXML and MIDI.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--key", default="C", help="Root note of the scale (e.g. C, G, Bb, F#).")
    p.add_argument("--mode", default="major", choices=_VALID_MODES, help="Scale mode.")
    p.add_argument("--octave", type=int, default=4, help="Starting octave (4 = middle C area).")
    p.add_argument("--duration", default="quarter", choices=_VALID_DURATIONS, help="Note duration.")
    p.add_argument("--time-signature", default="4/4", dest="time_signature",
                   help="Time signature (e.g. 4/4, 3/4, 6/8).")
    p.add_argument("--tempo", type=float, default=120.0, help="Beats per minute.")
    p.add_argument("--instrument", default="Violin", type=_instrument_name,
                   metavar="INSTRUMENT", help="Instrument name.")
    p.add_argument("--descending", action="store_true",
                   help="Generate descending scale instead of ascending.")
    p.add_argument("--title", default="", help="Score title (auto-generated if omitted).")
    p.add_argument("--composer", default="", help="Composer name.")
    p.add_argument("--output", "-o", required=True,
                   help="Output path stem (e.g. outputs/c_major_scale). "
                        "Suffixes .musicxml and .mid are added automatically.")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        score = generate_scale_score(
            key=args.key,
            mode=args.mode,
            octave=args.octave,
            duration=args.duration,
            time_signature=args.time_signature,
            tempo=args.tempo,
            instrument=args.instrument,
            ascending=not args.descending,
            title=args.title,
            composer=args.composer,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    xml_path = score.export_musicxml(out.with_suffix(".musicxml"))
    mid_path = score.export_midi(out.with_suffix(".mid"))

    print(score.summary())
    print()
    print(f"MusicXML : {xml_path}")
    print(f"MIDI     : {mid_path}")
    print()
    print("Open the MusicXML file in MuseScore to view and print the sheet music.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
