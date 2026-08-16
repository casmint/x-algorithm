# D4 Production Spec — Ranking vs. Visibility Filtering

Source wireframe: `../diagrams/04-ranking-vs-visibility.md` (unchanged this phase — see
`README.md`'s Part 1 review). Built from `ART_DIRECTION.md` and `COMPONENT_LIBRARY.md`.

**Primary takeaway:** a high ranking score does not guarantee a post is shown. This should
be the simplest, most immediately shareable diagram in the suite — production decisions
below all favor legibility in under ten seconds over completeness.

---

## Core composition

```
HIGH-SCORING POST
      ↓
MAKES TOP 50                              [component 9]
      ↓
VISIBILITY FILTERING                      [component 6, hexagon — the diagram's one
   ↙      ↓       ↘                        and only gate shape]
ALLOW  INTERSTITIAL  DROP
  ↓         ↓          ✕
continues  warning/    removed —
toward     tap-through  never reaches
feed       delivery     the client
```

A vertical "funnel narrowing, then forking" layout: the post and Top-50 stages render as a
narrowing funnel shape (not literal boxes) to reinforce that this is a winnowing process,
then the funnel forks visibly into two policy lanes (see "Secondary layer" below), each
ending in the three terminal states above, rendered with distinct non-color terminal
glyphs per `ART_DIRECTION.md`'s accessibility rule for role 5 (a filled dot for
Allow-continues, a warning-triangle for Interstitial, an X-in-circle for Drop).

## Secondary layer

Below the primary fork, a smaller comparison strip — visually subordinate to the main
funnel, never competing with it for the reader's first glance:

| | TimelineHome | TimelineHomeRecommendations |
|---|---|---|
| Applies to | In-network posts | Out-of-network posts, plus any ancestor/quote/retweet target pulled in from outside the follow graph |
| Scope | More permissive — account-state issues, blocks/mutes, legal takedowns, hard NSFW cases | Everything TimelineHome checks, **plus** roughly two dozen additional drop rules |
| Framing label | "IN-network policy" | "OON-recommendation policy — stricter, not unsafe-vs-safe" |

**Language discipline, enforced in the label text itself, not just the walkthrough prose:**
the OON lane's label reads "stricter" and "more rules," never "less safe" or "riskier
content." This isn't a hedge added around the diagram — it's baked into the on-diagram copy
so a reader skimming only the labels, not the prose, still gets the correct framing.

## Index-time filtering

A single small annotation, rendered as a side note connected to the funnel's *top* (before
"Makes Top 50") by a thin dotted line — deliberately not part of the main
Allow/Interstitial/Drop visual, and deliberately not drawn as a fourth outcome lane:

> **Separate mechanism:** some posts are excluded before request-time ranking even begins,
> through Phoenix's own index-admission safety check — see Diagrams 02 and 05.

This note uses annotation-voice type (small, italic, muted), the smallest text on the
whole diagram, specifically so it cannot compete with the primary fork for visual weight
while still being present and legible for a reader who wants it.

## Language

On-diagram copy, not just walkthrough prose, uses this exact framing wherever the diagram
needs to characterize what each system is doing:

> Ranking asks: **"How valuable might this be to this viewer?"**
> Visibility asks: **"What treatment is allowed for this viewer, in this context?"**

Rendered as a small two-line header above the funnel, in editorial voice, largest type on
the page after the diagram title itself — this pairing is the diagram's real headline, more
so than the funnel graphic underneath it.

**Banned on this diagram, per `EDITORIAL_RULES.md`:** "good post," "bad post," "censored,"
"approved," or any language implying a moral judgment rather than a mechanism. The only
exception is a clearly-quoted misconception explicitly labeled as such (e.g., inside a
future myth-page companion, not this diagram).

## Hierarchy

- **Foreground:** the funnel, the fork, the three terminal states, the ranking/visibility
  question pairing.
- **Secondary:** the TimelineHome vs. TimelineHomeRecommendations comparison strip.
- **Tertiary:** the index-time-filtering side note.

This is the flattest hierarchy of any diagram in the suite — intentionally, since this
diagram's entire job is to be readable in one glance without needing tiers at all beyond
"the funnel is the point, everything else is support."

## Copy

| Element | Component name | Subtitle / label |
|---|---|---|
| Header pairing | — | "Ranking asks: how valuable? / Visibility asks: what's allowed?" |
| Funnel top | — | "High-scoring post" |
| Funnel narrow | `Top 50` | "Made the cut by score" |
| Gate | `Visibility Filtering (VF)` | "Runs after ranking, per viewer, per post" |
| Allow terminal | — | "Continues toward feed" |
| Interstitial terminal | — | "Delivered, with a tap-through warning" |
| Drop terminal | — | "Removed — never reaches the client, regardless of score" |
| Lane A | `TimelineHome` | "In-network policy" |
| Lane B | `TimelineHomeRecommendations` | "Out-of-network policy — stricter" |
| Side note | — | "Separate mechanism: index-time exclusion — see Diagrams 02, 05" |

## Responsive versions

**Desktop full version:** header pairing, full funnel-and-fork, both policy lanes with
their comparison strip, index-time side note all visible at once.

**Mobile simplified version:** identical structure, stacked narrower — nothing collapses
here, since this diagram is already minimal. The comparison strip's two-column table
becomes two stacked cards instead of side-by-side columns; that's the only mobile-specific
change.

**Social-card crop:** the funnel-and-fork alone, with the header pairing above it — no
comparison strip, no side note. This crop is designed to be the single most-shared image
in the entire project (`../ROADMAP.md` calls D4 "the most shareable diagram in the suite"
directly), so it gets the tightest, cleanest crop of any diagram: header, funnel, fork,
three terminal states, nothing else.

## What this must NOT imply

- That a high RankingScorer score is meaningless.
- That "Allow" guarantees the post reaches the viewer — truncation and BlenderSelector
  still apply afterward (Diagram 01).
- That Interstitial and Drop are two flavors of the same outcome.
- That index-time exclusion and per-request visibility filtering are the same check run
  twice.
- That every out-of-network post gets dropped, or every in-network post gets shown — both
  policies produce all three outcomes.
- **Production-specific:** that the OON lane's "stricter" framing means "less trustworthy"
  or "worse" — the comparison strip's label text is written specifically to foreclose that
  reading without needing a reader to find and read the walkthrough prose first.

## Claim dependencies

`CLAIM_BANK.md` #31, #32, #33, #34, #35, #41, #57.

## Provenance

Master synthesis §9 (the full VF section), §11 (concrete label examples), §16 walkthrough C
(the worked example this diagram's headline scenario is drawn from), §10 (index-time
exclusion, for the side note).
