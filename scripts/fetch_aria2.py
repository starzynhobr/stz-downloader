"""Download the aria2 Windows binary into third_party/aria2/.

Usage:  python scripts/fetch_aria2.py

Fetches the latest aria2 1.x Windows build from the official GitHub releases,
extracts aria2c.exe and the bundled COPYING (GPL) license into
third_party/aria2/. The binary is not committed to git (see .gitignore).
"""
from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

DEST = Path(__file__).resolve().parents[1] / "third_party" / "aria2"
# Pin a known-good release. Update as needed.
RELEASE = "https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip"


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {RELEASE} …")
    with urllib.request.urlopen(RELEASE) as resp:  # noqa: S310 - trusted URL
        data = resp.read()

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for member in zf.namelist():
            base = member.rsplit("/", 1)[-1]
            if base in ("aria2c.exe", "COPYING"):
                target = DEST / ("LICENSE" if base == "COPYING" else base)
                target.write_bytes(zf.read(member))
                print(f"  -> {target.relative_to(DEST.parents[1])}")

    if not (DEST / "aria2c.exe").exists():
        print("ERROR: aria2c.exe not found in archive", file=sys.stderr)
        return 1
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
