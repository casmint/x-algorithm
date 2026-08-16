# Art Direction

One direction for the whole diagram suite, not a menu. This document describes the
aesthetic and composition system; `../VISUAL_LANGUAGE.md` remains the semantic rulebook
(what shapes and arrows *mean*) and this file never redefines that meaning — it only
specifies how it should look, in enough detail that a different implementer could execute
D1–D4 identically from this document alone.

## The direction: Field Atlas

**Name:** Field Atlas — the visual character of a technical field guide or a transit
authority's system map, not a startup architecture diagram.

**One-sentence description:** ink-on-paper technical cartography — orthogonal routing,
a restrained two-hue-family palette per system category, a hatch texture reserved
exclusively for the unknown, and two typefaces that keep "what the system is called" and
"what it means in plain language" visually distinct at every label.

**Why this direction, in three sentences:** The project's central risk isn't that readers
won't understand the pipeline — it's that a simplified picture will make them feel more
certain than the evidence supports. A transit-map register (functional color, no
decoration, every line means exactly one thing) is built for exactly that problem: transit
maps are trusted precisely because they look drawn by someone who cared about being
correct, not persuasive. Editorial technical illustration — muted ink tones, generous
whitespace, restrained accent color — gives that correctness a warmth that a pure
engineering-wiki diagram doesn't have, which matters because this content is for a general
reader, not an on-call engineer.

**What this rules out, explicitly:**
- Gradients, drop shadows, glassmorphism, glossy UI chrome, rounded 3D bevels — anything
  that reads as "app screenshot" rather than "drawn diagram."
- Neon or saturated multi-hue palettes assigning a unique bright color to every service —
  the "AI infographic" failure mode this project exists to avoid.
- Curvy, organic connector lines and free-floating icon clusters — the "startup
  flowchart" failure mode.
- All-caps everywhere, heavy iconography standing in for words, decorative arrowheads.

### How it holds up across contexts

