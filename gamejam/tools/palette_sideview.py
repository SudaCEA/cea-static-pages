"""Snap the side-view artwork onto a strict flat palette.

The source PNG came out of a lossy pipeline: the artwork only uses five flat
colours, but the file stores ~25k near-miss shades (compression noise, a
one-pixel fringe along silhouettes, slightly warm "white").  Painting with it
or re-tracing it drags all that dirt into the result.

This tool rebuilds the bitmap on an explicit palette — white, grey, black and
the deep crimson — and removes the fringe so that the saved image contains
nothing but those colours.  The output is an indexed PNG, which also keeps the
palette visible to any later tool.

Usage:
    python gamejam/tools/palette_sideview.py
    python gamejam/tools/palette_sideview.py --palette soft --target out.png
"""

from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from trace_sideview import read_png  # noqa: E402

ROOT = TOOLS.parent.parent
ASSETS = ROOT / "gamejam" / "assets" / "mirror-26"
DEFAULT_SOURCE = ASSETS / "ellia-sideview.png"
DEFAULT_TARGET = ASSETS / "ellia-sideview-flat.png"

# "flat" is the requested four-colour cut: one neutral grey for the whole cape.
# "soft" keeps the two greys the artwork actually used for the cloth shading.
PALETTES = {
    "flat": (
        ("paper", (255, 255, 255)),
        ("grey", (136, 136, 136)),
        ("ink", (0, 0, 0)),
        ("accent", (138, 2, 17)),
    ),
    "soft": (
        ("paper", (255, 255, 255)),
        ("shade", (126, 126, 126)),
        ("veil", (145, 145, 145)),
        ("ink", (0, 0, 0)),
        ("accent", (138, 2, 17)),
    ),
}
GREY_NAMES = frozenset({"grey", "shade", "veil"})


# --------------------------------------------------------------------------
# Colour science
# --------------------------------------------------------------------------


def _linear(channel: int) -> float:
    value = channel / 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def _lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = (_linear(channel) for channel in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else 7.787 * t + 16.0 / 116.0

    fx, fy, fz = f(x), f(y), f(z)
    return 116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)


def _nearest(rgb: tuple[int, int, int], labs, accent: int, accent_rule: bool) -> int:
    r, g, b = rgb
    if accent_rule and r - max(g, b) >= 30 and r >= 70:
        # Pink/crimson anti-aliasing: never let it fall through to grey.
        return accent
    lab = _lab(rgb)
    best = 0
    best_distance = None
    for index, other in enumerate(labs):
        dl = lab[0] - other[0]
        da = lab[1] - other[1]
        db = lab[2] - other[2]
        distance = dl * dl + da * da + db * db
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best = index
    return best


# --------------------------------------------------------------------------
# Bit-plane helpers (same representation as trace_sideview)
# --------------------------------------------------------------------------


def _bit_rows(labels: bytearray, width: int, height: int, layer: int) -> list[int]:
    table = bytearray(b"0" * 256)
    table[layer] = ord("1")
    table = bytes(table)
    rows: list[int] = []
    for y in range(height):
        row = bytes(labels[y * width:(y + 1) * width])
        rows.append(int(row.translate(table)[::-1], 2))
    return rows


def _erode3(rows: list[int], width: int) -> list[int]:
    full = (1 << width) - 1
    horizontal = [row & ((row << 1) & full) & (row >> 1) for row in rows]
    out = [0] * len(rows)
    for y in range(1, len(rows) - 1):
        out[y] = horizontal[y - 1] & horizontal[y] & horizontal[y + 1]
    return out


def _dilate3(rows: list[int], width: int) -> list[int]:
    full = (1 << width) - 1
    horizontal = [row | ((row << 1) & full) | (row >> 1) for row in rows]
    out = [0] * len(rows)
    for y in range(1, len(rows) - 1):
        out[y] = (horizontal[y - 1] | horizontal[y] | horizontal[y + 1]) & full
    return out


def _remove_fringe(
    labels: bytearray,
    width: int,
    height: int,
    grey_indices: tuple[int, ...],
    colour_count: int,
) -> int:
    """Drop thin grey slivers left by lossy edges.

    Anti-aliasing between black and white passes through mid-grey, so a plain
    nearest-colour pass paints a grey outline around every ink shape.  A 3x3
    opening deletes grey structures thinner than two pixels; those pixels go to
    the majority of their neighbours, which reattaches the fringe to the edge
    it belongs to.  Grey pixels that form part of a real grey area are thick
    enough to survive and keep their colour.
    """
    rows = {layer: _bit_rows(labels, width, height, layer) for layer in grey_indices}
    updates: list[tuple[int, int]] = []
    for layer in grey_indices:
        opened = _dilate3(_erode3(rows[layer], width), width)
        for y in range(height):
            removed = rows[layer][y] & ~opened[y]
            if not removed:
                continue
            bits = removed
            while bits:
                lowest = bits & -bits
                x = lowest.bit_length() - 1
                bits ^= lowest
                counts = [0] * colour_count
                for ny in range(max(0, y - 1), min(height, y + 2)):
                    base = ny * width
                    for nx in range(max(0, x - 1), min(width, x + 2)):
                        if nx == x and ny == y:
                            continue
                        counts[labels[base + nx]] += 1
                best = layer
                best_count = 0
                for index, count in enumerate(counts):
                    if count > best_count:
                        best_count = count
                        best = index
                if best in grey_indices:
                    best = layer
                updates.append((y * width + x, best))
        rows[layer] = opened
    for index, label in updates:
        labels[index] = label
    return len(updates)


