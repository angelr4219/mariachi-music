"""Time signature: beats per measure and beat unit."""

from __future__ import annotations

from dataclasses import dataclass


_VALID_BEATS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 12}
_VALID_UNITS = {1, 2, 4, 8, 16}


@dataclass(frozen=True)
class TimeSignature:
    """Time signature such as 4/4, 3/4, 6/8.

    Attributes:
        beats_per_measure: The numerator (e.g. 4 in 4/4).
        beat_unit:         The denominator (e.g. 4 in 4/4, meaning a quarter note = one beat).
    """

    beats_per_measure: int
    beat_unit: int

    def __post_init__(self) -> None:
        if self.beats_per_measure not in _VALID_BEATS:
            raise ValueError(
                f"beats_per_measure={self.beats_per_measure} is unusual. "
                f"Expected one of {sorted(_VALID_BEATS)}."
            )
        if self.beat_unit not in _VALID_UNITS:
            raise ValueError(
                f"beat_unit={self.beat_unit} is not a valid note value denominator. "
                f"Expected one of {sorted(_VALID_UNITS)}."
            )

    @classmethod
    def parse(cls, text: str) -> "TimeSignature":
        """Parse '4/4', '3/4', '6/8', etc."""
        parts = text.strip().split("/")
        if len(parts) != 2:
            raise ValueError(f"Cannot parse time signature: {text!r}. Expected 'n/d' format.")
        try:
            top, bottom = int(parts[0]), int(parts[1])
        except ValueError as exc:
            raise ValueError(f"Non-integer in time signature: {text!r}.") from exc
        return cls(beats_per_measure=top, beat_unit=bottom)

    @property
    def beats_per_measure_in_quarters(self) -> float:
        """How many quarter-note beats fit in one measure (used for overflow checking)."""
        return self.beats_per_measure * (4.0 / self.beat_unit)

    def __str__(self) -> str:
        return f"{self.beats_per_measure}/{self.beat_unit}"


# Common presets
FOUR_FOUR = TimeSignature(4, 4)
THREE_FOUR = TimeSignature(3, 4)
TWO_FOUR = TimeSignature(2, 4)
SIX_EIGHT = TimeSignature(6, 8)
