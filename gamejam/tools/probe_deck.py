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
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_content_field import SHOT_DIR, check, open_page  # noqa: E402

ENABLE_HTML_IN_CANVAS = "--enable-features=CanvasDrawElement"
DISABLE_HTML_IN_CANVAS = "--disable-features=CanvasDrawElement"
# The clips now play with sound; the probe drives slide changes from script, so
# the autoplay policy is relaxed to keep the check deterministic.
ALLOW_AUTOPLAY = "--autoplay-policy=no-user-gesture-required"
EXPECTED_COUNT = 5


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


def wait_video_ready(page, timeout=25000):
    page.wait_for_function(
        "window.__mirrorHome.detail && "
        "window.__mirrorHome.detail.getState().video.phase === 'ready'",
        timeout=timeout,
    )
    page.wait_for_timeout(120)
    return page.evaluate("window.__mirrorHome.detail.getState()")


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
          const coverSideImage = cover.querySelector('.cover-side img');
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
            originTrialTokens: [...document.querySelectorAll('meta[http-equiv="origin-trial"]')]
              .map((el) => (el.getAttribute('content') || '').length),
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
              sideImageCount: cover.querySelectorAll('.cover-side img').length,
              sideImage: coverSideImage ? {
                src: coverSideImage.currentSrc || coverSideImage.src,
                alt: coverSideImage.alt,
                complete: coverSideImage.complete,
                naturalWidth: coverSideImage.naturalWidth,
                naturalHeight: coverSideImage.naturalHeight,
                objectFit: getComputedStyle(coverSideImage).objectFit,
                display: getComputedStyle(coverSideImage).display
              } : null,
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
    check(layout["artOverflow"] == "hidden" and
          layout["deckOverflow"] in ("hidden", "clip"),
          f"sheet rules would not be clipped by the content: {layout}")
    check(layout["sheetRules"] == 2 and layout["sheetRuleFades"] == 0 and
          layout["sheetRuleInSlide"] is False,
          f"sheet rules are tied to the slide lifecycle: {layout}")
    check(layout["ruleMode"] == "bar",
          f"sheet rules do not start as the cover bar: {layout}")
    check(len(layout["originTrialTokens"]) == 1 and
          layout["originTrialTokens"][0] > 100,
          f"the HTML-in-Canvas origin trial token is missing: {layout}")
    check(layout["navPointerEvents"] == "none", f"nav intercepts pointer: {layout}")
    check(layout["navInert"] is False, f"nav stayed inert after boot: {layout}")
    check(page.locator("#deckIndex").count() == 0,
          "page-number indicator should be removed")
    check(page.evaluate("document.querySelectorAll('.detail-video-slot').length") == 0,
          "the detail clip is preloaded before its slide is opened")
    check(page.evaluate("window.__mirrorHome.detail.getState().video.phase") == "idle",
          "the detail clip state is not idle on the cover")

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
    # At 150% the sideview box grows past the text column, so the image is
    # allowed to overlap the lockup's bounding box (the drawing is transparent
    # there); what still matters is the flush bottom-right corner and staying
    # inside the content.
    check(cover["side"][0] >= layout["art"][0] - 1,
          f"cover sideview leaves the content left edge: {cover}")
    art_right = layout["art"][0] + layout["art"][2]
    art_bottom = layout["art"][1] + layout["art"][3]
    side_right = cover["side"][0] + cover["side"][2]
    side_bottom = cover["side"][1] + cover["side"][3]
    check(abs(side_right - (art_right + 2)) <= 0.6,
          f"cover image is not flush to the content right with nudge: {cover}")
    check(abs(side_bottom - art_bottom) <= 0.6,
          f"cover image is not flush to the content bottom: {cover}")
    side_image = cover["sideImage"]
    check(cover["sideSvg"] == 0 and cover["sideImageCount"] == 1 and side_image,
          f"cover sideview is not a single image: {cover}")
    check(side_image["complete"] and side_image["naturalWidth"] > 0 and
          side_image["naturalHeight"] > 0,
          f"cover sideview image did not load: {side_image}")
    check(side_image["src"].endswith(
              "/mirror-2610/assets/ellia-sideview-flat-clipped.png"),
          f"cover sideview image path is wrong: {side_image['src']}")
    check(abs(side_image["naturalWidth"] / side_image["naturalHeight"] -
              1401 / 978) <= 0.001,
          f"cover sideview source ratio is wrong: {side_image}")
    check(side_image["alt"] == "ellia sideview" and
          side_image["objectFit"] == "contain" and
          side_image["display"] == "block",
          f"cover sideview image presentation is wrong: {side_image}")
    check(all(value == "0px" for value in cover["textBorders"]),
          f"cover text still has a border: {cover['textBorders']}")
    check(cover["rule"][2] >= layout["art"][2] - 2 and cover["rule"][3] == 6,
          f"cover bottom rule does not span the content: {cover}")
    check(abs((cover["rule"][1] + cover["rule"][3]) -
              (layout["art"][1] + layout["art"][3])) <= 1,
          f"cover bottom rule is not at the content bottom: {cover}")
    lockup_bottom = cover["lockup"][1] + cover["lockup"][3]
    check(abs(cover["rule"][1] - lockup_bottom - 32) <= 1,
          f"cover default text bottom gap is wrong: {cover}")
    check(cover["borderTop"] == "0px" and cover["borderBottom"] == "0px",
          f"cover has an extra edge: {cover}")
    check("GameJam" in layout["slides"][0]["text"], f"cover copy missing: {layout}")
    if page.evaluate("window.__mirrorHome.mirror.mode") == "svg":
        glass_clip = page.evaluate(
            "getComputedStyle(document.querySelector('.mirror-glass')).clipPath"
        )
        check(glass_clip.startswith("path("),
              f"SVG glass is not clipped around the content: {glass_clip}")
    check("来自：" in layout["slides"][3]["text"] and
          "在线游玩" in layout["slides"][3]["text"] and
          "项目主页" in layout["slides"][3]["text"],
          f"detail copy missing: {layout}")
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
        # Retry the move: a mirror repaint or a lost pointer sample can drop the
        # first hover update on a slow frame.
        for attempt in range(3):
            page.mouse.move(art[0] + art[2] * nx, art[1] + art[3] * ny, steps=3)
            page.wait_for_timeout(260)
            state = page.evaluate("window.__mirrorHome.quadrant.getState()")
            if state["hover"] == name:
                break
            page.wait_for_timeout(120)
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


