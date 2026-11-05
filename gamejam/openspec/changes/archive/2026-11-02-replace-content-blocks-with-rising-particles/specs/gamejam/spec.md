# Spec Delta

## ADDED Requirements

### Requirement: Rising particle field

The content area SHALL draw a continuously rising field of dark particles on the nested canvas. Particles SHALL originate at or below the content bottom, move upward slowly, and recycle at the bottom after fading out.

Particle size, opacity/depth, speed, horizontal sway, and lifetime SHALL be independently randomized. The default particle colour SHALL be `#242622`.

#### Scenario: Continuous upward motion

- **WHEN** the field is observed over time
- **THEN** particles move upward from the content bottom
- **AND** expired particles recycle below the bottom and fade in again
- **AND** the field remains populated across the content height

#### Scenario: Randomized size and depth

- **WHEN** the particle pool is inspected
- **THEN** particle sizes vary within the configured range
- **AND** particle opacities vary independently of their sizes
- **AND** the field contains both small dark specks and larger faint motes

#### Scenario: Shrink and fade

- **WHEN** a particle ages
- **THEN** its drawn radius decreases
- **AND** its opacity fades out near the end of its life
- **AND** it is no longer visible before it recycles

#### Scenario: Reduced motion

- **WHEN** `prefers-reduced-motion: reduce` is active
- **THEN** the field renders a static distribution of particles
- **AND** the animation loop does not run

### Requirement: Continuous field scheduling

The particle field SHALL run its animation loop continuously while the document is visible. Pointer stillness, pointer movement, or the pointer leaving the content SHALL NOT pause or resume the field.

#### Scenario: Pointer stillness does not pause

- **WHEN** the pointer is held stationary inside or outside the content
- **THEN** the field continues advancing frames and time
- **AND** no idle timer stops the loop

#### Scenario: Hidden document

- **WHEN** the document becomes hidden
- **THEN** the field stops scheduling frames
- **AND** it resumes when the document becomes visible again

### Requirement: Particle field fallback

If a Canvas 2D context cannot be created, the page SHALL keep a static CSS content background, skip the particle field, and continue mounting the mirror. It SHALL NOT leave the loading layer stuck or raise a page error.

#### Scenario: 2D context unavailable

- **WHEN** the field canvas cannot create a 2D context
- **THEN** the page mounts the mirror and removes the loading layer
- **AND** the content shows a static fallback background with the configured centre colour
- **AND** no particle field is shown

## MODIFIED Requirements

### Requirement: Procedural content field

The content area SHALL contain exactly one decorative Canvas 2D canvas sized to fill the content rectangle. The canvas SHALL be `aria-hidden` and SHALL NOT introduce user-facing text, DOM particles, or a CSS border. The page SHALL render the first field frame before removing the loading layer.

#### Scenario: Single decorative canvas

- **WHEN** the content rectangle is inspected
- **THEN** it contains exactly one canvas child using a 2D context
- **AND** the canvas is `aria-hidden`
- **AND** the content has no text content or CSS border

#### Scenario: Field is ready before the page is revealed

- **WHEN** the mirror has mounted and the loading layer is about to be removed
- **THEN** the field canvas has a non-zero backing store and has rendered at least one frame

### Requirement: Floating surface panel

The page SHALL provide a floating panel outside the mirror stage so it is not captured by the mirror.

The panel SHALL adjust only particle colour and centre colour. Feather SHALL be fixed at 72px and SHALL NOT be adjustable. It SHALL NOT expose fade, blur, WebGL scale, SVG map, or feather controls. It SHALL show the backend, DPR, content and canvas sizes, and provide `Copy config`, `Reset`, `localStorage`, and a collapsed state at or below 560px.

#### Scenario: Surface colours change live

- **WHEN** the particle colour or centre colour control changes
- **THEN** the content field and mirror root update without rebuilding the mirror
- **AND** the seam guard follows the centre colour

#### Scenario: Fixed settings are not editable

- **WHEN** the panel is inspected
- **THEN** it contains no fade, blur, WebGL scale, SVG map, or feather controls
- **AND** it shows the fixed feather of `72`
- **AND** `Copy config` reports the fixed backend and particle-field values

#### Scenario: Feather is fixed

- **WHEN** either backend is active
- **THEN** its filter feather is `72`
- **AND** no control can change it

#### Scenario: Reset restores defaults

- **WHEN** the reset action is used
- **THEN** the adjustable colours return to defaults
- **AND** the active mirror receives the fixed feather `72` and the fixed backend options
- **AND** the content field receives the default centre and particle colours
- **AND** the saved tuning value is replaced with defaults

#### Scenario: Tuning persists

- **WHEN** a visitor reloads the page after changing panel values
- **THEN** the saved colours are restored
- **AND** the mirror is created with the fixed feather `72`
- **AND** the content field starts with those values

## REMOVED Requirements

### Requirement: Pointer block field

**Reason**: The pointer-reactive block grid is replaced by a self-running particle field; pointer listeners, block cells, and pointer-presence fading are no longer part of the content.

**Migration**: Remove the pointer event listeners, pointer state/presence API, cell grid, and block shader. The canvas now draws the rising particle field and runs continuously.

### Requirement: Faint outside blocks

**Reason**: Blocks and their outside-threshold faint grid no longer exist.

**Migration**: Remove the cell grid, threshold control values, and outside-block noise. The solid centre surface remains, with dark particles drawn above it.

### Requirement: Content field fallback

**Reason**: The content field no longer depends on WebGL2; it uses a Canvas 2D context and has a different fallback trigger.

**Migration**: Replace the WebGL2 fallback requirement with the Particle field fallback requirement, which preserves the static centre surface when 2D context creation fails.
