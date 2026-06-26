"""Configuration loading.

Defaults live in ``pyproject.toml`` under ``[tool.stz-downloader.*]``.
A user override may live at ``%APPDATA%/stz-downloader/config.toml`` with the
same table layout but without the ``tool.stz-downloader`` prefix, e.g.::

    [aria2]
    rpc_port = 6900

    [downloads]
    directory = "D:/Downloads"
"""
from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

APP_NAME = "stz-downloader"


def _project_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # src/stz_downloader/config.py -> project root is two parents up from package
    return Path(__file__).resolve().parents[2]


def user_config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / APP_NAME


def _default_downloads_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Downloads"
    return Path.home() / "Downloads"


@dataclass
class Aria2Config:
    binary: str = "bundled"
    rpc_host: str = "127.0.0.1"
    rpc_port: int = 6800
    rpc_secret: str = "stz-local-secret"
    extra_args: list[str] = field(default_factory=list)

    @property
    def rpc_url(self) -> str:
        return f"http://{self.rpc_host}:{self.rpc_port}/jsonrpc"

    def resolve_binary(self) -> str:
        if self.binary != "bundled":
            return self.binary
        exe = "aria2c.exe" if sys.platform == "win32" else "aria2c"
        bundled = _project_root() / "third_party" / "aria2" / exe
        return str(bundled) if bundled.exists() else exe  # fall back to PATH


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8765


@dataclass
class DownloadsConfig:
    directory: str = ""

    def resolve_directory(self) -> Path:
        return Path(self.directory) if self.directory else _default_downloads_dir()


@dataclass
class Config:
    aria2: Aria2Config = field(default_factory=Aria2Config)
    server: ServerConfig = field(default_factory=ServerConfig)
    downloads: DownloadsConfig = field(default_factory=DownloadsConfig)


def _read_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def load_config() -> Config:
    # 1. Defaults from pyproject.toml [tool.stz-downloader.*]
    pyproject = _read_toml(_project_root() / "pyproject.toml")
    base = pyproject.get("tool", {}).get("stz-downloader", {})

    # 2. User overrides
    user = _read_toml(user_config_dir() / "config.toml")

    def merged(section: str) -> dict:
        return {**base.get(section, {}), **user.get(section, {})}

    return Config(
        aria2=Aria2Config(**merged("aria2")),
        server=ServerConfig(**merged("server")),
        downloads=DownloadsConfig(**merged("downloads")),
    )
