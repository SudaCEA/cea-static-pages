# gamejam Specification

## Purpose

Define the public static page set for the GameJam 2026 site and the runtime, visual, and build behavior of the `mirror-2610` page.

## Requirements

### Requirement: Published page set

The site SHALL publish a Material 3 directory page at `/` and a mirror homepage at `/mirror-2610/`. The diagnostic lab `mirror-2610/mirror-lab.html` SHALL remain a source-only development page: it SHALL stay in the source tree for the probe scripts, and SHALL NOT be part of the build output.

The directory page SHALL list `MIRROR / 2610` as its only page entry and SHALL NOT list the mirror lab.

#### Scenario: Directory lists only the public page

- **WHEN** a visitor opens `/`
- **THEN** the page displays one page card linking to `./mirror-2610/`
- **AND** the page contains no link or label for the mirror lab

#### Scenario: Lab stays source-only

- **WHEN** the page is built
- **THEN** `dist/gamejam/` contains no `mirror-2610/mirror-lab.html`
- **AND** the lab file is still present in the source tree for local probes
- **AND** the page build hook fails if the lab leaks into the staging tree

#### Scenario: Directory theme switching

- **WHEN** a visitor selects a theme color on `/`
- **THEN** the Material 3 color roles, theme preview, `theme-color` meta value, and `aria-pressed` states update
- **AND** the selection persists across reloads

### Requirement: Three bundle loading progress

The `mirror-2610` page SHALL load the shared three.js bundle before running the HTML-in-Canvas preflight and SHALL show the download progress while it loads.

The progress indicator SHALL show a percentage when the total size is known and an indeterminate state otherwise.

#### Scenario: Known download size

- **WHEN** the three bundle response includes a usable total size
- **THEN** the loading overlay reports the downloaded bytes, total bytes, and a percentage
- **AND** the progress bar advances with the download

#### Scenario: Unknown download size

- **WHEN** the total size is unavailable
- **THEN** the loading overlay uses the indeterminate progress state
- **AND** the page still proceeds to the compatibility preflight after the bundle loads

### Requirement: Loading and preflight presentation

The `mirror-2610` loading layer SHALL use a white background, black foreground, square controls, and no decorative branding.

The layer SHALL contain the progress indicator and the preflight question in one surface. Both SHALL be centered in the viewport. It SHALL remain visible until any required preflight question has been answered.

#### Scenario: Centered crossfade

- **WHEN** the three bundle finishes and a preflight question is required
- **THEN** the loading progress and the question are both centered in the viewport
- **AND** the progress fades out while the question fades in
- **AND** the crossfade completes in 250ms

#### Scenario: No decorative branding

- **WHEN** the loading layer is visible
- **THEN** it displays only functional status, progress, and preflight content
- **AND** it does not display `MIRROR / 2610`, `MIRROR`, or `镜像` as decoration

#### Scenario: Preflight stays inside the loading layer

- **WHEN** the preflight result requires a choice or an informational acknowledgement
- **THEN** the question appears as a square panel inside the loading layer
- **AND** the loading layer stays visible while the question is open
- **AND** it is removed only after the question is answered or dismissed

#### Scenario: Square monochrome presentation

- **WHEN** the loading layer and preflight panel are rendered
- **THEN** the background is white and the foreground is black
- **AND** the progress bar, panel, and buttons have no corner radius

### Requirement: HTML-in-Canvas backend selection

After the three bundle loads, the page SHALL run `checkHtmlInCanvasSupport()` and select WebGL, offer a choice, or fall back to SVG according to the preflight result.

#### Scenario: Compatible Chrome starts WebGL

- **WHEN** the preflight reports HTML-in-Canvas support and a compatible Chrome version
- **THEN** the page starts the WebGL backend without a compatibility dialog
- **AND** the loading overlay is removed after the mirror is ready

#### Scenario: Incompatible Chrome offers a choice

- **WHEN** the preflight reports support but a Chrome version below `157.0.8080.0`
- **THEN** the page explains the possible offset or scaling issue in a panel inside the loading layer
- **AND** it provides “继续使用 WEBGL” and “回退到 SVG” actions
- **AND** the loading layer stays visible until the panel is dismissed
- **AND** dismissing the panel defaults to SVG

#### Scenario: Unknown version offers a choice

- **WHEN** the preflight reports support but cannot detect the browser version
- **THEN** the page explains that compatibility is unverified inside the loading layer
- **AND** it provides the same WebGL and SVG choices

#### Scenario: Unsupported browser falls back to SVG

- **WHEN** the preflight reports that HTML-in-Canvas is unavailable
- **THEN** the page starts the SVG backend
- **AND** it shows a one-button informational panel inside the loading layer recommending a compatible Chrome with `chrome://flags/#canvas-draw-element`
- **AND** the loading layer stays visible until the panel is dismissed

#### Scenario: Runtime failure falls back to SVG

- **WHEN** the three bundle fails to load or WebGL startup fails
- **THEN** the page falls back to SVG
- **AND** it shows a failure panel inside the loading layer
- **AND** the loading layer is removed only after the panel is dismissed instead of leaving it indefinitely

### Requirement: HTML-in-Canvas origin trial

