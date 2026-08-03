"""Spawn and supervise the ``aria2c`` RPC subprocess."""
from __future__ import annotations

import logging
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

from ..config import Aria2Config
from ..config import user_config_dir

log = logging.getLogger(__name__)

# Options that describe *this* process rather than download behaviour. An
# already-running aria2 is never rejected over these.
_TRANSIENT_ARGS = {
    "enable-rpc",
    "rpc-listen-all",
    "rpc-listen-port",
    "rpc-secret",
    "save-session",
    "save-session-interval",
    "input-file",
}


_SIZE_SUFFIX = {"K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}
_SIZE_RE = re.compile(r"^(\d+)([KMG])?$", re.IGNORECASE)


def _normalize_option(value: str) -> str:
    """Put an option value in the form aria2 reports it back in.

    aria2 expands size suffixes, so ``--min-split-size=1M`` comes back as
    ``1048576``. Comparing the raw strings would flag every launch as a config
    change and restart a perfectly good process.
    """
    text = str(value).strip()
    match = _SIZE_RE.match(text)
    if not match:
        return text
    number, suffix = match.groups()
    return str(int(number) * (_SIZE_SUFFIX[suffix.upper()] if suffix else 1))


class Aria2Manager:
    def __init__(self, cfg: Aria2Config, download_dir: Path):
        self.cfg = cfg
        self.download_dir = download_dir
        self._proc: subprocess.Popen | None = None
        # Guards against a restart loop if aria2 reports an option back in a
        # form that never compares equal to what we passed.
        self._replaced_stale = False

    def start(self) -> None:
        if self._proc and self._proc.poll() is None:
            return
        if self._rpc_port_is_open():
            # An aria2 is already listening. It may be an orphan from a
            # previous run, started with options we have since changed --
            # adopting it blindly means config edits silently never apply.
            if self._replaced_stale or self._existing_matches_config():
                return
            log.warning("Existing aria2 has stale options; restarting it")
            self._replaced_stale = True
            if not self._shutdown_existing():
                log.error("Could not shut down the existing aria2; adopting it as-is")
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

    # -- reconciling with an already-running aria2 -----------------------

    def _desired_options(self) -> dict[str, str]:
        """The download-behaviour options we would pass, as aria2 names them.

        ``--file-allocation=none`` becomes ``{"file-allocation": "none"}``, so
        it can be compared against ``aria2.getGlobalOption``.
        """
        wanted: dict[str, str] = {"dir": str(self.download_dir)}
        for arg in self.cfg.extra_args:
            if not arg.startswith("--") or "=" not in arg:
                continue
            key, _, value = arg[2:].partition("=")
            if key not in _TRANSIENT_ARGS:
                wanted[key] = value
        return wanted

    def _rpc(self, method: str, *params, timeout: float = 5.0):
        payload = {
            "jsonrpc": "2.0",
            "id": "manager",
            "method": method,
            "params": [f"token:{self.cfg.rpc_secret}", *params],
        }
        resp = httpx.post(self.cfg.rpc_url, json=payload, timeout=timeout)
        data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", "aria2 error"))
        return data["result"]

    def _existing_matches_config(self) -> bool:
        """Is the running aria2 ours, and configured the way we want?

        Answering "no" to either question means we replace it. A process we
        can't authenticate against isn't ours to kill, so that counts as a
        match and we leave it alone.
        """
        try:
            current = self._rpc("aria2.getGlobalOption")
        except Exception as exc:  # noqa: BLE001 -- not ours, or not healthy
            log.warning("Could not query the running aria2 (%s); leaving it alone", exc)
            return True

        for key, value in self._desired_options().items():
            # Options aria2 doesn't report back are not worth restarting over.
            if key not in current:
                continue
            if _normalize_option(current[key]) != _normalize_option(value):
                log.info("aria2 option %s is %r, want %r", key, current[key], value)
                return False
        return True

    def _shutdown_existing(self) -> bool:
        """Ask the running aria2 to exit, and wait for the port to free up.

        ``aria2.shutdown`` is graceful: it saves the session first, so queued
        and partial downloads survive into the process we start next.
        """
        try:
            self._rpc("aria2.shutdown")
        except Exception as exc:  # noqa: BLE001
            log.warning("aria2.shutdown failed (%s)", exc)
            return False
        # Preallocation can keep aria2 busy for a while before it honours the
        # shutdown, so this waits well past the usual sub-second case.
        for _ in range(60):
            if not self._rpc_port_is_open():
                return True
            time.sleep(0.5)
        return False

    def is_running(self) -> bool:
        if self._proc is not None:
            return self._proc.poll() is None
        # We adopted an existing process rather than spawning one.
        return self._rpc_port_is_open()

    def stop(self) -> None:
        if self._proc is None:
            return
        if self._proc.poll() is None:
            # Shut down over RPC first so aria2 writes its session file; a bare
            # terminate() loses anything queued since the last autosave.
            try:
                self._rpc("aria2.shutdown", timeout=2.0)
                self._proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                pass
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