def assert_detail_page(page):
    page.mouse.move(5, 5)
    page.wait_for_timeout(220)
    before = page.evaluate(
        """() => ({
          mode: document.getElementById('art').dataset.ruleMode,
          art: (() => {
            const r = document.getElementById('art').getBoundingClientRect();
            return [r.x, r.y, r.width, r.height];
          })(),
          rules: [...document.querySelectorAll('.sheet-rule')].map((el) => {
            const r = el.getBoundingClientRect();
            return {
              x: r.x, y: r.y, width: r.width, height: r.height,
              cx: r.x + r.width / 2, cy: r.y + r.height / 2,
              transform: getComputedStyle(el).transform
            };
          })
        })"""
    )
    check(before["mode"] == "rank",
          f"detail transition did not start from the ranking rules: {before['mode']}")
    check(len(before["rules"]) == 2 and
          before["rules"][0]["height"] > before["rules"][0]["width"] and
          before["rules"][1]["height"] > before["rules"][1]["width"],
          f"ranking rules are not both vertical before detail: {before['rules']}")
    page.evaluate("window.__mirrorHome.deck.goTo(3)")
    page.wait_for_timeout(340)
    mid_turn = page.evaluate(
        "getComputedStyle(document.getElementById('sheetRuleA')).transform"
    )
    wait_unlocked(page)
    wait_video_ready(page)
    page.wait_for_timeout(800)
    page.mouse.move(5, 5)
    page.wait_for_timeout(220)
    data = page.evaluate(
        """() => {
          const art = document.getElementById('art');
          const artRect = art.getBoundingClientRect();
          const slide = document.querySelector('.slide-detail');
          const slideRect = slide.getBoundingClientRect();
          const rules = [...document.querySelectorAll('.sheet-rule')].map((el) => {
            const rect = el.getBoundingClientRect();
            return {
              x: rect.x, y: rect.y, width: rect.width, height: rect.height,
              right: rect.right, bottom: rect.bottom,
              cx: rect.x + rect.width / 2, cy: rect.y + rect.height / 2,
              transform: getComputedStyle(el).transform
            };
          });
          const rectOf = (element) => {
            const rect = element.getBoundingClientRect();
            return [rect.x, rect.y, rect.width, rect.height, rect.right, rect.bottom];
          };
          const fontOf = (selector) => getComputedStyle(
            slide.querySelector(selector)
          ).fontFamily;
          const fontSizeOf = (selector) => getComputedStyle(
            slide.querySelector(selector)
          ).fontSize;
          const card = slide.querySelector('.detail-intro-card');
          const title = slide.querySelector('.detail-intro-title');
          const body = slide.querySelector('.detail-intro-body');
          const meta = slide.querySelector('.detail-intro-meta');
          const team = slide.querySelector('.detail-intro-team');
          const video = slide.querySelector('.detail-video');
          const activeSlot = slide.querySelector('.detail-video-slot.is-active');
          const actions = slide.querySelector('.detail-actions');
          const footer = slide.querySelector('.detail-footer');
          const switcher = slide.querySelector('.detail-switcher');
          const pager = slide.querySelector('.detail-pager');
          const switchButtons = [...slide.querySelectorAll('.detail-switch-button')];
          const introStyle = getComputedStyle(slide.querySelector('.detail-intro'));
          const actionStyle = getComputedStyle(actions);
          const fadeItems = [...slide.querySelectorAll('[data-fade]')];
          return {
            mode: art.dataset.ruleMode,
            art: [artRect.x, artRect.y, artRect.width, artRect.height],
            slide: [slideRect.x, slideRect.y, slideRect.width, slideRect.height],
            overflow: [slide.scrollWidth, slide.clientWidth,
                       slide.scrollHeight, slide.clientHeight],
            rules,
            intro: rectOf(slide.querySelector('.detail-intro')),
            card: rectOf(card),
            title: rectOf(title),
            body: rectOf(body),
            meta: rectOf(meta),
            team: rectOf(team),
            video: rectOf(video),
            mediaBox: activeSlot ? rectOf(activeSlot) : null,
            slotCount: slide.querySelectorAll('.detail-video-slot').length,
            videoPlaceholderDisplay: (() => {
              const box = slide.querySelector('.detail-video-placeholder');
              return box ? getComputedStyle(box).display : null;
            })(),
            actions: rectOf(actions),
            footer: rectOf(footer),
            switcher: rectOf(switcher),
            pager: rectOf(pager),
            pagerDashes: [...pager.querySelectorAll('.detail-pager-dash')].map(
              (el, index) => {
                const bar = getComputedStyle(el, '::before');
                const rect = el.getBoundingClientRect();
                return {
                  index,
                  current: el.classList.contains('is-current'),
                  tag: el.tagName,
                  ariaCurrent: el.getAttribute('aria-current'),
                  label: el.getAttribute('aria-label') || '',
                  x: rect.x,
                  width: rect.width,
                  height: rect.height,
                  background: bar.backgroundColor,
                  barHeight: Number.parseFloat(bar.height)
                };
              }
            ),
            pagerRole: pager.getAttribute('role'),
            switchButtons: switchButtons.map((el) => {
              const rect = el.getBoundingClientRect();
              const style = getComputedStyle(el);
              return {
                text: el.textContent.trim(),
                deckClass: el.classList.contains('deck-button'),
                rect: [rect.x, rect.y, rect.width, rect.height,
                       rect.right, rect.bottom],
                background: style.backgroundColor,
                borderWidth: style.borderTopWidth,
                borderColor: style.borderTopColor,
                fontFamily: style.fontFamily,
                fontSize: style.fontSize
              };
            }),
            deckButtonStyle: (() => {
              const el = document.getElementById('deckPrev');
              const rect = el.getBoundingClientRect();
              const style = getComputedStyle(el);
              return {
                width: rect.width,
                height: rect.height,
                background: style.backgroundColor,
                borderWidth: style.borderTopWidth,
                borderColor: style.borderTopColor,
                fontFamily: style.fontFamily,
                fontSize: style.fontSize
              };
            })(),
            introPadding: [
              parseFloat(introStyle.paddingTop),
              parseFloat(introStyle.paddingRight),
              parseFloat(introStyle.paddingBottom),
              parseFloat(introStyle.paddingLeft)
            ],
            cardBorder: getComputedStyle(card).borderTopWidth,
            titleBorder: getComputedStyle(title).borderTopWidth,
            titleAlign: getComputedStyle(title).textAlign,
            metaBorder: getComputedStyle(meta).borderTopWidth,
            videoMedia: (() => {
              const media = activeSlot;
              if (!media) return null;
              return {
                src: media.currentSrc || media.src,
                attrSrc: media.getAttribute('src'),
                width: media.videoWidth,
                height: media.videoHeight,
                readyState: media.readyState,
                paused: media.paused,
                muted: media.muted,
                loop: media.loop,
                objectFit: getComputedStyle(media).objectFit
              };
            })(),
            stall: (() => {
              const stall = document.getElementById('detailVideoStall');
              const veil = document.getElementById('detailVideoVeil');
              const style = getComputedStyle(stall);
              return {
                hidden: stall.hidden,
                z: Number(style.zIndex),
                veilZ: Number(getComputedStyle(veil).zIndex),
                background: style.backgroundColor,
                pointerEvents: style.pointerEvents
              };
            })(),
            veilBarColors: (() => {
              const veil = document.getElementById('detailVideoVeil');
              const bar = document.getElementById('detailVideoVeilBar');
              const hadReady = veil.classList.contains('is-ready');
              veil.classList.remove('is-ready');
              const loading = getComputedStyle(bar).backgroundColor;
              veil.classList.add('is-ready');
              const ready = getComputedStyle(bar).backgroundColor;
              veil.classList.toggle('is-ready', hadReady);
              return { loading, ready };
            })(),
            veil: (() => {
              const veil = document.getElementById('detailVideoVeil');
              const window_ = slide.querySelector('.detail-video-window');
              const style = getComputedStyle(veil);
              return {
                exists: !!veil,
                hasWindow: !!window_,
                windowOverflow: window_ ? getComputedStyle(window_).overflow : '',
                translate: style.translate,
                hidden: veil.getAttribute('aria-hidden'),
                role: veil.getAttribute('role'),
                live: veil.getAttribute('aria-live'),
                name: document.getElementById('detailVideoVeilName').textContent.trim(),
                meta: document.getElementById('detailVideoVeilMeta').textContent.trim(),
                barWidth: document.getElementById('detailVideoVeilBar').style.width
              };
            })(),
            videoStage: (() => {
              const stage = slide.querySelector('.detail-video-stage');
              if (!stage) return null;
              const rect = stage.getBoundingClientRect();
              return {
                rect: [rect.x, rect.y, rect.width, rect.height,
                       rect.right, rect.bottom],
                ratio: rect.width / rect.height
              };
            })(),
            videoCorners: [...slide.querySelectorAll('.detail-video-corner')].map(
              (el) => {
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return {
                  cls: el.className,
                  rect: [rect.x, rect.y, rect.width, rect.height,
                         rect.right, rect.bottom],
                  stroke: Math.max(
                    parseFloat(style.borderTopWidth),
                    parseFloat(style.borderLeftWidth),
                    parseFloat(style.borderRightWidth),
                    parseFloat(style.borderBottomWidth)
                  )
                };
              }
            ),
            videoDecorations: slide.querySelectorAll(
              '.detail-video-top, .detail-video-foot, .detail-video-mark, '
              + '.detail-video-word, .detail-video-sub, .detail-video-media-text'
            ).length,
            videoTrigger: (() => {
              const frame = slide.querySelector('.detail-video');
              return {
                role: frame.getAttribute('role'),
                tabIndex: frame.getAttribute('tabindex'),
                expanded: frame.getAttribute('aria-expanded'),
                controls: frame.getAttribute('aria-controls'),
                label: frame.getAttribute('aria-label') || '',
                frameClass: frame.className
              };
            })(),
            parallaxDepths: [...slide.querySelectorAll('[data-parallax]')].map(
              (el) => Number(el.dataset.parallax)
            ),
            actionStyle: (() => {
              const tools = slide.querySelector('.detail-tools');
              const toolsStyle = tools ? getComputedStyle(tools) : null;
              return {
                opacity: toolsStyle ? toolsStyle.opacity : '1',
                visibility: toolsStyle ? toolsStyle.visibility : 'visible',
                pointerEvents: toolsStyle ? toolsStyle.pointerEvents : 'auto',
                background: actionStyle.backgroundColor,
                backdropFilter: actionStyle.backdropFilter,
                border: actionStyle.borderTopWidth
              };
            })(),
            volume: (() => {
              const tools = slide.querySelector('.detail-tools');
              const slider = document.getElementById('detailVolume');
              const value = document.getElementById('detailVolumeValue');
              const style = slider ? getComputedStyle(slider) : null;
              return {
                hasSlider: Boolean(slider),
                toolsFirstChild: tools && tools.firstElementChild
                  ? tools.firstElementChild.className
                  : '',
                value: slider ? slider.value : '',
                label: value ? value.textContent.trim() : '',
                ariaLabel: slider ? slider.getAttribute('aria-label') : '',
                accent: style ? style.accentColor : ''
              };
            })(),
            fontsSizes: {
              body: Number.parseFloat(fontSizeOf('.detail-intro-body')),
              action: Number.parseFloat(fontSizeOf('.detail-action')),
              actionSub: Number.parseFloat(fontSizeOf('.detail-action-sub'))
            },
            actionButtons: [...slide.querySelectorAll('.detail-action')].map((el) => {
              const style = getComputedStyle(el);
              return {
                text: el.textContent.replace(/\\s+/g, ' ').trim(),
                link: el.dataset.link || '',
                href: el.dataset.href || '',
                disabled: el.disabled,
                className: el.className,
                color: style.color,
                background: style.backgroundColor,
                borderWidth: style.borderTopWidth,
                borderColor: style.borderTopColor,
                cursor: style.cursor
              };
            }),
            actionChrome: {
              head: slide.querySelectorAll('.detail-actions-head').length,
              close: slide.querySelectorAll('.detail-actions-close').length,
              note: slide.querySelectorAll('.detail-actions-note').length
            },
            removed: {
              side: slide.querySelectorAll('.detail-side').length,
              cta: slide.querySelectorAll('.detail-cta').length,
              award: slide.querySelectorAll('.detail-award').length,
              footerWork: slide.querySelectorAll('.detail-work').length
            },
            fonts: {
              title: fontOf('.detail-intro-title'),
              body: fontOf('.detail-intro-body'),
              from: fontOf('.detail-intro-from'),
              team: fontOf('.detail-intro-team'),
              action: fontOf('.detail-action')
            },
            text: {
              work: title.textContent.trim(),
              team: team.textContent.trim(),
              from: slide.querySelector('.detail-intro-from').textContent.trim(),
              body: body.textContent.trim(),
              label: slide.getAttribute('aria-label')
            },
            fadeCount: fadeItems.length,
            fadeInDelays: fadeItems.map((el) => Number(el.dataset.fadeInDelay)),
            fadeOutDelays: fadeItems.map((el) => Number(el.dataset.fadeOutDelay)),
            state: window.__mirrorHome.detail.getState()
          };
        }"""
    )
    check(data["mode"] == "detail",
          f"detail page did not switch the sheet rules: {data['mode']}")
    check(data["overflow"][0] <= data["overflow"][1] + 2 and
          data["overflow"][2] <= data["overflow"][3] + 2,
          f"detail page overflows: {data['overflow']}")
    art_left, art_top, art_width, art_height = data["art"]
    check(len(data["rules"]) == 2,
          f"detail page should have two sheet rules: {data['rules']}")
    if len(data["rules"]) == 2:
        top_rule = data["rules"][0]
        bottom_rule = data["rules"][1]
        check(top_rule["width"] > top_rule["height"] and
              bottom_rule["width"] > bottom_rule["height"],
              f"detail rules did not turn horizontal: {data['rules']}")
        check(top_rule["width"] >= art_width - 1 and
              bottom_rule["width"] >= art_width - 1,
              f"detail rules do not span the content: {data['rules']}")
        check(abs(top_rule["y"] - art_top) <= 1.5,
              f"top detail rule is not on the content top edge: {top_rule}")
        check(abs(bottom_rule["y"] + bottom_rule["height"] -
                  (art_top + art_height)) <= 1.5,
              f"bottom detail rule is not on the content bottom edge: {bottom_rule}")
        check(top_rule["transform"].startswith("matrix(-1, 0, 0, -1") and
              bottom_rule["transform"].startswith("matrix(-1, 0, 0, -1"),
              f"detail rules did not finish their 180deg turn: {data['rules']}")
        turn_values = [
            float(value)
            for value in mid_turn.removeprefix("matrix(").removesuffix(")").split(",")
        ]
        check(len(turn_values) == 6 and turn_values[0] < 0,
              f"top rule exceeded or reversed its clockwise quarter turn: {mid_turn}")
        check(abs(before["rules"][0]["cx"] -
                  (before["art"][0] + before["art"][2] * 0.3)) <= 2 and
              abs(before["rules"][1]["cx"] -
                  (before["art"][0] + before["art"][2] * 0.9)) <= 2,
              f"ranking rules were not at 30/90 before detail: {before}")

    card = data["card"]
    intro = data["intro"]
    title = data["title"]
    video = data["video"]
    media_box = data["mediaBox"]
    actions = data["actions"]
    footer = data["footer"]
    switcher = data["switcher"]
    pager = data["pager"]
    pager_dashes = data["pagerDashes"]
    check(data["cardBorder"] == "0px",
          f"detail intro still draws a full card border: {data['cardBorder']}")
    title_border = float(data["titleBorder"].replace("px", ""))
    check(0.5 <= title_border <= 1.5,
          f"detail work title is not boxed: {data['titleBorder']}")
    check(data["titleAlign"] == "center",
          f"detail work title is not centred in its box: {data['titleAlign']}")
    check(title[0] > intro[0] and title[4] < intro[4] and
          title[1] > intro[1] and title[5] < intro[5],
          f"detail title box leaves the intro rail: {title} {intro}")
    check(video[2] > art_width * 0.65,
          f"detail video lost the main column width: {video} in {data['art']}")
    check(video[0] > intro[4] + 8 and
          video[4] < art_left + art_width - 12 and
          video[1] > art_top + 20 and video[5] < footer[1] - 8,
          f"detail video panel is outside the main column: {video}")
    video_right_gap = art_left + art_width - video[4]
    check(8 <= video_right_gap <= 38,
          f"detail video did not move closer to the content right edge: "
          f"{video_right_gap}px")
    top_pad, right_pad, bottom_pad, left_pad = data["introPadding"]
    check(14 <= top_pad <= 30 and 10 <= right_pad <= 26 and
          abs(top_pad - bottom_pad) <= 1 and
          abs(right_pad - left_pad) <= 1,
          f"detail intro padding is not a tight symmetric inset: "
          f"{data['introPadding']}")
    check(0.06 <= footer[3] / art_height <= 0.08,
          f"detail footer height was not reduced to the 7% band: {footer} "
          f"in {data['art']}")
    meta_border = float(data["metaBorder"].replace("px", ""))
    check(0.5 <= meta_border <= 1.5,
          f"detail source rule above the team is not a hairline: "
          f"{data['metaBorder']}")
    group_center = (title[1] + data["meta"][5]) / 2
    rail_center = (intro[1] + intro[5]) / 2
    check(abs(group_center - rail_center) <= 6,
          f"detail intro copy is not vertically centred in the rail: "
          f"{group_center} vs {rail_center}")
    check(data["meta"][1] > data["body"][5] and
          data["meta"][5] < intro[5] - 10,
          f"detail source/team is not stacked under the body inside the rail: "
          f"{data['meta']} {data['body']} {intro}")
    check((data["team"][0] + data["team"][2] / 2) >
          art_left + art_width * 0.24 / 2,
          f"detail team is not centred in the narrow rail: {data['team']}")
    check(abs((switcher[0] + switcher[2] / 2) - (art_left + art_width / 2)) <= 2,
          f"detail work switcher is not centred under the content: {switcher}")
    check(switcher[1] > footer[1] and switcher[5] < footer[5],
          f"detail work switcher leaves the footer: {switcher} {footer}")
    bottom_gap = footer[5] - switcher[5]
    check(7 <= bottom_gap <= 16,
          f"detail pager keeps no fixed gap above the bottom rule: "
          f"{bottom_gap}px")
    check(len(data["switchButtons"]) == 2,
          f"detail footer does not have two switch buttons: {data['switchButtons']}")
    deck_button = data["deckButtonStyle"]
    for button, glyph in zip(data["switchButtons"], ("←", "→")):
        check(button["deckClass"] is False and button["text"] == glyph,
              f"detail switch button should own its styling, not borrow "
              f"deck-button: {button}")
        check(abs(button["rect"][2] - deck_button["width"]) <= 0.5 and
              abs(button["rect"][3] - deck_button["height"]) <= 0.5 and
              button["borderWidth"] == deck_button["borderWidth"],
              f"detail switch button does not match the deck button box: "
              f"{button} vs {deck_button}")
        check(button["background"] == "rgba(0, 0, 0, 0)" and
              button["borderColor"] == "rgba(0, 0, 0, 0)",
              f"detail switch button is filled or outlined at rest: {button}")
        check(button["fontFamily"] == deck_button["fontFamily"] and
              button["fontSize"] == deck_button["fontSize"],
              f"detail switch button glyph font does not match deck paging: "
              f"{button} vs {deck_button}")
    check(len(pager_dashes) == 15 and
          sum(1 for dash in pager_dashes if dash["current"]) == 1,
          f"detail pager does not show all works with one current mark: "
          f"{pager_dashes}")
    widths = [round(dash["width"], 1) for dash in pager_dashes]
    current_dash = next(dash for dash in pager_dashes if dash["current"])
    other_dashes = [dash for dash in pager_dashes if not dash["current"]]
    check(max(widths) - min(widths) <= 0.5,
          f"detail pager dashes are not equal length: {widths}")
    check(abs(current_dash["width"] - other_dashes[0]["width"]) <= 0.5 and
          current_dash["background"] == "rgb(10, 10, 10)" and
          all(dash["background"].startswith("rgba") for dash in other_dashes),
          f"detail pager current mark is not a colour difference: "
          f"{pager_dashes}")
    check(abs(current_dash["barHeight"] - 4) <= 0.6 and
          all(abs(dash["barHeight"] - 2) <= 0.4 for dash in other_dashes),
          f"detail pager current mark is not twice as thick: "
          f"{[dash['barHeight'] for dash in pager_dashes[:4]]}")
    check(all(dash["tag"] == "BUTTON" for dash in pager_dashes) and
          data["pagerRole"] == "group",
          f"detail pager dashes are not clickable buttons: "
          f"{pager_dashes[:2]} role={data['pagerRole']}")
    check(current_dash["ariaCurrent"] == "true" and
          all(dash["ariaCurrent"] is None for dash in other_dashes),
          f"detail pager does not mark its current button: {pager_dashes}")
    check(all(dash["label"].startswith(f"第 {dash['index'] + 1} 件作品")
              for dash in pager_dashes),
          f"detail pager buttons lost their labels: {pager_dashes[:2]}")
    pager_gaps = [
        round(pager_dashes[index + 1]["x"] - (
            pager_dashes[index]["x"] + pager_dashes[index]["width"]
        ), 2)
        for index in range(len(pager_dashes) - 1)
    ]
    check(all(abs(gap) <= 0.35 for gap in pager_gaps),
          f"detail pager still spaces its dashes apart: {pager_gaps}")
    check(pager[2] > switcher[2] * 0.45 and
          pager[0] > switcher[0] + deck_button["width"],
          f"detail pager does not span between the switch buttons: "
          f"{pager} {switcher}")

    # Hovering a non-current dash thickens only that bar.
    hover_index = 5 if current_dash["index"] != 5 else 6
    dash_box = page.locator(".detail-pager-dash").nth(hover_index).bounding_box()
    dash_x = dash_box["x"] + dash_box["width"] / 2
    dash_y = dash_box["y"] + dash_box["height"] / 2
    page.mouse.move(dash_x, dash_y, steps=3)
    page.wait_for_timeout(260)
    hovered_bars = page.evaluate(
        """(index) => {
          const dashes = [...document.querySelectorAll('.detail-pager-dash')];
          const bar = (el) => Number.parseFloat(
            getComputedStyle(el, '::before').height
          );
          const current = dashes.findIndex(
            (el) => el.classList.contains('is-current')
          );
          return {
            hovered: bar(dashes[index]),
            current: bar(dashes[current]),
            neighbour: bar(dashes[(index + 1) % dashes.length])
          };
        }""",
        hover_index,
    )
    check(hovered_bars["hovered"] >= 20 and
          abs(hovered_bars["current"] - 4) <= 0.6 and
          hovered_bars["neighbour"] <= 2.5,
          f"detail pager hover does not thicken just the point: {hovered_bars}")
    check(all(dash["height"] >= 26 for dash in pager_dashes),
          f"detail pager hit band is too short: "
          f"{[dash['height'] for dash in pager_dashes[:3]]}")
    page.mouse.move(5, 5)
    page.wait_for_timeout(220)

    # Clicking a dash jumps straight to that work.
    page.mouse.click(dash_x, dash_y)
    page.wait_for_function(
        f"window.__mirrorHome.detail.getState().index === {hover_index}",
        timeout=15000,
    )
    wait_video_ready(page)
    jumped = page.evaluate(
        """() => ({
          index: window.__mirrorHome.detail.getState().index,
          current: [...document.querySelectorAll('.detail-pager-dash')]
            .findIndex((el) => el.classList.contains('is-current'))
        })"""
    )
    check(jumped == {"index": hover_index, "current": hover_index},
          f"detail pager click did not jump to the work: {jumped}")
    page.mouse.move(5, 5)
    page.wait_for_timeout(200)
    page.evaluate("window.__mirrorHome.detail.select(0)")
    wait_video_ready(page)

    rest_style = page.evaluate(
        """() => {
          const style = getComputedStyle(document.getElementById('detailPrev'));
          return {
            transitionProperty: style.transitionProperty,
            transitionDuration: style.transitionDuration
          };
        }"""
    )
    check("border-color" in rest_style["transitionProperty"] and
          rest_style["transitionDuration"] not in ("0s", "0.01ms"),
          f"detail switch button border has no transition: {rest_style}")

    page.hover("#detailPrev")
    page.wait_for_timeout(260)
    hover_button = page.evaluate(
        """() => {
          const el = document.getElementById('detailPrev');
          const style = getComputedStyle(el);
          return {
            background: style.backgroundColor,
            borderColor: style.borderTopColor,
            color: style.color
          };
        }"""
    )
    check(hover_button["background"] == "rgba(0, 0, 0, 0)" and
          hover_button["borderColor"] == "rgb(10, 10, 10)" and
          hover_button["color"] == "rgb(10, 10, 10)",
          f"detail switch button hover did not draw just an outline: "
          f"{hover_button}")
    page.hover("#detailNext")
    page.wait_for_timeout(260)
    next_hover = page.evaluate(
        """() => {
          const style = getComputedStyle(document.getElementById('detailNext'));
          const prev = getComputedStyle(document.getElementById('detailPrev'));
          return {
            background: style.backgroundColor,
            borderColor: style.borderTopColor,
            color: style.color,
            prevBackground: prev.backgroundColor,
            prevBorder: prev.borderTopColor
          };
        }"""
    )
    check(next_hover["background"] == "rgba(0, 0, 0, 0)" and
          next_hover["borderColor"] == "rgb(10, 10, 10)" and
          next_hover["color"] == "rgb(10, 10, 10)" and
          next_hover["prevBackground"] == "rgba(0, 0, 0, 0)" and
          next_hover["prevBorder"] == "rgba(0, 0, 0, 0)",
          f"detail switch button hover drew a fill or stuck after leaving: "
          f"{next_hover}")
    page.mouse.move(5, 5)
    page.wait_for_timeout(120)
    check(data["removed"] == {
        "side": 0, "cta": 0, "award": 0, "footerWork": 0
    }, f"removed featured/footer pieces are still present: {data['removed']}")

    check(data["parallaxDepths"] == [0.16, 0.52, 0.52],
          f"detail parallax layers are not mounted: {data['parallaxDepths']}")
    media = data["videoMedia"]
    check(media is not None,
          "detail video panel has no video element")
    check(media["src"].endswith("/mirror-2610/assets/video-placeholder.mp4"),
          f"detail video does not use the per-work clip: {media}")
    check("has-video" in data["videoTrigger"]["frameClass"],
          f"detail frame does not report a bound video: {data['videoTrigger']}")
    check((media["width"], media["height"]) == (988, 586),
          f"detail video reported the wrong intrinsic size: {media}")
    check(media["readyState"] >= 2 and media["paused"] is False,
          f"detail placeholder video is not running: {media}")
    check(media["muted"] is False and media["loop"] is True and
          media["objectFit"] == "contain",
          f"detail placeholder video settings are wrong: {media}")
    check(data["slotCount"] >= 1,
          f"detail clip pool is empty: {data['slotCount']}")
    check(data["videoPlaceholderDisplay"] == "none",
          f"detail placeholder is visible over a real clip: "
          f"{data['videoPlaceholderDisplay']}")

    veil = data["veil"]
    check(veil["exists"] and veil["hasWindow"] and
          veil["windowOverflow"] == "hidden",
          f"detail veil is not clipped by its window: {veil}")
    check(veil["role"] == "status" and veil["live"] == "polite",
          f"detail veil lost its live-region wiring: {veil}")
    check(veil["hidden"] == "true" and "101" in veil["translate"],
          f"detail veil is not parked below the clip at rest: {veil}")

    stall = data["stall"]
    check(stall["hidden"] is True,
          f"detail stall sheet is visible at rest: {stall}")
    check(stall["z"] < stall["veilZ"],
          f"detail stall sheet sits above the loading veil: {stall}")
    check(stall["pointerEvents"] == "none" and
          stall["background"].startswith("rgba"),
          f"detail stall sheet is not a non-interactive translucent layer: "
          f"{stall}")
    bar_colors = data["veilBarColors"]
    check(bar_colors["loading"] == "rgb(216, 74, 51)" and
          bar_colors["ready"] == "rgb(10, 10, 10)",
          f"detail veil bar does not switch to the accent before canplay: "
          f"{bar_colors}")
    check(data["videoDecorations"] == 0,
          f"detail video panel still has decorative rows: "
          f"{data['videoDecorations']}")

    stage = data["videoStage"]
    check(stage is not None, "detail video panel has no contain stage")
    check(abs(stage["ratio"] - 988 / 586) <= 0.02,
          f"detail video stage is not on the clip ratio: {stage}")
    check(stage["rect"][0] >= video[0] and
          stage["rect"][4] <= video[4] and
          stage["rect"][1] >= video[1] and
          stage["rect"][5] <= video[5],
          f"detail video stage leaves the panel: {stage} {video}")
    check(abs(media_box[0] - stage["rect"][0]) <= 1 and
          abs(media_box[1] - stage["rect"][1]) <= 1 and
          abs(media_box[2] - stage["rect"][2]) <= 1 and
          abs(media_box[3] - stage["rect"][3]) <= 1,
          f"detail video does not fill its contain stage: "
          f"{media_box} {stage}")
    corners = {entry["cls"].split(" ")[-1]: entry for entry in data["videoCorners"]}
    check(set(corners) == {"is-tl", "is-tr", "is-bl", "is-br"} and
          len(data["videoCorners"]) == 4,
          f"detail video is missing corner marks: {data['videoCorners']}")
    tl, tr, bl, br = (corners[key]["rect"]
                      for key in ("is-tl", "is-tr", "is-bl", "is-br"))
    half = corners["is-tl"]["rect"][2] / 2
    check(abs((tl[4] - stage["rect"][0]) - half) <= 1 and
          abs((tl[5] - stage["rect"][1]) - half) <= 1 and
          abs((stage["rect"][4] - tr[0]) - half) <= 1 and
          abs((tr[5] - stage["rect"][1]) - half) <= 1 and
          abs((bl[4] - stage["rect"][0]) - half) <= 1 and
          abs((bl[5] - stage["rect"][5]) - half) <= 1 and
          abs((stage["rect"][4] - br[0]) - half) <= 1 and
          abs((br[5] - stage["rect"][5]) - half) <= 1,
          f"detail corner marks do not keep the half-size offset from the "
          f"video corners: {data['videoCorners']} stage={stage['rect']}")
    for entry in data["videoCorners"]:
        check(abs(entry["stroke"] - 2) <= 0.7,
              f"detail corner mark stroke is not 2px: {entry}")
        check(entry["rect"][0] >= video[0] - 1 and
              entry["rect"][4] <= video[4] + 1 and
              entry["rect"][1] >= video[1] - 1 and
              entry["rect"][5] <= video[5] + 1,
              f"detail corner mark leaves the panel: {entry} {video}")
    trigger = data["videoTrigger"]
    check(trigger["role"] == "button" and trigger["tabIndex"] == "0" and
          trigger["controls"] == "detailActions" and
          trigger["expanded"] == "false",
          f"detail video trigger wiring is wrong: {trigger}")

    check(data["actionStyle"]["opacity"] == "0" and
          data["actionStyle"]["visibility"] == "hidden" and
          data["actionStyle"]["pointerEvents"] == "none",
          f"detail action tray is not hidden at rest: {data['actionStyle']}")
    tray_background = data["actionStyle"]["background"]
    check(tray_background in ("rgba(0, 0, 0, 0)", "transparent") and
          float(data["actionStyle"]["border"].replace("px", "")) == 0 and
          data["actionStyle"]["backdropFilter"] in ("none", ""),
          f"detail action tray still has chrome of its own: "
          f"{data['actionStyle']}")
    check(data["actionChrome"] == {"head": 0, "close": 0, "note": 0},
          f"detail action tray kept its title/close/note chrome: "
          f"{data['actionChrome']}")

    volume = data["volume"]
    check(volume["hasSlider"] is True and volume["ariaLabel"] == "视频音量",
          f"detail volume control is missing: {volume}")
    check("detail-volume" in volume["toolsFirstChild"],
          f"detail volume control does not sit above the actions: {volume}")
    check(volume["value"] == "60" and volume["label"] == "60",
          f"detail volume control has the wrong default: {volume}")
    sizes = data["fontsSizes"]
    check(sizes["body"] >= 13 and sizes["action"] >= 15 and
          sizes["actionSub"] >= 9,
          f"detail copy did not grow: {sizes}")
    check(actions[4] > video[4] + 4 and actions[4] <= art_left + art_width - 0.2,
          f"detail action tray does not sit just outside the video right edge: "
          f"{actions} {video}")
    check(actions[5] > video[5] + 4 and actions[5] < art_top + art_height - 4,
          f"detail action tray does not sit just outside the video bottom edge: "
          f"{actions} {video}")
    check(actions[0] < video[4] and actions[1] < video[5] and
          actions[2] < video[2] * 0.4 and actions[3] < video[3] * 0.6,
          f"detail action tray has the wrong size or overlap: {actions} {video}")
    check([
        button["text"] for button in data["actionButtons"]
    ] == ["下载 Download", "在线游玩 Play online", "项目主页 Project page"],
          f"detail action buttons are wrong: {data['actionButtons']}")
    check([button["link"] for button in data["actionButtons"]] ==
          ["download", "play", "project"],
          f"detail action buttons lost their data keys: {data['actionButtons']}")
    download, play, project = data["actionButtons"]
    check("is-download" in download["className"] and
          "is-download" not in play["className"] and
          "is-download" not in project["className"],
          f"only the download action should be accented: "
          f"{data['actionButtons']}")
    # The first work ships every link, so all three actions are live.
    for button in (download, play, project):
        check(button["disabled"] is False and
              button["href"].startswith("https://example.com/"),
              f"detail action did not enable for a linked work: {button}")
        check(button["background"] == "rgb(255, 255, 255)" and
              button["cursor"] == "pointer" and
              float(button["borderWidth"].replace("px", "")) >= 0.5,
              f"enabled action is not a white outlined button: {button}")
    check(download["borderColor"] == "rgb(216, 74, 51)" and
          download["color"] == "rgb(216, 74, 51)",
          f"enabled download action lost its accent: {download}")
    for button in (play, project):
        check(button["borderColor"] == "rgb(10, 10, 10)" and
              button["color"] == "rgb(10, 10, 10)",
              f"enabled neutral action is not inked: {button}")

    check(all("serif" in font.lower() for font in data["fonts"].values()),
          f"detail page mixes in a non-serif face: {data['fonts']}")
    text = data["text"]
    check(text["work"] == "镜界" and text["team"] == "吴彦组" and
          text["from"] == "来自：" and
          "《镜界》" in text["body"] and "吴彦组" in text["body"],
          f"detail work copy is not bound to the fixture: {text}")
    check("镜界" in text["label"],
          f"detail slide label is stale: {text['label']}")
    state = data["state"]
    check({key: state[key] for key in
           ("index", "count", "teamId", "workTitle", "hasVideo",
            "links", "actionsPinned")} == {
        "index": 0, "count": 15, "teamId": 7, "workTitle": "镜界",
        "hasVideo": True,
        "links": {
            "download": "https://example.com/cea-gamejam-2026/works/07/build.zip",
            "play": "https://example.com/cea-gamejam-2026/works/07/play",
            "project": "https://example.com/cea-gamejam-2026/works/07"
        },
        "actionsPinned": False
    }, f"detail controller state is wrong: {state}")
    check(state["video"]["phase"] == "ready" and
          state["video"]["activeId"] == 7 and
          state["video"]["veilShown"] is False,
          f"detail clip state is wrong: {state['video']}")
    check(data["fadeCount"] == 3 and
          len(set(data["fadeInDelays"])) > 1 and
          len(set(data["fadeOutDelays"])) > 1,
          f"detail fade group is incomplete: {data}")

    log_before = page.evaluate(
        "window.__mirrorHome.detail.getState().video.log.length"
    )
    page.locator("#detailNext").click()
    page.wait_for_timeout(70)
    midway = page.evaluate("window.__mirrorHome.detail.getState()")
    forward_veil = page.evaluate(
        "getComputedStyle(document.getElementById('detailVideoVeil')).translate"
    )
    check(forward_veil.startswith("0px") and
          float(forward_veil.split()[1].rstrip("%")) > 0,
          f"forward switch did not enter from below: {forward_veil}")
    check(midway["index"] == 1 and midway["video"]["locked"] is True,
          f"detail switch did not start with a locked veil: {midway}")
    # Switches requested while the veil is moving must be dropped.
    page.evaluate("window.__mirrorHome.detail.next()")
    page.evaluate("window.__mirrorHome.detail.previous()")
    page.wait_for_timeout(120)
    still_locked = page.evaluate("window.__mirrorHome.detail.getState()")
    check(still_locked["index"] == 1,
          f"detail switch ignored the veil lock: {still_locked}")

    wait_video_ready(page)
    next_state = page.evaluate(
        """() => ({
          state: window.__mirrorHome.detail.getState(),
          title: document.getElementById('detailWork').textContent.trim(),
          team: document.getElementById('detailTeam').textContent.trim(),
          body: document.querySelector('.detail-intro-body').textContent.trim(),
          pagerCurrent: [...document.querySelectorAll('.detail-pager-dash')]
            .findIndex((el) => el.classList.contains('is-current')),
          buttons: [...document.querySelectorAll('.detail-action')].map((el) => {
            const style = getComputedStyle(el);
            return {
              link: el.dataset.link,
              disabled: el.disabled,
              color: style.color,
              borderColor: style.borderTopColor,
              background: style.backgroundColor
            };
          }),
          label: document.querySelector('.slide-detail').getAttribute('aria-label')
        })"""
    )
    check(next_state["state"]["index"] == 1 and
          next_state["state"]["workTitle"] == "破镜" and
          next_state["title"] == "破镜" and
          next_state["team"] == "欢乐斗地组" and
          "《破镜》" in next_state["body"] and
          next_state["pagerCurrent"] == 1 and
          "破镜" in next_state["label"],
          f"detail next work did not update: {next_state}")
    check(next_state["state"]["video"]["phase"] == "ready" and
          next_state["state"]["video"]["activeId"] == 8,
          f"detail clip did not settle on the second work: {next_state}")
    next_log = next_state["state"]["video"]["log"]
    cycle = next_log[log_before:] if log_before <= len(next_log) else next_log
    check(cycle == ["entering", "loading", "exiting", "ready"],
          f"detail veil did not run exactly one enter/exit cycle: {cycle}")

    # Backward switches wipe from the top instead of the bottom.
    page.locator("#detailPrev").click()
    page.wait_for_timeout(70)
    backward_veil = page.evaluate(
        "getComputedStyle(document.getElementById('detailVideoVeil')).translate"
    )
    check(backward_veil.startswith("0px") and
          float(backward_veil.split()[1].rstrip("%")) < 0,
          f"backward switch did not enter from above: {backward_veil}")
    wait_video_ready(page)
    check(page.evaluate("window.__mirrorHome.detail.getState().index") == 0,
          "backward switch did not return to the first work")
    page.locator("#detailNext").click()
    wait_video_ready(page)
    check(page.evaluate("window.__mirrorHome.detail.getState().index") == 1,
          "forward switch did not return to the second work")

    # Volume slider drives the active clip.
    page.evaluate(
        "const el = document.getElementById('detailVolume');"
        "el.value = '25'; el.dispatchEvent(new Event('input', { bubbles: true }));"
    )
    page.wait_for_timeout(160)
    volume_after = page.evaluate(
        """() => {
          const slot = document.querySelector('.detail-video-slot.is-active');
          return {
            ui: document.getElementById('detailVolumeValue').textContent.trim(),
            value: slot ? slot.volume : null
          };
        }"""
    )
    check(volume_after["ui"] == "25" and
          abs(volume_after["value"] - 0.25) <= 0.01,
          f"detail volume control did not reach the clip: {volume_after}")
    page.evaluate(
        "const el = document.getElementById('detailVolume');"
        "el.value = '60'; el.dispatchEvent(new Event('input', { bubbles: true }));"
    )
    page.wait_for_timeout(120)

    # Using the slider must not pin the stack open: after the click the tools
    # still follow hover (regression guard for the old :focus-within rule).
    video_hover_box = page.locator(".detail-video").bounding_box()
    page.mouse.move(
        video_hover_box["x"] + video_hover_box["width"] * 0.5,
        video_hover_box["y"] + video_hover_box["height"] * 0.5,
        steps=4,
    )
    page.wait_for_timeout(260)
    slider_box = page.locator("#detailVolume").bounding_box()
    page.mouse.move(
        slider_box["x"] + slider_box["width"] * 0.5,
        slider_box["y"] + slider_box["height"] * 0.5,
        steps=4,
    )
    page.wait_for_timeout(200)
    page.mouse.down()
    page.mouse.up()
    page.wait_for_timeout(200)
    page.mouse.move(5, 5)
    page.wait_for_timeout(420)
    tools_hidden = page.evaluate(
        "getComputedStyle(document.getElementById('detailTools')).visibility"
    )
    check(tools_hidden == "hidden",
          "detail tools stayed open after using the volume slider")
    page.mouse.move(
        video_hover_box["x"] + video_hover_box["width"] * 0.5,
        video_hover_box["y"] + video_hover_box["height"] * 0.5,
        steps=4,
    )
    page.wait_for_timeout(320)
    tools_shown = page.evaluate(
        "getComputedStyle(document.getElementById('detailTools')).visibility"
    )
    check(tools_shown == "visible",
          "detail tools stopped following hover after the volume slider")
    page.mouse.move(5, 5)
    page.wait_for_timeout(320)

    # This fixture work only ships a download link.
    second_buttons = {button["link"]: button for button in next_state["buttons"]}
    check(second_buttons["download"]["disabled"] is False,
          f"download should stay enabled for a linked work: {next_state}")
    for key in ("play", "project"):
        button = second_buttons[key]
        check(button["disabled"] is True and
              button["background"] == "rgba(255, 255, 255, 0.62)" and
              button["borderColor"] == "rgba(10, 10, 10, 0.22)" and
              button["color"] == "rgba(10, 10, 10, 0.34)",
              f"unlinked action is not disabled and faded: {button}")

    video_box = page.locator(".detail-video").bounding_box()
    hover_x = video_box["x"] + video_box["width"] * 0.62
    hover_y = video_box["y"] + video_box["height"] * 0.55
    page.mouse.move(hover_x, hover_y, steps=5)
    page.wait_for_timeout(320)
    hover = page.evaluate(
        """() => {
          const panel = document.getElementById('detailTools');
          const style = getComputedStyle(panel);
          return {
            opacity: style.opacity,
            visibility: style.visibility,
            pointerEvents: style.pointerEvents,
            expanded: document.getElementById('detailVideoFrame')
              .getAttribute('aria-expanded'),
            videoHover: document.querySelector('.detail-video').matches(':hover')
          };
        }"""
    )
    check(hover["opacity"] == "1" and hover["visibility"] == "visible" and
          hover["pointerEvents"] == "auto" and hover["videoHover"] is True,
          f"video hover did not reveal the action tray: {hover}")

    open_tray = page.evaluate(
        """() => {
          const rect = document.getElementById('detailTools').getBoundingClientRect();
          return [rect.x, rect.y, rect.width, rect.height, rect.right, rect.bottom];
        }"""
    )
    page.mouse.move(open_tray[4] - 12, open_tray[5] - 12, steps=4)
    page.wait_for_timeout(260)
    outside_hover = page.evaluate(
        """() => {
          const panel = document.getElementById('detailTools');
          return {
            visible: getComputedStyle(panel).visibility,
            panelHover: panel.matches(':hover'),
            videoHover: document.querySelector('.detail-video').matches(':hover')
          };
        }"""
    )
    check(outside_hover["visible"] == "visible" and
          outside_hover["panelHover"] is True and
          outside_hover["videoHover"] is False,
          f"action tray does not survive the pointer crossing its outer corner: "
          f"{outside_hover}")



    page.mouse.move(
        video_box["x"] + video_box["width"] * 0.4,
        video_box["y"] + video_box["height"] * 0.4,
    )
    page.wait_for_timeout(120)
    page.locator(".detail-video").click()
    page.wait_for_timeout(160)
    pinned = page.evaluate(
        """() => ({
          state: window.__mirrorHome.detail.getState(),
          expanded: document.getElementById('detailVideoFrame')
            .getAttribute('aria-expanded')
        })"""
    )
    check(pinned["state"]["actionsPinned"] is True and
          pinned["expanded"] == "true",
          f"detail video click cannot pin the actions: {pinned}")
    page.mouse.move(5, 5)
    page.wait_for_timeout(320)
    pinned_visual = page.evaluate(
        "getComputedStyle(document.getElementById('detailTools')).visibility"
    )
    check(pinned_visual == "visible",
          f"pinned action tray hid when the pointer left: {pinned_visual}")

    # With the tray pinned it stays visible, so the hover fill can be read
    # without the hover-reveal racing the pointer. This work links a download.
    page.hover(".detail-action.is-download")
    page.wait_for_timeout(260)
    download_hover = page.evaluate(
        """() => {
          const style = getComputedStyle(
            document.querySelector('.detail-action.is-download')
          );
          return {
            background: style.backgroundColor,
            color: style.color,
            borderColor: style.borderTopColor
          };
        }"""
    )
    check(download_hover["background"] == "rgb(216, 74, 51)" and
          download_hover["color"] == "rgb(255, 255, 255)" and
          download_hover["borderColor"] == "rgb(216, 74, 51)",
          f"download action hover is not accent-filled: {download_hover}")

    page.keyboard.press("Escape")
    page.wait_for_timeout(320)
    closed = page.evaluate(
        """() => ({
          state: window.__mirrorHome.detail.getState(),
          expanded: document.getElementById('detailVideoFrame')
            .getAttribute('aria-expanded'),
          visibility: getComputedStyle(document.getElementById('detailTools')).visibility
        })"""
    )
    check(closed["state"]["actionsPinned"] is False and
          closed["expanded"] == "false" and
          closed["visibility"] == "hidden",
          f"detail action tray did not close on Escape: {closed}")

    page.locator(".detail-video").click()
    page.wait_for_timeout(200)
    check(page.evaluate("window.__mirrorHome.detail.getState().actionsPinned") is True,
          "detail video click did not reopen the action tray")
    page.mouse.click(art_left + 20, art_top + 20)
    page.wait_for_timeout(260)
    check(page.evaluate("window.__mirrorHome.detail.getState().actionsPinned") is False,
          "clicking outside the detail video did not close the action tray")

    # Third fixture work: no video, but every link. The panel must empty itself
    # and the neutral actions must become live.
    page.locator("#detailNext").click()
    wait_video_ready(page)
    empty_state = page.evaluate(
        """() => {
          const frame = document.getElementById('detailVideoFrame');
          const media = document.querySelector('.detail-video-slot.is-active');
          return {
            state: window.__mirrorHome.detail.getState(),
            title: document.getElementById('detailWork').textContent.trim(),
            frameClass: frame.className,
            aria: frame.getAttribute('aria-label'),
            mediaSrc: media ? media.getAttribute('src') : null,
            paused: media ? media.paused : true,
            readyState: media ? media.readyState : 0,
            placeholder: (() => {
              const box = document.querySelector('.detail-video-placeholder');
              if (!box) return null;
              return {
                display: getComputedStyle(box).display,
                title: box.querySelector('.detail-video-placeholder-title')
                  .textContent.trim(),
                sub: box.querySelector('.detail-video-placeholder-sub')
                  .textContent.trim()
              };
            })(),
            stageRatio: (() => {
              const rect = document.getElementById('detailVideoStage')
                .getBoundingClientRect();
              return rect.width / rect.height;
            })(),
            buttons: [...document.querySelectorAll('.detail-action')].map((el) => ({
              link: el.dataset.link,
              disabled: el.disabled,
              href: el.dataset.href || ''
            }))
          };
        }"""
    )
    check(empty_state["state"]["index"] == 2 and
          empty_state["state"]["hasVideo"] is False,
          f"third work is not the video-less fixture: {empty_state}")
    check(empty_state["mediaSrc"] is None and empty_state["paused"] is True,
          f"video-less work still plays a clip: {empty_state}")
    check("is-video-empty" in empty_state["frameClass"] and
          "has-video" not in empty_state["frameClass"] and
          "暂无" in empty_state["aria"],
          f"video-less work did not mark the panel empty: {empty_state}")
    placeholder = empty_state["placeholder"]
    check(placeholder is not None and placeholder["display"] == "grid" and
          placeholder["title"] == "暂无视频" and
          placeholder["sub"] == "No clip yet",
          f"video-less work did not show its placeholder: {placeholder}")
    check(abs(empty_state["stageRatio"] - 988 / 586) <= 0.02,
          f"empty stage lost the clip ratio: {empty_state}")
    check(all(button["disabled"] is False and
              button["href"].startswith("https://example.com/")
              for button in empty_state["buttons"]),
          f"video-less work did not keep its links live: {empty_state}")

    video_box = page.locator(".detail-video").bounding_box()
    page.mouse.move(
        video_box["x"] + video_box["width"] * 0.5,
        video_box["y"] + video_box["height"] * 0.5,
        steps=4,
    )
    page.wait_for_timeout(320)
    page.locator(".detail-video").click()
    page.wait_for_timeout(200)
    page.hover('.detail-action[data-link="play"]')
    page.wait_for_timeout(260)
    neutral_hover = page.evaluate(
        """() => {
          const style = getComputedStyle(
            document.querySelector('.detail-action[data-link="play"]')
          );
          return {
            background: style.backgroundColor,
            color: style.color,
            borderColor: style.borderTopColor
          };
        }"""
    )
    check(neutral_hover["background"] == "rgb(10, 10, 10)" and
          neutral_hover["color"] == "rgb(255, 255, 255)" and
          neutral_hover["borderColor"] == "rgb(10, 10, 10)",
          f"neutral action hover is not ink-filled: {neutral_hover}")
    page.mouse.click(art_left + 20, art_top + 20)
    page.wait_for_timeout(200)

    # Boundaries hand the gesture to the deck instead of wrapping works.
    page.evaluate("window.__mirrorHome.detail.select(0)")
    wait_video_ready(page)
    page.locator("#detailPrev").click()
    wait_unlocked(page)
    page.wait_for_timeout(320)
    check(page.evaluate("window.__mirrorHome.deck.getState().index") == 2 and
          page.evaluate("window.__mirrorHome.detail.getState().index") == 0,
          "previous on the first work did not turn back a page")

    page.evaluate("window.__mirrorHome.deck.goTo(3)")
    wait_unlocked(page)
    wait_video_ready(page)
    page.evaluate("window.__mirrorHome.detail.select(14)")
    wait_video_ready(page)
    page.locator("#detailNext").click()
    wait_unlocked(page)
    page.wait_for_timeout(200)
    after_last = page.evaluate(
        """() => ({
          deck: window.__mirrorHome.deck.getState().index,
          work: window.__mirrorHome.detail.getState().index
        })"""
    )
    check(after_last == {"deck": 4, "work": 14},
          f"next on the last work did not open the closing page: {after_last}")

    page.evaluate("window.__mirrorHome.deck.goTo(3)")
    wait_unlocked(page)
    wait_video_ready(page)
    page.evaluate("window.__mirrorHome.detail.select(1)")
    wait_video_ready(page)
    check(page.evaluate("window.__mirrorHome.detail.getState().index") == 1,
          "detail select did not land on the second work")
    reused = page.evaluate(
        "window.__mirrorHome.detail.getState().video.log.slice(-4)"
    )
    check(reused == ["entering", "loading", "exiting", "ready"],
          f"warm work did not replay a short veil cycle: {reused}")

    page.mouse.move(art_left + art_width / 2, art_top + art_height / 2)
    page.wait_for_timeout(120)
    page.mouse.wheel(0, 120)
    page.wait_for_function(
        "window.__mirrorHome.detail.getState().index === 2",
        timeout=8000,
    )
    page.mouse.wheel(0, 120)
    wait_video_ready(page)
    wheeled = page.evaluate(
        """() => ({
          deck: window.__mirrorHome.deck.getState(),
          detail: window.__mirrorHome.detail.getState(),
          title: document.getElementById('detailWork').textContent.trim(),
          pagerCurrent: [...document.querySelectorAll('.detail-pager-dash')]
            .findIndex((el) => el.classList.contains('is-current'))
        })"""
    )
    check(wheeled["deck"]["index"] == 3 and
          wheeled["detail"]["index"] == 2 and
          wheeled["title"] == "镜间" and
          wheeled["pagerCurrent"] == 2,
          f"wheel inside the detail frame did not switch works: {wheeled}")
    page.wait_for_timeout(1100)
    page.mouse.wheel(0, -120)
    page.wait_for_function(
        "window.__mirrorHome.detail.getState().index === 1",
        timeout=8000,
    )
    wait_video_ready(page)
    back = page.evaluate(
        """() => ({
          deck: window.__mirrorHome.deck.getState(),
          detail: window.__mirrorHome.detail.getState(),
          pagerCurrent: [...document.querySelectorAll('.detail-pager-dash')]
            .findIndex((el) => el.classList.contains('is-current'))
        })"""
    )
    check(back["deck"]["index"] == 3 and back["detail"]["index"] == 1 and
          back["pagerCurrent"] == 1,
          f"detail wheel up did not return one work: {back}")

    page.mouse.move(art_left - 28, art_top + art_height / 2)
    page.wait_for_timeout(650)
    page.mouse.wheel(0, -120)
    wait_unlocked(page)
    check(page.evaluate("window.__mirrorHome.deck.getState().index") == 2,
          "wheel outside the detail frame did not resume deck navigation")
    print("detail page: ok")

