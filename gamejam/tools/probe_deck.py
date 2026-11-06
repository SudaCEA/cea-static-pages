"""Probe the mirror-2610 slide deck.

Run with the repository's Playwright environment:

    .venv\\Scripts\\python.exe gamejam\\tools\\probe_deck.py

Requires the local server on http://127.0.0.1:4173. Chrome Beta is the
default because stable Chrome 155 has the known nested-canvas device-pixel
bug. Override with MIRROR_CHANNEL if needed.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_content_field import SHOT_DIR, check, open_page  # noqa: E402

ENABLE_HTML_IN_CANVAS = "--enable-features=CanvasDrawElement"
DISABLE_HTML_IN_CANVAS = "--disable-features=CanvasDrawElement"
EXPECTED_COUNT = 4


def wait_deck(page):
    page.wait_for_function(
        "window.__mirrorHome && window.__mirrorHome.deck",
        timeout=20000,
    )
    page.wait_for_timeout(300)
    return page.evaluate("window.__mirrorHome.deck.getState()")


def wait_unlocked(page):
    page.wait_for_function(
        "window.__mirrorHome.deck.getState().locked === false",
        timeout=8000,
    )
    return page.evaluate("window.__mirrorHome.deck.getState()")


def read_layout(page):
    return page.evaluate(
        """() => {
          const art = document.getElementById('art');
          const stage = document.getElementById('stage');
          const deck = document.getElementById('deck');
          const nav = document.getElementById('deckControls');
          const prev = document.getElementById('deckPrev');
          const next = document.getElementById('deckNext');
          const artRect = art.getBoundingClientRect();
          const deckRect = deck.getBoundingClientRect();
          const prevRect = prev.getBoundingClientRect();
          const nextRect = next.getBoundingClientRect();
          const deckStyle = getComputedStyle(deck);
          const cover = document.querySelector('.slide-cover');
          const coverTitle = cover.querySelector('.cover-title');
          const coverDate = cover.querySelector('.cover-date');
          const coverBrand = cover.querySelector('.cover-brand-text');
          const coverLockup = cover.querySelector('.cover-lockup');
          const coverMeta = cover.querySelector('.cover-meta');
          const coverSide = cover.querySelector('.cover-side');
          const coverSidePath = cover.querySelector('.cover-side path');
          const coverRule = document.getElementById('sheetRuleA');
          const coverStyle = getComputedStyle(cover);
          const rectOf = (element) => {
            const rect = element.getBoundingClientRect();
            return [rect.x, rect.y, rect.width, rect.height];
          };
          return {
            art: [artRect.x, artRect.y, artRect.width, artRect.height],
            deckRect: [deckRect.x, deckRect.y, deckRect.width, deckRect.height],
            artContainsDeck: art.contains(deck),
            stageContainsDeck: stage.contains(deck),
            stageContainsNav: stage.contains(nav),
            canvasCount: art.querySelectorAll('canvas').length,
            artText: art.textContent.replace(/\\s+/g, ' ').trim(),
            deckPosition: deckStyle.position,
            deckZ: deckStyle.zIndex,
            deckBackground: deckStyle.backgroundColor,
            deckParent: deck.parentElement.id,
            artOverflow: getComputedStyle(art).overflow,
            deckOverflow: deckStyle.overflow,
            sheetRules: document.querySelectorAll('.sheet-rule').length,
            sheetRuleFades: document.querySelectorAll('.sheet-rule[data-fade]').length,
            sheetRuleInSlide: !!document.querySelector('.slide .sheet-rule'),
            ruleMode: art.dataset.ruleMode,
            mirrorContainerType: getComputedStyle(
              document.querySelector('.mirror-content')
            ).containerType,
            cover: {
              hasHeader: !!cover.querySelector('.slide-kicker'),
              hasFooter: !!cover.querySelector('.slide-foot'),
              brandText: coverBrand.textContent.trim(),
              dateText: coverDate.textContent.trim(),
              titleText: coverTitle.textContent.trim(),
              brandFont: getComputedStyle(coverBrand).fontFamily,
              dateFont: getComputedStyle(coverDate).fontFamily,
              titleFont: getComputedStyle(coverTitle).fontFamily,
              brandAlign: getComputedStyle(coverBrand).textAlign,
              dateAlign: getComputedStyle(coverDate).textAlign,
              titleAlign: getComputedStyle(coverTitle).textAlign,
              brandDepth: Number(coverBrand.dataset.parallax),
              dateDepth: Number(coverDate.dataset.parallax),
              titleDepth: Number(coverTitle.dataset.parallax),
              brand: rectOf(coverBrand),
              date: rectOf(coverDate),
              lockup: rectOf(coverLockup),
              meta: rectOf(coverMeta),
              side: rectOf(coverSide),
              sideSvg: cover.querySelectorAll('.cover-side svg').length,
              sideLineWidth: getComputedStyle(coverSidePath).strokeWidth,
              rule: rectOf(coverRule),
              title: rectOf(coverTitle),
              textBorders: [
                getComputedStyle(coverBrand).borderTopWidth,
                getComputedStyle(coverDate).borderTopWidth,
                getComputedStyle(coverTitle).borderTopWidth
              ],
              borderTop: coverStyle.borderTopWidth,
              borderBottom: coverStyle.borderBottomWidth,
              paddingBottom: coverStyle.paddingBottom
            },
            navPointerEvents: getComputedStyle(nav).pointerEvents,
            navInert: nav.hasAttribute('inert'),
            prev: {
              x: prevRect.x, y: prevRect.y,
              right: prevRect.right, width: prevRect.width,
              height: prevRect.height, disabled: prev.disabled
            },
            next: {
              x: nextRect.x, y: nextRect.y,
              right: nextRect.right, width: nextRect.width,
              height: nextRect.height, disabled: next.disabled
            },
            slides: [...document.querySelectorAll('#deck .slide')].map((slide) => {
              const fadeItems = [...slide.querySelectorAll('[data-fade]')];
              return {
                index: Number(slide.dataset.slide),
                active: slide.classList.contains('is-active'),
                ariaHidden: slide.getAttribute('aria-hidden'),
                opacity: getComputedStyle(slide).opacity,
                visibility: getComputedStyle(slide).visibility,
                scrollWidth: slide.scrollWidth,
                scrollHeight: slide.scrollHeight,
                clientWidth: slide.clientWidth,
                clientHeight: slide.clientHeight,
                text: slide.textContent.replace(/\\s+/g, ' ').trim(),
                fadeCount: fadeItems.length,
                fadeInDelays: fadeItems.map((el) => Number(el.dataset.fadeInDelay)),
                fadeOutDelays: fadeItems.map((el) => Number(el.dataset.fadeOutDelay))
              };
            }),
            state: window.__mirrorHome.deck.getState()
          };
        }"""
    )


def assert_structure(page):
    layout = read_layout(page)
    check(layout["canvasCount"] == 1, f"expected one content canvas: {layout}")
    check(layout["artContainsDeck"] is True, f"deck is not inside mirrored content: {layout}")
    check(layout["stageContainsDeck"] is True, f"deck left the mirror stage: {layout}")
    check(layout["deckParent"] == "art", f"deck is not a child of #art: {layout}")
    check(layout["stageContainsNav"] is False, f"nav is inside mirrored content: {layout}")
    check("Mirror" in layout["artText"], f"deck text is missing from content: {layout}")
    for axis in range(4):
        check(abs(layout["art"][axis] - layout["deckRect"][axis]) <= 1,
              f"deck does not fill content: {layout}")
    check(layout["deckPosition"] == "absolute", f"deck position: {layout}")
    check(layout["deckZ"] == "1", f"deck z-index: {layout}")
    check(layout["deckBackground"] == "rgba(0, 0, 0, 0)",
          f"deck has a background: {layout}")
    check(layout["mirrorContainerType"] == "size",
          f"mirror container is not a size container: {layout}")
    check(layout["artOverflow"] == "hidden" and layout["deckOverflow"] == "hidden",
          f"sheet rules would not be clipped by the content: {layout}")
    check(layout["sheetRules"] == 2 and layout["sheetRuleFades"] == 0 and
          layout["sheetRuleInSlide"] is False,
          f"sheet rules are tied to the slide lifecycle: {layout}")
    check(layout["ruleMode"] == "bar",
          f"sheet rules do not start as the cover bar: {layout}")
    check(layout["navPointerEvents"] == "none", f"nav intercepts pointer: {layout}")
    check(layout["navInert"] is False, f"nav stayed inert after boot: {layout}")
    check(page.locator("#deckIndex").count() == 0,
          "page-number indicator should be removed")

    check(len(layout["slides"]) == EXPECTED_COUNT,
          f"expected {EXPECTED_COUNT} slides: {layout}")
    check(layout["state"]["index"] == 0 and layout["state"]["count"] == EXPECTED_COUNT,
          f"unexpected initial deck state: {layout['state']}")
    check(layout["prev"]["disabled"] is True, f"prev should start disabled: {layout}")
    check(layout["next"]["disabled"] is False, f"next should start enabled: {layout}")
    check(layout["prev"]["width"] <= 50 and layout["prev"]["height"] <= 45,
          f"prev is not compact: {layout}")
    check(layout["next"]["width"] <= 50 and layout["next"]["height"] <= 45,
          f"next is not compact: {layout}")
    check(layout["prev"]["x"] < 100 and layout["prev"]["y"] < 100,
          f"prev is not top-left: {layout}")
    check(layout["next"]["right"] > page.evaluate("innerWidth") - 100 and
          layout["next"]["y"] < 100,
          f"next is not top-right: {layout}")

    for index, slide in enumerate(layout["slides"]):
        check(slide["index"] == index, f"slide index mismatch: {slide}")
        check(slide["text"] != "", f"slide {index} is empty: {slide}")
        check(slide["ariaHidden"] == ("false" if index == 0 else "true"),
              f"slide aria-hidden: {slide}")
        check(slide["active"] is (index == 0), f"slide active state: {slide}")
        check(slide["opacity"] == "1", f"slide opacity should stay 1: {slide}")
        check(slide["fadeCount"] >= 3, f"not enough fade items: {slide}")
        check(len(set(slide["fadeInDelays"])) > 1,
              f"fade-in delays are not staggered: {slide}")
        check(len(set(slide["fadeOutDelays"])) > 1,
              f"fade-out delays are not staggered: {slide}")
    cover = layout["cover"]
    check(cover["hasHeader"] is False and cover["hasFooter"] is False,
          f"cover still has header/footer rules: {cover}")
    check(cover["brandText"] == "CEA GameJam" and
          cover["dateText"] == "2026.10" and
          cover["titleText"] == "参赛作品展示",
          f"cover copy does not match the reference: {cover}")
    for key in ("brandFont", "dateFont", "titleFont"):
        check("serif" in cover[key].lower(),
              f"cover {key} is not serif: {cover[key]}")
    for key in ("brandAlign", "dateAlign", "titleAlign"):
        check(cover[key] == "left", f"cover {key} is not left aligned: {cover[key]}")
    cover_depths = {cover["brandDepth"], cover["dateDepth"], cover["titleDepth"]}
    check(len(cover_depths) == 3 and min(cover_depths) > 0,
          f"cover text parallax depths are not distinct: {cover}")
    check(all(cover[key][2] > 0 and cover[key][3] > 0
              for key in ("brand", "date", "lockup", "side", "title")),
          f"cover layout is empty: {cover}")
    check(cover["brand"][2] > cover["date"][2] and
          cover["brand"][3] > cover["date"][3],
          f"cover brand/date sizes do not follow the reference: {cover}")
    check(cover["date"][1] >= cover["brand"][1] - 1 and
          abs((cover["date"][1] + cover["date"][3]) -
              (cover["brand"][1] + cover["brand"][3])) <= 4,
          f"cover date is not baseline-aligned with the brand: {cover}")
    check(cover["title"][1] >= cover["meta"][1] + cover["meta"][3] - 1,
          f"cover title overlaps the meta line: {cover}")
    check(abs(cover["title"][0] - cover["brand"][0]) <= 1,
          f"cover title is not left aligned with the brand: {cover}")
    check(cover["title"][0] + cover["title"][2] <= cover["side"][0] + 2,
          f"cover title overlaps the sideview slot: {cover}")
    check(abs((cover["lockup"][1] + cover["lockup"][3]) -
              (cover["side"][1] + cover["side"][3])) <= 1,
          f"cover text and sideview are not bottom aligned: {cover}")
    check(cover["side"][0] >= cover["lockup"][0] + cover["lockup"][2] - 1,
          f"cover sideview overlaps the text lockup: {cover}")
    check(cover["side"][2] < cover["lockup"][2],
          f"cover sideview is not narrower than the text: {cover}")
    check(cover["sideSvg"] == 1 and cover["sideLineWidth"] == "2px",
          f"cover sideview placeholder is not a 2px triangle: {cover}")
    check(all(value == "0px" for value in cover["textBorders"]),
          f"cover text still has a border: {cover['textBorders']}")
    check(cover["rule"][2] >= layout["art"][2] - 2 and cover["rule"][3] == 3,
          f"cover bottom rule does not span the content: {cover}")
    check(abs((cover["rule"][1] + cover["rule"][3]) -
              (layout["art"][1] + layout["art"][3])) <= 1,
          f"cover bottom rule is not at the content bottom: {cover}")
    content_bottom = max(
        cover["lockup"][1] + cover["lockup"][3],
        cover["side"][1] + cover["side"][3]
    )
    check(cover["rule"][1] >= content_bottom - 1,
          f"cover bottom rule overlaps the content: {cover}")
    check(abs(cover["rule"][1] - content_bottom - 32) <= 1,
          f"cover default bottom gap is wrong: {cover}")
    check(cover["borderTop"] == "0px" and cover["borderBottom"] == "0px",
          f"cover has an extra edge: {cover}")
    check("GameJam" in layout["slides"][0]["text"], f"cover copy missing: {layout}")
    if page.evaluate("window.__mirrorHome.mirror.mode") == "svg":
        glass_clip = page.evaluate(
            "getComputedStyle(document.querySelector('.mirror-glass')).clipPath"
        )
        check(glass_clip.startswith("path("),
              f"SVG glass is not clipped around the content: {glass_clip}")
    check("Interactive study" in layout["slides"][3]["text"],
          f"info copy missing: {layout}")
    return layout


def assert_quadrant_page(page):
    page.bring_to_front()
    page.wait_for_timeout(800)
    data = page.evaluate(
        """() => {
          const slide = document.querySelector('.slide-quadrants');
          const art = document.getElementById('art').getBoundingClientRect();
          const stage = document.getElementById('quadrantStage').getBoundingClientRect();
          const units = [...slide.querySelectorAll('[data-quadrant]')];
          const frames = [...slide.querySelectorAll('.quadrant-frame')];
          const filters = [...slide.querySelectorAll('.quadrant-filter')];
          const defs = [...slide.querySelectorAll('.quadrant-filter-defs filter')];
          const pointer = document.getElementById('quadrantPointer');
          const parallax = window.__mirrorHome.parallax;
          const state = window.__mirrorHome.quadrant.getState();
          const style = (el) => getComputedStyle(el);
          return {
            art: [art.x, art.y, art.width, art.height],
            stage: [stage.x, stage.y, stage.width, stage.height],
            unitNames: units.map((el) => el.dataset.quadrant),
            frameRects: frames.map((el) => {
              const r = el.getBoundingClientRect();
              return [r.x, r.y, r.width, r.height];
            }),
            frameBorders: frames.map((el) => style(el).borderTopWidth),
            frameBackgrounds: frames.map((el) => style(el).backgroundColor),
            sheetRules: [...document.querySelectorAll('.sheet-rule')].map((el) => {
              const r = el.getBoundingClientRect();
              return {
                id: el.id,
                rect: [r.x, r.y, r.width, r.height],
                top: style(el).top,
                transform: style(el).transform
              };
            }),
            titleFonts: units.map((el) => style(el.querySelector('.quadrant-title')).fontFamily),
            titleAligns: units.map((el) => style(el.querySelector('.quadrant-title')).textAlign),
            filterRects: filters.map((el) => {
              const r = el.getBoundingClientRect();
              return [r.x, r.y, r.width, r.height];
            }),
            filterValues: filters.map((el) => style(el).backdropFilter),
            filterZ: filters.map((el) => Number(style(el).zIndex)),
            slideZ: Number(style(slide).zIndex),
            contentZ: Number(style(slide.querySelector('.quadrant-content')).zIndex),
            pointerZ: Number(style(pointer).zIndex),
            pointerParent: pointer.parentElement?.id || null,
            centerZ: Number(style(slide.querySelector('.quadrant-center')).zIndex),
            centerBackground: style(slide.querySelector('.quadrant-center')).backgroundColor,
            centerBorder: style(slide.querySelector('.quadrant-center')).borderTopWidth,
            centerRect: (() => {
              const r = slide.querySelector('.quadrant-center').getBoundingClientRect();
              return [r.x, r.y, r.width, r.height];
            })(),
            centerParallax: Number(
              slide.querySelector('.quadrant-center-word').dataset.parallax
            ),
            ruleParallax: document.querySelectorAll('.sheet-rule[data-parallax]').length,
            filterParallax: slide.querySelectorAll('.quadrant-filter[data-parallax]').length,
            unitParallax: units.map((el) => el.querySelectorAll('[data-parallax]').length),
            titles: units.map((el) => el.querySelector('.quadrant-title').textContent.trim()),
            details: units.map((el) => el.querySelector('.quadrant-detail').textContent.trim()),
            filterOpacities: filters.map((el) => Number(style(el).opacity)),
            filterFadeCount: slide.querySelectorAll('.quadrant-filter[data-fade]').length,
            filterDefs: defs.map((filter) => ({
              id: filter.id,
              floods: [...filter.querySelectorAll('feFlood')].map((el) => el.getAttribute('flood-color')),
              blends: [...filter.querySelectorAll('feBlend')].map((el) => el.getAttribute('mode')),
              saturates: [...filter.querySelectorAll('feColorMatrix')].map((el) => ({
                type: el.getAttribute('type'),
                values: el.getAttribute('values')
              }))
            })),
            defsId: slide.querySelector('.quadrant-filter-defs')?.id || null,
            pointerColor: style(pointer).color,
            pointerDisplay: style(pointer).display,
            pointerHasRing: !!pointer.querySelector('.quadrant-pointer-ring'),
            pointerSvgCount: pointer.querySelectorAll('svg').length,
            ringSize: style(pointer).getPropertyValue('--quad-ring-size').trim(),
            ringStroke: style(pointer).getPropertyValue('--quad-ring-stroke').trim(),
            artCursor: style(document.getElementById('art')).cursor,
            ruleMode: document.getElementById('art').dataset.ruleMode,
            legacyRules: slide.querySelectorAll('.quadrant-rule').length,
            parallaxLayers: parallax ? parallax.getState().layers.map((layer) => layer.depth) : null,
            parallaxMax: parallax ? parallax.getState().maxShiftPx : null,
            outsideParallax: document.querySelectorAll(
              '.slide-quadrants ~ * [data-parallax], body > [data-parallax]'
            ).length,
            state
          };
        }"""
    )

    check(data["unitNames"] == ["time", "theme", "limit", "score"],
          f"quadrant names: {data['unitNames']}")
    check(data["titles"] == ["时间", "主题", "限制", "评分"],
          f"quadrant titles: {data['titles']}")
    expected_details = [
        ["10月23日到10月25日", "传统 48 小时 GameJam 模式"],
        ["镜", "光路的魔术", "从镜中看到怎样的玩法？", "从镜中诞生怎样的世界？"],
        [
            "美术呈现只能使用不多于三个色相",
            "鼓励用简洁的颜色凸显玩法与创意",
            "保留可供风格化的发挥空间",
        ],
        ["各队展示后互评", "美术、创意、切题、完成度", "评委作为单独队伍参与打分"],
    ]
    for index, fragments in enumerate(expected_details):
        for fragment in fragments:
            check(fragment in data["details"][index],
                  f"quadrant {index} detail copy is missing {fragment!r}: {data['details'][index]}")
    check(all("serif" in font.lower() for font in data["titleFonts"]),
          f"quadrant titles are not serif: {data['titleFonts']}")
    check(all(align == "center" for align in data["titleAligns"]),
          f"quadrant titles are not centred: {data['titleAligns']}")
    widths = [rect[2] for rect in data["frameRects"]]
    check(len(widths) == 4 and max(widths) - min(widths) <= 0.5,
          f"quadrant frames are not equal width: {data['frameRects']}")
    check(all(r[3] >= 104 for r in data["frameRects"]),
          f"quadrant copy blocks collapsed below their minimum height: {data['frameRects']}")
    check(all(width == "0px" for width in data["frameBorders"]),
          f"quadrant copy still has a visible outer border: {data['frameBorders']}")
    check(all(background == "rgba(0, 0, 0, 0)"
              for background in data["frameBackgrounds"]),
          f"quadrant copy has an opaque background: {data['frameBackgrounds']}")
    stage = data["stage"]
    stage_width, stage_height = stage[2], stage[3]
    check(data["ruleMode"] == "cross",
          f"sheet rules did not enter cross mode: {data['ruleMode']}")
    check(data["legacyRules"] == 0,
          f"old quadrant rules are still in the DOM: {data['legacyRules']}")
    check(len(data["sheetRules"]) == 2,
          f"expected two persistent sheet rules: {data['sheetRules']}")
    if len(data["sheetRules"]) == 2:
        horizontal, vertical = data["sheetRules"]
        rule_length = 2 * max(stage_width, stage_height)
        check(horizontal["rect"][2] >= rule_length - 1 and
              abs(horizontal["rect"][3] - 3) <= 0.5,
              f"horizontal sheet rule is too short: {horizontal}")
        check(abs(vertical["rect"][2] - 3) <= 0.5 and
              vertical["rect"][3] >= rule_length - 1,
              f"vertical sheet rule is too short: {vertical}")
    frames = data["frameRects"]
    corners = [(-1, -1), (1, -1), (-1, 1), (1, 1)]
    for index, ((sx, sy), frame) in enumerate(zip(corners, frames)):
        center_x = frame[0] + frame[2] / 2
        center_y = frame[1] + frame[3] / 2
        quadrant_x = stage[0] + stage[2] * (0.25 if index % 2 == 0 else 0.75)
        quadrant_y = stage[1] + stage[3] * (0.25 if index < 2 else 0.75)
        check((center_x - quadrant_x) * sx > 10 and
              (center_y - quadrant_y) * sy > 8,
              f"quadrant {index} copy did not move toward its corner: "
              f"{[center_x, center_y]} vs {[quadrant_x, quadrant_y]}")
        check(frame[0] >= stage[0] and frame[0] + frame[2] <= stage[0] + stage[2] and
              frame[1] >= stage[1] and frame[1] + frame[3] <= stage[1] + stage[3],
              f"quadrant {index} copy escaped the content: {frame} in {stage}")
    check(len(data["filterRects"]) == 4, f"expected four tint panels: {data}")
    check(data["filterValues"] == [
        'url("#quad-tint-red")', 'url("#quad-tint-green")',
        'url("#quad-tint-blue")', 'url("#quad-tint-gray")'
    ], f"filter panels do not reference their SVG filters: {data['filterValues']}")
    check(data["filterDefs"][0]["floods"] == ["#ff2b2b"] and
          data["filterDefs"][0]["blends"] == ["screen"],
          f"red filter is not a screen tint: {data['filterDefs']}")
    check(data["filterDefs"][1]["floods"] == ["#00c853"] and
          data["filterDefs"][1]["blends"] == ["screen"],
          f"green filter is not a screen tint: {data['filterDefs']}")
    check(data["filterDefs"][2]["floods"] == ["#1f52ff"] and
          data["filterDefs"][2]["blends"] == ["screen"],
          f"blue filter is not a screen tint: {data['filterDefs']}")
    check(data["filterDefs"][3]["saturates"] == [{"type": "saturate", "values": "0"}],
          f"grayscale filter is not saturation removal: {data['filterDefs']}")
    check(data["filterFadeCount"] == 4 and
          all(opacity > 0.99 for opacity in data["filterOpacities"]),
          f"filter panels are not fully faded in: {data['filterOpacities']}")
    check(data["pointerParent"] == "deck" and data["pointerZ"] == 0 and
          data["slideZ"] == 1,
          f"pointer is not a deck-level layer below the slides: {data}")
    check(data["contentZ"] < data["centerZ"] < min(data["filterZ"]),
          f"content/centre/filter stacking order is wrong: {data}")
    check(data["centerBackground"] == "rgba(0, 0, 0, 0)" and
          data["centerBorder"] == "0px",
          f"centre mark still has a frame: {data}")
    check(data["filterParallax"] == 0 and data["ruleParallax"] == 0,
          f"filters or rules received parallax: {data}")
    check(data["centerParallax"] >= 0.8 and
          len(set(data["parallaxLayers"] or [])) >= 3,
          f"quadrant parallax depths are missing: {data}")
    check(data["parallaxMax"] >= 8, f"parallax shift is missing: {data}")
    check(data["artCursor"] == "auto", f"native cursor is hidden: {data}")
    check(data["pointerHasRing"] is True and data["pointerSvgCount"] == 0,
          f"custom pointer is not a ring: {data}")
    check(data["pointerColor"] == "rgb(157, 157, 157)",
          f"pointer is not light grey: {data['pointerColor']}")

    # Move to each quadrant; the hover state uses the raw pointer target, so
    # the copy switch is immediate.
    art = data["art"]
    points = {
        "time": (0.25, 0.25),
        "theme": (0.75, 0.25),
        "limit": (0.25, 0.75),
        "score": (0.75, 0.75)
    }
    for name, (nx, ny) in points.items():
        page.mouse.move(art[0] + art[2] * nx, art[1] + art[3] * ny, steps=3)
        page.wait_for_timeout(260)
        state = page.evaluate("window.__mirrorHome.quadrant.getState()")
        check(state["hover"] == name, f"quadrant {name} did not activate: {state}")
        visible = page.evaluate(
            """(name) => {
              const unit = document.querySelector(`[data-quadrant="${name}"]`);
              return {
                title: Number(getComputedStyle(unit.querySelector('.quadrant-title')).opacity),
                detail: Number(getComputedStyle(unit.querySelector('.quadrant-detail')).opacity)
              };
            }""",
            name,
        )
        check(visible["title"] < 0.1 and visible["detail"] > 0.9,
              f"quadrant copy did not reveal: {name} {visible}")

    # The centre mark keeps an invisible dead zone for hover copy. There is no
    # frame, so the custom ring stays visible under the mark.
    page.mouse.move(art[0] + art[2] / 2, art[1] + art[3] / 2, steps=3)
    page.wait_for_timeout(120)
    center = page.evaluate("window.__mirrorHome.quadrant.getState()")
    cursor = page.evaluate(
        "getComputedStyle(document.getElementById('art')).cursor"
    )
    check(center["inCenter"] is True and center["hover"] is None,
          f"centre did not clear quadrant hover: {center}")
    check(center["shown"] is True, f"custom pointer disappeared at centre: {center}")
    check(cursor == "auto", f"native cursor disappeared at centre: {cursor}")

    # The ring grows and thins with speed, then returns to its small/thick
    # resting state. The ring centre tracks the raw pointer, not a trail.
    page.mouse.move(art[0] + art[2] * 0.2, art[1] + art[3] * 0.2, steps=1)
    page.wait_for_timeout(1200)
    rest = page.evaluate("window.__mirrorHome.quadrant.getState()")
    check(rest["speed"] < 30 and rest["ring"]["size"] <= 40,
          f"ring did not settle to rest: {rest}")
    page.mouse.move(art[0] + art[2] * 0.8, art[1] + art[3] * 0.22, steps=18)
    page.wait_for_timeout(20)
    fast = page.evaluate("window.__mirrorHome.quadrant.getState()")
    check(fast["speed"] > rest["speed"] + 100,
          f"ring speed did not rise: {rest} -> {fast}")
    check(fast["ring"]["size"] > rest["ring"]["size"] + 15,
          f"ring did not grow with speed: {rest} -> {fast}")
    check(fast["ring"]["stroke"] < rest["ring"]["stroke"] - 1.5,
          f"ring did not thin with speed: {rest} -> {fast}")
    check(abs(fast["current"]["x"] - fast["target"]["x"]) <= 0.5 and
          abs(fast["current"]["y"] - fast["target"]["y"]) <= 0.5,
          f"ring centre did not track the pointer: {fast}")
    page.wait_for_timeout(1400)
    back = page.evaluate("window.__mirrorHome.quadrant.getState()")
    check(back["ring"]["size"] <= 40 and back["ring"]["stroke"] >= 4.5,
          f"ring did not return to rest: {fast} -> {back}")

    print("quadrant page: ok")


def assert_rank_page(page):
    page.evaluate("window.__mirrorHome.deck.goTo(2)")
    wait_unlocked(page)
    page.wait_for_timeout(800)
    data = page.evaluate(
        """() => {
          const art = document.getElementById('art').getBoundingClientRect();
          const board = document.querySelector('.slide-rank .rank-board');
          const boardRect = board.getBoundingClientRect();
          const cards = [...document.querySelectorAll('.slide-rank .rank-card')];
          const rules = [...document.querySelectorAll('.sheet-rule')].map((el) => {
            const rect = el.getBoundingClientRect();
            return rect.x + rect.width / 2;
          });
          return {
            mode: document.getElementById('art').dataset.ruleMode,
            art: [art.x, art.y, art.width, art.height],
            board: [boardRect.x, boardRect.y, boardRect.width, boardRect.height],
            scroll: [board.scrollHeight, board.clientHeight],
            overflowX: getComputedStyle(board).overflowX,
            overflowY: getComputedStyle(board).overflowY,
            labels: [...document.querySelectorAll('.rank-side-title')].map((el) => {
              const rect = el.getBoundingClientRect();
              const style = getComputedStyle(el);
              return {
                text: el.textContent.trim(),
                writingMode: style.writingMode,
                fontSize: Number.parseFloat(style.fontSize),
                depth: Number(el.dataset.parallax),
                rect: [rect.x, rect.y, rect.width, rect.height],
                transform: el.style.transform
              };
            }),
            cards: cards.length,
            cardBorder: getComputedStyle(cards[0]).borderTopWidth,
            cardHeights: cards.map((card) => card.getBoundingClientRect().height),
            firstCard: cards[0] ? {
              classes: [...cards[0].classList],
              number: cards[0].querySelector('.rank-number')?.textContent.trim(),
              work: cards[0].querySelector('.rank-work')?.textContent.trim(),
              team: cards[0].querySelector('.rank-team')?.textContent.trim(),
              score: cards[0].querySelector('.rank-score')?.textContent.trim(),
              awards: [...cards[0].querySelectorAll('.rank-award')].map((el) => el.textContent.trim()),
              criteria: [...cards[0].querySelectorAll('.rank-criterion')].map((el) => ({
                label: el.querySelector('.rank-criterion-label')?.textContent.trim(),
                value: el.querySelector('.rank-criterion-value')?.textContent.trim(),
                award: el.classList.contains('is-award'),
                color: getComputedStyle(el).color
              })),
              rankColor: getComputedStyle(cards[0].querySelector('.rank-number')).color,
              scoreColor: getComputedStyle(cards[0].querySelector('.rank-score')).color
            } : null,
            podiumColors: cards.slice(0, 3).map((card) =>
              getComputedStyle(card.querySelector('.rank-number')).color
            ),
            podiumScores: cards.slice(0, 3).map((card) =>
              getComputedStyle(card.querySelector('.rank-score')).color
            ),
            tieLabels: cards.map((card) =>
              card.querySelector('.rank-tie')?.textContent.trim() || null
            ),
            rules
          };
        }"""
    )
    check(data["mode"] == "rank",
          f"ranking page did not switch the sheet rules: {data['mode']}")
    labels = data["labels"]
    check([label["text"] for label in labels] == ["评分排行", "Rank list"],
          f"ranking rail labels: {labels}")
    check(all(label["writingMode"] == "horizontal-tb" for label in labels),
          f"ranking labels are not horizontal: {labels}")
    check(labels[0]["fontSize"] > labels[1]["fontSize"] * 1.5,
          f"ranking label hierarchy is missing: {labels}")
    check(len({label["depth"] for label in labels}) == 1 and labels[0]["depth"] > 0,
          f"ranking labels do not share one parallax depth: {labels}")
    upper_label, lower_label = labels
    upper = upper_label["rect"]
    lower = lower_label["rect"]
    art_left, art_top, _, art_height = data["art"]
    rail_left = upper[0] - art_left
    check(abs(upper[0] - lower[0]) <= 1,
          f"ranking labels are not aligned in one rail: {labels}")
    check(lower[1] - (upper[1] + upper[3]) >= 8,
          f"ranking labels are not stacked with a gap: {labels}")
    check(8 <= rail_left <= 64,
          f"ranking rail is not inset from the left edge: {rail_left} {labels}")
    stack_center = (upper[1] + lower[1] + lower[3]) / 2
    check(abs(stack_center - (art_top + art_height / 2)) <= art_height * 0.08,
          f"ranking rail is not vertically centred: {labels} {data['art']}")
    for label in labels:
        right = label["rect"][0] + label["rect"][2]
        check(right < data["rules"][0] - 4,
              f"ranking labels cross the left rule: {labels} {data['rules']}")
        check(right < data["board"][0] - 4,
              f"ranking labels overlap the list: {labels} {data['board']}")
    check(data["cards"] == 15,
          f"expected fifteen ranking teams: {data['cards']}")
    first = data["firstCard"]
    check(first and first["number"] == "#1" and first["work"] == "镜界" and
          first["team"] == "吴彦组" and first["score"] == "7.93",
          f"ranking card content is wrong: {first}")
    check(first["awards"] == ["完成度奖"],
          f"ranking award tag is wrong: {first}")
    check(first["classes"].count("is-first") == 1 and
          "is-podium" in first["classes"],
          f"ranking podium classes are wrong: {first['classes']}")
    check(first["rankColor"] == "rgb(216, 74, 51)" and
          first["scoreColor"] == "rgb(216, 74, 51)",
          f"ranking accent is missing: {first}")
    check(all(color == "rgb(216, 74, 51)" for color in data["podiumColors"]),
          f"podium ranks are not accented: {data['podiumColors']}")
    check(data["podiumScores"][0] == "rgb(216, 74, 51)" and
          all(color != "rgb(216, 74, 51)" for color in data["podiumScores"][1:]),
          f"first-place score accent is wrong: {data['podiumScores']}")
    award_cells = [cell for cell in first["criteria"] if cell["award"]]
    check(len(award_cells) == 1 and award_cells[0]["label"] == "完成度" and
          award_cells[0]["color"] == "rgb(216, 74, 51)",
          f"award criterion is not accented: {first['criteria']}")
    check(all(cell["color"] != "rgb(216, 74, 51)"
              for cell in first["criteria"] if not cell["award"]),
          f"non-award criteria are accented: {first['criteria']}")
    check(data["tieLabels"][5] == "并列" and data["tieLabels"][6] == "并列",
          f"tied ranks are not labelled: {data['tieLabels']}")
    check(data["scroll"][0] > data["scroll"][1] + 40,
          f"ranking list is not scrollable: {data['scroll']}")
    check(data["overflowX"] == "hidden" and data["overflowY"] == "auto",
          f"ranking list scroll axes are wrong: {data}")
    check(data["board"][2] / data["art"][2] > 0.54,
          f"ranking list is too narrow: {data['board']} in {data['art']}")
    check(all(height > 90 for height in data["cardHeights"]),
          f"ranking cards are too short: {data['cardHeights']}")
    check(abs(float(data["cardBorder"].replace("px", "")) - 1) <= 0.5,
          f"ranking card border: {data['cardBorder']}")
    check(abs(data["rules"][0] - (data["art"][0] + data["art"][2] * 0.3)) <= 2 and
          abs(data["rules"][1] - (data["art"][0] + data["art"][2] * 0.9)) <= 2,
          f"ranking rules are not at the 30/90 columns: {data['rules']}")
    check((data["art"][0] + data["art"][2] * 0.9) -
          (data["board"][0] + data["board"][2]) > 4,
          f"ranking scrollbar sits too close to the right rule: {data}")

    # The line itself must hand the wheel to the list when the pointer is on
    # the boundary, even though the rule has pointer-events:none.
    page.mouse.move(data["rules"][0] - 1, data["art"][1] + data["art"][3] / 2, steps=3)
    page.mouse.wheel(0, 120)
    page.wait_for_timeout(220)
    line_scroll = page.evaluate(
        """() => ({
          index: window.__mirrorHome.deck.getState().index,
          scrollTop: document.querySelector('.slide-rank .rank-board').scrollTop
        })"""
    )
    check(line_scroll["index"] == 2 and line_scroll["scrollTop"] > 0,
          f"ranking boundary did not take the wheel: {line_scroll}")
    page.evaluate("document.querySelector('.slide-rank .rank-board').scrollTop = 0")
    page.wait_for_timeout(100)

    board = data["board"]
    page.mouse.move(board[0] + board[2] / 2, board[1] + board[3] / 2, steps=4)
    page.mouse.wheel(0, 160)
    page.wait_for_timeout(40)
    early = page.evaluate(
        """() => ({
          index: window.__mirrorHome.deck.getState().index,
          scroll: window.__mirrorHome.rank.getState().scroll
        })"""
    )
    check(early["index"] == 2 and early["scroll"]["animating"] and
          early["scroll"]["target"] > early["scroll"]["top"] + 1,
          f"ranking scroll is not interpolated: {early}")
    page.wait_for_timeout(600)
    scrolled = page.evaluate(
        """() => ({
          index: window.__mirrorHome.deck.getState().index,
          scroll: window.__mirrorHome.rank.getState().scroll
        })"""
    )
    check(scrolled["index"] == 2 and scrolled["scroll"]["top"] > 0 and
          not scrolled["scroll"]["animating"] and
          abs(scrolled["scroll"]["top"] - scrolled["scroll"]["target"]) < 1,
          f"ranking interpolation did not settle independently of the deck: {scrolled}")
    page.evaluate("document.querySelector('.slide-rank .rank-board').scrollTop = 0")
    page.wait_for_timeout(120)

    card = page.locator('.slide-rank .rank-card').first
    box = card.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=4)
    page.wait_for_timeout(300)
    hover = page.evaluate(
        """() => {
          const card = document.querySelector('.slide-rank .rank-card');
          const style = getComputedStyle(card);
          return {
            background: style.backgroundColor,
            scale: Number(style.scale),
            depth: Number(card.dataset.parallax),
            rank: window.__mirrorHome.rank.getState()
          };
        }"""
    )
    check(hover["background"] == "rgba(0, 0, 0, 0)",
          f"ranking card still fills white on hover: {hover}")
    check(hover["scale"] > 1.01 and hover["depth"] > 0.5,
          f"ranking card did not scale or move nearer: {hover}")
    check(hover["rank"]["hovered"] == "吴彦组",
          f"ranking parallax did not track the hovered card: {hover}")
    page.mouse.click(box["x"] + box["width"] * 0.55,
                     box["y"] + box["height"] * 0.72)
    page.wait_for_timeout(80)
    page.mouse.move(data["art"][0] + data["art"][2] * 0.08,
                    data["art"][1] + data["art"][3] * 0.5, steps=4)
    page.wait_for_timeout(220)
    reset = page.evaluate(
        """() => ({
          depth: Number(document.querySelector('.slide-rank .rank-card').dataset.parallax),
          hover: window.__mirrorHome.rank.getState().hovered
        })"""
    )
    check(reset["hover"] is None and reset["depth"] < 0.4,
          f"ranking card depth did not reset: {reset}")
    print("ranking page: ok")


def assert_pointer_all_slides(page):
    art = page.evaluate(
        """() => {
          const r = document.getElementById('art').getBoundingClientRect();
          return {x: r.x, y: r.y, width: r.width, height: r.height};
        }"""
    )
    for index in (0, 2, 3):
        if page.evaluate("window.__mirrorHome.deck.getState().index") != index:
            page.evaluate(f"window.__mirrorHome.deck.goTo({index})")
            wait_unlocked(page)
            page.wait_for_timeout(300)

        page.mouse.move(
            art["x"] + art["width"] * 0.5,
            art["y"] + art["height"] * 0.2,
            steps=4,
        )
        page.wait_for_timeout(350)
        state = page.evaluate("window.__mirrorHome.quadrant.getState()")
        visible = page.evaluate(
            "document.getElementById('quadrantPointer').classList.contains('is-visible')"
        )
        check(state["active"] is True and state["shown"] is True and visible,
              f"pointer ring is missing on slide {index}: {state}")
        check(state["hover"] is None,
              f"non-quadrant slide kept a quadrant hover: {state}")
        check(page.evaluate(
            "document.getElementById('quadrantPointer').parentElement.id"
        ) == "deck", "pointer ring is not a deck-level layer")

    # Return to the cover and confirm the ring yields to the paging chrome.
    page.evaluate("window.__mirrorHome.deck.goTo(0)")
    wait_unlocked(page)
    nav = page.locator("#deckNext").bounding_box()
    page.mouse.move(nav["x"] + nav["width"] / 2, nav["y"] + nav["height"] / 2, steps=3)
    page.wait_for_timeout(220)
    check(page.evaluate(
        "document.getElementById('quadrantPointer').classList.contains('is-visible')"
    ) is False, "pointer ring stayed visible over the paging controls")
    print("pointer all slides: ok")


def assert_navigation(page):
    page.locator("#deckNext").click()
    immediate = page.evaluate("window.__mirrorHome.deck.getState()")
    check(immediate["locked"] is True, f"transition did not lock the deck: {immediate}")
    check(page.locator("#deckPrev").is_disabled() and page.locator("#deckNext").is_disabled(),
          "navigation stayed enabled during the fade")
    page.wait_for_timeout(100)
    mid = page.evaluate(
        """() => {
          const outgoing = document.querySelector('[data-slide="0"]');
          const items = [...outgoing.querySelectorAll('[data-fade]')];
          return {
            state: window.__mirrorHome.deck.getState(),
            delays: items.map((el) => Number(el.dataset.fadeOutDelay)),
            opacities: items.map((el) => Number(getComputedStyle(el).opacity)),
            animationDelays: items.map((el) =>
              el.getAnimations().map((a) => a.effect.getTiming().delay)
            )
          };
        }"""
    )
    check(len(set(mid["delays"])) > 1, f"fade-out delays are not staggered: {mid}")
    check(len(set(round(value, 2) for value in mid["opacities"])) > 1,
          f"fade-out opacities are not staggered: {mid}")
    check(all(len(delays) for delays in mid["animationDelays"]),
          f"fade-out animations are missing: {mid}")
    check(mid["state"]["locked"] is True and mid["state"]["index"] == 0,
          f"deck advanced before fade-out completed: {mid['state']}")

    wait_unlocked(page)
    after_next = read_layout(page)
    complete = page.evaluate(
        """() => {
          const active = document.querySelector('#deck .slide.is-active');
          const outgoing = document.querySelector('[data-slide="0"]');
          return {
            active: [...active.querySelectorAll('[data-fade]')].map(
              (el) => Number(getComputedStyle(el).opacity)
            ),
            outgoing: [...outgoing.querySelectorAll('[data-fade]')].map(
              (el) => Number(getComputedStyle(el).opacity)
            )
          };
        }"""
    )
    check(all(value > 0.99 for value in complete["active"]),
          f"active fade-in did not finish: {complete}")
    check(all(value < 0.01 for value in complete["outgoing"]),
          f"outgoing fade-out did not finish: {complete}")
    check(after_next["state"]["index"] == 1, f"next did not advance: {after_next['state']}")
    check(after_next["slides"][1]["active"] is True and
          after_next["slides"][0]["active"] is False,
          f"active slide did not swap: {after_next}")
    check(float(after_next["slides"][1]["opacity"]) > 0.99 and
          after_next["slides"][0]["visibility"] == "hidden",
          f"fade did not complete: {after_next}")
    check(after_next["prev"]["disabled"] is False, f"prev should enable: {after_next}")

    assert_quadrant_page(page)

    page.keyboard.press("End")
    page.wait_for_function(
        """() => {
          const filters = [...document.querySelectorAll('.quadrant-filter')];
          return filters.length === 4 && filters.every((el) =>
            el.getAnimations().some((animation) => animation.id === 'mirror-fade')
          );
        }""",
        timeout=2000,
    )
    fading_filters = page.evaluate(
        """() => [...document.querySelectorAll('.quadrant-filter')].map((el) =>
          el.getAnimations()
            .filter((animation) => animation.id === 'mirror-fade')
            .map((animation) => animation.effect.getTiming().duration)
        )"""
    )
    check(len(fading_filters) == 4 and
          all(durations and all(duration == 220 for duration in durations)
              for durations in fading_filters),
          f"filter panels are not in the 220ms fade group: {fading_filters}")
    wait_unlocked(page)
    last = read_layout(page)
    check(last["state"]["index"] == EXPECTED_COUNT - 1, f"End did not reach last: {last}")
    check(last["next"]["disabled"] is True, f"next should disable at end: {last}")

    page.keyboard.press("Home")
    wait_unlocked(page)
    first = read_layout(page)
    check(first["state"]["index"] == 0, f"Home did not return to first: {first}")
    check(first["prev"]["disabled"] is True, f"prev should disable at start: {first}")

    page.keyboard.press("ArrowRight")
    wait_unlocked(page)
    check(page.evaluate("window.__mirrorHome.deck.getState().index") == 1,
          "ArrowRight did not advance")
    page.keyboard.press("ArrowLeft")
    wait_unlocked(page)
    check(page.evaluate("window.__mirrorHome.deck.getState().index") == 0,
          "ArrowLeft did not go back")

    rect = page.evaluate(
        """() => {
          const r = document.getElementById('art').getBoundingClientRect();
          return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
        }"""
    )
    page.mouse.move(rect["x"], rect["y"])
    page.mouse.wheel(0, 140)
    wait_unlocked(page)
    check(page.evaluate("window.__mirrorHome.deck.getState().index") == 1,
          "wheel down did not advance")
    page.wait_for_timeout(950)
    page.mouse.wheel(0, -140)
    wait_unlocked(page)
    check(page.evaluate("window.__mirrorHome.deck.getState().index") == 0,
          "wheel up did not go back")
    return first, last


def assert_structure_veil(page):
    initial = page.evaluate(
        """() => {
          const veil = document.getElementById('structureVeil');
          const art = document.getElementById('art').getBoundingClientRect();
          return {
            hidden: !veil.classList.contains('is-visible'),
            outsideArt: !document.getElementById('art').contains(veil),
            pointerEvents: getComputedStyle(veil).pointerEvents,
            z: Number(getComputedStyle(veil).zIndex),
            regions: veil.querySelectorAll('.structure-veil-region').length,
            resizing: veil.querySelector('.structure-veil-resizing')?.textContent || '',
            width: document.getElementById('structureWidth').textContent,
            height: document.getElementById('structureHeight').textContent,
            artWidth: `${Math.round(art.width)}px`,
            artHeight: `${Math.round(art.height)}px`
          };
        }"""
    )
    check(initial["hidden"] and initial["outsideArt"],
          f"structure veil is visible on load or inside the mirror: {initial}")
    check(initial["pointerEvents"] == "none" and 70 < initial["z"] < 80,
          f"structure veil layering is wrong: {initial}")
    check(initial["regions"] == 4 and initial["resizing"] == "resizing...",
          f"structure veil diagram is incomplete: {initial}")
    check(initial["width"] == initial["artWidth"] and
          initial["height"] == initial["artHeight"],
          f"structure veil dimensions are stale: {initial}")

    page.set_viewport_size({"width": 1120, "height": 820})
    page.wait_for_timeout(120)
    early = page.evaluate(
        """() => {
          const veil = document.getElementById('structureVeil');
          return {
            visible: veil.classList.contains('is-visible'),
            opacity: Number(getComputedStyle(veil).opacity),
            width: document.getElementById('structureWidth').textContent,
            height: document.getElementById('structureHeight').textContent
          };
        }"""
    )
    check(early["visible"] and early["opacity"] > 0,
          f"structure veil did not fade in on resizeStart: {early}")
    check(early["width"] != initial["width"] or
          early["height"] != initial["height"],
          f"structure veil measures did not update at resizeStart: "
          f"{initial} -> {early}")
    page.wait_for_timeout(730)
    active = page.evaluate(
        """() => {
          const veil = document.getElementById('structureVeil');
          const style = getComputedStyle(veil);
          const art = document.getElementById('art').getBoundingClientRect();
          return {
            visible: veil.classList.contains('is-visible'),
            opacity: Number(style.opacity),
            visibility: style.visibility,
            width: document.getElementById('structureWidth').textContent,
            height: document.getElementById('structureHeight').textContent,
            artWidth: `${Math.round(art.width)}px`,
            artHeight: `${Math.round(art.height)}px`
          };
        }"""
    )
    check(active["visible"] and active["visibility"] == "visible" and
          active["opacity"] > 0.05,
          f"structure veil did not pulse on resize: {active}")
    check(active["width"] == active["artWidth"] and
          active["height"] == active["artHeight"],
          f"structure veil dimensions did not follow the resize: {active}")

    page.wait_for_timeout(1800)
    settled = page.evaluate(
        """() => {
          const veil = document.getElementById('structureVeil');
          const style = getComputedStyle(veil);
          return {
            visible: veil.classList.contains('is-visible'),
            opacity: Number(style.opacity),
            visibility: style.visibility
          };
        }"""
    )
    check(settled["visible"] is False and
          (settled["opacity"] < 0.01 or settled["visibility"] == "hidden"),
          f"structure veil did not fade out: {settled}")
    print("structure veil: ok")


def assert_cover_tuning(page):
    if page.locator("#tuneBody").is_hidden():
        page.locator("#tuneToggle").click()
        page.wait_for_timeout(120)

    def set_cover(id_, value):
        page.locator(f"#{id_}").evaluate(
            "(el, value) => { el.value = String(value); "
            "el.dispatchEvent(new Event('input', { bubbles: true })); }",
            value,
        )

    check(page.locator("#tuneCoverGap").count() == 0,
          "cover gap should be fixed, not adjustable")
    check(page.locator("#tuneCoverTextY").count() == 0,
          "cover text translate should be fixed, not adjustable")

    set_cover("tuneCoverBar", 6)
    set_cover("tuneCoverArtY", 0)
    page.wait_for_timeout(850)
    baseline = page.evaluate(
        """() => {
          const cover = document.querySelector('.slide-cover');
          const lockup = cover.querySelector('.cover-lockup').getBoundingClientRect();
          const brand = cover.querySelector('.cover-brand-text').getBoundingClientRect();
          const side = cover.querySelector('.cover-side').getBoundingClientRect();
          const rule = document.getElementById('sheetRuleA').getBoundingClientRect();
          const rootStyle = getComputedStyle(document.documentElement);
          return {
            brandTop: brand.top,
            sideTop: side.top,
            ruleHeight: rule.height,
            bottomGap: rule.top - Math.max(lockup.bottom, side.bottom),
            gapVar: rootStyle.getPropertyValue('--cover-bottom-gap').trim(),
            textYVar: rootStyle.getPropertyValue('--cover-text-y').trim(),
            lineWidth: getComputedStyle(
              cover.querySelector('.cover-side path')
            ).strokeWidth,
            readout: [
              document.getElementById('tuneCoverBarValue').textContent,
              document.getElementById('tuneCoverGapFixed').textContent,
              document.getElementById('tuneCoverTextYFixed').textContent,
              document.getElementById('tuneCoverArtYValue').textContent
            ]
          };
        }"""
    )
    check(abs(baseline["ruleHeight"] - 6) <= 0.5,
          f"cover bottom line height did not update: {baseline}")
    check(abs(baseline["bottomGap"] - 32) <= 1,
          f"cover bottom gap is not fixed at 32px: {baseline}")
    check(baseline["gapVar"] == "32px" and baseline["textYVar"] == "0px",
          f"fixed cover CSS variables are wrong: {baseline}")
    check(baseline["lineWidth"] == "2px",
          f"bottom-line control changed the placeholder stroke: {baseline}")
    check(baseline["readout"] == ["6px", "32px", "0px", "0px"],
          f"cover tuning readout did not update: {baseline}")
    check(page.evaluate(
        "document.getElementById('structureVeil').classList.contains('is-visible')"
    ) is False, "cover tuning pulsed the structure veil")

    set_cover("tuneCoverArtY", -18)
    page.wait_for_timeout(160)
    image_shift = page.evaluate(
        """() => {
          const cover = document.querySelector('.slide-cover');
          return {
            brandTop: cover.querySelector('.cover-brand-text').getBoundingClientRect().top,
            sideTop: cover.querySelector('.cover-side').getBoundingClientRect().top
          };
        }"""
    )
    check(abs(image_shift["brandTop"] - baseline["brandTop"]) <= 1,
          f"image translate moved the fixed text: {baseline} -> {image_shift}")
    check(abs((baseline["sideTop"] - image_shift["sideTop"]) - 18) <= 1,
          f"image translate did not move the placeholder: {baseline} -> {image_shift}")

    page.locator("#tuneReset").click()
    page.wait_for_timeout(850)
    reset = page.evaluate(
        """() => {
          const cover = document.querySelector('.slide-cover');
          const lockup = cover.querySelector('.cover-lockup').getBoundingClientRect();
          const side = cover.querySelector('.cover-side').getBoundingClientRect();
          const rule = document.getElementById('sheetRuleA').getBoundingClientRect();
          const rootStyle = getComputedStyle(document.documentElement);
          return {
            barHeight: rootStyle.getPropertyValue('--cover-bar-height').trim(),
            bottomGap: rootStyle.getPropertyValue('--cover-bottom-gap').trim(),
            textY: rootStyle.getPropertyValue('--cover-text-y').trim(),
            imageY: rootStyle.getPropertyValue('--cover-art-y').trim(),
            actualRule: rule.height,
            actualGap: rule.top - Math.max(lockup.bottom, side.bottom),
            lineWidth: getComputedStyle(
              cover.querySelector('.cover-side path')
            ).strokeWidth,
            inputs: [
              document.getElementById('tuneCoverBar').value,
              document.getElementById('tuneCoverArtY').value
            ],
            fixed: [
              document.getElementById('tuneCoverGapFixed').textContent,
              document.getElementById('tuneCoverTextYFixed').textContent
            ]
          };
        }"""
    )
    check(reset["barHeight"] == "3px" and reset["bottomGap"] == "32px",
          f"cover tuning reset failed: {reset}")
    check(reset["textY"] == "0px" and reset["imageY"] == "0px",
          f"cover translate reset failed: {reset}")
    check(abs(reset["actualRule"] - 3) <= 0.5 and
          abs(reset["actualGap"] - 32) <= 1 and reset["lineWidth"] == "2px",
          f"cover reset did not restore the line/gap: {reset}")
    check(reset["inputs"] == ["3", "0"],
          f"cover reset did not restore the sliders: {reset}")
    check(reset["fixed"] == ["32px", "0px"],
          f"cover reset changed the fixed readouts: {reset}")
    print("cover tuning: ok")


def assert_config(page):
    if page.locator("#tuneBody").is_hidden():
        page.locator("#tuneToggle").click()
        page.wait_for_timeout(120)
    page.locator("#tuneCopy").click()
    page.wait_for_timeout(150)
    config = json.loads(page.evaluate("navigator.clipboard.readText()"))
    deck = config.get("deck")
    check(deck is not None, f"copy config has no deck: {config}")
    check(deck["count"] == EXPECTED_COUNT and deck["index"] == 0,
          f"copy config deck state: {deck}")
    check(deck["fadeDuration"] == 220, f"copy config fade duration: {deck}")
    check(deck["fadeMode"] == "staggered", f"copy config fade mode: {deck}")
    check(deck["fadeItems"] >= 20, f"copy config fade item count: {deck}")
    check("fadeOutMs" not in deck and "fadeInMs" not in deck,
          f"copy config kept old fade timings: {deck}")
    parallax = config.get("parallax")
    check(parallax is not None, f"copy config has no parallax: {config}")
    check(len(parallax["layers"]) == 30,
          f"copy config parallax layers: {parallax}")
    check(len({layer["depth"] for layer in parallax["layers"]}) >= 5,
          f"copy config parallax depths: {parallax}")
    check([layer["depth"] for layer in parallax["layers"][:3]] == [0.14, 0.26, 0.44],
          f"copy config cover parallax depths: {parallax}")
    check(config.get("quadrants") == {
        "index": 1,
        "hover": None,
        "tintPanels": ["red", "green", "blue", "gray"],
        "tintColors": {
            "red": "#ff2b2b",
            "green": "#00c853",
            "blue": "#1f52ff"
        },
        "pointer": {
            "nativeCursor": True,
            "sizePx": [34, 82],
            "strokePx": [5.5, 1.1],
            "speedCapPxPerSec": 1500,
            "speedSmoothing": 10,
            "speedDecay": 6.5
        }
    }, f"copy config quadrant state: {config.get('quadrants')}")
    check(config["feather"] == 72, f"copy config feather: {config}")
    check(config["renderScale"] == 1, f"copy config render scale: {config}")
    check(config.get("cover") == {
        "barHeight": 3, "bottomGap": 32, "textY": 0, "imageY": 0
    }, f"copy config cover layout: {config.get('cover')}")


def assert_reduced(browser):
    page, context, errors = open_page(browser, reduced=True)
    try:
        page.bring_to_front()
        wait_deck(page)
        page.locator("#deckNext").click()
        page.wait_for_timeout(80)
        state = page.evaluate("window.__mirrorHome.deck.getState()")
        check(state["index"] == 1 and state["locked"] is False,
              f"reduced-motion transition did not snap: {state}")
        active = page.evaluate(
            """() => {
              const slide = document.querySelector('#deck .slide[data-slide="1"]');
              return {
                opacity: getComputedStyle(slide).opacity,
                visibility: getComputedStyle(slide).visibility
              };
            }"""
        )
        check(active["opacity"] == "1" and active["visibility"] == "visible",
              f"reduced-motion slide not visible: {active}")
        check(not errors, "console/page errors: " + "\n".join(errors))
        print("reduced: ok")
    finally:
        context.close()


def assert_mobile(browser):
    page, context, errors = open_page(browser, width=390, height=844, dpr=2)
    try:
        page.bring_to_front()
        wait_deck(page)
        layout = read_layout(page)
        for axis in range(4):
            check(abs(layout["art"][axis] - layout["deckRect"][axis]) <= 1,
                  f"mobile deck is misaligned: {layout}")
        for slide in layout["slides"]:
            check(slide["scrollWidth"] <= slide["clientWidth"] + 2,
                  f"mobile slide overflows horizontally: {slide}")
            check(slide["scrollHeight"] <= slide["clientHeight"] + 2,
                  f"mobile slide overflows vertically: {slide}")
        check(layout["prev"]["x"] >= 0 and layout["next"]["right"] <= 390,
              f"mobile nav is outside the viewport: {layout}")
        page.evaluate("document.getElementById('tuner').style.display = 'none'")
        page.screenshot(path=str(SHOT_DIR / "probe-deck-mobile.png"), scale="css")
        check(not errors, "console/page errors: " + "\n".join(errors))
        print("mobile: ok")
    finally:
        context.close()


def run_backend(browser, mode, tag, *, width=1200, height=900, dpr=1):
    page, context, errors = open_page(
        browser, width=width, height=height, dpr=dpr
    )
    try:
        page.bring_to_front()
        wait_deck(page)
        check(page.evaluate("window.__mirrorHome.mirror.mode") == mode,
              f"expected {mode}")
        page.evaluate("window.__mirrorHome.parallax?.reset()")
        page.wait_for_timeout(450)
        layout = assert_structure(page)
        first, last = assert_navigation(page)
        assert_rank_page(page)
        assert_pointer_all_slides(page)
        assert_cover_tuning(page)
        assert_config(page)
        page.evaluate("document.getElementById('tuner').style.display = 'none'")
        page.screenshot(path=str(SHOT_DIR / f"probe-deck-{tag}.png"), scale="css")
        assert_structure_veil(page)
        check(not errors, "console/page errors: " + "\n".join(errors))
        print(f"{tag}:", json.dumps({
            "content": layout["art"],
            "first": first["state"],
            "last": last["state"]
        }))
    finally:
        context.close()


def main():
    SHOT_DIR.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel=os.environ.get("MIRROR_CHANNEL", "chrome-beta"),
            headless=False,
            args=[ENABLE_HTML_IN_CANVAS],
        )
        try:
            run_backend(browser, "webgl", "webgl", width=1440, height=900, dpr=1.5)
            assert_reduced(browser)
            assert_mobile(browser)
        finally:
            browser.close()

        browser = p.chromium.launch(
            channel=os.environ.get("MIRROR_CHANNEL", "chrome-beta"),
            headless=False,
            args=[DISABLE_HTML_IN_CANVAS],
        )
        try:
            run_backend(browser, "svg", "svg")
        finally:
            browser.close()

    print("DECK PROBE PASSED")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        print(f"FAILED: {error}", file=sys.stderr)
        raise