The `mirror-2610` page SHALL carry a Chrome origin trial token for the `HTMLInCanvas` feature in its document head, so stable Chrome visitors can use the WebGL backend without enabling a flag. The token SHALL be a static `<meta http-equiv="origin-trial">` in the page head rather than something injected per backend, because a token applies to the whole document and must be present before any feature detection runs. The source-only diagnostic lab SHALL NOT carry the token.

#### Scenario: Token in the document head

- **WHEN** `mirror-2610/index.html` is inspected
- **THEN** exactly one `<meta http-equiv="origin-trial">` sits inside `<head>`
- **AND** its payload names the `HTMLInCanvas` feature, the production origin with the subdomain flag, and an expiry date in the future
- **AND** the token is not conditioned on the selected backend
- **AND** `mirror-lab.html` contains no token

#### Scenario: Preflight logic stays unchanged

- **WHEN** the token enables the API for a visitor
- **THEN** support is still decided by the feature probe in `checkHtmlInCanvasSupport()`
- **AND** the `157.0.8080.0` version gate still guards the nested-canvas device-pixel bug
- **AND** a participating Chrome below the gate reaches the existing WebGL/SVG compatibility dialog instead of falling back silently
- **AND** browsers that ignore origin trials keep the SVG fallback path

#### Scenario: Missing or expired token

- **WHEN** the token is absent, expired, or served from a non-matching origin
- **THEN** Chrome ignores it without raising a page error
- **AND** the page keeps booting with whatever the feature probe reports, falling back to SVG when the API is unavailable

### Requirement: Content sizing

The content region SHALL target 72% of the stage width and 72% of the stage height, and SHALL fill the stage at 100% × 100% on engines that cannot render the mirror bands.

The actual CSS content size SHALL remain within 1 CSS pixel of the target after device-pixel snapping.

#### Scenario: Default desktop size

- **WHEN** the page is viewed at 1440×900 CSS pixels
- **THEN** the content target is `1036.8 × 648`
- **AND** the rendered CSS content size is `1036 × 648`

#### Scenario: Full-bleed fallback

- **WHEN** the browser cannot paint the mirror bands (see SVG backend engine coverage)
- **THEN** the content target is the full stage and the mirror renders no bands
- **AND** the page marks its layout as full-bleed for styling and diagnostics
- **AND** the deck keeps the same container-relative typography, so the composition scales with the stage

#### Scenario: Resize updates the content

- **WHEN** the viewport size changes
- **THEN** the content target is recalculated from the new stage size
- **AND** the mirror relayouts using the new result

### Requirement: Device-pixel alignment

`mirror.js` SHALL own the shared layout calculation and SHALL produce both CSS-pixel and integer device-pixel rectangles.

SVG filter geometry, WebGL canvas output, render targets, texture capture rectangles, and hit-test geometry SHALL derive from the same layout. Pages SHALL NOT perform their own DPR snapping before calling `createMirror()`.

#### Scenario: Integer layout at DPR 1.5

- **WHEN** the page is viewed at 1440×900 CSS pixels with DPR 1.5
- **THEN** the device content rectangle is `1554 × 972` at `(303, 189)`
- **AND** every content edge coordinate is an integer number of device pixels
- **AND** the WebGL canvas output is `2160 × 1350`

#### Scenario: Same layout for both backends

- **WHEN** the same viewport and DPR are rendered through SVG and WebGL
- **THEN** both backends consume the same CSS and device content rectangles

#### Scenario: No content-edge seam

- **WHEN** either backend renders the page at a tested DPR
- **THEN** the content edge does not expose the page backdrop through a 1–2px seam
- **AND** pixel inspection across the content boundary finds no abrupt color step
- **AND** when the WebGL composite path is active, it draws a two-device-pixel full-resolution edge skirt from the body texture
- **AND** no DOM overlay border is drawn along the content edge

### Requirement: Fixed backend render settings

The WebGL backend SHALL default to `renderScale: 1` and `contentScale: 1`, rendering the mirrored region and content body in the direct 1x pass. When `renderScale` is below 1, its composite pass SHALL draw a two-device-pixel full-resolution skirt around the content, sampling the body texture's stable edge colour over the low-resolution seam.

The SVG backend SHALL use `mapScale: 0.1` and cap the displacement map at `1920 × 1080`.

Both backends SHALL use `blur: 2.00` and `feather: 72`.

#### Scenario: WebGL direct resolution

- **WHEN** the WebGL backend starts
- **THEN** its render detail reports `renderScale: 1` and `contentScale: 1`

#### Scenario: SVG low-resolution map

- **WHEN** the SVG backend starts
- **THEN** its SVG options report `mapScale: 0.1` and `maxMR: 1920x1080`

#### Scenario: Shared blur

- **WHEN** either backend starts
- **THEN** its filter blur is `2.00`

#### Scenario: Shared feather

- **WHEN** either backend starts
- **THEN** its filter feather is `72`

### Requirement: SVG backend engine coverage

The SVG backend SHALL render its reflections through a `backdrop-filter: url(#…)` reference whose primitive chain includes `feImage` (displacement map and feather mask) and `feDisplacementMap`.

The page SHALL detect the gap before mounting and render the content full-bleed instead of leaving empty margins. The preflight panel SHALL name the missing capability and recommend Chrome. No engine-specific reflection fallback SHALL ship in this revision.