def assert_end_page(page):
    """Closing page: two 45deg cuts centred on the left/right edge midpoints."""
    if page.evaluate("window.__mirrorHome.deck.getState().index") != 3:
        page.evaluate("window.__mirrorHome.deck.goTo(3)")
        wait_unlocked(page)
        wait_video_ready(page)
        page.wait_for_timeout(700)
    page.mouse.move(5, 5)
    page.wait_for_timeout(220)
    before = page.evaluate(
        """() => {
          const art = document.getElementById('art');
          return {
            mode: art.dataset.ruleMode,
            rules: [...document.querySelectorAll('.sheet-rule')].map((el) => {
              const r = el.getBoundingClientRect();
              return { cx: r.x + r.width / 2, cy: r.y + r.height / 2 };
            })
          };
        }"""
    )
    check(before["mode"] == "detail",
          f"closing transition did not start from the detail rules: {before['mode']}")

    page.evaluate("window.__mirrorHome.deck.goTo(4)")
    samples = page.evaluate(
        """async () => {
          const el = document.getElementById('sheetRuleA');
          const out = [];
          const start = performance.now();
          await new Promise((resolve) => {
            function tick(now) {
              const m = new DOMMatrixReadOnly(getComputedStyle(el).transform);
              out.push({ t: Math.round(now - start), a: m.a, b: m.b });
              if (now - start > 900) { resolve(); return; }
              requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
          });
          return out;
        }"""
    )
    wait_unlocked(page)
    page.wait_for_timeout(600)
    page.mouse.move(5, 5)
    page.evaluate("window.__mirrorHome.parallax?.reset()")
    page.wait_for_timeout(450)
    data = page.evaluate(
        """() => {
          const art = document.getElementById('art');
          const artRect = art.getBoundingClientRect();
          const slide = document.querySelector('.slide-end');
          const slideRect = slide.getBoundingClientRect();
          const rectOf = (el) => {
            const r = el.getBoundingClientRect();
            return [r.x, r.y, r.width, r.height, r.right, r.bottom];
          };
          const rules = [...document.querySelectorAll('.sheet-rule')].map((el) => {
            const r = el.getBoundingClientRect();
            const m = new DOMMatrixReadOnly(getComputedStyle(el).transform);
            return {
              cx: r.x + r.width / 2,
              cy: r.y + r.height / 2,
              width: r.width,
              height: r.height,
              a: m.a,
              b: m.b
            };
          });
          const logo = slide.querySelector('.end-logo');
          const note = slide.querySelector('.end-note');
          const noteMain = slide.querySelector('.end-note-main');
          const noteSub = slide.querySelector('.end-note-sub');
          return {
            mode: art.dataset.ruleMode,
            deckScroll: [
              document.getElementById('deck').scrollLeft,
              document.getElementById('deck').scrollTop
            ],
            art: [artRect.x, artRect.y, artRect.width, artRect.height,
                  artRect.right, artRect.bottom],
            slide: [slideRect.x, slideRect.y, slideRect.width, slideRect.height],
            overflow: [slide.scrollWidth, slide.clientWidth,
                       slide.scrollHeight, slide.clientHeight],
            active: slide.classList.contains('is-active'),
            ariaHidden: slide.getAttribute('aria-hidden'),
            label: slide.getAttribute('aria-label'),
            rules,
            logo: rectOf(logo),
            logoNatural: [logo.naturalWidth, logo.naturalHeight],
            logoSrc: logo.getAttribute('src') || '',
            logoAlt: logo.getAttribute('alt') || '',
            note: rectOf(note),
            noteText: note.textContent.replace(/\\s+/g, ' ').trim(),
            noteColor: getComputedStyle(noteMain).color,
            subColor: getComputedStyle(noteSub).color,
            fadeCount: [...slide.querySelectorAll('[data-fade]')].length,
            next: document.getElementById('deckNext').disabled,
            prev: document.getElementById('deckPrev').disabled,
            state: window.__mirrorHome.deck.getState()
          };
        }"""
    )
    check(data["mode"] == "end",
          f"closing page did not switch the sheet rules: {data['mode']}")
    check(data["deckScroll"] == [0, 0],
          f"closing page deck is scrolled: {data['deckScroll']}")
    check(data["active"] is True and data["ariaHidden"] == "false" and
          data["label"] == "结束",
          f"closing slide is not the active slide: {data}")
    check(data["overflow"][0] <= data["overflow"][1] + 2 and
          data["overflow"][2] <= data["overflow"][3] + 2,
          f"closing page overflows: {data['overflow']}")
    check(data["state"]["index"] == EXPECTED_COUNT - 1 and data["next"] is True and
          data["prev"] is False,
          f"closing page is not the deck end: {data['state']}")

    art_x, art_y, art_w, art_h, art_right, art_bottom = data["art"]
    art_cy = art_y + art_h / 2
    check(len(data["rules"]) == 2,
          f"closing page should keep two sheet rules: {data['rules']}")
    if len(data["rules"]) == 2:
        # A framed the content top and must land on the top-right cut (the
        # right short edge); B framed the bottom and lands bottom-left.
        top_rule, bottom_rule = data["rules"]
        left_cut, right_cut = sorted(data["rules"], key=lambda cut: cut["cx"])
        check(top_rule["cx"] > bottom_rule["cx"],
              f"closing cuts are swapped: the top rule should settle on the right "
              f"edge, got A={top_rule['cx']:.1f} B={bottom_rule['cx']:.1f}")
        for cut, side in ((left_cut, art_x), (right_cut, art_right)):
            check(abs(cut["a"] + 0.7071) <= 0.01 and abs(cut["b"] + 0.7071) <= 0.01,
                  f"closing cut is not a 225deg bar: {cut}")
            # The bar is twice the content axis, so its composited bounding box
            # can snap by a pixel or two at fractional DPR.
            check(abs(cut["cx"] - side) <= 2.5 and abs(cut["cy"] - art_cy) <= 2.5,
                  f"closing cut is not centred on the short edge midpoint: "
                  f"{cut} in {data['art']}")
    check(len(samples) > 10, f"closing turn produced no frames: {samples[:3]}")
    if samples:
        check(max(entry["b"] for entry in samples) <= 0.01 and
              min(entry["b"] for entry in samples) <= -0.5,
              f"closing cut did not turn clockwise from 180deg: {samples[:6]}")
        check(all(later["b"] <= earlier["b"] + 0.02
                  for earlier, later in zip(samples, samples[1:])),
              f"closing cut reversed direction mid-turn: {samples}")

    logo = data["logo"]
    note = data["note"]
    check(min(data["logoNatural"]) > 0 and
          data["logoSrc"].endswith("cea-logo.svg"),
          f"closing logo did not load: {data['logoNatural']} {data['logoSrc']}")
    check(len(data["logoAlt"]) > 2, f"closing logo lost its alt text: {data['logoAlt']}")
    check(abs((logo[0] + logo[2] / 2) - (art_x + art_w / 2)) <= 2,
          f"closing logo is not centred horizontally: {logo} in {data['art']}")
    check(abs(((logo[1] + note[5]) / 2) - art_cy) <= 6,
          f"closing lockup is not centred vertically: {logo} {note} in {data['art']}")
    check(note[1] >= logo[5] + 8,
          f"closing detail is not below the logo: {note} {logo}")
    for key in ("noteColor", "subColor"):
        color = data[key]
        alpha = 1.0
        if color.startswith("rgba"):
            alpha = float(color.rsplit(",", 1)[1].rstrip(")").strip())
        check(alpha <= 0.6, f"closing detail is not muted ({key}={color})")
    check("苏州大学计算机爱好者协会" in data["noteText"] and
          "DarkskyX" in data["noteText"],
          f"closing detail is missing its placeholder copy: {data['noteText']}")
    check(0.17 <= logo[2] / art_w <= 0.26,
          f"closing logo has the wrong scale: {logo[2] / art_w:.3f} of {data['art']}")
    check(data["fadeCount"] >= 2,
          f"closing lockup is outside the fade group: {data['fadeCount']}")

    page.locator("#deckPrev").click()
    wait_unlocked(page)
    page.wait_for_timeout(800)
    back = page.evaluate(
        """() => {
          const m = new DOMMatrixReadOnly(
            getComputedStyle(document.getElementById('sheetRuleA')).transform
          );
          return {
            mode: document.getElementById('art').dataset.ruleMode,
            rule: { a: m.a, b: m.b },
            index: window.__mirrorHome.deck.getState().index,
            active: document.querySelector('#deck .slide.is-active')
              .getAttribute('aria-label')
          };
        }"""
    )
    check(back["mode"] == "detail" and back["index"] == 3 and
          abs(back["rule"]["a"] + 1) <= 0.01 and abs(back["rule"]["b"]) <= 0.01,
          f"closing page did not hand the rules back to the detail layout: {back}")
    check(str(back["active"]).startswith("作品详情"),
          f"closing page did not return to the work detail: {back}")
    print("closing page: ok")


