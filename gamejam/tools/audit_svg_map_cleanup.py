import json

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/mirror-lab.html"
FLAGS = ["--enable-features=CanvasDrawElement"]


def check(condition, message):
    if not condition:
        raise AssertionError(message)


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=False, args=FLAGS)
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(URL, wait_until="networkidle")
    page.wait_for_function("window.__mirrorLab && window.__mirrorLab.mirror")
    page.wait_for_function("window.__mirrorLab.mirror.getState().layout?.width === 1200")

    initial = page.evaluate("""() => {
      const root = document.querySelector('.mirror-root');
      const filters = [...root.querySelectorAll('filter')];
      const images = [...root.querySelectorAll('feImage')];
      const map = images[0];
      window.__mapAudit = { hrefMutations: 0, filterMutations: 0 };
      window.__oldHref = map.getAttribute('href');
      const observer = new MutationObserver((records) => {
        for (const record of records) {
          if (record.type !== 'attributes' || record.attributeName !== 'href') continue;
          if (record.target === map) window.__mapAudit.hrefMutations += 1;
        }
      });
      observer.observe(map, { attributes: true, attributeFilter: ['href'] });
      window.__mapObserver = observer;
      return {
        root: !!root,
        filters: filters.length,
        filterIds: filters.map((el) => el.id),
        images: images.length,
        mapWidth: map.getAttribute('width'),
        mapHrefLength: (map.getAttribute('href') || '').length,
        mapHrefPrefix: (map.getAttribute('href') || '').slice(0, 22),
      };
    }""")
    print("initial:", json.dumps(initial, ensure_ascii=False))
    check(initial["root"] is True, "missing mirror root")
    check(initial["filters"] == 1, f"unexpected filter count {initial['filters']}")
    check(initial["images"] == 2, f"unexpected feImage count {initial['images']}")

    # Debounced resize: the map must not be replaced during `resizing`.
    page.evaluate("""() => {
      const stage = window.__mirrorLab.stage;
      stage.style.right = 'auto';
      stage.style.bottom = 'auto';
      stage.style.width = '1000px';
      stage.style.height = '700px';
    }""")
    page.wait_for_timeout(40)
    during = page.evaluate("""() => ({
      same: document.querySelector('.mirror-root feImage').getAttribute('href') === window.__oldHref,
      mutations: window.__mapAudit.hrefMutations,
      size: window.__mirrorLab.mirror.getState().layout,
    })""")
    print("during:", json.dumps(during, ensure_ascii=False))
    check(during["same"] is True, "displacement map changed before debounce ended")
    check(during["mutations"] == 0, f"map mutated during resize: {during['mutations']}")

    page.wait_for_function(
        "document.querySelector('.mirror-root feImage').getAttribute('href') !== window.__oldHref",
        timeout=3000
    )
    after = page.evaluate("""() => {
      const images = [...document.querySelectorAll('.mirror-root feImage')];
      const map = images[0];
      const backend = window.__mirrorLab.mirror._backend;
      return {
        same: map.getAttribute('href') === window.__oldHref,
        mutations: window.__mapAudit.hrefMutations,
        imageCount: images.length,
        filterCount: document.querySelectorAll('.mirror-root filter').length,
        mapHrefMatchesBackend: !!backend && backend._mirrorMap && map.getAttribute('href') === backend._mirrorMap.url,
        backendCurrent: !!backend && backend._mirrorMap
          ? { width: backend._mirrorMap.width, height: backend._mirrorMap.height }
          : null,
        oldHrefStillInDom: images.some((el) => el.getAttribute('href') === window.__oldHref),
      };
    }""")
    print("after:", json.dumps(after, ensure_ascii=False))
    check(after["same"] is False, "resize did not replace the map")
    check(after["mutations"] == 1, f"map should be replaced once, got {after['mutations']}")
    check(after["imageCount"] == 2, f"feImage count changed: {after['imageCount']}")
    check(after["filterCount"] == 1, f"filter count changed: {after['filterCount']}")
    check(after["mapHrefMatchesBackend"] is True, "feImage does not point at the backend's current map")
    check(after["oldHrefStillInDom"] is False, "old map href is still referenced by a feImage")

    # Mode switch must remove the old SVG/filter entirely.
    page.evaluate("() => window.__mirrorLab.setMode('webgl')")
    page.wait_for_function("window.__mirrorLab.mirror.mode === 'webgl'")
    page.wait_for_timeout(300)
    webgl = page.evaluate("""() => ({
      filterCount: document.querySelectorAll('.mirror-root filter').length,
      imageCount: document.querySelectorAll('.mirror-root feImage').length,
      svgCount: document.querySelectorAll('.mirror-root svg').length,
      backendKind: window.__mirrorLab.mirror._backend.kind,
    })""")
    print("webgl:", json.dumps(webgl, ensure_ascii=False))
    check(webgl["filterCount"] == 0 and webgl["imageCount"] == 0,
          f"old SVG filter survived mode switch: {webgl}")
    check(webgl["backendKind"] == "webgl", f"unexpected backend {webgl['backendKind']}")

    page.evaluate("() => window.__mirrorLab.setMode('svg')")
    page.wait_for_function("window.__mirrorLab.mirror.mode === 'svg'")
    page.wait_for_timeout(250)
    restored = page.evaluate("""() => ({
      filterCount: document.querySelectorAll('.mirror-root filter').length,
      imageCount: document.querySelectorAll('.mirror-root feImage').length,
      svgCount: document.querySelectorAll('.mirror-root svg').length,
      mapHrefLength: (document.querySelector('.mirror-root feImage')?.getAttribute('href') || '').length,
    })""")
    print("restored:", json.dumps(restored, ensure_ascii=False))
    check(restored["filterCount"] == 1 and restored["imageCount"] == 2,
          f"restored SVG filters: {restored}")

    # destroy() must drop hrefs and backend map references.
    destroyed = page.evaluate("""() => {
      const mirror = window.__mirrorLab.mirror;
      mirror.destroy();
      return {
        rootCount: document.querySelectorAll('.mirror-root').length,
        filterCount: document.querySelectorAll('filter').length,
        imageCount: document.querySelectorAll('feImage').length,
        backend: mirror._backend,
      };
    }""")
    print("destroyed:", json.dumps(destroyed, ensure_ascii=False))
    check(destroyed["rootCount"] == 0, f"root survived destroy: {destroyed['rootCount']}")
    check(destroyed["filterCount"] == 0 and destroyed["imageCount"] == 0,
          f"SVG map/filter survived destroy: {destroyed}")
    check(destroyed["backend"] is None, "backend reference survived destroy")

    browser.close()

if errors:
    raise AssertionError("\n".join(errors))
print("ALL SVG MAP CLEANUP CHECKS PASSED")
