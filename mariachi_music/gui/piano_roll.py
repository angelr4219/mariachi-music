"""Interactive piano roll editor widget for the Mariachi Music score engine.

Renders a pitch-vs-time grid using QPainter, supports full mouse editing
(create, select, drag, delete), and operates directly on a Part object so
all edits are live and immediately reflected in the data model.
"""

from __future__ import annotations

from PyQt5.QtCore import (
    Qt,
    QPoint,
    QRect,
    QSize,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPen,
    QWheelEvent,
    QKeyEvent,
    QMouseEvent,
    QPaintEvent,
)
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from mariachi_music.core.instrument import INSTRUMENTS, Instrument
from mariachi_music.core.measure import Measure
from mariachi_music.core.note import Note, Rest, NoteOrRest
from mariachi_music.core.part import Part
from mariachi_music.core.pitch import Pitch
from mariachi_music.core.duration import Duration, DurationValue
from mariachi_music.core.time_signature import TimeSignature

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

MIDI_MIN = 21       # A0
MIDI_MAX = 108      # C8
SEMITONE_HEIGHT = 14   # pixels per semitone row
KEY_LABEL_WIDTH = 48   # pixels for the piano key label column on the left
HEADER_HEIGHT = 32     # pixels for the time ruler at the top
DEFAULT_BEAT_WIDTH = 80  # pixels per quarter-note beat
SNAP_SUBDIVISIONS = 4   # default quantise grid: 1/4 of a beat

# MIDI pitch → whether it is a black key (semitone within octave)
_BLACK_KEY_SEMITONES = {1, 3, 6, 8, 10}   # C#, D#, F#, G#, A#

# Colour palette for instruments (cycles if more than len instruments)
_INSTRUMENT_COLORS: list[QColor] = [
    QColor(70, 130, 200),    # steel blue
    QColor(200, 80, 60),     # warm red
    QColor(80, 170, 100),    # medium green
    QColor(200, 150, 40),    # amber
    QColor(150, 80, 200),    # purple
    QColor(60, 185, 185),    # teal
    QColor(220, 110, 170),   # rose
    QColor(110, 130, 80),    # olive
]

# Duration display labels for the toolbar buttons
_DURATION_LABELS = ["Whole", "Half", "Quarter", "Eighth", "16th"]
_DURATION_STRINGS = ["whole", "half", "quarter", "eighth", "sixteenth"]
_DURATION_BEATS = [4.0, 2.0, 1.0, 0.5, 0.25]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _is_black_key(midi: int) -> bool:
    """Return True when the given MIDI note corresponds to a black piano key."""
    return (midi % 12) in _BLACK_KEY_SEMITONES


def _pitch_label(midi: int) -> str:
    """Return a human-readable label for a MIDI note (e.g. 'C4', 'F#5')."""
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octave = midi // 12 - 1
    name = names[midi % 12]
    # Only label C notes and a few others to reduce clutter
    return f"{name}{octave}"


def _should_show_label(midi: int) -> bool:
    """Return True for C notes and every other white key — reduces label clutter."""
    return (midi % 12) == 0   # Only show Cx labels


# ---------------------------------------------------------------------------
# NoteData: lightweight record stored per visible note
# ---------------------------------------------------------------------------

class _NoteData:
    """Internal record tracking a rendered note, its Part location, and rect."""

    __slots__ = ("note", "measure_idx", "event_idx", "beat_start", "rect")

    def __init__(
        self,
        note: Note,
        measure_idx: int,
        event_idx: int,
        beat_start: float,
        rect: QRect,
    ) -> None:
        self.note = note
        self.measure_idx = measure_idx
        self.event_idx = event_idx
        self.beat_start = beat_start   # absolute beat position (from score start)
        self.rect = rect


# ---------------------------------------------------------------------------
# PianoRollCanvas — the actual drawing + interaction surface
# ---------------------------------------------------------------------------

