"""CLI: analyze an audio file — detect tempo, measures, and chords.

Usage::

    # Analyze first 30 seconds of a song
    python -m mariachi_music.cli.analyze_audio song.mp3 --duration 30

    # Analyze in 3/4 time and export as MusicXML
    python -m mariachi_music.cli.analyze_audio song.wav \\
        --beats-per-measure 3 \\
        --output outputs/song_chords \\
        --export-score

    # Include 7th chords in matching and use all mariachi instruments
    python -m mariachi_music.cli.analyze_audio song.mp3 \\
        --extended-chords \\
        --instruments Guitarrón Guitar Vihuela Violin Trumpet \\
        --output outputs/song_full
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mariachi_music.core.instrument import INSTRUMENTS
from mariachi_music.transcription.chord_detector import analyze_audio, analysis_to_score


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mariachi-analyze",
        description=(
            "Analyze an audio file: detect tempo, measure boundaries, "
            "and the chord playing in each measure."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("audio", help="Path to audio file (WAV, MP3, M4A, FLAC, etc.).")
    p.add_argument(
        "--beats-per-measure", type=int, default=4, dest="beats_per_measure",
        help="Beats per measure: 4 for 4/4, 3 for 3/4, etc.",
    )
    p.add_argument(
        "--duration", type=float, default=None, metavar="SECONDS",
        help="Analyze only the first N seconds (default: full file).",
    )
    p.add_argument(
        "--extended-chords", action="store_true", dest="extended",
        help="Also match against 7th chords (dominant7, major7, minor7).",
    )
    p.add_argument(
        "--no-hpss", action="store_true", dest="no_hpss",
        help="Skip harmonic/percussive separation (faster but less accurate).",
    )
    p.add_argument(
        "--min-confidence", type=float, default=0.0, dest="min_confidence",
        help="Skip measures with confidence below this threshold (0.0–1.0).",
    )
    p.add_argument(
        "--export-score", action="store_true", dest="export_score",
        help="Export detected chords as MusicXML + MIDI using instrument voicings.",
    )
    p.add_argument(
        "--instruments", nargs="+",
        default=["Guitarrón", "Guitar", "Violin"],
        choices=sorted(INSTRUMENTS.keys()),
        help="Instruments for score export (used with --export-score).",
    )
    p.add_argument(
        "--key", default="C",
        help="Key signature root for score export (e.g. C, G, Bb).",
    )
    p.add_argument(
        "--mode", default="major", choices=["major", "minor"],
        help="Key mode for score export.",
    )
    p.add_argument(
        "--output", "-o", default=None,
        help="Output path stem for JSON + optional score files.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"Error: file not found: {audio_path}", file=sys.stderr)
        return 1

    print(f"Analyzing: {audio_path.name}")
    if args.duration:
        print(f"  → first {args.duration:.0f} seconds only")
    print(f"  → {args.beats_per_measure}/4 time  |  "
          f"{'with' if not args.no_hpss else 'without'} HPSS  |  "
          f"{'extended ' if args.extended else ''}triads")
    print()

    try:
        analysis = analyze_audio(
            audio_path=audio_path,
            beats_per_measure=args.beats_per_measure,
            use_harmonic_separation=not args.no_hpss,
            extended_chords=args.extended,
            min_confidence=args.min_confidence,
            max_duration_sec=args.duration,
        )
    except Exception as exc:
        print(f"Analysis error: {exc}", file=sys.stderr)
        return 1

    # ── Print results ──────────────────────────────────────────────────────
    print(analysis.summary())
    print()

    # Chord sequence (compact)
    seq = analysis.chord_sequence()
    deduped = [seq[0]] if seq else []
    for c in seq[1:]:
        if c != deduped[-1]:
            deduped.append(c)
    print(f"Chord sequence (deduplicated): {' → '.join(deduped)}")
    print()

    # ── Save JSON ──────────────────────────────────────────────────────────
    if args.output:
        out = Path(args.output)
        json_path = analysis.to_json(out.with_suffix(".json"))
        print(f"JSON saved : {json_path}")

    # ── Export score ───────────────────────────────────────────────────────
    if args.export_score:
        if not args.output:
            print("Error: --output is required when using --export-score.", file=sys.stderr)
            return 1
        try:
            score = analysis_to_score(
                analysis,
                instruments=args.instruments,
                key_root=args.key,
                mode=args.mode,
            )
            out = Path(args.output)
            xml_path = score.export_musicxml(out.with_suffix(".musicxml"))
            mid_path = score.export_midi(out.with_suffix(".mid"))
            print(f"MusicXML   : {xml_path}")
            print(f"MIDI       : {mid_path}")
            print()
            print("Open the MusicXML in MuseScore to see the chord sheet.")
        except Exception as exc:
            print(f"Score export error: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
