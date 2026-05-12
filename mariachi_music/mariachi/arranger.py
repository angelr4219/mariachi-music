"""Generate structured mariachi arrangements from genre/context templates."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from mariachi_music.core.instrument import Instrument
from mariachi_music.core.key_signature import KeySignature
from mariachi_music.core.note import Note, Rest
from mariachi_music.core.part import Part
from mariachi_music.core.score import Score
from mariachi_music.core.tempo import Tempo
from mariachi_music.core.time_signature import TimeSignature
from mariachi_music.generation.rhythm_engine import RhythmPattern
from mariachi_music.mariachi.contexts import ContextRule, get_context_rule
from mariachi_music.mariachi.forms import MariachiFormTemplate, SectionTemplate, get_genre_template
from mariachi_music.theory.chords import Chord, chords_in_key


@dataclass(frozen=True)
class MariachiSongRequest:
    """Inputs to the template arrangement engine."""

    genre: str
    context: str = "restaurant"
    key: str = "G"
    mode: str = "major"
    tempo: float | None = None
    length: str = "full"
    ensemble: tuple[str, ...] | None = None
    subtype: str = ""
    title: str = ""
    composer: str = ""


@dataclass(frozen=True)
class SectionPlan:
    """Concrete section metadata for generated output."""

    index: int
    label: str
    role: str
    degrees: tuple[int, ...]
    roman_numerals: tuple[str, ...]
    start_measure: int
    measure_count: int


@dataclass(frozen=True)
class ArrangementResult:
    """Generated score plus the arrangement grammar used to create it."""

    score: Score
    request: MariachiSongRequest
    template: MariachiFormTemplate
    context_rule: ContextRule
    sections: tuple[SectionPlan, ...]

    def section_map(self) -> dict[str, Any]:
        """Return JSON-friendly section metadata."""
        return {
            "request": asdict(self.request),
            "template": {
                "genre": self.template.genre,
                "meter": self.template.meter,
                "rhythm_style": self.template.rhythm_style,
                "feel": self.template.feel,
                "intro_rule": self.template.intro_rule,
                "ending_rule": self.template.ending_rule,
                "innovation_allowed": list(self.template.innovation_allowed),
                "innovation_restricted": list(self.template.innovation_restricted),
            },
            "context": asdict(self.context_rule),
            "sections": [asdict(section) for section in self.sections],
        }

    def write_section_map(self, path: str | Path) -> Path:
        """Write the section map as JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.section_map(), indent=2), encoding="utf-8")
        return path


def generate_mariachi_arrangement(request: MariachiSongRequest) -> ArrangementResult:
    """Generate a structured mariachi arrangement skeleton.

    This is intentionally a grammar-first arranger. It creates reusable section
    structure, idiomatic rhythm roles, and a believable harmonic/motivic map
    before trying to produce sophisticated melodic composition.
    """
    template = get_genre_template(request.genre, request.subtype)
    context = get_context_rule(request.context)
    sections = template.sections_for_length(_resolve_length(request.length, context))
    instruments = list(request.ensemble or context.typical_instruments)
    tempo = request.tempo if request.tempo is not None else template.default_tempo

    ts = _time_signature_for_template(template)
    pattern = RhythmPattern.from_name(template.rhythm_style)
    key_chords = chords_in_key(request.key, request.mode)

    score = Score(
        title=request.title or _default_title(request, template, context),
        composer=request.composer,
        tempo=Tempo(float(tempo)),
        key_signature=KeySignature(request.key, request.mode),
        time_signature=ts,
    )

    section_plans = _section_plans(sections, key_chords)

    for instrument_name in instruments:
        inst = Instrument.by_name(instrument_name)
        part = Part(instrument=inst, default_ts=ts)
        for section in sections:
            for degree in section.degrees:
                chord = _chord_for_degree(key_chords, degree)
                for _ in range(section.measures_per_chord):
                    events = _events_for_section(pattern, chord, inst, section)
                    _add_events_to_part(part, events)
        score.add_part(part)

    return ArrangementResult(
        score=score,
        request=request,
        template=template,
        context_rule=context,
        sections=tuple(section_plans),
    )


def _resolve_length(length: str, context: ContextRule) -> str:
    key = length.strip().lower()
    if key in {"auto", "context"}:
        return "short" if context.use_truncated_forms is True else "full"
    return key


def _time_signature_for_template(template: MariachiFormTemplate) -> TimeSignature:
    meter = template.meter[0] if isinstance(template.meter, tuple) else template.meter
    return TimeSignature.parse(meter)


def _default_title(
    request: MariachiSongRequest,
    template: MariachiFormTemplate,
    context: ContextRule,
) -> str:
    return (
        f"{request.key} {template.genre.replace('_', ' ').title()} "
        f"({context.name}, {request.length})"
    )


