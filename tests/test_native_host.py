import pytest
import base64
import hashlib
import io
import json
from pathlib import Path

from stz_downloader.native_host import (
    CHROME_EXTENSION_ID,
    NativeBridgeClient,
    _read_message,
    _write_message,
)
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
