# Field Atlas — implementation

Phase 2B.1. This directory turns `../diagram-design/ART_DIRECTION.md` and
`../diagram-design/COMPONENT_LIBRARY.md` into a real, rendered visual system,
and produces the first actual diagram asset: **D4 — Ranking vs. Visibility
Filtering**.

Nothing here reopens diagram semantics. Every shape, color, and word traces
back to `../diagram-design/D4_PRODUCTION_SPEC.md`, `../diagrams/04-ranking-vs-visibility.md`,
`../CLAIM_BANK.md`, and `../EDITORIAL_RULES.md`. Where this implementation had
to make a call the specs left open, that call and its reasoning are recorded
below rather than silently baked into the SVG.

**Production order: D4 → D1 → D2 → D3.** D4 is done (this phase). D1 has
**not** started — do not treat anything in this directory as a template
already proven at D1's scale (fifteen stages, three hierarchy tiers) until it
actually gets built there.

---

## Directory structure

```
assets/
├── README.md                  — this file
├── field-atlas.css            — canonical design tokens (single source of truth)
├── field-atlas.svgdefs.svg    — reusable SVG defs reference (arrow markers, hatch pattern)
├── preview/
│   └── index.html             — local QA harness, all four render targets side by side
├── src/                       — hand-authored, editable SVG sources
│   ├── d4-ranking-vs-visibility.svg         (desktop, light — canonical)
│   ├── d4-ranking-vs-visibility-dark.svg    (desktop, dark)
│   ├── d4-ranking-vs-visibility-mobile.svg  (mobile, vertical)
│   └── d4-ranking-vs-visibility-social.svg  (social/share card)
├── exports/                   — generated output only, never hand-edited
│   ├── d4-ranking-vs-visibility.svg   (copy of the canonical light source)
│   ├── d4-ranking-vs-visibility.png
│   ├── d4-ranking-vs-visibility-dark.png
│   ├── d4-ranking-vs-visibility-mobile.png
│   └── d4-ranking-vs-visibility-social.png
└── tools/
    ├── render.sh                 — reproducible SVG → PNG export (headless Chrome)
    └── sync-svg-styles.py        — injects field-atlas.css's shared tokens into every managed SVG
```

`src/` is source. `exports/` is output. Never hand-edit a file in `exports/`
— re-run `tools/render.sh` instead. Within `src/`, never hand-edit the
generated block inside a managed SVG's `<style id="field-atlas-shared">`
— see "Editing shared tokens" below.

---

## Why hand-authored SVG, not Mermaid/canvas/image generation

Per the phase brief: text must be exact, shapes carry semantic meaning
(a hexagon means something specific — see `../diagram-design/COMPONENT_LIBRARY.md`
item 6), arrows must route precisely, and future diagrams need to reuse the
same components. Mermaid's layout engine doesn't give the control this
system's shape language requires (a real elongated hexagon, orthogonal fork
routing, distinct terminal glyphs); canvas/raster drawing and image
generation aren't editable; screenshots of HTML boxes aren't diagrams. Plain
hand-authored SVG plus a shared CSS token file, rendered with vanilla
HTML/JS tooling only for export, is the whole implementation.

## Why each SVG is self-contained (no external stylesheet link)

