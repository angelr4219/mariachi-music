"""Left-side controls panel: score settings + generation tools."""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from mariachi_music.core.instrument import INSTRUMENTS


class ControlsPanel(QWidget):
    """Left panel: score metadata + scale generation settings."""

    # Emitted when the user clicks Generate Scale
    generate_requested = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # ── Score Settings ──────────────────────────────────────────────
        score_box = QGroupBox("Score Settings")
        score_form = QFormLayout(score_box)

        self.title_edit = QLineEdit("Untitled Score")
        score_form.addRow("Title:", self.title_edit)

        self.composer_edit = QLineEdit()
        score_form.addRow("Composer:", self.composer_edit)

        self.tempo_spin = QDoubleSpinBox()
        self.tempo_spin.setRange(20, 400)
        self.tempo_spin.setValue(120)
        self.tempo_spin.setSuffix(" BPM")
        score_form.addRow("Tempo:", self.tempo_spin)

        self.key_combo = QComboBox()
        self.key_combo.addItems([
            "C", "G", "D", "A", "E", "B", "F#",
            "F", "Bb", "Eb", "Ab", "Db",
        ])
        score_form.addRow("Key:", self.key_combo)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["major", "minor", "dorian", "mixolydian",
                                   "phrygian", "lydian", "chromatic"])
        score_form.addRow("Mode:", self.mode_combo)

        self.time_sig_combo = QComboBox()
        self.time_sig_combo.addItems(["4/4", "3/4", "2/4", "6/8"])
        score_form.addRow("Time Sig:", self.time_sig_combo)

        layout.addWidget(score_box)

        # ── Scale Generator ─────────────────────────────────────────────
        gen_box = QGroupBox("Scale Generator")
        gen_form = QFormLayout(gen_box)

        self.instrument_combo = QComboBox()
        self.instrument_combo.addItems(sorted(INSTRUMENTS.keys()))
        gen_form.addRow("Instrument:", self.instrument_combo)

        self.octave_spin = QSpinBox()
        self.octave_spin.setRange(0, 8)
        self.octave_spin.setValue(4)
        gen_form.addRow("Octave:", self.octave_spin)

        self.duration_combo = QComboBox()
        self.duration_combo.addItems(["whole", "half", "quarter", "eighth"])
        self.duration_combo.setCurrentText("quarter")
        gen_form.addRow("Duration:", self.duration_combo)

        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["Ascending", "Descending"])
        gen_form.addRow("Direction:", self.direction_combo)

        self.generate_btn = QPushButton("Generate Scale")
        self.generate_btn.setStyleSheet(
            "QPushButton { background: #2c6fad; color: white; font-weight: bold; "
            "padding: 6px; border-radius: 4px; }"
            "QPushButton:hover { background: #3a82cc; }"
        )
        self.generate_btn.clicked.connect(self._on_generate)
        gen_form.addRow(self.generate_btn)

        layout.addWidget(gen_box)
        layout.addStretch()

    def _on_generate(self) -> None:
        params = {
            "title": self.title_edit.text() or "Untitled",
            "composer": self.composer_edit.text(),
            "tempo": self.tempo_spin.value(),
            "key": self.key_combo.currentText(),
            "mode": self.mode_combo.currentText(),
            "time_signature": self.time_sig_combo.currentText(),
            "instrument": self.instrument_combo.currentText(),
            "octave": self.octave_spin.value(),
            "duration": self.duration_combo.currentText(),
            "ascending": self.direction_combo.currentText() == "Ascending",
        }
        self.generate_requested.emit(params)

    def get_score_params(self) -> dict:
        return {
            "title": self.title_edit.text() or "Untitled",
            "composer": self.composer_edit.text(),
            "tempo": self.tempo_spin.value(),
            "key": self.key_combo.currentText(),
            "mode": self.mode_combo.currentText(),
            "time_signature": self.time_sig_combo.currentText(),
        }