class PianoRollCanvas(QWidget):
    """The inner drawing surface of the piano roll.

    This widget is placed inside a scroll area managed by PianoRollWidget.
    It handles all QPainter rendering and mouse-based editing interactions.

    Signals:
        notes_changed: Emitted after any note creation, deletion, or move.
        status_message: Short string suitable for a status bar.
    """

    notes_changed = pyqtSignal()
    status_message = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # Data
        self._part: Part | None = None
        self._note_records: list[_NoteData] = []

        # Display settings
        self._beat_width = DEFAULT_BEAT_WIDTH
        self._quantise = True
        self._selected_duration = "quarter"
        self._selected_duration_beats = 1.0

        # Instrument → colour mapping
        self._color_cache: dict[str, QColor] = {}
        self._color_index = 0

        # Drag state
        self._drag_note: _NoteData | None = None
        self._drag_origin_px: QPoint = QPoint()
        self._drag_origin_beat: float = 0.0
        self._drag_origin_midi: int = 0
        self._dragging: bool = False
        self._drag_threshold = 4   # pixels before we commit to dragging

        # Hover / selection
        self._hovered_note: _NoteData | None = None
        self._selected_note: _NoteData | None = None

        # Canvas geometry will be recalculated in _recalc_size()
        self._total_beats: float = 32.0   # default before any part is loaded
        self._beats_per_measure: float = 4.0
        self._recalc_size()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_part(self, part: Part) -> None:
        """Load a Part object and rebuild the internal note list.

        Args:
            part: The Part to render and edit.  All mutations go directly
                  into this object's measures/events.
        """
        self._part = part
        self._selected_note = None
        self._hovered_note = None
        self._drag_note = None
        self._color_cache.clear()
        self._color_index = 0
        self._beats_per_measure = part.default_ts.beats_per_measure_in_quarters
        self._rebuild_note_records()
        self._recalc_size()
        self.update()

    def set_beat_width(self, width: int) -> None:
        """Set horizontal zoom: pixels per quarter-note beat."""
        self._beat_width = max(20, min(300, width))
        self._rebuild_note_records()
        self._recalc_size()
        self.update()

    def set_quantise(self, enabled: bool) -> None:
        """Enable or disable snap-to-grid."""
        self._quantise = enabled

    def set_selected_duration(self, duration_str: str, beats: float) -> None:
        """Set which duration will be used when the user creates new notes."""
        self._selected_duration = duration_str
        self._selected_duration_beats = beats

    def get_beat_width(self) -> int:
        """Return current horizontal zoom in pixels per beat."""
        return self._beat_width

    # ------------------------------------------------------------------
    # Coordinate conversion
    # ------------------------------------------------------------------

    def _beat_to_x(self, beat: float) -> int:
        """Convert an absolute beat position to a canvas x-coordinate."""
        return KEY_LABEL_WIDTH + int(beat * self._beat_width)

    def _x_to_beat(self, x: int) -> float:
        """Convert a canvas x-coordinate to an absolute beat position."""
        return (x - KEY_LABEL_WIDTH) / self._beat_width

    def _midi_to_y(self, midi: int) -> int:
        """Return the top y-coordinate of the row for the given MIDI pitch.

        Higher MIDI = higher on screen = smaller y value.
        """
        # Row 0 (top of canvas body) = MIDI_MAX; row N-1 = MIDI_MIN
        row = MIDI_MAX - midi
        return HEADER_HEIGHT + row * SEMITONE_HEIGHT

    def _y_to_midi(self, y: int) -> int:
        """Convert a canvas y-coordinate to the nearest MIDI pitch."""
        row = (y - HEADER_HEIGHT) // SEMITONE_HEIGHT
        midi = MIDI_MAX - row
        return max(MIDI_MIN, min(MIDI_MAX, midi))

    def _snap_beat(self, beat: float) -> float:
        """Snap a beat position to the quantise grid if quantise is on."""
        if not self._quantise:
            return max(0.0, beat)
        grid = 1.0 / SNAP_SUBDIVISIONS
        return max(0.0, round(beat / grid) * grid)

    # ------------------------------------------------------------------
    # Canvas size
    # ------------------------------------------------------------------

    def _recalc_size(self) -> None:
        """Recalculate and set the widget's minimum size."""
        num_rows = MIDI_MAX - MIDI_MIN + 1
        height = HEADER_HEIGHT + num_rows * SEMITONE_HEIGHT

        # Add enough columns for all measures + a few empty ones
        visible_beats = max(self._total_beats + 16, 32.0)
        width = KEY_LABEL_WIDTH + int(visible_beats * self._beat_width)

        self.setMinimumSize(QSize(width, height))
        self.resize(QSize(width, height))

    # ------------------------------------------------------------------
    # Building the note record list from the Part
    # ------------------------------------------------------------------

    def _rebuild_note_records(self) -> None:
        """Walk the Part and build _NoteData records with pixel rects."""
        self._note_records.clear()
        if self._part is None:
            self._total_beats = 32.0
            return

        abs_beat = 0.0
        total = 0.0

        for m_idx, measure in enumerate(self._part.measures):
            evt_beat = abs_beat
            last_start_beat = evt_beat
            for e_idx, event in enumerate(measure.events):
                current_beat = evt_beat
                if isinstance(event, Note) and event.chord:
                    current_beat = last_start_beat
                if isinstance(event, Note):
                    midi = event.midi_number
                    x = self._beat_to_x(current_beat)
                    y = self._midi_to_y(midi)
                    w = max(2, int(event.beats * self._beat_width) - 2)
                    h = SEMITONE_HEIGHT - 2
                    rect = QRect(x, y + 1, w, h)
                    nd = _NoteData(
                        note=event,
                        measure_idx=m_idx,
                        event_idx=e_idx,
                        beat_start=current_beat,
                        rect=rect,
                    )
                    self._note_records.append(nd)
                if not (isinstance(event, Note) and event.chord):
                    last_start_beat = evt_beat
                    evt_beat += event.beats
            abs_beat += measure.capacity_beats
            total = abs_beat

        self._total_beats = max(total, 32.0)

        # Keep selected / hovered references valid
        if self._selected_note is not None:
            self._selected_note = self._find_matching_record(self._selected_note)
        if self._hovered_note is not None:
            self._hovered_note = None

    def _find_matching_record(self, old: _NoteData) -> _NoteData | None:
        """After a rebuild, try to re-find the previously selected note."""
        for nd in self._note_records:
            if nd.measure_idx == old.measure_idx and nd.event_idx == old.event_idx:
                return nd
        return None

    def _note_at(self, pos: QPoint) -> _NoteData | None:
        """Return the topmost _NoteData whose rect contains pos, or None."""
        # Iterate in reverse so later-drawn (top) notes are hit first
        for nd in reversed(self._note_records):
            if nd.rect.contains(pos):
                return nd
        return None

    # ------------------------------------------------------------------
    # Instrument colour
    # ------------------------------------------------------------------

    def _color_for_instrument(self, name: str) -> QColor:
        """Return a consistent colour for the given instrument name."""
        if name not in self._color_cache:
            self._color_cache[name] = _INSTRUMENT_COLORS[
                self._color_index % len(_INSTRUMENT_COLORS)
            ]
            self._color_index += 1
        return self._color_cache[name]

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Render the entire piano roll using QPainter."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        clip = event.rect()

        self._draw_background(painter, clip)
        self._draw_grid(painter, clip)
        self._draw_piano_keys(painter, clip)
        self._draw_time_ruler(painter, clip)
        self._draw_notes(painter, clip)

        painter.end()

    def _draw_background(self, painter: QPainter, clip: QRect) -> None:
        """Fill the note area with alternating white / light-grey rows."""
        for midi in range(MIDI_MIN, MIDI_MAX + 1):
            y = self._midi_to_y(midi)
            if y + SEMITONE_HEIGHT < clip.top() or y > clip.bottom():
                continue
            if _is_black_key(midi):
                color = QColor(220, 220, 228)
            else:
                color = QColor(245, 245, 248)
            painter.fillRect(
                KEY_LABEL_WIDTH, y,
                self.width() - KEY_LABEL_WIDTH, SEMITONE_HEIGHT,
                color,
            )

        # Header background
        painter.fillRect(0, 0, self.width(), HEADER_HEIGHT, QColor(45, 50, 60))

        # Key label column background
        painter.fillRect(0, HEADER_HEIGHT, KEY_LABEL_WIDTH, self.height(), QColor(30, 30, 36))

    def _draw_grid(self, painter: QPainter, clip: QRect) -> None:
        """Draw measure barlines, beat lines, and subdivision lines."""
        if self._part is None:
            beats_per_measure = 4.0
        else:
            beats_per_measure = self._beats_per_measure

        total_beats = self._total_beats + 16
        grid_top = HEADER_HEIGHT
        grid_bottom = self.height()

        # Horizontal lines between semitone rows (subtle)
        painter.setPen(QPen(QColor(200, 200, 205), 1))
        for midi in range(MIDI_MIN, MIDI_MAX + 1):
            y = self._midi_to_y(midi)
            if y < clip.top() - 1 or y > clip.bottom() + 1:
                continue
            painter.drawLine(KEY_LABEL_WIDTH, y, self.width(), y)

        # Subdivision lines (dotted, very faint)
        sub_pen = QPen(QColor(190, 190, 200), 1, Qt.DotLine)
        beat_pen = QPen(QColor(160, 165, 180), 1, Qt.DashLine)
        bar_pen = QPen(QColor(80, 85, 100), 2, Qt.SolidLine)

        beat = 0.0
        while beat <= total_beats:
            x = self._beat_to_x(beat)
            if x < clip.left() - 2 or x > clip.right() + 2:
                beat += 1.0 / SNAP_SUBDIVISIONS
                continue

            within_measure = beat % beats_per_measure
            is_barline = abs(within_measure) < 1e-9 or abs(within_measure - beats_per_measure) < 1e-9
            is_beat = abs(within_measure - round(within_measure)) < 1e-9

            if is_barline:
                painter.setPen(bar_pen)
                painter.drawLine(x, grid_top, x, grid_bottom)
            elif is_beat:
                painter.setPen(beat_pen)
                painter.drawLine(x, grid_top, x, grid_bottom)
            else:
                painter.setPen(sub_pen)
                painter.drawLine(x, grid_top, x, grid_bottom)

            beat += 1.0 / SNAP_SUBDIVISIONS

    def _draw_piano_keys(self, painter: QPainter, clip: QRect) -> None:
        """Draw the piano keyboard strip on the left side."""
        font = QFont("Helvetica", 7)
        painter.setFont(font)
        fm = QFontMetrics(font)

        for midi in range(MIDI_MIN, MIDI_MAX + 1):
            y = self._midi_to_y(midi)
            if y + SEMITONE_HEIGHT < clip.top() or y > clip.bottom():
                continue

            if _is_black_key(midi):
                key_color = QColor(40, 40, 40)
                text_color = QColor(200, 200, 200)
            else:
                key_color = QColor(240, 240, 245)
                text_color = QColor(50, 50, 60)

            painter.fillRect(0, y, KEY_LABEL_WIDTH - 1, SEMITONE_HEIGHT - 1, key_color)

            if _should_show_label(midi):
                label = _pitch_label(midi)
                text_width = fm.horizontalAdvance(label)
                tx = (KEY_LABEL_WIDTH - 2) - text_width
                ty = y + SEMITONE_HEIGHT - 3
                painter.setPen(QPen(text_color))
                painter.drawText(tx, ty, label)

        # Right border of key strip
        painter.setPen(QPen(QColor(100, 100, 110), 1))
        painter.drawLine(KEY_LABEL_WIDTH - 1, HEADER_HEIGHT,
                         KEY_LABEL_WIDTH - 1, self.height())

    def _draw_time_ruler(self, painter: QPainter, clip: QRect) -> None:
        """Draw beat numbers and measure markers in the header strip."""
        if self._part is None:
            beats_per_measure = 4.0
        else:
            beats_per_measure = self._beats_per_measure

        font = QFont("Helvetica", 8, QFont.Bold)
        painter.setFont(font)
        fm = QFontMetrics(font)

        painter.fillRect(KEY_LABEL_WIDTH, 0, self.width() - KEY_LABEL_WIDTH, HEADER_HEIGHT,
                         QColor(45, 50, 60))

        total_beats = self._total_beats + 16
        beat = 0.0
        measure_num = 1

        while beat <= total_beats:
            x = self._beat_to_x(beat)
            if x < clip.left() - 60 or x > clip.right() + 2:
                beat += beats_per_measure
                measure_num += 1
                continue

            within = beat % beats_per_measure
            is_barline = abs(within) < 1e-9 or abs(within - beats_per_measure) < 1e-9

            if is_barline:
                # Measure number label
                label = str(measure_num)
                tw = fm.horizontalAdvance(label)
                painter.setPen(QPen(QColor(220, 230, 250)))
                painter.drawText(x + 3, HEADER_HEIGHT - 6, label)

                # Tick mark
                painter.setPen(QPen(QColor(180, 185, 200), 1))
                painter.drawLine(x, HEADER_HEIGHT - 12, x, HEADER_HEIGHT)
                measure_num += 1
            else:
                # Minor beat tick
                painter.setPen(QPen(QColor(120, 125, 140), 1))
                painter.drawLine(x, HEADER_HEIGHT - 6, x, HEADER_HEIGHT)

            beat += 1.0

        # Bottom border of header
        painter.setPen(QPen(QColor(100, 105, 120), 1))
        painter.drawLine(0, HEADER_HEIGHT - 1, self.width(), HEADER_HEIGHT - 1)

    def _draw_notes(self, painter: QPainter, clip: QRect) -> None:
        """Draw all note rectangles with colour, border, and selection highlight."""
        instr_name = (
            self._part.instrument.name if self._part is not None else "Piano"
        )
        base_color = self._color_for_instrument(instr_name)

        for nd in self._note_records:
            if (nd.rect.right() < clip.left() or
                    nd.rect.left() > clip.right() or
                    nd.rect.bottom() < clip.top() or
                    nd.rect.top() > clip.bottom()):
                continue

            is_selected = (nd is self._selected_note)
            is_hovered = (nd is self._hovered_note)

            if is_selected:
                fill = base_color.lighter(130)
                border = QColor(255, 220, 50)
                border_width = 2
            elif is_hovered:
                fill = base_color.lighter(115)
                border = base_color.lighter(160)
                border_width = 1
            else:
                fill = base_color
                border = base_color.darker(140)
                border_width = 1

            painter.fillRect(nd.rect, fill)
            painter.setPen(QPen(border, border_width))
            painter.drawRect(nd.rect)

            # Velocity shade on left edge (darker = quieter)
            vel_ratio = nd.note.velocity / 127.0
            vel_color = QColor(0, 0, 0, int((1.0 - vel_ratio) * 80))
            painter.fillRect(nd.rect.x(), nd.rect.y(), 3, nd.rect.height(), vel_color)

    # ------------------------------------------------------------------
    # Mouse handling
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Handle left-click (create/select) and right-click (delete)."""
        pos = event.pos()
        hit = self._note_at(pos)

        if event.button() == Qt.LeftButton:
            if hit is not None:
                # Select this note; prepare for drag
                self._selected_note = hit
                self._drag_note = hit
                self._drag_origin_px = pos
                self._drag_origin_beat = hit.beat_start
                self._drag_origin_midi = hit.note.midi_number
                self._dragging = False
                self.status_message.emit(
                    f"Selected: {hit.note.pitch}  {hit.note.duration}  "
                    f"vel={hit.note.velocity}"
                )
            else:
                # Create a new note at this position
                self._selected_note = None
                beat = self._snap_beat(self._x_to_beat(pos.x()))
                midi = self._y_to_midi(pos.y())
                if beat >= 0 and MIDI_MIN <= midi <= MIDI_MAX:
                    self._create_note(beat, midi)

        elif event.button() == Qt.RightButton:
            if hit is not None:
                self._delete_note(hit)
                self._selected_note = None

        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Handle hover highlighting and note drag."""
        pos = event.pos()

        if event.buttons() & Qt.LeftButton and self._drag_note is not None:
            # Check if we've moved enough to begin dragging
            delta = pos - self._drag_origin_px
            if not self._dragging and (abs(delta.x()) > self._drag_threshold or
                                        abs(delta.y()) > self._drag_threshold):
                self._dragging = True

            if self._dragging:
                self._perform_drag(pos)
            return

        # Update hover
        hit = self._note_at(pos)
        if hit is not self._hovered_note:
            self._hovered_note = hit
            self.update()

        if hit is not None:
            self.status_message.emit(
                f"{hit.note.pitch}  {hit.note.duration}  vel={hit.note.velocity}"
            )
        else:
            beat = self._x_to_beat(pos.x())
            midi = self._y_to_midi(pos.y())
            if midi >= MIDI_MIN:
                pitch = Pitch.from_midi(midi)
                self.status_message.emit(
                    f"Beat {beat:.2f}  Pitch {pitch}  "
                    f"(click to add {self._selected_duration})"
                )

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Finish a drag operation."""
        if event.button() == Qt.LeftButton:
            self._drag_note = None
            self._dragging = False
        self.update()

    def _perform_drag(self, pos: QPoint) -> None:
        """Move the dragged note to match the current mouse position."""
        if self._drag_note is None or self._part is None:
            return

        delta_x = pos.x() - self._drag_origin_px.x()
        delta_y = pos.y() - self._drag_origin_px.y()

        # Time offset in beats
        beat_delta = delta_x / self._beat_width
        new_beat = self._snap_beat(self._drag_origin_beat + beat_delta)
        new_beat = max(0.0, new_beat)

        # Pitch offset in semitones
        semitone_delta = -round(delta_y / SEMITONE_HEIGHT)
        new_midi = max(MIDI_MIN, min(MIDI_MAX,
                                     self._drag_origin_midi + semitone_delta))

        old_pitch = self._drag_note.note.pitch
        old_beat = self._drag_note.beat_start

        if abs(new_beat - old_beat) < 1e-9 and new_midi == old_pitch.midi_number:
            return   # nothing changed

        # Build new Pitch from MIDI
        new_pitch = Pitch.from_midi(new_midi)

        # Mutate the Note object in place (both pitch and timing)
        nd = self._drag_note
        # Remove old note and reinsert with new properties
        old_note = nd.note
        new_note = Note(
            pitch=new_pitch,
            duration=old_note.duration,
            velocity=old_note.velocity,
            chord=old_note.chord,
            tie_start=old_note.tie_start,
            tie_end=old_note.tie_end,
            lyrics=old_note.lyrics,
        )

        measures = self._part.measures
        # Remove from old location
        old_measure = measures[nd.measure_idx]
        if old_note in old_measure._events:
            old_measure._events.remove(old_note)

        # Find destination measure for new_beat
        m_idx, offset_in_measure = self._beat_to_measure_position(new_beat)
        if m_idx is None:
            # Beyond existing measures — ensure measures exist
            while len(self._part.measures) <= (m_idx or 0):
                self._part.new_measure()
            m_idx = len(self._part.measures) - 1
            offset_in_measure = 0.0

        dest_measure = self._part.measures[m_idx]
        # Insert at the right position within that measure
        self._insert_note_at_offset(dest_measure, new_note, offset_in_measure)

        self._rebuild_note_records()
        # Re-identify the dragged note after rebuild
        self._drag_note = self._find_note_near(new_beat, new_midi)
        self._selected_note = self._drag_note

        self.update()
        self.notes_changed.emit()
        self.status_message.emit(
            f"Moved: {new_pitch}  beat {new_beat:.2f}  {old_note.duration}"
        )

    def _beat_to_measure_position(self, abs_beat: float) -> tuple[int | None, float]:
        """Convert an absolute beat to (measure_index, offset_within_measure).

        Returns (None, 0.0) if no measures exist.
        """
        if self._part is None:
            return None, 0.0

        measures = self._part.measures
        if not measures:
            return None, 0.0

        cursor = 0.0
        for i, m in enumerate(measures):
            cap = m.capacity_beats
            if abs_beat < cursor + cap + 1e-9:
                return i, abs_beat - cursor
            cursor += cap

        # Past end — last measure
        last_idx = len(measures) - 1
        cursor_start = cursor - measures[last_idx].capacity_beats
        return last_idx, abs_beat - cursor_start

    def _insert_note_at_offset(
        self, measure: Measure, note: Note, offset: float
    ) -> None:
        """Insert note into measure._events at the position matching offset beats."""
        # Walk existing events to find insertion point
        beat = 0.0
        for i, evt in enumerate(measure._events):
            if beat >= offset - 1e-9:
                measure._events.insert(i, note)
                return
            beat += evt.beats
        measure._events.append(note)

    def _find_note_near(self, beat: float, midi: int) -> _NoteData | None:
        """After a rebuild, find the note closest to the given position."""
        best: _NoteData | None = None
        best_dist = 1e9
        for nd in self._note_records:
            dist = abs(nd.beat_start - beat) + abs(nd.note.midi_number - midi) * 0.5
            if dist < best_dist:
                best_dist = dist
                best = nd
        return best if best_dist < 2.0 else None

    # ------------------------------------------------------------------
    # Note creation and deletion
    # ------------------------------------------------------------------

    def _create_note(self, beat: float, midi: int) -> None:
        """Create a new Note in the Part at the given beat and MIDI pitch."""
        if self._part is None:
            return

        pitch = Pitch.from_midi(midi)
        pitch_str = pitch.full_name
        new_note = Note.from_str(pitch_str, self._selected_duration)

        # Ensure enough measures exist
        m_idx, offset = self._beat_to_measure_position(beat)
        if m_idx is None:
            self._part.new_measure()
            m_idx, offset = 0, beat

        # Grow measures until we have one covering `beat`
        cursor = sum(m.capacity_beats for m in self._part.measures)
        while beat >= cursor - 1e-9:
            self._part.new_measure()
            cursor += self._part.measures[-1].capacity_beats

        m_idx, offset = self._beat_to_measure_position(beat)
        dest = self._part.measures[m_idx]
        # Insert only if there is room; otherwise place in a new measure
        if new_note.beats <= dest.remaining_beats + 1e-9:
            self._insert_note_at_offset(dest, new_note, offset)
        else:
            # Spill into the next measure (or create one)
            next_idx = m_idx + 1
            if next_idx >= len(self._part.measures):
                self._part.new_measure()
            next_dest = self._part.measures[next_idx]
            self._insert_note_at_offset(next_dest, new_note, 0.0)

        self._rebuild_note_records()
        # Select the just-created note
        self._selected_note = self._find_note_near(beat, midi)
        self.update()
        self.notes_changed.emit()
        self.status_message.emit(
            f"Created: {pitch}  {self._selected_duration}  beat {beat:.2f}"
        )

    def _delete_note(self, nd: _NoteData) -> None:
        """Remove the given note from the Part."""
        if self._part is None:
            return

        measures = self._part.measures
        if nd.measure_idx >= len(measures):
            return
        measure = measures[nd.measure_idx]
        if nd.note in measure._events:
            measure._events.remove(nd.note)

        self._rebuild_note_records()
        self.update()
        self.notes_changed.emit()
        self.status_message.emit(
            f"Deleted: {nd.note.pitch}  {nd.note.duration}"
        )

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Handle Delete/Backspace to remove the selected note."""
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if self._selected_note is not None:
                self._delete_note(self._selected_note)
                self._selected_note = None
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Wheel scroll (delegated to parent scroll area)
    # ------------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """Pass wheel events upward so the QScrollArea handles them."""
        event.ignore()


