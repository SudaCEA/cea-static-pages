"""Cut a chroma-key green background out of a PNG and save it with alpha.

The flat-colour cut of the side view is easy to key: its palette is only white,
grey, black and crimson, so any saturated green is background by construction.
Pixels that pass the green test become fully transparent; everything else is
left untouched, which keeps the artwork's hard pixel edges exactly as they are.

Transparent pixels are stored as white so that viewers that ignore the alpha
channel still show the artwork the way it was drawn (on white).

Usage:
    python gamejam/tools/key_green.py
    python gamejam/tools/key_green.py --source in.png --target out.png
"""

from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SOURCE = ROOT / "gamejam" / "assets" / "mirror-26" / "ellia-sideview-flat.png"

GREEN_MIN = 100
GREEN_DOMINANCE = 60


def read_png_rgba(path: Path) -> tuple[int, int, bytearray]:
    """Decode an 8-bit RGB/RGBA PNG into tightly packed RGBA bytes."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG file")

    pos = 8
    idat = bytearray()
    width = height = depth = colour = interlace = 0
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, depth, colour, _comp, _filter, interlace = struct.unpack(
                ">IIBBBBB", chunk
            )
        elif kind == b"IDAT":
            idat += chunk
        elif kind == b"IEND":
            break

    if depth != 8 or interlace != 0 or colour not in (2, 6):
        raise ValueError(f"{path}: expected an 8-bit non-interlaced RGB/RGBA PNG")
    channels = 3 if colour == 2 else 4
    stride = width * channels
    raw = zlib.decompress(bytes(idat))
    pixels = bytearray(width * height * 4)
    previous = bytearray(stride)
    offset = 0
    for y in range(height):
        filter_type = raw[offset]
        offset += 1
        line = bytearray(raw[offset:offset + stride])
        offset += stride
        if filter_type == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                line[i] = (line[i] + previous[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + previous[i]) >> 1)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                up = previous[i]
                up_left = previous[i - channels] if i >= channels else 0
                pa = abs(up - up_left)
                pb = abs(left - up_left)
                pc = abs(left + up - 2 * up_left)
                predictor = left if pa <= pb and pa <= pc else (up if pb <= pc else up_left)
                line[i] = (line[i] + predictor) & 0xFF
        previous = line

        base = y * width * 4
        if channels == 4:
            pixels[base:base + stride] = line
        else:
            for x in range(width):
                pixels[base + x * 4:base + x * 4 + 3] = line[x * 3:x * 3 + 3]
                pixels[base + x * 4 + 3] = 255
    return width, height, pixels


def write_rgba_png(path: Path, width: int, height: int, pixels: bytes | bytearray) -> None:
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += pixels[y * stride:(y + 1) * stride]
    compressed = zlib.compress(bytes(raw), 9)

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = struct.pack(">I", len(payload)) + kind + payload
        return body + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )


def is_green(r: int, g: int, b: int) -> bool:
    return g >= GREEN_MIN and g - max(r, b) >= GREEN_DOMINANCE


def key_green(pixels: bytearray) -> int:
    removed = 0
    for i in range(0, len(pixels), 4):
        r = pixels[i]
        g = pixels[i + 1]
        b = pixels[i + 2]
        if is_green(r, g, b):
            # White underlay: sensible if a viewer ignores alpha, and invisible
            # to premultiplied compositing.
            pixels[i] = pixels[i + 1] = pixels[i + 2] = 255
            pixels[i + 3] = 0
            removed += 1
    return removed


def cut(source: Path, target: Path, *, quiet: bool = False) -> dict[str, object]:
    width, height, pixels = read_png_rgba(source)
    removed = key_green(pixels)
    write_rgba_png(target, width, height, pixels)

    opaque = 0
    semi = 0
    for i in range(3, len(pixels), 4):
        alpha = pixels[i]
        if alpha == 255:
            opaque += 1
        elif alpha:
            semi += 1

    stats = {
        "size": (width, height),
        "target": target,
        "bytes": target.stat().st_size,
        "transparent": removed,
        "opaque": opaque,
        "semi": semi,
    }
    if not quiet:
        print(f"{width}x{height} -> {target} ({stats['bytes'] / 1024:.1f} KiB)")
        print(f"  transparent {removed} px, opaque {opaque} px, partial {semi} px")
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Replace a green-screen background with transparency.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    target = args.target if args.target is not None else args.source
    cut(args.source, target, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
