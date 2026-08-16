# Diagram Design — Phase 2A

This directory turns the six diagram wireframes in `../diagrams/` into a single coherent
visual system, plus production-ready specifications for D1–D4. It does not contain final
artwork. A designer, an SVG/HTML builder, or an image-generation workflow should be able
to execute D1–D4 from the specs here without reinterpreting the algorithm.

Nothing here supersedes `../diagrams/` wireframes for *meaning* — it specifies how that
already-reviewed meaning should look. Nothing here reopens `_analysis/`; every factual
claim traces to `../CLAIM_BANK.md` or the master synthesis sections `../CONTENT_MAP.md`
already mapped.

## Files in this directory

- **`README.md`** (this file) — phase overview, Part 1's adversarial review of D1–D6, and
  the D5/D6 review-only conclusions.
- **`ART_DIRECTION.md`** — the one chosen visual direction: composition character, color
  system, typography/labeling, shape language, arrow vocabulary, badges.
- **`COMPONENT_LIBRARY.md`** — sixteen reusable visual components, each with purpose,
  semantic meaning, visual treatment, example label, and a misuse to avoid.
- **`D1_PRODUCTION_SPEC.md`** — full production spec for the flagship pipeline diagram.
- **`D2_PRODUCTION_SPEC.md`** — full production spec for retrieval sources.
- **`D3_PRODUCTION_SPEC.md`** — full production spec for the ranking stack.
- **`D4_PRODUCTION_SPEC.md`** — full production spec for ranking vs. visibility filtering.

D5 and D6 are reviewed below (Part 8 scope) but not promoted to full production specs this
phase — see the two review sections near the end of this file.

---

## Part 1 — Adversarial diagram review

Conclusion up front: **none of the six wireframes required a factual correction.** They
were already built with the same evidence discipline as the master synthesis — every
wireframe cross-references `CLAIM_BANK.md`, every specific number already carries a
checked-in-default badge, and every "must NOT imply" section already anticipates the
misreadings this review was looking for. The one concrete defect found was structural, not
factual: an unlabeled arrow in Diagram 05, now fixed (see "Wireframe corrections" below).

The rest of this section works through the nine review questions for each diagram, then
records where production-spec elaboration goes beyond the wireframe without changing what
it means.

### D1 — Full For You pipeline

- **10-second takeaway:** the feed is assembled by one orchestrator running its own local
  code plus calls to several separate services, in a fixed order — not one model.
- **Most likely incorrect inference:** that RankingScorer/filters/BlenderSelector are
  remote calls (already guarded against); that retrieval sources are checked in priority
  order rather than pooled concurrently (now backed by `CLAIM_BANK.md` #58); that reaching
  "Top 50" or an "Allow" verdict guarantees final display.
- **Visually essential:** the Home Mixer local/remote boundary; the concurrent-retrieval
  vs. sequential-filters-and-scorers distinction; the Top-50 → Visibility Filtering → Drop
  moment.
- **Technically true but omit from primary view:** the exact count of pre-scoring filters
  (18) and their individual names; the specific ad-blend strategy names (§12) — prose/
  companion detail, not headline nodes.
- **Needs a callout, not a main node:** side effects/served history (already pushed
  off-flow in the wireframe) and caching's re-weighting behavior (§13, not in the
  wireframe at all — the production spec adds it as a small footnote, not a pipeline
  stage, since it only applies to a subset of requests).
- **Terms needing human-language subtitles:** Home Mixer, RankingScorer, BlenderSelector,
  VMRanker, Phoenix, Gizmoduck — all get first-occurrence subtitles per
  `../VISUAL_LANGUAGE.md`'s naming rule.
- **Uncertainty/default state to mark:** Top-50 and 35-post truncation numbers (checked-in
  default badges, already flagged in the wireframe).
- **Doing too much?** It's intentionally the widest diagram (15 conceptual stages) and the
  roadmap treats that as correct — D1 is the whole-system map by design. The risk isn't
  scope, it's flattened hierarchy: all 15 stages must not read as equally important (see
  D1 spec's foreground/secondary/tertiary tiers).
