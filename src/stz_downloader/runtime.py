"""Per-user runtime discovery for the local bridge.

The bridge port is intentionally not an identity or a single-instance lock.
The application reserves any available loopback port, then publishes the
actual endpoint and a session token in a user-private runtime file.  Native
Messaging and second launches use that file to find the current instance.
"""
from __future__ import annotations

import json
import os
import socket
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import BinaryIO

from .config import APP_NAME

RUNTIME_APP = "stz-downloader"
RUNTIME_PROTOCOL = 1


def runtime_dir() -> Path:
    """Return a per-user, non-roaming directory for ephemeral state."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if not base:
        base = str(Path.home() / ".local" / "state")
    return Path(base) / APP_NAME


def runtime_path() -> Path:
    return runtime_dir() / "runtime.json"


def lock_path() -> Path:
    return runtime_dir() / "instance.lock"


@dataclass(frozen=True)
class RuntimeInfo:
    pid: int
    host: str
    port: int
    token: str
    instance_id: str
    app: str = RUNTIME_APP
    protocol: int = RUNTIME_PROTOCOL

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def authorization(self) -> str:
        return f"Bearer {self.token}"


def load_runtime(path: Path | None = None) -> RuntimeInfo | None:
    target = path or runtime_path()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        info = RuntimeInfo(**payload)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    if info.app != RUNTIME_APP or info.protocol != RUNTIME_PROTOCOL:
        return None
    if info.host not in {"127.0.0.1", "localhost"} or not 0 < info.port < 65536:
        return None
    if not info.token or not info.instance_id:
        return None
    return info


def publish_runtime(info: RuntimeInfo, path: Path | None = None) -> None:
    """Atomically publish a complete runtime record."""
    target = path or runtime_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(asdict(info), separators=(",", ":")), encoding="utf-8")
    if os.name != "nt":
        temp.chmod(0o600)
    os.replace(temp, target)


def remove_runtime(instance_id: str, path: Path | None = None) -> None:
    """Remove only the record owned by this instance."""
    target = path or runtime_path()
    current = load_runtime(target)
    if current and current.instance_id == instance_id:
        try:
            target.unlink()
        except FileNotFoundError:
            pass


def reserve_server_socket(host: str, preferred_port: int) -> tuple[socket.socket, int]:
    """Reserve the preferred port, falling back atomically to an ephemeral one."""
    ports = [preferred_port]
    if preferred_port != 0:
        ports.append(0)

    last_error: OSError | None = None
    for port in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind((host, port))
            sock.set_inheritable(True)
            return sock, int(sock.getsockname()[1])
        except OSError as exc:
            last_error = exc
            sock.close()
    assert last_error is not None
    raise last_error


class InstanceLock:
    """A process-lifetime, per-user file lock independent from TCP ports."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or lock_path()
        self._file: BinaryIO | None = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = self.path.open("a+b")
        if fh.seek(0, os.SEEK_END) == 0:
            fh.write(b"0")
            fh.flush()
        fh.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self._file = fh
        return True

    def release(self) -> None:
        if not self._file:
            return
        fh, self._file = self._file, None
        try:
            fh.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()

    def __enter__(self) -> "InstanceLock":
        if not self.acquire():
            raise RuntimeError("another instance owns the runtime lock")
        return self

    def __exit__(self, *_args) -> None:
        self.release()
