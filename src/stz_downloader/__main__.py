"""Entry point.

Runs the FastAPI bridge in a background thread and the PySide6/QML UI on the
main thread. ``--headless`` runs only the bridge (useful for the extension
without the GUI, or for development).
"""
from __future__ import annotations

import argparse
import sys
import threading

import uvicorn

from .config import load_config
from .server import create_app


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
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server


def main() -> int:
    parser = argparse.ArgumentParser(prog="stz-downloader")
    parser.add_argument("--headless", action="store_true", help="run the bridge without the GUI")
    args = parser.parse_args()

    cfg = load_config()
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

    return run_ui(cfg)


if __name__ == "__main__":
    sys.exit(main())
