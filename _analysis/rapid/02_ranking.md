# Ranking — How Candidates Become an Ordered Feed

Rapid-track macro covering S05 (Phoenix ranking semantics), S08 (VMRanker/diversity/
reranking), and only the S17 parameters that materially change ranking behavior, per
`_analysis/rapid/README.md`. Builds on `_analysis/rapid/01_retrieval.md` (candidate pool)
and S01's orchestration model; does not re-derive them.

## Plain-English summary

Once the seven retrieval sources have produced a merged pool of candidates, three
scorers run in strict sequence — `PhoenixScorer`, then `RankingScorer`, then `VMRanker`
— and a single field, `PostCandidate.score`, is what ultimately decides the order.
Understanding ranking means understanding what each of the three writes into that field
and whether the next stage overwrites it or leaves it alone.

**`PhoenixScorer`** does no ranking math itself. It sends the candidate pool plus the
viewer's recent action history (`scoring_sequence`) to an external model-serving cluster
(prod gRPC, with an optional xDS path gated by a decider), and writes back one number per
candidate per predicted action — "how likely is this viewer to favorite this post,"
"how likely to reply," "how many seconds will they dwell on it," and about twenty more —
into a `phoenix_scores` struct on the candidate. If the viewer has no scoring sequence at
all, `PhoenixScorer` short-circuits and writes empty predictions for everyone rather than
failing; if the whole model call fails, no predictions are written at all and every
candidate keeps whatever it had before (nothing, on a fresh request).

**`RankingScorer`** is where the actual point-scoring happens, entirely inside Home
Mixer, no external call. For each candidate it multiplies every predicted-action
probability by a checked-in weight (favorite × 0.5, reply × 5.0, report × -234.0, and so
on for roughly two dozen heads), sums the positive contributions and the negative ones
separately, and combines them into one number. It's important to be precise about what
that number means: **these weights multiply a predicted probability, not a raw count of
past engagements.** A "one report = 468 likes" style statement is a misreading — reports
are astronomically rarer than favorites in the underlying data, so a report's weight has
to be large simply for the model's *predicted probability* of a report (which will be a
tiny fraction, not 1.0) to move the score at all. The magnitude of a weight is not an
exchange rate.

After the weighted sum, `RankingScorer` layers on several independent adjustments: an
**author-diversity discount** that shrinks a candidate's score the more posts from the
same author already rank above it in this batch (asymptoting toward a floor, not zero);
an **out-of-network discount** (0.75× by default) applied to anything not from a followed
author — and, by current checked-in default, *also* applied to in-network replies and
retweets, which is a genuinely non-obvious detail; a **bidirectional-follow boost**
mechanism that can add extra weight to the reply and dwell heads specifically for
original (non-reply, non-retweet) posts from someone who mutually follows the viewer —
under checked-in defaults this actually adds +15.0 to the reply weight but +0.0 to the
dwell weight, so today only the reply boost has any effect; and a **cold-start
mechanism** that, once per request, finds the best eligible low-follower/low-impression
post and raises its score to at least whatever score currently occupies the 16th-ranked
slot in this batch. That is a floor on the *pre-adjustment* score at that point in the
pipeline, not a guarantee of a final feed position — author-diversity and OON
adjustments that run afterward, and VMRanker after that, can still move the boosted
candidate up or down from wherever this floor placed it.

There is also a second, entirely different scoring mode — **dwell-regret** — selectable
by a `ValueModelMode` parameter, plus a **gated** variant that uses a small linear model
over the viewer's recent-activity features to decide, per request, whether to route that
viewer into the new dwell-regret formula or the classic weighted-sum formula. Under the
checked-in default (`ValueModelMode = "weighted"`), neither activates — every request
uses the classic weighted-sum path unless production configuration overrides that
default, which this snapshot cannot see.

**`VMRanker`** is the final stage. It runs as a separate Rust service
(`vm-ranker/`, whose implementation — including its DPP diversity algorithm — is
checked into this repository, not external or unpublished, correcting an earlier
pass through this material). Home Mixer sends it the already-scored candidate list
(again with an optional xDS-then-DNS fallback path) along with diversity parameters
(DPP theta and a max rank depth). Under the checked-in default value model
(`"dpp"`), the server's DPP implementation is not a second predictive model at all —
it's a **selection layer**: it sorts candidates by the score Home Mixer already sent,
keeps up to a configured pool size, builds a similarity kernel from an embedding
lookup, greedily selects a diverse top-`k` from that pool, and returns each candidate
either with its *original, unchanged* incoming score (if selected) or a score of
exactly `0.0` (if not selected). Home Mixer's own logic still does the same thing
either way — the returned value **directly replaces** `RankingScorer`'s score, not
supplements it — but under DPP mode, the "replacement" is normally either the prior
score verbatim or zero, not an opaque model-generated number. Under a different,
non-default value-model setting (`"author_diversity"`, only reachable if MPN scoring
is also on, which defaults off), VMRanker's response is instead used as a
*multiplier* on RankingScorer's raw positive/negative parts rather than a
replacement — two structurally different ways the same field ends up populated,
gated by configuration. If VMRanker's whole call fails, Home Mixer does not fail the
request or blank the score — it simply skips VMRanker's `update()` and every
candidate keeps `RankingScorer`'s score untouched. This closes S01's open
field-level question (S01-F012) directly: yes, VMRanker overwrites, and yes, its
failure leaves the prior stage's score exactly where it was. What remains genuinely
external is not the algorithm but the *runtime state*: the server's DPP path is
gated behind a `--dpp-enabled` flag whose checked-in default is `false`, and its
similarity kernel depends on an embedding store this snapshot doesn't populate —
so whether DPP selection actually runs in production, and against what embedding
data, is unknown even though the code that would run it is fully public.

The very last step, `TopKScoreSelector`, does nothing clever — it sorts candidates
descending by whatever ended up in `.score` (missing scores sort last) and keeps the top
50. Those 50 then go through visibility/safety post-selection filtering (S01), and the
survivors are truncated to 35 for the final organic result — meaning it is possible,
though not typical, for fewer than 35 organic posts to reach S02's blending stage if
enough of the top 50 get filtered out downstream.

A recurring, easy-to-miss theme: **cache mode does not mean "replay the old ranking."**
`PhoenixScorer` explicitly skips on `has_cached_posts` (reusing the stored predictions),
but neither `RankingScorer` nor `VMRanker` checks `has_cached_posts` in their `enable()`
gates at all — they simply run again, every time, using whatever feature-switch weights
are active *right now*, against the *stored* Phoenix predictions from up to 180 seconds
ago. A weight change deployed in that window can change a cached response's order even
though no new model inference happened.

Finally: this report cannot confirm what happens in current production, only what the
checked-in source does. Every weight, mode selector, and gate cited here has a specific
checked-in default; whether that default is what's actually being served is outside what
this snapshot can show (consistent with every prior pass in this repository).

## Score pipeline at a glance

