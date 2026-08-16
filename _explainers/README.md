# X Algorithm Explainers

This is the public-explainers layer built on top of a completed technical analysis of
`xai-org/x-algorithm`'s public source snapshot. It exists to turn that analysis into
diagrams, guides, and plain-language content that a non-specialist reader can actually
use — without distorting what the analysis found.

## Status of the underlying analysis

The analysis is **complete and frozen**. It lives on branch `analysis/final-residuals`,
tagged `analysis-complete-2026-08-16`, pointing at commit `a895c97d8a86e18351bd5f317f913df93cb3d299`.

That analysis read one upstream source snapshot: `xai-org/x-algorithm` commit `c65aa179`
(2026-08-15). Nothing in this explainers project re-reads source code. If a claim needs
checking, it gets checked against the master synthesis below, not against
`phoenix/`, `home-mixer/`, or any other source directory.

The master explanation is:

**`_analysis/synthesis/HOW_FOR_YOU_WORKS.md`**

Supporting documents:

- `_analysis/synthesis/GLOSSARY.md` — quick-reference term definitions
- `_analysis/synthesis/ADVERSARIAL_REVIEW.md` — the independent review that caught and
  fixed several errors in the master document before it was finalized
- `_analysis/residuals/PHOENIX_SERVING_AND_RETRIEVAL.md` — the final residual pass that
  closed out remaining questions about Phoenix's serving and retrieval mechanics

Earlier forensic and rapid-understanding reports (`_analysis/rapid/`, and the full-audit
`S00`–`S02` reports referenced throughout the master synthesis) remain available for
provenance, but explainers should not derive from them directly — they were superseded
by the master synthesis specifically so that later work wouldn't need to re-interpret raw
findings independently.

## What `_explainers/` is

A workspace for derivative public content: diagrams, guides, myth-busting pieces, FAQs,
and (eventually) polished visual assets — all traceable back to specific sections of the
master synthesis.

## What `_explainers/` is NOT

- **Not a second analysis.** Nothing here should be produced by reading source code
  directly. If a claim can't be traced to the master synthesis or its named supporting
  documents, it doesn't belong here yet — go get it added to the master synthesis first,
  through the analysis process, not by writing around it here.
- **Not authoritative over the master.** The explainers are **derivative content**. They
  do not supersede `_analysis/synthesis/HOW_FOR_YOU_WORKS.md`. If an explainer ever
  conflicts with the master explanation, **the explainer is wrong and gets corrected** —
  not the other way around.
- **Not a place to modify `_analysis/`.** `_analysis/final-residuals`, everything under
  `_analysis/`, and the analyzed source code are read-only from this branch's
  perspective. If something in the master synthesis looks wrong while writing an
  explainer, that's a stop-and-report situation, not a same-branch fix.

## The three-layer reading model

Explainers content is written for three different amounts of reader attention:

**QUICK** — the idea in a few minutes. For someone who wants a correct mental model
without technical depth. Trades precision for speed, but never trades away correctness —
a QUICK piece can be incomplete, but not wrong.

**GUIDE** — meaningful technical understanding. For someone willing to spend 15–20
minutes to actually understand a subsystem: how retrieval works, how ranking works, how
visibility filtering works. Precise, but doesn't require reading source.

**MASTER** — `HOW_FOR_YOU_WORKS.md` itself. The full source-grounded explanation, with
every hedge, caveat, and evidence boundary intact. The final word.

Below MASTER sits the evidence layer this project doesn't rewrite: the rapid and forensic
research reports, and beneath those, the source snapshot itself.

```
Public quick explanation   (QUICK)
        ↓
Detailed guide              (GUIDE)
        ↓
Master synthesis            (MASTER — HOW_FOR_YOU_WORKS.md)
        ↓
Research reports            (rapid/, forensic S00-S02 — provenance only)
        ↓
Source snapshot             (c65aa179 — read-only, not re-interpreted here)
```

Every future artifact — a graphic, a tip, an FAQ entry, an article — links **upward**
toward the master synthesis for its facts. It does not independently reinterpret the
source snapshot at the bottom. That's what keeps thirty pieces of derivative content from
slowly drifting into thirty slightly different, uncoordinated claims about how the system
works.

## Where to go next

- `ROADMAP.md` — the full artifact plan: what's being built, in what order, for whom
- `CONTENT_MAP.md` — which master-synthesis section backs which planned artifact
- `EDITORIAL_RULES.md` — the evidence-class system every claim must be checked against
- `CLAIM_BANK.md` — a reusable library of pre-checked safe claims and their unsafe
  counterparts
- `VISUAL_LANGUAGE.md` — the semantic vocabulary the diagrams use
- `diagrams/` — six source-grounded diagram wireframes
