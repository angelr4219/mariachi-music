"""CLI for mariachi form-template generation and audio genre recognition."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mariachi_music.core.instrument import INSTRUMENTS
from mariachi_music.mariachi import (
    CONTEXT_RULES,
    GENRE_TEMPLATES,
    MariachiSongRequest,
    classify_audio_genre,
    generate_mariachi_arrangement,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mariachi-template",
        description="Generate or recognize mariachi genre/form templates.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate a template-based mariachi score.")
    gen.add_argument("--genre", required=True, choices=sorted(GENRE_TEMPLATES))
    gen.add_argument("--subtype", default="", help="Optional subtype, e.g. ranchera_3_4 or polca_ranchera.")
    gen.add_argument("--context", default="restaurant", choices=sorted(CONTEXT_RULES))
    gen.add_argument("--key", default="G")
    gen.add_argument("--mode", default="major", choices=["major", "minor"])
    gen.add_argument("--tempo", type=float, default=None)
    gen.add_argument("--length", default="full", choices=["short", "full", "auto"])
    gen.add_argument("--ensemble", nargs="+", choices=sorted(INSTRUMENTS), default=None)
    gen.add_argument("--title", default="")
    gen.add_argument("--composer", default="")
    gen.add_argument("--output", "-o", required=True, help="Output path stem.")
    gen.set_defaults(func=_generate)

    cls = sub.add_parser("classify-audio", help="Guess son/bolero/ranchera from an audio file.")
    cls.add_argument("audio")
    cls.add_argument("--duration", type=float, default=90.0)
    cls.add_argument("--sample-rate", type=int, default=22050)
    cls.set_defaults(func=_classify_audio)

    return parser


def _generate(args: argparse.Namespace) -> int:
    request = MariachiSongRequest(
        genre=args.genre,
        context=args.context,
        key=args.key,
        mode=args.mode,
        tempo=args.tempo,
        length=args.length,
        ensemble=tuple(args.ensemble) if args.ensemble else None,
        subtype=args.subtype,
        title=args.title,
        composer=args.composer,
    )
    try:
        result = generate_mariachi_arrangement(request)
    except Exception as exc:
        print(f"Generation error: {exc}", file=sys.stderr)
        return 1

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    xml_path = result.score.export_musicxml(out.with_suffix(".musicxml"))
    mid_path = result.score.export_midi(out.with_suffix(".mid"))
    map_path = result.write_section_map(out.with_suffix(".sections.json"))

    print(result.score.summary())
    print()
    print(f"Genre   : {result.template.genre}")
    print(f"Context : {result.context_rule.name}")
    print(f"Feel    : {result.template.feel}")
    print(f"Sections: {' '.join(section.label for section in result.sections)}")
    print()
    print(f"MusicXML    : {xml_path}")
    print(f"MIDI        : {mid_path}")
    print(f"Section map : {map_path}")
    return 0


def _classify_audio(args: argparse.Namespace) -> int:
    try:
        guess = classify_audio_genre(args.audio, sample_rate=args.sample_rate, duration=args.duration)
    except Exception as exc:
        print(f"Classification error: {exc}", file=sys.stderr)
        return 1

    print(f"Genre      : {guess.genre}")
    print(f"Confidence : {guess.confidence:.3f}")
    print(f"Tempo      : {guess.tempo_bpm:.1f} bpm")
    print(f"Meter hint : {guess.meter_hint}")
    print("Reasoning  :")
    for line in guess.reasoning:
        print(f"  - {line}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
