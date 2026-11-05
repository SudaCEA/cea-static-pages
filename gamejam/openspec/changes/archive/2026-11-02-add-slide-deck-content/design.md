# Design

## Context

The page is a mirror study built on `mirror.js`. The content is a drawable subtree captured by the WebGL HTML-in-Canvas path (Chrome Beta) or the SVG fallback. Previous iterations used transparent parallax containers as placeholders; those are now replaced by real editorial content.

The user requires the content to remain inside `#art` so it participates in the mirror. The paging controls, by contrast, must remain page chrome and must not be mirrored. The top page counter is removed; only two arrow buttons remain.

## Goals / Non-Goals

**Goals:**

- Present four real slides with a clear cover, about, mechanism, and info sequence.
- Keep the deck inside the mirrored content subtree.
- Provide wheel, keyboard, and compact corner-button navigation.
- Fade the outgoing slide out and the incoming slide in.
- Prevent rapid input from skipping slides.
- Keep the tuner available without covering the top buttons or dominating the page.

**Non-Goals:**

- No routing, URL hashes, autoplay, or slide thumbnails.
- No new content-management system; slides stay as static HTML.
- No further parallax page effect. The shared module remains available but unused.
- No mirror.js or canvas geometry changes.

## Decisions

### Deck inside `#art`

The four `<section class="slide">` elements live in `#art` after the particle canvas. `#art` remains the mirror's content, so the deck text is captured and reflected. The deck uses `position:absolute; inset:0; z-index:1` over the particle canvas. All copy, rules, and labels are transparent-background DOM.

The alternative—an overlay outside the captured subtree—was rejected by the user because it removed the content from the mirror.

### Compact corner controls outside the mirror

The paging buttons are a fixed `<nav>` outside `#art`, so they are not captured. Each is a 40×34px square with a 1px black border and a single arrow glyph; the mobile size is 36×32px. The previous labels and top-center `01 / 04` indicator are removed.

### Four static slides

The deck contains four static sections:

- `00 / Mirror study` — title and short premise.
- `01 / About` — a two-column introduction with a side list.
- `02 / Mechanism` — a three-step explanation.
- `03 / Info` — closing copy and a small information grid.

The layout uses `cqw`/`cqh` from the mirror content container. At narrow widths, the split becomes one column, steps stack, and the info grid becomes a single column.

### Per-element fade sequencing

`js/effects/fade.js` provides `fadeIn(root)`, `fadeOut(root)`, and `resetFade(root)`. It discovers `[data-fade]` elements and reads:

```html
data-fade
data-fade-in-delay="120"   <!-- ms -->
data-fade-out-delay="30"   <!-- ms -->
```

Each element is animated independently with the Web Animations API over a shared `220ms` base duration. Enter animations use `fill: backwards` so a delayed element stays transparent during its delay; exit animations use `fill: forwards` so it stays hidden until the next enter. The module resolves only after every element's delay + duration has completed.

`goToSlide(index)`:

1. Locks navigation.
2. Fades out every marked element on the outgoing slide using its own exit delay.
3. Hides the outgoing slide, shows the incoming slide, and fades in its marked elements using their own enter delays.
4. Unlocks after the entire entry group completes.

The current choreography is forward on enter, with staggered side rows, steps, and info rows; exit delays are shorter so content leaves before the next page arrives. `prefers-reduced-motion` cancels the animations and switches instantly.

Alternative considered: CSS transition-delay per element. It is simpler, but cancelling and reversing mid-transition, waiting for the longest delay, and supporting separate in/out delays is more reliable with Web Animations.

### Wheel and keyboard input

Wheel deltas accumulate until a 36px threshold, then advance or go back. An 850ms wheel lock absorbs trackpad momentum. Wheel events over the tuner are ignored so the panel can scroll. Keyboard supports ArrowLeft/ArrowRight, ArrowUp/ArrowDown, PageUp/PageDown, Home, and End. Buttons and inputs are excluded from key handling.

### Tuner placement

The tuning panel moves to the bottom-right and starts collapsed. The collapsed header is below the content rectangle at desktop sizes, so it does not overlap the deck or the top-right paging control. Opening it reveals the existing controls and can overlay the page while tuning.

### Verification

The deck probe checks:

- compact top-corner buttons, no page-number node;
- four non-empty slides inside `#art`, with the nav outside;
- one active/visible slide and correct aria-hidden state;
- button, wheel, keyboard, boundary, and locked-transition behavior;
- distinct in/out delays on every slide;
- staggered mid-transition opacity and completed active/outgoing opacity;
- transition lock until the slowest fade finishes;
- reduced-motion snap;
- mobile layout without overflow;
- `Copy config` deck values and the absence of parallax config.

The existing content-field probe is updated to accept deck text in `#art` while retaining canvas, particle, seam, DPR, reduced-motion, and fallback checks.

## Risks / Trade-offs

- **Content is reflected and can be visually busy** → This is intentional; the user explicitly required the content to participate in the mirror. Keep generous margins and 1px rules.
- **Chrome Beta HTML-in-Canvas paint-record capture can lag for compositor-only slide opacity changes in the side bands** → The center content and navigation are correct. A future mirror update can force a fresh content paint record after transitions if the side-band lag becomes a blocker.
- **Wheel momentum can skip slides** → Threshold plus 850ms lock; the deck also remains locked until the longest fade completes.
- **A long stagger delays navigation** → Keep base duration at 220ms and cap enter delays around 290ms; the total is roughly 800ms, and the next input is ignored until it finishes.
- **Tuner covers content when open** → It starts collapsed and sits in the bottom margin; it is a development tool, not page content.
- **Narrow slides can overflow** → Mobile breakpoints stack the split, steps, and info grid; the probe checks scroll/client dimensions.

## Migration

- Delete the parallax container markup and page-level `createParallax` wiring.
- Keep `js/effects/parallax.js` and its reusable-module requirement, but do not mount it in `mirror-2610`.
- Remove `probe_parallax.py`; its page-level assumptions no longer hold.
- Move the deck into `#art`; commit the text content as static HTML.
