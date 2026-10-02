import sys
from pathlib import Path

from fastapi.testclient import TestClient

from stz_downloader import autostart
from stz_downloader.aria2.manager import Aria2Manager
from stz_downloader.config import Config
from stz_downloader.server.app import create_app


def test_frozen_engine_registers_the_desktop_shell(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "stz-engine.exe"))

    assert autostart.launch_command() == f'"{tmp_path / "stz-downloader.exe"}" --minimized'


def test_other_frozen_builds_register_themselves(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "stz-downloader.exe"))

    assert autostart.launch_command() == f'"{Path(tmp_path / "stz-downloader.exe")}" --minimized'


def test_settings_store_what_windows_accepted(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(Aria2Manager, "start", lambda self: None)
    monkeypatch.setattr(Aria2Manager, "stop", lambda self: None)
    applied = []
    monkeypatch.setattr(autostart, "supported", lambda: True)
    monkeypatch.setattr(autostart, "apply", lambda enabled: applied.append(enabled) or False)

    with TestClient(create_app(Config())) as client:
        response = client.put("/api/settings", json={"start_with_windows": True})

    assert applied == [True]
    assert response.json()["start_with_windows"] is False
