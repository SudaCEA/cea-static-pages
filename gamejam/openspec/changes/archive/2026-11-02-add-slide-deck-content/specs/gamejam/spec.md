# Spec Delta

## ADDED Requirements

### Requirement: Slide deck content

The content area SHALL present four static slides: a cover, an about page, a mechanism page, and an info page. Each slide SHALL contain non-empty editorial copy and SHALL live inside the mirrored content subtree. Exactly one slide SHALL be active at a time.

#### Scenario: Four content slides

- **WHEN** the content is inspected
- **THEN** it contains four slides with distinct eyebrow, title, body, and footer copy
- **AND** the slides cover the sequence `00 / Mirror study`, `01 / About`, `02 / Mechanism`, and `03 / Info`

#### Scenario: Deck participates in the mirror

- **WHEN** the page is rendered
- **THEN** the slide deck is a child of the mirrored content element
- **AND** the page's slide text is not rendered in a separate non-mirrored overlay

#### Scenario: One active slide

- **WHEN** the deck is at rest
- **THEN** exactly one slide is active and visible
- **AND** all other slides are hidden and `aria-hidden="true"`
- **AND** the active slide is `aria-hidden="false"`

#### Scenario: Responsive content

- **WHEN** the deck is rendered at a narrow viewport
- **THEN** multi-column sections stack and the slide content remains within the content rectangle
- **AND** no slide has horizontal or vertical overflow

### Requirement: Deck navigation

The page SHALL provide one compact previous button at the top-left and one compact next button at the top-right. Both buttons SHALL be outside the mirrored content. The top page-number indicator SHALL NOT be shown.

Navigation SHALL also respond to vertical wheel input, arrow keys, PageUp/PageDown, and Home/End.

#### Scenario: Compact corner controls

- **WHEN** the deck controls are inspected
- **THEN** two arrow-only buttons are positioned at the top-left and top-right corners
- **AND** they are outside the mirrored content subtree
- **AND** no page-number indicator is displayed

#### Scenario: Wheel navigation

- **WHEN** the pointer is over the page and a vertical wheel gesture passes the threshold
- **THEN** wheel down advances one slide and wheel up goes back one slide
- **AND** a wheel lock prevents momentum from skipping additional slides

#### Scenario: Keyboard navigation

- **WHEN** the page has focus and an allowed navigation key is pressed
- **THEN** Arrow/PageDown advances and Arrow/PageUp goes back
- **AND** Home goes to the first slide and End goes to the last slide

#### Scenario: Boundary controls

- **WHEN** the first slide is active
- **THEN** the previous button is disabled
- **WHEN** the last slide is active
- **THEN** the next button is disabled

#### Scenario: Transition lock

- **WHEN** a slide transition is in progress
- **THEN** both paging buttons are disabled
- **AND** additional wheel or button input does not change the target slide

### Requirement: Staggered fade transitions

Slide changes SHALL fade marked elements individually using separate enter and exit delays. The base fade duration SHALL be `220ms`. The deck SHALL remain locked until every element in the outgoing and incoming groups has completed its delay plus duration.

#### Scenario: Staggered exit

- **WHEN** the next or previous slide is requested
- **THEN** the outgoing slide's marked elements fade out using their own `data-fade-out-delay` values
- **AND** elements with later delays remain visible longer
- **AND** the outgoing slide is hidden only after the slowest element finishes

#### Scenario: Staggered entry

- **WHEN** the incoming slide becomes active
- **THEN** its marked elements start from transparent and fade in using their own `data-fade-in-delay` values
- **AND** elements with later delays remain transparent during their delay
- **AND** every element ends fully opaque

#### Scenario: Completed transition

- **WHEN** the complete staggered sequence finishes
- **THEN** the active slide's elements are fully visible
- **AND** the outgoing slide's elements are fully transparent
- **AND** the deck unlocks the controls

#### Scenario: Reduced motion

- **WHEN** `prefers-reduced-motion: reduce` is active and the slide changes
- **THEN** the previous slide is hidden immediately
- **AND** the new slide is visible immediately
- **AND** no fade animation is scheduled

### Requirement: Reusable fade sequencing

