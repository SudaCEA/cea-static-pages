# Tasks

## 1. Reusable parallax module

- [x] 1.1 Add `js/effects/parallax.js` with `createParallax(root, options)`, `data-parallax` discovery, depth normalization, and `PARALLAX_DEFAULTS`.
- [x] 1.2 Normalize pointer position against the root rectangle, clamp to `[-1, 1]`, apply depth-scaled transforms in the opposite direction, and smooth movement.
- [x] 1.3 Stop the rAF loop when the target is reached; reset on window blur/document leave; expose `setPointer`, `reset`, `refresh`, `getState`, and `destroy`.
- [x] 1.4 Render a static centred state and skip scheduling with `prefers-reduced-motion: reduce`; clean up listeners and transforms on destroy.

## 2. Content containers and visual language

- [x] 2.1 Add a transparent `aria-hidden` parallax root after the content canvas with four differently sized containers at depths `0.18`, `0.62`, `1.05`, and `1.60`.
- [x] 2.2 Style the containers with transparent backgrounds, 1px black borders, square corners, black monospace labels, corner marks, a crosshair, and a segmented meter.
- [x] 2.3 Keep the nested canvas at `z-index: 0` with no transforms; place the parallax overlay above it without intercepting pointer events.
- [x] 2.4 Add container-query sizing and a narrow-viewport layout so portrait content uses a landscape frame and labels do not overflow.

## 3. Page integration

- [x] 3.1 Import and instantiate the module after the mirror/field mount; leave the field and mirror lifecycle unchanged.
- [x] 3.2 Expose the instance through `window.__mirrorHome.parallax` and report `maxShiftPx`, smoothing, and layer depths through `Copy config`.
- [x] 3.3 Add `js/effects/parallax.js` to `gamejam/build.py`'s required runtime list.
- [x] 3.4 Update the existing content-field probe for the decorative DOM overlay while retaining its canvas, particle, seam, DPR, and fallback checks.

## 4. Verification and documentation

- [x] 4.1 Add `tools/probe_parallax.py` covering structure, transparency, black foreground, square corners, distinct sizes/depths, transform ordering, settle-to-idle, and reset.
- [x] 4.2 Verify live DOM transform capture in both WebGL and SVG by sampling the mirrored bands before and after pointer movement.
- [x] 4.3 Verify reduced motion, `Copy config`, no page errors, and a mobile viewport without label overflow.
- [x] 4.4 Update `README.md` for the parallax module, content layers, and new probe; verify the directory tree and test commands.
- [x] 4.5 Run the content-field probe, the parallax probe, `openspec validate --specs --strict`, and `python build.py gamejam --clean --strict`; verify screenshots in both backends.

## Workflow follow-up

- Review the initial parallax composition and depth strength before archiving.
- Sync the delta into `gamejam/openspec/specs/gamejam/spec.md` and archive the change when the review is accepted.
- Commit only if the user explicitly asks for a commit.