def assert_detail_loading_switch(browser):
    """Switching while the clip is still loading must retarget, not re-enter.

    The media request is held with the Fetch domain so the loading phase can be
    observed deterministically instead of racing a cached clip.
    """
    page, context, errors = open_page(browser, width=1440, height=900, dpr=1)
    try:
        page.bring_to_front()
        client = context.new_cdp_session(page)
        paused = []
        client.on("Fetch.requestPaused", lambda event: paused.append(event))
        client.send(
            "Fetch.enable",
            {"patterns": [{"urlPattern": "*video-placeholder.mp4*"}]},
        )
        wait_deck(page)
        page.wait_for_timeout(300)
        page.evaluate("window.__mirrorHome.deck.goTo(3)")
        wait_unlocked(page)
        page.wait_for_function(
            "window.__mirrorHome.detail.getState().video.phase === 'loading'",
            timeout=10000,
        )
        before = page.evaluate(
            """() => {
              const state = window.__mirrorHome.detail.getState();
              return {
                index: state.index,
                phase: state.video.phase,
                log: state.video.log,
                pendingId: state.video.pendingId,
                translate: getComputedStyle(
                  document.getElementById('detailVideoVeil')
                ).translate
              };
            }"""
        )
        check(before["phase"] == "loading" and before["pendingId"] is not None,
              f"detail loading phase was not reached: {before}")

        page.evaluate("window.__mirrorHome.detail.next()")
        page.wait_for_timeout(280)
        mid = page.evaluate(
            """() => {
              const state = window.__mirrorHome.detail.getState();
              return {
                index: state.index,
                phase: state.video.phase,
                log: state.video.log,
                pendingId: state.video.pendingId,
                name: document.getElementById('detailVideoVeilName').textContent.trim(),
                translate: getComputedStyle(
                  document.getElementById('detailVideoVeil')
                ).translate,
                hidden: document.getElementById('detailVideoVeil')
                  .getAttribute('aria-hidden')
              };
            }"""
        )
        check(mid["index"] == before["index"] + 1 and mid["phase"] == "loading",
              f"detail switch during loading did not retarget: {mid}")
        check(mid["log"] == before["log"],
              f"detail switch during loading replayed the veil: "
              f"{before['log']} -> {mid['log']}")
        check(mid["pendingId"] != before["pendingId"],
              f"detail pending clip did not change while loading: {mid}")
        check(mid["hidden"] == "false" and mid["translate"] == before["translate"],
              f"detail veil moved while it should stay parked: {mid}")
        check(mid["name"] == "破镜",
              f"detail veil name did not follow the new work: {mid}")

        for event in list(paused):
            try:
                client.send("Fetch.continueRequest",
                            {"requestId": event["requestId"]})
            except Exception:  # noqa: BLE001 - already continued/aborted
                pass
        wait_video_ready(page, timeout=20000)
        final = page.evaluate(
            """() => {
              const state = window.__mirrorHome.detail.getState();
              return {
                index: state.index,
                phase: state.video.phase,
                log: state.video.log.slice(-2)
              };
            }"""
        )
        check(final["index"] == before["index"] + 1 and
              final["phase"] == "ready" and
              final["log"] == ["exiting", "ready"],
              f"detail loading switch did not finish cleanly: {final}")

        # Failure path: a clip that cannot load must leave the veil in place.
        # Step onto the clip-less fixture (index 2); the following switch then
        # moves to a work that does carry a clip and can be failed on purpose.
        for _ in range(4):
            if page.evaluate("window.__mirrorHome.detail.getState().index") == 2:
                break
            page.evaluate("window.__mirrorHome.detail.next()")
            wait_video_ready(page)
        check(page.evaluate("window.__mirrorHome.detail.getState().index") == 2,
              "the failure fixture did not reach the clip-less work")
        active_before = page.evaluate(
            "window.__mirrorHome.detail.getState().video.activeId"
        )
        paused.clear()
        page.evaluate("window.__mirrorHome.detail.next()")
        page.wait_for_function(
            "window.__mirrorHome.detail.getState().video.phase === 'loading'",
            timeout=10000,
        )
        page.wait_for_timeout(200)
        for _ in range(3):
            if not paused:
                page.wait_for_timeout(250)
            for event in list(paused):
                try:
                    client.send(
                        "Fetch.failRequest",
                        {"requestId": event["requestId"],
                         "errorReason": "Failed"},
                    )
                except Exception:  # noqa: BLE001 - already settled
                    pass
            paused.clear()
            page.wait_for_timeout(250)
        failed = page.evaluate(
            """() => {
              const veil = document.getElementById('detailVideoVeil');
              const state = window.__mirrorHome.detail.getState();
              return {
                phase: state.video.phase,
                activeId: state.video.activeId,
                hidden: veil.getAttribute('aria-hidden'),
                translate: getComputedStyle(veil).translate,
                error: veil.classList.contains('is-error'),
                meta: document.getElementById('detailVideoVeilMeta')
                  .textContent.trim()
              };
            }"""
        )
        check(failed["phase"] == "loading" and failed["hidden"] == "false",
              f"detail veil left the panel after a load error: {failed}")
        check(failed["translate"] in ("0px 0px", "0px 0%"),
              f"detail veil moved away after a load error: {failed}")
        check(failed["error"] is True and failed["meta"] == "加载失败",
              f"detail veil did not show the error state: {failed}")
        check(failed["activeId"] == active_before,
              f"detail clip switched even though the load failed: {failed}")

        # Recovery: the next work with a working clip must clear the veil.
        paused.clear()
        page.evaluate("window.__mirrorHome.detail.next()")
        page.wait_for_function(
            "window.__mirrorHome.detail.getState().video.phase === 'loading'",
            timeout=10000,
        )
        for _ in range(4):
            page.wait_for_timeout(250)
            for event in list(paused):
                try:
                    client.send(
                        "Fetch.continueRequest",
                        {"requestId": event["requestId"]},
                    )
                except Exception:  # noqa: BLE001 - already settled
                    pass
            if page.evaluate(
                "window.__mirrorHome.detail.getState().video.phase"
            ) == "ready":
                break
        wait_video_ready(page, timeout=20000)
        recovered = page.evaluate(
            """() => ({
              phase: window.__mirrorHome.detail.getState().video.phase,
              hidden: document.getElementById('detailVideoVeil')
                .getAttribute('aria-hidden'),
              error: document.getElementById('detailVideoVeil')
                .classList.contains('is-error')
            })"""
        )
        check(recovered["phase"] == "ready" and recovered["hidden"] == "true" and
              recovered["error"] is False,
              f"detail veil did not recover after an error: {recovered}")

        unexpected = [
            error for error in errors
            if "ERR_FAILED" not in error and "Failed to load resource" not in error
        ]
        check(not unexpected,
              "console/page errors: " + "\n".join(unexpected))
        print("detail loading switch: ok")
    finally:
        context.close()


