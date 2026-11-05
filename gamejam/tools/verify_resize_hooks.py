import json

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/mirror-2610/mirror-lab.html"
FLAGS = ["--enable-features=CanvasDrawElement"]
errors = []


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def attach(page):
    page.evaluate("""() => {
      window.__resizeEvents = [];
      const mirror = window.__mirrorLab.mirror;
      if (window.__resizeMirror === mirror) return;
      window.__resizeMirror = mirror;
      for (const type of ['resizeStart', 'resizing', 'resize', 'resizeEnd']) {
        mirror.on(type, (event) => window.__resizeEvents.push({
          type,
          t: Math.round(performance.now()),
          width: event.detail.width,
          height: event.detail.height,
          dpr: event.detail.dpr,
          interval: event.detail.interval,
          elapsed: Number.isFinite(event.detail.elapsed) ? Math.round(event.detail.elapsed) : null,
          layoutWidth: event.detail.layout?.width ?? null,
          layoutHeight: event.detail.layout?.height ?? null,
          mode: event.detail.mode,
        }));
      }
    }""")


def events(page):
    return page.evaluate("window.__resizeEvents")


def state(page):
    return page.evaluate("window.__mirrorLab.mirror.getState()")


def frame(page):
    return page.evaluate("""() => {
      const el = document.getElementById('resizeFrame');
      const style = getComputedStyle(el);
      return {
        on: el.classList.contains('on'),
        label: document.getElementById('resizeFrameLabel').textContent,
        visibility: style.visibility,
        opacity: style.opacity,
      };
    }""")


def types(items):
    return [item["type"] for item in items]


