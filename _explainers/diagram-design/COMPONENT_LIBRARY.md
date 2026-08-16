# Component Library

Sixteen reusable visual components, built from `ART_DIRECTION.md`'s color/shape/type
system and `../VISUAL_LANGUAGE.md`'s semantics. Every diagram in D1–D4 (and, eventually,
D5–D6) should be assembled from these — a production spec that needs a seventeenth
component is a signal to check whether an existing one actually fits before inventing a
new one.

Each entry: purpose, semantic meaning, visual treatment, an example label, and a misuse to
avoid.

---

### 1. Pipeline stage card

**Purpose:** the generic container for one step in a left-to-right or top-to-bottom
process flow — the base unit most other components specialize.

**Semantic meaning:** "something happens here, in this order relative to its neighbors."
Carries no locality claim (local/remote) by itself — that's added by specializing into
component 2 or 3.

**Visual treatment:** rounded rectangle, editorial-voice title line, optional
technical-voice component-name line beneath it. Connects via the primary candidate-flow
arrow (thick solid) by default.

**Example label:** `Hydration` / "concurrent lookups: block/mute state, follow direction,
engagement counts."

**Misuse to avoid:** don't use this generic card where component 2 or 3 applies —
locality is one of this project's most important distinctions (`CLAIM_BANK.md` #2), and a
generic card silently erases it.

---

### 2. Home Mixer local card

**Purpose:** marks a stage as ordinary code running inside the Home Mixer process, no RPC.

**Semantic meaning:** role 1 (Home Mixer / local logic) from `ART_DIRECTION.md`. Everything
inside the Home Mixer container boundary in D1 uses this component: RankingScorer, the
pre-scoring filters, BlenderSelector, query construction.

**Visual treatment:** rounded rectangle, solid role-1 (warm sand/ochre) fill, dark ink
text directly on the fill, no LOCAL badge needed when it visibly sits inside the Home
Mixer container — add the LOCAL badge only in cropped contexts that lose the container
boundary (see `ART_DIRECTION.md`, Badges table).

**Example label:** `RankingScorer` / "turns predictions into one score — runs locally, no
remote call."

**Misuse to avoid:** never apply this to Phoenix, VMRanker, or Visibility Filtering — this
was a real error in an earlier draft of the master synthesis's own glossary
(`ADVERSARIAL_REVIEW.md` AR-001) and diagrams exist specifically to not repeat it.

---

### 3. Remote service card

**Purpose:** marks a stage as a separate process reached over RPC.

**Semantic meaning:** role 2 (remote model / service). Phoenix (both ranking and
retrieval sides), VMRanker, Visibility Filtering, Thunder, SimClusters, Gizmoduck,
TweetMixer.

**Visual treatment:** rounded rectangle, double-ruled border (role-2 slate-blue stroke,
no or minimal fill), technical-voice component name, editorial-voice subtitle beneath.

**Example label:** `Phoenix` / "predicts likely reactions — a separate service Home Mixer
calls."

**Misuse to avoid:** don't fill this shape solidly — an accidental solid fill on a remote
card visually collapses the local/remote distinction this whole system exists to keep
sharp.

---

### 4. Candidate-source card

**Purpose:** represents one retrieval mechanism contributing posts to the candidate pool.

**Semantic meaning:** a specialization of component 3, always paired with an IN/OON label
and, when applicable, an Optional-path marker (component 11).

**Visual treatment:** remote-service card treatment plus a small compact footer row for
IN/OON status and default-enabled status, so all seven sources in D2 are scannable as a
uniform card grid without reading full prose on each.

**Example label:** `Thunder` / "recent posts from people you follow" · `IN-network` ·
always-on.

**Misuse to avoid:** don't give a disabled-by-default source (TweetMixer,
PhoenixMOESource) the same solid-weight border as an always-on source — pair with the
dashed optional-path modifier every time.

---

### 5. Model card

**Purpose:** represents a prediction- or embedding-producing model specifically, as
opposed to a generic remote service — used where a diagram needs to show the model doing
model-shaped work (predicting, encoding), not just being called.

**Semantic meaning:** a specialization of component 3 for Phoenix's ranking and retrieval
sides, and their internal towers in a future D6 spec.

**Visual treatment:** remote-service card with an internal sub-row for what it outputs,
using score/prediction-transform pills (component 10) to show that output leaving the
card — e.g., a Phoenix model card shows a cluster of small pills labeled with a few
representative action names, not a wall of text.

**Example label:** `Phoenix` / outputs: favorite · reply · report · ... (~24 total,
representative subset shown).

**Misuse to avoid:** never show every one of Phoenix's ~24 predicted heads as individual
pills in a primary composition — that's an explicit "technically true but should be
omitted from primary view" case; show a representative handful and label it as such.

---

### 6. Filter / policy gate

**Purpose:** a branching decision node with a fixed, named set of outcomes.

**Semantic meaning:** role 5 (visibility/policy) — reserved exclusively for genuine
decision points: Visibility Filtering's Allow/Interstitial/Drop, a pre-scoring filter's
keep/remove, `phoenix-rankall`'s admit/exclude.