- **Missing conceptual boundary?** Yes, one worth making explicit in the production spec:
  the wireframe's prose already notes the organic pipeline is "just one input" to an outer
  ad/WTF/prompt blend (§12, `CLAIM_BANK.md` #5), but the wireframe draws that only as text
  inside the BlenderSelector node, not as visible side-input boxes. The phase brief's
  required D1 structure calls for those as explicit side inputs — the production spec adds
  them as visual cards feeding BlenderSelector. This is elaboration, not a correction: the
  wireframe never claimed otherwise, it just deferred the detail.

### D2 — Retrieval sources

- **10-second takeaway:** multiple independent systems, not one recommender, decide what's
  even eligible before ranking — and corpus admission is a different event from a
  request's search.
- **Most likely incorrect inference:** collapsing `phoenix-rankall` admission and
  two-tower search into one step (the wireframe already guards this explicitly, as its own
  headline claim); reading IN/OON as a clean binary that every source fits without
  exception.
- **Visually essential:** the two-subgraph time split (background admission vs.
  request-time retrieval); all seven sources; cache's total-bypass behavior.
- **Technically true but omit:** exact per-source retention windows beyond the universal
  48-hour filter (Thunder ~48h, SimClusters ~2 days) — correctly kept to prose.
- **Needs a callout, not a main node:** `search_unfiltered`'s unknown live reach (already a
  callout attached directly to the exclusion branch, not a footnote — correct); TweetMixer
  needs a "implementation not included in snapshot" badge, which the wireframe states in
  prose but doesn't yet render as a visual badge — added in the production spec.
- **Terms needing subtitles:** Thunder, SimClusters, `phoenix-rankall`, TweetMixer.
- **Uncertainty/default state to mark:** the 48-hour age filter (checked-in default,
  already flagged).
- **Doing too much?** No, but the Phoenix sublayer (post-side background admission vs.
  request-side two-tower search) deserves a crisper two-stage visual than the current flat
  fan-out of `PhoenixSource`/`PhoenixTopicsSource`/`PhoenixMOESource` gives it — the phase
  brief's required D2 structure asks for this explicitly. The production spec restructures
  this as its own labeled two-stage block without changing what any wireframe box claims.
- **Missing conceptual boundary?** Cache mode is drawn as one parallel branch among seven
  peers, but it isn't a retrieval mechanism — it's a conditional bypass that replaces the
  other six. The production spec visually demotes it to a dashed override path rather than
  a peer source, matching the phase brief's explicit "reuse candidate set, not
  recommendation model" framing.

### D3 — Ranking stack

- **10-second takeaway:** Phoenix predicts roughly two dozen outcomes; RankingScorer turns
  those predictions into one score; neither is a raw count of what anyone did.
- **Most likely incorrect inference:** reading the myth text inside the warning box ("NOT:
  1 report = 468 likes") as more memorable than the correction next to it — a real risk the
  phase brief calls out directly. The production spec's typography makes the myth
  visually subordinate (struck through / muted) and the correction dominant.
- **Visually essential:** three distinct kinds of numbers — Phoenix's prediction vector,
  RankingScorer's scalar, VMRanker's kept-or-zeroed result — currently distinguished only
  by node label text, not by shape or color. This is the highest-value fix the production
  spec makes to this diagram (see D3 spec, "Three different values").
- **Technically true but omit:** the full 14-value weight table (already deferred to an
  optional inset, correctly).
- **Needs a callout, not a main node:** DPP's conditionality (already dashed/conditioned
  correctly).
- **Terms needing subtitles:** RankingScorer, VMRanker, DPP ("diversity-aware selection,"
  not "Determinantal Point Process" — the acronym expansion isn't reader-useful, the
  function description is).
- **Uncertainty/default state to mark:** OON discount, mutual-follow boost, diversity
  floor, cold-start position, `--dpp-enabled=false` — all already flagged in the
  wireframe.
- **Doing too much?** Borderline yes — candidate → predict → score → four sequential
  adjustments → VMRanker → DPP → Top K is a lot for a ten-second read. The wireframe
  already groups the four adjustments into a secondary sub-block; the production spec
  keeps that grouping and pushes it one visual tier below the primary predict→score→
  select spine, so a skim-reader gets the spine and a closer reader gets the adjustments.
