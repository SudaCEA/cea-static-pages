# Tasks

## 1. Replace placeholders

- [x] 1.1 Remove the `FIELD / SPECIMEN / INDEX / NODE` parallax markup and page-level `createParallax` wiring from `mirror-2610`.
- [x] 1.2 Keep `js/effects/parallax.js` as a reusable module but stop requiring it as a `mirror-2610` runtime file.
- [x] 1.3 Move the slide deck into `#art` so its text and rules are captured by the mirror.
- [x] 1.4 Move the tuning panel to the bottom-right, start it collapsed, and keep it out of the top paging controls.

## 2. Slide content

- [x] 2.1 Add four static slides: cover, about, mechanism, and info, each with eyebrow, title, copy, and footer.
- [x] 2.2 Style the deck with the loading/preflight language: transparent backgrounds, black text and rules, square corners, monospace micro-labels.
- [x] 2.3 Add responsive layouts for the split, steps, and info grid without slide overflow at narrow widths.
- [x] 2.4 Remove the top page-number indicator.

## 3. Navigation and transitions

- [x] 3.1 Add compact 40×34px arrow-only previous/next buttons at the top corners, outside the mirror, with 36×32px mobile sizes.
- [x] 3.2 Implement a shared deck state machine with per-element fade-out and fade-in, active/aria-hidden swaps, and a transition lock.
- [x] 3.3 Add wheel accumulation/threshold/lock while ignoring wheel events over the tuner.
- [x] 3.4 Add Arrow/Page/Home/End keyboard navigation and disabled boundary buttons.
- [x] 3.5 Respect `prefers-reduced-motion` by switching slides immediately with `transition:none`.

## 4. Verification and documentation

- [x] 4.1 Add `tools/probe_deck.py` for structure, mirror participation, compact controls, one active slide, fades, wheel/keyboard, boundaries, and transition locking.
- [x] 4.2 Verify the deck at WebGL and SVG backends, reduced motion, and a 390×844 mobile viewport without overflow.
- [x] 4.3 Update `probe_content_field.py` to accept deck text inside `#art` while retaining canvas, particle, seam, DPR, and fallback checks.
- [x] 4.4 Update `README.md` for slide content, navigation, fades, tuner placement, and test commands.
- [x] 4.5 Run `probe_content_field.py`, `probe_deck.py`, `openspec validate --specs --strict`, and `python build.py gamejam --clean --strict`.

## 5. Staggered fade support

- [x] 5.1 Add `js/effects/fade.js` with `fadeIn`, `fadeOut`, and `resetFade`, reading `data-fade`, `data-fade-in-delay`, and `data-fade-out-delay`.
- [x] 5.2 Animate only opacity through Web Animations and resolve after every element's delay + duration; support cancelled/previous animations safely.
- [x] 5.3 Mark the existing slide elements with different enter/exit delays and drive the deck transition from the module.
- [x] 5.4 Update `Copy config` and deck state with `fadeDuration`, `fadeMode`, and the number of fade items.
- [x] 5.5 Extend `probe_deck.py` to assert distinct in/out delays, staggered mid-transition opacity, completed active opacity, hidden outgoing opacity, and reduced-motion snap.
- [x] 5.6 Update `README.md` for the fade attributes, module, base duration, and the practiced per-element choreography; run the probes, spec validation, and strict build.

## Workflow follow-up

- Review the initial copy and the side-band mirror capture in Chrome Beta before archiving.
- Sync the delta into `gamejam/openspec/specs/gamejam/spec.md` and archive the change when the review is accepted.
- Commit only if the user explicitly asks for a commit.
