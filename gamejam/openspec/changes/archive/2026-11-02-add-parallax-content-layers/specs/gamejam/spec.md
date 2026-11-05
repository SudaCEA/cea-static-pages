# Spec Delta

## ADDED Requirements

### Requirement: Parallax content layers

The content area SHALL contain at least three decorative parallax containers with different sizes and depths. The containers SHALL use transparent backgrounds, black foreground text and borders, square corners, and SHALL be hidden from assistive technology.

#### Scenario: Layered transparent containers

- **WHEN** the content is inspected
- **THEN** it contains at least three parallax containers with distinct sizes and depths
- **AND** each container has a transparent background and no rounded corners
- **AND** borders and text use the black foreground colour

#### Scenario: Pointer-driven depth

- **WHEN** the pointer moves relative to the content rectangle
- **THEN** every parallax container translates in the opposite direction of the pointer
- **AND** containers with greater depth move farther than shallower containers
- **AND** the movement is smoothed rather than applied as a single jump

#### Scenario: Settle and reset

- **WHEN** the pointer stops moving
- **THEN** the layers settle and the parallax animation loop stops
- **AND** the pointer leaving the document returns the layers to their centred position

#### Scenario: Layout isolation

- **WHEN** the parallax layers move
- **THEN** their layout boxes do not change
- **AND** the nested canvas geometry and the content rectangle remain unchanged

#### Scenario: Live mirror capture

- **WHEN** the parallax layers move while the WebGL or SVG backend is active
- **THEN** the mirrored bands update with the transformed containers

#### Scenario: Reduced motion

- **WHEN** `prefers-reduced-motion: reduce` is active
- **THEN** the containers stay in their centred position
- **AND** the parallax loop does not run

### Requirement: Reusable parallax module

The page SHALL use a shared parallax module that accepts a root element and reads each layer's depth from `data-parallax`. The module SHALL only update layer transforms, SHALL stop scheduling when settled, and SHALL clean up listeners and transforms when destroyed.

#### Scenario: Depth declaration

- **WHEN** the module is initialized with `data-parallax` layers
- **THEN** each layer's depth is read from its attribute
- **AND** a missing or invalid depth leaves that layer fixed

#### Scenario: Module cleanup

- **WHEN** the parallax instance is destroyed
- **THEN** pointer, visibility, and motion listeners are removed
- **AND** layer transforms are cleared
- **AND** no parallax frames are scheduled afterwards

## MODIFIED Requirements

### Requirement: Procedural content field

The content area SHALL contain exactly one decorative Canvas 2D canvas and one aria-hidden parallax overlay containing decorative DOM containers. The canvas SHALL be `aria-hidden` and SHALL fill the content rectangle. The content SHALL NOT introduce a CSS border. The page SHALL render the first field frame before removing the loading layer.

#### Scenario: Single decorative canvas

- **WHEN** the content rectangle is inspected
- **THEN** it contains exactly one canvas child using a 2D context
- **AND** the canvas is `aria-hidden`
- **AND** the parallax overlay is present and `aria-hidden`
- **AND** the content has no CSS border

#### Scenario: Field is ready before the page is revealed

- **WHEN** the mirror has mounted and the loading layer is about to be removed
- **THEN** the field canvas has a non-zero backing store and has rendered at least one frame
