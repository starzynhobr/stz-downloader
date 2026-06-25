"""PySide6/QML user interface."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from ..config import Config
from .backend import Backend
from .translator import Translator

QML_DIR = Path(__file__).resolve().parent / "qml"


def run_ui(cfg: Config) -> int:
    app = QGuiApplication(sys.argv)
    app.setApplicationName("stz-downloader")

    engine = QQmlApplicationEngine()
    backend = Backend(cfg)
    translator = Translator()
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("i18n", translator)

    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        return 1

    app.aboutToQuit.connect(backend.stop)  # stop the worker thread cleanly
    backend.start()
    return app.exec()
