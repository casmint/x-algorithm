# Visual Language

A semantic vocabulary for diagrams — what shapes, lines, and badges *mean*, not what they
should look like. This is not art direction. No color palette, no typography, no brand
decisions here; that's Phase 2+ work, once the semantics below are validated against the
six wireframes.

Every diagram in `diagrams/` uses this vocabulary. When it's time to redesign a diagram
visually, the underlying meaning shouldn't need to change — only its rendering.

## Node types

**Local Home Mixer logic** — solid box. Ordinary code running inside the Home Mixer
process itself: RankingScorer, pre-scoring/post-selection filters, BlenderSelector, query
construction. No RPC involved in the decision itself, even if the data it reads arrived
via RPC earlier.

**Remote service / dependency** — outlined box (border only, no fill), labeled with the
service name. A separate process Home Mixer calls over RPC: Phoenix (ranking and
retrieval sides), VMRanker, visibility filtering, Thunder, SimClusters,
`phoenix-rankall`'s serving-side search, TweetMixer, Gizmoduck.

**Background / asynchronous system** — dashed-border box. Runs continuously,
independent of any single request: Agatha, BDSM, Grox, Botmaker/Scarecrow,
abuse-enforcement-service, `phoenix-rankall`'s ingestion pipeline. Not queried
synchronously mid-request — it produces state that a later request reads.

**Data store / state** — cylinder or stacked-rectangle shape. A place state lives between
requests: Gizmoduck's account records, Phoenix's post-vector table, the short-lived
candidate cache, the safety-label annotation record.

**Policy / filter decision point** — diamond or hexagon. A branching decision that
produces one of a fixed set of outcomes: visibility filtering's Allow/Interstitial/Drop,
a pre-scoring filter's keep/remove, `phoenix-rankall`'s admit/exclude.

## Flow types

**Candidate / post flow** — thick solid arrow. The primary path a candidate post travels:
retrieval → hydration → filters → scoring → visibility → response.

**Score / prediction flow** — thinner solid arrow, distinct from the candidate-flow
weight, labeled with what's flowing (a prediction, a score, a similarity value). Used
when the diagram needs to show a *number* moving between stages, not the post itself.

**Metadata / signal enrichment** — side arrow, entering the main flow from the side rather
than continuing it. Used for hydration steps (follow graph, engagement counts, safety
labels) that add information to a candidate without representing the candidate's own
forward progress.

**Policy / filter decision** — arrow leading out of a diamond/hexagon node, one per
possible outcome, each labeled with that outcome (Allow / Interstitial / Drop; Keep /
Remove).

**Conditional / feature-gated path** — dashed arrow. A path that only runs under specific
conditions: a disabled-by-default retrieval source, DPP selection if the server flag is
on, an interstitial-only branch.

## Badges

**Checked-in default** — a small warning/note badge attached to any node or arrow
carrying a specific number (a weight, a threshold, a percentage). Reads roughly:
"checked-in default, not confirmed production value." Required wherever a specific
number appears in a diagram.

**Production unknown** — a question-mark badge for anything the repository doesn't show
at all: live feature-switch values, the trained model checkpoint, live cluster routing,
BDSM's real thresholds. Distinct from the checked-in-default badge — this marks total
absence, not "default that might differ live."

**Optional / feature-gated** — a small gate or toggle icon, paired with a dashed border or
dashed arrow, for anything off by default or conditionally enabled: TweetMixer,
PhoenixMOESource, DPP (both layers of its conditionality).

## Arrow-label vocabulary

Every arrow gets a verb. Don't leave an arrow unlabeled when more than one relationship
between the same two node types is possible in the diagram.

- **"retrieves"** — a retrieval source pulling candidates into the pool.
- **"predicts"** — Phoenix producing action-probability predictions for a candidate.
- **"scores"** — RankingScorer (or VMRanker, when it recomputes rather than masks)
  producing a scalar.
- **"filters"** — a pre-scoring or post-selection filter removing or keeping a candidate.
- **"queries"** — a synchronous, per-request lookup against a remote store (Gizmoduck,
  the social graph).
- **"writes label"** — a detector or enforcement system persisting a label or account
  state.
- **"reads state"** — a consumer (visibility filtering, index admission) pulling
  previously-written labels or account state.
- **"blends"** — BlenderSelector inserting or interleaving non-post items.

Never leave an arrow meaning "something happens between these two boxes" — if no verb
from this list fits, that's a sign the diagram is collapsing two different relationships
into one arrow, and it should be split.

## Naming rules

- On first appearance in a diagram, use the human name before the codename: "Visibility
  Filtering (VF)," not "VF." Same for "RankingScorer (the scoring component)," "Phoenix
  (the prediction model)," etc. — codenames are fine after the first labeled appearance.
- Every codename-heavy diagram (05 especially) needs a one-line explanation attached to
  each unfamiliar proper noun the first time it appears — don't assume the reader has
  read the glossary first.
- Don't invent a friendlier name for something the source only calls by its codename —
  "Home Mixer," "Thunder," "Gizmoduck" stay as-is; add the human-language *description*
  next to them, don't rename them.

## What this file does not do

It does not specify colors, fonts, line weights in pixels, icon sets, or brand identity.
Those choices come later, once the six wireframes have been reviewed and the semantic
distinctions above are confirmed to be the right ones to draw. A wireframe built from
this vocabulary should be redesignable by a different visual system without changing what
any shape or arrow *means*.
