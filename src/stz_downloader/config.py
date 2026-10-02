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

# Runtime-critical aria2 defaults belong in executable code, not only in
# pyproject.toml. Frozen PyInstaller builds do not ship the repository's
# pyproject, and silently falling back to aria2's defaults means `prealloc`
# zero-fills very large files before the first byte can be downloaded.
DEFAULT_ARIA2_EXTRA_ARGS = (
    "--max-connection-per-server=16",
    "--split=16",
    "--min-split-size=1M",
    "--continue=true",
    "--file-allocation=falloc",
    "--auto-file-renaming=true",
    # System resolver: follows VPN / network changes instead of fixed servers.
    "--async-dns=false",
    # Keep retrying through network drops (VPN switch, Wi-Fi hiccup); the
    # user can still cancel. Permanent errors like 404 are not retried.
    "--max-tries=0",
    "--retry-wait=5",
    "--connect-timeout=15",
    "--timeout=30",
    "--lowest-speed-limit=0",
)


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
    extra_args: list[str] = field(default_factory=lambda: list(DEFAULT_ARIA2_EXTRA_ARGS))

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
