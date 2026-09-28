"""PySide6/QML user interface."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt, QUrl, qInstallMessageHandler
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from ..config import Config
from .backend import Backend
from .translator import Translator
from .tray import Tray

QML_DIR = Path(__file__).resolve().parent / "qml"
_DLL_DIR_HANDLES = []


def _configure_qt_paths() -> None:
    if not getattr(sys, "frozen", False) or not hasattr(sys, "_MEIPASS"):
        return

    bundle_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    pyside_dir = bundle_dir / "PySide6"
    plugins_dir = pyside_dir / "plugins"
    qml_dir = pyside_dir / "qml"

    if pyside_dir.exists():
        os.environ["PATH"] = f"{pyside_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        if hasattr(os, "add_dll_directory"):
            _DLL_DIR_HANDLES.append(os.add_dll_directory(str(pyside_dir)))
    if plugins_dir.exists():
        QCoreApplication.addLibraryPath(str(plugins_dir))

    os.environ.setdefault("QML2_IMPORT_PATH", str(qml_dir))
    os.environ.setdefault("QT_PLUGIN_PATH", str(plugins_dir))
    logging.info("Configured Qt paths PySide6=%s plugins=%s qml=%s", pyside_dir, plugins_dir, qml_dir)


def _qt_message_handler(mode, context, message) -> None:
    file = getattr(context, "file", "") or ""
    line = getattr(context, "line", 0) or 0
    logging.warning("Qt[%s] %s:%s %s", mode, file, line, message)


def _app_icon_path() -> Path | None:
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.extend(
            [
                Path(sys.executable).resolve().parent / "Assets" / "stz-downloader.ico",
                Path(sys.executable).resolve().parent / "_internal" / "Assets" / "stz-downloader.ico",
            ]
        )
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / "Assets" / "stz-downloader.ico")  # type: ignore[attr-defined]
    candidates.append(Path(__file__).resolve().parents[3] / "assets" / "stz-downloader.ico")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def run_ui(
    cfg: Config,
    start_minimized: bool = False,
    base_url: str | None = None,
    auth_token: str | None = None,
) -> int:
    _configure_qt_paths()
    qInstallMessageHandler(_qt_message_handler)
    logging.info("Starting UI with QML dir %s", QML_DIR)

    # QApplication rather than QGuiApplication: QSystemTrayIcon and its menu
    # live in QtWidgets.
    app = QApplication(sys.argv)
    app.setApplicationName("STZ Downloader")
    app.setApplicationDisplayName("STZ Downloader")
    icon_path = _app_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(str(icon_path)))
        logging.info("Using app icon %s", icon_path)
    else:
        logging.warning("App icon not found")

    engine = QQmlApplicationEngine()
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        engine.addImportPath(str(Path(sys._MEIPASS) / "PySide6" / "qml"))  # type: ignore[attr-defined]
    engine.warnings.connect(
        lambda warnings: [
            logging.error("QML warning: %s", warning.toString()) for warning in warnings
        ]
    )
    backend = Backend(cfg, base_url=base_url, auth_token=auth_token)
    translator = Translator()
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("i18n", translator)

    qml_file = QML_DIR / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_file)))
    if not engine.rootObjects():
        logging.error("QML failed to load from %s", qml_file)
        return 1
    if icon_path:
        for root in engine.rootObjects():
            if hasattr(root, "setIcon"):
                root.setIcon(QIcon(str(icon_path)))

    window = engine.rootObjects()[0]

    def show_window() -> None:
        window.show()
        window.raise_()
        window.requestActivate()

    tray = None
    if icon_path:
        tray = Tray(
            QIcon(str(icon_path)),
            on_open=show_window,
            on_quit=app.quit,
            labels={"open": translator.tray_open, "quit": translator.tray_quit},
        )
        tray.show()
        translator.languageChanged.connect(
            lambda: tray.retranslate(
                {"open": translator.tray_open, "quit": translator.tray_quit}
            )
        )
    else:
        logging.warning("No app icon: running without a tray icon")

    # With a tray icon the window closing must not end the process -- the
    # bridge keeps serving the extension and downloads keep running. QML
    # decides whether a close hides or quits; this stops Qt quitting first.
    app.setQuitOnLastWindowClosed(tray is None)
    backend.focusRequested.connect(show_window)

    # Minimising should reach the tray too, not just closing. QML owns the
    # close path; the minimise path is only observable from here.
    def hide_if_minimized() -> None:
        if not tray:
            return
        try:
            minimized = bool(window.windowState() & Qt.WindowState.WindowMinimized)
        except TypeError:  # some platforms report an unrelated state type
            return
        if minimized and backend.settings.get("minimize_to_tray", True):
            window.hide()

    window.windowStateChanged.connect(lambda _state: hide_if_minimized())

    # Launched at login: come up in the tray rather than stealing focus.
    if start_minimized and tray:
        window.hide()

    def on_quit() -> None:
        if tray:
            tray.hide()
        backend.stop()

    app.aboutToQuit.connect(on_quit)  # stop the worker thread cleanly
    backend.start()
    return app.exec()
