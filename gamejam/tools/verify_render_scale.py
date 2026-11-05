import json
import math
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/mirror-2610/mirror-lab.html"
FLAGS = ["--enable-features=CanvasDrawElement"]
errors = []


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def state(page):
    return page.evaluate("window.__mirrorLab.mirror.getState()")


def set_scale(page, value, content=1):
    page.evaluate(
        "([value, content]) => window.__mirrorLab.mirror.setWebglOptions({ renderScale: value, contentScale: content })",
        [value, content]
    )
    page.wait_for_timeout(350)
    return state(page)


def install_probe(page):
    page.evaluate("""() => {
      window.__hitOffsets = [];
      const btn = document.getElementById('hitBtn');
      btn.addEventListener('click', (event) => {
        const rect = btn.getBoundingClientRect();
        window.__hitOffsets.push({
          offsetX: event.offsetX,
          offsetY: event.offsetY,
          fromRectX: event.clientX - rect.left,
          fromRectY: event.clientY - rect.top,
          w: rect.width,
          h: rect.height,
        });
      });
    }""")


def click_button_edge(page, edge="center"):
    box = page.locator("#hitBtn").bounding_box()
    check(box is not None, "button box")
    if edge == "center":
        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] / 2
    elif edge == "left":
        x = box["x"] + 2.5
        y = box["y"] + box["height"] / 2
    else:
        x = box["x"] + box["width"] - 2.5
        y = box["y"] + box["height"] / 2
    before = int(page.locator("#hitN").inner_text())
    page.mouse.click(x, y)
    page.wait_for_timeout(100)
    after = int(page.locator("#hitN").inner_text())
    check(after == before + 1, f"button {edge} click did not hit ({before}->{after}) at {x},{y}")
    entry = page.evaluate("window.__hitOffsets.at(-1)")
    check(entry is not None, "missing hit probe entry")
    expected_x = x - box["x"]
    expected_y = y - box["y"]
    check(
        abs(entry["fromRectX"] - expected_x) <= 1.01 and
        abs(entry["fromRectY"] - expected_y) <= 1.01,
        f"hit coords shifted: {entry} expected {expected_x},{expected_y}"
    )
    return entry


