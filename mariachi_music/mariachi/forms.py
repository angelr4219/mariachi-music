"""Standardized mariachi genre forms used by the arrangement engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SectionTemplate:
    """A named section with musical role and harmonic plan."""

    label: str
    role: str
    degrees: tuple[int, ...]
    measures_per_chord: int = 1


@dataclass(frozen=True)
class MariachiFormTemplate:
    """High-level form grammar for a mariachi genre."""

    genre: str
    meter: str | tuple[str, ...]
    rhythm_style: str
    feel: str
    default_tempo: int
    full_sections: tuple[SectionTemplate, ...]
    short_sections: tuple[SectionTemplate, ...]
    innovation_allowed: tuple[str, ...]
    innovation_restricted: tuple[str, ...] = ()
    intro_rule: str = ""
    ending_rule: str = ""

    def sections_for_length(self, length: str) -> tuple[SectionTemplate, ...]:
        key = length.strip().lower()
        if key in {"short", "truncated"}:
            return self.short_sections
        if key in {"full", "long"}:
            return self.full_sections
        raise ValueError("length must be 'short' or 'full'.")


SON_FULL = (
    SectionTemplate("A", "instrumental_melody", (1, 5)),
    SectionTemplate("A'", "vocal_verse_melody_variant", (1, 5)),
    SectionTemplate("A'", "vocal_verse_melody_variant", (1, 5)),
    SectionTemplate("B", "vocal_chorus", (4, 5, 1)),
    SectionTemplate("B", "vocal_chorus", (4, 5, 1)),
    SectionTemplate("A", "instrumental_melody", (1, 5)),
    SectionTemplate("A", "instrumental_melody", (1, 5)),
    SectionTemplate("A'", "vocal_verse_melody_variant", (1, 5)),
    SectionTemplate("A'", "vocal_verse_melody_variant", (1, 5)),
    SectionTemplate("B", "vocal_chorus", (4, 5, 1)),
    SectionTemplate("B", "vocal_chorus", (4, 5, 1)),
    SectionTemplate("A''", "truncated_signature_ending", (5, 1)),
)

SON_SHORT = (
    SectionTemplate("A", "instrumental_melody", (1, 5)),
    SectionTemplate("A'", "vocal_verse_melody_variant", (1, 5)),
    SectionTemplate("B", "vocal_chorus", (4, 5, 1)),
    SectionTemplate("A''", "truncated_signature_ending", (5, 1)),
)

BOLERO_FULL = (
    SectionTemplate("A", "instrumental_intro_independent_mood", (1, 4, 5, 1)),
    SectionTemplate("B", "solo_verse", (1, 6, 2, 5)),
    SectionTemplate("B'", "modified_verse", (1, 6, 4, 5)),
    SectionTemplate("C", "vocal_bridge", (4, 5, 3, 6)),
    SectionTemplate("B''", "instrumental_interlude", (1, 6, 2, 5)),
    SectionTemplate("C", "vocal_bridge", (4, 5, 3, 6)),
    SectionTemplate("D", "final_tag", (4, 5, 1)),
)

BOLERO_SHORT = (
    SectionTemplate("A", "instrumental_intro_independent_mood", (1, 5)),
    SectionTemplate("B", "solo_verse", (1, 6, 2, 5)),
    SectionTemplate("C", "vocal_bridge", (4, 5, 1)),
    SectionTemplate("D", "final_tag", (5, 1)),
)

RANCHERA_FULL = (
    SectionTemplate("A", "intro_states_main_melody", (1, 5)),
    SectionTemplate("A'", "intro_repeat_or_lead_in", (5, 1)),
    SectionTemplate("B", "solo_verse", (1, 4, 5, 1)),
    SectionTemplate("B", "solo_verse_repeat", (1, 4, 5, 1)),
    SectionTemplate("C", "harmony_chorus_first_half", (4, 1, 5)),
    SectionTemplate("C'", "harmony_chorus_second_half", (4, 5, 1)),
    SectionTemplate("A", "intro_return", (1, 5)),
    SectionTemplate("A'", "lead_in_return", (5, 1)),
    SectionTemplate("B", "solo_verse", (1, 4, 5, 1)),
    SectionTemplate("B", "solo_verse_repeat", (1, 4, 5, 1)),
    SectionTemplate("C", "harmony_chorus_first_half", (4, 1, 5)),
    SectionTemplate("C''", "final_chorus_ending", (4, 5, 1)),
)

RANCHERA_SHORT = (
    SectionTemplate("A", "intro_states_main_melody", (1, 5)),
    SectionTemplate("B", "solo_verse", (1, 4, 5, 1)),
    SectionTemplate("B", "solo_verse_repeat", (1, 4, 5, 1)),
    SectionTemplate("C", "harmony_chorus", (4, 1, 5)),
    SectionTemplate("C''", "final_chorus_ending", (4, 5, 1)),
)


GENRE_TEMPLATES: dict[str, MariachiFormTemplate] = {
    "son": MariachiFormTemplate(
        genre="son",
        meter=("6/8", "3/4"),
        rhythm_style="son",
        feel="fast_lively_2_against_3",
        default_tempo=132,
        full_sections=SON_FULL,
        short_sections=SON_SHORT,
        innovation_allowed=(
            "melodic_embellishment_during_vocal_sections",
            "small_supporting_line_variations",
        ),
        innovation_restricted=("main_melody_replacement", "core_form_replacement"),
        intro_rule="intro should closely define the main melodic material",
        ending_rule="final A double-prime truncated signature",
    ),
    "bolero": MariachiFormTemplate(
        genre="bolero",
        meter="4/4",
        rhythm_style="bolero",
        feel="romantic_ballad",
        default_tempo=72,
        full_sections=BOLERO_FULL,
        short_sections=BOLERO_SHORT,
        innovation_allowed=(
            "new_intro_that_sets_mood_or_tonality",
            "trumpet_bridge_improvisation",
            "solo_vocal_expression",
        ),
        intro_rule="intro may be independent but should establish key, mood, and contour",
        ending_rule="final tag or held cadence",
    ),
    "ranchera": MariachiFormTemplate(
        genre="ranchera",
        meter="3/4",
        rhythm_style="waltz",
        feel="waltz_like_ranchera",
        default_tempo=132,
        full_sections=RANCHERA_FULL,
        short_sections=RANCHERA_SHORT,
        innovation_allowed=(
            "intro_arrangement_variation",
            "closing_section_variation",
            "vocal_display",
            "supporting_line_embellishment",
        ),
        intro_rule="intro often states the main melody like a son",
        ending_rule="standard 3/4 ranchera ending",
    ),
    "polca_ranchera": MariachiFormTemplate(
        genre="polca_ranchera",
        meter="2/4",
        rhythm_style="waltz",
        feel="polka_like",
        default_tempo=144,
        full_sections=RANCHERA_FULL,
        short_sections=RANCHERA_SHORT,
        innovation_allowed=(
            "intro_arrangement_variation",
            "closing_section_variation",
            "vocal_display",
            "supporting_line_embellishment",
        ),
        intro_rule="intro often states the main melody like a son",
        ending_rule="stylized ritard plus polca signature",
    ),
}


def get_genre_template(genre: str, subtype: str = "") -> MariachiFormTemplate:
    """Return the template for a genre/subtype."""
    key = subtype.strip().lower() or genre.strip().lower()
    if key == "ranchera_3_4":
        key = "ranchera"
    if key not in GENRE_TEMPLATES:
        raise ValueError(f"Unknown mariachi genre {genre!r}. Available: {sorted(GENRE_TEMPLATES)}.")
    return GENRE_TEMPLATES[key]
