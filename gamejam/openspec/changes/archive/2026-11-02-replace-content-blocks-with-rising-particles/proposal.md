# Proposal

## Why

The content field is currently a pointer-reactive block grid that pauses when the pointer stops. The page now needs a quieter, self-running surface: dark particles that rise from the bottom of the content, vary in size and depth, and shrink/fade over their lifetime. Removing the pointer interaction also removes the idle-pause branch and its rAF lifecycle complexity.

## What Changes

- Replace the WebGL2 block shader and all pointer listeners in `content-field.js` with a Canvas 2D particle system.
- Spawn a fixed-size particle pool at and below the content bottom; each particle rises slowly, sways slightly, shrinks, and fades over its lifetime, then recycles at the bottom.
- Randomize particle size, opacity/depth, speed, sway, and lifetime with a seeded PRNG; prewarm the pool across the full life span so the field is populated on the first frame.
- Fill the canvas with the solid `center` colour each frame and draw dark particles with a soft halo plus a small solid core.
- Keep the loop running continuously while the page is visible. Mouse stillness or leaving the content SHALL NOT pause the field.
- Keep `prefers-reduced-motion` support by rendering a static field without starting the rAF loop.
- Rename the panel's `Faint` block-colour control to `Particle`, defaulting to the dark particle colour `#242622`; centre colour and fixed feather `72` behaviour stay.
- Update `Copy config` to report particle size/speed/density/count instead of block cell/radius/threshold settings.
- Replace the block-field probe with particle assertions: dark pixels, randomized samples, upward motion, continuous frames, live mirror capture, tuning/reset, DPR, reduced motion, and 2D fallback.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `gamejam`: Replace the pointer block field and faint outside grid with a continuously rising Canvas 2D particle field; update the content canvas, fallback, and panel requirements.

## Impact

- `gamejam/mirror-2610/content-field.js`: replaced with a Canvas 2D particle renderer.
- `gamejam/mirror-2610/index.html`: canvas comments, particle palette wiring, panel control, config snapshot.
- `gamejam/tools/probe_content_field.py`: rewritten particle probe.
- `gamejam/openspec/specs/gamejam/spec.md`: updated after the change is applied.
- `README.md`: content-field and tuning documentation.
- `gamejam/build.py` and the build output are unchanged: `content-field.js` remains a required runtime file.
