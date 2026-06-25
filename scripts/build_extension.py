"""Swap the active extension manifest between Chrome and Firefox.

The two browsers need different `background` keys (service_worker vs scripts)
and Firefox needs a gecko id, so we keep both variants and copy the chosen one
to extension/manifest.json (the file the browser actually reads).

Usage:
    python scripts/build_extension.py firefox
    python scripts/build_extension.py chrome
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

EXT = Path(__file__).resolve().parents[1] / "extension"

# The canonical Chrome manifest is kept alongside as manifest.chrome.json so we
# never lose it when manifest.json gets overwritten by the Firefox variant.
CHROME_SRC = EXT / "manifest.chrome.json"
FIREFOX_SRC = EXT / "manifest.firefox.json"
ACTIVE = EXT / "manifest.json"


def _ensure_chrome_backup() -> None:
    # On first run, snapshot the current (Chrome) manifest.json.
    if not CHROME_SRC.exists() and ACTIVE.exists():
        shutil.copyfile(ACTIVE, CHROME_SRC)


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("chrome", "firefox"):
        print(__doc__)
        return 2

    _ensure_chrome_backup()
    target = sys.argv[1]
    src = FIREFOX_SRC if target == "firefox" else CHROME_SRC
    if not src.exists():
        print(f"ERROR: {src.name} not found", file=sys.stderr)
        return 1

    shutil.copyfile(src, ACTIVE)
    print(f"Active manifest.json -> {target} ({src.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
