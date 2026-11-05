# Proposal

## Why

The four parallax containers were placeholders and no longer represent the page. The mirror study now needs actual copy organized into a small, deliberate sequence. A slide-deck structure keeps the content readable while preserving the mirror as the page's visual system, and gives the page a real beginning, middle, and end.

## What Changes

- Remove the placeholder parallax containers and the page-level parallax mount. Keep `js/effects/parallax.js` as a reusable module, but it no longer participates in this page.
- Move the slide deck inside `#art` so its text, rules, and layout are captured by the mirror and reflected in the surrounding bands.
- Add four real slides: cover, about, mechanism, and info. Each has an eyebrow, title, body copy, and footer line.
- Add compact arrow-only paging buttons at the top-left and top-right corners, outside the mirrored content. Remove the top page-number indicator.
- Add wheel, arrow-key, PageUp/PageDown, Home/End, and button navigation with a shared transition lock.
- Add a reusable `js/effects/fade.js` module that animates elements individually with `data-fade-in-delay` / `data-fade-out-delay` milliseconds.
- Apply different enter and exit delays to the existing slide elements: kickers, titles, body copy, side rows, steps, info rows, and footers.
- Wait for the complete staggered exit and entry before unlocking the deck. `prefers-reduced-motion` switches instantly.
- Move the tuning panel to the bottom-right and start it collapsed so it does not conflict with the top paging controls. It opens on demand.
- Add a deck probe and update the content-field probe for the deck inside the mirrored content.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `gamejam`: Replace the placeholder parallax content with an in-mirror slide deck; add deck content, navigation, fade, and collapsed-tuner requirements. Remove the page-level parallax content requirement and keep the shared parallax module as a project library.

## Impact

- `gamejam/js/effects/fade.js`: new reusable per-element fade sequencer.
- `gamejam/mirror-2610/index.html`: slide markup/styles, per-element delays, deck controller, compact nav, tuner placement/collapsed state.
- `gamejam/tools/probe_deck.py`: new probe; `probe_content_field.py` adjusted for deck text inside content.
- `gamejam/build.py`: `fade.js` becomes a required runtime file; the parallax module is no longer required by this page.
- `README.md`: slide deck, controls, transitions, tuner placement, and test commands.
- No mirror backend, canvas, build pipeline, or dependency changes.
