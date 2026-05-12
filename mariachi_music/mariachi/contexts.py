"""Performance-context rules for mariachi arrangement generation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextRule:
    """How performance context affects arrangement choices."""

    name: str
    ensemble_size: str
    typical_instruments: tuple[str, ...]
    arrangement_length: str
    use_truncated_forms: bool | str
    innovation_level: str
    standardization: str


CONTEXT_RULES: dict[str, ContextRule] = {
    "cantina": ContextRule(
        name="cantina",
        ensemble_size="small",
        typical_instruments=("Guitarrón", "Vihuela", "Trumpet", "Violin"),
        arrangement_length="short",
        use_truncated_forms=True,
        innovation_level="low",
        standardization="high",
    ),
    "restaurant": ContextRule(
        name="restaurant",
        ensemble_size="medium",
        typical_instruments=(
            "Guitarrón", "Vihuela", "Guitar", "Trumpet", "Trumpet", "Violin", "Violin",
        ),
        arrangement_length="medium_or_full",
        use_truncated_forms="sometimes",
        innovation_level="medium",
        standardization="medium_high",
    ),
    "restaurant_or_private_party": ContextRule(
        name="restaurant_or_private_party",
        ensemble_size="medium",
        typical_instruments=(
            "Guitarrón", "Vihuela", "Guitar", "Trumpet", "Trumpet", "Violin", "Violin",
        ),
        arrangement_length="medium_or_full",
        use_truncated_forms="sometimes",
        innovation_level="medium",
        standardization="medium_high",
    ),
    "show": ContextRule(
        name="show",
        ensemble_size="large",
        typical_instruments=(
            "Guitarrón", "Vihuela", "Guitar", "Trumpet", "Trumpet",
            "Violin", "Violin", "Violin", "Voice",
        ),
        arrangement_length="long",
        use_truncated_forms=False,
        innovation_level="high_but_rehearsed",
        standardization="arranged",
    ),
    "show_or_concert": ContextRule(
        name="show_or_concert",
        ensemble_size="large",
        typical_instruments=(
            "Guitarrón", "Vihuela", "Guitar", "Trumpet", "Trumpet",
            "Violin", "Violin", "Violin", "Voice",
        ),
        arrangement_length="long",
        use_truncated_forms=False,
        innovation_level="high_but_rehearsed",
        standardization="arranged",
    ),
}


def get_context_rule(name: str) -> ContextRule:
    """Return a context rule by name."""
    key = name.strip().lower()
    if key not in CONTEXT_RULES:
        raise ValueError(f"Unknown mariachi context {name!r}. Available: {sorted(CONTEXT_RULES)}.")
    return CONTEXT_RULES[key]