def assert_pointer_all_slides(page):
    art = page.evaluate(
        """() => {
          const r = document.getElementById('art').getBoundingClientRect();
          return {x: r.x, y: r.y, width: r.width, height: r.height};
        }"""
    )
    for index in (0, 2, 3, 4):
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

    resized_at = time.monotonic()
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

    # resizeEnd fires after the mirror's 500ms debounce; the veil then holds
    # 475ms and leaves over 250ms, so it must be gone around 1.22s after the
    # viewport change instead of the earlier ~1.95s.
    page.wait_for_function(
        """() => {
          const veil = document.getElementById('structureVeil');
          const style = getComputedStyle(veil);
          return !veil.classList.contains('is-visible') &&
                 style.visibility === 'hidden';
        }""",
        polling=50,
        timeout=4000,
    )
    gone_after_ms = (time.monotonic() - resized_at) * 1000
    check(1050 <= gone_after_ms <= 1700,
          f"structure veil left at {gone_after_ms:.0f}ms after the resize; "
          "expected the shortened ~1.22s budget")
    settled = page.evaluate(
        """() => {
          const veil = document.getElementById('structureVeil');
          const style = getComputedStyle(veil);
          return {
            visible: veil.classList.contains('is-visible'),
            opacity: Number(style.opacity),
            visibility: style.visibility,
            exitDuration: style.transitionDuration
          };
        }"""
    )
    check(settled["visible"] is False and
          (settled["opacity"] < 0.01 or settled["visibility"] == "hidden"),
          f"structure veil did not fade out: {settled}")
    check(settled["exitDuration"].startswith("0.25s"),
          f"structure veil exit is not the shortened 250ms fade: {settled}")
    print(f"structure veil: ok ({gone_after_ms:.0f}ms after resize)")