#### Scenario: Firefox renders everything except the bands

- **WHEN** the page is rendered by Firefox and the SVG backend is active
- **THEN** the deck, paging, fades, particle field, and quadrant colour filters all render normally
- **AND** the mirror bands outside the content rectangle stay flat, because Gecko drops the non-GPU-accelerated `feImage` / `feDisplacementMap` primitives (mozilla bug 1896504, duplicate 1972363)
- **AND** the content fills the viewport instead of leaving the four empty margins
- **AND** the preflight panel reports that the mirror reflection is unsupported and recommends Chrome
- **AND** no error, fallback banner, or console error is produced
- **AND** the mirror skips the displacement and mask maps entirely, so no full-viewport filter rasterization happens

#### Scenario: Safari renders no url() backdrop filter

- **WHEN** the page is rendered by a WebKit browser
- **THEN** neither the mirror bands nor the quadrant colour filters render, because `backdrop-filter: url(#…)` is not implemented (webkit bug 245510)
- **AND** the content fills the viewport and the preflight panel reports the missing reflection
- **AND** the rest of the deck stays usable

#### Scenario: Chromium renders the bands

- **WHEN** the page is rendered by a Chromium browser with either backend
- **THEN** the reflected bands render outside the content rectangle
- **AND** the quadrant colour filters tint their quadrants

#### Scenario: Coverage stays documented

- **WHEN** the browser limitation is reviewed
- **THEN** the `mirror.js` module docs and the project README both name Gecko and WebKit, the two upstream bug IDs, and the fact that the failure is in the `feImage` primitive rather than in how the map is mounted (data URI, blob URL, or element reference)

### Requirement: Static build integration

The gamejam page SHALL build through the repository build entry into `dist/gamejam/`.

The build SHALL include the directory page, the `mirror-2610` homepage, its page assets and data, shared effects, three runtime assets, and the closing wordmark, and SHALL exclude source-only files including the diagnostic lab.

#### Scenario: Clean build

- **WHEN** `python build.py gamejam --clean --strict` runs
- **THEN** the build succeeds
- **AND** `dist/gamejam/` contains the root index, `mirror-2610/index.html`, its `assets/` and `data/`, `assets/mirror-26/cea-logo.svg`, `js/effects/`, and `libs/three/`
- **AND** it contains no `tools/`, `page.toml`, `build.py`, `libs/three/src/`, or `mirror-2610/mirror-lab.html` paths

### Requirement: Resize structure veil

The page SHALL provide a non-interactive full-screen veil outside the mirrored content, above the deck controls and below the boot layer. It SHALL fade in on the mirror's `resizeStart`, stay visible through `resizing`, and fade out after `resizeEnd`. The mirror resize debounce SHALL be 500ms. Programmatic `resize` emissions SHALL only update measurements, not show the veil.

#### Scenario: Initial state

- **WHEN** the page finishes loading
- **THEN** the structure veil is hidden and the mirror is unchanged
- **AND** the veil is outside the mirrored content

#### Scenario: Resize pulse

- **WHEN** the mirror emits `resizeStart`
- **THEN** the veil fades in while resizing is active
- **AND** the measurements update continuously while the resize sequence runs
- **AND** they use the current container size without waiting for layout
- **WHEN** the mirror emits `resizeEnd` after the 500ms debounce
- **THEN** it holds 475ms and then fades out over 250ms
- **AND** it is completely gone roughly 0.7s after `resizeEnd`
- **AND** it never intercepts pointer events

#### Scenario: Programmatic refresh does not pulse

- **WHEN** `mirror.refresh()` emits `resize` without a resize lifecycle
- **THEN** the veil stays hidden
- **AND** only the dimension labels may update

#### Scenario: Constructivist structure

- **WHEN** the veil is visible
- **THEN** it shows the content rectangle and four surrounding reflection regions
- **AND** live width and height measures sit above and left of the content
- **AND** pale serif labels name the four reflection regions and the content
- **AND** `resizing...` sits at the bottom right

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

### Requirement: Solid content surface

The content background SHALL be the configured centre colour with no depth band, edge gradient, rectangular rings, aperture line, or CSS border. The mirror root SHALL use the same centre colour.

#### Scenario: Solid surface

- **WHEN** the content background is inspected
- **THEN** it is a solid configured centre colour
- **AND** no depth band or edge gradient is drawn
- **AND** no rectangular rings or inner border are drawn

#### Scenario: Seamless centre colour

- **WHEN** pixels are sampled across the content boundary on a background edge
- **THEN** the content edge and the mirror root use the same configured centre colour
- **AND** the WebGL edge skirt repeats the content edge colour at the boundary
- **AND** no white outline appears under a bottom rule

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

### Requirement: Fixed visual parameters

The page SHALL NOT expose a runtime tuning panel. The two former knobs SHALL be baked into the stylesheet: the cover bottom rule SHALL be `6px` high and the sideview image SHALL sit at `150%` of its column, anchored at the content's bottom-right corner. The cover content-to-rule gap SHALL stay `32px`, the text translation `0px`, and the surface colours SHALL be constants: centre `#ffffff` and particles `#242622`. Feather SHALL stay fixed at `72px`.

#### Scenario: No tuning panel

