"""Read-only staff notation renderer using PyQt5 QPainter.

Renders a Score as traditional sheet music:
  - 5-line staff per Part
  - Treble and bass clef symbols
  - Note heads (filled quarter/eighth, open half, large open whole)
  - Stems (up for low notes, down for high notes)
  - Ledger lines
  - Measure barlines
  - Key signature (sharps / flats at start of each system)
  - Time signature numbers
  - Tempo marking at top left
  - Instrument name on the left of each part
  - Multi-part systems stacked vertically
  - Automatic line-wrapping after a configurable number of measures

Usage:
    view = NotationView()
    view.load_score(score)
    scroll_area.setWidget(view)
"""

from __future__ import annotations

import math
from typing import List, Optional

from PyQt5.QtCore import Qt, QRect, QRectF, QPointF, QSizeF, QSize
from PyQt5.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
    QBrush,
)
from PyQt5.QtWidgets import QWidget

from mariachi_music.core.score import Score
from mariachi_music.core.note import Note, Rest
from mariachi_music.core.duration import DurationValue


# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

STAFF_LINE_COUNT = 5
STAFF_LINE_GAP = 10          # pixels between adjacent staff lines
STAFF_HEIGHT = (STAFF_LINE_COUNT - 1) * STAFF_LINE_GAP   # 40 px
STAFF_SPACE = STAFF_LINE_GAP / 2  # half-step = 5 px (one staff position unit)

LEFT_MARGIN = 50             # left edge of page
RIGHT_MARGIN = 30
TOP_MARGIN = 60              # top of first system
SYSTEM_GAP = 60              # vertical gap between systems
PART_GAP = 30                # vertical gap between parts within a system

CLEF_WIDTH = 30              # space reserved for clef drawing
KEYSIG_ACCIDENTAL_WIDTH = 8  # pixels per accidental glyph
TIMESIG_WIDTH = 22           # space reserved for time sig numbers

LABEL_COLUMN_WIDTH = 70      # instrument name column on the left
BEAT_WIDTH = 50              # pixels per quarter-note beat (spacing)
MIN_MEASURE_WIDTH = 40       # minimum width even for empty/rest measures
BARLINE_WIDTH = 2

STEM_LENGTH = STAFF_HEIGHT * 0.75      # 30 px
NOTEHEAD_W = STAFF_LINE_GAP * 1.4     # 14 px
NOTEHEAD_H = STAFF_LINE_GAP * 0.95    # ~9.5 px

# Colours
COLOR_STAFF = QColor(30, 30, 30)
COLOR_NOTE = QColor(10, 10, 10)
COLOR_TEXT = QColor(20, 20, 20)
COLOR_LEDGER = QColor(30, 30, 30)
COLOR_KEYSIG = QColor(20, 20, 20)
COLOR_REST = QColor(30, 30, 30)

# Treble clef staff positions (bottom line = 0, each staff position = +0.5 line)
# Treble clef: bottom line = E4 (MIDI 64)
_TREBLE_BOTTOM_MIDI = 64   # E4

# Bass clef: bottom line = G2 (MIDI 43)
_BASS_BOTTOM_MIDI = 43     # G2

# Sharps order (circle of fifths) for key signature display
_SHARP_NOTES = ["F", "C", "G", "D", "A", "E", "B"]
_FLAT_NOTES  = ["B", "E", "A", "D", "G", "C", "F"]

# Staff positions (in half-steps from bottom line = 0) for each accidental glyph
# Treble clef positions for each sharp/flat note
_TREBLE_SHARP_POSITIONS = {
    "F": 5.0,  # F5 — top line
    "C": 3.5,  # C5 — 3rd space
    "G": 5.5,  # G5 — above top line
    "D": 4.0,  # D5 — 4th space… but conventional: D5 is 4th line = pos 3
    # Use conventional engraving positions:
    "A": 2.5,
    "E": 4.5,
    "B": 1.0,
}
_TREBLE_FLAT_POSITIONS = {
    "B": 3.0,   # B4 — middle line
    "E": 4.5,
    "A": 2.0,
    "D": 3.5,
    "G": 1.5,
    "C": 3.0,
    "F": 2.5,
}
_BASS_SHARP_POSITIONS = {
    "F": 3.0,
    "C": 1.5,
    "G": 3.5,
    "D": 2.0,
    "A": 3.5,
    "E": 2.5,
    "B": 1.0,
}
_BASS_FLAT_POSITIONS = {
    "B": 1.0,
    "E": 2.5,
    "A": 0.5,
    "D": 2.0,
    "G": 0.0,
    "C": 1.5,
    "F": 0.0,
}


