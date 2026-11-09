"""Capture the closing slide: the rule turn frames plus the settled page.

    .venv\\Scripts\\python.exe gamejam\\tools\\shot_end.py [--backend=svg] [--large]

Requires the local server on http://127.0.0.1:4173. Writes screenshots into
.dsh/ so a rule/layout tweak can be reviewed quickly.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_content_field import (  # noqa: E402
    DISABLE_HTML_IN_CANVAS,
    ENABLE_HTML_IN_CANVAS,
    SHOT_DIR,
    open_page,
)

MATRIX = """() => [...document.querySelectorAll('.sheet-rule')].map(
  (el) => getComputedStyle(el).transform
)"""


def main() -> int:
    backend = "svg" if "--backend=svg" in sys.argv else "webgl"
    size = (1600, 900) if "--large" in sys.argv else (1200, 900)
    flag = DISABLE_HTML_IN_CANVAS if backend == "svg" else ENABLE_HTML_IN_CANVAS
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel="chrome-beta",
            args=[flag, "--autoplay-policy=no-user-gesture-required"],
        )
        page, context, errors = open_page(browser, width=size[0], height=size[1])
        try:
            page.bring_to_front()
            page.evaluate("window.__mirrorHome.deck.goTo(3)")
            page.wait_for_function(
                "window.__mirrorHome.deck.getState().locked === false",
                timeout=8000,
            )
            page.wait_for_timeout(700)

            page.evaluate("window.__mirrorHome.deck.goTo(4)")
            at = 0
            for mark in (120, 260, 420, 620):
                page.wait_for_timeout(mark - at)
                at = mark
                matrix = page.evaluate(MATRIX)
                page.screenshot(
                    path=str(SHOT_DIR / f"end-turn{mark}-{backend}.png"), scale="css"
                )
                print(f"t={mark}ms", matrix)
            page.wait_for_function(
                "window.__mirrorHome.deck.getState().locked === false",
                timeout=8000,
            )
            page.wait_for_timeout(900)
            page.screenshot(path=str(SHOT_DIR / f"end-{backend}.png"), scale="css")
            print("final", page.evaluate(MATRIX))
            mode = page.evaluate("document.getElementById('art').dataset.ruleMode")
            print(f"backend={backend} ruleMode={mode} errors={errors}")
        finally:
            context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
