#!/usr/bin/env python3
"""Redraw assets/mirror-26/ellia-sideview.png as a flat-colour SVG.

The illustration is flat-shaded: paper white, two greys (cape), near-black ink
and one crimson accent.  This tool reconstructs it as clean vector art instead
of embedding the bitmap:

1. decode the PNG with the standard library (no Pillow/numpy),
2. classify every pixel against the five sampled palette colours,
3. drop anti-aliasing fringes from the two grey layers (they would otherwise
   turn every black/white edge into a thin grey outline) and absorb tiny
   classification islands (paper dots in the hair, ink specks in the cape),
4. trace the pixel-exact outline of every layer (outer contours and holes),
5. smooth each outline with Taubin lambda/mu filtering, which removes the
   1 px staircase without collapsing the drawing's proportions,
6. simplify (RDP), optionally smooth the vertices, then approximate with cubic
   Béziers (Schneider's fitting algorithm) - with handle clamping and an
   out-of-bounds guard so a curve can never bow into a long spike,
7. write a layered SVG next to the PNG.

The goal is flowing vector lines, not a pixel-perfect trace: `--flow` controls
how strongly the raster steps are washed out.

Tracing only needs the standard library.  ``--render``/``--diff`` additionally
use Playwright + Chrome Beta (already available in the repository's .venv) to
rasterise the result and report per-layer agreement.

Usage (from the repository root):

    .\\.venv\\Scripts\\python.exe gamejam\\tools\\trace_sideview.py
    .\\.venv\\Scripts\\python.exe gamejam\\tools\\trace_sideview.py --render .dsh/ellia-preview.png --diff .dsh/ellia-diff.png

The defaults (``--epsilon 0.65 --tolerance 0.75 --smoothing 2 --stroke 0.3``)
are tuned for this drawing.  The 0.3 px same-colour stroke closes sub-pixel
seams between the stacked flat layers.

The source's soft crimson shadow under the ribbon has no palette entry of its
own; it is reproduced as a thinner/darker-looking boundary in the red layer
rather than as an extra gradient.

The script is intentionally tied to this artwork's palette and layer order; it
is the redraw tool for mirror-26, not a general-purpose tracer.
"""

from __future__ import annotations

import argparse
import math
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "assets" / "mirror-26" / "ellia-sideview.png"
DEFAULT_TARGET = DEFAULT_SOURCE.with_suffix(".svg")

# Palette sampled from the source (exact mode colours of each flat region).
PAPER = 0
SHADE = 1
VEIL = 2
INK = 3
ACCENT = 4
PALETTE = (
    ("paper", (254, 254, 254)),
    ("shade", (126, 126, 126)),
    ("veil", (145, 145, 145)),
    ("ink", (15, 15, 14)),
    ("accent", (138, 2, 17)),
)
# Paper is a full-canvas rect; the remaining layers are painted in this order.
LAYER_ORDER = (SHADE, VEIL, INK, ACCENT)
# The two grey cape layers are the only ones that need fringe cleanup.
GREY_LAYERS = (SHADE, VEIL)

BIT_TABLES = []
for _index in range(len(PALETTE)):
    _table = bytearray(b"0" * 256)
    _table[_index] = ord("1")
    BIT_TABLES.append(bytes(_table))

DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))  # right, down, left, up


# --------------------------------------------------------------------------
# PNG input / output
# --------------------------------------------------------------------------


