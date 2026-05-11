"""Duration values: whole, half, quarter, eighth, sixteenth, with dots."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DurationValue(str, Enum):
    WHOLE = "whole"
    HALF = "half"
    QUARTER = "quarter"
    EIGHTH = "eighth"
    SIXTEENTH = "sixteenth"
    THIRTY_SECOND = "thirty_second"

    # Dotted variants (1.5× the base)
    DOTTED_WHOLE = "dotted_whole"
    DOTTED_HALF = "dotted_half"
    DOTTED_QUARTER = "dotted_quarter"
    DOTTED_EIGHTH = "dotted_eighth"


# Quarter note = 1 beat (the standard Western music reference unit)
_BASE_BEATS: dict[DurationValue, float] = {
    DurationValue.WHOLE: 4.0,
    DurationValue.HALF: 2.0,
    DurationValue.QUARTER: 1.0,
    DurationValue.EIGHTH: 0.5,
    DurationValue.SIXTEENTH: 0.25,
    DurationValue.THIRTY_SECOND: 0.125,
    DurationValue.DOTTED_WHOLE: 6.0,
    DurationValue.DOTTED_HALF: 3.0,
    DurationValue.DOTTED_QUARTER: 1.5,
    DurationValue.DOTTED_EIGHTH: 0.75,
}

# MusicXML duration type attribute strings
_XML_TYPE: dict[DurationValue, str] = {
    DurationValue.WHOLE: "whole",
    DurationValue.HALF: "half",
    DurationValue.QUARTER: "quarter",
    DurationValue.EIGHTH: "eighth",
    DurationValue.SIXTEENTH: "16th",
    DurationValue.THIRTY_SECOND: "32nd",
    DurationValue.DOTTED_WHOLE: "whole",
    DurationValue.DOTTED_HALF: "half",
    DurationValue.DOTTED_QUARTER: "quarter",
    DurationValue.DOTTED_EIGHTH: "eighth",
}

# MusicXML uses divisions-per-quarter-note ticks.
# We use 24 divisions per quarter (handles down to 32nds cleanly).
DIVISIONS_PER_QUARTER = 24

_DIVISIONS: dict[DurationValue, int] = {
    DurationValue.WHOLE: 96,
    DurationValue.HALF: 48,
    DurationValue.QUARTER: 24,
    DurationValue.EIGHTH: 12,
    DurationValue.SIXTEENTH: 6,
    DurationValue.THIRTY_SECOND: 3,
    DurationValue.DOTTED_WHOLE: 144,
    DurationValue.DOTTED_HALF: 72,
    DurationValue.DOTTED_QUARTER: 36,
    DurationValue.DOTTED_EIGHTH: 18,
}

_SHORTHAND: dict[str, DurationValue] = {
    "w": DurationValue.WHOLE,
    "h": DurationValue.HALF,
    "q": DurationValue.QUARTER,
    "e": DurationValue.EIGHTH,
    "s": DurationValue.SIXTEENTH,
    "whole": DurationValue.WHOLE,
    "half": DurationValue.HALF,
    "quarter": DurationValue.QUARTER,
    "eighth": DurationValue.EIGHTH,
    "sixteenth": DurationValue.SIXTEENTH,
    "32nd": DurationValue.THIRTY_SECOND,
    "thirty_second": DurationValue.THIRTY_SECOND,
    "dotted_whole": DurationValue.DOTTED_WHOLE,
    "dotted whole": DurationValue.DOTTED_WHOLE,
    "dotted_half": DurationValue.DOTTED_HALF,
    "dotted half": DurationValue.DOTTED_HALF,
    "dotted_quarter": DurationValue.DOTTED_QUARTER,
    "dotted quarter": DurationValue.DOTTED_QUARTER,
    "dotted_eighth": DurationValue.DOTTED_EIGHTH,
    "dotted eighth": DurationValue.DOTTED_EIGHTH,
}


@dataclass(frozen=True)
class Duration:
    """A note or rest duration.

    Attributes:
        value: The duration type (e.g. DurationValue.QUARTER).
        beats: Duration in quarter-note beats (derived from value).
    """

    value: DurationValue

    @classmethod
    def parse(cls, text: str) -> "Duration":
        """Parse a duration from a string like 'quarter', 'h', 'dotted_half'."""
        key = text.strip().lower()
        if key not in _SHORTHAND:
            raise ValueError(
                f"Unknown duration: {text!r}. "
                f"Valid values: {sorted(_SHORTHAND.keys())}."
            )
        return cls(value=_SHORTHAND[key])

    @property
    def beats(self) -> float:
        return _BASE_BEATS[self.value]

    @property
    def divisions(self) -> int:
        """MusicXML tick count at DIVISIONS_PER_QUARTER resolution."""
        return _DIVISIONS[self.value]

    @property
    def xml_type(self) -> str:
        return _XML_TYPE[self.value]

    @property
    def is_dotted(self) -> bool:
        return self.value in (
            DurationValue.DOTTED_WHOLE,
            DurationValue.DOTTED_HALF,
            DurationValue.DOTTED_QUARTER,
            DurationValue.DOTTED_EIGHTH,
        )

    @property
    def seconds(self) -> float:
        """Duration in seconds at 120 BPM (caller should scale by actual BPM)."""
        return self.beats * (60.0 / 120.0)

    def seconds_at_bpm(self, bpm: float) -> float:
        return self.beats * (60.0 / bpm) if bpm > 0 else 0.0

    def __str__(self) -> str:
        return self.value.value

    def __repr__(self) -> str:
        return f"Duration({self.value.value!r})"
