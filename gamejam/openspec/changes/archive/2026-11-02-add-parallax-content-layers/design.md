# Design

## Context

`mirror-2610` already captures a nested Canvas 2D particle field inside the drawable content frame. The content is a normal DOM subtree, so additional transparent DOM layers can be captured by both the WebGL and SVG mirror backends. The loading and preflight UI establishes the page's visual language: white surface, black foreground, 1px square borders, monospace uppercase labels, and no rounded corners.

The new effect must remain decorative and must not disturb the canvas geometry, mirror capture, particle field, or tuning panel. The parallax module should be reusable by other pages rather than coupled to `mirror-2610`.

## Goals / Non-Goals

**Goals:**

- Provide a small reusable `createParallax(root, options)` module driven by `data-parallax` depths.
- Compose several transparent containers with distinct sizes and depths inside the content.
- Move only with CSS transforms so layout and the nested-canvas contract stay unchanged.
- Smooth pointer movement and stop the rAF loop once the layers settle.
- Preserve reduced-motion behaviour and keep the decorative DOM hidden from assistive technology.
- Verify live capture in both mirror backends.

**Non-Goals:**

- No new tuning controls. Particle and centre colours remain the only adjustable values.
- No change to `mirror.js`, the three bundle, filter/layout settings, or the particle field.
- No pointer hover interactions, links, or interactive content inside the layers.
- No 3D camera, perspective, or scroll-driven parallax; motion is strictly pointer-driven.

## Decisions

### Transform-only, depth-declared layers

Each container is a normal absolutely positioned element inside a transparent `.parallax` root. The root scans `[data-parallax]` children and reads a numeric depth from `0` to `4`. On every frame it writes:

```text
offset = -normalizedPointer * depth * maxShiftPx
transform = translate3d(offsetX, offsetY, 0)
```

The layout box is never changed, so the canvas, mirror content frame, and seam geometry stay stable. `maxShiftPx` defaults to `20`; the four layers use depths `0.18`, `0.62`, `1.05`, and `1.60`, producing approximately 3.6px to 32px of travel at the content edge.

Alternatives considered:

- **Animate `left`/`top`:** changes layout and forces reflow every frame; rejected in favour of transforms.
- **CSS custom properties with a single transform rule:** workable, but the module would still need to write custom properties each frame and adds indirection without a gain.
- **Canvas-rendered containers:** loses text selection/accessibility structure and duplicates the particle canvas concern.

### Pointer space is the content rectangle

The module normalizes the pointer against `root.getBoundingClientRect()` on every pointer event and clamps to `[-1, 1]`. Pointer movement outside the content still drives the layers at the nearest edge, which keeps the effect continuous when the cursor crosses the mirror bands or the tuner. Pointer leave on the document resets to the centre.

Alternative considered:

- **Normalize against the viewport:** would make the content layers react to movement far away and lose the relationship between cursor and content.

### Settle-to-idle scheduling

The module starts a rAF loop on pointer movement, lerps the current position toward the target with an exponential smoothing factor (`8/s`), and stops when both axes are within `0.0005`. This avoids a permanently running animation loop while keeping the motion soft. A new pointer move restarts the loop. Reduced motion skips the loop and keeps all layers at zero.

Alternative considered:

- **CSS transition on each transform:** simpler, but pointer updates during a transition make the timing unpredictable; an explicit loop also makes settling and testing deterministic.

### Transparent black-on-white containers

The content remains the solid centre colour. The four containers draw only borders, labels, corner marks, a crosshair, and a small meter; their backgrounds stay `transparent`. This matches the loading layer's square, monochrome style while letting the particles show through.

Layout uses `cqw`/`cqh` units because `.mirror-content` already establishes a size container. A narrow-viewport media query turns the large frame landscape and enlarges the cards' relative footprint so labels do not overflow on phones.

Layer composition:

- `.p-frame` — 56cqw × 72cqh, depth `0.18`, four edge labels, corner marks, centre crosshair.
- `.p-panel` — 25cqw × 20cqh, depth `0.62`, specimen header, segmented meter, depth footer.
- `.p-index` — 15cqw × 21cqh, depth `1.05`, index labels and a large `03`.
- `.p-node` — 8cqw × 11cqh, depth `1.60`, a small `04` and solid node dot.

The root and all decorative text are `aria-hidden`; the content remains a visual study, not a navigation surface.

### Capture and testing

CSS transforms on ordinary DOM children are part of the content paint, so both mirror backends capture them live. The probe moves the pointer between opposite content corners and samples the mirrored band before and after. It also verifies computed transparency, black borders/text, square corners, depth ordering, transform-to-state agreement, settle-to-idle, reduced motion, and `Copy config`.

## Risks / Trade-offs

- **Mirrored duplicates become visually busy** → Keep labels small, borders 1px, backgrounds transparent, and depths subtle. The mirror duplication is inherent to the page's concept.
- **HTML-in-Canvas capture of transformed DOM** → Verify mirrored-band changes in WebGL and SVG; if a backend misses transforms, fall back to transform updates on a single content layer rather than changing the mirror.
- **Pointer outside the content keeps layers at an edge** → Reset on document pointer leave; clamping keeps the effect predictable.
- **Very narrow content squeezes labels** → A media query changes the frame orientation and scales up card footprints; probes check that layers do not overflow their content boxes.
- **Continuous particle animation masks a stalled parallax loop** → Expose parallax frame/current state through `window.__mirrorHome.parallax` and assert the parallax frame counter stops independently.
