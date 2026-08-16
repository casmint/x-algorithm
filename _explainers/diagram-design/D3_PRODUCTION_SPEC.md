# D3 Production Spec — Ranking Stack

Source wireframe: `../diagrams/03-ranking-stack.md` (unchanged this phase — see
`README.md`'s Part 1 review). Built from `ART_DIRECTION.md` and `COMPONENT_LIBRARY.md`.

**Primary takeaway:** Phoenix predicts reactions; RankingScorer turns those predictions
into a score. This is the diagram with the highest misinformation risk in the suite —
every decision below is subordinate to getting that risk right.

---

## Required structure

1. **Candidate post** [terminal start node] — a post that survived pre-scoring filters.
2. **Phoenix predictions** [component 5, model card] — outputs a cluster of prediction
   pills [component 10], one per representative head, not all ~24:
   - Positive: Favorite, Reply, Repost, Share, Follow author.
   - Negative: Not interested, Block, Mute, Report.
   - Other: Click, dwell, video.
   Each pill carries the `PREDICTED` qualifier in its label treatment (bold/caps per
   `ART_DIRECTION.md`'s typography table) — this is the single most important word on the
   diagram after the warning callout itself.
3. **RankingScorer** [component 2, Home Mixer local card] — the conceptual formula, set as
   large editorial-voice display type, not buried in a caption:

   > **score = Σ (predicted outcome × configured weight)**

4. **Adjustments** [component 1, secondary-tier pipeline stage, one sub-block] — in fixed
   order: OON/network adjustment, mutual-follow boost, author diversity decay, cold-start
   floor. Rendered as a single visually subordinate strip beneath the main RankingScorer
   node (per the wireframe's existing `ADJDETAIL` grouping) — foreground for the spine
   (predict → score → select), secondary for the adjustment detail.
5. **VMRanker** [component 3, remote service card] — optional diversity selection (DPP).
6. **Top K** [component 9, later-stage pool] — zoom-out link back to Diagram 01.

## Three different values

This is the highest-value visual correction this phase makes to the D3 wireframe's
existing structure (see `README.md`'s D3 review notes) — the wireframe's prose already
knows these are three different numbers; the production spec makes that a shape
distinction, not just a text one, using component 10's three variants:

| Value | Shape | Color | Label discipline |
|---|---|---|---|
| Phoenix's prediction vector | Cluster of small pills | Role 4 (ranking/score), low-saturation | Always plural framing: "predictions," never "the prediction." |
| RankingScorer's scalar score | One larger pill | Role 4, full saturation | Always singular: "one score," with "PREDICTED" never attached to this pill — it's a computed number, not a prediction itself. |
| VMRanker's selection result | The same scalar pill, either filled (kept, exact original value) or hollow with a "0" label (not selected) | Role 4 fill (kept) / no fill, ink outline only (zeroed) | Never a new color or a new pill size — DPP doesn't recompute, it only masks (`CLAIM_BANK.md` #27). |

No two of these three ever share a shape at the same size. A reader who only looks at
shapes, never reading a single label, should still be able to tell "several small things
became one thing, and that one thing either survived or got zeroed."

## Warning callout

Mandatory, non-optional, rendered with component 15 (warning/correction callout) at
maximum visual weight — the single largest, boldest text block in the entire diagram
suite, positioned directly beneath the RankingScorer formula so it can't be skimmed past.

**Primary line (large, bold, first):**
> These weights multiply **predicted probabilities**, not raw counts of likes, replies, or
> reports.

**Secondary line (smaller, muted, second, optionally struck through per component 15's
myth-subordination rule):**
> ~~There is no literal exchange rate such as "1 report = 468 likes."~~

The ordering is deliberate and non-negotiable per the phase brief: the myth text must never
be visually louder than the correction. If a design pass ever produces a version where the
struck-through myth reads more prominently than the bold primary line (larger type, higher
contrast, brighter color), that version is wrong regardless of how it tests for engagement
— this is the project's single most important editorial guardrail (`EDITORIAL_RULES.md`'s
practical-advice policy) rendered as a layout constraint, not just a writing rule.

## Numeric weights

**Primary diagram: no detailed weight table.** The RankingScorer node shows the conceptual
formula only.

**Optional inset**, separated from the main flow by its own bordered container (not
floating loose in the canvas), containing a handful of representative checked-in examples
— favorite, report, reply — each paired with its predicted-probability context inline,
never shown as a bare number:

> `CHECKED-IN DEFAULTS — NOT CONFIRMED LIVE VALUES`
> Favorite: weight 0.5, applied to a typically small predicted probability.
> Report: weight −234.0, applied to a typically far smaller predicted probability.
> Reply: weight ~10× favorite's, before any mutual-follow boost.

The inset badge is the `CHECKED-IN DEFAULT` badge from `COMPONENT_LIBRARY.md` item 13, set
at full size (not the micro/inline size), since this inset is the one place in the diagram
where getting that distinction missed would directly enable the exact myth the warning
callout exists to prevent. If a numeric weight ever appears anywhere on this diagram
without its predicted-probability context immediately adjacent, that's a defect — per the
phase brief, numbers without that context are exactly what invites "exchange rate" myths.

## DPP

Rendered conceptually, not as a guaranteed step:

- VMRanker's card shows a dashed-outlined sub-branch (component 11, optional-path marker)
  labeled `DPP — if server flag is on (checked-in default: off)`, separate from the
  always-taken "echo scores unchanged" path.
- A small illustrative panel, clearly captioned "illustrative, not a real ranked set":
  five similar high-scoring pills → a diversity-selector icon → two or three pills survive,
  the rest zero out. This matches the wireframe's own future-treatment note and the phase
  brief's suggested composition directly.
- Both VMRanker's client-request default (Home Mixer asks for DPP every call) and the
  server's own default (`--dpp-enabled=false`) get separate, individually labeled badges —
  never merged into one "DPP default" badge, since conflating them was a documented error
  in an earlier draft (`CLAIM_BANK.md` #28).

## Hierarchy

- **Foreground:** the predict → score → select spine; the warning callout; the
  three-different-values shape distinction.
- **Secondary:** the four adjustments sub-block; the DPP conditional branch.
- **Tertiary:** the optional weight-table inset (present but visually subordinate to the
  spine and the warning).

## Copy

| Element | Component name | Subtitle |
|---|---|---|
| Phoenix | `Phoenix` | "Predict likely reactions" |
| Prediction pills (representative) | — | `PREDICTED: favorite · reply · report · ...` |
| RankingScorer | `RankingScorer` | "Combine predictions into one score" |
| Adjustments | `Adjustments` | "Fixed order, checked-in defaults" |
| VMRanker | `VMRanker` | "Optional diversity selection" |
| Top K | `Top 50` | "Kept by score — see Diagram 01" |

## Responsive versions

**Desktop full version:** full spine, adjustments sub-block visible, warning callout at
full size, optional weight inset present.

**Mobile simplified version:** spine intact vertically; adjustments sub-block collapses to
one line reading `4 adjustments applied (OON, mutual-follow, diversity, cold-start)` with
a tap/expand affordance implied; warning callout keeps its full text and relative
dominance (it does not shrink proportionally with everything else — this is the one
element explicitly exempted from mobile compression); the weight inset is dropped
entirely on mobile rather than compressed, since a compressed weight table is exactly the
"numbers without context" failure mode this spec warns against.

**Social-card crop:** the warning callout *is* the card — no pipeline spine at all. Just
the primary/secondary two-line warning, set at maximum type scale, on its own. This is the
diagram's single most shareable, single most important sentence, and the social crop
should carry nothing else that could dilute it.

## What this must NOT imply

- That weight ratios are exchange rates between raw engagement events.
- That DPP "usually" runs.
- That the cold-start floor guarantees a final feed position.
- That RankingScorer's output is "the algorithm's opinion" of the post in any absolute
  sense.
- That Phoenix's ~24 predictions are all equally weighted or consequential.
- **Production-specific:** that the three value-types (prediction cluster / scalar /
  selection result) are interchangeable just because they're all rendered as pills — the
  shape distinctions in "Three different values" above are the whole point of using pills
  at all.
- **Production-specific:** that the optional weight inset's example numbers are
  representative of the full 14-value table, or are more real/current than any other
  checked-in default in the project.

## Claim dependencies

`CLAIM_BANK.md` #15, #16, #17, #18, #19, #20, #21, #22, #23, #24, #25, #26, #27, #28, #29,
#30, #51, #57.

## Provenance

Master synthesis §5 (Phoenix's prediction structure), §6 (RankingScorer's formula, full
weight table, and its own explicit warning against reading it as an exchange rate), §7
(the four adjustments, in order), §8 (VMRanker/DPP, both defaults).
