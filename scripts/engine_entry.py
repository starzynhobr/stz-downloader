"""PyInstaller entry for the headless engine used by the Tauri desktop shell.

The engine has no UI of its own, so it always runs as ``--headless`` whatever
it was launched with.
"""
import sys

from stz_downloader.__main__ import main


if __name__ == "__main__":
    if "--headless" not in sys.argv:
        sys.argv.append("--headless")
    raise SystemExit(main())
