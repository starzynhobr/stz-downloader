"""Browser Native Messaging host for STZ Downloader.

The browser starts this small console process by its registered application
name.  It forwards JSON requests to the authenticated, dynamically allocated
loopback bridge and starts the desktop application on demand for downloads.
"""
from __future__ import annotations

import json
import logging
import os
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import BinaryIO

import httpx

from .runtime import RuntimeInfo, load_runtime, runtime_dir

NATIVE_HOST_NAME = "com.stzlabs.downloader"
CHROME_EXTENSION_ID = "jhahaknbmgkbnhfnknclelilaoobmpcm"
FIREFOX_EXTENSION_ID = "stz-downloader@stzlabs.com"
MAX_MESSAGE_BYTES = 4 * 1024 * 1024


def _read_message(stream: BinaryIO) -> dict | None:
    raw_length = stream.read(4)
    if not raw_length:
        return None
    if len(raw_length) != 4:
        raise ValueError("incomplete native message header")
    length = struct.unpack("=I", raw_length)[0]
    if length > MAX_MESSAGE_BYTES:
        raise ValueError("native message is too large")
    raw = stream.read(length)
    if len(raw) != length:
        raise ValueError("incomplete native message body")
    message = json.loads(raw.decode("utf-8"))
    if not isinstance(message, dict):
        raise ValueError("native message must be a JSON object")
    return message


def _write_message(stream: BinaryIO, message: dict) -> None:
    raw = json.dumps(message, separators=(",", ":")).encode("utf-8")
    stream.write(struct.pack("=I", len(raw)))
    stream.write(raw)
    stream.flush()


def _application_command() -> list[str]:
    if getattr(sys, "frozen", False):
        app = Path(sys.executable).resolve().with_name("stz-downloader.exe")
        if not app.exists():
            raise FileNotFoundError(f"desktop application not found: {app}")
        return [str(app)]
    return [sys.executable, "-m", "stz_downloader"]


def _launch_application() -> None:
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    subprocess.Popen(_application_command(), **kwargs)


class NativeBridgeClient:
    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout

    def _call(
        self,
        info: RuntimeInfo,
        method: str,
        path: str,
        payload: dict | None = None,
    ) -> dict:
        response = httpx.request(
            method,
            f"{info.base_url}{path}",
            headers={"Authorization": info.authorization},
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("bridge returned an invalid response")
        return data

    def _healthy_runtime(self) -> RuntimeInfo | None:
        info = load_runtime()
        if not info:
            return None
        try:
            health = self._call(info, "GET", "/api/health")
        except Exception:  # noqa: BLE001 -- stale record or app still starting
            return None
        if health.get("ok") and health.get("app") == "stz-downloader":
            return info
        return None

    def runtime(self, launch: bool = False) -> RuntimeInfo | None:
        info = self._healthy_runtime()
        if info or not launch:
            return info

        _launch_application()
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            time.sleep(0.1)
            info = self._healthy_runtime()
            if info:
                return info
        raise TimeoutError("STZ Downloader did not become ready")

    def handle(self, message: dict) -> dict:
        kind = message.get("type")
        if kind == "status":
            info = self.runtime(launch=False)
            if not info:
                return {"ok": False, "error": "offline"}
            return {"ok": True, "result": self._call(info, "GET", "/api/health")}

        if kind == "settings":
            info = self.runtime(launch=False)
            if not info:
                return {"ok": False, "error": "offline"}
            return {"ok": True, "result": self._call(info, "GET", "/api/settings")}

        if kind == "download":
            payload = message.get("payload")
            if not isinstance(payload, dict) or not isinstance(payload.get("url"), str):
                return {"ok": False, "error": "invalid download payload"}
            info = self.runtime(launch=True)
            assert info is not None
            result = self._call(info, "POST", "/api/download", payload)
            return {"ok": True, "result": result}

        return {"ok": False, "error": "unsupported message type"}


def _native_manifest_dir() -> Path:
    return runtime_dir() / "native-messaging"


def register_native_host(host_executable: Path | None = None) -> bool:
    """Register the frozen helper for Chrome-family browsers and Firefox."""
    if sys.platform != "win32":
        return False
    import winreg

    host = (host_executable or Path(sys.executable)).resolve()
    if not host.exists():
        return False
    target = _native_manifest_dir()
    target.mkdir(parents=True, exist_ok=True)

    chrome_manifest = target / f"{NATIVE_HOST_NAME}.chromium.json"
    firefox_manifest = target / f"{NATIVE_HOST_NAME}.firefox.json"
    common = {
        "name": NATIVE_HOST_NAME,
        "description": "STZ Downloader browser integration",
        "path": str(host),
        "type": "stdio",
    }
    chrome_manifest.write_text(
        json.dumps(
            {**common, "allowed_origins": [f"chrome-extension://{CHROME_EXTENSION_ID}/"]},
            indent=2,
        ),
        encoding="utf-8",
    )
    firefox_manifest.write_text(
        json.dumps({**common, "allowed_extensions": [FIREFOX_EXTENSION_ID]}, indent=2),
        encoding="utf-8",
    )

    chromium_roots = [
        r"Software\Google\Chrome\NativeMessagingHosts",
        r"Software\Microsoft\Edge\NativeMessagingHosts",
        r"Software\Chromium\NativeMessagingHosts",
        r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts",
    ]
    for root in chromium_roots:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{root}\\{NATIVE_HOST_NAME}") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(chrome_manifest))
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER,
        rf"Software\Mozilla\NativeMessagingHosts\{NATIVE_HOST_NAME}",
    ) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(firefox_manifest))
    return True


def unregister_native_host() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    roots = [
        r"Software\Google\Chrome\NativeMessagingHosts",
        r"Software\Microsoft\Edge\NativeMessagingHosts",
        r"Software\Chromium\NativeMessagingHosts",
        r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts",
        r"Software\Mozilla\NativeMessagingHosts",
    ]
    for root in roots:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{root}\\{NATIVE_HOST_NAME}")
        except FileNotFoundError:
            pass
    for manifest in _native_manifest_dir().glob(f"{NATIVE_HOST_NAME}.*.json"):
        try:
            manifest.unlink()
        except FileNotFoundError:
            pass
    return True


def run_native_host(stdin: BinaryIO | None = None, stdout: BinaryIO | None = None) -> int:
    source = stdin or sys.stdin.buffer
    sink = stdout or sys.stdout.buffer
    if sys.platform == "win32" and stdin is None and stdout is None:
        import msvcrt

        msvcrt.setmode(source.fileno(), os.O_BINARY)
        msvcrt.setmode(sink.fileno(), os.O_BINARY)
    client = NativeBridgeClient()
    while True:
        try:
            message = _read_message(source)
            if message is None:
                return 0
            response = client.handle(message)
        except Exception as exc:  # noqa: BLE001 -- errors must cross the protocol
            logging.exception("Native Messaging request failed")
            response = {"ok": False, "error": str(exc)}
        _write_message(sink, response)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--register" in args:
        return 0 if register_native_host() else 1
    if "--unregister" in args:
        return 0 if unregister_native_host() else 1
    return run_native_host()


if __name__ == "__main__":
    raise SystemExit(main())
