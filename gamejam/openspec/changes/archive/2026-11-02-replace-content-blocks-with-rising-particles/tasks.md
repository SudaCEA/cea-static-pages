# Tasks

## 1. Particle renderer

- [x] 1.1 Replace the WebGL2 shader in `mirror-2610/content-field.js` with a Canvas 2D context, opaque centre-colour fill, DPR-capped backing store, and resize handling.
- [x] 1.2 Implement a fixed-size, area-derived particle pool with independent random size, opacity, speed, sway, rise, and lifetime; prewarm particles across the full life span.
- [x] 1.3 Draw each particle with a soft prebuilt radial sprite and a small solid core; shrink the radius and fade opacity with age; recycle particles below the content bottom.
- [x] 1.4 Remove pointer listeners, pointer state, presence fading, and idle scheduling; keep the rAF loop running while the document is visible.
- [x] 1.5 Render one static field frame and skip the loop when `prefers-reduced-motion: reduce` is active.

## 2. Page integration

- [x] 2.1 Rename the panel's `Faint` control to `Particle`, default it to `#242622`, and wire `setPalette({ center, particle })` to the field.
- [x] 2.2 Update `Copy config` to report particle size range, speed range, density, live count, and DPR cap; remove block field values.
- [x] 2.3 Keep the solid centre surface, mirror root, seam guard, fixed feather `72`, localStorage reset, and boot readiness behaviour.
- [x] 2.4 Handle 2D context creation failure by hiding the canvas, keeping the CSS fallback, and allowing the mirror to mount.

## 3. Verification and documentation

- [x] 3.1 Rewrite `tools/probe_content_field.py` to assert a dominant centre background, dark particle pixels, randomized samples, upward motion, continuous frames, and no pointer state.
- [x] 3.2 Verify the field keeps animating with the pointer held still inside the content and after the pointer leaves.
- [x] 3.3 Verify live capture in WebGL and SVG by changing the particle colour and sampling the mirrored band.
- [x] 3.4 Verify DPR 1/1.5/3 backing stores, reduced motion, forced 2D fallback, palette reset/persistence, and fixed feather.
- [x] 3.5 Update `README.md` for the particle field, continuous scheduling, tuning controls, and verification environment.
- [x] 3.6 Run `openspec validate --specs --strict`, the full dual-backend/DPR probe, and `python build.py gamejam --clean --strict`.

## Workflow follow-up

- Review the particle density and motion before archiving.
- Sync the delta into `gamejam/openspec/specs/gamejam/spec.md` and archive the change when the review is accepted.
- Commit only if the user explicitly asks for a commit.
