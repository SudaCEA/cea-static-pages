# Design

## Context

The `mirror-2610` content frame is a drawable HTML subtree. `mirror.js` moves `#art` into `.mirror-content`, captures it through the WebGL HTMLTexture path, and also renders the same subtree through the SVG backdrop-filter path. A nested canvas therefore has to be a normal, non-drawable child with stable CSS geometry; it is captured live by both backends. The existing lab already proves this for a simple pointer-following canvas, and the preflight warns about the Chrome <157 nested-canvas device-pixel issue.

The current content is only a two-layer CSS gradient. The change adds a page-local procedural field without changing the mirror layout, backend selection, or the `mirror.js` contract. See `proposal.md` for motivation and the delta spec for observable requirements.

## Goals / Non-Goals

**Goals:**

- Render the background and pointer effect in one nested WebGL2 canvas with one draw call per frame.
- Keep the centre clean, the content border borderless, and the surface plus mirror root fill on the same centre colour.
- Preserve the existing edge/center tuning path (faint blocks and surface), the fixed backend settings, and both mirror backends.
- Keep idle cost near zero and provide a static fallback when WebGL2 is unavailable.
- Make the canvas geometry, DPR contract, pointer field, and seam testable from Playwright.

**Non-Goals:**

- No new tuning controls, text, DOM block elements, or public content API.
- No change to `mirror.js`, the three bundle, the SVG filter layout, or the backend preflight.
- No 3D scene graph, textures, or additional dependencies; the field is a fullscreen fragment shader.
- No attempt to work around the Chrome <157 nested-canvas DPR bug inside the page.
- No change to the diagnostic lab's own mouse effect.

## Decisions

### One nested WebGL2 canvas, raw WebGL2

Use a single `<canvas>` appended to `#art`, and draw both the background and the blocks in the same fragment shader. Raw WebGL2 is enough for a fullscreen quad and avoids creating a second three.js renderer.

Alternatives considered:

- **Two canvases (background + overlay):** isolates repaint cost, but adds a second nested canvas and a second DPR/capture contract, and doubles the chance of an offset between layers.
- **CSS/SVG surface plus a canvas only for the pointer:** the canvas is still needed for the per-cell field, and a separate surface layer would add another capture surface.
- **three.js fullscreen pass:** already loaded for the mirror, but brings renderer, scene, and target overhead for a single shader.

### Solid content surface, no depth band

The content background is a single solid centre colour. There is no edge gradient, depth band, ring, aperture line, border, or grain. The mirror root and seam guard use the same centre colour, so the surface and mirror fill meet without a deliberate edge treatment.

This keeps the content visually quiet and leaves the pointer field as the only content effect. The alternative, keeping a shallow depth band, was removed because it competed with the faint outside grid and still produced a visible edge.

Alternatives considered:

- **A perspective 3D box/grid:** stronger literal depth, but more complex corner handling and likely busier than the page's minimal surface.
- **A pre-rendered background image:** would need external assets, DPR variants, and would not respond to palette tuning.

### Per-cell pointer field in the fragment shader

The pointer effect evaluates one control value per cell, not per pixel. The grid uses a fixed cell size of 8 CSS px and tracks the pointer without positional smoothing. For each cell centre:

```text
d       = length((cellCenter - pointer) * aspectCorrection)
wave    = 0.5 + 0.5 * sin(d * 80 - t * 2.4)
control = d / radius + (1 - wave) * 0.20
z       = clamp(control / threshold, 0, 1)
gaussian = exp(-0.5 * (z / 0.38)^2)
```

The wave is a single regular radial trigonometric animation; there is no angular or random noise. `z < 1` defines the threshold. A normal-distribution falloff maps `gaussian` to square size, colour darkness, and depth; the maximum depth is deliberately lighter than the previous near-black blocks. The square is evaluated at the cell centre, so the whole square shares one value and block edges stay crisp.

Cells above the threshold remain visible as very faint grey squares. Each cell hashes an independent phase and speed for scale and another pair for depth, then uses `sin(t * speed + phase)` to grow/shrink and to lighten/darken the square over time. The faint layer uses the edge colour at a low blend weight, so it reads as texture rather than a second effect.

Alternatives considered:

