"""Capture the cover at the baked 6px / 150% defaults.

    .venv\\Scripts\\python.exe gamejam\\tools\\shot_cover.py [width height dpr]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_content_field import (  # noqa: E402
    ENABLE_HTML_IN_CANVAS,
    SHOT_DIR,
    open_page,
)

PROBE = """() => {
  const art = document.getElementById('art').getBoundingClientRect();
  const cover = document.querySelector('.slide-cover');
  const coverRect = cover.getBoundingClientRect();
  const lockup = cover.querySelector('.cover-lockup').getBoundingClientRect();
  const side = cover.querySelector('.cover-side').getBoundingClientRect();
  const rule = document.getElementById('sheetRuleA').getBoundingClientRect();
  const root = getComputedStyle(document.documentElement);
  return {
    art: [art.x, art.y, art.width, art.height],
    lockup: [lockup.x, lockup.y, lockup.width, lockup.height, lockup.right],
    side: [side.x, side.y, side.width, side.height, side.right],
    overlapX: lockup.right - side.x,
    rule: [rule.x, rule.y, rule.width, rule.height],
    ruleBottomGap: coverRect.bottom - rule.bottom,
    textGap: rule.top - lockup.bottom,
    scaleVar: root.getPropertyValue('--cover-art-scale').trim(),
    barVar: root.getPropertyValue('--cover-bar-height').trim(),
    tunerNodes: document.querySelectorAll('#tuner, .tuner, [id^="tune"]').length
  };
}"""


def main() -> int:
    width = int(sys.argv[1]) if len(sys.argv) > 1 else 1600
    height = int(sys.argv[2]) if len(sys.argv) > 2 else 900
    dpr = float(sys.argv[3]) if len(sys.argv) > 3 else 1
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel="chrome-beta",
            args=[ENABLE_HTML_IN_CANVAS, "--autoplay-policy=no-user-gesture-required"],
        )
        page, context, errors = open_page(browser, width=width, height=height, dpr=dpr)
        try:
            page.bring_to_front()
            page.wait_for_timeout(700)
            page.mouse.move(4, 4)
            page.wait_for_timeout(300)
            print(json.dumps(page.evaluate(PROBE), ensure_ascii=False))
            page.screenshot(
                path=str(SHOT_DIR / f"cover-{width}x{height}.png"), scale="css"
            )
            print("errors:", errors)
        finally:
            context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
