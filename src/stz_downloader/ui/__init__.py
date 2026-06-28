"""PySide6/QML user interface."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QTimer, QUrl, qInstallMessageHandler
from PySide6.QtGui import QAction, QIcon, QWindow
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

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


class _TrayController(QObject):
    def __init__(
        self,
        app: QApplication,
        window: QWindow,
        icon: QIcon,
        backend: Backend,
        translator: Translator,
    ) -> None:
        super().__init__()
        self._app = app
        self._window = window
        self._backend = backend
        self._translator = translator
        self._enabled = True
        self._quitting = False

        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("STZ Downloader")
        self._menu = QMenu()
        self._show_action = QAction(self)
        self._hide_action = QAction(self)
        self._quit_action = QAction(self)
        self._menu.addAction(self._show_action)
        self._menu.addAction(self._hide_action)
        self._menu.addSeparator()
        self._menu.addAction(self._quit_action)
        self._tray.setContextMenu(self._menu)

        self._show_action.triggered.connect(self.show_window)
        self._hide_action.triggered.connect(self.hide_window)
        self._quit_action.triggered.connect(self.quit_app)
        self._tray.activated.connect(self._on_activated)
        self._translator.languageChanged.connect(self._update_menu)
        self._backend.settingsChanged.connect(self._sync_settings)
        self._window.installEventFilter(self)

        self._update_menu()
        self._sync_settings()
        self._tray.show()

    def _tr(self, key: str, fallback: str) -> str:
        return self._translator.strings.get(key, fallback)

    def _update_menu(self) -> None:
        self._show_action.setText(self._tr("tray_show", "Show STZ Downloader"))
        self._hide_action.setText(self._tr("tray_hide", "Hide to tray"))
        self._quit_action.setText(self._tr("tray_quit", "Quit"))

    def _sync_settings(self) -> None:
        settings = self._backend.settings
        self._enabled = bool(settings.get("minimize_to_tray", True))

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self._window and not self._quitting:
            if event.type() == QEvent.Type.Close:
                if self._enabled:
                    event.ignore()
                    self.hide_window()
                    return True
                self._quitting = True
                self._tray.hide()
                QTimer.singleShot(0, self._app.quit)
            if self._enabled and event.type() == QEvent.Type.WindowStateChange:
                QTimer.singleShot(0, self._hide_if_minimized)
        return super().eventFilter(watched, event)

    def _hide_if_minimized(self) -> None:
        try:
            minimized = bool(self._window.windowState() & QWindow.WindowState.WindowMinimized)
        except TypeError:
            minimized = False
        if self._enabled and minimized:
            self.hide_window()

    def _on_activated(self, reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_window()

    def show_window(self) -> None:
        self._window.setVisibility(QWindow.Visibility.Windowed)
        self._window.show()
        self._window.raise_()
        self._window.requestActivate()

    def hide_window(self) -> None:
        self._window.hide()

    def quit_app(self) -> None:
        self._quitting = True
        self._tray.hide()
        self._app.quit()


def run_ui(cfg: Config, start_minimized: bool = False) -> int:
    _configure_qt_paths()
    qInstallMessageHandler(_qt_message_handler)
    logging.info("Starting UI with QML dir %s", QML_DIR)

    app = QApplication(sys.argv)
    app.setApplicationName("STZ Downloader")
    app.setApplicationDisplayName("STZ Downloader")
    app.setQuitOnLastWindowClosed(False)
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
    root_window = engine.rootObjects()[0]
    if not isinstance(root_window, QWindow):
        logging.error("QML root is not a window: %s", type(root_window))
        return 1

    if icon_path and QSystemTrayIcon.isSystemTrayAvailable():
        tray = _TrayController(app, root_window, QIcon(str(icon_path)), backend, translator)
        app._stz_tray = tray  # type: ignore[attr-defined]
        if start_minimized:
            QTimer.singleShot(0, tray.hide_window)
    elif start_minimized:
        root_window.showMinimized()

    app.aboutToQuit.connect(backend.stop)  # stop the worker thread cleanly
    backend.start()
    return app.exec()
