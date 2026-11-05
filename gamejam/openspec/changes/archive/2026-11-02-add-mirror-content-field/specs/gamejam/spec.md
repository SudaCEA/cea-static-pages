# Spec Delta

## ADDED Requirements

### Requirement: Procedural content field

The content area SHALL contain exactly one decorative WebGL2 canvas sized to fill the content rectangle. The canvas SHALL be `aria-hidden` and SHALL NOT introduce user-facing text, DOM blocks, or a CSS border. The page SHALL render the first field frame before removing the loading layer.

#### Scenario: Single decorative canvas

- **WHEN** the content rectangle is inspected
- **THEN** it contains exactly one canvas child
- **AND** the canvas is `aria-hidden`
- **AND** the content has no text content or CSS border

#### Scenario: Field is ready before the page is revealed

- **WHEN** the mirror has mounted and the loading layer is about to be removed
- **THEN** the field canvas has a non-zero backing store and has rendered at least one frame

### Requirement: Solid content surface

The content background SHALL be the configured centre colour with no depth band, edge gradient, rectangular rings, aperture line, or CSS border. The mirror root and seam guard SHALL use the same centre colour.

#### Scenario: Solid surface

- **WHEN** the content background is inspected
- **THEN** it is a solid configured centre colour
- **AND** no depth band or edge gradient is drawn
- **AND** no rectangular rings or inner border are drawn

#### Scenario: Seamless centre colour

- **WHEN** pixels are sampled across the content boundary
- **THEN** the content edge and the mirror root use the same configured centre colour
- **AND** no abrupt colour step is visible at the boundary

### Requirement: Pointer block field

The page SHALL render a pointer-reactive block field on a UV cell grid of approximately 8 CSS px. Each cell's control SHALL combine its distance from the pointer with a regular radial trigonometric animation, without angular or random noise. Cells below the threshold SHALL draw squares whose size and darkness follow a normal-distribution falloff. Pointer position SHALL NOT be smoothed, and the field SHALL fade after the pointer leaves.

#### Scenario: Cell-aligned control field

- **WHEN** the pointer moves inside the content
- **THEN** squares appear near the pointer aligned to the 8px cell grid
- **AND** squares closer to the pointer are larger and darker than those near the threshold

#### Scenario: Regular radial animation

- **WHEN** the pointer is held stationary inside the content
- **THEN** the inside block pattern changes as a regular radial trigonometric wave
- **AND** no angular noise is applied

#### Scenario: Unsmoothed pointer

- **WHEN** the pointer jumps to a new position
- **THEN** the block field uses the new pointer position on the next frame
- **AND** no pointer-position easing is applied

#### Scenario: Pointer leave

- **WHEN** the pointer leaves the content
- **THEN** all blocks fade out
- **AND** the solid surface remains visible

#### Scenario: Reduced motion

- **WHEN** `prefers-reduced-motion: reduce` is active
- **THEN** the time-driven wave and random scale are frozen
- **AND** pointer movement still updates the block field

### Requirement: Faint outside blocks

Cells above the distance threshold SHALL draw very faint grey squares with a per-cell, time-varying random scale and depth. Scale and depth SHALL change smoothly over time and SHALL be driven by independent noise.

#### Scenario: Faint outside blocks

- **WHEN** a cell is above the distance threshold
- **THEN** it draws a very faint grey square
- **AND** its scale and depth vary randomly over time

### Requirement: Nested canvas style contract

The content canvas SHALL use a backing store equal to its CSS size multiplied by the device pixel ratio capped at 2. It SHALL NOT be a drawable root and SHALL NOT use CSS transforms, zoom, filters, opacity, or blend modes. Its CSS size SHALL fill the content rectangle without borders or padding.

#### Scenario: Device-pixel backing store

- **WHEN** the content is 900 by 600 CSS pixels at DPR 1.5
- **THEN** the canvas backing store is 1350 by 900
- **AND** the canvas CSS rectangle equals the content rectangle

#### Scenario: DPR cap

- **WHEN** the device pixel ratio is 3
- **THEN** the canvas backing store uses a ratio of 2

#### Scenario: Flat canvas styling

- **WHEN** the canvas computed style is inspected
- **THEN** transform is `none`, filter is `none`, opacity is `1`, and mix-blend-mode is `normal`
- **AND** the canvas has no `drawable` or `layoutsubtree` attribute

