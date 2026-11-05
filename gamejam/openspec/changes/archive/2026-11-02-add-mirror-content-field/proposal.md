# Proposal

## Why

The `mirror-2610` content area is currently an empty CSS gradient. It gives the page a clean white body, but the border band has no depth and the content does not react to the pointer. The mirror effect already reflects the content edge, so adding a procedural edge space and a pointer-driven block field would make the mirror itself feel deeper without adding another visual system or dependency.

## What Changes

- Replace the empty CSS-gradient content with one nested WebGL2 canvas that draws both the background and the pointer effect.
- Use a solid centre-colour content surface with no depth band, edge gradient, rings, aperture line, or CSS border.
- Add a pointer-reactive block field on an 8px cell grid: each cell combines its distance from the pointer with a regular radial trigonometric animation (no angular noise), and a normal-distribution falloff maps the control value to square size and lightness inside the threshold. Cells outside the threshold stay visible as very faint grey squares with a per-cell, time-varying random scale. Pointer movement is unsmoothed.
- Keep the field decorative and non-interactive: no text, no DOM blocks, no new content API.
- Add the nested-canvas integration contract: the field canvas is not a drawable root, uses a device-pixel backing store capped at DPR 2, does not use CSS transforms/filters, and updates live in both the WebGL and SVG mirror backends.
- Add lifecycle handling: resize/DPR updates, pointer smoothing and leave fade, idle animation pause, reduced-motion behaviour, and a static CSS fallback if WebGL2 is unavailable.
- Wire the existing `edge`/`center` colors to the faint outside blocks and the solid surface, and include the fixed field settings in `Copy config`. No fade, blur, scale, map, or feather controls are added; feather stays fixed at `72`.
- Add the field module to the build's required runtime files and add a Playwright probe covering both mirror backends, DPR sizing, surface, pointer blocks, faint outside blocks, boundary seam, and idle/reduced-motion states.
- Replace the "Empty gradient content area" requirement in the `gamejam` spec with solid-surface and pointer-field requirements.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `gamejam`: Replace the empty-gradient content requirement with a solid content surface and a pointer block field. Add requirements for the faint outside grid, the nested-canvas capture contract, and the surface-driven tuning behaviour; update the fixed-render requirements.

## Impact

- `gamejam/mirror-2610/index.html`: content markup, CSS, field lifecycle, tuning wiring, boot readiness.
- `gamejam/mirror-2610/content-field.js`: new page-local WebGL2 module.
- `gamejam/build.py`: require the new runtime file.
- `gamejam/openspec/specs/gamejam/spec.md`: replaced and added requirements after the change is applied.
- `gamejam/tools/`: new content-field probe.
- `README.md`: content-area and tuning documentation.
- Both mirror backends and both DPR paths remain supported. No public API, third-party dependency, or build pipeline change is introduced beyond the new page-local module.
