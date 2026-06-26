"""PySide6/QML user interface."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QUrl, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine

from ..config import Config
from .backend import Backend
from .translator import Translator

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


def run_ui(cfg: Config) -> int:
    _configure_qt_paths()
    qInstallMessageHandler(_qt_message_handler)
    logging.info("Starting UI with QML dir %s", QML_DIR)

    app = QGuiApplication(sys.argv)
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
    backend = Backend(cfg)
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

    app.aboutToQuit.connect(backend.stop)  # stop the worker thread cleanly
    backend.start()
    return app.exec()