- **Missing conceptual boundary?** The three-different-values distinction above is exactly
  this — not a missing box, but a missing *visual category* the wireframe's prose already
  knows to draw (§17, `CLAIM_BANK.md` #57) but the diagram itself doesn't yet encode
  outside of text.

### D4 — Ranking vs. Visibility Filtering

- **10-second takeaway:** a high score doesn't guarantee a post is shown — ranking and
  visibility are two separate questions, asked by two separate systems.
- **Most likely incorrect inference:** reading the OON policy as "unsafe" or Drop as
  equivalent across both policies. The wireframe's prose already refuses this framing
  ("not a bug," "not maximally restrictive") — the production spec's language section
  keeps that discipline in the on-diagram copy itself, not just the walkthrough prose.
- **Visually essential:** the funnel narrowing into a fork, the fork into two policy lanes,
  three terminal states per lane.
- **Technically true but omit:** the full rule-evaluation order and the label→consequence
  table — correctly deferred to companion reference material.
- **Needs a callout, not a main node:** the index-time-exclusion note — already isolated
  from the main flow in the wireframe; the production spec keeps it as a side panel, not a
  pipeline stage.
- **Terms needing subtitles:** Visibility Filtering (VF), TimelineHome,
  TimelineHomeRecommendations, Interstitial.
- **Uncertainty/default state to mark:** none required in the main flow — "roughly two
  dozen additional drop rules" is a hedge on a count, not a specific checked-in number, so
  it doesn't need the checked-in-default badge treatment.
- **Doing too much?** No — this is correctly the simplest diagram in the suite and the
  production spec preserves that discipline over adding detail.
- **Missing conceptual boundary?** None found.

### D5 — Safety/reputation signal flow (review only, per Part 8)

Verified every arrow in the wireframe for a real semantic verb, per the phase brief's
explicit instruction. Thirteen of fourteen arrows already carry a specific relationship
label (`writes flags`, `spam score consumed by...`, `skip-gate`, `writes labels with NO
confirmed VF consumer`, `read by`, etc.). One did not: `BDSM --> BDSMENF` had no label at
all, which is exactly the "ambiguous arrow" failure mode the brief warns against.

**Wireframe correction made:** `../diagrams/05-safety-label-flow.md` now reads
`BDSM -->|"flags account for"| BDSMENF`, matching the walkthrough prose ("BDSM classifies
a user's recent action sequence for bot-like behavior... [feeding] BDSM's own enforcement
pipeline") and `CLAIM_BANK.md`'s existing framing of BDSM as a detector distinct from its
enforcement consequence.

No other structural issues found. The detector→enforcement→state→consumer layering is
sound, the "no confirmed VF consumer" arrows are already visually distinguishable in intent
(even if not yet in final color), and the BDSM≠adult-content / Botmaker≠Scarecrow
corrections are both present as required callouts. D5 remains at WIREFRAME status —
promoting it to a full production spec is Phase 2B scope (see the recommendation at the
end of this document).

### D6 — Phoenix two-tower retrieval (review only, per Part 8)

Verified the four distinctions the phase brief calls out specifically:

- `phoenix-rankall` corpus admission is drawn as its own upstream subgraph, separate from
  both towers — correct, not merged with anything downstream.
- The viewer tower and item/post tower are separate subgraphs with visibly different
  internal structure (full transformer vs. smaller item network), matching the master
  synthesis's own asymmetry.
- The resident post-vector table is explicitly marked "production contents UNKNOWN" with a
  distinct (hatched/dashed) style already called for in "Future visual treatment" — this
  is the diagram's single most load-bearing caveat and it's already treated as such.
- The top-k search is explicitly labeled exact, checked-in, and "NOT handed off to an
  external ANN service" — the wireframe already refuses the word "ANN" without that
  qualifier, which is exactly what the brief requires.
- The reference-architecture-vs-production-unknown distinction is carried through the
  walkthrough, the required-labels section, and the "must NOT imply" section consistently.

No structural issues found. D6 remains at WIREFRAME status; no changes made.

---

## Wireframe corrections made this phase

| Diagram | Change | Reason |
|---|---|---|
| 05 — Safety/reputation signal flow | Labeled the `BDSM --> BDSMENF` arrow as `"flags account for"` | Previously the only unlabeled arrow in the diagram; `../diagrams/README.md` and this phase's brief both require every D5 arrow to carry a real verb. |

No other wireframe file was changed. Everything else described as "the production spec
adds/restructures X" above is new visual detail introduced in the D1–D4 production specs,
not a change to what any wireframe claims — the wireframes' semantics were already
correct; the production specs make some of that semantics more visually explicit than a
Mermaid sketch reasonably can.

## Two new claims added to CLAIM_BANK.md

D1's production spec needed to state the retrieval-concurrency and filter-sequencing rules
as on-diagram copy, and neither was yet a standalone `CLAIM_BANK.md` entry (both were only
present as "safest reusable claims" prose inside `CONTENT_MAP.md`'s §2 row). Added as
**#58** (concurrent retrieval pooling, no priority order) and **#59** (fixed sequential
order for filters/scorers), both sourced directly from master synthesis §2 — no new
interpretation, just promoting an already-established claim to the reusable bank.

---

## Recommended Phase 2B scope

1. Execute D1–D4 as actual assets (SVG or HTML/CSS) from the production specs in this
   directory, in this order: **D4 first** (simplest, highest shareability, fastest to
   validate the art direction end-to-end), then **D1** (flagship, validates the art
   direction at its most complex), then **D2** and **D3**.
2. Promote D5 and D6 to full production specs once D1–D4 have validated the component
   library and art direction against real production constraints — D5 in particular will
   stress-test the badge system (it has the highest badge density of any diagram in the
   suite).
3. Do not start G1 or any myth page until at least D1 and D4 exist as real assets — both
   are listed prerequisites in `../ROADMAP.md` for exactly that content.
