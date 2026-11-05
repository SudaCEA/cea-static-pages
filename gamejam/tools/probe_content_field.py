"""Probe the mirror-2610 rising particle field.

Run with the repository's Playwright environment:

    .venv\\Scripts\\python.exe gamejam\\tools\\probe_content_field.py

Requires the local server on http://127.0.0.1:4173. Chrome Beta is the
default because stable Chrome 155 has the known nested-canvas device-pixel
bug. Override with MIRROR_CHANNEL if needed.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/mirror-2610/"
CHANNEL = os.environ.get("MIRROR_CHANNEL", "chrome-beta")
ENABLE_HTML_IN_CANVAS = "--enable-features=CanvasDrawElement"
DISABLE_HTML_IN_CANVAS = "--disable-features=CanvasDrawElement"
SHOT_DIR = Path(__file__).resolve().parents[2] / ".dsh"
PARTICLE_DEFAULT = "#242622"


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def rgb(hex_color):
    value = hex_color.lstrip("#")
    return [int(value[i:i + 2], 16) for i in (0, 2, 4)]


def close_color(actual, expected, tolerance=5):
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected))


def open_page(browser, *, width=1200, height=900, dpr=1, reduced=False, init_script=None):
    context = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=dpr,
        reduced_motion="reduce" if reduced else "no-preference",
        permissions=["clipboard-read", "clipboard-write"],
    )
    page = context.new_page()
    if init_script:
        page.add_init_script(init_script)
    errors = []

    def on_console(msg):
        if msg.type in ("error", "assert"):
            errors.append(f"{msg.type}: {msg.text}")

    page.on("console", on_console)
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    page.goto(URL, wait_until="networkidle")
    page.wait_for_timeout(250)

    question = page.locator("#bootQuestion:not([hidden])")
    if question.count():
        page.locator("#questionActions .primary").click()

    page.wait_for_function("document.getElementById('boot').hidden", timeout=20000)
    return page, context, errors


def wait_field(page, *, require_field=True):
    page.wait_for_function("window.__mirrorHome && window.__mirrorHome.ready", timeout=20000)
    if require_field:
        page.wait_for_function(
            "window.__mirrorHome.field && window.__mirrorHome.field.getState().rendered",
            timeout=20000,
        )
        page.wait_for_timeout(300)
        return page.evaluate("window.__mirrorHome.field.getState()")
    return page.evaluate(
        """() => ({
          ready: window.__mirrorHome.ready,
          mode: window.__mirrorHome.mirror?.mode || null,
          hasField: !!window.__mirrorHome.field,
          canvasHidden: document.getElementById('contentField')?.hidden ?? null,
          artClass: document.getElementById('art')?.className || ''
        })"""
    )


def field_layout(page):
    return page.evaluate(
        """() => {
          const art = document.getElementById('art');
          const canvas = document.getElementById('contentField');
          const cs = canvas ? getComputedStyle(canvas) : null;
          const artRect = art.getBoundingClientRect();
          const canvasRect = canvas.getBoundingClientRect();
          return {
            state: window.__mirrorHome.field.getState(),
            canvasCount: art.querySelectorAll('canvas').length,
            deckCount: art.querySelectorAll('#deck .slide').length,
            text: art.textContent,
            borderWidth: getComputedStyle(art).borderTopWidth,
            ariaHidden: canvas.getAttribute('aria-hidden'),
            drawable: canvas.hasAttribute('drawable'),
            layoutSubtree: canvas.hasAttribute('layoutsubtree'),
            context2d: !!canvas.getContext('2d'),
            contextWebgl2: !!canvas.getContext('webgl2'),
            style: cs ? {
              position: cs.position,
              display: cs.display,
              transform: cs.transform,
              filter: cs.filter,
              opacity: cs.opacity,
              mixBlendMode: cs.mixBlendMode,
              pointerEvents: cs.pointerEvents
            } : null,
            artRect: [artRect.x, artRect.y, artRect.width, artRect.height],
            canvasRect: [canvasRect.x, canvasRect.y, canvasRect.width, canvasRect.height]
          };
        }"""
    )


def sample_screenshot(page, points):
    image = base64.b64encode(page.screenshot(scale="css")).decode("ascii")
    return page.evaluate(
        """async ({ image, points }) => {
          const img = new Image();
          img.src = 'data:image/png;base64,' + image;
          await img.decode();
          const canvas = document.createElement('canvas');
          canvas.width = img.width;
          canvas.height = img.height;
          const ctx = canvas.getContext('2d', { willReadFrequently: true });
          ctx.drawImage(img, 0, 0);
          return points.map(([x, y]) => Array.from(ctx.getImageData(x, y, 1, 1).data));
        }""",
        {"image": image, "points": points},
    )


def sample_patch(page, x, y, width, height, stride=4):
    image = base64.b64encode(page.screenshot(scale="css")).decode("ascii")
    return page.evaluate(
        """async ({ image, x, y, width, height, stride }) => {
          const img = new Image();
          img.src = 'data:image/png;base64,' + image;
          await img.decode();
          const canvas = document.createElement('canvas');
          canvas.width = img.width;
          canvas.height = img.height;
          const ctx = canvas.getContext('2d', { willReadFrequently: true });
          ctx.drawImage(img, 0, 0);
          const data = ctx.getImageData(x, y, width, height).data;
          const pixels = [];
          for (let yy = 0; yy < height; yy += stride) {
            for (let xx = 0; xx < width; xx += stride) {
              const i = (yy * width + xx) * 4;
              pixels.push([data[i], data[i + 1], data[i + 2]]);
            }
          }
          return pixels;
        }""",
        {
            "image": image,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "stride": stride,
        },
    )


def canvas_stats(page):
    return page.evaluate(
        """() => {
          const canvas = document.getElementById('contentField');
          const ctx = canvas.getContext('2d');
          const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
          const histogram = new Map();
          let dark = 0;
          let min = 255;
          let samples = 0;
          for (let y = 0; y < canvas.height; y += 2) {
            for (let x = 0; x < canvas.width; x += 2) {
              const i = (y * canvas.width + x) * 4;
              const r = data[i];
              const g = data[i + 1];
              const b = data[i + 2];
              const value = Math.min(r, g, b);
              if (value < min) min = value;
              if (Math.max(r, g, b) < 230) dark += 1;
              const key = `${r},${g},${b}`;
              histogram.set(key, (histogram.get(key) || 0) + 1);
              samples += 1;
            }
          }
          let mode = '0,0,0';
          let modeCount = 0;
          for (const [key, count] of histogram) {
            if (count > modeCount) {
              mode = key;
              modeCount = count;
            }
          }
          return {
            background: mode.split(',').map(Number),
            backgroundRatio: modeCount / samples,
            dark,
            min,
            width: canvas.width,
            height: canvas.height
          };
        }"""
    )


def canvas_hash(page):
    return page.evaluate(
        """() => {
          const canvas = document.getElementById('contentField');
          const ctx = canvas.getContext('2d');
          const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
          let hash = 2166136261;
          for (let i = 0; i < data.length; i += 12) {
            hash ^= data[i] | (data[i + 1] << 8) | (data[i + 2] << 16);
            hash = Math.imul(hash, 16777619);
          }
          return hash >>> 0;
        }"""
    )


def assert_canvas_contract(page, *, expected_dpr=None):
    layout = field_layout(page)
    state = layout["state"]
    check(layout["canvasCount"] == 1, f"expected exactly one content canvas: {layout}")
    check(layout["deckCount"] == 4, f"expected the slide deck in content: {layout}")
    check(layout["text"].strip() != "", f"content has no deck text: {layout}")
    check(layout["borderWidth"] == "0px", f"content has a CSS border: {layout}")
    check(layout["ariaHidden"] == "true", "content canvas is not aria-hidden")
    check(not layout["drawable"], "content canvas must not be a drawable root")
    check(not layout["layoutSubtree"], "content canvas must not have layoutsubtree")
    check(layout["context2d"], "content canvas does not use a 2D context")
    check(not layout["contextWebgl2"], "content canvas unexpectedly has a WebGL2 context")
    check(layout["style"]["position"] == "absolute", f"canvas position: {layout['style']}")
    check(layout["style"]["display"] == "block", f"canvas display: {layout['style']}")
    check(layout["style"]["transform"] == "none", f"canvas transform: {layout['style']}")
    check(layout["style"]["filter"] == "none", f"canvas filter: {layout['style']}")
    check(layout["style"]["opacity"] == "1", f"canvas opacity: {layout['style']}")
    check(layout["style"]["mixBlendMode"] == "normal", f"canvas blend: {layout['style']}")
    check(layout["style"]["pointerEvents"] == "none", f"canvas pointer events: {layout['style']}")

    art = layout["artRect"]
    canvas_rect = layout["canvasRect"]
    check(abs(art[0] - canvas_rect[0]) <= 1, f"canvas is not aligned with content: {layout}")
    check(abs(art[1] - canvas_rect[1]) <= 1, f"canvas is not aligned with content: {layout}")
    check(abs(art[2] - canvas_rect[2]) <= 1, f"canvas does not fill content: {layout}")
    check(abs(art[3] - canvas_rect[3]) <= 1, f"canvas does not fill content: {layout}")

    dpr = expected_dpr if expected_dpr is not None else min(page.evaluate("devicePixelRatio"), 2)
    check(abs(state["dpr"] - dpr) < 0.001, f"field DPR {state['dpr']} != {dpr}")
    expected_width = round(state["css"]["width"] * dpr)
    expected_height = round(state["css"]["height"] * dpr)
    check(state["canvas"]["width"] == expected_width,
          f"canvas width {state['canvas']['width']} != {expected_width}")
    check(state["canvas"]["height"] == expected_height,
          f"canvas height {state['canvas']['height']} != {expected_height}")
    check(state["count"] >= 24, f"particle pool too small: {state}")
    check(state["particle"]["dprCap"] == 2, f"unexpected DPR cap: {state}")
    return layout


def assert_surface(page):
    state = page.evaluate("window.__mirrorHome.field.getState()")
    stats = canvas_stats(page)
    center = [round(c * 255) for c in state["palette"]["center"]]
    check(close_color(stats["background"], center, 1),
          f"canvas background {stats['background']} != {center}")
    check(stats["backgroundRatio"] > 0.8,
          f"particles cover too much of the surface: {stats}")
    check(stats["dark"] >= 40, f"too few visible particle pixels: {stats}")
    check(stats["min"] < 160, f"particles are not dark enough: {stats}")
    return stats


def assert_content_edges(page, *, tolerance=12):
    check(page.locator("#contentSeam").count() == 0,
          "the DOM seam guard should be removed")
    rect = page.evaluate(
        """() => {
          const r = document.getElementById('art').getBoundingClientRect();
          return { left: r.left, top: r.top, width: r.width, height: r.height };
        }"""
    )
    center = page.evaluate("window.__mirrorHome.field.getState().palette.center")
    expected = [round(c * 255) for c in center]
    y = round(rect["top"] + rect["height"] / 2)
    left = round(rect["left"])
    points = [(left + dx, y) for dx in range(-4, 5)]
    pixels = sample_screenshot(page, points)
    for point, pixel in zip(points, pixels):
        check(close_color(pixel[:3], expected, tolerance),
              f"content edge pixel {point} = {pixel[:3]}, expected {expected}")

    x = round(rect["left"] + rect["width"] / 2)
    top = round(rect["top"])
    points = [(x, top + dy) for dy in range(-4, 5)]
    pixels = sample_screenshot(page, points)
    for point, pixel in zip(points, pixels):
        check(close_color(pixel[:3], expected, tolerance),
              f"content edge pixel {point} = {pixel[:3]}, expected {expected}")

    # The cover's black bottom rule is rendered by the direct 1x mirror pass.
    # If the optional composite path is enabled, the edge skirt carries it.
    if page.evaluate("window.__mirrorHome.mirror.mode") == "webgl":
        detail = page.evaluate(
            "window.__mirrorHome.mirror.getState().renderDetail"
        )
        check(detail["renderScale"] == 1 and detail["contentScale"] == 1,
              f"WebGL default scales are not direct 1x: {detail}")
        bottom = round(rect["top"] + rect["height"])
        bottom_pixel = sample_screenshot(page, [(x, bottom)])[0]
        check(max(bottom_pixel[:3]) < 40,
              f"bottom content edge did not stay dark: {bottom_pixel}")


def assert_particles(page):
    first = page.evaluate("window.__mirrorHome.field.getState()")
    check(first["animating"] is True, "field is not animating after boot")
    check("pointer" not in first and "presence" not in first,
          f"field still exposes pointer state: {first}")
    check(first["count"] >= 24, f"particle pool too small: {first}")

    samples = first["samples"]
    sizes = {round(item["size"], 2) for item in samples}
    alphas = {round(item["alpha"], 2) for item in samples}
    progress = [item["progress"] for item in samples]
    check(len(sizes) > 1, f"particle sizes are not randomized: {samples}")
    check(len(alphas) > 1, f"particle depths are not randomized: {samples}")
    check(max(progress) - min(progress) > 0.2,
          f"particles are not distributed through their lifetime: {samples}")

    first_hash = canvas_hash(page)
    page.wait_for_timeout(1000)
    second = page.evaluate("window.__mirrorHome.field.getState()")
    matched = {
        item["id"]: item for item in second["samples"]
    }
    moved = [
        sample for sample in samples
        if sample["id"] in matched and
        matched[sample["id"]]["y"] < sample["y"] - 2
    ]
    check(len(moved) >= 2, f"particles did not rise: {samples} -> {second['samples']}")
    check(second["frames"] > first["frames"] + 10,
          f"field frames did not advance: {first['frames']} -> {second['frames']}")
    check(second["time"] > first["time"], "field time did not advance")
    second_hash = canvas_hash(page)
    check(second_hash != first_hash, "particle field pixels did not change")

    # Mouse stillness and leaving the content must not pause the loop.
    page.mouse.move(600, 450)
    page.wait_for_timeout(900)
    still = page.evaluate("window.__mirrorHome.field.getState()")
    page.mouse.move(80, 80)
    page.wait_for_timeout(1200)
    outside = page.evaluate("window.__mirrorHome.field.getState()")
    check(still["animating"] is True, f"field paused while the pointer was still: {still}")
    check(outside["animating"] is True, f"field paused after the pointer left: {outside}")
    check(outside["frames"] > still["frames"] + 10,
          f"field frames stalled outside the content: {still['frames']} -> {outside['frames']}")

    return {
        "count": first["count"],
        "moved": len(moved),
        "frames": [first["frames"], second["frames"], outside["frames"]],
    }


def assert_live_capture(page):
    rect = page.evaluate(
        """() => {
          const r = document.getElementById('art').getBoundingClientRect();
          return { left: r.left, top: r.top, width: r.width, height: r.height };
        }"""
    )
    x = max(0, round(rect["left"] - 100))
    width = max(8, round(rect["left"] - 4) - x)
    y = max(0, round(rect["top"] + 40))
    height = max(8, round(rect["height"] - 80))
    before = sample_patch(page, x, y, width, height, stride=3)
    page.evaluate(
        """() => {
          const el = document.getElementById('tuneParticle');
          el.value = '#d84a33';
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }"""
    )
    page.wait_for_timeout(1200)
    after = sample_patch(page, x, y, width, height, stride=3)
    page.evaluate(
        """() => {
          const el = document.getElementById('tuneParticle');
          el.value = '#242622';
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }"""
    )
    page.wait_for_timeout(300)

    deltas = [
        max(abs(a - b) for a, b in zip(before_pixel, after_pixel))
        for before_pixel, after_pixel in zip(before, after)
    ]
    delta = max(deltas)
    changed = sum(1 for value in deltas if value >= 4)
    check(delta >= 5 and changed >= 4,
          f"mirrored band did not follow the canvas: delta={delta}, changed={changed}")
    return {"points": len(deltas), "delta": delta, "changed": changed}


def open_tuner(page):
    if page.locator("#tuneBody").is_hidden():
        page.locator("#tuneToggle").click()
        page.wait_for_timeout(120)


def close_tuner(page):
    if not page.locator("#tuneBody").is_hidden():
        page.locator("#tuneToggle").click()
        page.wait_for_timeout(120)


def assert_tuning(page):
    open_tuner(page)
    page.evaluate(
        """() => {
          const set = (id, value) => {
            const el = document.getElementById(id);
            el.value = value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
          };
          set('tuneParticle', '#334455');
          set('tuneCenter', '#f8f8f4');
        }"""
    )
    page.wait_for_timeout(300)
    state = page.evaluate("window.__mirrorHome.field.getState()")
    check(close_color([round(c * 255) for c in state["palette"]["particle"]], rgb("#334455"), 1),
          f"particle colour not applied: {state}")
    check(close_color([round(c * 255) for c in state["palette"]["center"]], rgb("#f8f8f4"), 1),
          f"center colour not applied: {state}")
    stats = canvas_stats(page)
    check(close_color(stats["background"], rgb("#f8f8f4"), 1),
          f"solid surface did not update: {stats}")

    page.locator("#tuneReset").click()
    page.wait_for_timeout(300)
    state = page.evaluate("window.__mirrorHome.field.getState()")
    check(close_color([round(c * 255) for c in state["palette"]["particle"]], rgb(PARTICLE_DEFAULT), 1),
          f"reset particle: {state}")
    check(close_color([round(c * 255) for c in state["palette"]["center"]], rgb("#ffffff"), 1),
          f"reset center: {state}")

    page.locator("#tuneCopy").click()
    page.wait_for_timeout(150)
    copied = page.evaluate("navigator.clipboard.readText()")
    config = json.loads(copied)
    check(config["particles"]["count"] >= 24, f"copy config missing particle count: {config}")
    check(config["particles"]["sizePx"] == [1.2, 4.2],
          f"copy config particle size: {config}")
    check(config["particles"]["speedPxPerSec"] == [16, 38],
          f"copy config particle speed: {config}")
    check(config["particles"]["dprCap"] == 2, f"copy config particle DPR: {config}")
    check("field" not in config, f"copy config kept block field: {config}")
    check(config["feather"] == 72, f"copy config feather: {config}")


def assert_fixed_feather(page):
    check(page.locator("#tuneFeather").count() == 0, "feather input should be removed")
    check(page.locator("#tuneFeatherFixed").inner_text() == "72",
          "feather readout should be 72")
    filter_state = page.evaluate("window.__mirrorHome.mirror.getState().filter")
    check(filter_state["feather"] == 72, f"feather not fixed at 72: {filter_state}")
    check(filter_state["blur"] == 2, f"blur changed: {filter_state}")


def run_webgl(browser, width=1200, height=900, dpr=1, tag="webgl"):
    page, context, errors = open_page(
        browser, width=width, height=height, dpr=dpr
    )
    try:
        state = wait_field(page)
        check(page.evaluate("window.__mirrorHome.mirror.mode") == "webgl", "expected WebGL mode")
        check(state["fallback"] is False, f"field is in fallback: {state}")
        assert_canvas_contract(page)
        assert_surface(page)
        assert_content_edges(page)
        particles = assert_particles(page)
        live = assert_live_capture(page)
        assert_tuning(page)
        assert_fixed_feather(page)

        # Persistence: changing the surface colour must survive a reload;
        # feather stays fixed.
        page.evaluate(
            """() => {
              const el = document.getElementById('tuneCenter');
              el.value = '#f0f0ec';
              el.dispatchEvent(new Event('input', { bubbles: true }));
            }"""
        )
        page.wait_for_timeout(350)
        page.reload(wait_until="networkidle")
        page.wait_for_function("document.getElementById('boot').hidden", timeout=20000)
        state = wait_field(page)
        check(close_color([round(c * 255) for c in state["palette"]["center"]],
                          rgb("#f0f0ec"), 1),
              f"persistence center: {state['palette']}")
        check(page.evaluate("window.__mirrorHome.mirror.getState().filter.feather") == 72,
              "feather drifted after reload")
        open_tuner(page)
        page.locator("#tuneReset").click()
        page.wait_for_timeout(250)
        close_tuner(page)

        SHOT_DIR.mkdir(exist_ok=True)
        page.screenshot(path=str(SHOT_DIR / f"probe-particles-{tag}.png"), scale="css")
        print(f"{tag}:", json.dumps({
            "state": state,
            "particles": particles,
            "live": live
        }))
        check(not errors, "console/page errors: " + "\n".join(errors))
    finally:
        context.close()


def run_svg(browser, width=1200, height=900, dpr=1, tag="svg"):
    page, context, errors = open_page(
        browser, width=width, height=height, dpr=dpr
    )
    try:
        state = wait_field(page)
        check(page.evaluate("window.__mirrorHome.mirror.mode") == "svg", "expected SVG mode")
        check(state["fallback"] is False, f"field is in fallback: {state}")
        assert_canvas_contract(page)
        assert_surface(page)
        assert_content_edges(page)
        particles = assert_particles(page)
        live = assert_live_capture(page)
        assert_tuning(page)
        close_tuner(page)
        page.screenshot(path=str(SHOT_DIR / f"probe-particles-{tag}.png"), scale="css")
        print(f"{tag}:", json.dumps({"particles": particles, "live": live}))
        check(not errors, "console/page errors: " + "\n".join(errors))
    finally:
        context.close()


def run_reduced(browser):
    page, context, errors = open_page(browser, reduced=True)
    try:
        state = wait_field(page)
        check(state["reducedMotion"] is True, f"reduced motion not detected: {state}")
        check(state["time"] == 0, f"reduced motion time advanced: {state}")
        check(state["animating"] is False, f"reduced motion kept the loop running: {state}")
        stats = assert_surface(page)
        first_hash = canvas_hash(page)
        page.mouse.move(600, 450)
        page.wait_for_timeout(700)
        second_hash = canvas_hash(page)
        state = page.evaluate("window.__mirrorHome.field.getState()")
        check(first_hash == second_hash, "reduced-motion field changed while idle")
        check(state["animating"] is False, f"reduced-motion loop started: {state}")
        check(not errors, "console/page errors: " + "\n".join(errors))
        print("reduced:", json.dumps({"dark": stats["dark"], "count": state["count"]}))
    finally:
        context.close()


def run_dpr(browser):
    results = []
    for dpr in (1.5, 3):
        page, context, errors = open_page(
            browser, width=1250, height=834, dpr=dpr
        )
        try:
            state = wait_field(page)
            layout = assert_canvas_contract(page, expected_dpr=min(dpr, 2))
            results.append({
                "dpr": dpr,
                "fieldDpr": state["dpr"],
                "css": state["css"],
                "canvas": state["canvas"]
            })
            check(not errors, "console/page errors: " + "\n".join(errors))
        finally:
            context.close()
    print("dpr:", json.dumps(results))


def run_fallback(browser):
    init_script = """
      (() => {
        const original = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function(type, ...args) {
          if (this.id === 'contentField' && type === '2d') return null;
          return original.call(this, type, ...args);
        };
      })();
    """
    page, context, errors = open_page(browser, init_script=init_script)
    try:
        state = wait_field(page, require_field=False)
        check(state["mode"] == "svg", f"fallback did not use SVG: {state}")
        check(state["hasField"] is False, f"fallback created a field: {state}")
        check(state["canvasHidden"] is True, f"fallback canvas is visible: {state}")
        check("is-field-fallback" in state["artClass"], f"fallback class missing: {state}")
        check(not errors, "console/page errors: " + "\n".join(errors))
        page.screenshot(path=str(SHOT_DIR / "probe-particles-fallback.png"), scale="css")
        print("fallback:", json.dumps(state))
    finally:
        context.close()


def main():
    SHOT_DIR.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel=CHANNEL,
            headless=False,
            args=[ENABLE_HTML_IN_CANVAS],
        )
        try:
            run_webgl(browser)
            run_webgl(browser, width=1440, height=900, dpr=1.5, tag="webgl-15")
            run_reduced(browser)
            run_dpr(browser)
        finally:
            browser.close()

        browser = p.chromium.launch(
            channel=CHANNEL,
            headless=False,
            args=[DISABLE_HTML_IN_CANVAS],
        )
        try:
            run_svg(browser)
            run_svg(browser, width=1440, height=900, dpr=1.5, tag="svg-15")
        finally:
            browser.close()

        browser = p.chromium.launch(
            channel=CHANNEL,
            headless=False,
            args=[DISABLE_HTML_IN_CANVAS, "--disable-webgl"],
        )
        try:
            run_fallback(browser)
        finally:
            browser.close()

    print("CONTENT FIELD PROBE PASSED")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        print(f"FAILED: {error}", file=sys.stderr)
        raise