- **WHEN** the page is inspected
- **THEN** no floating panel, collapse toggle, slider, colour input, `Copy config`, or `Reset` control exists
- **AND** no tuning value is read from or written to `localStorage`

#### Scenario: Baked cover defaults

- **WHEN** the cover slide is active
- **THEN** the bottom rule is `6px` high, spans the content, and sits on the content bottom edge
- **AND** the sideview image renders at `150%` scale, anchored at the content bottom-right, with only the fixed `2px` right nudge
- **AND** the content-to-rule gap is `32px` and the text lockup keeps `0` vertical translation
- **AND** the sideview image stays loaded and keeps `object-fit: contain`

#### Scenario: Fixed surface and filter values

- **WHEN** either backend is active
- **THEN** the content field draws on `#ffffff` with `#242622` particles
- **AND** the mirror feather is `72` and cannot be changed at runtime
- **AND** the WebGL and SVG backend options are only supplied at creation time
- **AND** layout and backend diagnostics remain readable through `window.__mirrorHome.getState()`

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

### Requirement: Reusable parallax module

The project SHALL provide a shared parallax module that reads each layer's `data-parallax` depth, updates only layer transforms, settles to idle, and cleans up on destroy. `mirror-2610` SHALL mount it on the cover, quadrant, ranking, work detail, and closing slides, with distinct depths for the cover text, quadrant copy, ranking board/cards, and the closing lockup; the two ranking labels SHALL share one depth. It SHALL scale its displacement down on narrow viewports.

#### Scenario: Depth declaration

- **WHEN** the module is initialized with `data-parallax` layers
- **THEN** each layer's depth is read from its attribute
- **AND** a missing or invalid depth leaves that layer fixed

#### Scenario: Cover depth layers

- **WHEN** the cover slide is inspected
- **THEN** `CEA GameJam`, `2026.10`, and `参赛作品展示` each carry a `data-parallax` depth
- **AND** the three depths are distinct
- **AND** only those text elements translate

#### Scenario: Quadrant depth layers

- **WHEN** the quadrant slide is inspected
- **THEN** its titles, details, and centre mark have at least three distinct `data-parallax` depths
- **AND** the transforms are applied only to text inside the quadrant slide
- **AND** the filter panels and rules do not translate

#### Scenario: Ranking depth layers

- **WHEN** the ranking slide is inspected
- **THEN** the board and cards carry `data-parallax` depths
- **AND** both left-rail labels carry the same `data-parallax` depth
- **AND** hovering a card raises only that card to a nearer depth
- **AND** leaving the card restores its base depth

#### Scenario: Closing depth layers

- **WHEN** the closing slide is inspected
- **THEN** the wordmark carries a far `data-parallax` depth and the detail copy a nearer one
- **AND** only the lockup elements translate
- **AND** the two sheet rules do not translate

#### Scenario: Module cleanup

- **WHEN** the parallax instance is destroyed
- **THEN** pointer, visibility, and motion listeners are removed
- **AND** layer transforms are cleared
- **AND** no parallax frames are scheduled afterwards

### Requirement: Slide deck content

The content area SHALL present five mirrored slides: a cover, a quadrant page, a ranking page, a work detail page, and a closing page. Exactly one slide SHALL be active. Each slide SHALL contain non-empty editorial copy and SHALL live inside the mirrored content subtree.

#### Scenario: Five content slides

- **WHEN** the content is inspected
- **THEN** it contains five slides with non-empty editorial copy
- **AND** the cover presents `CEA GameJam`, `2026.10`, and `参赛作品展示`
- **AND** the remaining slides cover the quadrant page, the ranking page, the work detail page, and the closing page

#### Scenario: Quadrant page structure

- **WHEN** the quadrant slide is active
- **THEN** it shows a 3px centred cross, a free-standing `镜` at the origin, and four copy groups in the quadrants
- **AND** each copy group and the centre mark have no visible outer border or background
- **AND** the four serif titles read `时间`, `主题`, `限制`, and `评分`
- **AND** all titles are centred
- **AND** the titles and the centre mark use an enlarged serif hierarchy, substantially larger than the detail copy
- **AND** the page has no eyebrow or footer separator
- **AND** the centre mark sits below the filter panels

#### Scenario: Quadrant typography

- **WHEN** the quadrant slide is rendered
- **THEN** its titles and centre mark use a display-serif scale substantially larger than the detail copy
- **AND** the detail copy spans multiple lines and wraps when space is tight
- **AND** neither the title nor the detail crosses the centre rules

#### Scenario: Corner offsets

- **WHEN** the quadrant slide is rendered
- **THEN** each copy group is translated outward from its quadrant centre toward its outer corner
- **AND** the offset uses the content width and height so it scales with the page
- **AND** the offset shrinks on narrow viewports
- **AND** every copy group remains inside the content rectangle

#### Scenario: Quadrant copy reveal

- **WHEN** the pointer is outside a quadrant or over the centre mark's dead zone
- **THEN** that quadrant shows only its large serif title
- **WHEN** the pointer is inside a quadrant
- **THEN** its title fades out and a multi-line serif detail fades in
- **AND** the details remain centred in the offset copy area and do not cross the centre rules

#### Scenario: Cover layout