def assert_cover_defaults(page):
    """The tuning panel is gone; its two knobs are baked into the stylesheet."""
    data = page.evaluate(
        """() => {
          const art = document.getElementById('art').getBoundingClientRect();
          const cover = document.querySelector('.slide-cover');
          const coverRect = cover.getBoundingClientRect();
          const lockup = cover.querySelector('.cover-lockup').getBoundingClientRect();
          const sideEl = cover.querySelector('.cover-side');
          const side = sideEl.getBoundingClientRect();
          const rule = document.getElementById('sheetRuleB').getBoundingClientRect();
          const rootStyle = getComputedStyle(document.documentElement);
          return {
            tunerNodes: document.querySelectorAll(
              '#tuner, .tuner, #tuneBody, #tuneToggle, [id^="tune"]'
            ).length,
            art: [art.x, art.y, art.width, art.height],
            lockup: [lockup.x, lockup.y, lockup.width, lockup.height],
            side: [side.x, side.y, side.width, side.height, side.right, side.bottom],
            // Measured against the slide box, which is the positioning context,
            // so a transient mirror-wide offset cannot fake it.
            rightNudge: side.right - coverRect.right,
            bottomFlush: coverRect.bottom - side.bottom,
            ruleHeight: rule.height,
            ruleSpan: rule.width,
            ruleBottom: rule.bottom,
            coverBottom: coverRect.bottom,
            textGap: rule.top - lockup.bottom,
            barVar: rootStyle.getPropertyValue('--cover-bar-height').trim(),
            gapVar: rootStyle.getPropertyValue('--cover-bottom-gap').trim(),
            textYVar: rootStyle.getPropertyValue('--cover-text-y').trim(),
            scaleVar: rootStyle.getPropertyValue('--cover-art-scale').trim(),
            scale: getComputedStyle(sideEl).scale,
            imageLoaded: (() => {
              const image = cover.querySelector('.cover-side img');
              return !!image && image.complete && image.naturalWidth > 0;
            })()
          };
        }"""
    )
    check(data["tunerNodes"] == 0,
          f"the tuning panel is still in the document: {data['tunerNodes']}")
    check(data["barVar"] == "6px" and data["gapVar"] == "32px" and
          data["textYVar"] == "0px" and data["scaleVar"] == "1.5",
          f"cover defaults are not the baked values: {data}")
    check(abs(data["ruleHeight"] - 6) <= 0.5,
          f"cover bottom line is not 6px: {data}")
    check(data["ruleSpan"] >= data["art"][2] - 2,
          f"cover bottom line does not span the content: {data}")
    check(abs(data["ruleBottom"] - data["coverBottom"]) <= 0.6,
          f"cover bottom line is not on the content bottom: {data}")
    check(abs(data["textGap"] - 32) <= 1,
          f"cover text bottom gap is not 32px: {data}")
    check(abs(float(data["scale"]) - 1.5) <= 0.01,
          f"cover image is not scaled to 150%: {data}")
    check(abs(data["rightNudge"] - 2) <= 0.6,
          f"cover image lost its 2px right nudge: {data}")
    check(abs(data["bottomFlush"]) <= 0.6,
          f"cover image is not flush to the content bottom: {data}")
    check(data["imageLoaded"] is True, f"cover sideview image is missing: {data}")
    check(page.evaluate(
        "document.getElementById('structureVeil').classList.contains('is-visible')"
    ) is False, "reading the cover pulsed the structure veil")
    print("cover defaults: ok")


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

        page.screenshot(path=str(SHOT_DIR / "probe-deck-mobile.png"), scale="css")
        page.evaluate("window.__mirrorHome.deck.goTo(3)")
        wait_unlocked(page)
        wait_video_ready(page)
        page.wait_for_timeout(500)
        page.mouse.move(4, 4)
        page.wait_for_timeout(200)
        detail = page.evaluate(
            """() => {
              const slide = document.querySelector('.slide-detail');
              const art = document.getElementById('art').getBoundingClientRect();
              const rectOf = (el) => {
                const r = el.getBoundingClientRect();
                return [r.x, r.y, r.width, r.height, r.right, r.bottom];
              };
              const rules = [...document.querySelectorAll('.sheet-rule')].map(rectOf);
              const panel = document.getElementById('detailTools');
              return {
                art: [art.x, art.y, art.width, art.height, art.right, art.bottom],
                rules,
                intro: rectOf(slide.querySelector('.detail-intro')),
                title: rectOf(slide.querySelector('.detail-intro-title')),
                titleBorder: getComputedStyle(
                  slide.querySelector('.detail-intro-title')
                ).borderTopWidth,
                video: rectOf(slide.querySelector('.detail-video')),
                footer: rectOf(slide.querySelector('.detail-footer')),
                panel: rectOf(panel),
                panelVisibility: getComputedStyle(panel).visibility,
                sideCount: slide.querySelectorAll('.detail-side').length,
                oldAwardCount: slide.querySelectorAll('.detail-award').length,
                overflow: [slide.scrollWidth, slide.clientWidth,
                           slide.scrollHeight, slide.clientHeight],
                mediaReady: (() => {
                  const media = slide.querySelector('.detail-video-slot.is-active');
                  return !!media && media.readyState >= 2;
                })(),
                veilHidden: (() => {
                  const veil = document.getElementById('detailVideoVeil');
                  return veil.getAttribute('aria-hidden') === 'true';
                })(),
                state: window.__mirrorHome.detail.getState()
              };
            }"""
        )
        art = detail["art"]
        check(detail["overflow"][0] <= detail["overflow"][1] + 2 and
              detail["overflow"][2] <= detail["overflow"][3] + 2,
              f"mobile detail overflows: {detail['overflow']}")
        check(len(detail["rules"]) == 2 and
              all(rule[2] > rule[3] for rule in detail["rules"]) and
              abs(detail["rules"][0][1] - art[1]) <= 1.5 and
              abs(detail["rules"][1][5] - art[5]) <= 1.5,
              f"mobile detail rules do not frame the content: {detail['rules']}")
        check(detail["sideCount"] == 0 and detail["oldAwardCount"] == 0,
              f"mobile detail kept the removed featured/award pieces: {detail}")
        check(detail["titleBorder"] != "0px" and
              detail["title"][2] > art[2] * 0.7,
              f"mobile detail title is not boxed across the rail: {detail}")
        check(detail["intro"][5] <= detail["video"][1] + 1 and
              detail["video"][5] <= detail["footer"][1] + 1,
              f"mobile detail did not stack intro/video/footer: {detail}")
        check(detail["panelVisibility"] == "hidden" and
              detail["mediaReady"] is True and detail["veilHidden"] is True,
              f"mobile action tray starts open or the veil is still up: "
              f"{detail}")
        page.locator(".detail-video").click()
        page.wait_for_timeout(280)
        opened = page.evaluate(
            """() => {
              const art = document.getElementById('art').getBoundingClientRect();
              const panel = document.getElementById('detailTools');
              const r = panel.getBoundingClientRect();
              return {
                opacity: getComputedStyle(panel).opacity,
                panel: [r.x, r.y, r.width, r.height, r.right, r.bottom],
                art: [art.x, art.y, art.width, art.height, art.right, art.bottom],
                state: window.__mirrorHome.detail.getState()
              };
            }"""
        )
        panel = opened["panel"]
        check(opened["opacity"] == "1" and
              opened["state"]["actionsPinned"] is True and
              panel[0] >= opened["art"][0] - 1 and
              panel[1] >= opened["art"][1] - 1 and
              panel[4] <= opened["art"][4] + 1 and
              panel[5] <= opened["art"][5] + 1,
              f"mobile action tray leaves the content when opened: {opened}")
        page.locator(".detail-video").click()
        page.wait_for_timeout(300)
        check(page.evaluate(
            "getComputedStyle(document.getElementById('detailTools')).visibility"
        ) == "hidden", "mobile action tray did not close on a second tap")
        page.wait_for_timeout(250)
        page.screenshot(path=str(SHOT_DIR / "probe-deck-mobile-detail.png"), scale="css")
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
        assert_detail_page(page)
        assert_end_page(page)
        assert_pointer_all_slides(page)
        assert_cover_defaults(page)
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
            args=[ENABLE_HTML_IN_CANVAS, ALLOW_AUTOPLAY],
        )
        try:
            run_backend(browser, "webgl", "webgl", width=1440, height=900, dpr=1.5)
            assert_detail_loading_switch(browser)
            assert_reduced(browser)
            assert_mobile(browser)
        finally:
            browser.close()

        browser = p.chromium.launch(
            channel=os.environ.get("MIRROR_CHANNEL", "chrome-beta"),
            headless=False,
            args=[DISABLE_HTML_IN_CANVAS, ALLOW_AUTOPLAY],
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