def lifecycle(page, mode, label):
    before = state(page)["layout"]
    page.set_viewport_size({"width": 1100, "height": 800})
    page.wait_for_timeout(20)
    page.set_viewport_size({"width": 1000, "height": 720})
    page.wait_for_timeout(20)
    page.set_viewport_size({"width": 1080, "height": 760})
    page.wait_for_timeout(400)

    items = events(page)
    t = types(items)
    check(t.count("resizeStart") == 1, f"{label}: resizeStart count {t}")
    check(t.count("resize") == 1, f"{label}: resize count {t}")
    check(t.count("resizeEnd") == 1, f"{label}: resizeEnd count {t}")
    check(t[0] == "resizeStart", f"{label}: first event {t}")
    check(t[-1] == "resizeEnd", f"{label}: last event {t}")
    check(t.index("resize") < t.index("resizeEnd"), f"{label}: resize before end {t}")
    end = [item for item in items if item["type"] == "resizeEnd"][0]
    after = state(page)["layout"]
    check(after is not None and (after["width"], after["height"]) == (1080, 760), f"{label}: final layout {after}")
    check((end["width"], end["height"]) == (1080, 760), f"{label}: end detail {end}")
    check(end["layoutWidth"] == 1080 and end["layoutHeight"] == 760, f"{label}: end layout detail {end}")
    check(end["mode"] == mode, f"{label}: end mode {end}")
    check(before is not None, f"{label}: initial layout")
    return items


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=False, args=FLAGS)
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.on("console", lambda msg: errors.append(f"console {msg.type}: {msg.text}"))
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    page.goto(URL, wait_until="networkidle")
    page.wait_for_function("window.__mirrorLab && window.__mirrorLab.mirror")

    attach(page)
    page.wait_for_timeout(200)
    check(events(page) == [], f"initial quiet state emitted {events(page)}")
    svg_events = lifecycle(page, "svg", "svg/default")
    print("SVG:", json.dumps(svg_events, ensure_ascii=False))

    # 300 ms interval must keep the old layout until the quiet period elapses.
    page.evaluate("() => window.__mirrorLab.setResizeInterval(300)")
    page.wait_for_timeout(250)
    before = state(page)["layout"]
    attach(page)
    page.set_viewport_size({"width": 980, "height": 700})
    page.wait_for_timeout(150)
    mid = state(page)["layout"]
    check(mid["width"] == before["width"] and mid["height"] == before["height"],
          f"300ms interval applied too early: {before} -> {mid}")
    check(types(events(page)).count("resize") == 0, f"300ms interval emitted resize too early: {events(page)}")
    active_frame = frame(page)
    check(active_frame["on"] is True, f"resize frame not shown on start: {active_frame}")
    check(active_frame["visibility"] == "visible", f"resize frame not visible: {active_frame}")
    check("980 × 700" in active_frame["label"], f"resize frame label: {active_frame}")
    page.wait_for_timeout(300)
    items = events(page)
    t = types(items)
    check(t.count("resizeStart") == 1 and t.count("resize") == 1 and t.count("resizeEnd") == 1,
          f"300ms lifecycle {t}")
    end = [item for item in items if item["type"] == "resizeEnd"][0]
    check(end["interval"] == 300, f"300ms interval detail {end}")
    check((end["width"], end["height"]) == (980, 700), f"300ms end size {end}")
    ended_frame = frame(page)
    check(ended_frame["on"] is False, f"resize frame still on after end: {ended_frame}")
    check(ended_frame["visibility"] == "hidden", f"resize frame still visible after end: {ended_frame}")
    print("300ms:", json.dumps(items, ensure_ascii=False))

    # WebGL uses the same scheduler and lifecycle.
    page.evaluate("() => window.__mirrorLab.setResizeInterval(100)")
    page.evaluate("() => window.__mirrorLab.setMode('webgl')")
    page.wait_for_function("window.__mirrorLab.mirror.mode === 'webgl'")
    page.wait_for_timeout(300)
    attach(page)
    page.wait_for_timeout(200)
    check(events(page) == [], f"webgl initial quiet state emitted {events(page)}")
    webgl_events = lifecycle(page, "webgl", "webgl/default")
    print("WebGL:", json.dumps(webgl_events, ensure_ascii=False))

    # A sustained resize must emit throttled `resizing` notifications while
    # still performing exactly one final layout.
    attach(page)
    page.evaluate("""async () => {
      const stage = window.__mirrorLab.stage;
      stage.style.right = 'auto';
      stage.style.bottom = 'auto';
      stage.style.width = '1000px';
      stage.style.height = '700px';
      await new Promise((resolve) => {
        let index = 0;
        const timer = setInterval(() => {
          index += 1;
          stage.style.width = `${1000 + index * 5}px`;
          stage.style.height = `${700 + index * 3}px`;
          if (index >= 10) {
            clearInterval(timer);
            setTimeout(resolve, 350);
          }
        }, 50);
      });
    }""")
    sustained = events(page)
    print("sustained:", json.dumps(sustained, ensure_ascii=False))
    st = types(sustained)
    check(st.count("resizeStart") == 1, f"sustained resizeStart {st}")
    check(st.count("resizing") >= 1, f"sustained resizing {st}")
    check(st.count("resize") == 1, f"sustained resize {st}")
    check(st.count("resizeEnd") == 1, f"sustained resizeEnd {st}")
    check(st.index("resizing") < st.index("resize"), f"sustained resizing order {st}")
    check(st.index("resize") < st.index("resizeEnd"), f"sustained end order {st}")
    final_layout = state(page)["layout"]
    check(final_layout is not None and (final_layout["width"], final_layout["height"]) == (1050, 730),
          f"sustained final layout {final_layout}")

    # Hiding and re-showing at the same size must clear `suspended`.
    attach(page)
    page.evaluate("window.__mirrorLab.stage.style.display = 'none'")
    page.wait_for_timeout(250)
    hidden = state(page)
    check(hidden["suspended"] is True, f"hidden state {hidden['suspended']}")
    page.evaluate("window.__mirrorLab.stage.style.display = ''")
    page.wait_for_timeout(250)
    shown = state(page)
    check(shown["suspended"] is False, f"shown state {shown['suspended']}")
    check(shown["layout"] is not None and
          (shown["layout"]["width"], shown["layout"]["height"]) == (1050, 730),
          f"shown layout {shown['layout']}")

    # destroy() must cancel a pending debounce timer.
    attach(page)
    page.set_viewport_size({"width": 1000, "height": 700})
    page.wait_for_timeout(30)
    page.evaluate("window.__mirrorLab.mirror.destroy()")
    page.wait_for_timeout(300)
    destroyed = events(page)
    check(types(destroyed).count("resizeEnd") == 0, f"destroy did not cancel resizeEnd: {destroyed}")

    # Invalid interval is rejected at creation.
    invalid = page.evaluate("""async () => {
      const { createMirror } = await import('../js/effects/mirror.js');
      const container = document.createElement('div');
      const content = document.createElement('div');
      container.style.cssText = 'width:100px;height:100px';
      content.style.cssText = 'width:10px;height:10px';
      document.body.append(container, content);
      try {
        await createMirror({ container, content, resize: { interval: -1 } });
        return 'no error';
      } catch (error) {
        return error.name + ': ' + error.message;
      } finally {
        container.remove();
        content.remove();
      }
    }""")
    check("TypeError" in invalid and "resize.interval" in invalid, f"invalid interval: {invalid}")

    browser.close()

if errors:
    raise AssertionError("\n".join(errors))
print("ALL RESIZE CHECKS PASSED")