**Visual treatment:** hexagon, unfilled, role-5 red-orange stroke (per
`ART_DIRECTION.md`'s hard rule that this hue never appears anywhere else). Each outgoing
arrow labeled with its exact outcome, no unlabeled branches ever.

**Example label:** `Visibility Filtering` / Allow / Interstitial / Drop.

**Misuse to avoid:** don't use a hexagon for a simple binary keep/remove pre-scoring filter
if the diagram is trying to stay low-detail — a hexagon signals "this is a real,
named-outcome decision the reader should track," and using it for every minor filter
dilutes that signal. Reserve it for outcomes a reader is meant to remember.

---

### 7. Data / state store

**Purpose:** represents persistent state living between requests.

**Semantic meaning:** role 7. Gizmoduck's account records, Phoenix's post-vector table,
the short-lived candidate cache, the safety-label annotation record.

**Visual treatment:** cylinder, role-7 slate-gray fill — unique shape in the whole system,
so hue is never required to identify it.

**Example label:** `Gizmoduck` (account state) — cylinder, queried live per request (paired
with a REQUEST-TIME badge to distinguish it from a background-written store).

**Misuse to avoid:** don't use the cylinder for a value in transit (a score, a prediction)
— that's component 10's job. A cylinder means "this persists here," not "this is a number
right now."

---

### 8. Background producer

**Purpose:** represents a continuously-running, request-independent system that produces
state for something else to read later.

**Semantic meaning:** role 6. Agatha, BDSM, Grox, Botmaker/Scarecrow,
abuse-enforcement-service, `phoenix-rankall`'s ingestion pipeline.

**Visual treatment:** dashed-border rounded rectangle, role-6 muted-plum stroke (when a
safety/reputation system) or neutral dashed (when a non-safety background system, e.g.
`phoenix-rankall` ingestion), paired with a BACKGROUND badge wherever a reader might
otherwise assume a synchronous, per-request step.

**Example label:** `Scarecrow` / "spam/abuse rule engine — runs continuously, not
per-request."

**Misuse to avoid:** never apply this to Gizmoduck — Gizmoduck is queried live and
synchronously per request, the opposite of this component's meaning, and this exact
miscategorization was a corrected error in earlier internal drafts
(`CLAIM_BANK.md` #4).

---

### 9. Candidate pool

**Purpose:** represents an unordered collection of candidate posts at a specific pipeline
stage.

**Semantic meaning:** the pooled, concatenated result of concurrent retrieval
contributions (`CLAIM_BANK.md` #58), or the top-K survivors of a scoring/filtering stage.

**Visual treatment:** three overlapping, offset rounded cards, role-3 (retrieval) teal
accent when it's the raw retrieval pool, neutral ink when it's a later-stage pool (e.g.,
Top 50).

**Example label:** `Candidate pool` / "concurrent contributions, simply concatenated — no
priority order."

**Misuse to avoid:** don't imply ordering within this shape (e.g., don't stack the cards
in a way that reads as "first card = first priority") — the whole point of this shape is
"many, unordered."

---

### 10. Score / prediction transform

**Purpose:** represents a value — a prediction, a score, a similarity number — moving
between stages, as distinct from the candidate post itself moving.

**Semantic meaning:** role 4 (ranking/score) for scores and predictions; distinguishes
three specific quantities per `CLAIM_BANK.md` #57 — a retrieval similarity score, a
Phoenix prediction, and a RankingScorer score are three different numbers.

**Visual treatment:** small pill/capsule riding along its arrow. A **prediction vector**
(Phoenix's output) renders as a small cluster of pills. A **scalar score**
(RankingScorer's output) renders as one larger pill. A **selection result** (VMRanker's
output) renders as that same pill either filled (kept, exact original score) or hollow
with a "0" label (not selected) — never a new color, since DPP doesn't produce a new
number, only a keep/zero decision (`CLAIM_BANK.md` #27).

**Example label:** cluster of small pills labeled "favorite · reply · report · ..." →
single pill labeled "RankingScorer score" → same pill, filled or hollow-zero.

**Misuse to avoid:** never draw all three of these value-types as the same shape — that's
precisely the "three different values" collapse `ART_DIRECTION.md` and D3's spec exist to
prevent. Never let a scalar and a vector look interchangeable.

---

### 11. Optional-path marker

**Purpose:** flags any path or node that only runs under specific conditions.

**Semantic meaning:** role 9. A disabled-by-default retrieval source, DPP selection when
the server flag is on, an interstitial-only branch.

**Visual treatment:** modifier, not a standalone shape — dashed stroke applied to whatever
base component it's marking, plus a small corner gate glyph; the connecting arrow is also
dashed (`ART_DIRECTION.md` arrow vocabulary).

**Example label:** `PhoenixMOESource` (dashed remote-service card) / "off by default."

**Misuse to avoid:** don't apply the dashed modifier to a stage that's sequential-but-rare
— reserve it strictly for genuinely conditional/feature-gated paths, not for "this doesn't
always produce output" (e.g., SimClusters with zero engagement signals still *runs*, it
just returns nothing — that's not this marker's job).

---

### 12. Unknown-production badge

**Purpose:** flags total repository silence about a value or state.

**Semantic meaning:** role 8. The trained model checkpoint, live feature-switch values,
live cluster routing, BDSM's real thresholds, the production post-vector table's contents.

**Visual treatment:** hatch-fill (45° hairlines) overlay on the base shape's existing fill,
plus a `?`-glyph badge (`PRODUCTION UNKNOWN` at full type size). Never a standalone color —
always layered on an existing role.

**Example label:** the D6 post-vector table cylinder, role-7 gray fill, hatched, badged
`PRODUCTION UNKNOWN`.

**Misuse to avoid:** don't use this for a checked-in default that simply might differ in
production (that's component 13) — this badge means the repository shows *nothing at
all*, not "shows a default that could be overridden."

---

### 13. Checked-in-default badge

**Purpose:** flags a specific number read directly from source that could be overridden
per-request by mechanism the repository shows but not the live value of.

**Semantic meaning:** every specific weight, threshold, or percentage anywhere in the
diagram suite requires this badge, no exceptions (`../diagrams/README.md`).

**Visual treatment:** plain outlined tag (not hatched — that's the unknown badge's
signature), technical voice, attached directly to the number itself rather than to the
whole containing node.

**Example label:** `0.75×` `CHECKED-IN DEFAULT` next to the OON discount value.

**Misuse to avoid:** don't attach this badge to the node as a whole when only one number
inside it is checked-in — attach it to the specific value, so a reader can tell exactly
which part of the node is a default and which part (if any) is an architectural fact.

---

### 14. Reference-implementation badge

**Purpose:** flags a model, config, or code path that's real and runnable, and is what the
repository's own tooling documents or uses — but isn't independently confirmed as what
production runs.

**Semantic meaning:** the two-tower retrieval architecture, the
`home_direct_packed*`/`xrecsys_two_tower*` config pairing.

**Visual treatment:** plain outlined tag, technical voice, `SHIPPED REFERENCE`, placed at
the corner of the node it describes — visually distinct from the checked-in-default badge
(which marks a *value*, not an *implementation*) even though both use the plain-outline
treatment, to keep the badge vocabulary from growing past what `ART_DIRECTION.md`'s
"three badges per diagram" discipline rule allows.

**Example label:** the D6 two-tower model card, badged `SHIPPED REFERENCE`.

**Misuse to avoid:** never use this badge to imply "probably true of production" — the
badge's entire job is to prevent that exact inference. Pair it with subtitle language like
"the repository's own tooling documents," not "production likely runs."

---

### 15. Warning / correction callout

**Purpose:** a rare, maximum-weight callout for a genuinely critical correction — reserved,
by design, for the single most important myth this project exists to prevent per diagram.

**Semantic meaning:** used once per diagram at most. D3's "these weights multiply
predictions, not raw counts" warning is the canonical instance; no other diagram in D1–D4
currently needs one at this strength (D4's index-time-exclusion note is a lower-weight
side-note, component 16 territory, not this one).

**Visual treatment:** bordered box, strongest ink weight anywhere in the diagram, editorial
voice, bold. The corrected/true statement is set larger and first; the myth being corrected
is set smaller, second, and visually subordinated (muted tone, optionally struck through)
— never the reverse, since a louder myth than correction is the exact failure mode this
component exists to prevent (see `README.md`'s D3 review notes).

**Example label:** "These weights multiply **predicted probabilities**, not raw counts."
(primary, bold, large) / ~~"1 report = 468 likes"~~ (secondary, muted, small).

**Misuse to avoid:** don't reuse this component for routine caveats — if it appears more
than once per diagram, it stops reading as "the one thing to remember" and starts reading
as generic caution, which defeats its purpose.

---

### 16. Zoom-in link / "see diagram X"

**Purpose:** signals that a box on this diagram is deliberately underspecified here because
another diagram in the suite covers it in full.

**Semantic meaning:** the mechanism that lets D1 stay at 15 conceptual stages instead of
absorbing D2/D3/D4/D5/D6 wholesale — every "intentionally omits" section across the suite
relies on this component existing.

**Visual treatment:** small editorial-voice footer line inside or beneath the relevant
node: "— see Diagram 0N." No icon needed; the arrow/link affordance is implied by the
diagram-numbering convention already established across the suite. In an interactive
future context (Phase 4, `../ROADMAP.md` I2) this becomes a real hyperlink; in this phase's
static specs it's plain text.

**Example label:** `Up to 7 candidate sources (only enabled ones run) — see Diagram 02.`

**Misuse to avoid:** don't use this as a substitute for a component that genuinely belongs
in the current diagram at low detail — it's for content that's a whole diagram's worth of
depth elsewhere, not an excuse to omit something this diagram's own "what this diagram
must NOT imply" section depends on the reader knowing.
