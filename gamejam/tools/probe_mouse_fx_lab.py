import json
import os

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/mirror-2610/mirror-lab.html"
CHANNEL = os.environ.get("MIRROR_CHANNEL", "chrome")


def check(condition, message):
    if not condition:
        raise AssertionError(message)


with sync_playwright() as p:
    browser = p.chromium.launch(channel=CHANNEL, headless=False, args=["--enable-features=CanvasDrawElement"])
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = []
    page.on("console", lambda msg: errors.append(f"{msg.type}: {msg.text}"))
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    page.goto(URL, wait_until="networkidle")
    page.wait_for_function("window.__mirrorLab && window.__mirrorLab.mirror && window.__mouseFx && window.__mouseFx.canvas")
    page.wait_for_timeout(500)

    # Hover inside the art, away from the panel.
    page.mouse.move(720, 430)
    page.wait_for_timeout(200)

    svg = page.evaluate("""() => {
      const fx = window.__mouseFx.canvas;
      const gl = fx.getContext('webgl2');
      const pixels = new Uint8Array(4);
      gl.readPixels(fx.width / 2 | 0, fx.height / 2 | 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
      return {
        canvas: [fx.width, fx.height],
        css: [fx.getBoundingClientRect().width, fx.getBoundingClientRect().height],
        center: Array.from(pixels),
        mode: window.__mirrorLab.mirror.mode,
        path: fx.parentElement.className,
      };
    }""")
    print("svg:", json.dumps(svg))
    check(svg["mode"] == "svg", "expected svg mode")
    check(svg["center"][3] > 10, f"mouse fx did not draw: {svg}")

    geometry = page.evaluate("""() => {
      const art = document.getElementById('art').getBoundingClientRect();
      const fx = window.__mouseFx.canvas.getBoundingClientRect();
      return {
        art: [art.left, art.top, art.right, art.bottom],
        fx: [fx.left, fx.top, fx.right, fx.bottom],
      };
    }""")
    print("bounds:", json.dumps(geometry))
    check(geometry["fx"][0] <= geometry["art"][0] + 0.75, f"effect canvas clips left border: {geometry}")
    check(geometry["fx"][1] <= geometry["art"][1] + 0.75, f"effect canvas clips top border: {geometry}")
    check(geometry["fx"][2] >= geometry["art"][2] - 0.75, f"effect canvas clips right border: {geometry}")
    check(geometry["fx"][3] >= geometry["art"][3] - 0.75, f"effect canvas clips bottom border: {geometry}")

    page.evaluate("() => window.__mirrorLab.setMode('webgl')")
    page.wait_for_function("window.__mirrorLab.mirror.mode === 'webgl'")
    page.wait_for_function("window.__mouseFx && window.__mouseFx.canvas")
    page.wait_for_timeout(900)
    page.mouse.move(720, 430)
    page.wait_for_timeout(300)

    webgl = page.evaluate("""() => {
      const fx = window.__mouseFx.canvas;
      const gl = fx.getContext('webgl2');
      const pixels = new Uint8Array(4);
      gl.readPixels(fx.width / 2 | 0, fx.height / 2 | 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
      return {
        canvas: [fx.width, fx.height],
        css: [fx.getBoundingClientRect().width, fx.getBoundingClientRect().height],
        center: Array.from(pixels),
        mode: window.__mirrorLab.mirror.mode,
        drawable: fx.hasAttribute('drawable'),
        state: window.__mirrorLab.mirror.getState().renderDetail,
      };
    }""")
    print("webgl:", json.dumps(webgl))
    check(webgl["mode"] == "webgl", "expected webgl mode")
    check(webgl["center"][3] > 10, f"mouse fx did not draw in webgl: {webgl}")
    check(webgl["drawable"] is False, "mouse fx canvas must not be drawable")

    print("errors:", errors)
    if errors:
        raise AssertionError("\n".join(errors))
    browser.close()

print("MOUSE FX LAB CHECKS PASSED")
