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
    QListWidget,
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
    notes_requested = pyqtSignal(dict)
    chords_requested = pyqtSignal(dict)
    template_requested = pyqtSignal(dict)
    classify_audio_requested = pyqtSignal()
    add_instrument_requested = pyqtSignal(str)
    remove_instrument_requested = pyqtSignal(int)
    selected_part_changed = pyqtSignal(int)

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

        # ── Instruments ────────────────────────────────────────────────
        inst_box = QGroupBox("Instruments")
        inst_layout = QVBoxLayout(inst_box)

        self.part_list = QListWidget()
        self.part_list.currentRowChanged.connect(self.selected_part_changed.emit)
        inst_layout.addWidget(self.part_list)

        inst_controls = QFormLayout()
        self.add_instrument_combo = QComboBox()
        self.add_instrument_combo.addItems(sorted(INSTRUMENTS.keys()))
        inst_controls.addRow("Add:", self.add_instrument_combo)

        self.add_instrument_btn = QPushButton("Add Instrument")
        self.add_instrument_btn.clicked.connect(
            lambda: self.add_instrument_requested.emit(self.add_instrument_combo.currentText())
        )
        inst_controls.addRow(self.add_instrument_btn)

        self.remove_instrument_btn = QPushButton("Remove Selected")
        self.remove_instrument_btn.clicked.connect(
            lambda: self.remove_instrument_requested.emit(self.part_list.currentRow())
        )
        inst_controls.addRow(self.remove_instrument_btn)
        inst_layout.addLayout(inst_controls)

        layout.addWidget(inst_box)

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

        # ── Mariachi Template Engine ────────────────────────────────────
        template_box = QGroupBox("Mariachi Template Engine")
        template_form = QFormLayout(template_box)

        self.template_genre_combo = QComboBox()
        self.template_genre_combo.addItems(["ranchera", "son", "bolero", "polca_ranchera"])
        template_form.addRow("Genre:", self.template_genre_combo)

        self.template_context_combo = QComboBox()
        self.template_context_combo.addItems([
            "restaurant",
            "cantina",
            "show",
            "restaurant_or_private_party",
            "show_or_concert",
        ])
        template_form.addRow("Context:", self.template_context_combo)

        self.template_length_combo = QComboBox()
        self.template_length_combo.addItems(["full", "short", "auto"])
        template_form.addRow("Length:", self.template_length_combo)

        self.template_subtype_combo = QComboBox()
        self.template_subtype_combo.addItems(["", "ranchera_3_4", "polca_ranchera"])
        template_form.addRow("Subtype:", self.template_subtype_combo)

        self.generate_template_btn = QPushButton("Generate Arrangement")
        self.generate_template_btn.setStyleSheet(
            "QPushButton { background: #8a5a2b; color: white; font-weight: bold; "
            "padding: 6px; border-radius: 4px; }"
            "QPushButton:hover { background: #a36b34; }"
        )
        self.generate_template_btn.clicked.connect(self._on_generate_template)
        template_form.addRow(self.generate_template_btn)

        self.classify_audio_btn = QPushButton("Classify Audio...")
        self.classify_audio_btn.clicked.connect(self.classify_audio_requested.emit)
        template_form.addRow(self.classify_audio_btn)

        layout.addWidget(template_box)

        # ── Manual Writer ───────────────────────────────────────────────
        write_box = QGroupBox("Manual Writer")
        write_form = QFormLayout(write_box)

        self.note_entry = QLineEdit()
        self.note_entry.setPlaceholderText("C4 D4 E4 or C D E")
        write_form.addRow("Notes:", self.note_entry)

        self.add_notes_btn = QPushButton("Add Notes")
        self.add_notes_btn.clicked.connect(self._on_add_notes)
        write_form.addRow(self.add_notes_btn)

        self.chord_entry = QLineEdit()
        self.chord_entry.setPlaceholderText("G, A, D, C or G Am D7 C")
        write_form.addRow("Chords:", self.chord_entry)

        self.add_chords_btn = QPushButton("Add Chords")
        self.add_chords_btn.setStyleSheet(
            "QPushButton { background: #6b5b95; color: white; font-weight: bold; "
            "padding: 6px; border-radius: 4px; }"
            "QPushButton:hover { background: #7b69ad; }"
        )
        self.add_chords_btn.clicked.connect(self._on_add_chords)
        write_form.addRow(self.add_chords_btn)

        layout.addWidget(write_box)
        layout.addStretch()

    def set_parts(self, names: list[str], selected_index: int = 0) -> None:
        self.part_list.blockSignals(True)
        self.part_list.clear()
        for idx, name in enumerate(names, 1):
            self.part_list.addItem(f"{idx}. {name}")
        if names:
            self.part_list.setCurrentRow(max(0, min(selected_index, len(names) - 1)))
        self.part_list.blockSignals(False)

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

    def _base_params(self) -> dict:
        return {
            "title": self.title_edit.text() or "Untitled",
            "composer": self.composer_edit.text(),
            "tempo": self.tempo_spin.value(),
            "key": self.key_combo.currentText(),
            "mode": self.mode_combo.currentText(),
            "time_signature": self.time_sig_combo.currentText(),
            "instrument": self.instrument_combo.currentText(),
            "octave": self.octave_spin.value(),
            "duration": self.duration_combo.currentText(),
        }

    def _on_add_notes(self) -> None:
        params = self._base_params()
        params["notes"] = self.note_entry.text()
        self.notes_requested.emit(params)

    def _on_add_chords(self) -> None:
        params = self._base_params()
        params["chords"] = self.chord_entry.text()
        self.chords_requested.emit(params)

    def _on_generate_template(self) -> None:
        params = self.get_score_params()
        params.update({
            "genre": self.template_genre_combo.currentText(),
            "context": self.template_context_combo.currentText(),
            "length": self.template_length_combo.currentText(),
            "subtype": self.template_subtype_combo.currentText(),
        })
        self.template_requested.emit(params)

    def get_score_params(self) -> dict:
        return {
            "title": self.title_edit.text() or "Untitled",
            "composer": self.composer_edit.text(),
            "tempo": self.tempo_spin.value(),
            "key": self.key_combo.currentText(),
            "mode": self.mode_combo.currentText(),
            "time_signature": self.time_sig_combo.currentText(),
        }
