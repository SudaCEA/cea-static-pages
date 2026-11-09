"""Check the HTML-in-Canvas origin trial token shipped with the deck.

    .venv\\Scripts\\python.exe gamejam\\tools\\probe_origin_trial.py

Two parts:

1. Offline: decode the `origin-trial` meta of `mirror-2610/index.html` and check
   the payload Chrome will read (origin, feature, expiry, subdomain flag).
2. Browser: boot the page with no `CanvasDrawElement` flag on the local dev
   server. The token is issued for `https://ellia.cn`, so Chrome must ignore it
   here without logging an error and the page must still reach a working mirror
   (WebGL on a Chrome build that already enables the API, SVG otherwise).
"""

from __future__ import annotations

import base64
import datetime
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_content_field import SHOT_DIR, check, open_page  # noqa: E402

PAGE = Path(__file__).resolve().parents[1] / "mirror-2610" / "index.html"
META_RE = re.compile(
    r'<meta\s+http-equiv="origin-trial"\s+content="([^"]+)"\s*>', re.IGNORECASE
)
EXPECTED_ORIGIN = "https://ellia.cn:443"
EXPECTED_FEATURE = "HTMLInCanvas"


def decode_token(token):
    """Parse Chrome's token layout: version | ed25519 signature | length | JSON."""
    raw = base64.b64decode(token + "=" * (-len(token) % 4))
    check(raw[0] == 2, f"unexpected token version byte: {raw[0]}")
    start = raw.find(b'{"origin"')
    check(start == 1 + 64 + 4, f"unexpected token layout, payload at {start}")
    declared = int.from_bytes(raw[start - 4:start], "big")
    payload_text = raw[start:]
    check(declared == len(payload_text),
          f"token length prefix {declared} != payload {len(payload_text)}")
    return json.loads(payload_text.decode("utf-8"))


def check_source():
    html = PAGE.read_text(encoding="utf-8")
    tokens = META_RE.findall(html)
    check(len(tokens) == 1, f"expected one origin-trial meta: {len(tokens)}")
    head = html[:html.index("</head>")]
    check(META_RE.search(head) is not None, "origin-trial meta is outside <head>")
    payload = decode_token(tokens[0])
    print("token payload:", payload)
    check(payload["origin"] == EXPECTED_ORIGIN,
          f"token origin drifted: {payload['origin']}")
    check(payload["feature"] == EXPECTED_FEATURE,
          f"token feature drifted: {payload['feature']}")
    check(payload["isSubdomain"] is True, "token no longer covers subdomains")
    expiry = datetime.datetime.fromtimestamp(
        payload["expiry"], datetime.timezone.utc
    )
    check(expiry > datetime.datetime.now(datetime.timezone.utc),
          f"token expired on {expiry.isoformat()}")
    print(f"token valid until {expiry.isoformat()}")
    lab = PAGE.parent / "mirror-lab.html"
    check(lab.is_file(), "the lab page disappeared from the source tree")
    check("origin-trial" not in lab.read_text(encoding="utf-8"),
          "the lab page must not carry the token")
    print("token source: ok")


BROWSER_PROBE = """() => ({
  mode: window.__mirrorHome?.mirror?.mode ?? null,
  supported: window.__mirrorHome?.preflight?.supported ?? null,
  meta: document.querySelectorAll('meta[http-equiv="origin-trial"]').length
})"""


def check_browser(browser):
    page, context, errors = open_page(browser)
    messages = []
    page.on("console", lambda msg: messages.append((msg.type, msg.text)))
    try:
        page.bring_to_front()
        page.wait_for_function(
            "window.__mirrorHome && window.__mirrorHome.mirror", timeout=20000
        )
        page.wait_for_timeout(500)
        data = page.evaluate(BROWSER_PROBE)
        print("browser state:", data)
        trial_messages = [
            text for _, text in messages if "origin trial" in text.lower()
        ]
        for text in trial_messages:
            print("trial notice:", text)
        check(data["meta"] == 1, f"the deck lost its origin-trial meta: {data}")
        check(data["mode"] in ("webgl", "svg"),
              f"no mirror backend was mounted: {data}")
        check(not [1 for kind, _ in messages if kind in ("error", "pageerror")],
              f"page raised errors: {messages}")
        check(not [1 for text in trial_messages if "invalid" in text.lower()],
              f"Chrome rejected the token: {trial_messages}")
        page.screenshot(path=str(SHOT_DIR / "origin-trial-boot.png"), scale="css")
        print("token browser: ok")
    finally:
        context.close()


def main() -> int:
    SHOT_DIR.mkdir(exist_ok=True)
    check_source()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome-beta")
        try:
            check_browser(browser)
        finally:
            browser.close()
    print("ORIGIN TRIAL PROBE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
