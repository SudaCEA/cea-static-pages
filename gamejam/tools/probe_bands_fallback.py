"""Assert the SVG band capability table and the full-bleed fallback layout.

    .venv\\Scripts\\python.exe gamejam\\tools\\probe_bands_fallback.py

Requires the local server on http://127.0.0.1:4173.

Part 1 checks `checkMirrorBandsSupport()` against a UA table (the Gecko and
WebKit rows are what switch the preflight copy and the layout). Part 2 boots
the real page twice in Chromium: once normally, and once with a spoofed Gecko
user agent, which forces the full-bleed layout even though the engine could
paint the bands.
"""

from __future__ import annotations

import json
import os

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/mirror-2610/"
MIRROR_MODULE = "/js/effects/mirror.js"
CHANNEL = os.environ.get("MIRROR_CHANNEL", "chrome-beta")
FLAGS = [
    "--enable-features=CanvasDrawElement",
    "--autoplay-policy=no-user-gesture-required",
]

GECKO = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:159.0) "
    "Gecko/20100101 Firefox/159.0"
)
WEBKIT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.2 Safari/605.1.15"
)
IOS_CHROME = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/133.0.6943.90 "
    "Mobile/15E148 Safari/604.1"
)
IOS_FIREFOX = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/136.0 Mobile/15E148 Safari/604.1"
)
CHROMIUM = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/158.0.0.0 Safari/537.36"
)
ANDROID_CHROME = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/158.0.0.0 Mobile Safari/537.36"
)


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def boot(page):
    page.goto(URL, wait_until="load")
    page.wait_for_function(
        "document.body.classList.contains('mirror-ready')", timeout=30000)
    page.wait_for_timeout(1200)


def wait_for_question(page):
    page.goto(URL, wait_until="load")
    page.wait_for_function(
        """() => {
          const question = document.getElementById('bootQuestion');
          return !!question && !question.hasAttribute('hidden');
        }""",
        timeout=30000,
    )
    page.wait_for_timeout(400)


def read_layout(page):
    return page.evaluate(
        """() => {
          const home = window.__mirrorHome;
          const mirror = home.mirror;
          const state = mirror ? mirror.getState() : null;
          return {
            fullBleed: document.body.dataset.mirrorLayout || null,
            bands: home.bandSupport,
            mode: state ? state.mode : null,
            layout: state ? state.layout : null,
            map: state ? state.map : null,
            stage: [document.getElementById('stage').clientWidth,
                    document.getElementById('stage').clientHeight],
            question: document.querySelector('#bootQuestion')?.innerText
              .replace(/\\s+/g, ' ').trim().slice(0, 160) || null,
            buttons: [...document.querySelectorAll('#bootQuestion button')]
              .map((b) => b.textContent.trim())
          };
        }"""
    )


def main():
    results = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=CHANNEL, headless=False, args=FLAGS)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))

            # --- Part 1: the capability table -------------------------------
            page.goto(URL, wait_until="load")
            table = page.evaluate(
                """async (cases) => {
                  const mod = await import('/js/effects/mirror.js');
                  const out = {};
                  for (const [name, ua] of Object.entries(cases)) {
                    const result = mod.checkMirrorBandsSupport({ userAgent: ua });
                    out[name] = { ok: result.ok, engine: result.engine,
                                  code: result.issue?.code || null };
                  }
                  return out;
                }""",
                {
                    "chromium": CHROMIUM,
                    "android-chrome": ANDROID_CHROME,
                    "gecko": GECKO,
                    "webkit": WEBKIT,
                    "ios-chrome": IOS_CHROME,
                    "ios-firefox": IOS_FIREFOX,
                },
            )
            results["table"] = table
            for name in ("chromium", "android-chrome"):
                check(table[name]["ok"] is True,
                      f"{name} should keep the bands: {table[name]}")
                check(table[name]["engine"] == "chromium",
                      f"{name} engine misdetected: {table[name]}")
            for name in ("gecko", "webkit", "ios-chrome", "ios-firefox"):
                check(table[name]["ok"] is False,
                      f"{name} should fall back to full-bleed: {table[name]}")
            check(table["gecko"]["engine"] == "gecko" and
                  table["gecko"]["code"] == "gecko-backdrop-feimage",
                  f"gecko row is wrong: {table['gecko']}")
            for name in ("webkit", "ios-chrome", "ios-firefox"):
                check(table[name]["engine"] == "webkit" and
                      table[name]["code"] == "webkit-backdrop-url",
                      f"{name} should be classified as WebKit: {table[name]}")
            print("capability table: ok")

            # --- Part 2a: Chromium keeps the banded layout ------------------
            boot(page)
            banded = read_layout(page)
            results["banded"] = banded
            check(banded["fullBleed"] == "banded",
                  f"chromium should stay banded: {banded['fullBleed']}")
            check(banded["bands"]["ok"] is True,
                  f"chromium bands reported unsupported: {banded['bands']}")
            check(banded["mode"] == "webgl",
                  f"chromium did not start the WebGL backend: {banded['mode']}")
            layout = banded["layout"]
            check(abs(layout["aw"] - layout["width"] * 0.72) <= 1 and
                  abs(layout["ah"] - layout["height"] * 0.72) <= 1,
                  f"chromium content is not 72%: {layout}")
            check(not errors, f"chromium page errors: {errors}")
            print("banded layout: ok")
            page.close()

            # --- Part 2b: a Gecko UA forces the full-bleed layout -----------
            deep = browser.new_page(viewport={"width": 1440, "height": 900})
            deep_errors = []
            deep.on("pageerror", lambda exc: deep_errors.append(f"pageerror: {exc}"))
            deep.add_init_script(
                "Object.defineProperty(navigator, 'userAgent', {"
                "  configurable: true,"
                f" get: () => {json.dumps(GECKO)}"
                "});"
            )
            wait_for_question(deep)
            before = read_layout(deep)
            if "回退到 SVG" in before["buttons"]:
                deep.get_by_role("button", name="回退到 SVG").first.click()
                deep.wait_for_function(
                    "document.body.classList.contains('mirror-ready')", timeout=30000)
                deep.wait_for_timeout(1600)
            full = read_layout(deep)
            results["fullbleed"] = full
            check(full["bands"]["ok"] is False,
                  f"gecko UA did not disable the bands: {full['bands']}")
            check(full["fullBleed"] == "fullbleed",
                  f"full-bleed layout not marked: {full['fullBleed']}")
            check(full["map"]["mirror"] == "none" and full["map"]["mask"] == "none",
                  f"full-bleed still built the maps: {full['map']}")
            check(full["layout"]["aw"] == full["stage"][0] and
                  full["layout"]["ah"] == full["stage"][1],
                  f"content does not fill the stage: {full['layout']} {full['stage']}")
            check(not deep_errors, f"full-bleed page errors: {deep_errors}")
            print("full-bleed layout: ok")
            deep.close()
        finally:
            browser.close()

    print(json.dumps(results, indent=2, ensure_ascii=False))
    print("BANDS FALLBACK PROBE PASSED")


main()
