import json
import os

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/mirror-2610/mirror-lab.html"
FLAGS = ["--enable-features=CanvasDrawElement"]
CHANNEL = os.environ.get("MIRROR_CHANNEL", "chrome")


def check(condition, message):
    if not condition:
        raise AssertionError(message)


with sync_playwright() as p:
    browser = p.chromium.launch(channel=CHANNEL, headless=False, args=FLAGS)
    page = browser.new_page(viewport={"width": 1200, "height": 900}, device_scale_factor=1.5)
    errors = []
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    page.goto(URL, wait_until="networkidle")
    page.wait_for_function("window.__mirrorLab && window.__mirrorLab.lastPreflight")
    print("channel:", CHANNEL)

    result = page.evaluate("""() => {
      const preflight = window.__mirrorLab.preflight;
      return {
        normal: preflight(),
        strict: preflight({ strictVersion: true }),
        subImage: preflight({ requireSubImage: true }),
      };
    }""")
    print("preflight:", json.dumps(result["normal"], indent=2))
    print("strict:", json.dumps({
        "ok": result["strict"]["ok"],
        "compatible": result["strict"]["compatible"],
        "errors": result["strict"]["errors"],
    }, indent=2))

    normal = result["normal"]
    check(normal["ok"] is True, f"preflight failed: {normal}")
    check(normal["features"]["htmlInCanvas"] is True, "HTML-in-Canvas feature check failed")
    check(normal["features"]["webgl2"] is True, "WebGL2 is unavailable")
    check(
        normal["features"]["texElementImage2D"] or normal["features"]["texElementSubImage2D"],
        "neither texElementImage2D nor texElementSubImage2D is available"
    )
    check(normal["browser"]["version"] is not None, "Chrome version was not detected")
    check(normal["version"]["minimum"] == "157.0.8080.0", "unexpected minimum Chrome version")

    if normal["version"]["ok"]:
        check(normal["compatible"] is True, "current Chrome should be compatible")
        check(result["strict"]["ok"] is True, "strict preflight rejected a compatible Chrome")
    else:
        codes = [issue["code"] for issue in normal["warnings"]]
        check("chrome-nested-canvas-dpr-bug" in codes, f"missing DPR warning: {normal['warnings']}")
        check(normal["compatible"] is False, "old Chrome should not be compatible")
        check(result["strict"]["ok"] is False, "strict preflight should reject old Chrome")

    check(result["subImage"]["ok"] is True, f"subImage preflight failed: {result['subImage']}")

    page.evaluate("window.__mirrorLab.setMode('webgl')")
    page.wait_for_function("window.__mirrorLab.mirror.mode === 'webgl'")
    page.wait_for_timeout(500)
    banner = page.evaluate("""() => {
      const el = document.getElementById('preflightOut');
      return {
        hidden: el.hidden,
        className: el.className,
        text: el.textContent,
      };
    }""")
    print("banner:", json.dumps(banner, indent=2))

    if normal["version"]["ok"]:
        check(banner["hidden"] is True, f"unexpected preflight banner: {banner}")
    else:
        check(banner["hidden"] is False, "preflight warning banner is hidden")
        check(banner["className"] == "warn", f"unexpected banner class: {banner}")
        check(
            "unexpected visual effects" in banner["text"].lower(),
            f"preflight banner does not explain the visual risk: {banner}"
        )

    check(errors == [], f"page errors: {errors}")
    browser.close()

print("PREFLIGHT CHECKS PASSED")