- **WHEN** the cover is inspected
- **THEN** it has no eyebrow, footer divider, or text border
- **AND** the bottom-left lockup puts `CEA GameJam` and `2026.10` on one baseline, with `参赛作品展示` below
- **AND** all cover text is serif and left aligned
- **AND** the bottom-right shows the transparent clipped `ellia / sideview` image at its native `1401/978` ratio
- **AND** the image uses `object-fit: contain`, renders at the fixed `150%` scale, and is anchored flush to the content bottom-right
- **AND** the image is nudged `2px` past the right content edge so the rendered edge has no white seam
- **AND** the image has finished loading before the mirror mounts
- **AND** the image is positioned independently of the text lockup and does not reduce its column width
- **AND** the brand/date line, the title, and the two columns have breathing room rather than sitting flush
- **AND** a black rule (`6px`) spans the content bottom below the lockup and image
- **AND** the rule sits `32px` below the lowest cover content

#### Scenario: Cover fade order

- **WHEN** the cover enters or leaves
- **THEN** the brand fades first, the date second, the exhibition title third, and the sideview image fourth
- **AND** the persistent sheet rules do not fade with the slide
- **AND** the exit uses a shorter independent delay for each element

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

### Requirement: Persistent sheet rules

The deck SHALL contain two solid absolute rules outside the slide fade groups, clipped by the content overflow. They SHALL follow the slides as an overlapping cover rule, a quadrant cross, ranking columns, detail top and bottom frames, and closing 45° cuts through the midpoints of the content's left and right edges. Separate quadrant rule elements SHALL NOT remain.

#### Scenario: Cover bottom rule

- **WHEN** the cover is active
- **THEN** the two rules overlap at the content bottom into one visible rule
- **AND** each uses the configured cover line height
- **AND** the rules are direct deck children outside every slide fade group

#### Scenario: Quadrant cross

- **WHEN** the quadrant slide is active
- **THEN** one rule spans the content horizontally at the centre height
- **AND** the other rotates 90 degrees into the full-height centre rule
- **AND** both rules use a 3px cross thickness
- **AND** the quadrant slide contains no separate rule elements

#### Scenario: Ranking columns

- **WHEN** the ranking slide is active
- **THEN** the two rules stand vertically at 30% and 90% of the content width
- **AND** both use a 3px thickness
- **AND** the ranking list occupies the 60% column between them

#### Scenario: Rule transition

- **WHEN** the deck moves from the cover to the quadrant slide
- **THEN** the rules transition to the cross positions with rotation
- **AND** the transition starts with the slide transition
- **AND** each rule is longer than the content diagonal so its ends stay clipped
- **WHEN** the deck moves to the ranking slide
- **THEN** the rules separate into the two vertical columns
- **WHEN** the deck moves to the work detail slide
- **THEN** both ranking rules turn clockwise by 90° into horizontal rules
- **AND** they land inside the content top and bottom edges
- **WHEN** the deck moves to the closing slide
- **THEN** both rules turn clockwise by a further 45° and travel until each centre sits on the midpoint of a content short edge
- **AND** the top rule travels to the right short edge and the bottom rule to the left short edge, so neither line crosses over the other
- **AND** each rule crosses its edge exactly at its own centre, so the two visible cuts run at 45° across the top-right and bottom-left corners
- **WHEN** the deck returns to the cover
- **THEN** the rules transition back to the overlapping bottom rule

### Requirement: Ranking page

The ranking slide SHALL frame a right-shifted scrollable team list between the persistent rules, with a large primary `评分排行` label and a smaller `Rank list` subtitle stacked in a left rail. Cards SHALL render from `data/ranking.json` with ranks, awards, work titles, team names, criterion scores, and overall scores. The list SHALL suppress horizontal scrolling and scroll vertically without deck navigation. Card depth SHALL follow pointer hover only.

#### Scenario: Framed list

- **WHEN** the ranking slide is active
- **THEN** the list column sits between the two vertical rules
- **AND** the scrollable list is inset from both rules
- **AND** the ranking slide does not clip cards at its own edges
- **AND** `评分排行` and `Rank list` sit horizontally in one left rail
- **AND** `评分排行` is the larger primary label and `Rank list` is a smaller tracked subtitle
- **AND** the rail is vertically centred and inset from the content edge
- **AND** the two labels are stacked with a gap and neither crosses the left rule
- **AND** both labels share the same parallax depth
- **AND** every team card has a transparent background and a 1px black border
- **AND** the card's rank/award cluster has no extra border

#### Scenario: Ranking data cards

- **WHEN** the ranking slide is active
- **THEN** the list renders one card per team from `data/ranking.json`, in rank order
- **AND** the left cluster stacks `#` plus the rank number and one tag per won award
- **AND** the centre shows the work title above the team name
- **AND** the right side shows a 2×2 grid of criterion labels and averages plus the overall score
- **AND** the top-ranked card reads `#1`, `镜界`, `吴彦组`, and `7.93`
- **AND** tied teams show the same rank number and a `并列` marker

#### Scenario: Ranking accent hierarchy

- **WHEN** the ranking cards are rendered
- **THEN** ranks 1–3 use the accent colour for their rank numbers
- **AND** the first-place overall score uses the accent colour
- **AND** award tags use the accent colour for text and border
- **AND** the criterion cell corresponding to a won award uses the accent colour for its label and value
- **AND** non-award criteria and the other overall scores remain neutral