def open_page(browser, dpr):
    page = browser.new_page(viewport={"width": 1200, "height": 900}, device_scale_factor=dpr)
    page.on("console", lambda msg: errors.append(f"dpr{dpr} console {msg.type}: {msg.text}"))
    page.on("pageerror", lambda exc: errors.append(f"dpr{dpr} pageerror: {exc}"))
    page.goto(URL, wait_until="networkidle")
    page.wait_for_timeout(500)
    check(page.locator("#renderScale").is_disabled(), "mirror control must start disabled in SVG mode")
    check(page.locator("#contentScale").is_disabled(), "body control must start disabled in SVG mode")
    page.evaluate("window.__mirrorLab.setMode('webgl')")
    page.wait_for_timeout(1200)
    install_probe(page)
    return page


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=False, args=FLAGS)

    # DPR 1: all supported scales, including edge clicks and input focus.
    page = open_page(browser, 1)
    check(page.evaluate("window.__mirrorLab.mirror.mode") == "webgl", "webgl mode")
    initial = state(page)
    check(initial["renderDetail"]["outputWidth"] == 1200, "dpr1 output width")
    check(initial["renderDetail"]["outputHeight"] == 900, "dpr1 output height")
    check(initial["renderDetail"]["active"] is False, "1x must take the direct path")
    check(page.locator("#renderScale").is_disabled() is False, "mirror control enabled in webgl")
    check(page.locator("#contentScale").is_disabled() is False, "body control enabled in webgl")
    check(
        (initial["renderDetail"]["contentWidth"], initial["renderDetail"]["contentHeight"]) == (600, 360),
        "default body target"
    )

    for scale, expected in [(0.75, (900, 675)), (0.5, (600, 450)), (0.25, (300, 225)), (0.125, (150, 113)), (1, (1200, 900))]:
        result = set_scale(page, scale)
        rd = result["renderDetail"]
        check(result["mode"] == "webgl", f"mode at {scale}")
        check((rd["width"], rd["height"]) == expected, f"render target {scale}: {rd}")
        check((rd["outputWidth"], rd["outputHeight"]) == (1200, 900), f"canvas at {scale}")
        check(rd["active"] is (scale < 1), f"active flag at {scale}")
        check(abs(rd["effectiveScale"] - scale) < 1e-6, f"effective scale at {scale}")
        check((rd["contentWidth"], rd["contentHeight"]) == (600, 360), f"body target at mirror {scale}")
        click_button_edge(page, "center")
        if scale <= 0.5:
            click_button_edge(page, "left")
            click_button_edge(page, "right")

    # Body scaling is independent of the mirror bands.
    for render_scale, content_scale, mirror_expected, body_expected in [
        (0.5, 0.5, (600, 450), (300, 180)),
        (0.25, 0.5, (300, 225), (300, 180)),
        (1, 0.5, (1200, 900), (300, 180)),
        (1, 1, (1200, 900), (600, 360)),
    ]:
        result = set_scale(page, render_scale, content_scale)
        rd = result["renderDetail"]
        check(
            (rd["width"], rd["height"]) == mirror_expected,
            f"mirror target at {render_scale}/{content_scale}: {rd}"
        )
        check(
            (rd["contentWidth"], rd["contentHeight"]) == body_expected,
            f"body target at {render_scale}/{content_scale}: {rd}"
        )
        check(
            rd["active"] is (render_scale < 1 or content_scale < 1),
            f"active at {render_scale}/{content_scale}"
        )
        click_button_edge(page, "center")
        click_button_edge(page, "left")
        click_button_edge(page, "right")

    # The two selects drive the same options without a rebuild.
    page.select_option("#renderScale", "0.5")
    page.select_option("#contentScale", "1")
    page.wait_for_timeout(500)
    ui_rd = state(page)["renderDetail"]
    check((ui_rd["renderScale"], ui_rd["contentScale"]) == (0.5, 1), f"UI mirror/body scales: {ui_rd}")
    check("composite" in page.locator("#readout").inner_text(), "composite readout")
    opts = page.evaluate("window.__mirrorLab.mirror.getWebglOptions()")
    check((opts["renderScale"], opts["contentScale"]) == (0.5, 1), f"webgl options: {opts}")

    # Input focus checks the exact hit rectangle, not just a large button.
    input_box = page.locator("#hitInput").bounding_box()
    page.mouse.click(input_box["x"] + 4, input_box["y"] + 4)
    page.keyboard.type("coords")
    check(page.evaluate("document.activeElement.id") == "hitInput", "input did not receive focus")
    check(page.locator("#hitInput").input_value() == "coords", "input value")

    # Switch to SVG and back: controls and stored option should survive.
    page.evaluate("window.__mirrorLab.setMode('svg')")
    page.wait_for_timeout(800)
    svg_state = state(page)
    check(svg_state["mode"] == "svg", "svg mode")
    check(page.locator("#renderScale").is_disabled(), "mirror control disabled in SVG")
    check(page.locator("#contentScale").is_disabled(), "body control disabled in SVG")
    check(svg_state["mapDetail"] is not None, "svg map detail")
    check(svg_state["mapDetail"]["width"] > 0, "svg map width")
    page.evaluate("window.__mirrorLab.mirror.setWebglOptions({ renderScale: 0.375 })")
    check(
        page.evaluate("window.__mirrorLab.mirror.getWebglOptions().renderScale") == 0.375,
        "webgl option can be stored while SVG"
    )
    page.evaluate("""() => {
      const select = document.getElementById('renderScale');
      select.value = '0.375';
    }""")
    page.evaluate("window.__mirrorLab.setMode('webgl')")
    page.wait_for_timeout(1200)
    rd = state(page)["renderDetail"]
    check(rd["requestedScale"] == 0.375 and (rd["width"], rd["height"]) == (450, 338), f"rebuilt scale: {rd}")
    click_button_edge(page, "center")

    # Invalid values must throw; valid string should normalize.
    for bad in [0, -0.1, 1.01, "abc", None]:
        threw = page.evaluate("""value => {
          try { window.__mirrorLab.mirror.setWebglOptions({ renderScale: value }); return false; }
          catch (error) { return error.name + ': ' + error.message; }
        }""", bad)
        check(threw is not False, f"invalid renderScale {bad!r} did not throw")
    for bad in [0, -0.1, 1.01, "abc", None]:
        threw = page.evaluate("""value => {
          try { window.__mirrorLab.mirror.setWebglOptions({ contentScale: value }); return false; }
          catch (error) { return error.name + ': ' + error.message; }
        }""", bad)
        check(threw is not False, f"invalid contentScale {bad!r} did not throw")
    page.evaluate("window.__mirrorLab.mirror.setWebglOptions({ renderScale: '0.5', contentScale: '0.5' })")
    page.wait_for_timeout(300)
    check(state(page)["renderDetail"]["requestedScale"] == 0.5, "numeric string mirror scale")
    check(state(page)["renderDetail"]["contentScale"] == 0.5, "numeric string body scale")

    # Resize with a low-res target and verify hit-testing still lines up.
    page.set_viewport_size({"width": 1000, "height": 700})
    page.wait_for_timeout(700)
    resized = state(page)
    check((resized["renderDetail"]["outputWidth"], resized["renderDetail"]["outputHeight"]) == (1000, 700), "resized canvas")
    check((resized["renderDetail"]["width"], resized["renderDetail"]["height"]) == (500, 350), "resized target")
    check((resized["renderDetail"]["contentWidth"], resized["renderDetail"]["contentHeight"]) == (300, 180), "resized body")
    click_button_edge(page, "center")
    page.close()

    # DPR 1.5: fractional backing store and hit testing.
    page = open_page(browser, 1.5)
    rd = state(page)["renderDetail"]
    check((rd["outputWidth"], rd["outputHeight"]) == (1800, 1350), f"dpr1.5 output: {rd}")
    result = set_scale(page, 0.5, 1)
    rd = result["renderDetail"]
    check((rd["width"], rd["height"]) == (900, 675), f"dpr1.5 target: {rd}")
    check((rd["contentWidth"], rd["contentHeight"]) == (900, 540), f"dpr1.5 body: {rd}")
    click_button_edge(page, "center")
    click_button_edge(page, "left")
    page.close()

    # DPR 2: canvas is 2x CSS; renderScale is relative to the DPR-capped output.
    page = open_page(browser, 2)
    rd = state(page)["renderDetail"]
    check((rd["outputWidth"], rd["outputHeight"]) == (2400, 1800), f"dpr2 output: {rd}")
    for scale, expected, body_expected in [
        (0.5, (1200, 900), (1200, 720)),
        (0.25, (600, 450), (1200, 720)),
        (0.5, (1200, 900), (600, 360)),
    ]:
        content = 0.5 if body_expected == (600, 360) else 1
        result = set_scale(page, scale, content)
        rd = result["renderDetail"]
        check((rd["outputWidth"], rd["outputHeight"]) == (2400, 1800), f"dpr2 canvas at {scale}")
        check((rd["width"], rd["height"]) == expected, f"dpr2 target at {scale}: {rd}")
        check((rd["contentWidth"], rd["contentHeight"]) == body_expected, f"dpr2 body at {scale}: {rd}")
        click_button_edge(page, "center")
        click_button_edge(page, "left")
        click_button_edge(page, "right")
    page.close()

    browser.close()

print("ALL CHECKS PASSED")
if errors:
    print("CONSOLE/ERRORS")
    print("\n".join(errors))
    raise SystemExit(1)
