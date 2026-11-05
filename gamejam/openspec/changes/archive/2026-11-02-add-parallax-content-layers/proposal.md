# Proposal

## Why

The content surface currently has rising particles but no spatial structure: every element sits on one plane. A small set of transparent, black-on-white containers moving at different depths would give the content a readable foreground without changing the mirror's backend, layout, or capture path. The effect is reusable beyond this page, so it belongs in a shared effects module rather than inline page code.

## What Changes

- Add `js/effects/parallax.js`, a reusable pointer-driven layer module that reads `data-parallax="<depth>"` and translates layers in CSS pixels.
- Add four transparent containers to `mirror-2610` content: a large field frame, a specimen panel, an index card, and a small node marker. They use different sizes and depths, 1px black borders, square corners, monospace labels, and black foreground on a transparent background.
- Drive the layers from the pointer position relative to the content rectangle: deeper layers move farther, movement is smoothed, and the rAF loop stops when the position settles.
- Reset to the centre when the window loses focus or the pointer leaves the document. Respect `prefers-reduced-motion` by leaving the layers static.
- Keep the existing Canvas 2D particle field and mirror capture contracts unchanged. The canvas remains a fixed-geometry child; only the parallax layers receive CSS transforms.
- Add the module to the build's required runtime files and add a Playwright probe covering structure, style, depth ordering, settling, both mirror backends, reduced motion, and `Copy config`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `gamejam`: Add parallax content-layer and module requirements; update the procedural content field to allow the decorative DOM overlay alongside the canvas.

## Impact

- `gamejam/js/effects/parallax.js`: new shared parallax module.
- `gamejam/mirror-2610/index.html`: content markup, layer styles, module wiring, `Copy config`.
- `gamejam/build.py`: require the new runtime module.
- `gamejam/tools/probe_parallax.py`: new probe; `probe_content_field.py` updated for the DOM overlay.
- `README.md`: parallax layer and test documentation.
- No mirror backend, WebGL/SVG filter, particle, build-output, or tuning-control behaviour changes.