#### Scenario: Compact ranking cards

- **WHEN** the ranking slide is rendered at or below `1120px`
- **THEN** the card header and the score breakdown stack into two rows
- **AND** the score remains below the criterion grid, aligned to the right
- **WHEN** the ranking slide is rendered at or below `700px`
- **THEN** the left-rail labels are hidden

#### Scenario: List scrolling

- **WHEN** the pointer is inside the framed ranking area and the wheel or trackpad scrolls
- **THEN** the scroll is forwarded to the team list as a target and interpolated with rAF
- **AND** no horizontal scrollbar appears
- **AND** native, keyboard, or scrollbar movement re-seeds the target
- **AND** the deck does not change slides
- **AND** the deck resumes wheel navigation outside that area

#### Scenario: Card hover

- **WHEN** the pointer hovers a team card
- **THEN** the card scales up without gaining a white fill
- **AND** its parallax depth becomes nearer than the base card depth
- **WHEN** the pointer leaves the card, including after clicking its transparent area
- **THEN** the card returns to its base parallax depth

#### Scenario: Narrow ranking

- **WHEN** the ranking slide is rendered at or below `700px`
- **THEN** the left-rail labels are hidden
- **AND** the rules move to the outer 4% / 96% columns
- **AND** the list keeps the full remaining width

### Requirement: Work detail page

The work detail slide SHALL frame the content with horizontal persistent rules, a 24% title/source rail, a per-work video panel, a chrome-free action tray, and a 7% dash-pager footer. Wheel input inside the frame SHALL switch works. Work data SHALL render from `data/ranking.json` and `data/works.json` before mirror mount.

#### Scenario: Detail composition

- **WHEN** the work detail slide is active
- **THEN** two 3px horizontal rules lie inside the content top and bottom edges
- **AND** the left rail holds a 1px-boxed work title, that work's description, and a `来自：` team line above a 1px rule, with symmetric tight padding
- **AND** that whole title/body/team group is vertically centred in the rail without stretching the body or pinning the team line to the bottom
- **AND** the video keeps a small right gap of roughly 3% of the content width
- **AND** the video panel renders only the current work's clip, with no caption rows, wordmark, counter, or ratio marks
- **AND** a work without a clip shows a centred `暂无视频 / NO CLIP YET` placeholder inside the framed stage instead of an empty panel
- **AND** the clip is contained in a fitted stage so it never exceeds the panel
- **AND** no clip element exists until the detail slide is first activated
- **AND** a clip is only visible while the detail slide is live, because the composited video layer ignores ancestor visibility
- **AND** clips are faststart-encoded so metadata precedes the media data
- **AND** four 2px L-shaped corner marks sit in the padding ring, offset outward from the clip corners by half their own size
- **AND** the clip plays with sound on loop while the slide is active and pauses when the slide leaves
- **AND** a browser refusing unmuted autoplay falls back to muted playback instead of stalling
- **AND** `prefers-reduced-motion` keeps the clip paused on its first frame

#### Scenario: Detail work media and links

- **WHEN** a work record in `data/works.json` is selected
- **THEN** its `description` fills the rail body
- **AND** its `video.src` becomes the panel source, or the panel empties when the record has no video
- **AND** an empty panel drops the source, pauses the element, keeps the stage ratio and corner marks, and relabels itself as having no video
- **AND** `links.download`, `links.play`, and `links.project` each enable exactly one action button when they hold a URL
- **AND** a missing link leaves its button disabled and faded
- **AND** enabled actions open their stored URL in a new tab
- **AND** records are keyed by `teamId`, one per team

#### Scenario: Detail clip loading veil

- **WHEN** a work with a clip is selected
- **THEN** a white veil slides in inside a clipped window before the clip is shown
- **AND** a forward switch enters from below and leaves through the top
- **AND** a backward switch enters from above and leaves through the bottom
- **AND** the veil shows a loading label, the work name, a progress bar, and a percentage
- **AND** the veil slides out through the top only after the clip reports `canplay`
- **AND** the visible clip is swapped while the veil still covers the panel, so the exit reveals the new clip rather than the old one
- **AND** a clip that is already loaded replays the same cycle with shortened timings
- **AND** the bar reports the buffered span as a share of the clip duration
- **AND** the bar is accented until `canplay` fires and turns to ink afterwards
- **AND** an unknown duration falls back to an indeterminate sweep
- **AND** playback starts as soon as `canplay` fires instead of after the whole file is fetched

#### Scenario: Detail clip stall layer

- **WHEN** the active clip fires `waiting` or `stalled` during playback
- **THEN** a translucent `Loading` sheet appears immediately over the clip with no transition
- **WHEN** the clip fires `playing`, `canplay`, `seeked`, or `pause`, or the slide leaves
- **THEN** the sheet disappears immediately
- **AND** the sheet never intercepts pointer events
- **AND** the sheet stacks below the loading veil and is never shown while the veil is presenting a switch
- **AND** a failed clip keeps the veil parked in an accent error state, never uncovering the panel or swapping the clip
- **AND** switching to a working clip afterwards still exits the veil normally

#### Scenario: Detail clip switch locking

