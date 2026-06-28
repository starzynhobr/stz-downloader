"""Build clean, store-ready extension packages.

Produces two zips under dist/:
  - stz-extension-chrome-<version>.zip   (manifest with service_worker)
  - stz-extension-firefox-<version>.zip  (manifest with background.scripts + gecko)

Each zip contains the shared files plus the right manifest renamed to
``manifest.json``. The variant files (manifest.chrome.json / manifest.firefox.json)
and the swap artifact (manifest.json) are NOT included, so the package is exactly
what each store expects.

Usage:  python scripts/package_extension.py
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "extension"
DIST = ROOT / "dist"

# Shared files/dirs that go into every package.
SHARED = ["background.js", "popup.html", "popup.js", "icons", "_locales"]

VARIANTS = {
    "chrome": "manifest.chrome.json",
    "firefox": "manifest.firefox.json",
}


def _iter_files(path: Path):
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if child.is_file():
                yield child
    elif path.is_file():
        yield path


def _version() -> str:
    manifest = json.loads((EXT / VARIANTS["chrome"]).read_text("utf-8"))
    return manifest.get("version", "0.0.0")


def build(target: str, manifest_name: str, version: str) -> Path:
    DIST.mkdir(parents=True, exist_ok=True)
    out = DIST / f"stz-extension-{target}-{version}.zip"
    if out.exists():
        out.unlink()

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        # the chosen manifest, written as manifest.json
        zf.writestr("manifest.json", (EXT / manifest_name).read_text("utf-8"))
        for name in SHARED:
            for file in _iter_files(EXT / name):
                zf.write(file, file.relative_to(EXT).as_posix())
    return out


def main() -> int:
    version = _version()
    for target, manifest_name in VARIANTS.items():
        out = build(target, manifest_name, version)
        size_kb = out.stat().st_size / 1024
        print(f"  -> {out.relative_to(ROOT)} ({size_kb:.1f} KB)")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
