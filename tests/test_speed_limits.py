from fastapi.testclient import TestClient

from stz_downloader.aria2.client import Aria2Client
from stz_downloader.aria2.manager import Aria2Manager
from stz_downloader.config import Config
from stz_downloader.server.app import create_app


def _client(tmp_path, monkeypatch, calls):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(Aria2Manager, "start", lambda self: None)
    monkeypatch.setattr(Aria2Manager, "stop", lambda self: None)

    async def change_global_option(self, options):
        calls.append(("global", options))
        return "OK"

    async def change_option(self, gid, options):
        calls.append(("item", gid, options))
        return "OK"

    monkeypatch.setattr(Aria2Client, "change_global_option", change_global_option)
    monkeypatch.setattr(Aria2Client, "change_option", change_option)
    return TestClient(create_app(Config()))


def test_global_limit_is_applied_live_and_persisted(tmp_path, monkeypatch):
    calls = []
    with _client(tmp_path, monkeypatch, calls) as client:
        response = client.put(
            "/api/settings", json={"download_limit_bps": 25 * 1024 * 1024}
        )

    assert response.status_code == 200
    assert response.json()["download_limit_bps"] == 25 * 1024 * 1024
    assert calls[-1] == (
        "global",
        {"max-overall-download-limit": str(25 * 1024 * 1024)},
    )


def test_per_download_limit_is_applied_live(tmp_path, monkeypatch):
    calls = []
    with _client(tmp_path, monkeypatch, calls) as client:
        response = client.post(
            "/api/downloads/deadbeef/speed-limit",
            json={"bytes_per_second": 5 * 1024 * 1024},
        )

    assert response.status_code == 200
    assert response.json() == {
        "gid": "deadbeef",
        "bytes_per_second": 5 * 1024 * 1024,
    }
    assert calls[-1] == (
        "item",
        "deadbeef",
        {"max-download-limit": str(5 * 1024 * 1024)},
    )


def test_negative_limits_are_rejected(tmp_path, monkeypatch):
    calls = []
    with _client(tmp_path, monkeypatch, calls) as client:
        global_response = client.put(
            "/api/settings", json={"download_limit_bps": -1}
        )
        item_response = client.post(
            "/api/downloads/deadbeef/speed-limit",
            json={"bytes_per_second": -1},
        )

    assert global_response.status_code == 422
    assert item_response.status_code == 422


def test_global_limit_remains_saved_while_aria2_is_starting(tmp_path, monkeypatch):
    calls = []
    with _client(tmp_path, monkeypatch, calls) as client:
        async def unavailable(self, options):
            raise ConnectionError("RPC socket is not ready")

        monkeypatch.setattr(Aria2Client, "change_global_option", unavailable)
        response = client.put(
            "/api/settings", json={"download_limit_bps": 10 * 1024 * 1024}
        )
        persisted = client.get("/api/settings")

    assert response.status_code == 200
    assert persisted.json()["download_limit_bps"] == 10 * 1024 * 1024


def test_limit_on_a_finished_download_is_a_conflict_not_a_crash(tmp_path, monkeypatch):
    from stz_downloader.aria2.client import Aria2Error

    async def change_option(self, gid, options):
        raise Aria2Error("GID deadbeef is not found")

    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(Aria2Manager, "start", lambda self: None)
    monkeypatch.setattr(Aria2Manager, "stop", lambda self: None)
    monkeypatch.setattr(Aria2Client, "change_option", change_option)
    with TestClient(create_app(Config())) as client:
        response = client.post(
            "/api/downloads/deadbeef/speed-limit", json={"bytes_per_second": 1024}
        )

    assert response.status_code == 409
