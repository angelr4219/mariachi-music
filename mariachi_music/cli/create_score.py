"""CLI: build a multi-instrument score programmatically.

Usage::

    python -m mariachi_music.cli.create_score \\
        --title "Mariachi Practice" --composer "Angel Ramirez" \\
        --tempo 120 --key C --mode major --time-signature 4/4 \\
        --output outputs/practice
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mariachi_music.core.instrument import INSTRUMENTS
from mariachi_music.core.key_signature import KeySignature
from mariachi_music.core.score import Score
from mariachi_music.core.tempo import Tempo
from mariachi_music.core.time_signature import TimeSignature
from mariachi_music.generation.scale_generator import generate_scale_score


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mariachi-score",
        description="Build and export a multi-instrument score.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--title", default="Untitled Score", help="Score title.")
    p.add_argument("--composer", default="", help="Composer name.")
    p.add_argument("--tempo", type=float, default=120.0, help="BPM.")
    p.add_argument("--key", default="C", help="Key signature root.")
    p.add_argument("--mode", default="major",
                   choices=["major", "minor", "dorian", "mixolydian"],
                   help="Key mode.")
    p.add_argument("--time-signature", default="4/4", dest="time_signature",
                   help="Time signature.")
    p.add_argument("--instruments", nargs="+", default=["Violin"],
                   choices=sorted(INSTRUMENTS.keys()),
                   help="List of instrument names to include (each plays a scale).")
    p.add_argument("--duration", default="quarter",
                   choices=["whole", "half", "quarter", "eighth"],
                   help="Note duration for generated content.")
    p.add_argument("--output", "-o", required=True,
                   help="Output path stem. .musicxml and .mid suffixes added.")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    ts = TimeSignature.parse(args.time_signature)
    tp = Tempo(bpm=args.tempo)
    ks = KeySignature(root=args.key, mode=args.mode)

    score = Score(
        title=args.title,
        composer=args.composer,
        tempo=tp,
        key_signature=ks,
        time_signature=ts,
    )

    from mariachi_music.core.instrument import Instrument
    from mariachi_music.generation.scale_generator import generate_scale_score
    from mariachi_music.core.part import Part
    from mariachi_music.theory.scales import Scale

    for inst_name in args.instruments:
        try:
            inst = Instrument.by_name(inst_name)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        scale = Scale.parse(root=args.key, mode=args.mode)
        pitches = scale.pitch_strings()
        part = Part(instrument=inst, default_ts=ts)
        part.add_notes(pitches, duration=args.duration)
        score.add_part(part)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        xml_path = score.export_musicxml(out.with_suffix(".musicxml"))
        mid_path = score.export_midi(out.with_suffix(".mid"))
    except Exception as exc:
        print(f"Export error: {exc}", file=sys.stderr)
        return 1

    print(score.summary())
    print()
    print(f"MusicXML : {xml_path}")
    print(f"MIDI     : {mid_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
