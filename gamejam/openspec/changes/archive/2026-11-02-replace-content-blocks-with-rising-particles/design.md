# Design

## Context

`mirror-2610` draws one nested canvas inside the drawable content frame. The canvas is captured live by both the WebGL and SVG mirror backends, so it must remain a normal, non-drawable child with stable CSS geometry and no CSS transforms or filters. The previous implementation used a WebGL2 fragment shader for a pointer-reactive block grid and stopped its rAF loop when the pointer left. That interaction and its idle branch are now removed.

The replacement is a decorative particle column: dark particles rise from the content bottom, with randomized size/depth and a slow shrink/fade lifecycle. It remains page-local and introduces no dependency or mirror API change.

## Goals / Non-Goals

**Goals:**

- Render the solid centre surface and particles in one nested Canvas 2D canvas.
- Make the field self-running: no pointer listeners and no idle pause.
- Randomize particle size, depth, speed, sway, and lifetime while keeping the visual distribution stable.
- Keep the DPR, live-capture, seam, fallback, and tuning contracts.
- Make particle motion and continuous scheduling testable from Playwright.

**Non-Goals:**

- No pointer interaction, block grid, depth band, gradient, or ring.
- No WebGL/three.js dependency for the content field.
- No new tuning controls beyond particle colour and centre colour; feather remains fixed at 72.
- No change to `mirror.js`, the mirror backends, or the build pipeline.

## Decisions

### Canvas 2D particle renderer

Use one `Canvas 2D` context on the existing nested canvas. Each frame fills the full canvas with the centre colour and draws the particles. The context is created with `alpha: false` so the surface is opaque and the mirror captures a stable background.

Alternatives considered:

- **Keep the WebGL2 shader and simulate particles in GLSL:** avoids CPU updates, but makes the particle lifecycle harder to inspect and keeps an unnecessary WebGL dependency after the block grid is gone.
- **DOM particles:** would add many captured elements and layout work; a canvas is simpler and already part of the capture contract.
- **CSS animation:** cannot randomize per-particle size, depth, speed, and lifetime cleanly.

### Fixed pool with continuous recycling

Maintain a fixed pool sized by content area (`area / 7000`, clamped to 24–120). Each particle has independent randomized size (`1.2–4.2px`), depth/opacity (`0.35–0.90`), speed (`16–38px/s`), horizontal sway, and lifetime. The pool is prewarmed across the full lifetime so the first frame is populated instead of starting with an empty column. A particle that reaches the end of its life is reset just below the content bottom; its alpha is already near zero, so the recycle is invisible.

Each particle's vertical position is derived from its age and total rise:

```text
progress = age / life
y = contentHeight + 24 - progress * rise
rise = (contentHeight + 120) * (0.78..1.03)
life = rise / speed
```

The particle also sways horizontally with a low-frequency sine. This keeps motion deterministic per particle and avoids accumulating drift.

Alternatives considered:

- **Spawn-and-destroy with a free list:** equivalent, but a fixed pool makes count, prewarm, and tests simpler.
- **Constant spawn rate:** the count would fluctuate and the visual density would depend on frame timing.

### Size and depth fade

The drawn radius shrinks continuously with progress (`radius = size * (1 - 0.55 * progress)`). Opacity fades in quickly, holds through the middle of life, and fades out after 58% progress. Size and depth are independent random values, so the field has both small dark specks and larger faint motes.

Each particle is drawn as a soft radial-gradient sprite (prebuilt per particle colour) plus a small solid core. The sprite provides the soft edge; the core keeps the particles from reading as uniform blur.

Alternatives considered:

- **Solid circles only:** crisp but visually flat.
- **Per-particle radial gradients every frame:** more allocations and draw cost.
- **`ctx.filter = blur(...)`:** expensive and unnecessary for a nested, mirrored canvas.

### Continuous scheduling

The rAF loop runs whenever the document is visible, regardless of pointer position. There is no pointer state, no presence fade, and no idle timer. Visibility changes stop the loop while hidden and restart it on return; reduced motion renders one static frame and does not schedule.

This is intentionally less efficient than the previous idle-pause design. The field is the page's main motion, and a fixed particle pool plus a DPR-capped canvas keeps the per-frame cost bounded.

### Tuning and fallback

`center` remains the solid surface, mirror root, and seam-guard colour. `particle` is the dark particle colour (default `#242622`). The panel exposes those two colours; `Copy config` reports particle size/speed/density/count and DPR cap. Feather stays fixed at `72`.

If a 2D context cannot be created, the canvas is hidden, `#art` keeps its static centre-colour background, the mirror still mounts, and the loading layer still clears.

### Verification strategy

Use Playwright with Chrome Beta. Read the canvas pixels directly to assert a dominant centre background, dark particle pixels, randomized sample sizes/depths, upward sample motion, and changing frame hashes. Move the mouse inside, hold it still, then move it outside and verify the frame counter continues. Change the particle colour and sample the mirrored band to prove live capture in both backends. Cover DPR 1/1.5/3, reduced motion, and a forced 2D-context failure.

## Risks / Trade-offs

- **Continuous rAF increases paint work** → Fixed pool, DPR cap 2, and a single opaque fill per frame keep the cost bounded. The SVG backend still re-rasterizes while the field animates; this is now an accepted trade-off for a continuously rising field.
- **Particles can look like noise** → Low density, dark but low-alpha colours, varied sizes, and slow motion keep the field atmospheric rather than busy.
- **Particle recycle pop** → Fade-out reaches near zero before the particle resets below the bottom, and new particles fade in over the first 6% of life.
- **Colour tuning changes the sprite** → The sprite is rebuilt only on palette change, not every frame.
- **2D context unavailable** → Hide the canvas and keep the static centre surface; the mirror contract is unaffected.