`field-atlas.css` is the **single canonical source of truth** for every
shared token value. But each SVG in `src/` carries its own inline copy of
the tokens it needs, rather than `<link>`-ing `field-atlas.css` externally
at render time. Reason: these SVGs need to work as a plain
`<img src="...">`, convert cleanly to PNG via headless Chrome, and be
droppable into any future article page — all contexts where an external
stylesheet reference from inside an SVG is unreliable (image contexts
generally don't fetch external CSS for security reasons). Self-contained
means portable.

### Editing shared tokens

The inline copy is **generated, not hand-maintained.** Each managed SVG
carries two separate `<style>` blocks with a deliberately obvious split:

- `<style id="field-atlas-shared">` — generated verbatim from
  `field-atlas.css`, wrapped in `BEGIN/END GENERATED` comment markers plus a
  provenance hash. **Never hand-edit this block** — edit is silently undone
  the next time anyone runs the sync script, and in the meantime it's out of
  sync with its own stated source.
- `<style id="diagram-local-styles">` — hand-authored, specific to that
  diagram/variant (font sizes, shape classes like `.funnel-shape` or
  `.vf-hex`, arrow routing styles). This is exactly the CSS a human should be
  editing directly.

Workflow:

```
1. edit field-atlas.css              (the only file where token VALUES live)
2. python3 tools/sync-svg-styles.py   (regenerates every managed SVG's shared block)
3. python3 tools/sync-svg-styles.py --check   (verify — exits nonzero if anything's stale)
4. tools/render.sh                    (re-export PNGs; this also re-runs step 2 automatically)
```

`tools/sync-svg-styles.py` (Python 3 standard library only, no dependencies)
finds every SVG under `src/` that contains a
`<style id="field-atlas-shared">` block — that marker is the only thing that
makes an SVG "managed," so a new D1/D2/D3 file participates automatically
the moment it includes one; there's no separate list to maintain. It then
replaces that block's contents with the current canonical CSS, deterministically
and idempotently (running it twice produces no second diff). `--check` makes
no changes and exits nonzero if any managed SVG is stale — useful as a CI/
pre-commit gate once this repo has one.

`tools/render.sh` always syncs before rendering (per the invariant below), so
exports can never be produced from a stale token block silently.

```
CHANGE A SHARED TOKEN ONCE
         ↓
  field-atlas.css
         ↓
  tools/sync-svg-styles.py
         ↓
every managed SVG's generated block matches, byte for byte
```

### Light/dark handling

`field-atlas.css`'s shared region has exactly one canonical representation
of both modes — no duplicated dark block anywhere:

```css
svg { /* light tokens, the implicit default */ }
.theme-dark { /* only the dark-mode deltas */ }
```

A dark SVG variant opts in by adding `class="theme-dark"` to its own root
`<svg>` element (see `src/d4-ranking-vs-visibility-dark.svg`'s opening tag);
everything else about that file — geometry, diagram-local styles — is
otherwise identical to its light counterpart. The base rule intentionally
targets the `svg` tag rather than `:root`: `tools/render.sh` screenshots each
SVG after wrapping it in a plain HTML document for headless Chrome, which
makes `:root` mean the *HTML* element, not the embedded `<svg>` — a real bug
caught during this refactor (see "What changed after real rendering" below).
A tag selector matches the actual `<svg>` element correctly whether the file
is ever opened standalone or embedded.

### For a future D1/D2/D3 SVG: how to opt in

1. Add two style blocks in the same place the D4 files have them: an empty
   placeholder `<style id="field-atlas-shared"></style>` and a
   `<style id="diagram-local-styles">` with that diagram's own classes.
2. For a dark variant, add `class="theme-dark"` to the root `<svg>` tag.
3. Run `python3 tools/sync-svg-styles.py` — the new file is discovered and
   populated automatically (no manifest edit required).
4. Write diagram-specific CSS only in the `diagram-local-styles` block. If a
   new *shared* token or cross-cutting base rule is needed (a new role color,
   for instance), add it to `field-atlas.css`'s SVG-SHARED region instead of
   inlining it locally, then re-sync.

## Why two typefaces stay as CSS font stacks, never bundled files

Per the phase brief: no font binaries in this repository. `--font-technical`
resolves to a monospace system stack (`ui-monospace, SFMono-Regular, Menlo,
Monaco, Consolas, "Liberation Mono", monospace`); `--font-editorial` resolves
to a humanist sans stack (`Inter, ui-sans-serif, system-ui, -apple-system,
BlinkMacSystemFont, "Segoe UI", sans-serif`). If Inter isn't installed, the
fallback chain still lands on a clean system sans — verified visually in this
phase's renders (see "Visual QA" below), which were produced on a machine
without Inter installed, so what's committed already reflects the no-Inter
fallback appearance, not a best case.

---

## Design tokens (Part 1)

Full canonical definitions live in `field-atlas.css`. Summary:

| Token group | Light | Dark | Used in D4? |
|---|---|---|---|
| Background / Paper / Ink / Muted ink / Rule | `#f6f2ea` / `#fffdf8` / `#2b241c` / `#6f6656` / `#d9d2c2` | `#17140f` / `#201c15` / `#f2ede0` / `#b0a68f` / `#3a3327` | yes |
| Role 1 — Home Mixer (sand/ochre) | fill `#e8d5ad` | fill `#6b5327` | not this diagram |
| Role 2 — Remote service (slate-blue) | stroke `#3f5872` | stroke `#7fa0bf` | not this diagram |
| Role 3 — Retrieval (teal) | fill `#cfe3e0` / stroke `#2f6e68` | fill `#2b4d49` / stroke `#6fb0a8` | not this diagram |
| Role 4 — Ranking/score (violet) | fill `#ddd3ee` / stroke `#5b4a8a` | fill `#4a3d70` / stroke `#a493d1` | **yes** — funnel |
| Role 5 — Visibility/policy (red-orange) | stroke `#b3491f` | stroke `#e2794a` | **yes** — VF hexagon, fork arrows |
| Role 6 — Background safety (plum) | stroke `#7c4a5c` | stroke `#c98fa0` | **yes** — index-time side note |
| Role 7 — Data/state (slate-gray) | fill `#d7d9d6` | fill `#4a4d49` | not this diagram |
| Role 10 — Non-organic (gold/amber) | fill `#ecd9a0` | fill `#b99a4a` | not this diagram |
| Unknown hatch | ink hairlines, 0.16 opacity, over existing fill | same, light-ink hairlines | not this diagram (no production-unknown element in D4) |
| Optional dash | ink-muted dasharray `6 5` | same | not this diagram (no gated path in D4) |

Roles 1, 2, 3, 7, 10, plus the hatch and dash modifiers, are defined now in
`field-atlas.css` specifically so D1–D3 don't have to repaint the palette —
D4 alone only exercises roles 4, 5, and 6.

**Contrast:** every text/fill pairing above was checked against WCAG's
relative-luminance formula before implementation; all pairs clear 4.5:1 in
both modes (role-1 sand/ink in light mode is the tightest at 10.6:1 — still
well clear). See the palette table's role-4 and role-5 pairs specifically,
since those are the two roles D4 actually uses for filled/stroked text
regions.

### Allow / Interstitial / Drop — a deliberate deviation from "give them each a token"

The phase brief's token list names `ALLOW`, `INTERSTITIAL`, `DROP` as if they
were three more hue roles alongside the ten in `ART_DIRECTION.md`. They
aren't, and making them so would violate the art direction's own rule: role
5 (red-orange) is **reserved exclusively for policy-gate shapes**, and no
other role may introduce a new hue for "safe/warn/danger" — `ART_DIRECTION.md`
explicitly requires shape, not color, to carry this distinction, precisely so
the diagram doesn't default to a green/red good/bad reading the source
material never supports (Interstitial isn't "kind of bad," Drop isn't
"unsafe," Allow isn't "approved").

What's implemented instead: `--outcome-allow` is plain ink (the calmest,
least-marked outcome — continuing is not itself a policy consequence).
Interstitial and Drop both resolve through a single `--outcome-policy`
token (itself `var(--role-5-stroke)`), because both are consequences of the
same VF policy gate — the *shape* carries the real distinction (filled dot
vs. outlined warning-triangle vs. filled X-in-circle), not a fourth invented
hue or a separate token per outcome. This reads correctly in grayscale
(verified — see "Visual QA" below) and never implies a red-vs-green safety
judgment.

---

## Reusable SVG component conventions (Part 2)

Established now, for D1–D3 to reuse — not all are exercised by D4 itself
(noted below). Implemented as SVG `<g>` groups with semantic classes/ids
(`.funnel-shape`, `.vf-hex`, `.policy-card`, `.side-note-box`, etc.), not a
component framework — per the phase brief, this is deliberately simple.

| Convention | D4 usage | Class/id pattern |
|---|---|---|
| Title block | ✅ | `#title-block`, `.diagram-title` |
| Section/layer label | — (not needed at D4's flat hierarchy) | `.header-line`, editorial uppercase micro-label style defined but unused here |
| Local process card (Home Mixer, role 1) | — | reserved, see `field-atlas.css` role-1 tokens |
| Remote service card (role 2, double-ruled) | — | reserved, see role-2 tokens |
| Policy hexagon | ✅ | `#vf-gate`, `.vf-hex` |
| Result/terminal state | ✅ | `#allow-outcome`, `#interstitial-outcome`, `#drop-outcome` |
| Warning callout (max-weight, per-diagram-once) | — (D4 doesn't need one; D3 does — see `COMPONENT_LIBRARY.md` item 15) | not implemented here, reserved for D3 |
| Uncertainty badge (`?`, hatched) | — (no production-unknown element in D4) | reserved, pairs with the hatch pattern in `field-atlas.svgdefs.svg` |
| Reference badge (`SHIPPED REFERENCE`) | — | reserved |
| Optional badge | — | reserved |
| Annotation (small italic muted) | ✅ | `.zoom-link`, `.framing-line` |
| Arrow / connector (open chevron, never filled triangle) | ✅ | `.arrow-primary`, `.arrow-policy`, markers in each SVG's `<defs>` |
| Separate-mechanism callout | ✅ | `#index-time-note`, `.side-note-box` (dashed, role-6) |
| Legend item | — (D4's header color-coding substitutes; D2's IN/OON legend will be the first real user) | reserved |
| Zoom-in / see-also marker | ✅ | `.zoom-link` — "— see Diagram 03", "— see Diagrams 02, 05" |

`field-atlas.svgdefs.svg` documents the two reusable `<defs>` primitives
(open-chevron arrowhead markers, the 45° unknown-hatch pattern) as a
copy-paste reference — each SVG still embeds its own copy, for the
self-containment reasons above.

---

## D4 content contract (Part 3) — what's on the diagram and why

Primary spine, matches `../diagram-design/D4_PRODUCTION_SPEC.md`'s "Core
composition" exactly: High-scoring post → Top K → Visibility Filtering (VF)
→ Allow / Interstitial / Drop, one fork, three terminal states. (Originally
labeled "Top 50" — renamed to "Top K" plus a subordinate checked-in-default
annotation after human visual review; see "Correction pass after human
visual review" below.)

**A composition ambiguity in the production spec, resolved:** the spec's
prose says the funnel "forks visibly into two policy lanes... each ending in
the three terminal states," which read literally would mean drawing the
Allow/Interstitial/Drop fork *twice* (once per policy lane) — but the spec's
own ASCII "Core composition" diagram shows exactly one hexagon forking
directly into three outcomes, and its Hierarchy section separately lists the
TimelineHome/TimelineHomeRecommendations comparison as a **secondary,
visually subordinate** element, not a duplicate of the foreground fork. Given
the production spec's explicit priority ("the flattest hierarchy of any
diagram in the suite... readable in one glance") and the phase brief's own
simplified primary-spine ASCII (which also shows one fork), this
implementation draws a single fork with a subordinate comparison strip below
it, not two duplicated forks. This is a rendering-ambiguity resolution, not a
semantic change — no claim on the diagram differs from either reading; it
resolves *only* which parts of the canvas the two truths occupy. Flagging it
here per the phase brief's instruction to report interpretive calls rather
than silently making them.

**Terminal-arrow labeling:** `COMPONENT_LIBRARY.md` item 6 requires "each
outgoing arrow labeled with its exact outcome." Rather than adding a
redundant text label mid-arrow *and* the bold outcome word at each terminal,
this implementation treats the terminal's own bold label (Allow /
Interstitial / Drop, positioned immediately where its arrow ends) as
satisfying that requirement — there is exactly one arrow per terminal, so the
mapping is unambiguous, and this avoids doubling text density in an
already-tight fork. If a future diagram has multiple arrows converging on
fewer labels, this shortcut would not apply there.

**Snapshot reference:** the provenance footer cites `c65aa179` per the phase
brief's supplied snapshot identifier.

---

## Composition (Part 4) — the four render targets

| Target | File | Logical canvas | Notes |
|---|---|---|---|
| A. Desktop/article | `src/d4-ranking-vs-visibility.svg` | 1600×900 | Canonical. Full content: header pairing, primary fork, secondary IN/OON strip, index-time note, provenance footer. |
| B. Dark desktop | `src/d4-ranking-vs-visibility-dark.svg` | 1600×900 | Identical structure to A; only the inline token block differs (see "Why each SVG is self-contained" above). |
| C. Mobile | `src/d4-ranking-vs-visibility-mobile.svg` | 400×948 | Vertical. Same primary spine (post → Top K → VF → fork); three outcomes stay side-by-side in three narrow columns rather than stacking, since they fit at this width without crowding; IN/OON becomes two stacked cards (not side-by-side); index-time note becomes a compact footnote card; header/subtitle copy condensed (see below) without dropping any claim. |
| D. Social/share card | `src/d4-ranking-vs-visibility-social.svg` | 1200×675 | Funnel + fork + header only, per spec — no secondary strip, no index-time note. Carries the one-line headline claim large and a minimal provenance mark. |

**Mobile copy compression, specifically:** the header pairing shortens from
full quoted questions ("Ranking asks: 'How valuable might this be to this
viewer?'") to "Ranking asks: how valuable?" — same claim, no information
dropped, just fewer words, matching the phase brief's own suggested
condensed header form. Outcome subtitles compress similarly (currently "May
still be delivered / with warning/treatment" — see "Correction pass after
human visual review" below for the wording history) while preserving the
one distinction that must never be lost: Interstitial is still delivered,
Drop is removed. Verified this distinction survives at
mobile scale during visual QA.

---

## Export tooling (Part 6)

`tools/render.sh` rasterizes each `src/*.svg` to `exports/*.png` at 2x scale
using headless Chrome (`google-chrome --headless=new`), which was the tool
actually available in this environment (checked first: no `rsvg-convert`, no
Inkscape CLI, no CairoSVG; ImageMagick's `convert` is present but its SVG
delegate does not reliably resolve CSS custom properties inside an inline
`<style>` block, which this system depends on). Chrome was verified to
render the CSS-variable-driven tokens correctly.

`render.sh` always runs `tools/sync-svg-styles.py` first (no flag to skip
it) — exports must never be produced from a stale shared-style block. Sync
failure aborts the render.

```
cd assets/tools
./render.sh
```

This produces all four PNGs plus a copy of the canonical SVG in `exports/`,
overwriting previous output — safe to re-run any time `src/` or
`field-atlas.css` changes. Lossless PNG throughout, no JPEG, per the phase
brief.

---

## Visual QA (Part 7) — what was actually checked

Every export was rendered and visually inspected as an image in this
session, not just validated as source markup. Two iterations on the
canonical desktop SVG:

1. **v1 → v2:** the "— see Diagram 03" zoom-link text sat directly on top of
   the arrow between Top 50 and the VF hexagon, and the dotted connector from
   the index-time note terminated inside the primary flow arrow rather than
   at the funnel's edge. Both fixed by repositioning (zoom-link moved off the
   arrow's centerline; dotted connector re-routed to land on the "High-scoring
   post" shape's corner instead of crossing the arrow).

No other layout defects found after that pass, across all four targets
(desktop light, desktop dark, mobile, social) at their rendered sizes.

**Grayscale test:** performed by converting the rendered desktop-light and
desktop-dark PNGs to grayscale (`convert ... -colorspace Gray`) and
inspecting. **Passed** — the VF hexagon remains recognizable purely by shape,
and Allow/Interstitial/Drop remain unambiguous from their glyphs alone
(filled dot / outlined triangle with exclamation mark / filled circle with
X) with no reliance on color.

**10-second test:** performed by looking at the canonical desktop PNG cold.
All three questions from the phase brief read correctly at a glance: ranking
is visibly not the last step (the spine continues through VF), a
highly-ranked post visibly can still reach Drop, and Allow/Interstitial/Drop
are visibly three distinct shapes with three distinct short labels, not two
flavors of one thing. **Passed.**

**Small-size test (social card):** the first draft of the social card left a
large empty gap between the fork and the footer — fixed by enlarging the
headline claim to two lines at 25px and tightening vertical rhythm. At
typical feed-thumbnail scale the headline claim and the three terminal
glyphs remain the dominant, legible elements.

---

## Accessibility & editability (Parts 8–9)

- Every SVG has a `<title>` and a `<desc>` with a concrete, specific summary
  (not "diagram of a pipeline" — the actual claims, so a screen reader user
  gets the real content).
- All text is real `<text>`/`<tspan>` elements — nothing converted to
  outlines/paths.
- Group and element ids are semantic: `vf-gate`, `allow-outcome`,
  `interstitial-outcome`, `drop-outcome`, `index-time-note`,
  `timeline-home-card`, `timeline-home-recommendations-card`, etc. — no
  `g1837`-style opaque ids anywhere.
- No base64-embedded images, no editor metadata bloat, no enormous
  auto-generated path dumps — every path in these files is a small,
  hand-written coordinate list.
- Every terminal outcome (Allow/Interstitial/Drop) carries a visible text
  label in addition to its glyph — meaning is never encoded by color,
  position, or texture alone.

---

## What changed after real rendering (honesty check)

Two things changed from the initial draft after seeing the actual render
(both cosmetic positioning fixes, documented above under "Visual QA"); no
Field Atlas *convention* (token, shape, component) had to change — the
system as specified in `../diagram-design/ART_DIRECTION.md` and
`COMPONENT_LIBRARY.md` rendered as intended on the first real attempt. The
one interpretive call (single fork vs. duplicated fork, see Part 3 above) was
a composition-ambiguity resolution, not a convention change.

## Maintenance patch: centralizing the shared styles (post-Phase-2B.1)

The four D4 SVGs originally each carried a hand-synchronized copy of the
shared tokens (documented at the time as a known, accepted maintenance cost).
That was fine at four files; it would not have scaled cleanly to D1–D3. This
patch replaced the manual copies with the generated
`<style id="field-atlas-shared">` block described above, sourced from
`field-atlas.css` by `tools/sync-svg-styles.py`.

Building the generator surfaced a real, pre-existing latent bug, not just a
maintenance smell: `field-atlas.css`'s token names (`--outcome-interstitial`,
`--outcome-drop`, `--outcome-drop-fill`) didn't actually match what the
shipped SVGs used (`--outcome-policy`) — the "canonical" file and the real
implementation had already drifted within a single phase. Consolidating to
the single `--outcome-policy` name (documented as the deliberate design
already in `field-atlas.css`'s own comments) fixed that.

Second, and more consequential: the first working version of the generator
used `:root` as the base token selector, matching the pre-refactor files'
own convention. It rendered the light variant correctly but silently broke
two tokens (`--outcome-allow`, `--outcome-policy`) specifically in the *dark*
export — both are defined as a `var()` indirection of another token, and
`tools/render.sh` renders each SVG by embedding it inside a wrapper HTML
document for headless Chrome, which makes `:root` resolve to the wrapper's
`<html>` element rather than the embedded `<svg>`. Since `.theme-dark` is a
class on the `<svg>` element itself, the two elements `:root` and
`.theme-dark` were targeting were no longer the same element, and the
indirected tokens silently fell back to their light-mode values while every
*directly*-referenced token (backgrounds, strokes) still looked correct —
exactly the kind of defect a visual-only spot check can miss. Caught by
pixel-diffing the new dark export against the previously-committed,
already-approved dark PNG (`compare -metric AE`, ImageMagick) rather than by
eye — light/mobile/social all diffed at 0 pixels immediately, dark diffed at
19,274 pixels, which localized cleanly to the fork arrows and terminal
glyphs once visualized. Fixed by switching the base selector from `:root` to
the `svg` type selector, which matches the same physical `<svg>` element
`.theme-dark` targets regardless of whether the file is embedded or opened
standalone. After the fix, all four exports are byte-identical to the
previously-committed, already-QA'd PNGs — this patch changed the maintenance
architecture, not the rendered output.

## Correction pass after human visual review

Field Atlas itself and D4's overall composition were approved as-is. Five
targeted content/wording corrections were made, all in diagram-local markup
— no shared token, shape convention, or component changed:

1. **Top-K epistemic fix.** `Top 50` read as an unconditional architectural
   fact. Renamed the node to `Top K` / "Highest-scoring candidates" (desktop,
   dark, mobile — social never had this node, by original design, and stays
   that way), with a small, visually subordinate checked-in-default
   annotation ("50 in checked-in defaults") beside it — a plain outlined tag
   per `COMPONENT_LIBRARY.md` item 13's badge convention, not a fourth new
   shape. Mobile's first attempt at this annotation collided with the
   primary-flow arrow (the arrow was drawn directly through the centered
   text); fixed the same way the very first implementation pass fixed an
   analogous collision — split into two pieces flanking the arrow rather
   than centered on it.
2. **Interstitial wording.** "Delivered, with a tap-through warning" named
   one specific, universal UI treatment the production spec doesn't actually
   guarantee. Desktop/dark/mobile now read "May still be delivered / with
   warning/treatment"; social (which has no room for two-line subtitles)
   reads "Warning / treatment." Interstitial vs. Drop remains unambiguous
   either way — the glyph (triangle vs. X-circle) already carried that
   distinction, and still does.
3. **Social double arrow.** A leftover artifact from the social crop's
   original simplification (Top K removed, but two arrow segments that used
   to sandwich it were never merged) — two consecutive `arrow-primary`
   paths between "High-scoring post" and the VF hexagon, producing two
   visible arrowheads in a straight line. Merged into one path. Confirmed
   via the pixel-diff below that this was the only structural change to the
   social card beyond the wording edits.
4. **Callout leader-line polish (desktop/dark only, optional).** The
   "SEPARATE MECHANISM" dotted connector previously ended at the
   "High-scoring post" shape's side corner, reading as a branch off the main
   flow. Re-routed to land at the shape's top-center instead — same box
   position, same "not part of the fork" framing, but now reads as
   upstream/before the pipeline starts rather than a mid-flow branch.
5. **Policy wording (optional).** "Out-of-network policy — stricter" →
   "Recommendation/OON policy — broader" on all three variants that show the
   comparison strip (desktop, dark, mobile — social never shows it). Same
   underlying fact (meaningfully more drop rules apply), less room for a
   moral/harshness reading at a glance. The framing line beneath the two
   cards already said "covers more drop cases, not a claim that OON content
   is unsafe" and didn't need to change.

**Verification:** pixel-diffed every export against the prior commit's
already-approved PNGs (`compare -metric AE` + a difference-composite
visualization). All five changes are the *only* pixels that moved in each
file — confirmed visually per file, not assumed. Dimensions unchanged (light/
dark 3200×1800 @ 1600×900 logical, mobile 800×1896 @ 400×948 logical, social
2400×1350 @ 1200×675 logical). `sync-svg-styles.py --check` passes; no
`field-atlas.css` token changed, so this pass required no re-sync beyond
confirming the shared block was already current. D4 stays REVIEWED, not
promoted to FINAL, pending the next human pass.

## Accessibility-copy parity check (final pass before sign-off)

The Top-K/Interstitial/policy-wording correction pass above updated the
*visible* diagram but left the accessible `<desc>` text on desktop, dark,
and mobile still reading "the more permissive TimelineHome... or the
stricter TimelineHomeRecommendations" — the exact framing the correction
pass had just removed from the visible copy for its moral/harshness
undertone. A screen reader user would have gotten a materially different
(and less careful) claim than a sighted reader looking at the diagram.

Fixed by rewording the affected `<desc>` sentence to the same "broader set
of drop rules" framing now used on-diagram:

> Which policy applies depends on the post's relationship to the viewer.
> TimelineHomeRecommendations, used for recommendation/OON contexts,
> includes a broader set of drop rules than TimelineHome.

The existing "both policies can produce all three outcomes" clause (desktop
and dark only — mobile's `<desc>` never had it) was preserved unchanged: it's
an already-approved claim, stated explicitly in
`../diagram-design/D4_PRODUCTION_SPEC.md`'s "What this must NOT imply"
section ("both policies produce all three outcomes; OON is stricter, not
maximally restrictive"). Social's `<desc>` never mentioned TimelineHome at
all (it doesn't show the comparison strip), so it needed no change.

Also renamed the `.top50-label` CSS class to `.top-k-label` in the three
files that carry it (desktop, dark, mobile — social has no Top K node) — a
pure identifier rename (same font-size/weight, same two call sites per
file: the class definition and its one usage), left over from the "Top 50"
→ "Top K" content change two passes ago.

Both changes are non-visual by construction (accessibility text and an
internal CSS class name respectively) — verified by pixel-diffing every
export against the immediately prior commit's PNGs: all four render at
**0 differing pixels**, confirming neither change touched a single rendered
pixel. D4 is now FINAL.
