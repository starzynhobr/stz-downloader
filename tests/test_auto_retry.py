import time

from fastapi.testclient import TestClient

from stz_downloader.aria2.client import Aria2Client
from stz_downloader.aria2.manager import Aria2Manager
from stz_downloader.config import Config
from stz_downloader.server import app as app_module
from stz_downloader.server.app import create_app

URL = "https://example.com/big.iso"


def _run(tmp_path, monkeypatch, error_code):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(Aria2Manager, "start", lambda self: None)
    monkeypatch.setattr(Aria2Manager, "stop", lambda self: None)
    monkeypatch.setattr(app_module, "RETRY_DELAY_SECONDS", 0.0)
    path = str(tmp_path / "big.iso")
    stopped = [{
        "gid": "old",
        "status": "error",
        "errorCode": error_code,
        "errorMessage": "SSL/TLS handshake failure",
        "totalLength": "100",
        "completedLength": "40",
        "files": [{"path": path, "uris": [{"uri": URL}, {"uri": URL}]}],
    }]
    added = []
    removed = []

    async def empty(self, *args, **kwargs):
        return []

    async def tell_stopped(self, offset=0, num=100):
        return list(stopped)

    async def tell_status(self, gid, keys=None):
        return stopped[0] if stopped else {}

    async def get_option(self, gid):
        return {"dir": str(tmp_path), "split": "8", "header": ["Cookie: a=b"], "out": "ignored"}

    async def add_uri_with_options(self, uris, options):
        added.append((uris, options))
        stopped.clear()
        return "new"

    async def remove_download_result(self, gid):
        removed.append(gid)
        return "OK"

    async def global_stat(self):
        return {}

    async def change_global_option(self, options):
        return "OK"

    monkeypatch.setattr(Aria2Client, "tell_active", empty)
    monkeypatch.setattr(Aria2Client, "tell_waiting", empty)
    monkeypatch.setattr(Aria2Client, "tell_stopped", tell_stopped)
    monkeypatch.setattr(Aria2Client, "tell_status", tell_status)
    monkeypatch.setattr(Aria2Client, "get_option", get_option)
    monkeypatch.setattr(Aria2Client, "add_uri_with_options", add_uri_with_options)
    monkeypatch.setattr(Aria2Client, "remove_download_result", remove_download_result)
    monkeypatch.setattr(Aria2Client, "get_global_stat", global_stat)
    monkeypatch.setattr(Aria2Client, "change_global_option", change_global_option)

    with TestClient(create_app(Config())):
        time.sleep(2.6)  # the broadcast loop ticks once per second
    return added, removed


def test_transient_error_is_requeued_into_the_same_file(tmp_path, monkeypatch):
    added, removed = _run(tmp_path, monkeypatch, "1")

    assert len(added) == 1
    uris, options = added[0]
    assert uris == [URL]
    assert options["out"] == "big.iso"
    assert options["continue"] == "true"
    assert options["auto-file-renaming"] == "false"
    assert options["header"] == ["Cookie: a=b"]
    assert options["split"] == "8"
    assert removed == ["old"]


def test_permanent_error_is_left_alone(tmp_path, monkeypatch):
    added, removed = _run(tmp_path, monkeypatch, "3")  # resource not found

    assert added == []
    assert removed == []


def _restart_client(tmp_path, monkeypatch, status):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(Aria2Manager, "start", lambda self: None)
    monkeypatch.setattr(Aria2Manager, "stop", lambda self: None)
    added = []

    async def tell_status(self, gid, keys=None):
        return {
            "status": status,
            "files": [{"path": str(tmp_path / "big.iso"), "uris": [{"uri": URL}]}],
        }

    async def get_option(self, gid):
        return {"dir": str(tmp_path), "header": ["Cookie: a=b"]}

    async def add_uri_with_options(self, uris, options):
        added.append((uris, options))
        return "new"

    async def remove_download_result(self, gid):
        return "OK"

    monkeypatch.setattr(Aria2Client, "tell_status", tell_status)
    monkeypatch.setattr(Aria2Client, "get_option", get_option)
    monkeypatch.setattr(Aria2Client, "add_uri_with_options", add_uri_with_options)
    monkeypatch.setattr(Aria2Client, "remove_download_result", remove_download_result)
    return TestClient(create_app(Config())), added


def test_cancelled_download_restarts_into_the_same_file(tmp_path, monkeypatch):
    client, added = _restart_client(tmp_path, monkeypatch, "removed")
    with client:
        response = client.post("/api/downloads/old/restart")

    assert response.json() == {"gid": "new", "started": True}
    uris, options = added[0]
    assert uris == [URL]
    assert options["out"] == "big.iso"
    assert options["continue"] == "true"
    assert options["header"] == ["Cookie: a=b"]


def test_running_download_cannot_be_restarted(tmp_path, monkeypatch):
    client, added = _restart_client(tmp_path, monkeypatch, "active")
    with client:
        response = client.post("/api/downloads/old/restart")

    assert response.status_code == 409
    assert added == []
