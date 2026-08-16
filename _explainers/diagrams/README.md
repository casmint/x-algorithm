# Diagram Suite

Six semantic wireframes, layered so a reader can start broad and zoom into whichever
subsystem they care about. These are wireframes — Mermaid sketches that get the
relationships right — not finished visual design. See `../VISUAL_LANGUAGE.md` for the
semantic vocabulary they all share, and `../CONTENT_MAP.md` for exactly which master-
synthesis sections back each one.

## The six diagrams

**01 — Full For You pipeline** (`01-for-you-pipeline.md`)
The whole-system map. Start here. Shows the complete path from opening the app to
receiving a response, with every later diagram's subject visible as a single box or
stage in this one.

**02 — Retrieval sources** (`02-retrieval-sources.md`)
Zoom into the "candidate sources" stage of diagram 01: all seven retrieval mechanisms,
what each one actually does, and how `phoenix-rankall`'s index-admission layer relates to
request-time search.

**03 — Ranking stack** (`03-ranking-stack.md`)
Zoom into the "scoring" stage of diagram 01: Phoenix's predictions, RankingScorer's
weighted sum, the network/diversity/cold-start adjustments, and VMRanker's optional DPP
layer.

**04 — Ranking vs. Visibility Filtering** (`04-ranking-vs-visibility.md`)
A conceptual diagram, not a pipeline zoom-in: the single most important distinction in
the whole system, made as simple and memorable as it can be made without becoming wrong.
A post can score highest and still never be shown.

**05 — Safety/reputation signal flow** (`05-safety-label-flow.md`)
Zoom into where visibility filtering's inputs come from: the detector → enforcement →
label → consumer chain, and the codenames (Agatha, BDSM, Grox, Botmaker/Scarecrow,
Gizmoduck) that make this ecosystem hard to talk about without a map.

**06 — Phoenix two-tower retrieval** (`06-phoenix-two-tower-retrieval.md`)
Zoom into the model-side mechanics diagram 02 gestures at but doesn't unpack: how the
shipped reference retrieval model actually turns a viewer and a candidate post into
comparable vectors, and what part of that process is checkpoint-dependent and therefore
unknown from this snapshot.

## How they're layered

```
        01 — Full pipeline (whole system)
       /        |         \
   02          03          04
retrieval    ranking    ranking vs.
sources      stack      visibility
   |            |
   06        (05 attaches to both
Phoenix      02's index-admission
two-tower    safety check and 04's
retrieval    visibility-filtering
             label inputs)
```

Diagram 05 isn't a strict child of one parent — safety/reputation signals feed both
retrieval (index-time exclusion, in diagram 02) and visibility filtering (per-request
labels, in diagram 04). It's presented as its own diagram specifically because the
codename ecosystem is dense enough to need a dedicated map, not because it's a clean
zoom-in on a single box.

## Diagram rules

- **One main takeaway per diagram.** If a diagram needs two headlines, it's two diagrams.
- **Do not cram the whole repository into one image.** Diagram 01 is the widest, and even
  it deliberately pushes safety-system internals out to diagram 05 and retrieval-model
  internals out to diagram 06.
- **Distinguish request-time and background systems explicitly**, using the node-type
  vocabulary in `../VISUAL_LANGUAGE.md` (solid vs. dashed borders).
- **Distinguish local Home Mixer components from remote dependencies explicitly** — this
  was a real error in an earlier draft of the master synthesis's own glossary
  (`ADVERSARIAL_REVIEW.md` AR-001), so diagrams need to get this right visibly, not just
  in prose.
- **Mark optional/conditional paths** (dashed arrows, gate badges) — don't draw a disabled-
  by-default source or a conditionally-active DPP layer with the same visual weight as an
  always-on stage.
- **Do not present checked-in defaults as live facts.** Any specific number gets the
  checked-in-default badge from `../VISUAL_LANGUAGE.md`.
- **Every diagram gets provenance** — a link back to the exact master-synthesis
  section(s) it derives from.
- **Every diagram gets a "What this does NOT mean" section** — the likely misreadings a
  simplified picture invites, stated explicitly so a reader can't assume a missing detail
  means that detail doesn't exist.

## Required file format

Every file in this directory follows this structure:

```
# Title

## One-sentence takeaway

## Audience

## Question this answers

## Semantic wireframe
(Mermaid, following ../VISUAL_LANGUAGE.md)

## Walkthrough

## Required labels/callouts

## What this diagram intentionally omits

## What this diagram must NOT imply

## Provenance

## Future visual treatment
```