### Requirement: Nested canvas live capture

The nested canvas SHALL update live through both the WebGL and SVG mirror backends without an explicit per-frame outer `requestPaint()` call. Animated canvas pixels SHALL appear in the mirrored bands as well as in the centre body.

#### Scenario: Live capture in WebGL

- **WHEN** the content canvas animates while the WebGL backend is active
- **THEN** the mirrored bands change with the canvas content

#### Scenario: Live capture in SVG

- **WHEN** the content canvas animates while the SVG backend is active
- **THEN** the mirrored bands change with the canvas content

### Requirement: Content field fallback

If a WebGL2 context cannot be created, the page SHALL keep a static CSS content background, skip the pointer block field, and continue mounting the mirror. It SHALL NOT leave the loading layer stuck or raise a page error.

#### Scenario: WebGL2 unavailable

- **WHEN** the field canvas cannot create a WebGL2 context
- **THEN** the page mounts the mirror and removes the loading layer
- **AND** the content shows a static fallback background with the configured centre colour
- **AND** no pointer block field is shown

### Requirement: Floating surface panel

The page SHALL provide a floating panel outside the mirror stage so it is not captured by the mirror.

The panel SHALL adjust only faint outside-block colour and centre colour. Feather SHALL be fixed at 72px and SHALL NOT be adjustable. It SHALL NOT expose fade, blur, WebGL scale, SVG map, or feather controls. It SHALL show the backend, DPR, content and canvas sizes, and provide `Copy config`, `Reset`, `localStorage`, and a collapsed state at or below 560px.

#### Scenario: Surface colours change live

- **WHEN** the faint colour or centre colour control changes
- **THEN** the content field and mirror root update without rebuilding the mirror
- **AND** the seam guard follows the centre colour

#### Scenario: Fixed settings are not editable

- **WHEN** the panel is inspected
- **THEN** it contains no fade, blur, WebGL scale, SVG map, or feather controls
- **AND** it shows the fixed feather of `72`
- **AND** `Copy config` reports the fixed backend and content-field values

#### Scenario: Feather is fixed

- **WHEN** either backend is active
- **THEN** its filter feather is `72`
- **AND** no control can change it

#### Scenario: Reset restores defaults

- **WHEN** the reset action is used
- **THEN** the adjustable colours return to defaults
- **AND** the active mirror receives the fixed feather `72` and the fixed backend options
- **AND** the content field receives the default centre and faint colours
- **AND** the saved tuning value is replaced with defaults

#### Scenario: Tuning persists

- **WHEN** a visitor reloads the page after changing panel values
- **THEN** the saved colours are restored
- **AND** the mirror is created with the fixed feather `72`
- **AND** the content field starts with those values

## MODIFIED Requirements

### Requirement: Fixed backend render settings

The WebGL backend SHALL render the mirrored/blurred region at `renderScale: 0.5` and the content body at `contentScale: 1`.

The SVG backend SHALL use `mapScale: 0.1` and cap the displacement map at `1920 × 1080`.

Both backends SHALL use `blur: 2.00` and `feather: 72`.

#### Scenario: WebGL split resolution

- **WHEN** the WebGL backend starts
- **THEN** its render detail reports `renderScale: 0.5` and `contentScale: 1`

#### Scenario: SVG low-resolution map

- **WHEN** the SVG backend starts
- **THEN** its SVG options report `mapScale: 0.1` and `maxMR: 1920x1080`

#### Scenario: Shared blur

- **WHEN** either backend starts
- **THEN** its filter blur is `2.00`

#### Scenario: Shared feather

- **WHEN** either backend starts
- **THEN** its filter feather is `72`

## REMOVED Requirements

### Requirement: Empty gradient content area

**Reason**: Replaced by a solid content surface and a pointer-reactive block field; the depth band and gradient edge are no longer part of the design.

**Migration**: Remove the two CSS linear-gradient layers and their `background-blend-mode: darken` dependency. The content surface uses the centre colour; the mirror root and seam guard use the same colour.

### Requirement: Floating tuning panel

**Reason**: The depth band and its fade control were removed, so the old panel's fade/feather surface controls no longer describe the page.

**Migration**: Use the new Floating surface panel, which exposes only faint outside-block colour and centre colour while feather remains fixed at `72`.
