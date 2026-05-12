"""CLI: export a score to various formats.

Usage::

    python -m mariachi_music.cli.export_score \\
        --input score.json \\
        --format lilypond \\
        --output out.ly

    python -m mariachi_music.cli.export_score \\
        --format lilypond \\
        --title "La Negra" --composer "Trad." \\
        --key G --mode major --tempo 140 \\
        --instruments Violin Trumpet \\
        --output outputs/la_negra.ly

The --input flag accepts a JSON file previously exported by the generation
tools.  If omitted the script generates a simple scale score from the other
flags so the CLI is immediately useful without a pre-built score file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Minimal JSON → Score loader (loads what generate_scale_score / create_score
# would have serialised; falls back gracefully to a generated scale score).
# ---------------------------------------------------------------------------

def _score_from_json(json_path: Path):  # -> Score
    """Best-effort reconstruction of a Score from a JSON snapshot.

    The JSON schema is not formally defined yet, so we support the simple
    dict that generate_scale_score produces when exported via note_table().
    For now we treat an unrecognised file as an error and give a clear message.
    """
    from mariachi_music.core.key_signature import KeySignature
    from mariachi_music.core.score import Score
    from mariachi_music.core.tempo import Tempo
    from mariachi_music.core.time_signature import TimeSignature

    raw = json.loads(json_path.read_text(encoding="utf-8"))

    title = raw.get("title", "Untitled")
    composer = raw.get("composer", "")
    bpm = float(raw.get("bpm", raw.get("tempo", 120)))
    key_root = raw.get("key", "C")
    key_mode = raw.get("mode", "major")
    ts_str = raw.get("time_signature", "4/4")

    score = Score(
        title=title,
        composer=composer,
        tempo=Tempo(bpm),
        key_signature=KeySignature(key_root, key_mode),
        time_signature=TimeSignature.parse(ts_str),
    )

    parts_data = raw.get("parts", [])
    if not parts_data:
        raise ValueError(
            "JSON file has no 'parts' key.  "
            "Please supply a score JSON with a 'parts' list, "
            "or omit --input to generate a scale score from flags."
        )

    from mariachi_music.core.duration import Duration
    from mariachi_music.core.instrument import Instrument
    from mariachi_music.core.note import Note, Rest
    from mariachi_music.core.part import Part
    from mariachi_music.core.pitch import Pitch

    for part_data in parts_data:
        inst_name = part_data.get("instrument", "Violin")
        try:
            inst = Instrument.by_name(inst_name)
        except ValueError:
            inst = Instrument(name=inst_name)

        part = Part(instrument=inst, default_ts=TimeSignature.parse(ts_str))

        for measure_data in part_data.get("measures", []):
            m = part.new_measure()
            for event_data in measure_data.get("events", []):
                dur = Duration.parse(event_data["duration"])
                if event_data.get("type") == "rest":
                    m.add(Rest(dur), strict=False)
                else:
                    pitch = Pitch.parse(event_data["pitch"])
                    m.add(Note(pitch=pitch, duration=dur), strict=False)

        score.add_part(part)

    return score


def _score_from_flags(args: argparse.Namespace):  # -> Score
    """Generate a simple scale score from CLI flags."""
    from mariachi_music.core.instrument import Instrument
    from mariachi_music.core.key_signature import KeySignature
    from mariachi_music.core.part import Part
    from mariachi_music.core.score import Score
    from mariachi_music.core.tempo import Tempo
    from mariachi_music.core.time_signature import TimeSignature
    from mariachi_music.theory.scales import Scale

    ts = TimeSignature.parse(args.time_signature)
    ks = KeySignature(root=args.key, mode=args.mode)

    score = Score(
        title=args.title,
        composer=args.composer,
        tempo=Tempo(bpm=args.tempo),
        key_signature=ks,
        time_signature=ts,
    )

    instruments = args.instruments or ["Violin"]
    for inst_name in instruments:
        try:
            inst = Instrument.by_name(inst_name)
        except ValueError as exc:
            print(f"Warning: {exc} — skipping.", file=sys.stderr)
            continue

        scale = Scale.parse(root=args.key, mode=args.mode)
        pitches = scale.pitch_strings()
        part = Part(instrument=inst, default_ts=ts)
        part.add_notes(pitches, duration=args.duration)
        score.add_part(part)

    return score


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mariachi-export",
        description="Export a mariachi_music Score to a specified format.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--input", "-i", metavar="SCORE_JSON",
        help="Path to a score JSON file.  If omitted, a scale score is generated.",
    )
    p.add_argument(
        "--format", "-f", default="lilypond",
        choices=["lilypond", "musicxml", "midi", "all"],
        help="Output format.",
    )
    p.add_argument(
        "--output", "-o", required=True,
        help="Output file path (or path stem when --format all).",
    )
    p.add_argument("--render-pdf", action="store_true",
                   help="After LilyPond export, attempt to render PDF with lilypond CLI.")

    # Score-generation flags (used when --input is omitted)
    p.add_argument("--title", default="Untitled Score")
    p.add_argument("--composer", default="")
    p.add_argument("--tempo", type=float, default=120.0, metavar="BPM")
    p.add_argument("--key", default="C", metavar="ROOT")
    p.add_argument(
        "--mode", default="major",
        choices=["major", "minor", "dorian", "mixolydian", "phrygian", "lydian"],
    )
    p.add_argument("--time-signature", default="4/4", dest="time_signature")
    p.add_argument(
        "--instruments", nargs="+", default=["Violin"],
        metavar="INSTRUMENT",
    )
    p.add_argument(
        "--duration", default="quarter",
        choices=["whole", "half", "quarter", "eighth", "sixteenth"],
    )
    return p


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Load or generate score
    if args.input:
        try:
            score = _score_from_json(Path(args.input))
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            print(f"Error loading score JSON: {exc}", file=sys.stderr)
            return 1
    else:
        score = _score_from_flags(args)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    fmt = args.format

    try:
        if fmt in ("lilypond", "all"):
            from mariachi_music.export.lilypond_export import (
                export_score_lilypond,
                render_lilypond_pdf,
            )
            ly_path = out if fmt == "lilypond" else out.with_suffix(".ly")
            exported = export_score_lilypond(score, ly_path)
            print(f"LilyPond : {exported}")

            if args.render_pdf:
                pdf = render_lilypond_pdf(exported)
                if pdf:
                    print(f"PDF      : {pdf}")
                else:
                    print(
                        "PDF rendering failed or lilypond not installed.",
                        file=sys.stderr,
                    )

        if fmt in ("musicxml", "all"):
            xml_path = out if fmt == "musicxml" else out.with_suffix(".musicxml")
            result = score.export_musicxml(xml_path)
            print(f"MusicXML : {result}")

        if fmt in ("midi", "all"):
            mid_path = out if fmt == "midi" else out.with_suffix(".mid")
            result = score.export_midi(mid_path)
            print(f"MIDI     : {result}")

    except Exception as exc:
        print(f"Export error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