- **Desktop article width:** full composition, all three visual-weight tiers (see each
  production spec's "Hierarchy" section) rendered at once.
- **Mobile width:** the same primary spine, stacked vertically; tertiary-tier detail
  (individual source names, individual non-organic modules) collapses into a single
  summary chip with a "+N more" style label rather than disappearing — nothing gets
  silently dropped, it gets compressed.
- **Standalone landscape diagram:** the "poster" rendering — full detail, widest canvas,
  intended as the version linked to directly or embedded at full size.
- **Cropped social/share card:** one takeaway only, extracted at 2–3x the type scale of
  the full diagram, at most one or two badges. Composition rules for each diagram's card
  crop are specified in its own production spec.
- **Dark/light:** every color is a semantic token (see below), never a literal hex baked
  into a shape. Hue families stay constant between modes; only lightness/saturation shift,
  so a reader who has seen the light-mode version still recognizes the dark-mode version
  as the same system.

---

## Color system

Ten semantic roles. Each role is a **hue family and a behavior**, not a hex value — exact
values are a Phase 2B implementation decision, made once against a real design tool where
contrast can be measured, not guessed here.

A hard rule that applies to all ten: **color is never the only signal.** Every role below
also has a distinct shape or stroke treatment (see "Shape language"), so the system
remains legible in grayscale, in print, and for colorblind readers. Color accelerates
recognition for readers who have it; it's never load-bearing alone.

### 1. Home Mixer / local logic
- **Visual purpose:** marks code that runs in-process, no RPC — the thing most readers
  will assume is a single "algorithm" but is actually the orchestrator's own logic.
- **Hue family:** warm neutral (sand / ochre) — the only "warm" role in the system,
  deliberately, so "this is the home base" reads instantly against everything else's cool
  or muted treatment.
- **Light mode:** low-saturation warm fill, dark ink text directly on the fill.
- **Dark mode:** the same hue family darkened and desaturated further, light ink text —
  never inverted to a *cool* hue; warmth is the identifying signal and must survive the
  mode switch.
- **Accessibility:** fill/text pairing held to 4.5:1 minimum in both modes; the solid-fill
  shape convention (see Shape language) means this role never depends on stroke color
  alone.
- **Appears as:** fill (solid box interior), never stroke-only.

### 2. Remote model / service
- **Visual purpose:** marks an RPC boundary — a separate process Home Mixer calls out to.
- **Hue family:** cool slate-blue.
- **Light mode:** unfilled or near-white interior, slate-blue double-ruled stroke (see
  Shape language).
- **Dark mode:** unfilled or near-black interior, lightened slate-blue stroke for
  sufficient contrast against a dark background.
- **Accessibility:** relies on the double-ruled stroke shape, not fill, so it stays legible
  even where fill color would fail contrast at small sizes.
- **Appears as:** stroke only, plus badge (LOCAL/REMOTE badges reinforce this role at a
  glance — see Badges).

### 3. Retrieval
- **Visual purpose:** marks anything whose job is finding candidates, not judging them.
- **Hue family:** teal/cyan.
- **Light mode:** light teal fill or teal accent stroke on cards within the retrieval
  cluster.
- **Dark mode:** desaturated teal, same hue.
- **Accessibility:** paired with the "candidate pool" stacked-card shape wherever a list of
  results appears, so shape confirms the role independent of hue.
- **Appears as:** fill on retrieval-source cards, accent stroke on the candidate-pool
  shape.

### 4. Ranking / score
- **Visual purpose:** marks anything that transforms a prediction into a number or reorders
  candidates by one.
- **Hue family:** violet/indigo.
- **Light mode:** light violet fill on the transform node itself; violet-tinted pills for
  the values in transit (see Shape language, "score/prediction transform").
- **Dark mode:** desaturated violet, same hue.
- **Accessibility:** the pill shape (vs. box shape) is this role's non-color signal —
  values-in-transit are never boxes.
- **Appears as:** fill on scorer nodes, fill on prediction/score pills, accent on related
  arrows.

### 5. Visibility / policy
- **Visual purpose:** marks a decision point with a fixed, named set of outcomes — this
  role should read as "consequential" wherever it appears, since it's the project's
  highest-myth-risk boundary.
- **Hue family:** warm red-orange, reserved *exclusively* for policy-gate shapes (the
  hexagon — see Shape language). No other role may borrow this hue family, even at low
  saturation, so a reader who has learned "orange hexagon = a real decision happens here"
  never has that association diluted.
- **Light mode:** unfilled hexagon, red-orange stroke; outcome labels (Allow / Interstitial
  / Drop) in ink, not colored text — the shape carries the weight, not colored typography.
- **Dark mode:** lightened red-orange stroke for contrast; same unfilled treatment.
- **Accessibility:** never the sole indicator of Drop vs. Allow — those outcomes also get
  distinct terminal shapes (a filled dot for Allow-continues, a warning-triangle glyph for
  Interstitial, an X-in-circle for Drop), so color-blind readers get the outcome from shape
  alone.
- **Appears as:** stroke only (hexagon), accent on the three outcome arrows leaving it.

### 6. Background safety / reputation
- **Visual purpose:** marks the detector/enforcement ecosystem — systems that run
  continuously, independent of any single request, and only leave state behind.
- **Hue family:** muted plum/maroon.
- **Light mode:** dashed-border box (per Shape language), plum stroke, no fill or very
  faint fill.
- **Dark mode:** lightened plum stroke, same dashed treatment.
- **Accessibility:** the dashed border is this role's primary non-color signal, shared with
  role 10 conceptually but never overlapping in the same diagram (background systems and
  ads never co-occur in one diagram, so no collision risk).
- **Appears as:** stroke + dashed border, small accent badge for "BACKGROUND."

### 7. Data / state / cache
- **Visual purpose:** marks a place state persists between requests.
- **Hue family:** cool slate-gray (distinct from role 2's slate-*blue* — gray reads as
  "inert storage," blue reads as "active call").
- **Light mode:** light gray fill inside the cylinder shape.
- **Dark mode:** darker desaturated gray fill, light ink text.
- **Accessibility:** the cylinder shape is unique to this role in the entire system — no
  other role ever uses it, so hue is never required to identify a data store.
- **Appears as:** fill (cylinder interior).

### 8. Uncertain / production-unknown
- **Visual purpose:** marks total absence — something the repository doesn't show at all,
  as opposed to a checked-in default that might differ live.
- **Hue family:** none of its own. This role is a **hatch texture modifier** (45° diagonal
  hairlines) applied on top of whatever role's hue the node already carries, plus a
  question-mark badge. A data store that's also production-unknown keeps its role-7 gray
  and gains the hatch; it doesn't switch to a new color.
- **Light mode:** hairlines in the same ink tone as body text, low opacity, over the
  existing fill.
- **Dark mode:** hairlines in the same light ink tone used for dark-mode text, over the
  existing fill.
- **Accessibility:** texture-based, so it survives grayscale printing and colorblindness
  by construction — this was the deciding reason to make it a texture rather than a hue.
- **Appears as:** fill overlay (hatch) + badge, never a fill by itself.

### 9. Optional / feature-gated
- **Visual purpose:** marks anything off by default or conditionally enabled.
- **Hue family:** none of its own, same logic as role 8 — this is a **stroke modifier**
  (dashed outline) plus a small gate glyph badge, applied on top of a node's existing role
  color.
- **Light/dark mode:** the dash pattern and gate glyph don't change color between modes;
  only the underlying node's own role color does.
- **Accessibility:** dash pattern + glyph, no reliance on hue.
- **Appears as:** stroke modifier + corner badge.

### 10. Ads / non-organic modules
- **Visual purpose:** marks anything inserted after organic ranking is finished — ads, Who
  to Follow, prompts, push-to-home, frames, survey. Deliberately visually separated from
  every ranking/retrieval hue so a reader can see at a glance that these never touched
  Phoenix or RankingScorer.
- **Hue family:** muted gold/amber — warm like role 1, but a distinctly different hue
  (amber vs. sand) and always paired with the "non-organic" badge, so it doesn't get
  mistaken for Home Mixer local logic at a glance.
- **Light mode:** light amber fill on module cards.
- **Dark mode:** desaturated amber, same hue.
- **Accessibility:** module cards in this role always use a distinct card shape (see
  Component Library, "candidate-source card" variant) with a small non-post icon glyph,
  never relying on amber alone.
- **Appears as:** fill on module cards, accent on the "blends" arrows feeding
  BlenderSelector.

---

## Typography / labeling

Two typefaces, used consistently for two different *voices* — this is the system's most
distinctive, least generic choice, and it should never be abandoned diagram-by-diagram.

- **Technical voice (monospace or semi-monospace technical sans):** anything that names a
  real system identifier — component names, codenames, field names. This is "what the
  source code calls it."
- **Editorial voice (humanist sans):** anything narrating meaning for a human reader —
  titles, subtitles, walkthrough copy, annotations. This is "what it means."

A label that mixes both in one line (e.g., "Phoenix — predicts likely reactions") sets the
codename in the technical voice and the subtitle in the editorial voice, in the same line,
so the visual switch itself teaches the reader which part is the proper noun.

| Element | Voice | Treatment |
|---|---|---|
| Diagram title | Editorial | Largest size in the diagram, sentence case (never all-caps), e.g. "Diagram 1 — Full For You pipeline." |
| Section/layer label | Editorial | Small uppercase micro-label, wide letter-spacing, used for grouping containers: "RETRIEVAL," "HOME MIXER — LOCAL LOGIC." |
| Component name | Technical | Set in the technical voice at all times, including first appearance: "RankingScorer," "Phoenix," "Gizmoduck." |
| Human-language subtitle | Editorial | One line max, sentence case, smaller than the component name, directly beneath or beside it: "predicts likely reactions." |
| Technical/codename label (standalone) | Technical | Same treatment as component name; used when a diagram references a term after its first full introduction. |
| Uncertainty badge | Technical | Smallest allowed size, uppercase, sits inside a hatched tag (role 8 treatment): "PRODUCTION UNKNOWN." |
| Default/reference badge | Technical | Same size class as the uncertainty badge, inside a plain outlined tag, not hatched: "CHECKED-IN DEFAULT." |
| Warning callout | Editorial | Bold, one size class larger than body copy, inside a bordered callout with the single strongest ink weight anywhere in the diagram — reserved for genuinely critical corrections (D3's weight-ratio warning is the canonical example), never used more than once per diagram, so it stays rare enough to work. |
| Annotation / note | Editorial | Italic, smallest editorial size, muted ink tone — asides like "cannot affect this response." |

**Naming rule (inherited from `../VISUAL_LANGUAGE.md`, unchanged):** on first appearance,
human name before codename — "Visibility Filtering (VF)," "RankingScorer (turns
predictions into one score)." Codename alone is fine after that. Never invent a friendlier
name for a term the source only calls by its codename.

---

## Shape language

One shape per structural role, applied consistently across all six diagrams. This is the
non-color half of every semantic distinction above.

| Meaning | Shape | Notes |
|---|---|---|
| Home Mixer local component | Rounded rectangle, solid fill | Role-1 color. The only "solid, filled, ordinary box" in the system — its plainness is the point. |
| Remote service | Rounded rectangle, **double-ruled border** (two parallel strokes, small gap between them) | Reads as a border crossing / customs checkpoint — reinforces "this is an RPC hop," not just a stylistic variant of the local-component box. |
| Background / asynchronous process | Rounded rectangle, dashed border | Role-6 color when it's a safety/reputation system; neutral dashed otherwise (e.g., `phoenix-rankall`'s ingestion pipeline). |
| Data store / state | Cylinder | Unique to this role — never reused for anything else, so it alone is sufficient to identify "persistent state." |
| Filter / policy decision gate | **Hexagon**, not diamond | A diamond reads as generic BPMN/flowchart; a hexagon reads more like a schematic junction box, closer to the transit-map register. Reserved for Allow/Interstitial/Drop-style fixed-outcome decisions. |
| Candidate pool / list | Stacked, overlapping rounded cards (three, offset) | Represents "many unordered items," distinct from any single-component box. |
| Score / prediction transform (value in transit) | Pill / capsule, small, riding along its arrow rather than sitting as a standalone node | A prediction *vector* (Phoenix's ~24 outputs) renders as a small cluster of pills; a scalar (RankingScorer's output) renders as one larger pill; VMRanker's result renders as that same pill either kept (filled) or hollowed to an outline labeled "0" — this is the concrete fix for D3's three-different-values problem (see D3 spec). |
| Optional / gated stage | Any base shape + dashed outline modifier + small corner gate glyph | Modifier, not a new shape — a gated remote service is still a double-ruled rectangle, just dashed. |
| Unknown / external boundary | Any base shape + 45° hatch fill + question-mark badge | Modifier, not a new shape, per the color system's role-8 rule. |
| Non-organic module card (ads/WTF/prompts/etc.) | Rounded rectangle with a clipped corner (one corner cut at 45°) | Distinct silhouette from the plain rounded-rectangle local component, visible even in a monochrome thumbnail. |