# ---------------------------------------------------------------------------
# MIDI → staff position helpers
# ---------------------------------------------------------------------------

def midi_to_staff_position(midi: int, clef: str) -> float:
    """Return staff position for a MIDI note number.

    The return value is measured in *staff-position units* from the bottom
    line of the staff, where:
        0.0  = bottom line (Line 1)
        0.5  = first space
        1.0  = Line 2
        …
        2.0  = middle line (Line 3)
        …
        4.0  = top line (Line 5)

    Positions outside [0, 4] indicate ledger lines above/below.
    """
    if clef == "bass":
        bottom_midi = _BASS_BOTTOM_MIDI
    else:
        bottom_midi = _TREBLE_BOTTOM_MIDI

    # Each semitone does NOT map linearly to staff position — we need
    # diatonic steps.  Map MIDI → diatonic steps above the bottom line.
    # Diatonic scale pattern: W W H W W W H  (2 2 1 2 2 2 1 semitones)
    # We count semitones from the bottom-line pitch.

    delta_semitones = midi - bottom_midi
    # Convert semitones to diatonic steps (half-positions)
    # C major diatonic: C=0, D=2, E=4, F=5, G=7, A=9, B=11 (mod 12)
    # Within each octave the diatonic index advances 0..6 for the 7 notes.
    # Each diatonic step = 0.5 staff-position units.

    octaves, rem = divmod(delta_semitones, 12)
    # Semitone offsets inside an octave → diatonic step index
    _SEMI_TO_DIATONIC = {
        0: 0, 1: 0, 2: 1, 3: 1, 4: 2, 5: 3, 6: 3,
        7: 4, 8: 4, 9: 5, 10: 5, 11: 6,
    }
    diatonic_in_octave = _SEMI_TO_DIATONIC.get(rem, 0)
    total_diatonic = octaves * 7 + diatonic_in_octave

    # Each diatonic step = 0.5 staff position units
    return total_diatonic * 0.5


def staff_y(pos: float, staff_top_y: float) -> float:
    """Convert staff position (from bottom line) to widget Y coordinate.

    pos=0   → bottom line (highest Y)
    pos=4   → top line (lowest Y)
    """
    return staff_top_y + STAFF_HEIGHT - pos * STAFF_LINE_GAP


# ---------------------------------------------------------------------------
# Main Widget
# ---------------------------------------------------------------------------

