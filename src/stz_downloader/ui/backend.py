"""Bridge between the QML UI and the local FastAPI server.

All network I/O runs on a worker ``QThread`` so the GUI never blocks waiting on
the bridge/aria2. The worker owns its HTTP client and WebSocket (created on the
worker thread) and emits results back to the main-thread ``Backend``, which
updates the QML-facing properties. Cross-thread signal connections are
automatically queued by Qt, so property updates happen safely on the GUI thread.
"""
from __future__ import annotations

import ctypes
import json
import sys

import httpx
from PySide6.QtCore import Property, QObject, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWebSockets import QWebSocket

from ..config import Config


class _Worker(QObject):
    """Lives on the worker thread; does every network call."""

    downloads = Signal(object, object, object, bool)  # items, pending, global, pending_grew
    settingsLoaded = Signal(object)
    failed = Signal(str)

    def __init__(self, base: str) -> None:
        super().__init__()
        self._base = base
        self._ws_url = base.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
        self._http: httpx.Client | None = None
        self._ws: QWebSocket | None = None
        self._reconnect_timer: QTimer | None = None
        self._prev_pending = 0
        self._ws_connected = False
        self._ws_connecting = False

    @Slot()
    def begin(self) -> None:
        # Created here so the client, socket, and timer belong to the worker thread.
        self._http = httpx.Client(timeout=10.0)
        self._ws = QWebSocket()
        self._ws.connected.connect(self._on_ws_connected)
        self._ws.disconnected.connect(self._on_ws_disconnected)
        self._ws.textMessageReceived.connect(self._on_ws_message)
        self._ws.errorOccurred.connect(self._on_ws_error)

        self._reconnect_timer = QTimer()
        self._reconnect_timer.setInterval(2000)
        self._reconnect_timer.timeout.connect(self._ensure_ws)
        self._reconnect_timer.start()

        self._load_settings()
        self._poll()
        self._ensure_ws()

    @Slot()
    def stop(self) -> None:
        if self._reconnect_timer:
            self._reconnect_timer.stop()
        if self._ws:
            self._ws.close()
        if self._http:
            self._http.close()

    def _emit_downloads(self, data: dict) -> None:
        pending = data.get("pending", [])
        grew = len(pending) > self._prev_pending
        self._prev_pending = len(pending)
        self.downloads.emit(data.get("items", []), pending, data.get("global", {}), grew)

    @Slot()
    def _poll(self) -> None:
        try:
            data = self._http.get(f"{self._base}/api/downloads").json()
            self._emit_downloads(data)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))

    @Slot()
    def _ensure_ws(self) -> None:
        if not self._ws or self._ws_connected or self._ws_connecting:
            return
        self._ws_connecting = True
        self._ws.open(QUrl(self._ws_url))

    @Slot()
    def _on_ws_connected(self) -> None:
        self._ws_connected = True
        self._ws_connecting = False

    @Slot()
    def _on_ws_disconnected(self) -> None:
        self._ws_connected = False
        self._ws_connecting = False

    @Slot(object)
    def _on_ws_error(self, _error) -> None:
        self._ws_connected = False
        self._ws_connecting = False
        if self._ws:
            self.failed.emit(f"WebSocket: {self._ws.errorString()}")

    @Slot(str)
    def _on_ws_message(self, message: str) -> None:
        try:
            data = json.loads(message)
        except json.JSONDecodeError as exc:
            self.failed.emit(f"Invalid WebSocket payload: {exc}")
            return
        if data.get("type") == "downloads":
            self._emit_downloads(data)

    @Slot()
    def _load_settings(self) -> None:
        try:
            self.settingsLoaded.emit(self._http.get(f"{self._base}/api/settings").json())
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))

    @Slot(str, object)
    def post(self, path: str, payload: object) -> None:
        try:
            self._http.post(f"{self._base}{path}", json=payload or None)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
        self._poll()

    @Slot(str, object)
    def put_settings(self, path: str, payload: object) -> None:
        try:
            self.settingsLoaded.emit(
                self._http.put(f"{self._base}{path}", json=payload).json()
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class Backend(QObject):
    downloadsChanged = Signal()
    pendingChanged = Signal()
    globalChanged = Signal()
    newPendingArrived = Signal()
    settingsChanged = Signal()
    statusChanged = Signal(str)

    # internal signals that drive the worker (connected to its slots)
    _requestPost = Signal(str, object)
    _requestPut = Signal(str, object)

    def __init__(self, cfg: Config) -> None:
        super().__init__()
        base = f"http://{cfg.server.host}:{cfg.server.port}"
        self._items: list[dict] = []
        self._pending: list[dict] = []
        self._global: dict = {}
        self._settings: dict = {}
        self._status = ""

        self._thread = QThread()
        self._worker = _Worker(base)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.begin)
        self._worker.downloads.connect(self._on_downloads)
        self._worker.settingsLoaded.connect(self._on_settings)
        self._worker.failed.connect(self._on_failed)
        self._requestPost.connect(self._worker.post)
        self._requestPut.connect(self._worker.put_settings)

    # -- properties -----------------------------------------------------
    @Property("QVariantList", notify=downloadsChanged)
    def downloads(self):  # noqa: N802
        return self._items

    @Property("QVariantList", notify=pendingChanged)
    def pending(self):
        return self._pending

    @Property("QVariantMap", notify=globalChanged)
    def globalStats(self):  # noqa: N802
        return self._global

    @Property("QVariantMap", notify=settingsChanged)
    def settings(self):
        return self._settings

    @Property(str, notify=statusChanged)
    def status(self):
        return self._status

    def _set_status(self, msg: str) -> None:
        if msg != self._status:
            self._status = msg
            self.statusChanged.emit(msg)

    def _main_window_handle(self) -> int:
        for window in QGuiApplication.allWindows():
            if window.title() == "STZ Downloader":
                return int(window.winId())
        return 0

    # -- lifecycle ------------------------------------------------------
    def start(self) -> None:
        self._thread.start()

    @Slot()
    def stop(self) -> None:
        # Ask the worker to release its resources, then stop the thread.
        if self._thread.isRunning():
            self._worker.stop()
            self._thread.quit()
            self._thread.wait(2000)

    # -- worker callbacks (run on the GUI thread) -----------------------
    @Slot(object, object, object, bool)
    def _on_downloads(self, items, pending, global_stats, grew) -> None:
        self._items = items
        self._global = global_stats
        self.downloadsChanged.emit()
        self.globalChanged.emit()
        if pending != self._pending:
            self._pending = pending
            self.pendingChanged.emit()
            if grew:
                self.newPendingArrived.emit()
        self._set_status("")

    @Slot(object)
    def _on_settings(self, settings) -> None:
        self._settings = settings
        self.settingsChanged.emit()

    @Slot(str)
    def _on_failed(self, msg) -> None:
        self._set_status(f"Bridge offline: {msg}")

    # -- actions (fire-and-forget to the worker) ------------------------
    @Slot(str, int)
    def addUrl(self, url: str, connections: int = 8) -> None:  # noqa: N802
        self._requestPost.emit("/api/download", {"url": url, "connections": connections})

    @Slot(str, int)
    def confirmPending(self, pid: str, connections: int) -> None:  # noqa: N802
        self._requestPost.emit(f"/api/pending/{pid}/confirm", {"connections": connections})

    @Slot(str)
    def cancelPending(self, pid: str) -> None:  # noqa: N802
        self._requestPost.emit(f"/api/pending/{pid}/cancel", {})

    @Slot()
    def flashTaskbar(self) -> None:  # noqa: N802
        if sys.platform != "win32":
            return
        hwnd = self._main_window_handle()
        if not hwnd:
            return

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("hwnd", ctypes.c_void_p),
                ("dwFlags", ctypes.c_uint),
                ("uCount", ctypes.c_uint),
                ("dwTimeout", ctypes.c_uint),
            ]

        flash_tray = 0x00000002
        flash_timer_no_fg = 0x0000000C
        info = FLASHWINFO(
            ctypes.sizeof(FLASHWINFO),
            ctypes.c_void_p(hwnd),
            flash_tray | flash_timer_no_fg,
            5,
            0,
        )
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))

    @Slot("QVariantMap")
    def saveSettings(self, patch: dict) -> None:  # noqa: N802
        self._requestPut.emit("/api/settings", patch)

    @Slot(str)
    def pause(self, gid: str) -> None:
        self._requestPost.emit(f"/api/downloads/{gid}/pause", {})

    @Slot(str)
    def resume(self, gid: str) -> None:
        self._requestPost.emit(f"/api/downloads/{gid}/resume", {})

    @Slot(str)
    def cancel(self, gid: str) -> None:
        self._requestPost.emit(f"/api/downloads/{gid}/cancel", {})

    @Slot(str)
    def openDownload(self, gid: str) -> None:  # noqa: N802
        self._requestPost.emit(f"/api/downloads/{gid}/open", {})

    @Slot(str)
    def revealDownload(self, gid: str) -> None:  # noqa: N802
        self._requestPost.emit(f"/api/downloads/{gid}/reveal", {})

    @Slot()
    def clearFinished(self) -> None:  # noqa: N802
        self._requestPost.emit("/api/downloads/purge", {})