def _remove_small(
    labels: bytearray, width: int, height: int, min_area: int, colour_count: int
) -> int:
    """Absorb islands smaller than `min_area` into their surroundings."""
    total = width * height
    visited = bytearray(total)
    absorbed = 0
    pending: list[tuple[list[int], int]] = []
    for start in range(total):
        if visited[start]:
            continue
        label = labels[start]
        visited[start] = 1
        stack = [start]
        members: list[int] = []
        overflow = False
        while stack:
            index = stack.pop()
            if not overflow:
                members.append(index)
                if len(members) > min_area:
                    overflow = True
                    members = []
            x = index % width
            if x > 0:
                neighbour = index - 1
                if not visited[neighbour] and labels[neighbour] == label:
                    visited[neighbour] = 1
                    stack.append(neighbour)
            if x + 1 < width:
                neighbour = index + 1
                if not visited[neighbour] and labels[neighbour] == label:
                    visited[neighbour] = 1
                    stack.append(neighbour)
            if index >= width:
                neighbour = index - width
                if not visited[neighbour] and labels[neighbour] == label:
                    visited[neighbour] = 1
                    stack.append(neighbour)
            if index + width < total:
                neighbour = index + width
                if not visited[neighbour] and labels[neighbour] == label:
                    visited[neighbour] = 1
                    stack.append(neighbour)
        if members:
            pending.append((members, label))
    for members, label in pending:
        counts = [0] * colour_count
        for index in members:
            x = index % width
            if x > 0 and labels[index - 1] != label:
                counts[labels[index - 1]] += 1
            if x + 1 < width and labels[index + 1] != label:
                counts[labels[index + 1]] += 1
            if index >= width and labels[index - width] != label:
                counts[labels[index - width]] += 1
            if index + width < total and labels[index + width] != label:
                counts[labels[index + width]] += 1
        best = label
        best_count = 0
        for candidate, count in enumerate(counts):
            if count > best_count:
                best_count = count
                best = candidate
        if best != label:
            for index in members:
                labels[index] = best
            absorbed += 1
    return absorbed


# --------------------------------------------------------------------------
# PNG output
# --------------------------------------------------------------------------


def write_indexed_png(
    path: Path,
    width: int,
    height: int,
    labels: bytearray,
    palette: tuple[tuple[str, tuple[int, int, int]], ...],
) -> None:
    stride = width
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += labels[y * stride:(y + 1) * stride]
    compressed = zlib.compress(bytes(raw), 9)

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = struct.pack(">I", len(payload)) + kind + payload
        return body + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    plte = bytes(channel for _name, rgb in palette for channel in rgb)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0))
        + chunk(b"PLTE", plte)
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------


def flatten(
    source: Path,
    target: Path,
    *,
    palette_name: str,
    min_area: int,
    quiet: bool = False,
) -> dict[str, object]:
    palette = PALETTES[palette_name]
    colour_count = len(palette)
    labs = [_lab(rgb) for _name, rgb in palette]
    accent = next(
        index for index, (name, _rgb) in enumerate(palette) if name == "accent"
    )
    grey_indices = tuple(
        index for index, (name, _rgb) in enumerate(palette) if name in GREY_NAMES
    )

    width, height, pixels = read_png(source)

    histogram: dict[int, int] = {}
    for i in range(0, len(pixels), 3):
        key = (pixels[i] << 16) | (pixels[i + 1] << 8) | pixels[i + 2]
        histogram[key] = histogram.get(key, 0) + 1

    mapping: dict[int, int] = {}
    for key in histogram:
        rgb = (key >> 16, (key >> 8) & 0xFF, key & 0xFF)
        mapping[key] = _nearest(rgb, labs, accent, accent_rule=True)

    labels = bytearray(width * height)
    for index in range(width * height):
        offset = index * 3
        key = (pixels[offset] << 16) | (pixels[offset + 1] << 8) | pixels[offset + 2]
        labels[index] = mapping[key]

    fringe = _remove_fringe(labels, width, height, grey_indices, colour_count) if grey_indices else 0
    # Absorbing an island can leave a one-pixel flake behind (the island is
    # recoloured before the island it touches).  Keep going until a pass is
    # clean; each absorbed island strictly reduces the component count.
    absorbed = 0
    for _ in range(6):
        absorbed_now = _remove_small(labels, width, height, min_area, colour_count)
        absorbed += absorbed_now
        if not absorbed_now:
            break

    write_indexed_png(target, width, height, labels, palette)

    counts = [0] * colour_count
    for label in labels:
        counts[label] += 1
    total = width * height
    stats = {
        "size": (width, height),
        "target": target,
        "bytes": target.stat().st_size,
        "colours": {
            name: (count, count * 100.0 / total)
            for (name, _rgb), count in zip(palette, counts)
        },
        "source_colours": len(histogram),
        "fringe_pixels": fringe,
        "absorbed": absorbed,
    }
    if not quiet:
        _report(stats)
    return stats


def _report(stats: dict[str, object]) -> None:
    width, height = stats["size"]
    print(f"source  {stats['source_colours']} distinct colours -> {width}x{height}")
    print(f"target  {stats['target']}  ({stats['bytes'] / 1024:.1f} KiB)")
    for name, (count, share) in stats["colours"].items():
        print(f"  {name:6s} {count:9d}  {share:6.2f}%")
    print(f"  fringe {stats['fringe_pixels']} px reassigned, {stats['absorbed']} specks absorbed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Snap the side-view PNG onto a flat palette.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--palette", choices=sorted(PALETTES), default="flat")
    parser.add_argument("--min-area", type=int, default=12)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    target = args.target
    if target is None:
        target = DEFAULT_TARGET if args.palette == "flat" else DEFAULT_SOURCE.with_name(
            f"ellia-sideview-{args.palette}.png"
        )

    flatten(
        args.source,
        target,
        palette_name=args.palette,
        min_area=args.min_area,
        quiet=args.quiet,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