def read_png(path: Path) -> tuple[int, int, bytearray]:
    """Decode an 8-bit PNG into tightly packed RGB bytes."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG file")

    pos = 8
    idat = bytearray()
    width = height = depth = colour = interlace = 0
    palette: list[tuple[int, int, int]] = []
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, depth, colour, _comp, _filter, interlace = struct.unpack(
                ">IIBBBBB", chunk
            )
        elif kind == b"PLTE":
            palette = [
                (chunk[i], chunk[i + 1], chunk[i + 2])
                for i in range(0, len(chunk), 3)
            ]
        elif kind == b"IDAT":
            idat += chunk
        elif kind == b"IEND":
            break

    if depth != 8 or interlace != 0:
        raise ValueError(f"{path}: only 8-bit non-interlaced PNGs are supported")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[colour]
    stride = width * channels
    raw = zlib.decompress(bytes(idat))
    pixels = bytearray(width * height * 3)
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

        base = y * width * 3
        if colour == 2:
            pixels[base:base + stride] = line
        elif colour == 6:
            for x in range(width):
                alpha = line[x * 4 + 3]
                for channel in range(3):
                    value = line[x * 4 + channel]
                    pixels[base + x * 3 + channel] = (value * alpha + 255 * (255 - alpha)) // 255
        elif colour == 0:
            for x in range(width):
                value = line[x]
                pixels[base + x * 3:base + x * 3 + 3] = bytes((value, value, value))
        elif colour == 4:
            for x in range(width):
                value = line[x * 2]
                alpha = line[x * 2 + 1]
                value = (value * alpha + 255 * (255 - alpha)) // 255
                pixels[base + x * 3:base + x * 3 + 3] = bytes((value, value, value))
        elif colour == 3:
            for x in range(width):
                r, g, b = palette[line[x]]
                pixels[base + x * 3:base + x * 3 + 3] = bytes((r, g, b))
        else:  # pragma: no cover - guarded by the channel map above
            raise ValueError(f"{path}: unsupported colour type {colour}")
    return width, height, pixels


def write_rgb_png(path: Path, width: int, height: int, pixels: bytes | bytearray) -> None:
    """Write tightly packed RGB bytes as a PNG."""
    stride = width * 3
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += pixels[y * stride:(y + 1) * stride]
    compressed = zlib.compress(bytes(raw), 6)

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = struct.pack(">I", len(payload)) + kind + payload
        return body + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )


# --------------------------------------------------------------------------
# Colour classification
# --------------------------------------------------------------------------


def _is_accent(r: int, g: int, b: int) -> bool:
    """Crimson, including its anti-aliasing towards paper and ink."""
    return r - max(g, b) >= 30 and r >= 70


def _nearest(r: int, g: int, b: int, indices: tuple[int, ...]) -> int:
    best = indices[0]
    best_distance = None
    for index in indices:
        pr, pg, pb = PALETTE[index][1]
        dr = r - pr
        dg = g - pg
        db = b - pb
        # Weight green the most, red the least: the customary quick approximation.
        distance = 2 * dr * dr + 4 * dg * dg + 3 * db * db
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best = index
    return best


def build_lut(indices: tuple[int, ...], accept_accent: bool) -> bytes:
    """Map a 15-bit RGB cube to the nearest palette index."""
    lut = bytearray(1 << 15)
    for key in range(1 << 15):
        r = ((key >> 10) & 31) * 8 + 4
        g = ((key >> 5) & 31) * 8 + 4
        b = (key & 31) * 8 + 4
        if accept_accent and _is_accent(r, g, b):
            lut[key] = ACCENT
        else:
            lut[key] = _nearest(r, g, b, indices)
    return bytes(lut)


def classify(width: int, height: int, pixels: bytearray) -> bytearray:
    lut = build_lut((PAPER, SHADE, VEIL, INK), accept_accent=True)
    labels = bytearray(width * height)
    source = pixels
    for index in range(width * height):
        offset = index * 3
        key = ((source[offset] >> 3) << 10) | ((source[offset + 1] >> 3) << 5) | (source[offset + 2] >> 3)
        labels[index] = lut[key]
    return labels


# --------------------------------------------------------------------------
# Bit-plane helpers
# --------------------------------------------------------------------------


def label_rows(labels: bytearray, width: int, height: int, layer: int) -> list[int]:
    """Turn one label layer into a list of row bitmasks (bit x = pixel x)."""
    rows: list[int] = []
    table = BIT_TABLES[layer]
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


def _assign_removed_pixels(
    rows: list[list[int]], labels: bytearray, width: int, height: int, layer: int
) -> None:
    """Hand removed grey pixels back to the strongest non-grey neighbour.

    Colour distance alone creates isolated 1 px ink dots along every anti-
    aliased edge (the fringe straddles the paper/ink threshold).  Looking at
    the neighbouring labels instead keeps the fringe attached to whichever
    region it borders, which avoids both dots and paper gaps.
    """
    opened = _dilate3(_erode3(rows[layer], width), width)
    for y in range(height):
        removed = rows[layer][y] & ~opened[y]
        if not removed:
            continue
        additions = [0] * len(PALETTE)
        bits = removed
        while bits:
            lowest = bits & -bits
            x = lowest.bit_length() - 1
            bits ^= lowest
            counts = [0] * len(PALETTE)
            for ny in range(max(0, y - 1), min(height, y + 2)):
                base = ny * width
                for nx in range(max(0, x - 1), min(width, x + 2)):
                    if nx == x and ny == y:
                        continue
                    neighbour = labels[base + nx]
                    if neighbour in GREY_LAYERS:
                        continue
                    counts[neighbour] += 1
            best = PAPER
            best_count = 0
            for index, count in enumerate(counts):
                if count > best_count:
                    best_count = count
                    best = index
            additions[best] |= lowest
        rows[layer][y] = opened[y]
        for index, addition in enumerate(additions):
            if addition and index != layer:
                rows[index][y] |= addition


def remove_small_labels(
    labels: bytearray, width: int, height: int, min_area: int
) -> int:
    """Absorb tiny classification islands into their surroundings.

    Anti-aliasing and the soft ribbon shadow leave single-pixel paper dots in
    the hair and ink specks in the cape.  At vector scale those become visible
    notches, so components smaller than `min_area` take the majority label of
    their four-neighbourhood.  Returns the number of absorbed components.
    """
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
        counts = [0] * len(PALETTE)
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
# Contour tracing
# --------------------------------------------------------------------------


def _bit(padded: list[int], x: int, y: int) -> int:
    return (padded[y + 2] >> (x + 2)) & 1


def _next_direction(padded: list[int], vx: int, vy: int, incoming: int) -> int:
    """Follow the boundary keeping the filled area on the right."""
    for step in (1, 0, 3, 2):  # right turn, straight, left turn, reverse
        direction = (incoming + step) % 4
        if direction == 0:
            if _bit(padded, vx, vy) and not _bit(padded, vx, vy - 1):
                return direction
        elif direction == 1:
            if _bit(padded, vx - 1, vy) and not _bit(padded, vx, vy):
                return direction
        elif direction == 2:
            if _bit(padded, vx - 1, vy - 1) and not _bit(padded, vx - 1, vy):
                return direction
        else:
            if _bit(padded, vx, vy - 1) and not _bit(padded, vx - 1, vy - 1):
                return direction
    raise RuntimeError(f"open contour at {vx},{vy} (direction {incoming})")


def _walk(
    padded: list[int],
    width: int,
    height: int,
    start_vertex: int,
    start_direction: int,
    visited: set[int],
) -> list[tuple[int, int]]:
    span = width + 1
    points: list[tuple[int, int]] = []
    vertex = start_vertex
    direction = start_direction
    while True:
        visited.add(vertex * 4 + direction)
        vy, vx = divmod(vertex, span)
        points.append((vx, vy))
        step_x, step_y = DIRECTIONS[direction]
        next_x = vx + step_x
        next_y = vy + step_y
        next_direction = _next_direction(padded, next_x, next_y, direction)
        vertex = next_y * span + next_x
        direction = next_direction
        if vertex == start_vertex and direction == start_direction:
            break
    return points


def trace_loops(rows: list[int], width: int, height: int) -> list[list[tuple[int, int]]]:
    """Return every closed crack outline of a bit-plane layer."""
    padded = [0, 0] + [row << 2 for row in rows] + [0, 0]
    full = (1 << width) - 1
    span = width + 1
    visited: set[int] = set()
    loops: list[list[tuple[int, int]]] = []

    for y in range(height):
        row = rows[y]
        if not row:
            continue
        above = rows[y - 1] if y else 0
        below = rows[y + 1] if y + 1 < height else 0

        starts: list[tuple[int, int]] = []
        # (mask, direction, vertex offset) for each boundary pixel edge.
        for mask, direction, dx, dy in (
            (row & ~above, 0, 0, 0),
            (row & ~below, 2, 1, 1),
            (row & ~((row << 1) & full), 3, 0, 1),
            (row & ~(row >> 1), 1, 1, 0),
        ):
            bits = mask
            while bits:
                lowest = bits & -bits
                x = lowest.bit_length() - 1
                bits ^= lowest
                starts.append(((y + dy) * span + (x + dx), direction))

        for vertex, direction in starts:
            if vertex * 4 + direction in visited:
                continue
            loops.append(_walk(padded, width, height, vertex, direction, visited))
    return loops


# --------------------------------------------------------------------------
# Simplification and Bézier fitting
# --------------------------------------------------------------------------


def _segment_distance(point, start, end) -> float:
    px, py = point
    ax, ay = start
    bx, by = end
    dx = bx - ax
    dy = by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / length_sq
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _rdp(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        if end <= start + 1:
            continue
        ax, ay = points[start]
        bx, by = points[end]
        best = -1.0
        best_index = -1
        for index in range(start + 1, end):
            distance = _segment_distance(points[index], (ax, ay), (bx, by))
            if distance > best:
                best = distance
                best_index = index
        if best > epsilon:
            keep[best_index] = True
            stack.append((start, best_index))
            stack.append((best_index, end))
    return [points[i] for i in range(len(points)) if keep[i]]


def simplify_ring(points: list[tuple[int, int]], epsilon: float) -> list[tuple[float, float]]:
    if len(points) <= 4:
        return [(float(x), float(y)) for x, y in points]
    closed = [(float(x), float(y)) for x, y in points]
    closed.append(closed[0])
    simplified = _rdp(closed, epsilon)
    simplified.pop()
    if len(simplified) < 3:
        return [(float(x), float(y)) for x, y in points]
    return simplified


def _unit(dx: float, dy: float) -> tuple[float, float]:
    length = math.hypot(dx, dy)
    if length == 0.0:
        return (0.0, 0.0)
    return (dx / length, dy / length)


def _normalise_ring(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    cleaned: list[tuple[float, float]] = []
    for point in points:
        if not cleaned or abs(point[0] - cleaned[-1][0]) > 1e-6 or abs(point[1] - cleaned[-1][1]) > 1e-6:
            cleaned.append(point)
    while len(cleaned) > 1 and abs(cleaned[0][0] - cleaned[-1][0]) < 1e-6 and abs(cleaned[0][1] - cleaned[-1][1]) < 1e-6:
        cleaned.pop()
    return cleaned


def _bezier_point(bez, u: float) -> tuple[float, float]:
    mu = 1.0 - u
    b0 = mu * mu * mu
    b1 = 3.0 * u * mu * mu
    b2 = 3.0 * u * u * mu
    b3 = u * u * u
    return (
        bez[0][0] * b0 + bez[1][0] * b1 + bez[2][0] * b2 + bez[3][0] * b3,
        bez[0][1] * b0 + bez[1][1] * b1 + bez[2][1] * b2 + bez[3][1] * b3,
    )


def _bezier_derivatives(bez, u: float):
    mu = 1.0 - u
    d0 = (bez[1][0] - bez[0][0], bez[1][1] - bez[0][1])
    d1 = (bez[2][0] - bez[1][0], bez[2][1] - bez[1][1])
    d2 = (bez[3][0] - bez[2][0], bez[3][1] - bez[2][1])
    point = (
        3.0 * (mu * mu * d0[0] + 2.0 * mu * u * d1[0] + u * u * d2[0]),
        3.0 * (mu * mu * d0[1] + 2.0 * mu * u * d1[1] + u * u * d2[1]),
    )
    first = (
        6.0 * mu * (d1[0] - d0[0]) + 6.0 * u * (d2[0] - d1[0]),
        6.0 * mu * (d1[1] - d0[1]) + 6.0 * u * (d2[1] - d1[1]),
    )
    second = (
        6.0 * (d2[0] - 2.0 * d1[0] + d0[0]),
        6.0 * (d2[1] - 2.0 * d1[1] + d0[1]),
    )
    return point, first, second


def _chord_length_parameterize(points, first: int, last: int) -> list[float]:
    u = [0.0]
    for index in range(first + 1, last + 1):
        step = math.hypot(
            points[index][0] - points[index - 1][0],
            points[index][1] - points[index - 1][1],
        )
        u.append(u[-1] + step)
    total = u[-1]
    if total <= 0.0:
        return [index / max(len(u) - 1, 1) for index in range(len(u))]
    return [value / total for value in u]


def _generate_bezier(points, first: int, last: int, u, t_hat1, t_hat2):
    p0 = points[first]
    p3 = points[last]
    c00 = c01 = c11 = 0.0
    x0 = x1 = 0.0
    for index, value in enumerate(u):
        mu = 1.0 - value
        b0 = mu * mu * mu
        b1 = 3.0 * value * mu * mu
        b2 = 3.0 * value * value * mu
        b3 = value * value * value
        a1x = t_hat1[0] * b1
        a1y = t_hat1[1] * b1
        a2x = t_hat2[0] * b2
        a2y = t_hat2[1] * b2
        c00 += a1x * a1x + a1y * a1y
        c01 += a1x * a2x + a1y * a2y
        c11 += a2x * a2x + a2y * a2y
        px, py = points[first + index]
        tx = px - (p0[0] * (b0 + b1) + p3[0] * (b2 + b3))
        ty = py - (p0[1] * (b0 + b1) + p3[1] * (b2 + b3))
        x0 += a1x * tx + a1y * ty
        x1 += a2x * tx + a2y * ty
    determinant = c00 * c11 - c01 * c01
    alpha1 = alpha2 = 0.0
    if abs(determinant) > 1e-12:
        alpha1 = (x0 * c11 - x1 * c01) / determinant
        alpha2 = (c00 * x1 - c01 * x0) / determinant
    chord = math.hypot(p3[0] - p0[0], p3[1] - p0[1])
    # A least-squares fit can hand back enormous tangents when the run is
    # nearly straight or has a hairpin; unclamped, the cubic bows far outside
    # the drawing and leaves a long thin spike.  Cap the handle length.
    limit = chord * 0.62
    if (
        not math.isfinite(alpha1)
        or not math.isfinite(alpha2)
        or alpha1 < 1e-6
        or alpha2 < 1e-6
        or alpha1 > limit
        or alpha2 > limit
    ):
        alpha1 = alpha2 = chord / 3.0
    return (
        p0,
        (p0[0] + t_hat1[0] * alpha1, p0[1] + t_hat1[1] * alpha1),
        (p3[0] + t_hat2[0] * alpha2, p3[1] + t_hat2[1] * alpha2),
        p3,
    )


def _reparameterize(points, first: int, last: int, u, bez) -> list[float]:
    out = list(u)
    for index in range(1, len(u) - 1):
        px, py = points[first + index]
        point, first_derivative, second_derivative = _bezier_derivatives(bez, u[index])
        dx = point[0] - px
        dy = point[1] - py
        numerator = dx * first_derivative[0] + dy * first_derivative[1]
        denominator = (
            first_derivative[0] * first_derivative[0]
            + first_derivative[1] * first_derivative[1]
            + dx * second_derivative[0]
            + dy * second_derivative[1]
        )
        if abs(denominator) > 1e-12:
            out[index] = min(1.0, max(0.0, u[index] - numerator / denominator))
    for index in range(1, len(out)):
        if out[index] <= out[index - 1]:
            out[index] = min(1.0, out[index - 1] + 1e-6)
    return out


def _compute_max_error(points, first: int, last: int, bez, u) -> tuple[float, int]:
    maximum = 0.0
    split = (first + last) // 2
    for offset in range(1, last - first):
        point = _bezier_point(bez, u[offset])
        dx = point[0] - points[first + offset][0]
        dy = point[1] - points[first + offset][1]
        distance = dx * dx + dy * dy
        if distance >= maximum:
            maximum = distance
            split = first + offset
    return math.sqrt(maximum), split


def _compute_center_tangent(points, split: int) -> tuple[float, float]:
    first = _unit(points[split - 1][0] - points[split][0], points[split - 1][1] - points[split][1])
    second = _unit(points[split][0] - points[split + 1][0], points[split][1] - points[split + 1][1])
    tangent = _unit(first[0] + second[0], first[1] + second[1])
    return tangent if tangent != (0.0, 0.0) else first


def _curve_escapes(points, first: int, last: int, bez, margin: float) -> bool:
    """True when the fitted curve bows far outside the run it approximates."""
    xs = [points[index][0] for index in range(first, last + 1)]
    ys = [points[index][1] for index in range(first, last + 1)]
    min_x = min(xs) - margin
    max_x = max(xs) + margin
    min_y = min(ys) - margin
    max_y = max(ys) + margin
    for step in range(1, 12):
        point = _bezier_point(bez, step / 12.0)
        if not (min_x <= point[0] <= max_x and min_y <= point[1] <= max_y):
            return True
    return False


def _straight_segment(points, first: int, last: int):
    p0 = points[first]
    p3 = points[last]
    return (
        p0,
        (p0[0] + (p3[0] - p0[0]) / 3.0, p0[1] + (p3[1] - p0[1]) / 3.0),
        (p0[0] + 2.0 * (p3[0] - p0[0]) / 3.0, p0[1] + 2.0 * (p3[1] - p0[1]) / 3.0),
        p3,
    )


def _fit_cubic(points, first: int, last: int, t_hat1, t_hat2, tolerance: float, depth: int):
    count = last - first + 1
    if count == 2:
        distance = math.hypot(
            points[last][0] - points[first][0], points[last][1] - points[first][1]
        ) / 3.0
        p0 = points[first]
        p3 = points[last]
        return [(
            p0,
            (p0[0] + t_hat1[0] * distance, p0[1] + t_hat1[1] * distance),
            (p3[0] + t_hat2[0] * distance, p3[1] + t_hat2[1] * distance),
            p3,
        )]
    margin = max(4.0, tolerance * 4.0)
    u = _chord_length_parameterize(points, first, last)
    bez = _generate_bezier(points, first, last, u, t_hat1, t_hat2)
    error, split = _compute_max_error(points, first, last, bez, u)
    escapes = _curve_escapes(points, first, last, bez, margin)
    if error < tolerance and not escapes:
        return [bez]
    if depth < 24:
        for _ in range(4):
            u = _reparameterize(points, first, last, u, bez)
            bez = _generate_bezier(points, first, last, u, t_hat1, t_hat2)
            error, split = _compute_max_error(points, first, last, bez, u)
            escapes = _curve_escapes(points, first, last, bez, margin)
            if error < tolerance and not escapes:
                return [bez]
    if split <= first + 1 or split >= last - 1:
        # Keep the recursion balanced: a pathological maximum right next to an
        # endpoint would otherwise nibble one point per level and exhaust the
        # depth budget with a long run still unsplit.
        split = (first + last) // 2
    if split <= first:
        split = first + 1
    elif split >= last:
        split = last - 1
    if depth > 30:
        # Never replace a long run with one chord (that is what sliced the top
        # of the head); fall back to the run's own polyline instead.
        return [
            _straight_segment(points, index, index + 1)
            for index in range(first, last)
        ]
    center = _compute_center_tangent(points, split)
    return _fit_cubic(
        points, first, split, t_hat1, center, tolerance, depth + 1
    ) + _fit_cubic(
        points, split, last, (-center[0], -center[1]), t_hat2, tolerance, depth + 1
    )


def _fit_open(points, t_hat1, t_hat2, tolerance: float):
    if len(points) < 2:
        return []
    return _fit_cubic(points, 0, len(points) - 1, t_hat1, t_hat2, tolerance, 0)


def _detect_corners(points: list[tuple[float, float]], corner_degrees: float) -> list[int]:
    count = len(points)
    threshold = math.cos(math.radians(corner_degrees))
    corners = []
    for index in range(count):
        previous = points[index - 1]
        current = points[index]
        following = points[(index + 1) % count]
        ax = current[0] - previous[0]
        ay = current[1] - previous[1]
        bx = following[0] - current[0]
        by = following[1] - current[1]
        length_a = math.hypot(ax, ay)
        length_b = math.hypot(bx, by)
        if length_a < 1e-9 or length_b < 1e-9:
            continue
        dot = (ax * bx + ay * by) / (length_a * length_b)
        if dot < threshold:
            corners.append(index)
    return corners


def fit_closed_ring(
    points: list[tuple[float, float]], tolerance: float, corner_degrees: float
) -> list[tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]]:
    """Approximate a closed outline with cubic Béziers (Schneider's method).

    Sharp corners split the ring into open runs; every run is fitted with an
    approximating curve instead of interpolating the noisy pixel outline, which
    is what removes the stair-step wobble from the result.
    """
    points = _normalise_ring(points)
    count = len(points)
    if count < 3:
        return []
    corners = _detect_corners(points, corner_degrees)
    if not corners:
        tangent = _unit(points[1][0] - points[-1][0], points[1][1] - points[-1][1])
        run = points + [points[0]]
        return _fit_open(run, tangent, (-tangent[0], -tangent[1]), tolerance)

    corners.sort()
    segments = []
    for index, start in enumerate(corners):
        end = corners[(index + 1) % len(corners)]
        if end > start:
            run = points[start:end + 1]
        else:
            run = points[start:] + points[:end + 1]
        if len(run) < 2:
            continue
        t_hat1 = _unit(run[1][0] - run[0][0], run[1][1] - run[0][1])
        t_hat2 = _unit(run[-2][0] - run[-1][0], run[-2][1] - run[-1][1])
        segments.extend(_fit_open(run, t_hat1, t_hat2, tolerance))
    return segments


def _fmt(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def ring_to_path_with_count(
    points: list[tuple[float, float]], tolerance: float, corner_degrees: float
) -> tuple[str, int]:
    points = _normalise_ring(points)
    if len(points) < 3:
        return "", 0
    segments = fit_closed_ring(points, tolerance, corner_degrees)
    if not segments:
        return "", 0
    start_x, start_y = segments[0][0]
    commands = [f"M{_fmt(start_x)} {_fmt(start_y)}"]
    for _start, control1, control2, end in segments:
        commands.append(
            "C"
            f"{_fmt(control1[0])} {_fmt(control1[1])} "
            f"{_fmt(control2[0])} {_fmt(control2[1])} "
            f"{_fmt(end[0])} {_fmt(end[1])}"
        )
    commands.append("Z")
    return "".join(commands), len(segments)


# --------------------------------------------------------------------------
# SVG assembly
# --------------------------------------------------------------------------


def _ring_metrics(points: list[tuple[int, int]]) -> tuple[float, float]:
    area = 0.0
    for index in range(len(points)):
        x0, y0 = points[index]
        x1, y1 = points[(index + 1) % len(points)]
        area += x0 * y1 - x1 * y0
    return abs(area) / 2.0, float(len(points))


def _smooth_ring(
    points: list[tuple[float, float]], corner_degrees: float, iterations: int
) -> list[tuple[float, float]]:
    """Nudge non-corner vertices towards their neighbours to drop stair noise."""
    if iterations <= 0 or len(points) < 5:
        return points
    corners = set(_detect_corners(points, corner_degrees))
    current = list(points)
    count = len(current)
    for _ in range(iterations):
        following = []
        for index, point in enumerate(current):
            if index in corners:
                following.append(point)
                continue
            previous = current[index - 1]
            target = current[(index + 1) % count]
            following.append((
                0.5 * point[0] + 0.25 * (previous[0] + target[0]),
                0.5 * point[1] + 0.25 * (previous[1] + target[1]),
            ))
        current = following
    return current


def _taubin(points: list[tuple[int, int]], iterations: int) -> list[tuple[float, float]]:
    """Smooth the pixel outline without collapsing it (Taubin lambda/mu).

    A plain blur would shrink every curve; alternating a positive and a
    negative Laplacian step removes the 1 px staircase while keeping the
    drawing's proportions.  This is the pass that turns traced pixels into
    flowing lines.
    """
    current = [(float(x), float(y)) for x, y in points]
    count = len(current)
    if count < 3 or iterations <= 0:
        return current
    lam = 0.5
    mu = -0.53
    for _ in range(iterations):
        for factor in (lam, mu):
            following = []
            for index, (x, y) in enumerate(current):
                ax = 0.5 * (current[index - 1][0] + current[(index + 1) % count][0])
                ay = 0.5 * (current[index - 1][1] + current[(index + 1) % count][1])
                following.append((x + factor * (ax - x), y + factor * (ay - y)))
            current = following
    return current


def _ring_path(
    points: list[tuple[int, int]],
    epsilon: float,
    tolerance: float,
    corner_degrees: float,
    smoothing: int,
    flow: int,
    stats: dict[str, int],
) -> str:
    """Smooth one ring and turn it into cubic Bézier segments.

    Specks below ~18 px are dropped; small details and thin shapes get their
    own smoothing budget so they follow the same flowing style as the large
    silhouettes instead of keeping their pixel staircase.
    """
    area, perimeter = _ring_metrics(points)
    thinness = 2.0 * area / perimeter if perimeter else 0.0
    stats["points"] += len(points)
    if area < 18.0 or perimeter < 16.0:
        stats["skipped_rings"] += 1
        return ""
    if area < 160.0 and perimeter < 220.0:
        # Small features (eye highlight, pin details, cape highlights) still
        # need soft curves; only the sub-20 px specks are dropped above.
        stats["detail_rings"] += 1
        smoothed = _taubin(points, 10)
        simplified = simplify_ring(smoothed, min(epsilon, 0.2))
        stats["simplified"] += len(simplified)
        path, segment_count = ring_to_path_with_count(
            simplified, min(tolerance, 0.45), corner_degrees
        )
        stats["segments"] += segment_count
        return path
    if thinness < 2.35:
        stats["thin_rings"] += 1
        smoothed = _taubin(points, 8)
        simplified = simplify_ring(smoothed, min(epsilon, 0.25))
        stats["simplified"] += len(simplified)
        path, segment_count = ring_to_path_with_count(
            simplified, min(tolerance, 0.45), corner_degrees
        )
        stats["segments"] += segment_count
        return path
    passes = flow
    if thinness < 4.0:
        passes = min(passes, 6)
    elif thinness < 8.0:
        passes = min(passes, 10)
    smoothed = _taubin(points, passes)
    simplified = simplify_ring(smoothed, epsilon)
    simplified = _smooth_ring(simplified, corner_degrees, smoothing)
    stats["simplified"] += len(simplified)
    path, segment_count = ring_to_path_with_count(simplified, tolerance, corner_degrees)
    stats["segments"] += segment_count
    return path


def build_svg(
    width: int,
    height: int,
    layer_loops: dict[int, list[list[tuple[int, int]]]],
    *,
    epsilon: float,
    tolerance: float,
    corner_degrees: float,
    smoothing: int,
    flow: int,
    stroke_width: float,
    source_name: str,
) -> tuple[str, dict[str, int]]:
    stats = {
        "rings": 0,
        "points": 0,
        "simplified": 0,
        "segments": 0,
        "detail_rings": 0,
        "thin_rings": 0,
        "skipped_rings": 0,
        "bytes": 0,
    }
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="ellia-title">'
        ),
        "  <title id=\"ellia-title\">ELLIA — side view</title>",
        (
            "  <desc>Flat-colour vector redraw of "
            f"{source_name}, traced from the flat-shade palette of the source bitmap.</desc>"
        ),
        f'  <rect width="{width}" height="{height}" fill="#fefefe"/>',
    ]
    for layer in LAYER_ORDER:
        loops = layer_loops[layer]
        name, (r, g, b) = PALETTE[layer]
        colour = f"#{r:02x}{g:02x}{b:02x}"
        subpaths = []
        # Cloth can take much more smoothing than the figure: the grey cape is
        # one broad shape, while the ink layer carries the face, boots and hair
        # tips that should keep their character.
        layer_flow = flow * 2 if layer in GREY_LAYERS else flow
        for points in loops:
            stats["rings"] += 1
            path = _ring_path(
                points, epsilon, tolerance, corner_degrees, smoothing, layer_flow, stats
            )
            if path:
                subpaths.append(path)
        if not subpaths:
            continue
        attributes = (
            f'fill="{colour}" fill-rule="evenodd" stroke="{colour}" '
            f'stroke-width="{stroke_width}" stroke-linejoin="round" stroke-linecap="round"'
            if stroke_width > 0
            else f'fill="{colour}" fill-rule="evenodd"'
        )
        parts.append(f'  <g id="{name}">')
        parts.append(f'    <path {attributes} d="{"".join(subpaths)}"/>')
        parts.append("  </g>")
    parts.append("</svg>")
    svg = "\n".join(parts) + "\n"
    stats["bytes"] = len(svg.encode("utf-8"))
    return svg, stats


# --------------------------------------------------------------------------
# Optional: rasterise and compare
# --------------------------------------------------------------------------


def render_svg_preview(svg_markup: str, target: Path, width: int, height: int) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:  # pragma: no cover - environment dependent
        raise SystemExit("Playwright is required for --render; install it into .venv") from error

    html = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<style>html,body{margin:0;padding:0;background:#fff}"
        "svg{display:block;width:100vw;height:auto}</style></head><body>"
        f"{svg_markup}</body></html>"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = None
        errors = []
        for kwargs in ({"channel": "chrome-beta"}, {"channel": "chrome"}, {}):
            try:
                browser = playwright.chromium.launch(headless=True, **kwargs)
                break
            except Exception as error:  # noqa: BLE001 - probe installed browsers
                errors.append(f"{kwargs}: {error}")
        if browser is None:  # pragma: no cover - environment dependent
            raise SystemExit("No Chromium available for --render:\n" + "\n".join(errors))
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
        page.set_content(html, wait_until="load")
        page.wait_for_timeout(100)
        page.screenshot(path=str(target))
        browser.close()


def compare_render(
    source_pixels: bytearray,
    source_labels: bytearray,
    render_path: Path,
    width: int,
    height: int,
    diff_path: Path | None,
) -> dict[str, float]:
    render_width, render_height, render_pixels = read_png(render_path)
    if (render_width, render_height) != (width, height):
        raise SystemExit(
            f"render is {render_width}x{render_height}, expected {width}x{height}"
        )
    render_labels = classify(width, height, render_pixels)

    counts = [0] * len(PALETTE)
    intersections = [0] * len(PALETTE)
    unions = [0] * len(PALETTE)
    matches = 0
    for index in range(width * height):
        left = source_labels[index]
        right = render_labels[index]
        counts[left] += 1
        if left == right:
            matches += 1
            intersections[left] += 1
            unions[left] += 1
        else:
            unions[left] += 1
            unions[right] += 1
    report = {"agreement": matches / (width * height)}
    for index, (name, _colour) in enumerate(PALETTE):
        report[name] = intersections[index] / unions[index] if unions[index] else 1.0
        report[f"{name}_source"] = counts[index]

    if diff_path is not None:
        diff = bytearray(width * height * 3)
        for index in range(width * height):
            source_offset = index * 3
            r = source_pixels[source_offset]
            g = source_pixels[source_offset + 1]
            b = source_pixels[source_offset + 2]
            if source_labels[index] != render_labels[index]:
                r, g, b = 255, 0, 170
            else:
                r = (r * 45 + 255 * 55) // 100
                g = (g * 45 + 255 * 55) // 100
                b = (b * 45 + 255 * 55) // 100
            diff[source_offset] = r
            diff[source_offset + 1] = g
            diff[source_offset + 2] = b
        write_rgb_png(diff_path, width, height, diff)
    return report


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def trace(
    source: Path,
    target: Path,
    *,
    epsilon: float,
    tolerance: float,
    corner_degrees: float,
    smoothing: int,
    flow: int,
    stroke_width: float,
    render: Path | None,
    diff: Path | None,
) -> dict[str, object]:
    width, height, pixels = read_png(source)
    labels = classify(width, height, pixels)

    rows = [label_rows(labels, width, height, layer) for layer in range(len(PALETTE))]
    for layer in GREY_LAYERS:
        _assign_removed_pixels(rows, labels, width, height, layer)
    # Two passes: the first can itself create a few new tiny islands when it
    # hands a speck back to a neighbouring label.
    remove_small_labels(labels, width, height, min_area=24)
    remove_small_labels(labels, width, height, min_area=24)
    rows = [label_rows(labels, width, height, layer) for layer in range(len(PALETTE))]

    layer_loops = {
        layer: trace_loops(rows[layer], width, height) for layer in LAYER_ORDER
    }
    svg, stats = build_svg(
        width,
        height,
        layer_loops,
        epsilon=epsilon,
        tolerance=tolerance,
        corner_degrees=corner_degrees,
        smoothing=smoothing,
        flow=flow,
        stroke_width=stroke_width,
        source_name=source.name,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(svg, encoding="utf-8")

    result: dict[str, object] = {
        "size": (width, height),
        "target": target,
        "stats": stats,
        "rings": {PALETTE[layer][0]: len(layer_loops[layer]) for layer in LAYER_ORDER},
    }
    if render is not None:
        render_svg_preview(svg, render, width, height)
        report = compare_render(pixels, labels, render, width, height, diff)
        result["report"] = report
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="input PNG")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET, help="output SVG")
    parser.add_argument("--epsilon", type=float, default=0.7, help="outline simplification in pixels")
    parser.add_argument("--tolerance", type=float, default=0.65, help="Bezier fit tolerance in pixels")
    parser.add_argument("--corner-angle", type=float, default=62.0, help="turns sharper than this stay corners")
    parser.add_argument("--smoothing", type=int, default=0, help="extra corner-preserving vertex smoothing passes")
    parser.add_argument("--flow", type=int, default=12, help="Taubin passes for ink/accent; grey cloth uses twice")

    parser.add_argument("--stroke", type=float, default=0.3, help="same-colour seam stroke width (0 disables)")
    parser.add_argument("--render", type=Path, help="rasterise the SVG here for inspection")
    parser.add_argument("--diff", type=Path, help="write a mismatch overlay here (implies --render)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if args.diff is not None and args.render is None:
        args.render = args.diff.with_name(args.diff.stem + "-render.png")

    result = trace(
        args.source,
        args.target,
        epsilon=args.epsilon,
        tolerance=args.tolerance,
        corner_degrees=args.corner_angle,
        smoothing=args.smoothing,
        flow=args.flow,
        stroke_width=args.stroke,
        render=args.render,
        diff=args.diff,
    )
    if not args.quiet:
        width, height = result["size"]
        stats = result["stats"]
        print(f"source      {args.source} ({width}x{height})")
        print(f"svg         {args.target} ({stats['bytes']} bytes)")
        print(
            "rings       "
            + ", ".join(f"{name}:{count}" for name, count in result["rings"].items())
            + f" ({stats['rings']} total)"
        )
        print(
            f"outline     {stats['points']} crack points -> {stats['simplified']} simplified "
            f"({100.0 * stats['simplified'] / max(stats['points'], 1):.1f}%) -> "
            f"{stats['segments']} Bezier segments "
            f"({stats['skipped_rings']} specks dropped, "
            f"{stats['detail_rings']} detail + {stats['thin_rings']} thin rings smoothed)"
        )
        if "report" in result:
            report = result["report"]
            print(f"render      {args.render}")
            print(f"agreement   {report['agreement'] * 100:.2f}% pixels")
            print(
                "layer IoU   "
                + ", ".join(
                    f"{name}:{report[name] * 100:.1f}%"
                    for name, _colour in PALETTE
                )
            )
        if "diff" in result:
            print(f"diff        {args.diff}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:  # pragma: no cover - piping into head
        sys.exit(0)
