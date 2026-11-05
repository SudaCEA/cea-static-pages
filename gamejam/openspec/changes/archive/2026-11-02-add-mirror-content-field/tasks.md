# Tasks

## 1. Canvas field foundation

- [x] 1.1 Create `mirror-2610/content-field.js` with a WebGL2 factory, fullscreen quad, shader compile/link checks, `setPalette`, `setPointer`, `render`, and `destroy`; verify the module parses and a browser load reports no shader or page errors.
- [x] 1.2 Add the single `content-field` canvas to `#art`, style it as an absolute full-size non-interactive layer, and instantiate the field after the mirror mounts; verify the canvas is not a drawable root, fills the content rectangle, and the loading layer still hides.
- [x] 1.3 Implement CSS-size/DPR tracking with a DPR cap of 2 and update the backing store on resize/DPR changes; verify at 900×600 CSS at DPR 1.5 and 3 that the backing store is 1350×900 and 1800×1200 respectively.
- [x] 1.4 Expose a small field state through `window.__mirrorHome` for tests (canvas size, DPR, grid, rendered flag); verify a Playwright probe can read it and the flat-style assertions in the spec pass.

## 2. Mirror corridor background

- [x] 2.1 Implement the base edge-to-centre gradient, rectangular depth band, perspective-compressed rings, directional shading, aperture line, and low-amplitude grain; verify a rendered frame shows axis-aligned contours restricted to the outer band and a solid centre.
- [x] 2.2 Wire `fade`, `edge`, and `center` to the shader uniforms and the CSS fallback; verify changing each control updates the frame without rebuilding the mirror.
- [x] 2.3 Extend the probe to sample the centre, the content edge, the mirror root, and a cross-boundary pixel line; verify the centre/edge colours and the no-seam scenario pass at DPR 1.5.
- [x] 2.4 Document the corridor background and its fade mapping in `README.md`; verify the documented controls match the panel and `Copy config`.

## 3. Pointer block field

- [x] 3.1 Implement cell-grid UV partitioning, pointer-centred distance and polar noise, control threshold, square size/darkness, and `fwidth` antialiasing; verify the grid and size/darkness gradient in a screenshot.
- [x] 3.2 Add pointer move/leave listeners on `#art` with smoothing, pointer presence fade, and background parallax; verify blocks follow the pointer, fade after leave, and the background remains visible.
- [x] 3.3 Extend the probe to move the pointer inside the content, confirm dark cell-aligned pixels near the cursor, and confirm they fade after the pointer leaves; verify there are no page errors.
- [x] 3.4 Document the pointer field and its fixed settings in `README.md`; verify the values reported by `Copy config` match the shader constants.

## 4. Scheduling, reduced motion, and fallback

- [x] 4.1 Add idle pause/resume, document visibility handling, and render-on-demand for palette/resize changes; verify the field reports not animating after the idle timeout and resumes on pointer movement.
- [x] 4.2 Freeze the time term when `prefers-reduced-motion: reduce` is active and keep pointer movement responsive; verify with emulated reduced motion that the pattern is stable while the pointer is still and updates on movement.
- [x] 4.3 Handle WebGL2 context creation/context-loss failure by hiding the canvas, keeping the static CSS fallback, and allowing the mirror to mount; verify with a WebGL-disabled browser launch that the page reaches SVG mode, hides the loading layer, and raises no page error.
- [x] 4.4 Extend the probe for idle pause, reduced motion, and the fallback path; verify all three pass without changing the mirror's backend selection behaviour.

## 5. Mirror capture and tuning integration

- [x] 5.1 Ensure the field's first frame is rendered before `hideBoot()` removes the loading layer; verify the field canvas has rendered when the page becomes visible.
- [x] 5.2 Wire the existing `fade`/`edge`/`center` inputs, `Reset`, `localStorage`, and `Copy config` to the field; verify reset restores the default palette/band and copy includes the fixed `field` values.
- [x] 5.3 Keep `feather` and the fixed backend options mirror-only; verify the panel still exposes only fade/colors/feather, and feather changes do not alter the field canvas.
- [x] 5.4 Extend the probe to run with and without `CanvasDrawElement`, animate the field, and sample the mirrored band in both WebGL and SVG; verify both live-capture scenarios pass.
- [x] 5.5 Update the tuning section of `README.md` for the field palette/depth behaviour; verify the documented `Copy config` shape matches the implementation.

## 6. Build, documentation, and integration checks

- [x] 6.1 Add `mirror-2610/content-field.js` to `gamejam/build.py`'s required runtime list; verify `python build.py gamejam --clean --strict` succeeds and `dist/gamejam/mirror-2610/content-field.js` exists.
- [x] 6.2 Update the README directory tree and startup steps for the nested canvas and content field; verify the documented files exist and the startup sequence matches the code.
- [x] 6.3 Run the full content-field probe at 1200×900 DPR 1 and 1440×900 DPR 1.5 in both backends; verify canvas geometry, palette, blocks, live capture, idle pause, reduced motion, fallback, and no page errors.
- [x] 6.4 Run `openspec validate --specs --strict` and `python build.py gamejam --clean --strict` from `gamejam/`; verify both pass and the final WebGL/SVG screenshots show no content-edge seam.

## 7. Refinements

- [x] 7.1 Fix feather at `72px` for both backends, remove the feather input, show a read-only value, and include it in `Copy config`; verify both modes report filter feather `72` and the panel has no feather control.
- [x] 7.2 Change the pointer field to 8px cells, remove pointer-position smoothing, replace angular noise with a regular radial sine, map control to size/darkness with a normal distribution, and lower the maximum block depth; verify the probe's pointer/animation checks and a close-up screenshot.
- [x] 7.3 Reduce the rectangular depth band to 0–16%, fade it into the centre, and remove rectangular rings, the aperture line, and the dark inner border; verify centre/edge pixels and a content screenshot.
- [x] 7.4 Update the delta spec, design, README, and probe for the refinements; verify `openspec validate`, the full dual-backend/dual-DPR probe, and `python build.py gamejam --clean --strict`.

## 8. Solid surface and faint outside grid

- [x] 8.1 Remove the depth band entirely, make the content surface the centre colour, and align the mirror root and seam guard with that colour; verify solid centre/edge pixels and no depth/ring/border artifacts.
- [x] 8.2 Draw cells above the distance threshold as very faint grey squares with per-cell, time-varying random scale; verify the probe's faint-outside check and a screenshot.
- [x] 8.3 Update the delta spec, design, proposal, README, and probe for the solid surface/faint grid; verify strict spec validation, the full dual-backend/dual-DPR probe, and the strict build.

## 9. Faint depth noise

- [x] 9.1 Drive outside-threshold square depth from an independent per-cell time noise, in addition to the existing random scale; verify the probe's faint depth range and a screenshot.
- [x] 9.2 Update the delta spec, design, README, and probe for depth noise; verify strict spec validation, the full dual-backend/dual-DPR probe, and the strict build.

## Workflow follow-up

- Review the screenshots and tuning behaviour before archiving.
- Sync the delta into `gamejam/openspec/specs/gamejam/spec.md` and archive the change when the review is accepted.
- Commit only if the user explicitly asks for a commit.
