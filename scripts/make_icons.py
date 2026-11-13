#!/usr/bin/env python3
"""Generate PWA icons with zero dependencies (stdlib zlib + struct only).

Draws the RecruiMate "R" mark on a brand-navy gradient with rounded corners
(regular icons) and full-bleed square (maskable icon for Android adaptive).

Usage: python3 scripts/make_icons.py   (from the repo root)
Writes into frontend/public/icons/.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

# 5x7 bitmap of the letter "R".
GLYPH = [
    "11110",
    "10001",
    "10001",
    "11110",
    "10100",
    "10010",
    "10001",
]

NAVY_TOP = (13, 27, 75)  # brand-950
NAVY_BOTTOM = (36, 51, 122)  # gradient end
WHITE = (255, 255, 255, 255)
ACCENT = (108, 140, 255)  # brand-400 underline


def png_bytes(width: int, height: int, get_rgba) -> bytes:
    """Minimal PNG encoder: 8-bit RGBA, no interlace."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type 0 (None)
        for x in range(width):
            raw.extend(get_rgba(x, y))
    compressed = zlib.compress(bytes(raw), 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )


def draw_icon(size: int, *, rounded: bool, glyph_scale: float = 0.42) -> bytes:
    """Render the icon at ``size`` px. ``rounded`` clips corners like iOS/Chrome."""
    radius = int(size * (0.18 if rounded else 0.0))
    cell = int(size * glyph_scale / 7)
    glyph_w, glyph_h = cell * 5, cell * 7
    gx0 = (size - glyph_w) // 2
    gy0 = (size - glyph_h) // 2 - int(size * 0.02)

    def pixel(x: int, y: int) -> tuple:
        if rounded:
            # Transparent outside the four corner circles (anti-aliased edge).
            r = radius - 1
            if x < radius and y < radius:
                if (x - radius) ** 2 + (y - radius) ** 2 > r * r:
                    return (0, 0, 0, 0)
            elif x >= size - radius and y < radius:
                if (x - (size - radius)) ** 2 + (y - radius) ** 2 > r * r:
                    return (0, 0, 0, 0)
            elif x < radius and y >= size - radius:
                if (x - radius) ** 2 + (y - (size - radius)) ** 2 > r * r:
                    return (0, 0, 0, 0)
            elif x >= size - radius and y >= size - radius:
                dx = x - (size - radius)
                dy = y - (size - radius)
                if dx * dx + dy * dy > r * r:
                    return (0, 0, 0, 0)
        # Vertical gradient background.
        t = y / max(size - 1, 1)
        bg = tuple(round(a + (b - a) * t) for a, b in zip(NAVY_TOP, NAVY_BOTTOM))

        # Letter R.
        col = (x - gx0) // cell
        row = (y - gy0) // cell
        if 0 <= col < 5 and 0 <= row < 7 and GLYPH[row][col] == "1":
            return WHITE

        # Accent underline bar beneath the glyph.
        bar_top = gy0 + glyph_h + int(cell * 0.55)
        bar_h = max(int(cell * 0.34), 2)
        bar_w = int(glyph_w * 0.62)
        bx0 = (size - bar_w) // 2
        if bar_top <= y < bar_top + bar_h and bx0 <= x < bx0 + bar_w:
            return (*ACCENT, 255)
        return (*bg, 255)

    return png_bytes(size, size, pixel)


def main() -> None:
    out = Path("frontend/public/icons")
    out.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        (out / f"icon-{size}.png").write_bytes(draw_icon(size, rounded=True))
    (out / "maskable-512.png").write_bytes(draw_icon(512, rounded=False, glyph_scale=0.34))
    (out / "apple-touch-icon.png").write_bytes(draw_icon(180, rounded=False, glyph_scale=0.46))
    print(f"wrote icons to {out}")


if __name__ == "__main__":
    main()
