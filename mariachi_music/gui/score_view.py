"""Center panel: note table preview of the current score."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mariachi_music.core.score import Score


_COLUMNS = ["Measure", "Beat", "Instrument", "Type", "Pitch", "Duration"]


class ScoreView(QWidget):
    """Table-based preview of notes in the current Score."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._current_score: Score | None = None

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._header_label = QLabel("No score loaded.")
        self._header_label.setFont(QFont("Helvetica", 11, QFont.Bold))
        layout.addWidget(self._header_label)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

    def load_score(self, score: Score) -> None:
        """Populate the table from a Score object."""
        self._current_score = score
        self._header_label.setText(
            f"{score.title}  —  {score.key_signature}  |  "
            f"{score.time_signature}  |  ♩ = {score.tempo.bpm:.0f} BPM"
        )

        rows = score.note_table()
        self._table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            self._table.setItem(r, 0, self._cell(str(row["measure"])))
            self._table.setItem(r, 1, self._cell(str(row["beat"])))
            self._table.setItem(r, 2, self._cell(row["instrument"]))
            self._table.setItem(r, 3, self._cell(row["type"]))
            self._table.setItem(r, 4, self._cell(row["pitch"]))
            self._table.setItem(r, 5, self._cell(row["duration"]))

        self._table.resizeColumnsToContents()

    def clear(self) -> None:
        self._table.setRowCount(0)
        self._header_label.setText("No score loaded.")
        self._current_score = None

    @staticmethod
    def _cell(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        return item
