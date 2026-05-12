"""Main application window."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAction,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QTabWidget,
)

from mariachi_music.core.score import Score
from mariachi_music.core.instrument import Instrument
from mariachi_music.core.key_signature import KeySignature
from mariachi_music.core.part import Part
from mariachi_music.core.project_io import load_score_project, save_score_project
from mariachi_music.core.tempo import Tempo
from mariachi_music.core.time_signature import TimeSignature
from mariachi_music.generation.scale_generator import generate_scale_score
from mariachi_music.generation.chord_sequence_generator import parse_chord_sequence
from mariachi_music.mariachi import (
    MariachiSongRequest,
    classify_audio_genre,
    generate_mariachi_arrangement,
)
from .controls_panel import ControlsPanel
from .score_view import ScoreView
from .export_panel import ExportPanel
from .piano_roll import PianoRollWidget
from .notation_view import NotationView


class MainWindow(QMainWindow):
    """Top-level window for the Mariachi Music application."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Mariachi Music — Score Generator")
        self.resize(1400, 800)
        self._current_score: Score | None = None
        self._current_project_path: Path | None = None
        self._selected_part_index = 0
        self._preview_dir = Path(tempfile.gettempdir()) / "mariachi_music_preview"
        self._build_ui()
        self._build_menu()

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Horizontal)

        # Left: controls
        self._controls = ControlsPanel()
        self._controls.setMinimumWidth(260)
        self._controls.setMaximumWidth(360)
        self._controls.generate_requested.connect(self._on_generate)
        self._controls.notes_requested.connect(self._on_add_notes)
        self._controls.chords_requested.connect(self._on_add_chords)
        self._controls.template_requested.connect(self._on_generate_template)
        self._controls.classify_audio_requested.connect(self._on_classify_audio)
        self._controls.add_instrument_requested.connect(self._on_add_instrument)
        self._controls.remove_instrument_requested.connect(self._on_remove_instrument)
        self._controls.selected_part_changed.connect(self._on_selected_part_changed)
        splitter.addWidget(self._controls)

        # Center: tabbed view with Score Table and Piano Roll
        self._center_tabs = QTabWidget()
        self._center_tabs.setTabPosition(QTabWidget.North)
        self._center_tabs.setDocumentMode(True)
        self._center_tabs.setStyleSheet(
            "QTabBar::tab { padding: 6px 16px; font-size: 12px; }"
            "QTabBar::tab:selected { font-weight: bold; }"
        )

        # Tab 0: original note-table view
        self._score_view = ScoreView()
        self._center_tabs.addTab(self._score_view, "Score Table")

        # Tab 1: staff notation preview
        self._notation_view = NotationView()
        self._notation_scroll = QScrollArea()
        self._notation_scroll.setWidgetResizable(False)
        self._notation_scroll.setWidget(self._notation_view)
        self._center_tabs.addTab(self._notation_scroll, "Staff View")

        # Tab 2: piano roll editor
        self._piano_roll = PianoRollWidget()
        self._piano_roll.notes_changed.connect(self._on_notes_changed)
        self._center_tabs.addTab(self._piano_roll, "Piano Roll")
        self._center_tabs.currentChanged.connect(self._on_tab_changed)

        splitter.addWidget(self._center_tabs)

        # Right: export panel
        self._export_panel = ExportPanel()
        self._export_panel.setMinimumWidth(180)
        self._export_panel.setMaximumWidth(240)
        self._export_panel.status_message.connect(self._show_status)
        splitter.addWidget(self._export_panel)

        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._show_status("Ready. Choose a key, instrument, and duration, then click Generate Scale.")

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        new_action = QAction("New Score", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._new_score)
        file_menu.addAction(new_action)

        open_action = QAction("Open Project…", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_project)
        file_menu.addAction(open_action)

        save_action = QAction("Save Project", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_project)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save Project As…", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self._save_project_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        xml_action = QAction("Export MusicXML…", self)
        xml_action.setShortcut("Ctrl+Shift+X")
        xml_action.triggered.connect(self._export_panel._export_musicxml)
        file_menu.addAction(xml_action)

        mid_action = QAction("Export MIDI…", self)
        mid_action.setShortcut("Ctrl+Shift+M")
        mid_action.triggered.connect(self._export_panel._export_midi)
        file_menu.addAction(mid_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # View menu
        view_menu = menubar.addMenu("View")

        table_action = QAction("Score Table", self)
        table_action.setShortcut("Ctrl+1")
        table_action.triggered.connect(lambda: self._center_tabs.setCurrentIndex(0))
        view_menu.addAction(table_action)

        roll_action = QAction("Piano Roll", self)
        roll_action.setShortcut("Ctrl+2")
        roll_action.triggered.connect(lambda: self._center_tabs.setCurrentIndex(2))
        view_menu.addAction(roll_action)

        staff_action = QAction("Staff View", self)
        staff_action.setShortcut("Ctrl+3")
        staff_action.triggered.connect(lambda: self._center_tabs.setCurrentIndex(1))
        view_menu.addAction(staff_action)

        # Tools menu
        tools_menu = menubar.addMenu("Tools")
        gen_action = QAction("Generate Scale", self)
        gen_action.setShortcut("Ctrl+G")
        gen_action.triggered.connect(lambda: self._controls.generate_btn.click())
        tools_menu.addAction(gen_action)

        template_action = QAction("Generate Mariachi Arrangement", self)
        template_action.setShortcut("Ctrl+Shift+G")
        template_action.triggered.connect(lambda: self._controls.generate_template_btn.click())
        tools_menu.addAction(template_action)

        classify_action = QAction("Classify Audio Genre…", self)
        classify_action.triggered.connect(self._on_classify_audio)
        tools_menu.addAction(classify_action)

        # Help menu
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _on_generate(self, params: dict) -> None:
        try:
            generated = generate_scale_score(
                key=params["key"],
                mode=params["mode"],
                octave=params["octave"],
                duration=params["duration"],
                time_signature=params["time_signature"],
                tempo=params["tempo"],
                instrument=params["instrument"],
                ascending=params["ascending"],
                title=params["title"],
                composer=params["composer"],
            )
            scale_part = generated.parts[0]
            score = self._ensure_score(params)
            part = self._selected_part()
            if part is None:
                raise ValueError("Add or select an instrument before generating a scale.")
            for measure in scale_part.measures:
                for event in measure.events:
                    if hasattr(event, "pitch"):
                        part.add_note(str(event.pitch), str(event.duration), getattr(event, "velocity", 90))
        except Exception as exc:
            self._show_status(f"Generation error: {exc}")
            QMessageBox.warning(self, "Generation Error", str(exc))
            return

        self._refresh_score_views()

        note_count = sum(len(p.all_notes) for p in score.parts)
        measure_count = sum(len(p.measures) for p in score.parts)
        self._show_status(
            f"Added scale to {part.instrument.name}: {score.title} — "
            f"{note_count} notes, "
            f"{measure_count} measures."
        )

    def _ensure_score(self, params: dict) -> Score:
        if self._current_score is not None:
            if not self._current_score.parts:
                self._current_score.new_part(params["instrument"])
            return self._current_score

        ts = TimeSignature.parse(params["time_signature"])
        score = Score(
            title=params["title"],
            composer=params["composer"],
            tempo=Tempo(params["tempo"]),
            key_signature=KeySignature(params["key"], params["mode"]),
            time_signature=ts,
        )
        part = Part(
            instrument=Instrument.by_name(params["instrument"]),
            default_ts=ts,
        )
        score.add_part(part)
        self._current_score = score
        return score

    def _selected_part(self) -> Part | None:
        if self._current_score is None or not self._current_score.parts:
            return None
        self._selected_part_index = max(
            0,
            min(self._selected_part_index, len(self._current_score.parts) - 1),
        )
        return self._current_score.parts[self._selected_part_index]

    def _tokens(self, text: str) -> list[str]:
        return [item.strip() for chunk in text.split(",") for item in chunk.split() if item.strip()]

    def _with_default_octave(self, token: str, octave: int) -> str:
        if token[-1:].isdigit():
            return token
        return f"{token}{octave}"

    def _on_add_notes(self, params: dict) -> None:
        try:
            tokens = [
                self._with_default_octave(token, params["octave"])
                for token in self._tokens(params["notes"])
            ]
            if not tokens:
                raise ValueError("Enter at least one note, for example C4 D4 E4.")

            score = self._ensure_score(params)
            part = self._selected_part()
            if part is None:
                raise ValueError("Add an instrument before adding notes.")
            part.add_notes(tokens, duration=params["duration"])
        except Exception as exc:
            self._show_status(f"Note entry error: {exc}")
            QMessageBox.warning(self, "Note Entry Error", str(exc))
            return

        self._refresh_score_views()
        self._show_status(f"Added notes: {', '.join(tokens)}")

    def _on_add_chords(self, params: dict) -> None:
        try:
            written = parse_chord_sequence(params["chords"], octave=params["octave"])
            if not written:
                raise ValueError("Enter at least one chord, for example G, A, D, C.")

            score = self._ensure_score(params)
            part = self._selected_part()
            if part is None:
                raise ValueError("Add an instrument before adding chords.")
            for item in written:
                part.add_chord(list(item.pitches), params["duration"])
        except Exception as exc:
            self._show_status(f"Chord entry error: {exc}")
            QMessageBox.warning(self, "Chord Entry Error", str(exc))
            return

        self._refresh_score_views()
        preview = "  ".join(f"{item.symbol}=({', '.join(item.pitches)})" for item in written)
        self._show_status(f"Added chords: {preview}")

    def _on_generate_template(self, params: dict) -> None:
        mode = params["mode"] if params["mode"] in {"major", "minor"} else "major"
        try:
            result = generate_mariachi_arrangement(MariachiSongRequest(
                genre=params["genre"],
                context=params["context"],
                key=params["key"],
                mode=mode,
                tempo=params["tempo"],
                length=params["length"],
                subtype=params["subtype"],
                title=params["title"],
                composer=params["composer"],
            ))
        except Exception as exc:
            self._show_status(f"Template generation error: {exc}")
            QMessageBox.warning(self, "Template Generation Error", str(exc))
            return

        self._current_score = result.score
        self._selected_part_index = 0
        self._current_project_path = None
        self._refresh_score_views()
        section_path = result.write_section_map(self._preview_dir / "preview.sections.json")
        self._show_status(
            f"Generated {result.template.genre} arrangement: "
            f"{' '.join(section.label for section in result.sections)} | {section_path.name}"
        )

    def _on_classify_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Classify Mariachi Audio",
            "",
            "Audio Files (*.wav *.mp3 *.m4a *.flac *.ogg);;All Files (*)",
        )
        if not path:
            return
        try:
            guess = classify_audio_genre(path)
        except Exception as exc:
            self._show_status(f"Classification error: {exc}")
            QMessageBox.warning(self, "Classification Error", str(exc))
            return

        reasoning = "\n".join(f"- {line}" for line in guess.reasoning)
        QMessageBox.information(
            self,
            "Mariachi Genre Guess",
            (
                f"Genre: {guess.genre}\n"
                f"Confidence: {guess.confidence:.3f}\n"
                f"Tempo: {guess.tempo_bpm:.1f} bpm\n"
                f"Meter hint: {guess.meter_hint}\n\n"
                f"Reasoning:\n{reasoning}"
            ),
        )
        self._show_status(
            f"Audio guess: {guess.genre} ({guess.confidence:.3f}), "
            f"{guess.tempo_bpm:.1f} bpm, meter {guess.meter_hint}"
        )

    def _on_add_instrument(self, name: str) -> None:
        params = self._controls.get_score_params()
        if self._current_score is None:
            self._current_score = Score(
                title=params["title"],
                composer=params["composer"],
                tempo=Tempo(params["tempo"]),
                key_signature=KeySignature(params["key"], params["mode"]),
                time_signature=TimeSignature.parse(params["time_signature"]),
            )
        score = self._current_score
        score.new_part(name)
        self._selected_part_index = len(score.parts) - 1
        self._refresh_score_views()
        self._show_status(f"Added instrument: {name}")

    def _on_remove_instrument(self, index: int) -> None:
        if self._current_score is None or index < 0:
            return
        try:
            removed = self._current_score.remove_part(index)
        except IndexError:
            return
        self._selected_part_index = max(0, min(index, len(self._current_score.parts) - 1))
        self._refresh_score_views()
        self._show_status(f"Removed instrument: {removed.instrument.name}")

    def _on_selected_part_changed(self, index: int) -> None:
        if index < 0:
            return
        self._selected_part_index = index
        self._refresh_score_views(load_staff=False)
        part = self._selected_part()
        if part is not None:
            self._show_status(f"Editing: {part.instrument.name}")

    def _refresh_score_views(self, load_staff: bool = True) -> None:
        if self._current_score is None:
            return
        self._score_view.load_score(self._current_score)
        if load_staff:
            self._notation_view.load_score(self._current_score)
        self._export_panel.set_score(self._current_score)
        part_names = [part.instrument.name for part in self._current_score.parts]
        self._controls.set_parts(part_names, self._selected_part_index)
        part = self._selected_part()
        if part is not None:
            self._piano_roll.load_part(part)
        else:
            self._piano_roll.clear()
        if load_staff:
            self._write_preview_files()

    def _write_preview_files(self) -> None:
        if self._current_score is None:
            return
        try:
            self._preview_dir.mkdir(parents=True, exist_ok=True)
            xml_path = self._current_score.export_musicxml(self._preview_dir / "preview.musicxml")
            mid_path = self._current_score.export_midi(self._preview_dir / "preview.mid")
            self._show_status(f"Preview files updated: {xml_path.name}, {mid_path.name}")
        except Exception as exc:
            self._show_status(f"Preview file error: {exc}")

    def _on_tab_changed(self, index: int) -> None:
        if index == 1 and self._current_score is not None:
            self._notation_view.load_score(self._current_score)
            self._write_preview_files()

    def _on_notes_changed(self) -> None:
        """Called whenever the piano roll modifies the Part.

        Refreshes the score table view to stay in sync with edits.
        """
        if self._current_score is not None:
            self._score_view.load_score(self._current_score)
            self._notation_view.load_score(self._current_score)
            self._export_panel.set_score(self._current_score)
            self._write_preview_files()
            note_count = sum(len(p.all_notes) for p in self._current_score.parts)
            self._show_status(
                f"{self._current_score.title} — "
                f"{note_count} notes (piano roll edit)"
            )

    def _new_score(self) -> None:
        self._current_score = None
        self._current_project_path = None
        self._score_view.clear()
        self._notation_view.clear()
        self._piano_roll.clear()
        self._selected_part_index = 0
        self._controls.set_parts([])
        self._export_panel.set_score(None)  # type: ignore[arg-type]
        self._show_status("New score. Configure settings and click Generate Scale.")

    def _save_project(self) -> None:
        if self._current_project_path is None:
            self._save_project_as()
            return
        self._save_project_to(self._current_project_path)

    def _save_project_as(self) -> None:
        if self._current_score is None:
            self._show_status("No score to save.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Mariachi Project",
            "",
            "Mariachi Project (*.mariachi.json);;JSON Files (*.json)",
        )
        if not path:
            return
        save_path = Path(path)
        if save_path.suffix != ".json":
            save_path = save_path.with_suffix(".mariachi.json")
        self._save_project_to(save_path)

    def _save_project_to(self, path: Path) -> None:
        if self._current_score is None:
            self._show_status("No score to save.")
            return
        try:
            saved = save_score_project(self._current_score, path)
        except Exception as exc:
            QMessageBox.warning(self, "Save Error", str(exc))
            self._show_status(f"Save error: {exc}")
            return
        self._current_project_path = saved
        self._show_status(f"Saved project: {saved}")

    def _open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Mariachi Project",
            "",
            "Mariachi Project (*.mariachi.json *.json);;All Files (*)",
        )
        if not path:
            return
        try:
            self._current_score = load_score_project(path)
        except Exception as exc:
            QMessageBox.warning(self, "Open Error", str(exc))
            self._show_status(f"Open error: {exc}")
            return
        self._current_project_path = Path(path)
        self._selected_part_index = 0
        self._refresh_score_views()
        self._show_status(f"Opened project: {path}")

    def _show_status(self, message: str) -> None:
        self._status.showMessage(message)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Mariachi Music",
            "Mariachi Music v0.1\n\n"
            "Score generation, transcription, and sheet music export.\n\n"
            "Generate scales → edit in Piano Roll → export MusicXML / MIDI.",
        )
