"""GUI entry point."""

from __future__ import annotations

import sys


def main() -> None:
    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import Qt
    except ImportError:
        print("PyQt5 is required for the GUI. Install it with: pip install PyQt5")
        sys.exit(1)

    from .main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Mariachi Music")
    app.setApplicationVersion("0.1")

    # Use a clean style
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
