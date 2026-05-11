"""Right panel: export controls."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mariachi_music.core.score import Score


class ExportPanel(QWidget):
    """Right panel with export buttons."""

    status_message = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._score: Score | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        export_box = QGroupBox("Export")
        vbox = QVBoxLayout(export_box)

        self._xml_btn = QPushButton("Export MusicXML…")
        self._xml_btn.clicked.connect(self._export_musicxml)
        self._xml_btn.setEnabled(False)
        vbox.addWidget(self._xml_btn)

        self._mid_btn = QPushButton("Export MIDI…")
        self._mid_btn.clicked.connect(self._export_midi)
        self._mid_btn.setEnabled(False)
        vbox.addWidget(self._mid_btn)

        self._both_btn = QPushButton("Export Both…")
        self._both_btn.clicked.connect(self._export_both)
        self._both_btn.setEnabled(False)
        vbox.addWidget(self._both_btn)

        layout.addWidget(export_box)
        layout.addStretch()

    def set_score(self, score: Score) -> None:
        self._score = score
        enabled = score is not None
        self._xml_btn.setEnabled(enabled)
        self._mid_btn.setEnabled(enabled)
        self._both_btn.setEnabled(enabled)

    def _export_musicxml(self) -> None:
        if not self._score:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export MusicXML", "", "MusicXML Files (*.musicxml *.xml)"
        )
        if not path:
            return
        try:
            self._score.export_musicxml(Path(path))
            self.status_message.emit(f"Saved MusicXML: {path}")
        except Exception as exc:
            self.status_message.emit(f"Export error: {exc}")

    def _export_midi(self) -> None:
        if not self._score:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export MIDI", "", "MIDI Files (*.mid)"
        )
        if not path:
            return
        try:
            self._score.export_midi(Path(path))
            self.status_message.emit(f"Saved MIDI: {path}")
        except Exception as exc:
            self.status_message.emit(f"Export error: {exc}")

    def _export_both(self) -> None:
        if not self._score:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Score (stem)", "", "All Files (*)"
        )
        if not path:
            return
        stem = Path(path)
        try:
            self._score.export_musicxml(stem.with_suffix(".musicxml"))
            self._score.export_midi(stem.with_suffix(".mid"))
            self.status_message.emit(
                f"Saved: {stem.with_suffix('.musicxml')} and {stem.with_suffix('.mid')}"
            )
        except Exception as exc:
            self.status_message.emit(f"Export error: {exc}")
