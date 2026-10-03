import pytest
import base64
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

from stz_downloader.native_host import (
    CHROME_EXTENSION_ID,
    NativeBridgeClient,
    _read_message,
    _write_message,
)
from stz_downloader import native_host
from stz_downloader.runtime import RuntimeInfo


def test_native_message_framing_round_trip():
    stream = io.BytesIO()
    _write_message(stream, {"type": "status", "value": "ç"})
    stream.seek(0)
    assert _read_message(stream) == {"type": "status", "value": "ç"}


def test_chrome_manifest_key_matches_registered_extension_id():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "extension" / "manifest.chrome.json").read_text("utf-8"))
    if "key" not in manifest:
        pytest.skip("key removed for first Chrome Web Store upload")
    public_key = base64.b64decode(manifest["key"])
    alphabet = "abcdefghijklmnop"
    digest = hashlib.sha256(public_key).digest()[:16]
    derived = "".join(alphabet[nibble] for byte in digest for nibble in (byte >> 4, byte & 15))
    assert derived == CHROME_EXTENSION_ID


def test_native_download_is_forwarded_to_authenticated_runtime(monkeypatch):
    client = NativeBridgeClient()
    info = RuntimeInfo(
        pid=1,
        host="127.0.0.1",
        port=50000,
        token="secret",
        instance_id="instance",
    )
    calls = []
    monkeypatch.setattr(client, "runtime", lambda launch=False: info)
    monkeypatch.setattr(
        client,
        "_call",
        lambda found, method, path, payload=None: calls.append(
            (found, method, path, payload)
        )
        or {"gid": "abc"},
    )

    response = client.handle(
        {"type": "download", "payload": {"url": "https://example.com/file.zip"}}
    )

    assert response == {"ok": True, "result": {"gid": "abc"}}
    assert calls == [
        (
            info,
            "POST",
            "/api/download",
            {"url": "https://example.com/file.zip"},
        )
    ]


def test_native_download_rejects_missing_url():
    assert NativeBridgeClient().handle({"type": "download", "payload": {}}) == {
        "ok": False,
        "error": "invalid download payload",
    }


@pytest.mark.skipif(sys.platform != "win32", reason="Windows job objects")
def test_app_is_launched_outside_the_browser_job(monkeypatch):
    calls = []
    monkeypatch.setattr(native_host, "_application_command", lambda: ["app.exe"])
    monkeypatch.setattr(native_host.subprocess, "Popen", lambda cmd, **kw: calls.append(kw))

    native_host._launch_application()

    assert calls[0]["creationflags"] & subprocess.CREATE_BREAKAWAY_FROM_JOB


@pytest.mark.skipif(sys.platform != "win32", reason="Windows job objects")
def test_launch_falls_back_when_the_job_forbids_breakaway(monkeypatch):
    calls = []

    def popen(cmd, **kw):
        calls.append(kw["creationflags"])
        if kw["creationflags"] & subprocess.CREATE_BREAKAWAY_FROM_JOB:
            raise PermissionError("access denied")

    monkeypatch.setattr(native_host, "_application_command", lambda: ["app.exe"])
    monkeypatch.setattr(native_host.subprocess, "Popen", popen)

    native_host._launch_application()

    assert len(calls) == 2
    assert not calls[1] & subprocess.CREATE_BREAKAWAY_FROM_JOB