Arrowheads: an open chevron (`>`), never a filled solid triangle — filled triangles are the
single most "PowerPoint" visual tell in flowchart-style diagrams, and this system avoids
that register deliberately.

---

## Arrow vocabulary

Built directly on top of `../VISUAL_LANGUAGE.md`'s flow types and arrow-label verbs — this
section adds weight, style, and color, not new meaning.

| Arrow | Line treatment | Used for |
|---|---|---|
| Primary candidate/feed flow | Solid, thick (heaviest line weight in the system) | The path an actual candidate post travels: retrieval → hydration → filters → scoring → visibility → response. |
| Request / call | Solid, thin | A single-value RPC: a query, a scoring request. |
| Metadata / context (side-entry) | Dotted, thin | Hydration-style enrichment entering the main flow from the side — follow-graph state, engagement counts. |
| Optional / gated path | Dashed, same weight as the request/call arrow it modifies | A conditionally-active path: a disabled-by-default source, DPP if the server flag is on. |
| Label-writing arrow ("writes label") | Solid, thin, role-6 (background safety) color | A detector or enforcement system persisting a label or account state. |
| State-read arrow ("reads state") | Dotted, role-2 (remote service) or role-7 (data store) color depending on which end is read | A consumer pulling previously-written labels or state. |
| Blends (BlenderSelector inserting non-post items) | Solid, thin, role-10 (ads/non-organic) color | Every arrow feeding into or out of BlenderSelector for non-organic modules specifically. |

