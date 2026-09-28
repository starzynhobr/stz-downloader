"""Generate high-resolution store-ready screenshots for STZ Downloader.

Produces 1280x800 screenshots matching the Chrome Web Store & Mozilla AMO specifications:
- screenshot_1_main.png: Main dashboard with active and completed downloads
- screenshot_2_settings.png: Settings drawer with options and file extension filters
- screenshot_3_confirm.png: Download confirmation dialog (IDM-style prompt)
- screenshot_4_popup.png: Browser extension popup interface

Saves images to assets/screenshots/ and copies them to the artifact folder.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

import PySide6.QtQuick  # Register QQuickItem C++ converter
from PySide6.QtCore import Property, QEventLoop, QObject, QSize, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QImage, QPainter
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
QML_DIR = ROOT / "src" / "stz_downloader" / "ui" / "qml"
OUT_DIR = ROOT / "assets" / "screenshots"
ARTIFACT_DIR = Path(r"C:\Users\tz\.gemini\antigravity\brain\9f725043-962d-4d01-9dc0-7ee92a97927c")

SAMPLE_SETTINGS = {
    "intercept_enabled": True,
    "auto_start": False,
    "intercept_all": False,
    "clipboard_enabled": True,
    "start_with_windows": True,
    "minimize_to_tray": True,
    "disk_guard_enabled": True,
    "disk_reserve_mb": 2048,
    "download_limit_bps": 0,
    "connections": 8,
    "extensions": ["zip", "iso", "exe", "msi", "tar.gz", "7z", "rar", "mp4", "mkv", "pdf"],
}

SAMPLE_DOWNLOADS = [
    {
        "gid": "1",
        "name": "ubuntu-24.04.1-desktop-amd64.iso",
        "status": "active",
        "progress": 0.65,
        "completed": 3968250000,
        "total": 6105000000,
        "speed": 44564480,  # 42.5 MB/s
        "speedLimit": 0,
        "path": "C:/Users/User/Downloads/ubuntu-24.04.1-desktop-amd64.iso",
        "error": "",
    },
    {
        "gid": "2",
        "name": "linux-6.10.9.tar.xz",
        "status": "active",
        "progress": 0.82,
        "completed": 116522000,
        "total": 142100000,
        "speed": 15938304,  # 15.2 MB/s
        "speedLimit": 0,
        "path": "C:/Users/User/Downloads/linux-6.10.9.tar.xz",
        "error": "",
    },
    {
        "gid": "3",
        "name": "blender-4.2.0-windows-x64.msi",
        "status": "complete",
        "progress": 1.0,
        "completed": 359137280,
        "total": 359137280,
        "speed": 0,
        "speedLimit": 0,
        "path": "C:/Users/User/Downloads/blender-4.2.0-windows-x64.msi",
        "error": "",
    },
    {
        "gid": "4",
        "name": "VSCodeSetup-x64-1.93.0.exe",
        "status": "complete",
        "progress": 1.0,
        "completed": 100453580,
        "total": 100453580,
        "speed": 0,
        "speedLimit": 0,
        "path": "C:/Users/User/Downloads/VSCodeSetup-x64-1.93.0.exe",
        "error": "",
    },
    {
        "gid": "5",
        "name": "cuda_12.6.0_560.76_windows.exe",
        "status": "paused",
        "progress": 0.38,
        "completed": 1264000000,
        "total": 3326000000,
        "speed": 0,
        "speedLimit": 20971520,  # 20 MB/s
        "path": "C:/Users/User/Downloads/cuda_12.6.0_560.76_windows.exe",
        "error": "",
    },
]

SAMPLE_GLOBAL = {
    "downloadSpeed": 60502784,  # 57.7 MB/s
    "numActive": 2,
}

SAMPLE_DISK = {
    "available": True,
    "path": "C:\\",
    "free": 264192000000,
    "total": 512000000000,
    "reserve": 2048 * 1024 * 1024,
    "guardTripped": False,
    "shortfall": 0,
}

SAMPLE_PENDING = [
    {
        "id": "pending-1",
        "name": "Python-3.12.5-amd64.exe",
        "url": "https://www.python.org/ftp/python/3.12.5/python-3.12.5-amd64.exe",
        "size": 26500000,
    }
]


class MockBackend(QObject):
    downloadsChanged = Signal()
    pendingChanged = Signal()
    globalChanged = Signal()
    diskChanged = Signal()
    newPendingArrived = Signal()
    settingsChanged = Signal()
    statusChanged = Signal(str)
    focusRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._downloads = SAMPLE_DOWNLOADS
        self._pending = []
        self._global = SAMPLE_GLOBAL
        self._disk = SAMPLE_DISK
        self._settings = SAMPLE_SETTINGS
        self._status = ""

    @Property("QVariantList", notify=downloadsChanged)
    def downloads(self):
        return self._downloads

    @Property("QVariantList", notify=pendingChanged)
    def pending(self):
        return self._pending

    def set_pending(self, items):
        self._pending = items
        self.pendingChanged.emit()

    @Property("QVariantMap", notify=globalChanged)
    def globalStats(self):
        return self._global

    @Property("QVariantMap", notify=diskChanged)
    def disk(self):
        return self._disk

    @Property("QVariantMap", notify=settingsChanged)
    def settings(self):
        return self._settings

    @Property(str, notify=statusChanged)
    def status(self):
        return self._status

    @Slot(str, int)
    def addUrl(self, url: str, connections: int = 8) -> None:
        pass

    @Slot(str)
    def pauseDownload(self, gid: str) -> None:
        pass

    @Slot(str)
    def resumeDownload(self, gid: str) -> None:
        pass

    @Slot(str)
    def cancelDownload(self, gid: str) -> None:
        pass

    @Slot()
    def clearFinished(self) -> None:
        pass

    @Slot(str)
    def openDownload(self, gid: str) -> None:
        pass

    @Slot(str)
    def revealDownload(self, gid: str) -> None:
        pass

    @Slot(str, int)
    def setSpeedLimit(self, gid: str, limit: int) -> None:
        pass

    @Slot(str, int)
    def confirmPending(self, id: str, connections: int = 8) -> None:
        pass

    @Slot(str)
    def cancelPending(self, id: str) -> None:
        pass

    @Slot(object)
    def saveSettings(self, new_settings: object) -> None:
        pass

    @Slot()
    def flashTaskbar(self) -> None:
        pass


def grab_qml(window, width: int = 1280, height: int = 800) -> QImage:
    """Grab the complete QQuickWindow (including popups, overlays, and drawers)."""
    img = window.grabWindow()
    if img.width() != width or img.height() != height:
        return img.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return img


def capture_popup() -> QImage:
    """Render the browser extension popup on a clean browser canvas (1280x800)."""
    from PySide6.QtWebEngineWidgets import QWebEngineView

    view = QWebEngineView()
    popup_html = (ROOT / "extension" / "popup.html").read_text("utf-8")
    # Replace i18n placeholders and ensure no scrollbars
    popup_html = popup_html.replace('data-i18n="appName">STZ Downloader', '>STZ Downloader')
    popup_html = popup_html.replace('data-i18n="interceptDownloads">Intercept downloads', '>Intercept downloads')
    popup_html = popup_html.replace('data-i18n="statusLabel">Status', '>Status')
    popup_html = popup_html.replace('<input type="checkbox" id="enabled" />', '<input type="checkbox" id="enabled" checked />')
    popup_html = popup_html.replace('id="status">…</span>', 'id="status" class="ok">connected</span>')
    popup_html = popup_html.replace('body {', 'body { overflow: hidden; box-sizing: border-box;')

    view.setHtml(popup_html, QUrl.fromLocalFile(str(ROOT / "extension" / "popup.html")))
    view.resize(280, 120)
    view.show()

    loop_start = time.monotonic()
    while time.monotonic() - loop_start < 0.6:
        QApplication.processEvents()

    popup_img = view.grab().toImage()

    # Create 1280x800 canvas with simulated browser environment
    canvas = QImage(1280, 800, QImage.Format_ARGB32)
    canvas.fill(QColor("#0f1115"))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing)

    # Simulated browser toolbar
    painter.fillRect(0, 0, 1280, 72, QColor("#181b22"))
    painter.fillRect(0, 71, 1280, 1, QColor("#2a2f3a"))

    # Address bar
    painter.setBrush(QColor("#121419"))
    painter.setPen(QColor("#2a2f3a"))
    painter.drawRoundedRect(120, 16, 820, 40, 8, 8)

    painter.setPen(QColor("#8b919e"))
    font = painter.font()
    font.setPointSize(11)
    painter.setFont(font)
    painter.drawText(140, 41, "https://github.com/starzynhobr/stz-downloader")

    # Extension icon in toolbar
    icon_path = ROOT / "extension" / "icons" / "icon48.png"
    if icon_path.exists():
        icon_img = QImage(str(icon_path)).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter.drawImage(980, 20, icon_img)

    # Draw popup beneath toolbar with drop shadow / border
    popup_x = 880
    popup_y = 80
    painter.setBrush(QColor("#181b22"))
    painter.setPen(QColor("#3a4050"))
    painter.drawRoundedRect(popup_x - 4, popup_y - 4, popup_img.width() + 8, popup_img.height() + 8, 10, 10)
    painter.drawImage(popup_x, popup_y, popup_img)

    # Feature callouts
    painter.setPen(QColor("#e7e9ee"))
    font.setPointSize(16)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(80, 220, "STZ Downloader — Browser Extension Integration")

    painter.setPen(QColor("#8b919e"))
    font.setPointSize(12)
    font.setBold(False)
    painter.setFont(font)
    painter.drawText(80, 260, "• Manifest V3 integration for Chrome, Firefox, Edge, and Floorp")
    painter.drawText(80, 295, "• Automatic download interception and one-click toggle")
    painter.drawText(80, 330, "• Native Messaging loopback IPC with zero network exposure")
    painter.drawText(80, 365, "• Forwards session cookies for authenticated downloads")

    painter.end()
    return canvas


def generate_promo_tile() -> QImage:
    """Generate 440x280 Small Promo Tile required for Chrome Web Store cards."""
    canvas = QImage(440, 280, QImage.Format_ARGB32)
    canvas.fill(QColor("#0d0f14"))
    p = QPainter(canvas)
    p.setRenderHint(QPainter.Antialiasing)

    # Card background
    p.setBrush(QColor("#181b22"))
    p.setPen(QColor("#2a2f3a"))
    p.drawRoundedRect(12, 12, 416, 256, 16, 16)

    # Icon
    icon_path = ROOT / "extension" / "icons" / "icon128.png"
    if icon_path.exists():
        icon_img = QImage(str(icon_path)).scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        p.drawImage(40, 95, icon_img)

    # Title & Subtitle
    p.setPen(QColor("#e7e9ee"))
    font = p.font()
    font.setPointSize(18)
    font.setBold(True)
    p.setFont(font)
    p.drawText(140, 130, "STZ Downloader")

    p.setPen(QColor("#4c8dff"))
    font.setPointSize(9)
    font.setBold(True)
    p.setFont(font)
    p.drawText(140, 155, "HIGH-SPEED DOWNLOAD MANAGER")

    p.setPen(QColor("#8b919e"))
    font.setPointSize(10)
    font.setBold(False)
    p.setFont(font)
    p.drawText(140, 182, "aria2 Engine & Browser Extension")

    p.end()
    return canvas


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("STZ Downloader")

    icon_path = ROOT / "assets" / "stz-downloader.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    from stz_downloader.ui.translator import Translator

    translator = Translator()
    translator.language = "en"  # Standard language for store review screenshots

    backend = MockBackend()

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("i18n", translator)

    qml_file = QML_DIR / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_file)))

    if not engine.rootObjects():
        print("ERROR: QML failed to load", file=sys.stderr)
        return 1

    window = engine.rootObjects()[0]
    window.setWidth(1280)
    window.setHeight(800)
    window.show()

    def process(duration: float = 0.5):
        start = time.monotonic()
        while time.monotonic() - start < duration:
            QApplication.processEvents()

    process(1.0)

    # 1. Capture Main Dashboard
    img_main = grab_qml(window, 1280, 800)
    main_path = OUT_DIR / "screenshot_1_main.png"
    img_main.save(str(main_path))
    print(f"Captured: {main_path} ({img_main.width()}x{img_main.height()})")

    # 2. Capture Settings Drawer
    drawer = window.findChild(QObject, "settingsDrawer")
    if drawer:
        drawer.open()
        process(0.8)
        img_settings = grab_qml(window, 1280, 800)
        settings_path = OUT_DIR / "screenshot_2_settings.png"
        img_settings.save(str(settings_path))
        print(f"Captured: {settings_path} ({img_settings.width()}x{img_settings.height()})")
        drawer.close()
        process(0.5)

    # 3. Capture Download Confirmation Dialog
    backend.set_pending(SAMPLE_PENDING)
    process(0.8)
    img_confirm = grab_qml(window, 1280, 800)
    confirm_path = OUT_DIR / "screenshot_3_confirm.png"
    img_confirm.save(str(confirm_path))
    print(f"Captured: {confirm_path} ({img_confirm.width()}x{img_confirm.height()})")

    # 4. Capture Extension Popup
    img_popup = capture_popup()
    popup_path = OUT_DIR / "screenshot_4_popup.png"
    img_popup.save(str(popup_path))
    print(f"Captured: {popup_path} ({img_popup.width()}x{img_popup.height()})")

    # 5. Generate Small Promo Tile (440x280)
    img_promo = generate_promo_tile()
    promo_path = OUT_DIR / "small_promo_tile.png"
    img_promo.save(str(promo_path))
    print(f"Captured: {promo_path} ({img_promo.width()}x{img_promo.height()})")

    # Copy to artifacts directory so user can inspect directly in chat/artifacts
    for p in [main_path, settings_path, confirm_path, popup_path, promo_path]:
        shutil.copyfile(p, ARTIFACT_DIR / p.name)

    print("\nAll store assets successfully generated!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