- **WHEN** the veil is entering or exiting
- **THEN** wheel, arrow, and click switches are ignored and the queued wheel delta is dropped
- **WHEN** the veil is parked on a loading clip and another work is selected
- **THEN** the veil does not replay its entrance or exit
- **AND** only the work name and progress display change
- **AND** the previously started load keeps running instead of being cancelled
- **AND** eviction only removes ready, inactive clips
- **AND** the action tray sits at the video's lower-right corner, protrudes slightly past its right and bottom borders, and remains inside the content
- **AND** the footer occupies 7% of the content height
- **AND** the former featured side card and award footer are absent

#### Scenario: Detail rule transition

- **WHEN** the deck moves from the ranking slide to the work detail slide
- **THEN** both ranking rules turn clockwise by 90° into horizontal detail rules
- **AND** the top rule lands on the content top edge and the bottom rule on the content bottom edge
- **AND** neither rule takes a counter-clockwise or 270° path

#### Scenario: Detail typography

- **WHEN** the work detail slide is rendered
- **THEN** the work title, body, source, team, and action labels use the serif stack
- **AND** the body copy is at least 13px, the action labels at least 15px, and their latin subtitles at least 9px
- **AND** the title is centred inside its 1px outline box
- **AND** the paging arrows reuse the mono deck-button face without turning editorial copy into sans or mono

#### Scenario: Detail footer

- **WHEN** the work detail slide is active
- **THEN** the work switcher is centred in the reduced 7% footer and keeps a fixed gap above the bottom rule
- **AND** the footer no longer carries the work counter, which the pager replaces
- **AND** both arrows use standalone button styles matching the deck-button dimensions and glyph face but stay bare at rest
- **AND** hovering an arrow draws only its 1px outline with a border-colour transition, keeping the transparent fill and black glyph
- **AND** 15 equal-length dash segments sit between the arrows with no gaps, and only the current work's segment turns solid black at twice the idle thickness
- **AND** each segment is a button with a 28–34px hover band; hovering or focusing a non-current segment triples its bar height to 24px
- **AND** clicking a segment jumps straight to that work, and the current segment carries `aria-current`
- **AND** the footer no longer repeats the work title or an award tag

#### Scenario: Detail work switch

- **WHEN** the detail arrows are used or the wheel moves with the pointer inside the top/bottom rules
- **THEN** the title, team, pager mark, and slide label update together and animate on entry
- **AND** the rail copy animates in three staggered `560ms` steps and the veil takes `560ms` in and `520ms` out
- **AND** wheel input is captured with a threshold and a short lock so one gesture advances one work
- **AND** the deck stays on the detail slide while the pointer is inside the frame
- **AND** wheel input outside the frame resumes deck navigation
- **AND** stepping before the first work hands the gesture to the deck and turns to the previous page
- **AND** stepping past the last work hands the gesture to the deck and turns to the closing page
- **AND** `prefers-reduced-motion` skips the work-switch animation

#### Scenario: Detail action tray

- **WHEN** the work detail slide is at rest
- **THEN** the action tray is hidden
- **AND** the tray has no background, border, title, close button, or footnote of its own
- **WHEN** the video is hovered, clicked, or focused and confirmed with `Enter` / `Space`
- **THEN** the tray becomes visible and the video reports `aria-expanded="true"`
- **AND** the pointer can move from the video onto the tray's protruding corner without dismissing it
- **AND** an outside click or `Escape` dismisses it
- **AND** the shared tools stack reveals a volume row directly above the tray, with the same hover and pin behaviour
- **AND** using the volume slider with the mouse does not keep the stack open: only keyboard focus pins it
- **AND** the volume slider drives the active clip's volume and new clips inherit the current value
- **AND** the tray holds three white, 1px-outlined buttons: `下载 / Download`, `在线游玩 / Play online`, and `项目主页 / Project page`
- **AND** the download action alone takes the accent colour for its outline and label
- **AND** enabled buttons invert on hover, with download filling in the accent and the others filling in ink
- **AND** disabled buttons fade their white face, outline, and label instead of staying fully inked
- **AND** an enabled action opens the URL bound to the current work, and a button with no URL stays disabled

#### Scenario: Detail parallax

- **WHEN** the work detail slide is active and the pointer moves
- **THEN** the left rail text uses the far `0.16` depth and the video plane uses the nearer `0.52` depth
- **AND** the action tray shares the video depth so it keeps hugging the video's corner
- **AND** the tray keeps enough inset for that deeper shift to stay inside the content
- **AND** `prefers-reduced-motion` parks both layers at zero offset

#### Scenario: Narrow detail

- **WHEN** the work detail slide is rendered at or below `700px`
- **THEN** the intro, video, and footer stack vertically as 24% / 69% / 7%
- **AND** both horizontal rules remain on the content top and bottom edges
- **AND** tapping the video opens the tray, and a second tap closes it
- **AND** the opened tray remains inside the content
- **AND** the slide has no horizontal or vertical overflow

### Requirement: Closing page

The deck SHALL end with a closing slide that carries no interactive controls. It SHALL centre the CEA wordmark inside the content rectangle, place muted placeholder copy directly below it, and let the two persistent rules settle as 45° cuts through the midpoints of the content's left and right edges.

#### Scenario: Closing lockup