The project SHALL provide a shared fade module with `fadeIn`, `fadeOut`, and `resetFade` helpers. The module SHALL discover elements marked with `data-fade`, read millisecond values from `data-fade-in-delay` and `data-fade-out-delay`, animate only opacity, and resolve only after the full group has finished.

#### Scenario: Per-element delays

- **WHEN** a slide contains multiple `data-fade` elements with different in/out delay values
- **THEN** each element's animation uses its own delay
- **AND** missing or invalid delay values default to `0`

#### Scenario: Separate entry and exit delays

- **WHEN** an element declares both an enter delay and an exit delay
- **THEN** the enter animation uses the enter delay
- **AND** the exit animation uses the exit delay

#### Scenario: Empty fade group

- **WHEN** a root has no `data-fade` elements
- **THEN** the helpers resolve without scheduling animations
- **AND** the caller can still show or hide the root normally

## MODIFIED Requirements

### Requirement: Procedural content field

The content area SHALL contain exactly one decorative Canvas 2D canvas and one decorative slide deck. Both SHALL live inside the mirrored content rectangle. The canvas SHALL be `aria-hidden`; the content SHALL NOT introduce a CSS border. The page SHALL render the first field frame before removing the loading layer.

#### Scenario: Single decorative canvas

- **WHEN** the content rectangle is inspected
- **THEN** it contains exactly one canvas child using a 2D context
- **AND** the canvas is `aria-hidden`
- **AND** the slide deck is present inside the content
- **AND** the content has no CSS border

#### Scenario: Field is ready before the page is revealed

- **WHEN** the mirror has mounted and the loading layer is about to be removed
- **THEN** the field canvas has a non-zero backing store and has rendered at least one frame

### Requirement: Reusable parallax module

The project SHALL provide a shared parallax module that accepts a root element, reads each layer's depth from `data-parallax`, updates only layer transforms, stops scheduling when settled, and cleans up listeners and transforms when destroyed. The current `mirror-2610` page SHALL NOT mount page-level parallax layers.

#### Scenario: Depth declaration

- **WHEN** the module is initialized with `data-parallax` layers
- **THEN** each layer's depth is read from its attribute
- **AND** a missing or invalid depth leaves that layer fixed

#### Scenario: Module cleanup

- **WHEN** the parallax instance is destroyed
- **THEN** pointer, visibility, and motion listeners are removed
- **AND** layer transforms are cleared
- **AND** no parallax frames are scheduled afterwards

### Requirement: Floating surface panel

The page SHALL provide a floating panel outside the mirror stage so it is not captured by the mirror. The panel SHALL start collapsed in the bottom-right corner and SHALL open on demand.

The panel SHALL adjust only particle colour and centre colour. Feather SHALL be fixed at 72px and SHALL NOT be adjustable. It SHALL NOT expose fade, blur, WebGL scale, SVG map, or feather controls. It SHALL show the backend, DPR, content and canvas sizes, and provide `Copy config`, `Reset`, `localStorage`, and the collapsed state.

#### Scenario: Starts collapsed

- **WHEN** the page first loads
- **THEN** the tuning panel is collapsed and shows only its header
- **AND** it does not overlap the top paging controls
- **WHEN** the header toggle is activated
- **THEN** the panel opens with its controls

#### Scenario: Surface colours change live

- **WHEN** the particle colour or centre colour control changes
- **THEN** the content field and mirror root update without rebuilding the mirror
- **AND** the seam guard follows the centre colour

#### Scenario: Fixed settings are not editable

- **WHEN** the panel is inspected
- **THEN** it contains no fade, blur, WebGL scale, SVG map, or feather controls
- **AND** it shows the fixed feather of `72`
- **AND** `Copy config` reports the fixed backend values and the deck state

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

### Requirement: Parallax content layers

**Reason**: The placeholder parallax containers were removed when real page content was introduced. The slide deck now lives directly inside the mirrored content.

**Migration**: Remove the `.parallax` root and its `data-parallax` containers from `mirror-2610`, remove the page's `createParallax` mount, and keep the shared `js/effects/parallax.js` module available for future pages.
