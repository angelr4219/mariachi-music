"""Main application window."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAction,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QWidget,
)

from mariachi_music.core.score import Score
from mariachi_music.generation.scale_generator import generate_scale_score
from .controls_panel import ControlsPanel
from .score_view import ScoreView
from .export_panel import ExportPanel


class MainWindow(QMainWindow):
    """Top-level window for the Mariachi Music application."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Mariachi Music — Score Generator")
        self.resize(1280, 720)
        self._current_score: Score | None = None
        self._build_ui()
        self._build_menu()

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Horizontal)

        # Left: controls
        self._controls = ControlsPanel()
        self._controls.setMinimumWidth(260)
        self._controls.setMaximumWidth(360)
        self._controls.generate_requested.connect(self._on_generate)
        splitter.addWidget(self._controls)

        # Center: score view
        self._score_view = ScoreView()
        splitter.addWidget(self._score_view)

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

        # Tools menu
        tools_menu = menubar.addMenu("Tools")
        gen_action = QAction("Generate Scale", self)
        gen_action.setShortcut("Ctrl+G")
        gen_action.triggered.connect(lambda: self._controls.generate_btn.click())
        tools_menu.addAction(gen_action)

        # Help menu
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _on_generate(self, params: dict) -> None:
        try:
            score = generate_scale_score(
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
        except Exception as exc:
            self._show_status(f"Generation error: {exc}")
            QMessageBox.warning(self, "Generation Error", str(exc))
            return

        self._current_score = score
        self._score_view.load_score(score)
        self._export_panel.set_score(score)
        self._show_status(
            f"Generated: {score.title} — "
            f"{sum(len(p.all_notes) for p in score.parts)} notes, "
            f"{sum(len(p.measures) for p in score.parts)} measures."
        )

    def _new_score(self) -> None:
        self._current_score = None
        self._score_view.clear()
        self._export_panel.set_score(None)  # type: ignore[arg-type]
        self._show_status("New score. Configure settings and click Generate Scale.")

    def _show_status(self, message: str) -> None:
        self._status.showMessage(message)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Mariachi Music",
            "Mariachi Music v0.1\n\n"
            "Score generation, transcription, and sheet music export.\n\n"
            "Generate scales → export MusicXML → open in MuseScore.",
        )
