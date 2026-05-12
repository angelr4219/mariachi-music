"""GUI tab for importing existing songs into local analysis folders."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QUrl, pyqtSignal
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtWidgets import (
    QComboBox,
    QFileDialog,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mariachi_music.transcription.song_importer import (
    DEFAULT_IMPORT_ROOT,
    ImportedSong,
    import_local_audio,
    import_youtube_audio,
)


class SongImportView(QWidget):
    """Import local/YouTube audio, write WAV, and create rough stems."""

    status_message = pyqtSignal(str)
    import_completed = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        box = QGroupBox("Import Existing Song")
        form = QFormLayout(box)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Example: Amor Eterno Study")
        form.addRow("Title:", self.title_edit)

        self.youtube_edit = QLineEdit()
        self.youtube_edit.setPlaceholderText("Paste YouTube URL for authorized analysis")
        form.addRow("YouTube URL:", self.youtube_edit)

        local_row = QWidget()
        local_layout = QHBoxLayout(local_row)
        local_layout.setContentsMargins(0, 0, 0, 0)
        self.local_path_edit = QLineEdit()
        self.local_path_edit.setPlaceholderText("Choose local audio file")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_local)
        local_layout.addWidget(self.local_path_edit)
        local_layout.addWidget(browse_btn)
        form.addRow("Local File:", local_row)

        output_row = QWidget()
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        self.output_root_edit = QLineEdit(str(DEFAULT_IMPORT_ROOT))
        out_btn = QPushButton("Folder...")
        out_btn.clicked.connect(self._browse_output)
        output_layout.addWidget(self.output_root_edit)
        output_layout.addWidget(out_btn)
        form.addRow("Library Folder:", output_row)

        self.stems_check = QCheckBox("Create mariachi stems: guitarrón / rhythm / violins")
        self.stems_check.setChecked(True)
        form.addRow(self.stems_check)

        profile_box = QGroupBox("Song Profile")
        profile_form = QFormLayout(profile_box)

        self.genre_combo = QComboBox()
        self.genre_combo.addItems(["bolero", "ranchera", "son", "polca_ranchera"])
        self.genre_combo.setCurrentText("bolero")
        profile_form.addRow("Genre:", self.genre_combo)

        self.tempo_spin = QLineEdit("172")
        self.tempo_spin.setPlaceholderText("172")
        profile_form.addRow("Tempo BPM:", self.tempo_spin)

        self.instruments_edit = QLineEdit("Guitarrón, Guitar, Violin")
        self.instruments_edit.setPlaceholderText("Guitarrón, Guitar, Violin")
        profile_form.addRow("Instruments:", self.instruments_edit)

        self.strum_combo = QComboBox()
        self.strum_combo.addItems([
            "strum_with_chord_on_top",
            "block_chords",
            "arpeggio",
            "unknown",
        ])
        profile_form.addRow("Guitar Style:", self.strum_combo)

        self.section_notes_edit = QTextEdit()
        self.section_notes_edit.setPlaceholderText("Verse / chorus / intro / ending notes")
        self.section_notes_edit.setMaximumHeight(90)
        profile_form.addRow("Section Notes:", self.section_notes_edit)

        root.addWidget(profile_box)

        buttons = QWidget()
        button_layout = QHBoxLayout(buttons)
        button_layout.setContentsMargins(0, 0, 0, 0)
        self.import_local_btn = QPushButton("Import Local Audio")
        self.import_local_btn.clicked.connect(self._import_local)
        self.import_youtube_btn = QPushButton("Import YouTube Audio")
        self.import_youtube_btn.clicked.connect(self._import_youtube)
        button_layout.addWidget(self.import_local_btn)
        button_layout.addWidget(self.import_youtube_btn)
        form.addRow(buttons)

        root.addWidget(box)

        note = QLabel(
            "Use this for songs you own, created, licensed, or have permission to analyze. "
            "The app stores local working files and stems; it does not redistribute songs."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        root.addWidget(self.result_text, 1)

        player_box = QGroupBox("Generated Audio Player")
        player_layout = QVBoxLayout(player_box)
        self.audio_label = QLabel("No generated audio loaded.")
        self.audio_label.setWordWrap(True)
        player_layout.addWidget(self.audio_label)

        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        self.play_btn = QPushButton("Play")
        self.pause_btn = QPushButton("Pause")
        self.stop_btn = QPushButton("Stop")
        self.play_btn.clicked.connect(self._play_audio)
        self.pause_btn.clicked.connect(self._pause_audio)
        self.stop_btn.clicked.connect(self._stop_audio)
        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.pause_btn)
        controls_layout.addWidget(self.stop_btn)
        player_layout.addWidget(controls)
        root.addWidget(player_box)

        self._player = QMediaPlayer(self)
        self._audio_path: Path | None = None

    def _browse_local(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Audio File",
            "",
            "Audio Files (*.wav *.mp3 *.m4a *.flac *.ogg);;All Files (*)",
        )
        if path:
            self.local_path_edit.setText(path)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose Import Library Folder")
        if path:
            self.output_root_edit.setText(path)

    def _import_local(self) -> None:
        path = self.local_path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "Missing File", "Choose a local audio file first.")
            return
        self._run_import(lambda: import_local_audio(
            path,
            title=self.title_edit.text(),
            output_root=self.output_root_edit.text() or DEFAULT_IMPORT_ROOT,
            create_stems=self.stems_check.isChecked(),
            genre=self.genre_combo.currentText(),
            tempo_bpm=self._tempo_bpm(),
            instruments=self._instruments(),
            strum_style=self.strum_combo.currentText(),
            section_notes=self.section_notes_edit.toPlainText().strip(),
        ))

    def _import_youtube(self) -> None:
        url = self.youtube_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Paste a YouTube URL first.")
            return
        self._run_import(lambda: import_youtube_audio(
            url,
            title=self.title_edit.text(),
            output_root=self.output_root_edit.text() or DEFAULT_IMPORT_ROOT,
            create_stems=self.stems_check.isChecked(),
            genre=self.genre_combo.currentText(),
            tempo_bpm=self._tempo_bpm(),
            instruments=self._instruments(),
            strum_style=self.strum_combo.currentText(),
            section_notes=self.section_notes_edit.toPlainText().strip(),
        ))

    def _run_import(self, fn) -> None:
        self.setEnabled(False)
        self.status_message.emit("Importing song...")
        try:
            result = fn()
        except Exception as exc:
            QMessageBox.warning(self, "Import Error", str(exc))
            self.status_message.emit(f"Import error: {exc}")
            return
        finally:
            self.setEnabled(True)

        self._show_result(result)
        self.import_completed.emit(result)
        self.status_message.emit(f"Imported song: {result.title}")

    def _show_result(self, result: ImportedSong) -> None:
        lines = [
            f"Title: {result.title}",
            f"Genre: {result.genre}",
            f"Tempo: {result.tempo_bpm:.1f} BPM",
            f"Time signature hint: {result.time_signature}",
            f"Instruments: {', '.join(result.instruments)}",
            f"Style: {result.strum_style}",
            f"Source type: {result.source_type}",
            f"Song folder: {result.song_dir}",
            f"WAV: {result.wav_path}",
            f"Stems folder: {result.stems_dir}",
            "",
            "Stems:",
        ]
        for name, path in result.stems.items():
            lines.append(f"  {name}: {path}")
        lines.extend(["", f"Manifest: {result.manifest_path}", "", result.rights_note])
        lines.extend([
            "",
            f"Profile: {getattr(result, 'profile_path', '')}",
            f"Analysis: {getattr(result, 'analysis_path', '')}",
            f"Analysis score: {getattr(result, 'analysis_score_path', '')}",
            "",
            "After import, the app loads a draft score and writes verification files under:",
            f"  {Path(result.song_dir) / 'verification'}",
            "Use the verification report to decide what to fix before exporting.",
        ])
        self.result_text.setPlainText("\n".join(lines))

    def set_audio_file(self, path: str | Path) -> None:
        path = Path(path)
        self._audio_path = path
        self.audio_label.setText(str(path))
        self._player.setMedia(QMediaContent(QUrl.fromLocalFile(str(path))))

    def _play_audio(self) -> None:
        if self._audio_path is None:
            QMessageBox.information(self, "No Audio", "No generated audio has been loaded yet.")
            return
        self._player.play()

    def _pause_audio(self) -> None:
        self._player.pause()

    def _stop_audio(self) -> None:
        self._player.stop()

    def _tempo_bpm(self) -> float:
        try:
            return float(self.tempo_spin.text().strip())
        except ValueError:
            return 172.0

    def _instruments(self) -> tuple[str, ...]:
        items = [item.strip() for item in self.instruments_edit.text().split(",")]
        cleaned = tuple(item for item in items if item)
        return cleaned or ("Guitarrón", "Guitar", "Violin")