# ---------------------------------------------------------------------------
# PianoRollWidget — toolbar + scroll area wrapper
# ---------------------------------------------------------------------------

class PianoRollWidget(QWidget):
    """Full piano roll editor: toolbar + scrollable canvas.

    This is the public widget to embed in the main window.

    Signals:
        notes_changed: Forwarded from the inner canvas whenever a note is
                       created, moved, or deleted.
    """

    notes_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._part: Part | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the toolbar strip and scrollable canvas area."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar ─────────────────────────────────────────────────────
        toolbar = self._build_toolbar()
        root.addWidget(toolbar)

        # ── Scroll area with canvas ──────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._scroll.setFocusPolicy(Qt.NoFocus)

        self._canvas = PianoRollCanvas()
        self._canvas.notes_changed.connect(self.notes_changed)
        self._canvas.status_message.connect(self._on_canvas_status)
        self._scroll.setWidget(self._canvas)

        root.addWidget(self._scroll)

        # ── Status label ─────────────────────────────────────────────────
        self._status_label = QLabel("No part loaded — generate a score first.")
        self._status_label.setStyleSheet(
            "QLabel { color: #aaa; font-size: 11px; padding: 2px 6px; "
            "background: #2a2a2e; border-top: 1px solid #444; }"
        )
        self._status_label.setFixedHeight(20)
        root.addWidget(self._status_label)

        # Scroll wheel on the scroll area → forward to scroll bars
        self._scroll.installEventFilter(self)

        # Scroll to the middle of the pitch range (around C4 = MIDI 60)
        self._scroll_to_pitch(60)

    def _build_toolbar(self) -> QWidget:
        """Construct the toolbar with duration buttons, instrument drop-down, etc."""
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet(
            "QWidget { background: #2d2d32; border-bottom: 1px solid #444; }"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)

        # Duration buttons
        dur_label = QLabel("Duration:")
        dur_label.setStyleSheet("color:#ccc; font-size:11px;")
        layout.addWidget(dur_label)

        self._dur_buttons: list[QPushButton] = []
        for label, dur_str, beats in zip(
            _DURATION_LABELS, _DURATION_STRINGS, _DURATION_BEATS
        ):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedWidth(54)
            btn.setFixedHeight(26)
            btn.setStyleSheet(self._dur_btn_style(False))
            btn.clicked.connect(
                lambda checked, d=dur_str, b=beats: self._on_duration_selected(d, b)
            )
            self._dur_buttons.append(btn)
            layout.addWidget(btn)

        # Default: Quarter selected
        self._dur_buttons[2].setChecked(True)
        self._dur_buttons[2].setStyleSheet(self._dur_btn_style(True))
        self._active_dur_idx = 2

        layout.addSpacing(12)

        # Instrument label
        instr_label = QLabel("Instrument:")
        instr_label.setStyleSheet("color:#ccc; font-size:11px;")
        layout.addWidget(instr_label)

        self._instr_combo = QComboBox()
        self._instr_combo.addItems(sorted(INSTRUMENTS.keys()))
        self._instr_combo.setFixedHeight(26)
        self._instr_combo.setFixedWidth(130)
        self._instr_combo.setStyleSheet(
            "QComboBox { background:#3a3a40; color:#eee; border:1px solid #555; "
            "padding:2px 4px; font-size:11px; }"
            "QComboBox QAbstractItemView { background:#3a3a40; color:#eee; }"
        )
        self._instr_combo.currentTextChanged.connect(self._on_instrument_changed)
        layout.addWidget(self._instr_combo)

        layout.addSpacing(12)

        # Quantise toggle
        self._quantise_btn = QPushButton("Snap")
        self._quantise_btn.setCheckable(True)
        self._quantise_btn.setChecked(True)
        self._quantise_btn.setFixedWidth(48)
        self._quantise_btn.setFixedHeight(26)
        self._quantise_btn.setStyleSheet(self._toggle_btn_style(True))
        self._quantise_btn.toggled.connect(self._on_quantise_toggled)
        layout.addWidget(self._quantise_btn)

        layout.addSpacing(12)

        # Zoom
        zoom_label = QLabel("Zoom:")
        zoom_label.setStyleSheet("color:#ccc; font-size:11px;")
        layout.addWidget(zoom_label)

        zoom_out = QPushButton("−")
        zoom_out.setFixedSize(26, 26)
        zoom_out.setStyleSheet(self._icon_btn_style())
        zoom_out.clicked.connect(self._zoom_out)
        layout.addWidget(zoom_out)

        zoom_in = QPushButton("+")
        zoom_in.setFixedSize(26, 26)
        zoom_in.setStyleSheet(self._icon_btn_style())
        zoom_in.clicked.connect(self._zoom_in)
        layout.addWidget(zoom_in)

        layout.addStretch()

        # Help hint
        hint = QLabel("L-click: add/select  |  drag: move  |  R-click: delete  |  Del: erase")
        hint.setStyleSheet("color:#777; font-size:10px;")
        layout.addWidget(hint)

        return bar

    @staticmethod
    def _dur_btn_style(active: bool) -> str:
        if active:
            return (
                "QPushButton { background:#3a6ea8; color:white; "
                "border:1px solid #5a8ece; border-radius:3px; font-size:10px; font-weight:bold; }"
            )
        return (
            "QPushButton { background:#3a3a40; color:#ccc; "
            "border:1px solid #555; border-radius:3px; font-size:10px; }"
            "QPushButton:hover { background:#4a4a52; }"
        )

    @staticmethod
    def _toggle_btn_style(on: bool) -> str:
        if on:
            return (
                "QPushButton { background:#3a7a50; color:white; "
                "border:1px solid #5aaa70; border-radius:3px; font-size:10px; font-weight:bold; }"
            )
        return (
            "QPushButton { background:#3a3a40; color:#aaa; "
            "border:1px solid #555; border-radius:3px; font-size:10px; }"
        )

    @staticmethod
    def _icon_btn_style() -> str:
        return (
            "QPushButton { background:#3a3a40; color:#eee; "
            "border:1px solid #555; border-radius:3px; font-size:14px; font-weight:bold; }"
            "QPushButton:hover { background:#505058; }"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_part(self, part: Part) -> None:
        """Load a Part into the piano roll canvas for editing.

        Args:
            part: The Part to render and edit in place.
        """
        self._part = part
        self._canvas.load_part(part)

        # Sync instrument combo to the part's instrument
        instr_name = part.instrument.name
        idx = self._instr_combo.findText(instr_name)
        if idx >= 0:
            self._instr_combo.blockSignals(True)
            self._instr_combo.setCurrentIndex(idx)
            self._instr_combo.blockSignals(False)

        # Scroll to a sensible pitch (instrument's mid range)
        mid_midi = (part.instrument.midi_min + part.instrument.midi_max) // 2
        self._scroll_to_pitch(mid_midi)
        self._status_label.setText(
            f"Loaded: {part.instrument.name}  —  "
            f"{len(part.measures)} measure(s), "
            f"{len(part.all_notes)} note(s)"
        )

    def clear(self) -> None:
        """Clear the piano roll (no part loaded)."""
        self._part = None
        self._canvas._part = None
        self._canvas._note_records.clear()
        self._canvas._selected_note = None
        self._canvas._hovered_note = None
        self._canvas.update()
        self._status_label.setText("No part loaded — generate a score first.")

    # ------------------------------------------------------------------
    # Toolbar callbacks
    # ------------------------------------------------------------------

    def _on_duration_selected(self, dur_str: str, beats: float) -> None:
        """Switch the active note duration."""
        idx = _DURATION_STRINGS.index(dur_str)
        for i, btn in enumerate(self._dur_buttons):
            active = (i == idx)
            btn.setChecked(active)
            btn.setStyleSheet(self._dur_btn_style(active))
        self._active_dur_idx = idx
        self._canvas.set_selected_duration(dur_str, beats)

    def _on_instrument_changed(self, name: str) -> None:
        """Change the Part's instrument (affects colour and label in canvas)."""
        if self._part is not None and name in INSTRUMENTS:
            self._part.instrument = INSTRUMENTS[name]
            self._canvas._color_cache.clear()
            self._canvas._color_index = 0
            self._canvas.update()

    def _on_quantise_toggled(self, checked: bool) -> None:
        """Toggle snap-to-grid."""
        self._quantise_btn.setStyleSheet(self._toggle_btn_style(checked))
        self._canvas.set_quantise(checked)

    def _zoom_in(self) -> None:
        """Increase horizontal zoom by 20%."""
        new_w = int(self._canvas.get_beat_width() * 1.25)
        self._canvas.set_beat_width(new_w)

    def _zoom_out(self) -> None:
        """Decrease horizontal zoom by 20%."""
        new_w = int(self._canvas.get_beat_width() / 1.25)
        self._canvas.set_beat_width(new_w)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _scroll_to_pitch(self, midi: int) -> None:
        """Scroll the vertical scroll bar so that midi is near vertical centre."""
        # Give Qt a moment to lay out before scrolling
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(50, lambda: self._do_scroll_to_pitch(midi))

    def _do_scroll_to_pitch(self, midi: int) -> None:
        y = self._canvas._midi_to_y(midi)
        half_viewport = self._scroll.viewport().height() // 2
        target = max(0, y - half_viewport)
        self._scroll.verticalScrollBar().setValue(target)

    def _on_canvas_status(self, msg: str) -> None:
        self._status_label.setText(msg)

    # ------------------------------------------------------------------
    # Event filter: wheel → scroll area scroll bars
    # ------------------------------------------------------------------

    def eventFilter(self, source, event) -> bool:  # type: ignore[override]
        """Route wheel events on the scroll area to its scroll bars."""
        from PyQt5.QtCore import QEvent
        if source is self._scroll and event.type() == QEvent.Wheel:
            wheel: QWheelEvent = event  # type: ignore[assignment]
            if wheel.modifiers() & Qt.ShiftModifier:
                # Horizontal scroll
                delta = wheel.angleDelta().y()
                bar = self._scroll.horizontalScrollBar()
                bar.setValue(bar.value() - delta)
            else:
                # Vertical scroll
                delta = wheel.angleDelta().y()
                bar = self._scroll.verticalScrollBar()
                bar.setValue(bar.value() - delta)
            return True
        return super().eventFilter(source, event)