def _section_plans(
    sections: tuple[SectionTemplate, ...],
    key_chords: list[tuple[str, Chord]],
) -> list[SectionPlan]:
    plans: list[SectionPlan] = []
    start = 1
    for index, section in enumerate(sections, 1):
        measure_count = len(section.degrees) * section.measures_per_chord
        romans = tuple(_roman_for_degree(key_chords, degree) for degree in section.degrees)
        plans.append(SectionPlan(
            index=index,
            label=section.label,
            role=section.role,
            degrees=section.degrees,
            roman_numerals=romans,
            start_measure=start,
            measure_count=measure_count,
        ))
        start += measure_count
    return plans


def _chord_for_degree(key_chords: list[tuple[str, Chord]], degree: int) -> Chord:
    if not 1 <= degree <= 7:
        raise ValueError(f"Scale degree {degree} is out of range 1-7.")
    return key_chords[degree - 1][1]


def _roman_for_degree(key_chords: list[tuple[str, Chord]], degree: int) -> str:
    if not 1 <= degree <= 7:
        raise ValueError(f"Scale degree {degree} is out of range 1-7.")
    return key_chords[degree - 1][0]


def _events_for_section(
    pattern: RhythmPattern,
    chord: Chord,
    instrument: Instrument,
    section: SectionTemplate,
) -> list[tuple[str | None, str]]:
    if pattern.time_signature == "2/4":
        return _polca_events(chord, instrument)

    events = pattern.get_notes_for_instrument(chord, instrument)

    # v0 motif logic: keep rhythm roles stable, but nudge melodic sections so
    # A/B/C material is distinguishable while still derived from chord tones.
    if instrument.name in {"Violin", "Trumpet", "Voice", "Generic Treble"}:
        if section.label.startswith("B"):
            return _rotate_pitched_events(events, 1)
        if section.label.startswith("C"):
            return _rotate_pitched_events(events, 2)
        if "ending" in section.role or section.label.endswith("''"):
            return _cadence_events(chord, instrument, pattern)
    return events


def _polca_events(chord: Chord, instrument: Instrument) -> list[tuple[str | None, str]]:
    """Simple 2/4 polca-ranchera pattern."""
    octave = 2 if instrument.clef == "bass" else 3
    pitches = chord.pitches_at_octave(octave)
    root = str(pitches[0])
    fifth = str(pitches[2 if len(pitches) > 2 else 0])
    if instrument.clef == "bass":
        return [(root, "quarter"), (fifth, "quarter")]
    if instrument.name in {"Vihuela", "Guitar"}:
        return [(root, "eighth"), (root, "eighth"), (fifth, "quarter")]
    melody_octave = 4
    melody = chord.pitches_at_octave(melody_octave)
    return [(str(melody[0]), "quarter"), (str(melody[2 if len(melody) > 2 else 0]), "quarter")]


def _rotate_pitched_events(
    events: list[tuple[str | None, str]],
    amount: int,
) -> list[tuple[str | None, str]]:
    pitches = [pitch for pitch, _duration in events if pitch is not None]
    if len(pitches) < 2:
        return events
    rotated = pitches[amount % len(pitches):] + pitches[:amount % len(pitches)]
    pitch_index = 0
    output: list[tuple[str | None, str]] = []
    for pitch, duration in events:
        if pitch is None:
            output.append((None, duration))
        else:
            output.append((rotated[pitch_index], duration))
            pitch_index += 1
    return output


def _cadence_events(
    chord: Chord,
    instrument: Instrument,
    pattern: RhythmPattern,
) -> list[tuple[str | None, str]]:
    pitches = chord.pitches_at_octave(4 if instrument.clef != "bass" else 2)
    root = str(pitches[0])
    fifth = str(pitches[2 if len(pitches) > 2 else 0])
    if pattern.time_signature == "6/8":
        return [(fifth, "eighth"), (None, "eighth"), (root, "quarter"), (root, "quarter")]
    if pattern.time_signature == "3/4":
        return [(fifth, "quarter"), (root, "half")]
    if pattern.time_signature == "2/4":
        return [(fifth, "quarter"), (root, "quarter")]
    return [(fifth, "quarter"), (root, "half"), (None, "quarter")]


def _add_events_to_part(part: Part, events: list[tuple[str | None, str]]) -> None:
    ts = part.default_ts
    for pitch_str, duration in events:
        if pitch_str is None:
            part.add_rest(duration)
        else:
            part.add_note(pitch_str, duration)
        if part.measures and part.measures[-1].is_overfull:
            raise ValueError(f"Generated overfull measure for {part.instrument.name} in {ts}.")
