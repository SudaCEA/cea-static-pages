# gamejam Specification

## Purpose

Define the public static page set for the GameJam 2026 site and the runtime, visual, and build behavior of the `mirror-2610` page.

## Requirements

### Requirement: Published page set

The site SHALL publish a Material 3 directory page at `/`, a mirror homepage at `/mirror-2610/`, and a diagnostic lab at `/mirror-2610/mirror-lab.html`.

The directory page SHALL list `MIRROR / 2610` as its only page entry and SHALL NOT list the mirror lab.

#### Scenario: Directory lists only the public page

- **WHEN** a visitor opens `/`
- **THEN** the page displays one page card linking to `./mirror-2610/`
- **AND** the page contains no link or label for the mirror lab

#### Scenario: Lab remains directly addressable

- **WHEN** a visitor opens `/mirror-2610/mirror-lab.html` directly
- **THEN** the diagnostic lab loads
- **AND** it is still absent from the directory page

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

### Requirement: Content sizing

The content region SHALL target 72% of the stage width and 72% of the stage height.

The actual CSS content size SHALL remain within 1 CSS pixel of the target after device-pixel snapping.

#### Scenario: Default desktop size

- **WHEN** the page is viewed at 1440×900 CSS pixels
- **THEN** the content target is `1036.8 × 648`
- **AND** the rendered CSS content size is `1036 × 648`

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

### Requirement: Static build integration

The gamejam page SHALL build through the repository build entry into `dist/gamejam/`.

The build SHALL include the directory page, both `mirror-2610` pages, shared effects, and three runtime assets, and SHALL exclude source-only files.

#### Scenario: Clean build

- **WHEN** `python build.py gamejam --clean --strict` runs
- **THEN** the build succeeds
- **AND** `dist/gamejam/` contains the root index, both mirror-2610 pages, `js/effects/`, and `libs/three/`
- **AND** it contains no `tools/`, `page.toml`, `build.py`, or `libs/three/src/` paths

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

### Requirement: Floating surface panel

The page SHALL provide a floating panel outside the mirror stage. It SHALL start collapsed in the bottom-right corner and open on demand.

The panel SHALL adjust particle colour, centre colour, cover bottom-rule height, and the sideview slot's vertical translation. The cover content-to-rule gap SHALL remain fixed at 32px and the text translation at 0. Feather SHALL remain fixed at 72px. It SHALL show backend/layout sizes and provide `Copy config`, `Reset`, `localStorage`, and a collapse toggle.

#### Scenario: Starts collapsed

- **WHEN** the page first loads
- **THEN** the tuning panel is collapsed and shows only its header
- **AND** it does not overlap the top paging controls
- **WHEN** the header toggle is activated
- **THEN** the panel opens with its controls

#### Scenario: Surface colours change live

- **WHEN** the particle colour or centre colour control changes
- **THEN** the content field and mirror root update without rebuilding the mirror

#### Scenario: Cover spacing changes live

- **WHEN** the line or image-Y control changes
- **THEN** the bottom-rule height or the sideview translation updates
- **AND** the content-to-rule gap stays `32px` and the text lockup stays at `0` vertical translation
- **AND** image translate moves only the sideview slot
- **AND** the sideview stroke stays fixed at 2px

#### Scenario: Fixed settings are not editable

- **WHEN** the panel is inspected
- **THEN** it contains no fade, blur, WebGL scale, SVG map, feather, cover-gap, or text-translate controls
- **AND** it shows the fixed feather of `72`, cover gap of `32px`, and text translation of `0px`
- **AND** `Copy config` reports the fixed backend values, deck state, cover bottom-rule/gap/translations, parallax depths, and quadrant filter/pointer settings

#### Scenario: Feather is fixed

- **WHEN** either backend is active
- **THEN** its filter feather is `72`
- **AND** no control can change it

#### Scenario: Reset restores defaults

- **WHEN** the reset action is used
- **THEN** the adjustable colours, bottom-rule height, and image translation return to defaults
- **AND** the fixed cover gap remains `32px` and the fixed text translation remains `0px`
- **AND** the active mirror receives the fixed feather `72` and the fixed backend options
- **AND** the content field receives the default centre and particle colours
- **AND** the saved tuning value is replaced with defaults

#### Scenario: Tuning persists

