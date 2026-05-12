"""CLI: generate a mariachi rhythm score and export it as MusicXML + MIDI.

Two modes of operation
-----------------------

Single-chord mode (--chord):

    python -m mariachi_music.cli.create_rhythm \\
        --chord G --rhythm waltz --key C --measures 8 \\
        --instruments Guitarrón Vihuela Guitar Violin Trumpet \\
        --output outputs/waltz_g_chord

Chord-progression mode (--key + --progression):

    python -m mariachi_music.cli.create_rhythm \\
        --key C --progression 1 4 5 1 --rhythm son \\
        --output outputs/son_progression

You can also control tempo, measures per chord, repetitions, title, and composer.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mariachi_music.core.instrument import INSTRUMENTS
from mariachi_music.generation.rhythm_engine import (
    _FULL_MARIACHI_BAND,
    _TIME_SIGNATURE,
    _TYPICAL_TEMPO_RANGE,
    generate_rhythm_score,
    generate_song_structure,
)

RHYTHM_CHOICES = sorted(_TIME_SIGNATURE.keys())
INSTRUMENT_CHOICES = sorted(INSTRUMENTS.keys())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mariachi-rhythm",
        description="Generate an authentic mariachi rhythm score (MusicXML + MIDI).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # ── output ──────────────────────────────────────────────────────────────
    p.add_argument(
        "--output", "-o",
        required=True,
        metavar="PATH_STEM",
        help="Output path stem — .musicxml and .mid suffixes are added automatically.",
    )

    # ── mode selection ───────────────────────────────────────────────────────
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--chord", "-c",
        metavar="ROOT",
        help=(
            "Single-chord mode.  Root note of the chord to hold "
            "(e.g. G, Bb, F#)."
        ),
    )
    mode.add_argument(
        "--progression", "-p",
        nargs="+",
        type=int,
        metavar="DEGREE",
        help=(
            "Progression mode.  Space-separated scale degrees 1–7 "
            "(e.g. 1 4 5 1).  Requires --key."
        ),
    )

    # ── common ──────────────────────────────────────────────────────────────
    p.add_argument(
        "--key",
        default="C",
        metavar="ROOT",
        help="Key signature root (e.g. C, G, Bb).  Used for chord lookup in progression mode.",
    )
    p.add_argument(
        "--chord-quality", "--quality",
        default="major",
        dest="chord_quality",
        metavar="QUALITY",
        help=(
            "Chord quality for single-chord mode "
            "(major, minor, dominant7, major7, minor7, diminished, augmented)."
        ),
    )
    p.add_argument(
        "--rhythm", "-r",
        default="waltz",
        choices=RHYTHM_CHOICES,
        help="Rhythm style to use.",
    )
    p.add_argument(
        "--instruments",
        nargs="+",
        default=list(_FULL_MARIACHI_BAND),
        metavar="INSTRUMENT",
        help=(
            "Instruments to include in the score.  "
            f"Available: {', '.join(INSTRUMENT_CHOICES)}."
        ),
    )
    p.add_argument(
        "--tempo",
        type=float,
        default=None,
        metavar="BPM",
        help="Tempo in BPM.  Defaults to the typical tempo for the chosen rhythm style.",
    )
    p.add_argument(
        "--title",
        default="",
        metavar="TITLE",
        help="Score title (auto-generated if omitted).",
    )
    p.add_argument(
        "--composer",
        default="",
        metavar="NAME",
        help="Composer name.",
    )

    # ── single-chord options ─────────────────────────────────────────────────
    p.add_argument(
        "--measures",
        type=int,
        default=8,
        metavar="N",
        help="[single-chord mode] Number of measures to generate.",
    )

    # ── progression options ──────────────────────────────────────────────────
    p.add_argument(
        "--measures-per-chord",
        type=int,
        default=4,
        dest="measures_per_chord",
        metavar="N",
        help="[progression mode] Measures to hold each chord.",
    )
    p.add_argument(
        "--repetitions",
        type=int,
        default=2,
        metavar="N",
        help="[progression mode] How many times to repeat the full progression.",
    )

    return p


def _validate_instruments(names: list[str]) -> list[str]:
    """Raise SystemExit if any instrument name is unrecognised."""
    bad = [n for n in names if n not in INSTRUMENTS]
    if bad:
        print(
            f"Error: unknown instrument(s): {bad!r}\n"
            f"Available: {INSTRUMENT_CHOICES}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return names


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args   = parser.parse_args(argv)

    # Validate instruments before doing any work
    _validate_instruments(args.instruments)

    lo, hi = _TYPICAL_TEMPO_RANGE[args.rhythm]
    ts_str = _TIME_SIGNATURE[args.rhythm]

    # ── dispatch ─────────────────────────────────────────────────────────────
    if args.progression:
        score = generate_song_structure(
            key=args.key,
            chord_progression=args.progression,
            rhythm=args.rhythm,
            measures_per_chord=args.measures_per_chord,
            instruments=args.instruments,
            repetitions=args.repetitions,
            tempo=args.tempo,
            title=args.title,
            composer=args.composer,
        )
        mode_desc = (
            f"Progression {args.progression} in {args.key} | "
            f"{args.repetitions}× repetition(s), {args.measures_per_chord} measures/chord"
        )
    else:
        # Default to single-chord mode; if neither flag was given, use C major.
        chord_root = args.chord or "C"
        score = generate_rhythm_score(
            chord_root=chord_root,
            chord_quality=args.chord_quality,
            rhythm=args.rhythm,
            key=args.key,
            instruments=args.instruments,
            measures=args.measures,
            tempo=args.tempo,
            title=args.title,
            composer=args.composer,
        )
        mode_desc = f"Chord {chord_root} {args.chord_quality} | {args.measures} measures"

    # ── export ────────────────────────────────────────────────────────────────
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        xml_path = score.export_musicxml(out.with_suffix(".musicxml"))
        mid_path = score.export_midi(out.with_suffix(".mid"))
    except Exception as exc:
        print(f"Export error: {exc}", file=sys.stderr)
        return 1

    # ── summary ──────────────────────────────────────────────────────────────
    print(score.summary())
    print()
    print(f"Rhythm   : {args.rhythm.upper()}  ({ts_str}, {lo}–{hi} bpm typical)")
    print(f"Mode     : {mode_desc}")
    print(f"Tempo    : {score.tempo.bpm:.1f} bpm")
    print()
    print(f"MusicXML : {xml_path}")
    print(f"MIDI     : {mid_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
