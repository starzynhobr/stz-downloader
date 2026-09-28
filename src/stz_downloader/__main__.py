"""Entry point.

Runs the FastAPI bridge in a background thread and the PySide6/QML UI on the
main thread. ``--headless`` runs only the bridge (useful for the extension
without the GUI, or for development).
"""
from __future__ import annotations

import argparse
import logging
import os
import secrets
import socket
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path

import uvicorn

from .config import load_config
from .config import user_config_dir
from .runtime import (
    InstanceLock,
    RuntimeInfo,
    load_runtime,
    publish_runtime,
    remove_runtime,
    reserve_server_socket,
)
from .server import create_app


def _setup_logging() -> None:
    log_path = user_config_dir() / "app.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_path,
        filemode="a",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)

    def _log_exception(exc_type, exc, tb) -> None:
        logging.critical(
            "Unhandled exception\n%s",
            "".join(traceback.format_exception(exc_type, exc, tb)),
        )

    sys.excepthook = _log_exception


def _ensure_stdio() -> None:
    """PyInstaller --windowed may set stdio streams to None."""
    if sys.stdin is None:
        sys.stdin = open(os.devnull, "r", encoding="utf-8")  # noqa: SIM115
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115


def _run_server(
    cfg,
    server_socket: socket.socket,
    auth_token: str,
) -> tuple[uvicorn.Server, threading.Thread]:
    app = create_app(cfg, auth_token=auth_token)
    # access_log off: the UI polls /api/downloads every second, which would
    # otherwise spam the console with one GET log line per second.
    config = uvicorn.Config(
        app,
        host=cfg.server.host,
        port=server_socket.getsockname()[1],
        log_level="warning",
        access_log=False,
        log_config=None,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(
        target=server.run,
        kwargs={"sockets": [server_socket]},
        daemon=True,
        name="stz-bridge",
    )
    thread.start()
    deadline = time.monotonic() + 20.0
    while thread.is_alive() and not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=2.0)
        raise RuntimeError("the local bridge did not become ready")
    return server, thread


def _handoff_to_running_instance(timeout: float = 20.0) -> bool:
    """If an instance is already up, ask it to show itself and report True.

    The per-user runtime lock owns single-instance behavior. Launching again
    uses the authenticated runtime record to surface the existing window.
    """
    import httpx

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        info = load_runtime()
        if info:
            headers = {"Authorization": info.authorization}
            try:
                health = httpx.get(
                    f"{info.base_url}/api/health", headers=headers, timeout=1.5
                ).json()
                if health.get("ok") and health.get("app") == "stz-downloader":
                    httpx.post(f"{info.base_url}/api/focus", headers=headers, timeout=1.5)
                    logging.info("Another instance is running; asked it to come to front")
                    return True
            except Exception:  # noqa: BLE001 -- first instance may still be starting
                pass
        time.sleep(0.1)
    return False


def _ensure_native_host_registration() -> None:
    if not getattr(sys, "frozen", False):
        return
    from .native_host import register_native_host

    helper = Path(sys.executable).resolve().with_name("stz-downloader-native-host.exe")
    if helper.exists():
        try:
            register_native_host(helper)
        except Exception:  # noqa: BLE001 -- downloads in the UI still work
            logging.exception("Could not register the browser Native Messaging host")


def main() -> int:
    _ensure_stdio()
    _setup_logging()
    logging.info(
        "Starting STZ Downloader argv=%s frozen=%s",
        sys.argv,
        getattr(sys, "frozen", False),
    )

    parser = argparse.ArgumentParser(prog="stz-downloader")
    parser.add_argument("--headless", action="store_true", help="run the bridge without the GUI")
    parser.add_argument("--minimized", action="store_true", help="start hidden in the tray")
    args, _unknown = parser.parse_known_args()

    cfg = load_config()
    instance_lock = InstanceLock()
    if not instance_lock.acquire():
        return 0 if _handoff_to_running_instance() else 1

    _ensure_native_host_registration()
    server = None
    server_thread = None
    runtime_info = None
    server_socket = None
    try:
        server_socket, actual_port = reserve_server_socket(cfg.server.host, cfg.server.port)
        if actual_port != cfg.server.port:
            logging.warning(
                "Preferred bridge port %s is unavailable; using dynamic port %s",
                cfg.server.port,
                actual_port,
            )
        runtime_info = RuntimeInfo(
            pid=os.getpid(),
            host=cfg.server.host,
            port=actual_port,
            token=secrets.token_urlsafe(32),
            instance_id=uuid.uuid4().hex,
        )
        server, server_thread = _run_server(cfg, server_socket, runtime_info.token)
        server_socket = None  # Uvicorn owns it now.
        publish_runtime(runtime_info)

        if args.headless:
            try:
                threading.Event().wait()
            except KeyboardInterrupt:
                pass
            return 0

        # GUI imports are deferred so --headless works without a display.
        from .ui import run_ui

        return run_ui(
            cfg,
            start_minimized=args.minimized,
            base_url=runtime_info.base_url,
            auth_token=runtime_info.token,
        )
    except Exception:  # noqa: BLE001 -- log startup failures in windowed builds
        logging.exception("STZ Downloader failed to start")
        return 1
    finally:
        if runtime_info:
            remove_runtime(runtime_info.instance_id)
        if server:
            server.should_exit = True
        if server_thread:
            server_thread.join(timeout=5.0)
        if server_socket:
            server_socket.close()
        instance_lock.release()


if __name__ == "__main__":
    sys.exit(main())
