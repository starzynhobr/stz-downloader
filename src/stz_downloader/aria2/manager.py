"""Spawn and supervise the ``aria2c`` RPC subprocess."""
from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path

from ..config import Aria2Config
from ..config import user_config_dir


class Aria2Manager:
    def __init__(self, cfg: Aria2Config, download_dir: Path):
        self.cfg = cfg
        self.download_dir = download_dir
        self._proc: subprocess.Popen | None = None

    def start(self) -> None:
        if self._proc and self._proc.poll() is None:
            return
        if self._rpc_port_is_open():
            return
        self.download_dir.mkdir(parents=True, exist_ok=True)
        session_file = user_config_dir() / "session.txt"
        session_file.parent.mkdir(parents=True, exist_ok=True)

        args = [
            self.cfg.resolve_binary(),
            "--enable-rpc",
            "--rpc-listen-all=false",
            f"--rpc-listen-port={self.cfg.rpc_port}",
            f"--rpc-secret={self.cfg.rpc_secret}",
            f"--dir={self.download_dir}",
            f"--save-session={session_file}",
            "--save-session-interval=30",
            *(["--input-file", str(session_file)] if session_file.exists() else []),
            *self.cfg.extra_args,
        ]

        # On Windows, avoid spawning a console window for the child.
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

        self._proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        try:
            self._proc.wait(timeout=0.25)
        except subprocess.TimeoutExpired:
            return
        self._proc = None

    def _rpc_port_is_open(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            return sock.connect_ex((self.cfg.rpc_host, self.cfg.rpc_port)) == 0

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def stop(self) -> None:
        if not self._proc:
            return
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
