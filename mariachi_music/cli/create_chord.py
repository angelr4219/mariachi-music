"""CLI: generate a chord or chord progression as MusicXML + MIDI.

Single chord example::

    python -m mariachi_music.cli.create_chord \\
        --chord G --quality major --key C \\
        --time-signature 3/4 --tempo 120 \\
        --instruments Guitarrón Guitar Violin \\
        --measures 4 \\
        --output outputs/g_chord

Chord progression example::

    python -m mariachi_music.cli.create_chord \\
        --key C --progression 1 4 5 1 \\
        --time-signature 3/4 --tempo 120 \\
        --instruments Guitarrón Guitar Violin \\
        --output outputs/c_major_145
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mariachi_music.core.instrument import INSTRUMENTS
from mariachi_music.generation.chord_generator import (
    generate_chord_score,
    generate_key_chord_progression,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mariachi-chord",
        description="Generate a chord or chord progression for multiple instruments.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # ── Chord or progression ──────────────────────────────────────────
    group = p.add_mutually_exclusive_group()
    group.add_argument(
        "--chord", metavar="ROOT",
        help="Chord root note (e.g. G, Bb, F#). Generates all instruments on this one chord.",
    )
    group.add_argument(
        "--progression", nargs="+", type=int, metavar="DEGREE",
        help="Scale degrees for a progression, e.g. --progression 1 4 5 1",
    )

    # ── Score settings ────────────────────────────────────────────────
    p.add_argument("--quality", default="major",
                   choices=["major", "minor", "diminished", "dominant7", "major7", "minor7"],
                   help="Chord quality (used with --chord).")
    p.add_argument("--key", default="C", help="Key signature root (e.g. C, G, Bb).")
    p.add_argument("--mode", default="major", choices=["major", "minor"],
                   help="Key mode.")
    p.add_argument("--time-signature", default="3/4", dest="time_signature",
                   help="Time signature (3/4, 4/4, 6/8, etc.).")
    p.add_argument("--tempo", type=float, default=120.0, help="BPM.")
    p.add_argument("--measures", type=int, default=4,
                   help="Measures per chord (for --chord) or per degree (for --progression).")
    p.add_argument("--duration", default="quarter",
                   choices=["whole", "half", "quarter", "eighth"],
                   help="Note duration per beat.")
    p.add_argument("--instruments", nargs="+",
                   default=["Guitarrón", "Guitar", "Violin"],
                   choices=sorted(INSTRUMENTS.keys()),
                   help="Instruments to include.")
    p.add_argument("--title", default="", help="Score title.")
    p.add_argument("--composer", default="", help="Composer name.")
    p.add_argument("--output", "-o", required=True,
                   help="Output path stem. .musicxml and .mid are appended.")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.progression:
            score = generate_key_chord_progression(
                key_root=args.key,
                mode=args.mode,
                degrees=args.progression,
                time_signature=args.time_signature,
                tempo=args.tempo,
                instruments=args.instruments,
                measures_per_chord=args.measures,
                duration=args.duration,
                title=args.title,
                composer=args.composer,
            )
        else:
            chord_root = args.chord or args.key   # default to tonic if no --chord given
            score = generate_chord_score(
                chord_root=chord_root,
                chord_quality=args.quality,
                key=args.key,
                mode=args.mode,
                time_signature=args.time_signature,
                tempo=args.tempo,
                instruments=args.instruments,
                measures=args.measures,
                duration=args.duration,
                title=args.title,
                composer=args.composer,
            )
    except (ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    xml_path = score.export_musicxml(out.with_suffix(".musicxml"))
    mid_path = score.export_midi(out.with_suffix(".mid"))

    print(score.summary())
    print()

    # Show per-part note preview
    for part in score.parts:
        notes = part.all_notes
        preview = "  ".join(str(n.pitch) for n in notes[:16])
        if len(notes) > 16:
            preview += " …"
        print(f"  {part.instrument.name:14s}: {preview}")

    print()
    print(f"MusicXML : {xml_path}")
    print(f"MIDI     : {mid_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
