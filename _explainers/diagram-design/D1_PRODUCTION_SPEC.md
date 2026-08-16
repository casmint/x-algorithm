# D1 Production Spec — Full For You Pipeline

Source wireframe: `../diagrams/01-for-you-pipeline.md` (unchanged this phase — see
`README.md`'s Part 1 review). Built from `ART_DIRECTION.md` and `COMPONENT_LIBRARY.md`.

**Target reader:** someone who knows nothing about X's internal codenames.

**Primary takeaway:** the For You feed is a multi-stage pipeline, not one model.

---

## Required structure

Fifteen stages, left-to-right (desktop) or top-to-bottom (mobile) primary flow. Every
stage below maps to a component from `COMPONENT_LIBRARY.md`; the component name is noted
in brackets.

1. **Viewer opens For You** [terminal start node] — the request's origin.
2. **Home Mixer: request context** [component 2, Home Mixer local card] — builds the
   query: identity, follow graph, recent actions, feature-switch bucket. Side-queries
   Gizmoduck (component 7, data store, with a request-time RPC tint — see "Local vs.
   remote" below).
3. **Retrieval** [fan-in of component 4, candidate-source cards] — up to seven sources,
   only enabled ones run, concurrently. Zoom-in link to Diagram 02.
4. **Candidate pool** [component 9] — concurrent contributions pooled, no priority order.
5. **Hydration + pre-scoring filters** [two adjacent component-1 pipeline-stage cards,
   secondary tier] — hydration adds context concurrently; 18 pre-scoring filters run
   sequentially afterward.
6. **Phoenix predicts** [component 5, model card] — zoom-in link to Diagram 03.
7. **RankingScorer** [component 2, Home Mixer local card] — converts predictions to one
   score.
8. **VMRanker** [component 3, remote service card] — optional diversity selection (DPP).
   Zoom-in link to Diagram 03.
9. **Top 50** [component 9, later-stage pool variant] — checked-in-default badge on "50."
10. **Visibility Filtering** [component 6, filter/policy gate hexagon] — Allow /
    Interstitial / Drop. Zoom-in link to Diagram 04.
11. **Organic survivors** [component 1, pipeline stage card] — truncated to 35;
    checked-in-default badge on "35."
12. **BlenderSelector** [component 2, Home Mixer local card] — mixes organic posts with
    everything else.
13. **Ads / WTF / prompts / push / frames / survey** [component 10 non-organic module
    cards, side inputs feeding step 12 via "blends" arrows] — never scored by Phoenix or
    RankingScorer.
14. **Final feed** [terminal end node] — response returned to client.
15. **Side effects / served history** [component 8, background producer, off the main
    spine] — logging and cache writes; connected by a dotted, not solid, line, explicitly
    positioned so it visibly does not sit on the path to step 14.

## Local vs. remote

The Home Mixer boundary is a single large containing shape (rounded outline, role-1 tint
at low opacity as a background wash, not a solid fill — the wash reads as "this whole
region is one process" without making every internal card look like a filled component-2
card). It contains stages 2, 5, 7, 9, 11, 12 — request context, hydration, pre-scoring
filters, RankingScorer, top-50 selection, truncation, and BlenderSelector.

Stages 3 (retrieval), 6 (Phoenix), 8 (VMRanker), and 10 (Visibility Filtering) sit visibly
outside that boundary, each using component 3's double-ruled border, connected to the
boundary by request/call arrows that visibly cross it.

**The retrieval nuance, specifically:** the seven candidate-source cards in stage 3 are
themselves Home Mixer-side abstractions — small HM components that each *may* call out to
a remote backend. Draw them as a sub-layer straddling the Home Mixer boundary's edge:
positioned mostly inside the boundary wash, each with a short connector breaking out to a
small remote-service tag for the backend it actually calls (Thunder, SimClusters, the
Phoenix retrieval family, TweetMixer). `CachedPostsSource` is the one exception — its
connector points to a data-store cylinder (the candidate cache) instead of a remote tag,
since it reads cached local state rather than calling out. Per the phase brief: do not
draw every retrieval source as a remote service outright — the HM-side abstraction is real
and worth preserving visually, not just in prose.

Gizmoduck gets its own hybrid treatment: cylinder shape (component 7, it holds state) with
a role-2 stroke tint and a REQUEST-TIME badge, connected to stage 2 by a solid thin
request/call arrow labeled "queries" — visually distinct from the background producers
(component 8) that only get read from later, since Gizmoduck is synchronous and per-request
in a way they aren't (`CLAIM_BANK.md` #4).

## Concurrency / order

Shown graphically, not in a paragraph beneath the diagram:

- **Stage 3 (retrieval):** the seven source cards sit inside a bracket labeled
  `CONCURRENT` in the section-label type style, drawn as parallel lanes fanning into stage
  4 — visually, sources never appear stacked in a single-file sequence.
- **Stages 5–9 (hydration through Top 50) and the local/remote stages inside them:** drawn
  as a single unbranching chain with a bracket labeled `SEQUENTIAL — FIXED ORDER`,
  reinforcing that each stage depends on state the previous one produced
  (`CLAIM_BANK.md` #59).
- **Stage 15 (side effects):** connected by a dotted line breaking away from the main
  spine after stage 14, labeled `POST-RESPONSE / ASYNC` — positioned so it visually cannot
  be mistaken for a stage the response passes through on its way out.

## Hierarchy

Three visual weight tiers — the fifteen stages must not read as equally important.

- **Foreground (heaviest line weight, largest cards):** retrieval (3), Phoenix (6),
  RankingScorer (7), VMRanker (8), Visibility Filtering (10), BlenderSelector (12). These
  are the stages each get their own diagram elsewhere in the suite, or are the single most
  counter-intuitive moment in the pipeline (10).
- **Secondary (medium weight):** hydration + pre-scoring filters (5), Top 50 (9), organic
  survivors (11), side effects (15).
- **Tertiary (smallest type, first to collapse on mobile):** individual retrieval-source
  names within stage 3, individual non-organic module names within stage 13.

## Copy

Exact display copy for every visible box. No sentences inside boxes — a name and a
subordinate human-language line, per `ART_DIRECTION.md`'s typography table.

| Stage | Component name (technical voice) | Subtitle (editorial voice) |
|---|---|---|
| 1 | — | "Viewer opens For You" |
| 2 | `Home Mixer` | "Builds the request context" |
| — (side query) | `Gizmoduck` | "Account state — queried live" |
| 3 | `Retrieval` | "Up to 7 sources — only enabled ones run" |
| 4 | `Candidate pool` | "Pooled, no priority order" |
| 5a | `Hydration` | "Adds context, concurrently" |
| 5b | `Pre-scoring filters` | "18 filters, fixed order" |
| 6 | `Phoenix` | "Predict likely reactions" |
| 7 | `RankingScorer` | "Combine predictions into one score" |
| 8 | `VMRanker` | "Optional diversity selection" |
| 9 | `Top 50` | "Kept by score" |
| 10 | `Visibility Filtering` | "Allow, warn, or remove" |
| 11 | `Organic survivors` | "Truncated to 35 posts" |
| 12 | `BlenderSelector` | "Mix organic posts with other feed items" |
| 13 | `Ads` / `Who to Follow` / `Prompts` / `Push to home` / `Frames` / `Survey` | "Inserted after ranking — never scored by Phoenix" (one shared subtitle for the group) |
| 14 | — | "Your feed" |
| 15 | `Side effects` | "Logging, cache writes — cannot affect this response" |

## Responsive versions

**Desktop full version:** all fifteen stages visible, three-tier hierarchy fully rendered,
every retrieval-source and non-organic-module name shown individually at tertiary size.

**Mobile simplified version:** single vertical column, primary spine intact end to end.
Stage 3 collapses to one card reading `Retrieval — 7 sources` with a tap/expand affordance
implied (static: "see Diagram 02" link) rather than seven individual cards. Stage 13
collapses to one card reading `Ads, Who to Follow, prompts +3 more`. Secondary-tier
subtitles remain readable; tertiary detail is what collapses, never the primary spine
itself.

**Social-card crop:** the Home Mixer boundary wash with stages 6, 8, 10 breaking out of it
as remote cards — cropped tightly around just that boundary-crossing moment, not the full
pipeline. Headline overlay text: "Your feed isn't one model. It's a pipeline." One badge
maximum (a small LOCAL/REMOTE legend key), no checked-in-default badges at this crop —
they're not legible at social-card scale and aren't this crop's point.

## What this must NOT imply

Carried forward from the wireframe (`../diagrams/01-for-you-pipeline.md`), plus
production-specific additions:

- That all seven retrieval sources always run.
- That RankingScorer, the pre-scoring filters, or BlenderSelector are remote calls.
- That reaching Top 50 or passing Visibility Filtering guarantees final display —
  truncation and blending still apply afterward.
- That side effects have any influence on the response already in flight.
- That this is the complete system — safety-label production and model internals are each
  their own diagram.
- **Production-specific:** that the candidate-source cards in stage 3 are themselves
  remote services — they're Home Mixer abstractions that mostly call remote backends,
  except `CachedPostsSource`, which doesn't call out at all.
- **Production-specific:** that Gizmoduck belongs with the background safety producers
  shown in Diagram 05 — its hybrid cylinder-plus-request-time treatment exists specifically
  to keep it visually distinct from them.
- **Production-specific:** that the Home Mixer boundary is a literal physical machine — it's
  a process boundary, rendered as a containing region, not a piece of hardware.

## Claim dependencies

`CLAIM_BANK.md` #1, #2, #3, #4, #5, #6, #43, #44, #45, #50, #51, #58, #59.

## Provenance

Master synthesis §1–2, §12, §13 (caching, mentioned only as the optional footnote below,
not a pipeline stage), §14 (failure behavior, referenced but not detailed).

## Optional footnote (not a pipeline stage)

A small annotation-voice note near stage 4 or 9, only in the desktop full version: "A
cached response (when eligible) skips fresh retrieval and Phoenix inference, but
RankingScorer and VMRanker both still re-run with current weights" — sourced from
`CLAIM_BANK.md` #46/#47, master §13. Omitted from mobile and the social crop entirely; it's
real but genuinely secondary to this diagram's one takeaway.