- **WHEN** a visitor reloads the page after changing panel values
- **THEN** the saved colours, bottom-rule height, and image translation are restored
- **AND** the cover gap is still `32px` and the text translation is still `0px`
- **AND** the mirror is created with the fixed feather `72`
- **AND** the content field starts with those values

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

The project SHALL provide a shared parallax module that reads each layer's `data-parallax` depth, updates only layer transforms, settles to idle, and cleans up on destroy. `mirror-2610` SHALL mount it only on the quadrant slide, with distinct depths for titles, details, and the centre mark, and SHALL scale its displacement down on narrow viewports.

#### Scenario: Depth declaration

- **WHEN** the module is initialized with `data-parallax` layers
- **THEN** each layer's depth is read from its attribute
- **AND** a missing or invalid depth leaves that layer fixed

#### Scenario: Quadrant depth layers

- **WHEN** the quadrant slide is inspected
- **THEN** its titles, details, and centre mark have at least three distinct `data-parallax` depths
- **AND** the transforms are applied only to text inside the quadrant slide
- **AND** the filter panels and rules do not translate

#### Scenario: Module cleanup

- **WHEN** the parallax instance is destroyed
- **THEN** pointer, visibility, and motion listeners are removed
- **AND** layer transforms are cleared
- **AND** no parallax frames are scheduled afterwards

### Requirement: Slide deck content

The content area SHALL present four mirrored slides: a cover, a quadrant page, a mechanism page, and an info page. Exactly one slide SHALL be active. Each slide SHALL contain non-empty editorial copy and SHALL live inside the mirrored content subtree. The quadrant slide SHALL use an enlarged serif hierarchy with titles and the centre mark set substantially larger than the detail copy.

#### Scenario: Four content slides

- **WHEN** the content is inspected
- **THEN** it contains four slides with non-empty editorial copy
- **AND** the cover presents `CEA GameJam`, `2026.10`, and `参赛作品展示`
- **AND** the remaining slides cover the quadrant page, `02 / Mechanism`, and `03 / Info`

#### Scenario: Quadrant page structure

- **WHEN** the quadrant slide is active
- **THEN** it shows a 3px centred cross, a free-standing `镜` at the origin, and four copy groups in the quadrants
- **AND** each copy group and the centre mark have no visible outer border or background
- **AND** the four serif titles read `时间`, `主题`, `限制`, and `评分`
- **AND** all titles are centred
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
- **AND** the bottom-right shows a blank triangular `ellia / sideview` placeholder with a 2px outline
- **AND** the text lockup and sideview slot are bottom aligned
- **AND** the brand/date line, the title, and the two columns have breathing room rather than sitting flush
- **AND** a black rule (3px by default) spans the content bottom below the lockup and placeholder
- **AND** the rule sits `32px` below the lowest cover content

#### Scenario: Cover fade order

- **WHEN** the cover enters or leaves
- **THEN** the brand fades first, the date second, the exhibition title third, and the sideview placeholder fourth
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

The deck SHALL contain two solid absolute rules outside the slide fade groups, clipped by the content overflow. They SHALL overlap into the cover bottom rule and rotate into the quadrant page's centred cross. Separate quadrant rule elements SHALL NOT remain.

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

#### Scenario: Rule transition

- **WHEN** the deck moves from the cover to the quadrant slide
- **THEN** the rules transition to the cross positions with rotation
- **AND** the transition starts with the slide transition
- **AND** each rule is longer than the content diagonal so its ends stay clipped
- **WHEN** the deck returns to the cover
- **THEN** the rules transition back to the overlapping bottom rule

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

- **WHEN** the deck moves between the cover, quadrant, mechanism, and info slides with the pointer inside the content
- **THEN** the ring stays visible at the pointer on the new slide
- **AND** only the quadrant slide applies quadrant hover states

#### Scenario: Speed-reactive ring

- **WHEN** the pointer is still or moving slowly
- **THEN** the ring has its smallest diameter and thickest stroke
- **WHEN** the pointer moves quickly
- **THEN** the ring's diameter grows and its stroke becomes thinner
- **AND** both values ease back to their resting values after the pointer stops

#### Scenario: Pointer leaves the content

- **WHEN** the pointer exits the content rectangle, enters the tuner or paging controls, or the boot layer is active
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
