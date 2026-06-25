"""Bridge between the QML UI and the local FastAPI server.

All HTTP I/O runs on a worker ``QThread`` so the GUI never blocks waiting on
the bridge/aria2. The worker owns its httpx client and a polling timer (both
created on the worker thread) and emits results back to the main-thread
``Backend``, which updates the QML-facing properties. Cross-thread signal
connections are automatically queued by Qt, so property updates happen safely
on the GUI thread.
"""
from __future__ import annotations

import httpx
from PySide6.QtCore import Property, QObject, QThread, QTimer, Signal, Slot

from ..config import Config


class _Worker(QObject):
    """Lives on the worker thread; does every network call."""

    downloads = Signal(object, object, bool)  # items, pending, pending_grew
    settingsLoaded = Signal(object)
    failed = Signal(str)

    def __init__(self, base: str) -> None:
        super().__init__()
        self._base = base
        self._http: httpx.Client | None = None
        self._timer: QTimer | None = None
        self._prev_pending = 0

    @Slot()
    def begin(self) -> None:
        # Created here so the client + timer belong to the worker thread.
        self._http = httpx.Client(timeout=10.0)
        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._poll)
        self._timer.start()
        self._load_settings()
        self._poll()

    @Slot()
    def stop(self) -> None:
        if self._timer:
            self._timer.stop()
        if self._http:
            self._http.close()

    @Slot()
    def _poll(self) -> None:
        try:
            data = self._http.get(f"{self._base}/api/downloads").json()
            pending = data.get("pending", [])
            grew = len(pending) > self._prev_pending
            self._prev_pending = len(pending)
            self.downloads.emit(data.get("items", []), pending, grew)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))

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
    @Slot(object, object, bool)
    def _on_downloads(self, items, pending, grew) -> None:
        self._items = items
        self.downloadsChanged.emit()
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

    @Slot()
    def clearFinished(self) -> None:  # noqa: N802
        self._requestPost.emit("/api/downloads/purge", {})
