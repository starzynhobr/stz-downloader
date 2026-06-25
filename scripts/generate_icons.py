"""Generate the extension icons (no external deps).

Draws a rounded accent-colored square with a white download arrow, at 16/48/128
px, into extension/icons/. Run: python scripts/generate_icons.py
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "extension" / "icons"
ACCENT = (76, 141, 255, 255)   # #4c8dff
WHITE = (255, 255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


def _png(width: int, height: int, pixels: list[tuple[int, int, int, int]]) -> bytes:
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type 0
        for x in range(width):
            raw.extend(pixels[y * width + x])

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    idat = zlib.compress(bytes(raw), 9)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def render(size: int) -> bytes:
    s = size
    r = s * 0.22  # corner radius
    px = [TRANSPARENT] * (s * s)

    def inside_round_rect(x: float, y: float) -> bool:
        # distance into the rounded-rect body
        cx = min(max(x, r), s - r)
        cy = min(max(y, r), s - r)
        dx = x - cx
        dy = y - cy
        return dx * dx + dy * dy <= r * r

    # arrow geometry (a downward arrow)
    shaft_w = s * 0.12
    head_w = s * 0.34
    top = s * 0.24
    shaft_bottom = s * 0.52
    tip = s * 0.74
    cxc = s / 2

    for y in range(s):
        for x in range(s):
            fx, fy = x + 0.5, y + 0.5
            if not inside_round_rect(fx, fy):
                continue
            color = ACCENT
            # shaft
            if top <= fy <= shaft_bottom and abs(fx - cxc) <= shaft_w / 2:
                color = WHITE
            # arrow head (triangle from shaft_bottom to tip)
            elif shaft_bottom <= fy <= tip:
                frac = (tip - fy) / (tip - shaft_bottom)
                half = (head_w / 2) * frac
                if abs(fx - cxc) <= half:
                    color = WHITE
            px[y * s + x] = color
    return _png(s, s, px)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (16, 48, 128):
        (OUT / f"icon{size}.png").write_bytes(render(size))
        print(f"  -> extension/icons/icon{size}.png")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