- **WHEN** the closing slide is active
- **THEN** the wordmark is centred horizontally in the content and the whole lockup is centred vertically
- **AND** the wordmark keeps the `315.5 / 108` ratio of `assets/mirror-26/cea-logo.svg` and inherits the page ink through `currentColor`
- **AND** the detail copy sits below the wordmark with a fixed gap and no frame, rule, or button
- **AND** both detail lines are muted (alpha below 0.6), with the secondary line lighter than the primary one
- **AND** the closing slide contains no link, button, media element, or pager

#### Scenario: Closing rule cuts

- **WHEN** the closing slide is active
- **THEN** each rule renders at 45° with its centre on the midpoint of a content short edge
- **AND** the rule that framed the content top sits on the right edge and the rule that framed the content bottom sits on the left edge
- **AND** the rule crosses that edge exactly at its own centre, which is that edge's midpoint
- **AND** one cut crosses the top-right corner and the other the bottom-left corner
- **AND** both rules keep the 3px rule thickness and stay clipped at the content boundary
- **AND** the cut geometry follows the content rectangle rather than a portrait layout, so no portrait tuning is required

#### Scenario: Closing transition and fade

- **WHEN** the deck moves from the work detail slide to the closing slide
- **THEN** both rules turn clockwise from 180° to 225° and travel to the short-edge midpoints inside the same `720ms` rule transition, which starts with the slide fade
- **AND** the top rule slides right into the top-right cut and the bottom rule slides left into the bottom-left cut
- **AND** the wordmark fades in before the two detail lines through staggered per-element delays
- **WHEN** the deck returns to the work detail slide
- **THEN** the rules turn back to the 180° top/bottom frame
- **AND** `prefers-reduced-motion` jumps both the slide and the rules to their final state

#### Scenario: Closing page boundary

- **WHEN** the closing slide is active
- **THEN** the next control is disabled and the previous control stays enabled
- **AND** the deck does not wrap past the closing slide
- **AND** stepping past the last work on the detail slide opens the closing slide instead of stopping

### Requirement: Quadrant colour filters

The quadrant slide SHALL use transparent `backdrop-filter` panels with inline SVG filters for all four quadrants: red screen in the top-left, green screen in the top-right, blue screen in the bottom-left, and saturation removal in the bottom-right. The panels SHALL cover the quadrant copy, pointer, and unframed centre mark. They SHALL fade in with the slide and fade out before it hides.

#### Scenario: Screen tint preserves white

- **WHEN** the red, green, or blue quadrant is rendered
- **THEN** its filter uses `feFlood` with `feBlend mode="screen"`
- **AND** a white backdrop pixel remains white
- **AND** black or dark-grey text and lines take the quadrant tint

#### Scenario: Grayscale quadrant

- **WHEN** the bottom-right quadrant is rendered
- **THEN** its filter applies `feColorMatrix type="saturate" values="0"`
- **AND** white and black remain unchanged
- **AND** any chromatic content loses its saturation

#### Scenario: Panel stacking

- **WHEN** the quadrant page is inspected
- **THEN** exactly four transparent filter panels exist
- **AND** each computed `backdrop-filter` references its own SVG filter ID
- **AND** the panels sit above the quadrant text, pointer, and centre mark
- **AND** the centre mark has no surrounding border or opaque background

#### Scenario: Filter fade

- **WHEN** the quadrant slide enters or leaves
- **THEN** all four filter panels animate opacity with the slide fade group
- **AND** the tint is fully applied after the slide settles
- **AND** the SVG filter URL itself is not interpolated

#### Scenario: Both mirror backends

- **WHEN** the quadrant page is rendered through WebGL or SVG
- **THEN** the tint panels, pointer, and mirrored copies are all visible
- **AND** no page or console error is produced

### Requirement: Content pointer ring

The content SHALL keep the native cursor visible and draw a light-grey ring around it inside the mirrored content on every slide. The ring SHALL stay centred on the pointer, increase in diameter with pointer speed, decrease in stroke width with speed, hide when outside the content, and remain below the quadrant backdrop-filter panels so quadrant tints also colour it.

#### Scenario: Native cursor remains

- **WHEN** any slide is active
- **THEN** the browser's native cursor is visible over the content
- **AND** the custom ring is drawn around the same pointer position
- **AND** the ring does not intercept pointer events

#### Scenario: Ring on every slide

- **WHEN** the deck moves between the cover, quadrant, ranking, work detail, and closing slides with the pointer inside the content
- **THEN** the ring stays visible at the pointer on the new slide
- **AND** only the quadrant slide applies quadrant hover states

#### Scenario: Speed-reactive ring

- **WHEN** the pointer is still or moving slowly
- **THEN** the ring has its smallest diameter and thickest stroke
- **WHEN** the pointer moves quickly
- **THEN** the ring's diameter grows and its stroke becomes thinner
- **AND** both values ease back to their resting values after the pointer stops

#### Scenario: Pointer leaves the content

- **WHEN** the pointer exits the content rectangle, enters the paging controls, or the boot layer is active
- **THEN** the custom ring and all quadrant hover states are hidden
- **AND** the native cursor remains available outside the content

#### Scenario: Centre mark

- **WHEN** the pointer is over the centre `镜` mark or its invisible dead zone
- **THEN** no quadrant is marked as hovered
- **AND** the custom ring remains below the centre mark
- **AND** the native cursor remains visible

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