- **Angular noise around the pointer:** produces irregular lobes and a less predictable pattern; removed in favour of the regular radial wave.
- **Per-pixel noise with a block mask:** produces noisy, unstable square edges and a different value per fragment.
- **Instanced quads:** more geometry and CPU updates for no visual gain at this cell count.
- **Smooth Gaussian blob (the current lab effect):** does not produce the requested discrete block field.

### Canvas style and DPR contract

The canvas is a normal child of `#art` with `position:absolute; inset:0; width:100%; height:100%; display:block; pointer-events:none`. It is not a drawable root and has no `layoutsubtree`. It must not use CSS transforms, zoom, filters, opacity, or blend modes; all visual effects live in the shader.

The backing store is `round(cssSize * min(devicePixelRatio, 2))`, matching the mirror's `dprCap: 2`. The canvas is created with `alpha: true`, `premultipliedAlpha: true`, and `preserveDrawingBuffer: true`; the shader writes an opaque result. The field canvas updates live through both backends without an outer `requestPaint()` loop; the existing lab verified this on the available Chrome build.

Alternatives considered:

- **DPR² oversampling for older Chrome:** explicitly rejected; it conflicts with the known bug fix and mirror.js's device-pixel contract.
- **`requestPaint()` every frame:** would duplicate the mirror's paint scheduling and risks racing its HTMLTexture upload.

### Seam guard for the 0.5x composite

The fixed WebGL `renderScale: 0.5` path composites a 1x body overlay over a 0.5x mirror target. At the content boundary this can leave a one-pixel light line where the two targets meet. The page paints a two-pixel centre-coloured overlay just outside `#art`; it is outside the mirror frame and outside hit testing, so it is not captured and does not change the fixed render scale. The alternative, changing `renderScale`, is rejected because it is a fixed requirement.

### Render scheduling

The background is static. The animation loop runs only while the pointer is active or fading, and stops after the pointer leaves and the presence fade completes; tuning and resize changes draw one frame immediately. With `prefers-reduced-motion: reduce`, the time component is frozen and only pointer movement triggers a redraw. This avoids continuously re-rasterising the SVG backdrop filter when the page is idle.

### Tuning and fallback integration

`edge` and `center` are pushed as uniforms. `center` is the solid surface, mirror root, and seam guard colour; `edge` is the faint outside-block colour. There is no fade control. Feather is fixed at 72px for both backends and is shown as a read-only value, not a control. `Copy config` adds a fixed `field` section (cell size, radius, threshold) without adding controls.

`#art` keeps a static CSS fallback background. If WebGL2 context creation fails, the canvas is removed/hidden, the fallback remains, and the mirror still mounts. The mirror root background is set from the selected centre colour in all cases, preserving the seam contract.

### Verification strategy

Use Playwright with `--enable-features=CanvasDrawElement` for the WebGL path and without it for the SVG fallback. The probe reads the field canvas dimensions/style, samples centre/edge pixels, moves the pointer to verify block presence, waits for animation to confirm the mirrored band changes, and checks the idle pause and reduced-motion paths. Screenshots at DPR 1 and 1.5 cover the visual seam and block sizing.

## Risks / Trade-offs

- **Chrome <157 nested-canvas DPR bug** → Keep the existing preflight warning and default-to-SVG choice; do not add a DPR² workaround. Verify DPR 1.5 on the SVG path, and treat WebGL DPR > 1 as the documented compatibility risk.
- **SVG backdrop-filter cost while the canvas animates** → Pause the loop after pointer leave, keep the field canvas small (content size, DPR capped at 2), and avoid repainting on tuning changes when values are unchanged.
- **Faint grid becoming visible noise** → Keep the outside blend weight low and the squares small; the edge colour is only a tint.
- **Block popping at the threshold** → Use a normal-distribution falloff and evaluate one value per cell; the Gaussian is near zero at the threshold.
- **Seam from the solid surface** → The surface, mirror root, and seam guard all use the centre colour; sample across the boundary in the probe.
- **Faint grid competing with the cursor** → The outside layer uses much lower opacity and smaller random scales than the inside Gaussian field.
- **WebGL2 context loss** → Hide the canvas, keep the CSS fallback, and do not throw; the mirror itself has its own fallback path.
