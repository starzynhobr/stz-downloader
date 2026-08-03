"""System tray icon.

The app is single-instance, so the tray never accumulates duplicates: a second
launch hands off to the running one instead of adding another icon.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class Tray:
    def __init__(
        self,
        icon: QIcon,
        on_open: Callable[[], None],
        on_quit: Callable[[], None],
        labels: dict[str, str],
    ) -> None:
        self._on_open = on_open
        self.icon = QSystemTrayIcon(icon)
        self.icon.setToolTip("STZ Downloader")

        self._menu = QMenu()
        self._open_action = QAction(labels.get("open", "Open"))
        self._open_action.triggered.connect(lambda: on_open())
        self._quit_action = QAction(labels.get("quit", "Quit"))
        self._quit_action.triggered.connect(lambda: on_quit())
        self._menu.addAction(self._open_action)
        self._menu.addSeparator()
        self._menu.addAction(self._quit_action)
        # setContextMenu already handles right-click; wiring it to activation
        # too would pop the menu twice.
        self.icon.setContextMenu(self._menu)

        self.icon.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # Left click and double click open; right click is the menu, which Qt
        # shows on its own.
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._on_open()

    def retranslate(self, labels: dict[str, str]) -> None:
        self._open_action.setText(labels.get("open", "Open"))
        self._quit_action.setText(labels.get("quit", "Quit"))

    def show(self) -> None:
        self.icon.show()

    def hide(self) -> None:
        self.icon.hide()