```
PostCandidate (from any of the 7 retrieval sources, no score field set)
        |
        v
  PhoenixScorer  (external model call; sequential, stage 1 of 3 scorers)
    writes: phoenix_scores (~26 predicted-action fields), prediction_request_id,
            last_scored_at_ms
    skip-if: has_cached_posts (reuses stored phoenix_scores) | killed by decider
    on missing scoring_sequence: writes empty predictions for every candidate (not Err)
    on model-call failure: writes nothing (Err) -> phoenix_scores stays at prior value
        |
        v
  RankingScorer  (pure local computation; stage 2 of 3)
    reads:  phoenix_scores, in_network, in_reply_to_tweet_id/retweeted_tweet_id,
            is_mutual_follow_author, author_followers_count/view_count/fav_count,
            slate_context (cache mode only), current feature-switch weights
    writes: weighted_score (pre-adjustment), score (post diversity/OON/cold-start),
            slate_context, mpn_parts (MPN mode only)
    skip-if: !EnableRanking
        |
        v
  VMRanker  (separate service, checked-in DPP-selection algorithm; stage 3 of 3)
    reads:  score, phoenix_scores (subset), slate_context, weighted_score/head_weights
            (both gated behind VMRankerSendHeadWeights, default off)
    writes: score  <- OVERWRITES with prior score (selected) or 0.0 (rejected) under
                       default "dpp" mode; MULTIPLIES RankingScorer's pos/neg parts
                       under non-default "author_diversity" + MPN mode
    skip-if: !EnableVMRanker; server-side DPP itself further gated by --dpp-enabled
             (checked-in server default false) — disabled DPP just echoes input scores
    on whole-call failure: writes nothing -> score stays at RankingScorer's value
        |
        v
  TopKScoreSelector   sort candidates descending by `.score` (missing -> sorts last),
                       keep top 50 (TOP_K_CANDIDATES_TO_SELECT)
        |
        v
  post-selection hydrators + filters (VF/visibility, S01) act on those 50
        |
        v
  truncate to RESULT_SIZE = 35  ->  organic ranked result
        |
        v
  ForYouCandidatePipeline's BlenderSelector interleaves with ads/WTF/prompts/etc. (S02)
```

## What Phoenix predicts