class NotationView(QWidget):
    """Read-only staff notation renderer.

    Call load_score(score) to display a Score.  The widget resizes itself
    to fit the full score and is designed to be placed inside a QScrollArea.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._score: Score | None = None
        self._measures_per_line: int = 4
        self._layout_cache: list | None = None  # computed by _compute_layout()
        self.setMinimumSize(600, 200)
        self._font_title = QFont("Helvetica", 13, QFont.Bold)
        self._font_body  = QFont("Helvetica", 9)
        self._font_small = QFont("Helvetica", 7)
        self._font_instr = QFont("Helvetica", 8, QFont.Bold)
        self._font_tempo = QFont("Helvetica", 9, QFont.Bold)
        self._font_clef  = QFont("Arial", 28)   # for Unicode clef glyphs
        self._font_timesig = QFont("Helvetica", 14, QFont.Bold)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Qt.white)
        self.setPalette(palette)

    def load_score(self, score: Score) -> None:
        """Render the given Score."""
        self._score = score
        self._layout_cache = None
        self._recompute_size()
        self.update()

    def clear(self) -> None:
        self._score = None
        self._layout_cache = None
        self.update()

    def set_measures_per_line(self, n: int) -> None:
        self._measures_per_line = max(1, n)
        self._layout_cache = None
        self._recompute_size()
        self.update()

    # ------------------------------------------------------------------
    # Layout computation
    # ------------------------------------------------------------------

    def _compute_layout(self) -> list:
        """Return a list of systems.

        Each system is a dict:
          {
            'system_y':     float,            # top Y of this system
            'system_height':float,
            'measures':     list[int],        # 0-based measure indices in this line
            'part_y':       list[float],      # top Y of each part's staff (within system)
            'staff_xs':     (clef_x, notes_x, end_x),
            'measure_xs':   list[(start_x, end_x)],   # one per measure in this system
          }
        """
        if self._score is None:
            return []

        score = self._score
        if not score.parts:
            return []

        # Total measures — use the first part as the reference
        n_measures = max(len(p.measures) for p in score.parts)
        if n_measures == 0:
            return []

        widget_width = max(self.width(), 600)
        usable_width = widget_width - LEFT_MARGIN - RIGHT_MARGIN - LABEL_COLUMN_WIDTH

        mpl = self._measures_per_line

        # Build systems
        systems = []
        current_y = TOP_MARGIN

        # Title height
        current_y += 30  # space for title

        measure_idx = 0
        while measure_idx < n_measures:
            measures_in_line = list(range(measure_idx, min(measure_idx + mpl, n_measures)))
            measure_idx += len(measures_in_line)

            # Compute prefix widths for this system (only first system gets full prefix)
            is_first_system = (len(systems) == 0)
            prefix_w = self._prefix_width(score, is_first_system)

            # Width for each measure
            avail_for_measures = usable_width - prefix_w
            n_m = len(measures_in_line)
            measure_width = max(MIN_MEASURE_WIDTH, avail_for_measures / max(n_m, 1))

            # X positions
            notes_start_x = LEFT_MARGIN + LABEL_COLUMN_WIDTH + prefix_w
            measure_xs = []
            x = notes_start_x
            for _ in measures_in_line:
                measure_xs.append((x, x + measure_width))
                x += measure_width

            # Y positions for each part within this system
            n_parts = len(score.parts)
            system_height = (
                n_parts * STAFF_HEIGHT
                + (n_parts - 1) * PART_GAP
                + 30  # top padding for clef/timesig overflow
            )
            part_y = []
            py = current_y + 20  # small top padding
            for _ in range(n_parts):
                part_y.append(py)
                py += STAFF_HEIGHT + PART_GAP

            systems.append({
                'system_y': current_y,
                'system_height': system_height,
                'measures': measures_in_line,
                'part_y': part_y,
                'prefix_w': prefix_w,
                'notes_start_x': notes_start_x,
                'measure_xs': measure_xs,
                'is_first_system': is_first_system,
            })

            current_y += system_height + SYSTEM_GAP

        return systems

    def _prefix_width(self, score: Score, is_first_system: bool) -> float:
        """Width of clef + key sig + time sig prefix before notes."""
        key_acc_count = abs(score.key_signature.fifths)
        w = CLEF_WIDTH + key_acc_count * KEYSIG_ACCIDENTAL_WIDTH + 6
        if is_first_system:
            w += TIMESIG_WIDTH
        return w

    def _recompute_size(self) -> None:
        if self._score is None:
            self.setMinimumHeight(200)
            return
        layout = self._compute_layout()
        self._layout_cache = layout
        if not layout:
            self.setMinimumHeight(200)
            return
        last = layout[-1]
        total_h = last['system_y'] + last['system_height'] + TOP_MARGIN
        self.setMinimumHeight(int(total_h) + 20)
        self.resize(self.width(), int(total_h) + 20)

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.fillRect(self.rect(), Qt.white)

        if self._score is None:
            painter.setPen(COLOR_TEXT)
            painter.setFont(self._font_body)
            painter.drawText(self.rect(), Qt.AlignCenter, "No score loaded.")
            painter.end()
            return

        score = self._score

        # Recompute layout if needed
        if self._layout_cache is None:
            self._layout_cache = self._compute_layout()

        layout = self._layout_cache

        # --- Title & Composer ---
        self._draw_title(painter, score)

        # --- Systems ---
        for system in layout:
            self._draw_system(painter, score, system)

        painter.end()

    def _draw_title(self, painter: QPainter, score: Score) -> None:
        painter.save()
        painter.setFont(self._font_title)
        painter.setPen(COLOR_TEXT)
        title_rect = QRect(LEFT_MARGIN, 10, self.width() - LEFT_MARGIN - RIGHT_MARGIN, 25)
        painter.drawText(title_rect, Qt.AlignHCenter | Qt.AlignTop, score.title)

        if score.composer:
            painter.setFont(self._font_body)
            comp_rect = QRect(LEFT_MARGIN, 30, self.width() - LEFT_MARGIN - RIGHT_MARGIN, 18)
            painter.drawText(comp_rect, Qt.AlignRight | Qt.AlignTop, score.composer)

        painter.restore()

    def _draw_system(self, painter: QPainter, score: Score, system: dict) -> None:
        measures_in_line = system['measures']
        part_y_list = system['part_y']
        notes_start_x = system['notes_start_x']
        measure_xs = system['measure_xs']
        is_first = system['is_first_system']
        prefix_w = system['prefix_w']

        n_parts = len(score.parts)

        # --- Tempo marking (first system only, above first staff) ---
        if is_first:
            self._draw_tempo(painter, score, part_y_list[0] if part_y_list else TOP_MARGIN + 20)

        # --- System bracket (curly brace on far left) ---
        if n_parts > 1:
            self._draw_system_bracket(
                painter,
                LEFT_MARGIN + LABEL_COLUMN_WIDTH - 12,
                part_y_list[0],
                part_y_list[-1] + STAFF_HEIGHT,
            )

        # --- Per-part rendering ---
        for pi, part in enumerate(score.parts):
            staff_top = part_y_list[pi]

            # Instrument label
            self._draw_instrument_label(painter, part.instrument.name, staff_top)

            # Staff lines
            clef_x = LEFT_MARGIN + LABEL_COLUMN_WIDTH
            self._draw_staff_lines(painter, clef_x, staff_top,
                                   notes_start_x + sum(x[1] - x[0] for x in measure_xs) - clef_x)

            # Clef
            clef_draw_x = clef_x + 4
            self._draw_clef(painter, part.instrument.clef, clef_draw_x, staff_top)

            # Key signature
            keysig_x = clef_x + CLEF_WIDTH + 2
            keysig_width = self._draw_key_signature(
                painter, score.key_signature, part.instrument.clef, keysig_x, staff_top
            )

            # Time signature (first system only)
            timesig_x = keysig_x + keysig_width + 4
            if is_first:
                self._draw_time_signature(painter, score.time_signature, timesig_x, staff_top)

            # Notes and barlines for each measure in this system
            for mi, m_idx in enumerate(measures_in_line):
                mx_start, mx_end = measure_xs[mi]

                # Get the measure for this part (may be absent if parts differ in length)
                if m_idx < len(part.measures):
                    measure = part.measures[m_idx]
                else:
                    measure = None

                # Draw barline at start (only after first measure column)
                if mi == 0:
                    painter.save()
                    painter.setPen(QPen(COLOR_STAFF, BARLINE_WIDTH))
                    painter.drawLine(int(mx_start), int(staff_top),
                                     int(mx_start), int(staff_top + STAFF_HEIGHT))
                    painter.restore()

                # Draw events inside measure
                if measure is not None:
                    self._draw_measure_events(
                        painter, measure, part.instrument.clef,
                        mx_start, mx_end, staff_top, score.time_signature
                    )

                # Draw barline at end of measure
                painter.save()
                painter.setPen(QPen(COLOR_STAFF, BARLINE_WIDTH))
                # Double barline on final measure
                if mi == len(measures_in_line) - 1 and m_idx == max(len(p.measures) for p in score.parts) - 1:
                    painter.drawLine(int(mx_end) - 3, int(staff_top),
                                     int(mx_end) - 3, int(staff_top + STAFF_HEIGHT))
                    painter.setPen(QPen(COLOR_STAFF, 3))
                    painter.drawLine(int(mx_end), int(staff_top),
                                     int(mx_end), int(staff_top + STAFF_HEIGHT))
                else:
                    painter.drawLine(int(mx_end), int(staff_top),
                                     int(mx_end), int(staff_top + STAFF_HEIGHT))
                painter.restore()

    # ------------------------------------------------------------------
    # Individual drawing helpers
    # ------------------------------------------------------------------

    def _draw_staff_lines(self, painter: QPainter, x: float, staff_top: float, width: float) -> None:
        painter.save()
        pen = QPen(COLOR_STAFF, 1)
        painter.setPen(pen)
        for i in range(STAFF_LINE_COUNT):
            y = staff_top + i * STAFF_LINE_GAP
            painter.drawLine(int(x), int(y), int(x + width), int(y))
        painter.restore()

    def _draw_clef(self, painter: QPainter, clef: str, x: float, staff_top: float) -> None:
        """Draw a simplified clef symbol."""
        painter.save()
        if clef == "treble":
            # Try to draw Unicode treble clef glyph
            # The treble clef glyph: 𝄞 (U+1D11E) — may not render in all fonts
            # Fallback: draw a simplified G-clef using QPainterPath
            painter.setFont(self._font_clef)
            painter.setPen(COLOR_TEXT)
            # The glyph sits on the second line from bottom (G4 line)
            # Anchor point: slightly below the top line
            glyph_y = int(staff_top + STAFF_HEIGHT + 10)
            glyph_rect = QRect(int(x) - 2, int(staff_top) - 8, 28, STAFF_HEIGHT + 20)
            # Try Unicode music font glyph first
            painter.drawText(glyph_rect, Qt.AlignLeft | Qt.AlignVCenter, "\U0001D11E")

        elif clef == "bass":
            painter.setFont(self._font_clef)
            painter.setPen(COLOR_TEXT)
            glyph_rect = QRect(int(x) - 2, int(staff_top) - 4, 28, STAFF_HEIGHT + 10)
            painter.drawText(glyph_rect, Qt.AlignLeft | Qt.AlignVCenter, "\U0001D122")

        elif clef in ("alto", "tenor"):
            # B-clef glyph: 𝄡
            painter.setFont(self._font_clef)
            painter.setPen(COLOR_TEXT)
            glyph_rect = QRect(int(x) - 2, int(staff_top) - 4, 28, STAFF_HEIGHT + 8)
            painter.drawText(glyph_rect, Qt.AlignLeft | Qt.AlignVCenter, "\U0001D121")

        painter.restore()

    def _draw_key_signature(
        self, painter: QPainter, ks, clef: str, x: float, staff_top: float
    ) -> float:
        """Draw sharp or flat symbols for the key signature.  Returns width used."""
        fifths = ks.fifths
        if fifths == 0:
            return 0.0

        painter.save()
        painter.setPen(QPen(COLOR_KEYSIG, 1))

        is_sharp = fifths > 0
        count = abs(fifths)
        notes = _SHARP_NOTES[:count] if is_sharp else _FLAT_NOTES[:count]
        pos_map = (
            (_TREBLE_SHARP_POSITIONS if is_sharp else _TREBLE_FLAT_POSITIONS)
            if clef != "bass"
            else (_BASS_SHARP_POSITIONS if is_sharp else _BASS_FLAT_POSITIONS)
        )
        glyph = "#" if is_sharp else "b"
        font = QFont("Helvetica", 10, QFont.Bold)
        painter.setFont(font)

        dx = 0.0
        for note_name in notes:
            pos = pos_map.get(note_name, 2.0)
            cy = staff_y(pos, staff_top) - 2
            painter.drawText(int(x + dx), int(cy), glyph)
            dx += KEYSIG_ACCIDENTAL_WIDTH

        painter.restore()
        return dx + 4

    def _draw_time_signature(self, painter: QPainter, ts, x: float, staff_top: float) -> None:
        painter.save()
        painter.setFont(self._font_timesig)
        painter.setPen(COLOR_TEXT)
        # Numerator on top half, denominator on bottom half
        top_y = int(staff_top)
        mid_y = int(staff_top + STAFF_HEIGHT / 2)
        r_top = QRect(int(x), top_y, TIMESIG_WIDTH, STAFF_HEIGHT // 2)
        r_bot = QRect(int(x), mid_y, TIMESIG_WIDTH, STAFF_HEIGHT // 2)
        painter.drawText(r_top, Qt.AlignHCenter | Qt.AlignVCenter, str(ts.numerator))
        painter.drawText(r_bot, Qt.AlignHCenter | Qt.AlignVCenter, str(ts.denominator))
        painter.restore()

    def _draw_tempo(self, painter: QPainter, score: Score, staff_top_y: float) -> None:
        painter.save()
        painter.setFont(self._font_tempo)
        painter.setPen(COLOR_TEXT)
        tempo_str = f"♩ = {int(score.tempo.bpm)}"
        painter.drawText(int(LEFT_MARGIN + LABEL_COLUMN_WIDTH), int(staff_top_y) - 4, tempo_str)
        painter.restore()

    def _draw_instrument_label(self, painter: QPainter, name: str, staff_top: float) -> None:
        painter.save()
        painter.setFont(self._font_instr)
        painter.setPen(COLOR_TEXT)
        rect = QRect(LEFT_MARGIN, int(staff_top), LABEL_COLUMN_WIDTH - 4, STAFF_HEIGHT)
        painter.drawText(rect, Qt.AlignRight | Qt.AlignVCenter, name)
        painter.restore()

    def _draw_system_bracket(
        self, painter: QPainter, x: float, top_y: float, bottom_y: float
    ) -> None:
        """Draw a simple square bracket on the left side spanning all parts."""
        painter.save()
        pen = QPen(COLOR_STAFF, 2)
        painter.setPen(pen)
        # Vertical bar
        painter.drawLine(int(x), int(top_y), int(x), int(bottom_y))
        # Top hook
        painter.drawLine(int(x), int(top_y), int(x + 6), int(top_y))
        # Bottom hook
        painter.drawLine(int(x), int(bottom_y), int(x + 6), int(bottom_y))
        painter.restore()

    def _draw_measure_events(
        self,
        painter: QPainter,
        measure,
        clef: str,
        x_start: float,
        x_end: float,
        staff_top: float,
        time_sig,
    ) -> None:
        """Draw all notes and rests within one measure."""
        usable_width = x_end - x_start
        total_beats = time_sig.beats_per_measure_in_quarters or 4.0
        if total_beats <= 0:
            total_beats = 4.0
        pixels_per_beat = usable_width / total_beats

        beat_cursor = 0.0
        for event in measure.events:
            note_x = x_start + beat_cursor * pixels_per_beat + 4

            if isinstance(event, Note):
                self._draw_note(painter, event, clef, note_x, staff_top)
            elif isinstance(event, Rest):
                self._draw_rest(painter, event, note_x, staff_top, pixels_per_beat)

            beat_cursor += event.beats

    def _draw_note(
        self, painter: QPainter, note: Note, clef: str, x: float, staff_top: float
    ) -> None:
        """Draw a single note: head, stem, accidental, ledger lines."""
        midi = note.midi_number
        pos = midi_to_staff_position(midi, clef)
        cy = staff_y(pos, staff_top)

        dv = note.duration.value
        is_whole   = dv == DurationValue.WHOLE
        is_half    = dv in (DurationValue.HALF, DurationValue.DOTTED_HALF, DurationValue.DOTTED_WHOLE)
        is_filled  = dv in (
            DurationValue.QUARTER, DurationValue.EIGHTH, DurationValue.SIXTEENTH,
            DurationValue.THIRTY_SECOND,
            DurationValue.DOTTED_QUARTER, DurationValue.DOTTED_EIGHTH,
        )

        painter.save()
        painter.setPen(QPen(COLOR_NOTE, 1.2))

        # --- Ledger lines ---
        self._draw_ledger_lines(painter, pos, x, staff_top)

        # --- Accidental ---
        accidental = note.pitch.accidental
        if accidental in ("#", "b", "n", "##", "bb"):
            self._draw_accidental(painter, accidental, x, cy)

        # --- Notehead ---
        nx = x + NOTEHEAD_W * 0.1
        if is_whole:
            # Large open oval
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(COLOR_NOTE, 1.5))
            painter.drawEllipse(
                QRectF(nx - NOTEHEAD_W * 0.1, cy - NOTEHEAD_H * 0.7,
                       NOTEHEAD_W * 1.3, NOTEHEAD_H * 1.4)
            )
        elif is_half:
            # Open oval (filled with white)
            painter.setBrush(QBrush(Qt.white))
            painter.setPen(QPen(COLOR_NOTE, 1.5))
            painter.drawEllipse(
                QRectF(nx, cy - NOTEHEAD_H / 2, NOTEHEAD_W, NOTEHEAD_H)
            )
        else:
            # Filled oval
            painter.setBrush(QBrush(COLOR_NOTE))
            painter.setPen(QPen(COLOR_NOTE, 1))
            painter.drawEllipse(
                QRectF(nx, cy - NOTEHEAD_H / 2, NOTEHEAD_W, NOTEHEAD_H)
            )

        # --- Dot for dotted durations ---
        if note.duration.is_dotted:
            dot_x = nx + NOTEHEAD_W + 3
            dot_y = cy - 2  # nudge dot up if note is on a line
            if abs(pos % 0.5) < 0.1:  # on a line → nudge dot into space above
                dot_y -= STAFF_SPACE * 0.5
            painter.setBrush(QBrush(COLOR_NOTE))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(dot_x, dot_y - 2, 3, 3))

        # --- Stem (not for whole notes) ---
        if not is_whole:
            # Stem goes up if note is on or below middle line (pos <= 2),
            # down if note is above middle line (pos > 2)
            middle_pos = 2.0
            stem_head_x = nx + NOTEHEAD_W if pos <= middle_pos else nx
            if pos <= middle_pos:
                # Stem up: from right side of notehead, upward
                stem_top = cy - STEM_LENGTH
                stem_bot = cy - NOTEHEAD_H / 2
                painter.setPen(QPen(COLOR_NOTE, 1.2))
                painter.drawLine(
                    QPointF(stem_head_x, stem_bot),
                    QPointF(stem_head_x, stem_top),
                )
            else:
                # Stem down: from left side of notehead, downward
                stem_top = cy + NOTEHEAD_H / 2
                stem_bot = cy + STEM_LENGTH
                painter.setPen(QPen(COLOR_NOTE, 1.2))
                painter.drawLine(
                    QPointF(stem_head_x, stem_top),
                    QPointF(stem_head_x, stem_bot),
                )

            # --- Flags for eighth and shorter ---
            if dv in (DurationValue.EIGHTH, DurationValue.DOTTED_EIGHTH):
                self._draw_flag(painter, 1, stem_head_x, cy, pos <= middle_pos)
            elif dv == DurationValue.SIXTEENTH:
                self._draw_flag(painter, 2, stem_head_x, cy, pos <= middle_pos)
            elif dv == DurationValue.THIRTY_SECOND:
                self._draw_flag(painter, 3, stem_head_x, cy, pos <= middle_pos)

        painter.restore()

    def _draw_flag(
        self, painter: QPainter, count: int, stem_x: float, cy: float, stem_up: bool
    ) -> None:
        """Draw 1, 2, or 3 flags on a stem."""
        if stem_up:
            flag_y_start = cy - STEM_LENGTH
            dy = 7
        else:
            flag_y_start = cy + STEM_LENGTH
            dy = -7

        painter.setPen(QPen(COLOR_NOTE, 1.2))
        for i in range(count):
            fy = flag_y_start + i * dy
            # Simple bezier-like arc flag
            path = QPainterPath()
            path.moveTo(stem_x, fy)
            ctrl_x = stem_x + 12
            ctrl_y = fy + (10 if stem_up else -10)
            end_x  = stem_x + 4
            end_y  = fy + (18 if stem_up else -18)
            path.quadTo(ctrl_x, ctrl_y, end_x, end_y)
            painter.drawPath(path)

    def _draw_ledger_lines(
        self, painter: QPainter, pos: float, x: float, staff_top: float
    ) -> None:
        """Draw ledger lines for notes above or below the staff."""
        painter.save()
        painter.setPen(QPen(COLOR_LEDGER, 1))
        lw = NOTEHEAD_W + 6  # ledger line extends past notehead
        lx = x - 2

        # Below staff: pos < 0  (bottom line = 0, below = negative)
        if pos < 0:
            # Draw ledger lines at each even half-step below the staff
            p = 0.0
            while p > pos - 0.1:
                if p <= pos + 0.1:
                    ly = staff_y(p, staff_top)
                    painter.drawLine(int(lx), int(ly), int(lx + lw), int(ly))
                p -= 1.0

        # Above staff: pos > 4
        if pos > 4.0:
            p = 4.0
            while p < pos + 0.1:
                if p >= pos - 0.1:
                    ly = staff_y(p, staff_top)
                    painter.drawLine(int(lx), int(ly), int(lx + lw), int(ly))
                p += 1.0

        # Special case: middle C (one ledger line below treble staff, pos ≈ -1)
        # Already handled above generically.

        painter.restore()

    def _draw_accidental(
        self, painter: QPainter, accidental: str, x: float, cy: float
    ) -> None:
        painter.save()
        font = QFont("Helvetica", 9, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QPen(COLOR_NOTE, 1))
        glyph_map = {
            "#": "#",
            "b": "b",
            "n": "♮",
            "##": "x",
            "bb": "bb",
        }
        glyph = glyph_map.get(accidental, accidental)
        painter.drawText(int(x) - 10, int(cy) + 4, glyph)
        painter.restore()

    def _draw_rest(
        self,
        painter: QPainter,
        rest: Rest,
        x: float,
        staff_top: float,
        pixels_per_beat: float,
    ) -> None:
        """Draw a rest symbol appropriate to the duration."""
        dv = rest.duration.value
        cx = x + 6
        mid_y = staff_y(2.0, staff_top)   # middle line Y

        painter.save()
        painter.setPen(QPen(COLOR_REST, 1.5))
        painter.setBrush(QBrush(COLOR_REST))

        if dv == DurationValue.WHOLE:
            # Whole rest: filled rectangle hanging from 4th line
            ry = staff_y(3.0, staff_top)   # 4th line (0-indexed pos=3)
            painter.drawRect(int(cx), int(ry), 14, 5)

        elif dv in (DurationValue.HALF, DurationValue.DOTTED_HALF):
            # Half rest: filled rectangle sitting on 3rd line
            ry = mid_y - 5
            painter.drawRect(int(cx), int(ry), 14, 5)

        elif dv in (DurationValue.QUARTER, DurationValue.DOTTED_QUARTER):
            # Quarter rest: squiggly (simplified as a zigzag line)
            self._draw_quarter_rest(painter, cx, mid_y)

        elif dv in (DurationValue.EIGHTH, DurationValue.DOTTED_EIGHTH):
            # Eighth rest: single flag shape
            painter.setPen(QPen(COLOR_REST, 1.5))
            painter.setBrush(Qt.NoBrush)
            path = QPainterPath()
            path.moveTo(cx + 4, mid_y - 8)
            path.lineTo(cx + 4, mid_y + 6)
            painter.drawPath(path)
            painter.setBrush(QBrush(COLOR_REST))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(cx, mid_y - 12, 8, 8))

        elif dv == DurationValue.SIXTEENTH:
            # Sixteenth rest: two flag shapes (simplified)
            painter.setPen(QPen(COLOR_REST, 1.5))
            painter.setBrush(Qt.NoBrush)
            path = QPainterPath()
            path.moveTo(cx + 4, mid_y - 12)
            path.lineTo(cx + 4, mid_y + 6)
            painter.drawPath(path)
            painter.setBrush(QBrush(COLOR_REST))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(cx, mid_y - 16, 8, 8))
            painter.drawEllipse(QRectF(cx + 4, mid_y - 8, 8, 8))

        else:
            # Fallback: draw "R" text
            painter.setPen(QPen(COLOR_REST, 1))
            painter.setFont(self._font_small)
            painter.drawText(int(cx), int(mid_y) + 4, "R")

        # Dot for dotted rests
        if rest.duration.is_dotted:
            painter.setBrush(QBrush(COLOR_REST))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(cx + 18, mid_y - 4, 3, 3))

        painter.restore()

    def _draw_quarter_rest(self, painter: QPainter, cx: float, cy: float) -> None:
        """Draw a simplified quarter rest as a small zigzag."""
        painter.setPen(QPen(COLOR_REST, 1.5))
        painter.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(cx + 8, cy - 10)
        path.lineTo(cx + 2, cy - 4)
        path.lineTo(cx + 10, cy + 2)
        path.lineTo(cx + 4, cy + 8)
        path.lineTo(cx + 6, cy + 14)
        painter.drawPath(path)
        # Small dot at the hook
        painter.setBrush(QBrush(COLOR_REST))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(cx + 2, cy - 6, 5, 5))

    # ------------------------------------------------------------------
    # Size hint
    # ------------------------------------------------------------------

    def sizeHint(self) -> QSize:
        return QSize(800, max(400, self.minimumHeight()))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._layout_cache = None
        self._recompute_size()
