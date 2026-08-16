# D2 Production Spec — Retrieval Sources

Source wireframe: `../diagrams/02-retrieval-sources.md` (unchanged this phase — see
`README.md`'s Part 1 review). Built from `ART_DIRECTION.md` and `COMPONENT_LIBRARY.md`.

**Primary takeaway:** before ranking can happen, multiple systems decide which posts even
get considered.

---

## Required structure

Two visually separated time-zones, not one flowchart — this is the single most important
compositional decision in this diagram, carried over directly from the wireframe's own
"Future visual treatment" note.

### Zone A — Index admission (background, once per post, no viewer)

`phoenix-rankall` [component 8, background producer] evaluates each new post or
qualifying favorite-count crossing, and either excludes it or admits it into the retrieval
corpus [component 7, data store, the post-vector table]. Zoom-in link to Diagram 06 for
the vector mechanics; zoom-in link to Diagram 05 for the safety-check branch of this
decision.

### Zone B — Request-time retrieval (viewer opens For You)

**Viewer request** [terminal start node] fans out into up to seven candidate-source cards
[component 4], each drawing from Zone A's corpus where applicable:

- **Thunder** — recent posts from people you follow. No model.
- **SimClusters** — similarity to your recent engagements. Independent system.
- **PhoenixSource** — two-tower search against Zone A's corpus.
- **PhoenixTopicsSource** — same mechanism, topic-scoped. [component 11, optional-path
  marker: topic-scoped requests only]
- **PhoenixMOESource** — same mechanism, alternate index. [component 11: off by default]
- **TweetMixerSource** — external service. [component 11: off by default, plus a
  `SHIPPED REFERENCE`-adjacent note — see "TweetMixer," below]
- **CachedPostsSource** — reuses a prior scored set. [see "Cache," below — this one does
  not sit in the parallel fan the way the other six do]

All contributing sources feed a **candidate pool** [component 9], then a single
**48-hour age filter** [component 6-adjacent gate, or a simple filter card if a full
hexagon reads as too heavy for a universal, non-branching filter — see note below], then
onward to Diagram 01's hydration stage.

**Note on the age filter's shape:** although `COMPONENT_LIBRARY.md` reserves the hexagon
for named, multi-outcome decisions, the 48-hour filter has exactly one real outcome
(keep/discard) applied uniformly — render it as a plain pipeline-stage card with a
checked-in-default badge on "48 hours," not a hexagon, so the diagram's one hexagon budget
(per `ART_DIRECTION.md`'s badge-discipline logic, extended here to shapes) stays reserved
for `phoenix-rankall`'s admit/exclude branch in Zone A, which is the decision this diagram
actually wants a reader to remember.

## D2 Phoenix sublayer

The two-stage structure required by the phase brief, kept visually unmerged:

```
POST-SIDE / BACKGROUND (Zone A)
  post event / favorite-threshold crossing
    → phoenix-rankall: admit to corpus? [hexagon]
    → retrieval corpus / post-vector table [cylinder, zoom-link to Diagram 06]

REQUEST-SIDE (Zone B)
  viewer request
    → two-tower query vector [pill, component 10]
    → top-k vector search against the corpus above [component 1, request-time]
    → candidates → candidate pool
```

These two stages are drawn in physically separate regions of the canvas (Zone A stacked
above or beside Zone B, never interleaved), connected by exactly one crossing arrow: the
corpus cylinder feeding into the top-k search box. That single arrow is the *only* place
the two zones touch — everything else in Zone B is request-time, everything else in Zone A
is background, and the composition should make that legible without reading any label.

## IN / OON

A compact legend, not a forced binary, placed once near the top of the diagram rather than
repeated as a badge on every source card:

> **Legend:** IN-network oriented · OON-oriented · mixed/special

Thunder is the sole card marked IN-network oriented — the wireframe's own framing ("the
main IN retrieval path") is preserved exactly. SimClusters, the three Phoenix-family
sources, and TweetMixer are marked OON-oriented. `CachedPostsSource` is marked
mixed/special, since it re-serves whatever mix a prior request already retrieved rather
than having a network orientation of its own. The legend's third category exists
specifically so the diagram doesn't force `CachedPostsSource` into a false IN/OON choice.

## Cache

`CachedPostsSource` is drawn outside the parallel candidate-source fan, connected instead
by a dashed override arrow that visually crosses out the other six sources' connectors
when active — the phase brief's "reuse candidate set, not recommendation model" framing
made literal: it doesn't get a model-card treatment (component 5) at all, only a
data-store link (component 7, to the short-lived candidate cache) plus a small annotation:
"when active, replaces all six other sources for this request." This keeps cache mode from
reading as an eighth peer retrieval mechanism.

## TweetMixer

Rendered as a component-4 candidate-source card like the others, but with its interior
left visually empty below the title — no output pills, no internal mechanism shown — and
a badge reading `IMPLEMENTATION NOT INCLUDED IN SNAPSHOT` in place of the subtitle a real
mechanism description would otherwise carry. This is deliberately a *different* kind of
badge from `SHIPPED REFERENCE` (which marks something real but production-unconfirmed) —
TweetMixer isn't even present to describe; the badge marks absence, not just
unconfirmation.

## Hierarchy

- **Foreground:** the two-zone split itself; the seven source cards; `phoenix-rankall`'s
  admit/exclude gate.
- **Secondary:** the candidate pool, the 48-hour filter.
- **Tertiary:** per-source retention-window detail (Thunder ~48h, SimClusters ~2 days
  internal) — prose-only, not drawn as separate paths, per the wireframe's existing
  omission.

## Copy

| Element | Component name | Subtitle |
|---|---|---|
| Zone A gate | `phoenix-rankall` | "Admits posts to the retrieval corpus" |
| Zone A store | `Retrieval corpus` | "Post vectors — see Diagram 06" |
| Thunder | `Thunder` | "Recent posts from people you follow" |
| SimClusters | `SimClusters` | "Similar to what you've recently engaged with" |
| PhoenixSource | `PhoenixSource` | "Two-tower search — see below" |
| PhoenixTopicsSource | `PhoenixTopicsSource` | "Same search, topic-scoped" |
| PhoenixMOESource | `PhoenixMOESource` | "Same search, alternate index" |
| TweetMixerSource | `TweetMixerSource` | "Implementation not included in snapshot" |
| CachedPostsSource | `CachedPostsSource` | "Reuses a prior scored set" |
| Pool | `Candidate pool` | "Pooled, no priority order" |
| Age filter | `Age filter` | "48-hour cutoff, applies to every source" |

## Responsive versions

**Desktop full version:** both zones fully rendered, all seven source cards individually
visible with IN/OON legend markers.

**Mobile simplified version:** Zone A and Zone B stack vertically (Zone A on top). The four
Phoenix-family sources (PhoenixSource/Topics/MOE plus the shared search mechanism)
collapse into one card reading `Phoenix retrieval — 3 variants` with a "see Diagram 06"
link; Thunder, SimClusters, and the Cache override remain individually visible since
they're each conceptually distinct enough to lose meaning if merged.

**Social-card crop:** just the one-line headline claim rendered as the whole image —
`phoenix-rankall` and the top-k search box, connected by the single crossing arrow, with
overlay text: "Admission and search are two different systems." No source-card fan-out at
all in this crop; it exists to carry exactly one distinction, not the whole diagram.

## What this must NOT imply

- That all seven sources always run.
- That `phoenix-rankall`'s admission decision and a specific request's two-tower search are
  the same event.
- That "excluded from the mainstream indices" means excluded from Phoenix retrieval, full
  stop — the `search_unfiltered` exception's live reach is unknown, and that caveat stays
  attached directly to the exclusion branch, not as a diagram-wide footnote.
- That SimClusters and Phoenix retrieval are related systems.
- That which source found a candidate has any bearing on its eventual rank.
- **Production-specific:** that TweetMixer's empty card means it doesn't exist or never
  runs — it means its internals aren't in this repository, which is a different claim.
- **Production-specific:** that `CachedPostsSource`'s override arrow means caching is
  itself a recommendation mechanism — it reuses a prior result, it doesn't compute one.

## Claim dependencies

`CLAIM_BANK.md` #6, #7, #8, #9, #10, #11, #12, #13, #14.

## Provenance

Master synthesis §3 (full retrieval section), §17 (index-time exclusion vs. per-request
filtering as a distinction to keep sharp).
