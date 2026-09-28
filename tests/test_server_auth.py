import pytest
from starlette.websockets import WebSocketDisconnect
from fastapi.testclient import TestClient

from stz_downloader.aria2.manager import Aria2Manager
from stz_downloader.config import Config
from stz_downloader.server.app import create_app


@pytest.fixture
def protected_client(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(Aria2Manager, "start", lambda self: None)
    monkeypatch.setattr(Aria2Manager, "stop", lambda self: None)
    monkeypatch.setattr(Aria2Manager, "is_running", lambda self: False)
    with TestClient(create_app(Config(), auth_token="test-token")) as client:
        yield client


def test_api_rejects_clients_without_runtime_token(protected_client):
    response = protected_client.get("/api/health")
    assert response.status_code == 401


def test_authenticated_health_identifies_the_bridge(protected_client):
    response = protected_client.get(
        "/api/health", headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "app": "stz-downloader",
        "protocol": 1,
        "aria2": False,
    }


def test_websocket_requires_the_same_runtime_token(protected_client):
    with pytest.raises(WebSocketDisconnect):
        with protected_client.websocket_connect("/ws"):
            pass

    with protected_client.websocket_connect(
        "/ws", headers={"Authorization": "Bearer test-token"}
    ):
        pass