`PhoenixScorer` (`home-mixer/scorers/phoenix_scorer.rs:76-116`) builds a prediction
request from the candidate batch plus `query.scoring_sequence` (the viewer's recent
action history, populated upstream by a query hydrator — S01) and
`query.columnar_scoring_sequence`, dispatches it via `PredictionDispatch` (prod client +
optional xDS path, same external-crate pattern as retrieval's `RetrievalDispatch`), and
maps the response back onto each candidate by tweet ID
(`predictions.candidate_scores(&c.get_original_tweet_id())`). The model itself — its
architecture, training data, and how it represents viewer history/candidate
text/media/embeddings — lives in `phoenix/xrex/` (a large JAX/PyTorch-style training and
serving stack: `models/recsys_model.py`, `recsys_attention.py`,
`recsys_two_tower_model.py`, etc.) and was **not deep-read here**, per this macro's
"what it consumes and predicts, not every training utility" mandate (S06's territory).
What *is* directly established from the serving-side call site: the model is invoked
per-request with a viewer identity, a sequence of recent actions, and a batch of
candidate posts, and returns one scalar per candidate per action head. Whether outputs
are true probabilities, logits, or regressed continuous values is **head-dependent and
not verified per-head from this snapshot** — the consuming code treats them uniformly as
`f64` and multiplies by a weight, which is consistent with probabilities/continuous
values but does not itself prove calibration. `dwell_time`/`click_dwell_time`/
`active_secs_5m_residual_norm` are explicitly continuous (durations/normalized activity),
not action probabilities — confirmed by their units-based names and their un-weighted use
alongside probability-style heads in the same summation.

**New-user / short-history behavior at the model-cluster level**: `PhoenixScorer`
resolves which inference cluster to query per request
(`phoenix_scorer.rs:24-60`) — if `query.scoring_sequence`'s action-history length is
below `PhoenixRankerNewUserHistoryThreshold` (checked-in default `0`, meaning this path
is **never triggered under current defaults** — see finding below), it routes to a
separate `PhoenixRankerNewUserInferenceClusterId` cluster (default
`"Experiment1Fou"`, i.e. currently identical to the standard cluster) instead of the
normal one. This mirrors the identical pattern already established in retrieval for
`PhoenixSource`'s new-user retrieval-cluster routing.

## Model inputs

Directly visible from the Rust-side request builder
(`home-mixer/util/phoenix_request.rs`, not independently deep-read beyond its call
sites) and the fields threaded into it:

- **Viewer/history**: `query.scoring_sequence` (recent action sequence, hydrated
  upstream), `query.user_id`, `query.user_features` (followed-user count, follower
  count — used by `RankingScorer`/`vqv_weight`, not confirmed as a *model* input beyond
  that consuming code).
- **Candidate-post inputs**: whatever `build_prediction_request` packs per candidate
  (tweet ID, author ID, and candidate-side fields available on `PostCandidate` at that
  point in the pipeline — hydrated by the 12 candidate hydrators, S01). The exact set of
  fields sent to the model versus fields used only downstream in `RankingScorer` was
  **not independently traced field-by-field** in `phoenix_request.rs` — routed to a
  follow-up if a full training/serving audit is ever performed (S06).
- **Text/media/embedding inputs**: `phoenix/xrex/models/recsys_feature_prep.py`,
  `recsys_embedding.py`, and `multimodal_retrieval.rs` (serving crate) suggest
  multimodal/embedding features are consumed by the underlying model, but this was
  **not traced from the Home Mixer request-construction side** — UNKNOWN whether
  Home Mixer's per-request call sends raw text/media or only IDs the serving side
  resolves internally.

## Prediction heads and checked-in weights

All heads below are read directly from `RankingScorer::compute_weighted_parts`
(`home-mixer/scorers/ranking_scorer.rs:460-552`) and their weights from
`home-mixer/params/param.rs`. **Weights multiply predicted probabilities/continuous
values, not raw engagement counts — do not read weight ratios as event-count exchange
rates** (this caution is stated directly in the source itself,
`ranking_scorer.rs:418-446`, and repeated here deliberately).

| Head | Meaning | Checked-in weight | Contribution |
|---|---|---|---|
| `favorite_score` | P(favorite) | 0.5 | positive |
| `reply_score` | P(reply) | 5.0 (+15.0 boost for eligible mutual-follow original posts, see below) | positive |
| `retweet_score` | P(retweet) | 1.0 | positive |
| `photo_expand_score` | P(photo expand) | 0.05 | positive |
| `video_open_score` | P(video open) | 0.05 | positive |
| `click_score` | P(click) | 0.4 | positive |
| `open_link_score` | P(open external link) | 0.2 | positive |
| `profile_click_score` | P(profile click) | 0.0 (effectively disabled) | positive (currently no-op) |
| `vqv_score` | P(video quality view) | 0.05, but **zeroed** if the viewer has ≥10,000 followers or the candidate's video is ≤10s (`MinVideoDurationMs`) | positive, conditionally gated |
| `share_score` | P(share) | 2.0 | positive |
| `share_via_dm_score` | P(share via DM) | 5.0 | positive |
| `share_via_copy_link_score` | P(share via copy-link) | 20.0 (highest positive weight) | positive |
| `dwell_score` | P(dwell, discrete head) | 0.0 (disabled; superseded by the continuous `dwell_time`/`cont_dwell_time_weight`) | positive (currently no-op) |
| `quote_score` | P(quote) | 5.0 | positive |
| `quoted_click_score` | P(click on a quoted post) | 0.05 | positive |
| `quoted_vqv_score` | P(video quality view on a quoted post's video) | 0.0 (disabled by default) | positive (currently no-op) |
| `dwell_time` (continuous) | predicted watch/dwell duration | `ContDwellTimeWeight = 0.004`, multiplicatively boosted by `post_unexplored_score` if `EnableMultiplicativePostUnexplored` (default off) | positive |
| `click_dwell_time` (continuous) | predicted dwell duration following a click | `ContClickDwellTimeWeight = 0.0` (disabled by default); if `EnableClickDwellLowFavRatePenalty` were on (default off), this term is scaled down for candidates with a low predicted favorite rate | positive (currently no-op) |
| `active_secs_5m_residual_norm` (continuous) | normalized post-impression active-time signal | 0.0 (disabled by default) | positive (currently no-op) |
| `follow_author_score` | P(follow the author) | 4.0 | positive |
| `post_unexplored_score` | P(this is a novel/unexplored kind of post for the viewer) | 0.02 additive by default (or multiplicative on `dwell_time` if the alternate mode is enabled); can be zeroed for OON candidates if `PostUnexploredWeightInNetworkOnly` (default **true**) | positive |
| `not_interested_score` | P(mark not interested) | -43.2 | negative |
| `block_author_score` | P(block the author) | -31.2 | negative |
| `mute_author_score` | P(mute the author) | -58.8 | negative |
| `report_score` | P(report) | **-234.0** (largest-magnitude weight in the table) | negative |
| `not_dwelled_score` | P(scroll past without dwelling) | -0.02 (smallest-magnitude negative weight) | negative |

Two heads named in the task's checklist — **"quote" and "quoted VQV" are present and
weighted as above**; a distinct **"quoted click" head exists separately from a plain
"click" head** (both weighted, at 0.05 and 0.4 respectively). No `PhoenixScores` field
resembling a raw "post unexplored" *binary* flag was found — it is a continuous
predicted-probability-shaped score like the others. The canonical, complete field list of
`PhoenixScores` itself is defined in an external crate
(`xai_candidate_pipeline::component_library::models`, re-exported at
`home-mixer/models/candidate.rs:4`) — this table lists every field this repo's own code
was observed to read, not a verified-complete enumeration of the struct.

## RankingScorer

Deep-read in full (`home-mixer/scorers/ranking_scorer.rs:1-910`; lines 912-1708 are
`#[cfg(test)]` and were used to verify behavior, not read as spec).

**Default mode — weighted sum** (`ValueModelMode = "weighted"`, the checked-in default):

```
for each head h:  term_h = weight_h * predicted_h        (Self::apply, L447-449)
pos = sum of positive terms;  neg = sum of |negative terms|   (L542-550)
combined = pos - neg
weighted_score = offset_score(combined)                        <- stored, pre-adjustment
```

`offset_score` (`ranking_scorer.rs:554-562`):
```
if total_sum(all weights) == 0:      combined.max(0)
elif combined < 0:                    (combined + negative_sum) / total_sum * 0.001
else:                                  combined + 0.001
```
`total_sum`/`negative_sum` are precomputed once from the weight set
(`ScoringWeights::from_params`, L105-128). Plain-English: a candidate whose weighted
sum is net-positive gets that sum plus a small constant (`NEGATIVE_SCORES_OFFSET = 0.001`,
`params/config.rs:40`); a candidate whose negative signal dominates gets compressed into
a small value near zero rather than staying deeply negative. The precise motivation for
this specific offset/compression shape is not stated in source — **STRONG_INFERENCE**
that it keeps scores in a comparable, mostly-positive range for downstream consumers
(selector, VM ranker, logging) rather than allowing unbounded negative values, not
**DIRECT** since no comment states the intent.

From `weighted_score`, three more adjustments produce the final `.score`
(`ranking_scorer.rs:851-901`, non-MPN path):
```
adjusted   = author_cold_start.apply(weighted_score)      (one candidate/request, see below)
diversity  = adjusted * author_diversity_multiplier(k)     if EnableAuthorDiversity
final      = diversity * OonWeightFactor                   if oon_applies(candidate)
```
`author_diversity_multiplier(k) = (1 - floor) * decay^k + floor` (L643-645), where `k` is
how many higher-ranked candidates from the same author already appear in this batch
(computed from a fresh rank-ordering of the pre-diversity scores, `compute_slate_contexts`,
L647-678). Checked-in: `decay = 0.5`, `floor = 0.25` — first post from an author: no
discount (k=0 → 1.0); second: ×0.625; third: ×0.4375; converging toward the 0.25 floor,
never fully zeroing an author out.

**MPN mode** (`EnableMpnScoring`, checked-in default **off**) restructures the same
`pos`/`neg` parts: instead of applying diversity/OON to the *final* offset score, it
computes a single combined `scalar_multiplier` (diversity × OON, if applicable) and
applies it directly to `net = pos - neg` *before* offsetting — `scaled = net >= 0 ?
multiplier * net : net` (negative nets are never discounted by diversity/OON, only
positive ones are) — then stores the raw `pos`/`neg`/`multiplier` in a new `mpn_parts`
field on the candidate (`ranking_scorer.rs:819-848`). This `mpn_parts` payload exists
specifically so `VMRanker` can later re-derive a comparable score from a VM-returned
"fold" ratio (see VMRanker section) — MPN mode and VMRanker's `"author_diversity"` value
model are a matched pair, not independent features.

**Dwell-regret modes** (`ValueModelMode = "dwell_regret_sigmoid"`, or
`"gated_dwell_regret"` when the gate model routes a viewer into it — both **off** under
checked-in defaults, since default `ValueModelMode = "weighted"`): a structurally
different, batch-relative formula (`compute_dwell_regret_base_scores`,
`ranking_scorer.rs:564-629`). For each candidate: compute how far above/below the
*request's own batch average* each positive head's prediction sits
(`centered_ratio = p/mean - 1`), weight those by `DwellRegretAlpha*` params and sum;
separately sum negative-head predictions weighted by large negative
`DwellRegretNeg*` constants (default range -8,000 to -60,000 — three orders of
magnitude larger than the weighted-sum mode's negative weights, because this formula
multiplies a *sigmoid-modulated dwell time*, not a bare probability sum); combine via
`modulation = 2 * sigmoid(positive/temperature) * exp(negative.min(0)/temperature)`
(temperature default 10.0) and multiply by the candidate's predicted `dwell_time`
(floored at `DwellRegretDwellFloor = 1.0`). Plain English: this mode scores a candidate
by its predicted watch time, scaled up if its predicted positive-engagement rate is
above this request's own average and scaled sharply down (via the negative
exponential term) if it has meaningful negative-feedback risk — a fundamentally
different shape from the linear weighted sum, not reachable under the checked-in
default `ValueModelMode`.

**Gate model** (`home-mixer/scorers/value_model_gate.rs`, 537 lines, deep-read):
decides whether a viewer gets routed into `gated_dwell_regret` scoring. It's a 19-feature
linear model (`seq_len`, per-action-type recent counts, activity-day counts, follower/
following counts, account age — most log1p-transformed) over the viewer's
`columnar_scoring_sequence`, producing `score = bias + Σ(weight_i * feature_i)`; if
`|score - threshold| <= hysteresis_band` (checked-in `hysteresis_band = 0.0`, so this
never triggers under default), the decision falls back to a stable per-user coin-flip
(`user_id` hashed, parity check) instead of re-deciding every request — avoiding
flip-flopping for borderline users. Checked-in `threshold = -0.634264`, `bias =
1.033918`, and a full 19-weight vector are present (`DwellRegretGateWeights`,
`param.rs:560-565`) — but this only matters if `ValueModelMode = "gated_dwell_regret"`,
which is not the checked-in default value of `ValueModelMode`.

## Positive signals

See the weights table above. Notably: `share_via_copy_link` (20.0) and `follow_author`
(4.0) carry among the largest positive weights in the default weighted-sum mode; several
otherwise-present heads (`profile_click`, `dwell` discrete, `click_dwell_time`,
`active_secs_5m_residual_norm`, `quoted_vqv`) are wired but weighted at **0.0** under
checked-in defaults, meaning they contribute nothing to the score right now regardless
of what the model predicts for them — wired-but-neutered, the same pattern flagged
repeatedly in the retrieval report.

## Negative signals

Four discrete negative heads (`not_interested`, `block_author`, `mute_author`, `report`)
plus one small continuous one (`not_dwelled`). Report carries the largest-magnitude
weight in the table (-234.0) — the source code itself explains why directly
(`ranking_scorer.rs:418-446`): reports are far rarer than favorites in the underlying
data, so the weight has to be large simply for the model's *predicted* report
probability — which will itself be a small fraction — to move the score meaningfully.
This is explicitly **not** an exchange rate ("one report cancels N likes" is stated in
the source as a misinterpretation to avoid), and the source also notes (not
independently verified by this macro, but stated as design intent in the comment) that
because recommendations are personalized and an action only counts if it occurred on a
post actually served in Home Timeline, coordinated mass-reporting primarily affects
recommendations shown to similar users, not the reported post's ranking to everyone
uniformly.

## IN vs OON / follow / mutual-follow effects

- **Being followed matters via retrieval, not a ranking bonus per se**: Thunder
  specifically retrieves posts from followed authors (retrieval report); `RankingScorer`
  applies no explicit "is this author followed" bonus beyond the `in_network` flag
  driving the OON discount below.
- **OON discount**: `effective_oon_weight` (`ranking_scorer.rs:710-729`) — non-topic
  requests use `OonWeightFactor` (checked-in **0.75**); topic requests use the steeper
  `TopicOonWeightFactor` (checked-in **0.5**). Applied whenever `c.in_network ==
  Some(false)`.
- **In-network replies/retweets can also be discounted**: `oon_applies`
  (`ranking_scorer.rs:776-783`) additionally applies the OON discount to *in-network*
  candidates if `EnableOonRescoreForInNetworkRepliesRetweets` (checked-in default
  **true**) **and** the candidate is a reply or retweet. This is a genuinely
  non-obvious default: a reply from someone you follow is, by current checked-in
  configuration, scored at the same 0.75× discount as an out-of-network post.
- **Mutual-follow (bidirectional) boost**: `bidirectional_boost_eligible`
  (`ranking_scorer.rs:180-184`) requires the candidate be an *original* post (not a
  reply, not a retweet) from an author the candidate hydration layer marked
  `is_mutual_follow_author == Some(true)` (populated by `BidirectionalFollowHydrator`,
  S01/S00). If eligible, the reply weight gets `+15.0` (on top of the base 5.0 — total
  20.0) and the dwell weight gets `+0.0` (checked-in `BidirectionalFollowDwellWeightBoost
  = 0.0`, i.e. currently a no-op for dwell specifically). **New-user OON near-zeroing
  exists but is currently unreachable**: `effective_oon_weight` special-cases viewers
  under `NewUserAgeThresholdSecs` with ≥5 follows to `NEW_USER_OON_WEIGHT_FACTOR =
  0.00001` (near-total OON suppression) — but `NewUserAgeThresholdSecs`'s checked-in
  default is **0**, meaning no viewer is ever "younger than 0 seconds" and this branch
  cannot fire under current defaults (see finding below).
- **New-user model-cluster routing** (separate from the OON-weight mechanism above):
  `PhoenixRankerNewUserHistoryThreshold`'s checked-in default is also **0**, so the
  short-history-routes-to-a-different-inference-cluster path in `PhoenixScorer` is
  likewise unreachable under checked-in defaults (see "What Phoenix predicts" above).

## Special boosts and penalties

- **Author diversity**: see RankingScorer section — a smooth decay per repeated author
  within the batch, floor 0.25, not a hard cap or exclusion.
- **Author cold start** (`home-mixer/scorers/author_cold_start.rs`, 758 lines,
  deep-read): every scoring pass (both weighted-sum and MPN paths call it), at most
  **one** candidate per request gets boosted. Eligibility: not a reply/retweet, author
  follower count ≤ `ColdStartFollowerCap` (default **1,000**), predicted view count <
  `ColdStartImpressionThreshold` (default **1,000**), post age ≤
  `ColdStartMaxPostAgeSecs`, and (only relevant when `EnableViewerColdStart`'s A/B arms
  are active via `PhoenixMoeCodivertViewerIs{Control,Treatment}`, default both false →
  viewer defaults to the "Holdout" arm) not already ranking in the top
  `LowImpressionsMaxPositionRatio` fraction of nonzero-scored candidates. The chosen
  candidate's score is floored (`effective[best_idx] = effective[best_idx].max(target)`,
  not replaced) at a *score value* — specifically, `cold_start_target` sorts the current
  batch's scores descending and reads off the score sitting at zero-based ranked index
  `ColdStartSlotMin` (checked-in `ColdStartSlotMin=15, ColdStartSlotMax=16`, a
  single-width range that always selects index 15). Selection of *which* candidate gets
  boosted is by raw score (`pick_by_score`) unless `EnableColdStartThompsonSampling`
  (default **off**) enables a Beta-distribution Thompson-sampling pick over
  `view_count`/`fav_count` instead. **This floors one candidate's pre-adjustment score
  to at least what the 16th-ranked candidate currently scores — it does not assign or
  guarantee a final 16th-place feed position.** The floor is applied inside
  `RankingScorer` before author-diversity and OON adjustments run on top of it, and
  before `VMRanker` runs afterward (checked-in default `EnableVMRanker=true`) and can
  replace `.score` outright — either stage can move the boosted candidate materially
  away from wherever this floor initially placed it. This answers "what happens for a
  new/small author's post": under checked-in defaults, at most one such post per
  request gets its score floor raised to a mid-pack level; whether it actually lands
  near the 16th slot in the *final* order depends on what runs after this floor is
  applied.
- **`post_unexplored`**: encourages showing the viewer something outside their normal
  pattern. Two modes: additive (`PostUnexploredWeight = 0.02`, default) or, if
  `EnableMultiplicativePostUnexplored` (default off) is set, it instead *multiplies* the
  continuous dwell-time term by `(1 + post_unexplored_score * alpha)` rather than being
  its own additive term. `PostUnexploredWeightInNetworkOnly` (default **true**) — despite
  its name — actually means the *opposite* of what it sounds like: reading the code
  (`post_unexplored_active_for`, L176-178) it's active `unless` this flag is set *and*
  the candidate is OON, i.e. checked-in default **restricts post_unexplored's bonus to
  in-network candidates only**.
- **Low-favorite-rate click-dwell penalty**: `EnableClickDwellLowFavRatePenalty`
  (default **off**) — when on, scales the click-dwell-time term down for candidates
  whose predicted favorite rate is low relative to a baseline, via a power-law
  multiplier clamped to `[floor, cap]`. Currently inert under defaults since the
  underlying `ContClickDwellTimeWeight` term it modulates is itself 0.0 by default.
- **VQV/video duration rules**: `vqv_weight` (`home-mixer/util/candidates_util.rs:19-40`)
  zeroes the VQV weight entirely if the viewer has ≥10,000 followers
  (`MAX_FOLLOWERS_THRESHOLD`) **or** the candidate's video is at/under
  `MinVideoDurationMs` (10 seconds). `quoted_vqv_weight` applies an analogous duration
  check to quoted-post videos, but only if `EnableQuotedVqvDurationCheck` (default
  **off**) is set — otherwise the raw weight (default 0.0 anyway) is used unconditionally.
- **No explicit age/recency term inside `RankingScorer` itself** was found — recency
  pressure comes entirely from the universal 48h `AgeFilter` upstream (retrieval report)
  and from whatever the model itself learned to weight recency into its predictions, not
  from an explicit scalar in this file.

## VMRanker and diversity

Deep-read `home-mixer/scorers/vm_ranker.rs` in full (227 lines).

**What Home Mixer sends** (`build_request`, L128-227): per candidate — tweet/author ID,
`in_network`, is-reply/is-retweet flags, author follower count, a `vqv_ineligible` flag
(same 10k-follower/duration logic as `RankingScorer`'s VQV gate), the current `.score`,
a *subset* of `phoenix_scores` (the "core" ~20 heads unconditionally; `video_open`,
`open_link`, `quoted_vqv`, `post_unexplored`, `active_secs_5m_residual_norm` only if
`VMRankerSendHeadWeights` is on, checked-in default **off**), the candidate's
`slate_context` (author-repetition rank info), and — also gated behind
`VMRankerSendHeadWeights` — the full computed `head_weights` and `weighted_score`.
Request-level: viewer ID, following count, `value_model_id` (checked-in **`"dpp"`**),
and `dpp_params` (`theta = 0.65`, `max_selected_rank = 150`) whenever either is nonzero
— which they are by default, so **Home Mixer requests DPP-based diversity selection by
default** (DIRECT: this is what Home Mixer sends). This is a separate,
independently-active mechanism from `RankingScorer`'s own author-diversity discount,
which is computed and applied entirely inside Home Mixer.

**The DPP implementation is checked into this repository** (`vm-ranker/`, a standalone
Rust gRPC service — `ranker_service.rs`, `scoring/mod.rs`, `scoring/dpp_model.rs`,
`dpp.rs`, `main.rs`, `args.rs`, `embedding_store.rs`, all read this pass) — correcting an
earlier pass's conclusion that VMRanker's server-side behavior was external/unpublished.
Traced precisely, end to end:

- `VMRankerServiceImpl::rank` (`ranker_service.rs:49-117`) calls `scoring::rank(req,
  self.dpp.as_ref())`.
- `scoring::rank` (`scoring/mod.rs:18-54`): if a `DppContext` was constructed at server
  startup, it applies Home Mixer's `theta`/`max_selected_rank` as **overrides** onto the
  server's own configured `DppConfig` (only if the sent value is nonzero,
  `scoring/mod.rs:31-38`) and calls `dpp_model::rank`. **If no `DppContext` exists (DPP
  disabled server-side), it returns each candidate's incoming score unchanged**
  (`scoring/mod.rs:46-53`) — a pure echo, not a re-ranking of any kind.
- `dpp_model::rank` (`scoring/dpp_model.rs:38-82,84-154`): sorts candidates by their
  incoming score descending, keeps up to `max_selected_rank` of them (the "candidate
  pool" DPP selects from — not necessarily every candidate Home Mixer sent), and for
  each looks up an embedding — by `retweeted_tweet_id` for retweets, by `tweet_id`
  otherwise — from an `EmbeddingStore`. **If no embedding is found for a candidate, the
  code generates a random unit vector on the spot** (`random_unit_embedding`,
  `dpp_model.rs:22-36`) and uses that as its embedding for the similarity kernel — a
  concrete, checked-in, non-obvious behavior: candidates with a missing embedding get a
  literally random position in similarity space, meaning diversity selection can be
  nondeterministic per-request for exactly those candidates. This report does not know
  the production embedding-miss rate.
- `dpp::rescore` (`dpp.rs:35-197`, `greedy_dpp` at `:205-286`) is the actual DPP
  algorithm: it normalizes each pooled candidate's score by the pool's top score
  (`q = score / max_score`), applies `theta` as a quality/diversity trade-off exponent
  (`alpha = theta / (2*(1-theta))`, `qf = exp(alpha * q)`), builds an `m×m`
  cosine-similarity kernel from the (real or random-fallback) embeddings scaled by
  `qf[i]*qf[j]`, and runs a **greedy DPP selection** (incremental Cholesky-based
  determinant maximization, a standard efficient greedy-DPP implementation) to pick up
  to `config.top_k` candidates that are jointly high-quality *and* mutually dissimilar.
  **Selected candidates keep their original incoming score verbatim in the returned
  `DppResult` — DPP does not compute or return a new calibrated score.** The function
  also emits a substantial set of Prometheus metrics (pool size, embedding-miss ratio,
  score distribution, average pairwise similarity before/after, top-k overlap with the
  pre-DPP ranking) — real operational instrumentation for a real, exercised code path,
  not dead code.
- Back in `dpp_model::rank`, every candidate Home Mixer originally sent is returned:
  selected ones keep their original score, everything else gets **`score = 0.0`**
  (`dpp_model.rs:143-153`).

**Corrected plain-English framing**: under the checked-in DPP implementation, VMRanker
is a **diversity-aware selection layer**, not a conventional second predictive scorer —
DPP picks a subset using Home Mixer's own incoming quality scores plus embedding
similarity; selected candidates retain their `RankingScorer` score exactly, and rejected
candidates are returned with score `0.0`. Home Mixer's own `update()` logic still
directly overwrites `candidate.score` with whatever VMRanker returns (DIRECT, unchanged
from before) — but under DPP mode, that overwritten value is normally either the prior
score verbatim or zero, not an opaque model-generated replacement.

**What is genuinely still unknown is runtime state, not the algorithm**:
`vm-ranker/args.rs` defines `--dpp-enabled` with a checked-in default of **`false`**, and
`main.rs` only constructs a `DppContext` (and only then attempts to preload/init an
`EmbeddingStore`) when that flag is set (`main.rs:23-44`). DIRECT: the full DPP
implementation is published; Home Mixer's checked-in defaults request
`value_model_id="dpp"` with `theta=0.65`/`max_selected_rank=150`; if the server has DPP
enabled, those request values override its own configured `theta`/`max_selected_rank`
(but **not** `top_k`, which `RankRequest`'s `DppParams` has no field for — the server's
own `--dpp-top-k` default, `50`, is not overridable from Home Mixer's request at all).
DIRECT: if server-side DPP is disabled, `scoring::rank` echoes input scores unchanged,
making the whole mechanism a no-op regardless of what Home Mixer requests. UNKNOWN:
the actual production `--dpp-enabled` state, the live VMRanker deployment's CLI/config,
and the live embedding store's contents — none of which this snapshot publishes.

**How the returned score is used** — two distinct paths depending on configuration
(`vm_ranker.rs:75-100`):
- **Checked-in default path** (`fold_weights` is `None`, because `EnableMpnScoring`
  defaults off): the VM-returned score for a tweet ID, if present, **replaces**
  `c.score` outright (`returned.or(c.score)` — if VMRanker didn't return a score for
  that tweet at all, the prior `.score` is kept as a fallback, not zeroed). Under DPP
  mode specifically, "if present" is essentially always true (every input candidate gets
  a returned row, per `dpp_model.rs:143-153`), so this fallback path is mostly moot for
  DPP; it matters more for the disabled/echo path only if the server drops a candidate
  entirely, which the code as read does not do.
- **Non-default "fold" path** (only when `EnableMpnScoring` is on **and**
  `VMRankerValueModelId == "author_diversity"`, i.e. not the checked-in
  `"dpp"` default): the returned score is instead treated as a ratio
  (`multiplier = (returned / sent_score).clamp(0, 10)`) applied to `RankingScorer`'s
  stored `mpn_parts.pos`, recombined with `mpn_parts.neg` and
  `mpn_parts.scalar_multiplier` (diversity/OON), and re-run through
  `RankingScorer::offset_score` — i.e. VMRanker's number here is a *correction factor*
  on RankingScorer's math, not a direct replacement. **In this fold path,
  `AuthorColdStart::apply` runs a second time** (`vm_ranker.rs:102-110`) on top of the
  already-VM-adjusted scores — meaning cold-start promotion can, in principle, be
  applied twice across the pipeline under this non-default configuration. Note this
  `"author_diversity"` value-model path is architecturally distinct from the DPP service
  path just described — this snapshot does not show a value-model implementation by
  that name inside `vm-ranker/`, only the `"dpp"` one; the fold-path's *own* re-ranking
  content, if any, beyond the client-side arithmetic Home Mixer performs on the returned
  ratio, remains unestablished.

**xDS → DNS fallback**: if an xDS client was configured and the
`enable_vm_ranker_xds_traffic` decider gate is on for this cluster, xDS is tried first;
on xDS failure, DNS/prod is tried **only if** `VMRankerEnableFallback` (checked-in
default **false**) is set — otherwise the whole scorer call fails (`Err` for every
candidate) without trying DNS at all. If xDS wasn't attempted (gate off or no xDS client),
DNS/prod is called directly; its failure is also a whole-call `Err`.

**Failure behavior**: per S01's framework semantics, a whole-call `Err` means
`update()` never runs for any candidate — every candidate keeps `RankingScorer`'s
`.score` exactly as computed, unchanged. VMRanker's failure degrades to
"final ranking = RankingScorer's output," never to a failed request or a blanked score.

## Final Top-K selection

`TopKScoreSelector` (`home-mixer/selectors/top_k_score_selector.rs`): `score(candidate)
= candidate.score.unwrap_or(f64::NEG_INFINITY)`; the framework's generic `Selector::sort`
(`candidate-pipeline/selector.rs:76-84`) sorts by `self.score(b).partial_cmp(&self.score(a))`
— **descending**, so higher `.score` ranks first; candidates with no score at all sort
strictly last, never crash the sort. `size()` returns `TOP_K_CANDIDATES_TO_SELECT = 50`
— the top 50 by `.score` become `selected`, the rest `non_selected` (still passed to
side effects, e.g. the Redis cache side-effect's `non_selected_candidates` union,
retrieval report). No tie-breaking beyond `partial_cmp`'s `Equal`/stable-sort behavior is
visible; exact-tie ordering among equal-scored candidates was not independently traced
further. Those top 50 then go through post-selection hydration/filtering (VF/visibility,
S01) — a post-selection filter can still remove a candidate after this point, and the
pipeline's `result_size() = 35` (`phoenix_candidate_pipeline.rs:967-968`) truncates
whatever survives to 35 for the organic result feeding S02's blending. **A VMRanker
failure changes which candidates make the top 50 only insofar as it leaves
`RankingScorer`'s ordering intact instead of VMRanker's** — the selection mechanism
itself (sort-and-truncate-to-50) runs identically either way.

## Cached-request ranking

Precisely resolved by tracing `has_cached_posts` through all three scorers' `enable()`
bodies and `RankingScorer::score`'s internal branches:

- **`PhoenixScorer`**: `enable()` returns `false` when `query.has_cached_posts`
  (`phoenix_scorer.rs:65-68`) — does not run; cached candidates' `phoenix_scores` are
  whatever `CachedPostsSource` restored (the predictions from when they were first
  computed, up to ~180s old).
- **`RankingScorer`**: `enable()` checks only `EnableRanking` (checked-in **true**) —
  **runs regardless of `has_cached_posts`**. Inside `score()`, `has_cached_posts` is
  checked in exactly one place: whether to reuse each candidate's *stored*
  `slate_context` (author-repetition rank data) versus recompute it fresh from this
  batch (`ranking_scorer.rs:786-790, 855-859`) — this affects only the
  author-diversity-discount basis, not the core weighted-sum computation. **The
  weighted-sum computation itself (`compute_weighted_parts`/`compute_weighted_score`) is
  never gated on `has_cached_posts` — it always recomputes, using `ScoringWeights::
  from_params(&query.params)`, i.e. the CURRENT request's feature-switch weights,
  against the STORED (reused) `phoenix_scores`.**
- **`VMRanker`**: `enable()` checks only `EnableVMRanker` (checked-in **true**) — also
  **runs regardless of `has_cached_posts`**, sending the freshly-recomputed `.score`
  (and, if `VMRankerSendHeadWeights` were on, freshly-recomputed head weights) to the
  separate VM Ranker service exactly as on a live request.

**Precise plain-English conclusion**: a cached (`has_cached_posts`) response skips live
retrieval (retrieval report) and skips a fresh Phoenix *model inference call* — but it
does **not** skip local re-weighting or re-ranking. `RankingScorer` and `VMRanker` both
run in full, against the reused Phoenix predictions, using whatever ranking weights and
DPP/diversity parameters are active for *this* request. Because the underlying
`weighted_score`/`.score` computation always uses current `query.params`, **a feature-
switch weight change deployed within the 180-second cache TTL can change the relative
order of a cached response** even though the underlying model predictions did not
change — cached mode reuses stale *predictions*, not a stale *ranking*. This resolves
`01_retrieval.md`'s explicit carry-forward question precisely.

## Failure and fallback behavior

Never described as "request fails" below unless the framework actually propagates a
failure — per S01, no scorer failure fails the request; it only leaves fields unset/stale.

| Condition | Consequence |
|---|---|
| `PhoenixScorer`'s model call fails (`Err`) | Per-candidate `phoenix_scores` update is skipped entirely (framework default `update_all`, S01) — every candidate keeps whatever `phoenix_scores` it had before (empty, on a fresh non-cached request) |
| `query.scoring_sequence` is `None` when `PhoenixScorer` runs | Not an error — `PhoenixScorer` explicitly returns `Ok(PostCandidate::default())` for every candidate, writing empty `phoenix_scores`. `RankingScorer` then computes a flat baseline `weighted_score = NEGATIVE_SCORES_OFFSET (0.001)` for all of them (every weighted term is `0 * weight = 0`), differentiated only by cold-start/diversity/OON adjustments |
| An individual prediction head is missing from the model response | `Self::apply(None, weight) = 0.0` — that head simply contributes nothing to the sum; no error, no candidate-level effect beyond that one head |
| `RankingScorer` disabled (`EnableRanking = false`) | `.score`/`weighted_score` are never written by this stage; whatever VMRanker does next operates on candidates with no prior `.score` (sorts last if VMRanker also fails or is disabled) |
| `VMRanker` disabled (`EnableVMRanker = false`) | Never runs; `.score` stays exactly as `RankingScorer` left it — this is the simplest, most direct "final ranking = RankingScorer's output" case |
| `VMRanker` xDS fails, `VMRankerEnableFallback = true` | Falls back to DNS/prod client transparently; only a DNS/prod failure after that is a whole-call `Err` |
| `VMRanker` xDS fails, `VMRankerEnableFallback = false` (**checked-in default**) | Whole call is `Err` immediately, no DNS attempt — `.score` stays at `RankingScorer`'s value |
| `VMRanker` xDS *and* DNS both fail | Whole call `Err` — same consequence as above |
| Cached mode (`has_cached_posts`) | See "Cached-request ranking" above — `PhoenixScorer` skipped, `RankingScorer`/`VMRanker` both re-run against reused predictions with current weights |
| Empty candidate pool reaches scoring | Not specifically traced in this macro; `RankingScorer`'s `compute_dwell_regret_base_scores` explicitly handles `n == 0` by returning an empty vec (`ranking_scorer.rs:569-571`) — the weighted-sum path has no analogous explicit empty-input branch but operates per-candidate over an iterator, which is a no-op on an empty slice by construction. `TopKScoreSelector` on zero candidates simply selects zero. |

## Checked-in defaults vs production state

All values below are **checked-in defaults from `home-mixer/params/param.rs`**, mirrored
(per the file's own header comment, `param.rs:1`, "mirrored from config feature-switch
defaults; last sync 2026-08-12T04:09:22Z") from external feature-switch config — **not
verified as current production values**, consistent with every prior pass's boundary
(S01/S17). This table intentionally covers only ranking-relevant parameters, not a full
S17 census.

| Parameter | Checked-in value | Meaning | Consumed by | Runtime-overridable? | Evidence |
|---|---|---|---|---|---|
| `EnableRanking` | `true` | Gates whether `RankingScorer` runs at all | `RankingScorer::enable` | Yes (feature switch) | DIRECT |
| `EnableVMRanker` | `true` | Gates whether `VMRanker` runs at all | `VMRanker::enable` | Yes | DIRECT |
| `ValueModelMode` | `"weighted"` | Selects weighted-sum vs. dwell-regret vs. gated-dwell-regret scoring | `RankingScorer::score` | Yes | DIRECT |
| `EnableMpnScoring` | `false` | Selects MPN-restructured scoring path + enables the VMRanker "fold" path | `RankingScorer::score`, `VMRanker::score` | Yes | DIRECT |
| `VMRankerValueModelId` | `"dpp"` | Which value model VMRanker uses; only `"author_diversity"` activates the fold path | `VMRanker::score`, request `value_model_id` | Yes | DIRECT |
| `VMRankerSendHeadWeights` | `false` | Whether RankingScorer's computed head weights/weighted_score and 5 extra phoenix-score fields are sent to VMRanker | `VMRanker::build_request` | Yes | DIRECT |
| `VMRankerDppTheta` / `VMRankerDppMaxSelectedRank` | `0.65` / `150` | DPP diversity strength / depth sent to VMRanker | `VMRanker::build_request` | Yes | DIRECT |
| `VMRankerEnableFallback` | `false` | Whether VMRanker falls back to DNS/prod after an xDS failure | `VMRanker::score` | Yes | DIRECT |
| `OonWeightFactor` / `TopicOonWeightFactor` | `0.75` / `0.5` | OON score discount, non-topic / topic requests | `RankingScorer::effective_oon_weight` | Yes | DIRECT |
| `EnableOonRescoreForInNetworkRepliesRetweets` | `true` | Applies the OON discount to in-network replies/retweets too | `RankingScorer::score`'s `oon_applies` | Yes | DIRECT |
| `NewUserAgeThresholdSecs` | `0` | Below this account age (+≥5 follows), OON weight collapses to ~0 | `RankingScorer::effective_oon_weight` | Yes, but **currently unreachable at 0** | DIRECT |
| `PhoenixRankerNewUserHistoryThreshold` | `0` | Below this action-history length, routes to a different Phoenix inference cluster | `PhoenixScorer::resolve_cluster` | Yes, but **currently unreachable at 0** | DIRECT |
| `EnableAuthorDiversity` | `true` | Gates the author-repetition score discount | `RankingScorer::score` | Yes | DIRECT |
| `AuthorDiversityDecay` / `AuthorDiversityFloor` | `0.5` / `0.25` | Diversity multiplier decay rate / floor | `RankingScorer::diversity_multiplier` | Yes | DIRECT |
| `BidirectionalFollowReplyWeightBoost` / `...DwellWeightBoost` | `15.0` / `0.0` | Extra reply/dwell weight for mutual-follow original posts | `RankingScorer::reply_weight_for`/`dwell_weight_for` | Yes | DIRECT |
| `EnableViewerColdStart` | `true` | Gates the cold-start floor mechanism | `AuthorColdStart::apply` | Yes | DIRECT |
| `ColdStartFollowerCap` / `ColdStartImpressionThreshold` | `1,000` / `1,000` | Eligibility caps for cold-start boost | `AuthorColdStart` | Yes | DIRECT |
| `ColdStartSlotMin` / `ColdStartSlotMax` | `15` / `16` | Target slot range the boosted candidate's score is floored to | `AuthorColdStart::cold_start_target` | Yes | DIRECT |
| `EnableColdStartThompsonSampling` | `false` | Selects Thompson-sampling vs. max-score pick for the cold-start candidate | `AuthorColdStart::apply` | Yes | DIRECT |
| `MinVideoDurationMs` | `10,000` (10s) | Minimum candidate video duration for VQV weight to apply | `candidates_util::vqv_weight`/`quoted_vqv_weight` | Yes | DIRECT |
| Report/block/mute/not-interested weights | `-234.0` / `-31.2` / `-58.8` / `-43.2` | Negative-head weights | `RankingScorer::compute_weighted_parts` | Yes | DIRECT |
| `DwellRegretGateThreshold`/`Bias`/`Weights`/`HysteresisBand` | see gate section | Linear-model gate deciding `gated_dwell_regret` routing | `GateModel` | Yes | DIRECT (only relevant if `ValueModelMode="gated_dwell_regret"`, not default) |

## Material findings

1. **VMRanker overwrites `RankingScorer`'s score by default; a failure leaves the prior
   stage's score untouched — resolves S01-F012's field-level uncertainty with DIRECT
   evidence.**
   Significance: HIGH. Evidence class: DIRECT.
   Claim: `VMRanker::update` (`vm_ranker.rs:123-125`) unconditionally sets
   `candidate.score = scored.score`; under the checked-in default value model (`"dpp"`),
   `VMRanker::score` sets each candidate's returned score to directly replace `.score`
   (`returned.or(c.score)`, `vm_ranker.rs:96-98`). A whole-call `Err` means `update()`
   never runs for any candidate (S01's framework semantics), so `.score` stays exactly
   at `RankingScorer`'s value.
   Source: `home-mixer/scorers/vm_ranker.rs:79-100,123-125`.
   Caveat: under the non-default `"author_diversity"` value model + `EnableMpnScoring`,
   VMRanker's number is a multiplier/correction on `RankingScorer`'s parts, not a direct
   replacement — see VMRanker section.

2. **In-network replies and retweets are discounted with the same weight as
   out-of-network content, by current checked-in default.**
   Significance: HIGH. Evidence class: DIRECT.
   Claim: `oon_applies` treats `c.in_network == Some(true)` candidates as OON-discount-
   eligible too, when `EnableOonRescoreForInNetworkRepliesRetweets` (checked-in default
   `true`) is set and the candidate is a reply or retweet.
   Source: `home-mixer/scorers/ranking_scorer.rs:773-783`.

3. **Cache mode reuses stale Phoenix predictions but re-ranks them with the current
   request's live feature-switch weights — not a replay of the original ranking.**
   Significance: HIGH. Evidence class: DIRECT.
   Claim: `RankingScorer::enable`/`VMRanker::enable` check only `EnableRanking`/
   `EnableVMRanker`, never `has_cached_posts`; the weighted-sum computation inside
   `RankingScorer::score` always calls `ScoringWeights::from_params(&query.params)`
   with no `has_cached_posts` branch.
   Source: `home-mixer/scorers/ranking_scorer.rs:734-736,743,786-790,855-859`,
   `home-mixer/scorers/vm_ranker.rs:24-26`.

4. **Two "new user" special-case mechanisms exist in source but are both currently
   unreachable because their triggering threshold parameters default to zero.**
   Significance: MEDIUM. Evidence class: DIRECT.
   Claim: `NewUserAgeThresholdSecs` (gates near-total OON suppression for new users) and
   `PhoenixRankerNewUserHistoryThreshold` (gates routing to a distinct new-user
   inference cluster) both have checked-in default `0`; `Duration::from_secs(0)` makes
   the "age < threshold" and "history length < threshold" comparisons unsatisfiable for
   any real account/history.
   Source: `home-mixer/params/param.rs` (`NewUserAgeThresholdSecs`,
   `PhoenixRankerNewUserHistoryThreshold`), `home-mixer/scorers/ranking_scorer.rs:717-728`,
   `home-mixer/scorers/phoenix_scorer.rs:28-41`.
   Caveat: production values for these thresholds are UNKNOWN; if overridden above zero
   in production, both mechanisms activate exactly as coded.

5. **The "post_unexplored_in_network_only" flag's name is the opposite of its effect —
   it restricts the post_unexplored bonus to in-network candidates, not out-of-network
   ones.**
   Significance: LOW–MEDIUM. Evidence class: DIRECT.
   Claim: `post_unexplored_active_for` returns `!self.post_unexplored_in_network_only ||
   candidate.in_network == Some(true)` — when the flag is `true` (checked-in default),
   the bonus applies only to in-network candidates.
   Source: `home-mixer/scorers/ranking_scorer.rs:176-178`.

6. **VQV (video-quality-view) weight is zeroed for viewers with ≥10,000 followers,
   independent of the candidate video's duration.**
   Significance: MEDIUM. Evidence class: DIRECT.
   Claim: `vqv_weight` returns `0.0` whenever `query.user_features.follower_count >=
   10_000` (`MAX_FOLLOWERS_THRESHOLD`), regardless of whether the candidate's video
   clears the duration bar.
   Source: `home-mixer/util/candidates_util.rs:4,19-40`.
   Caveat: the underlying rationale (e.g. distinguishing high-reach accounts' viewing
   behavior) is not stated in source — POSSIBLE explanation, not DIRECT.

7. **Author cold-start floors one candidate's score to at least the value currently
   occupying ranked index 15 under checked-in defaults — this is a score floor applied
   mid-pipeline, not a guaranteed final feed position.**
   Significance: MEDIUM. Evidence class: DIRECT.
   Claim: `ColdStartSlotMin = 15`, `ColdStartSlotMax = 16` — `cold_start_target`'s
   `rand::rng().random_range(lo..hi)` over a single-width range `[15, 16)` deterministically
   reads the *score value* at zero-based ranked index 15 from the current batch; only one
   candidate (`best_idx`) is boosted per call, via
   `effective[best_idx] = effective[best_idx].max(target)` — a floor, not an assignment.
   Under checked-in defaults, `RankingScorer`'s own author-diversity/OON adjustments run
   on top of this floored score afterward, and `VMRanker` (`EnableVMRanker=true` by
   default) runs after `RankingScorer` and can replace `.score` outright — so the
   boosted candidate's *final* position is not fixed by this mechanism alone.
   Source: `home-mixer/scorers/author_cold_start.rs:182-191,257-309`,
   `home-mixer/params/param.rs` (`ColdStartSlotMin`, `ColdStartSlotMax`).
   Caveat: whether the candidate ends up near rank 15 in the truly final order depends
   on the magnitude of the diversity/OON multipliers and on what VMRanker returns for
   it — not independently traced end-to-end for a concrete example in this macro.

8. **DPP-based diversity selection is requested at the VMRanker layer by default,
   independently of `RankingScorer`'s own author-diversity discount — two distinct
   diversity mechanisms are both active in the checked-in request path. Both are now
   fully traceable: the DPP algorithm itself is checked-in Rust
   (`vm-ranker/dpp.rs`/`scoring/dpp_model.rs`), not external. The only unknown is
   whether the server's `--dpp-enabled` flag (checked-in default `false`) is set in
   production.**
   Significance: MEDIUM. Evidence class: DIRECT (that Home Mixer sends nonzero DPP
   params by default; that `RankingScorer`'s local diversity discount runs
   independently; that the full greedy-DPP selection algorithm, its scoring formula,
   and its score-passthrough/zero-out output behavior are all checked-in and read this
   pass). UNKNOWN: live `--dpp-enabled` state and live embedding-store contents.
   Claim: `EnableAuthorDiversity = true` (RankingScorer-side, fully local and directly
   observed) and `VMRankerDppTheta = 0.65` (nonzero, sent to the VMRanker service by
   default) are both checked-in defaults, and neither gates the other.
   Source: `home-mixer/params/param.rs` (`EnableAuthorDiversity`, `VMRankerDppTheta`),
   `home-mixer/scorers/vm_ranker.rs:206-216`, `vm-ranker/dpp.rs:35-197`,
   `vm-ranker/args.rs:15-16`, `vm-ranker/main.rs:23-44`.

9. **`RankingScorer`'s negative-weight offset formula compresses net-negative candidates
   toward zero rather than leaving them deeply negative — a normalization step with no
   stated rationale in source.**
   Significance: LOW. Evidence class: DIRECT (the formula); STRONG_INFERENCE (the
   purpose).
   Claim: `offset_score` rescales any net-negative combined score by
   `(combined + negative_sum) / total_sum * 0.001`, while net-positive scores simply get
   `+0.001`.
   Source: `home-mixer/scorers/ranking_scorer.rs:554-562`, `params/config.rs:40`
   (`NEGATIVE_SCORES_OFFSET`).

## What remains unknown

- The Phoenix model's actual architecture, training data, and how it represents
  viewer-history/candidate/text/media inputs internally — `phoenix/xrex/` was not
  deep-read (S06's territory by design of this macro).
- Whether model outputs are calibrated probabilities, raw logits, or something else,
  per head — not verified from the serving-side call site alone.
- The complete, canonical field list of the external `PhoenixScores` struct — this
  report lists only fields this repo's own consuming code was observed to read.
- `RetrievalDispatch`/`PredictionDispatch`'s exact internal retry/fallback mechanics —
  external crate, same boundary already noted in the retrieval report.
- The live `--dpp-enabled` state of the production VMRanker deployment, and the
  contents of its embedding store — the DPP kernel/similarity computation itself is
  now fully traced (`vm-ranker/dpp.rs`), correcting an earlier pass's claim that it was
  external/unpublished; what remains unknown is purely runtime deployment state, not
  the algorithm.
- Production values for every parameter in the "Checked-in defaults" table — consistent
  with every prior pass, these are checked-in source defaults only.
- Exact tie-breaking behavior in `TopKScoreSelector`'s sort for candidates with
  identical `.score` — `partial_cmp`'s `Equal` case relies on Rust's stable sort
  (input order preserved) but this was not independently stress-tested here.
- Whether `RouteGate`'s decider-based xDS gating (`enable_vm_ranker_xds_traffic`,
  `enable_phoenix_xds_traffic`) is on in production for any cluster — external
  decider/config state, UNKNOWN.

## What the next macro needs to answer

Explicit handoff to the account/reputation + labels/moderation/visibility + content
understanding macro:

- `VFCandidateHydrator`/`VFFilter`/`AncillaryVFFilter` internals (S01 established only
  their pipeline placement) — this macro established that they run on the *already-
  ranked* top-50, after `TopKScoreSelector`, meaning visibility policy can still remove
  a high-scored candidate before the final 35, but did not trace what triggers that
  removal.
- What actually sets `is_mutual_follow_author`/`in_network` on a candidate in full detail
  beyond what S01/S00 established for `BidirectionalFollowHydrator`/`InNetworkCandidateHydrator`
  — this macro consumed those flags but did not re-derive their computation.
  the account-status/reputation signals (S11/S14/S15) that could independently suppress
  a candidate before it ever reaches scoring, separate from the ranking-layer OON/
  diversity/cold-start mechanics documented here.
- `author_rules::AuthorRulesEvaluator` (used by `AuthorColdStart` for MOE treatment/
  control corpus bucketing) — only its consumption inside cold-start was traced, not
  its own eligibility-computation internals.
- Whether the `search_unfiltered` Phoenix-rankall admission branch (flagged UNKNOWN in
  the retrieval report's corrected finding #1) feeds any ranking-relevant retrieval path
  — still unresolved, now doubly relevant since replies could theoretically be scored
  by this exact ranking chain if they do reach it.

## Source coverage note

**Deep-read in full**: `home-mixer/scorers/phoenix_scorer.rs`,
`home-mixer/scorers/ranking_scorer.rs` (non-test portion, L1-910, in full; test portion
L912-1708 used to verify specific behaviors, not read as spec line-by-line),
`home-mixer/scorers/vm_ranker.rs`, `home-mixer/scorers/author_cold_start.rs`,
`home-mixer/scorers/value_model_gate.rs`, `home-mixer/scorers/phoenix_scores_ranking_scorer.rs`,
`home-mixer/selectors/top_k_score_selector.rs`, `candidate-pipeline/selector.rs`,
`home-mixer/util/candidates_util.rs` (`vqv_weight`/`quoted_vqv_weight`),
`home-mixer/util/xds.rs`; relevant slices of `home-mixer/params/param.rs` (every
ranking-relevant `param!` declaration cross-referenced against the scorers' actual
`params.get(...)` calls) and `home-mixer/params/config.rs` (`NEW_USER_OON_WEIGHT_FACTOR`,
`NEW_USER_MIN_FOLLOWING`, `NEGATIVE_SCORES_OFFSET`, `TOP_K_CANDIDATES_TO_SELECT`,
`RESULT_SIZE`); **`vm-ranker/{ranker_service,scoring/mod,scoring/dpp_model,dpp,main,args}.rs`
in full, this pass** — the server-side DPP implementation, previously mischaracterized
as external/unpublished.

**Mechanically searched/surveyed, not deep-read**: `home-mixer/util/phoenix_request.rs`
(request-builder call site confirmed, internal field-by-field construction not traced);
`phoenix/xrex/` Python training/serving stack (model architecture/inputs — explicitly
out of scope per this macro's S06 boundary); `home-mixer/clients/vm_ranker_client.rs`
(client trait/construction confirmed via grep, internals not opened);
`RetrievalDispatch`/`PredictionDispatch` internals (external crate, consistent with the
retrieval report's boundary).

**Intentionally not exhaustively read**: `PhoenixScoresPipeline`'s full construction and
`SeedCandidatesSource` (S01 already covers its orchestration role; this macro only
opened `PhoenixScoresRankingScorer` to compare its formula to the main path);
`home-mixer/candidate_pipeline/phoenix_candidate_pipeline.rs` beyond the specific
`result_size()`/scorer-construction lines already cited in the retrieval report; the
full `xai_vm_ranker_proto`/`xai_recsys_proto` generated-proto definitions (field names
inferred from usage sites, not read from a `.proto` source in this snapshot).
