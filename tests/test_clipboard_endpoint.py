"""Clipboard offers: filtering, and how far de-duplication should go.

Regression: the server remembered the last URL it had offered, forever. So
copying the same link a second time -- a deliberate, repeatable action -- was
silently ignored. De-duplication should only protect against a prompt that is
still on screen.
"""
import pytest
from fastapi.testclient import TestClient

from stz_downloader.aria2.manager import Aria2Manager
from stz_downloader.config import Config
from stz_downloader.server.app import create_app

URL = "https://releases.ubuntu.com/26.04/ubuntu-26.04-desktop-amd64.iso"


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Keep settings.json inside the test's own directory.
    monkeypatch.setenv("APPDATA", str(tmp_path))
    # The endpoints under test never touch aria2; don't spawn it.
    monkeypatch.setattr(Aria2Manager, "start", lambda self: None)
    monkeypatch.setattr(Aria2Manager, "stop", lambda self: None)

    with TestClient(create_app(Config())) as c:
        c.put("/api/settings", json={"clipboard_enabled": True})
        yield c


def _offer(client, url=URL):
    return client.post("/api/clipboard", json={"url": url}).json()


def _pending(client):
    return client.get("/api/pending").json()["pending"]


def test_matching_url_is_offered(client):
    assert _offer(client)["accepted"] is True
    items = _pending(client)
    assert len(items) == 1
    assert items[0]["name"] == "ubuntu-26.04-desktop-amd64.iso"
    assert items[0]["source"] == "clipboard"


def test_same_url_while_prompt_is_open_does_not_duplicate(client):
    _offer(client)
    second = _offer(client)
    assert second["accepted"] is False
    assert second["reason"] == "already-pending"
    assert len(_pending(client)) == 1


def test_same_url_is_offered_again_after_the_prompt_is_dismissed(client):
    _offer(client)
    pid = _pending(client)[0]["id"]
    client.post(f"/api/pending/{pid}/cancel")
    assert _pending(client) == []

    assert _offer(client)["accepted"] is True, "re-copying the same link must re-offer"
    assert len(_pending(client)) == 1


def test_extension_outside_the_filter_is_ignored(client):
    r = _offer(client, "https://example.com/page.html")
    assert r["accepted"] is False and r["reason"] == "filtered"
    assert _pending(client) == []


def test_intercept_all_bypasses_the_filter(client):
    client.put("/api/settings", json={"intercept_all": True})
    assert _offer(client, "https://example.com/page.html")["accepted"] is True


def test_non_urls_are_rejected(client):
    for text in ["just some copied text", "ftp://example.com/x.iso", ""]:
        r = _offer(client, text)
        assert r["accepted"] is False and r["reason"] == "not-a-url", text


def test_nothing_is_offered_while_the_setting_is_off(client):
    client.put("/api/settings", json={"clipboard_enabled": False})
    r = _offer(client)
    assert r["accepted"] is False and r["reason"] == "disabled"
    assert _pending(client) == []
