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


def test_websocket_accepts_the_token_as_a_query_parameter(protected_client):
    with pytest.raises(WebSocketDisconnect):
        with protected_client.websocket_connect("/ws?token=wrong"):
            pass

    with protected_client.websocket_connect("/ws?token=test-token"):
        pass


def test_desktop_ui_origin_passes_cors_preflight_without_a_token(protected_client):
    response = protected_client.options(
        "/api/downloads",
        headers={
            "Origin": "http://tauri.localhost",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://tauri.localhost"


def test_other_origins_get_no_cors_grant(protected_client):
    response = protected_client.get(
        "/api/health",
        headers={"Origin": "https://evil.example", "Authorization": "Bearer test-token"},
    )
    assert "access-control-allow-origin" not in response.headers
