"""Only successfully accepted automatic browser downloads request attention."""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from stz_downloader.aria2.client import Aria2Client
from stz_downloader.config import Config
from stz_downloader.server.app import create_app


@pytest.mark.parametrize(
    "from_browser,auto_start,fail,expected",
    [(True, True, False, 1), (False, True, False, 0),
     (True, False, False, 0), (True, True, True, 0)],
)
def test_browser_attention_counter(tmp_path, monkeypatch, from_browser, auto_start, fail, expected):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    for method in ("tell_active", "tell_waiting", "tell_stopped"):
        monkeypatch.setattr(Aria2Client, method, AsyncMock(return_value=[]))
    monkeypatch.setattr(Aria2Client, "get_global_stat", AsyncMock(return_value={}))
    start = AsyncMock(return_value="abc", side_effect=RuntimeError("unavailable") if fail else None)
    monkeypatch.setattr(Aria2Client, "add_uri", start)
    # No lifespan: don't launch the real engine or background tasks.
    client = TestClient(create_app(Config()), raise_server_exceptions=False)
    client.put("/api/settings", json={"auto_start": auto_start})
    assert client.get("/api/downloads").json()["browserDownloads"] == 0
    response = client.post("/api/download", json={
        "url": "https://example.com/file.zip", "from_browser": from_browser,
    })
    assert response.status_code == (500 if fail else 200)
    for _ in range(2):
        assert client.get("/api/downloads").json()["browserDownloads"] == expected
    if from_browser and not auto_start:
        start.assert_not_awaited()