Every arrow keeps a verb label from `../VISUAL_LANGUAGE.md`'s vocabulary
(retrieves/predicts/scores/filters/queries/writes label/reads state/blends). An arrow with
no verb that fits is a sign two relationships are being drawn as one — split it, per the
existing rule; this phase found and fixed exactly one such case (Diagram 05's
`BDSM → BDSMENF` arrow — see this directory's `README.md`).

---

## Badges

Compact, reusable, and used sparingly — a diagram covered in stickers defeats its own
purpose. Each badge is a small rounded tag in the **technical voice**, rendered in neutral
ink (never a role's semantic hue), so badges read as structural metadata layered on top of
the color system rather than competing with it.

| Badge | Text | Placement | When to use |
|---|---|---|---|
| Checked-in default | `CHECKED-IN DEFAULT` | Attached to the specific number itself, not the whole node | Any node or arrow carrying a specific weight, threshold, or percentage. Required, no exceptions — see `../diagrams/README.md`. |
| Shipped reference | `SHIPPED REFERENCE` | Corner of the node | A model/config/path the repository's own tooling uses but that isn't confirmed as what production runs (e.g., the two-tower retrieval architecture). |
| Optional | small gate glyph, no text needed at full size; `OPTIONAL` at reduced/mobile sizes where the dashed stroke alone might not read | Corner of the node | Anything off by default or conditionally enabled. |
| Production unknown | `?` glyph inline, `PRODUCTION UNKNOWN` at full size | Corner of the node, paired with the hatch fill | Total repository silence — a checkpoint, a live threshold, a live cluster binding. |
| Background | small dashed-square glyph; `BACKGROUND` at full size | Corner of the node | Reinforces the dashed-border shape for background/async systems where a reader might otherwise assume synchronous. |
| Request-time | small clock-tick glyph; `REQUEST-TIME` at full size | Corner of the node | Used specifically where a diagram needs to contrast a request-time step against an adjacent background step (D2's two time-zones is the primary use case). |
| Local | — (the role-1 solid-fill shape already carries this; badge reserved for cases where a reader might not see the containing boundary, e.g. a cropped social card) | Corner of the node | Sparingly — mainly for crops that lose the Home Mixer container boundary. |
| Remote | — (the role-2 double-ruled shape already carries this; same crop exception as Local) | Corner of the node | Same as Local. |

**Discipline rule:** if a diagram needs more than three distinct badge types active at once
outside of D5 (which is explicitly the densest, most codename-heavy diagram in the suite),
that's a sign the diagram is trying to carry too much caveat weight in one image — push
detail to a companion table instead of adding a fourth badge.
