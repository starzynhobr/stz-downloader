"""Entry point.

Runs the FastAPI bridge in a background thread and the PySide6/QML UI on the
main thread. ``--headless`` runs only the bridge (useful for the extension
without the GUI, or for development).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import traceback

import uvicorn

from .config import load_config
from .config import user_config_dir
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


def _run_server(cfg) -> uvicorn.Server:
    app = create_app(cfg)
    # access_log off: the UI polls /api/downloads every second, which would
    # otherwise spam the console with one GET log line per second.
    config = uvicorn.Config(
        app,
        host=cfg.server.host,
        port=cfg.server.port,
        log_level="warning",
        access_log=False,
        log_config=None,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server


def _handoff_to_running_instance(cfg) -> bool:
    """If an instance is already up, ask it to show itself and report True.

    The bridge port doubles as the single-instance lock: only one process can
    hold it. Launching again should surface the running window rather than
    stack another tray icon, which is what made a previous app of this shape
    accumulate duplicates.
    """
    import httpx

    base = f"http://{cfg.server.host}:{cfg.server.port}"
    try:
        if not httpx.get(f"{base}/api/health", timeout=1.5).json().get("ok"):
            return False
        httpx.post(f"{base}/api/focus", timeout=1.5)
        logging.info("Another instance is running; asked it to come to front")
        return True
    except Exception:  # noqa: BLE001 -- nothing listening, or not our server
        return False


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

    if not args.headless and _handoff_to_running_instance(cfg):
        return 0

    server = _run_server(cfg)

    if args.headless:
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        server.should_exit = True
        return 0

    # GUI imports are deferred so --headless works without a display.
    from .ui import run_ui

    code = run_ui(cfg, start_minimized=args.minimized)
    server.should_exit = True
    return code


if __name__ == "__main__":
    sys.exit(main())
