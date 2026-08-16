# Model, Runtime & Production Boundaries — What the Public Algorithm Does and Does Not Reveal

Rapid-track final source-research macro, combining the behaviorally-relevant parts of S06
(Phoenix training/model/inference architecture), S16 (Under the Hood transparency
tooling), S17 (runtime configuration/experiments), and S18
(operational/reproducibility/public-vs-production boundaries), per
`_analysis/rapid/README.md`. Builds on `01_retrieval.md`, `02_ranking.md`, and the
corrected `03_eligibility_labels_visibility.md`; does not re-derive them. This is the
last source-research macro in this track — no general synthesis document is started here.

## Plain-English summary

Three earlier reports established *what* Home Mixer does — how a post is retrieved,
ranked, and filtered — largely by reading Home Mixer's own Rust source. This report asks
a different question: of everything those reports had to leave as "external" or
"UNKNOWN," how much can actually be resolved by going one layer deeper into this same
repository, and how much genuinely cannot?

The biggest resolvable gap was the Phoenix model itself. `02_ranking.md` deliberately
didn't open `phoenix/xrex/`. This report does, and finds two structurally different
models living in the same codebase, easy to conflate. One (`RecsysGenRecsModel`,
config name `xrecsys_gen_recs`) is trained with a contrastive, InfoNCE-style loss to
*predict the embedding of the next item a user will engage with* — a generative,
retrieval-flavored objective, evaluated on next-item retrieval accuracy (top-1 hit rate,
cosine similarity to the true next item), not on classifying discrete actions. The other
(the base `RecsysAggregatedModel` class both this and other model variants build on)
supports the genuinely multi-headed structure `RankingScorer` consumes: a shared
transformer backbone producing one logit per action type, each independently passed
through a `sigmoid` (for the ~26 discrete engagement heads — favorite, reply, retweet,
and the rest) or a per-head-configurable activation (`sigmoid`/`softplus`, sometimes with
a `tanh`-based output cap) for the small set of continuous heads (dwell time, click-dwell
time, a normalized activity residual). This repository does not name, in one place, which
exact model config is wired to the specific `PhoenixCluster`/`PhoenixRetrievalCluster`
identifiers Home Mixer's `PhoenixScorer`/`PhoenixSource` request by string
(`"Experiment1Fou"` and friends) — that binding lives in external cluster configuration,
not in this snapshot. What *is* directly established: both the retrieval-flavored
`gen_recs` model and the ranking-flavored multi-head model are built from the same
family of components (same hash-based ID embedding scheme, same transformer stack, same
history/candidate sequence construction), and both are trained at real production scale
(`total_samples=1e11` for the full `xrecsys_gen_recs` config, alongside a much smaller
`gen_recs_nano` variant clearly meant for local testing, not production).

The single most concrete resolution in this report closes a question two forensic passes
and this rapid track both left open: does the model actually see the bidirectional-follow
signal (`author_follows_viewer`, established all the way back in S00)? Yes — directly,
unambiguously. `home-mixer/models/candidate.rs`'s `as_tweet_info` sets
`AuthorInfo.is_following_user = self.author_follows_viewer`, gated to original posts only
(`if self.retweeted_user_id.is_none()`) — the exact same "not a retweet" condition
`RankingScorer`'s bidirectional-follow boost already required. The model receives both
directions of the follow relationship (`is_author_followed_by_user`, i.e. viewer→author,
unconditionally; `is_following_user`, i.e. author→viewer, for non-retweets), plus raw
engagement counts (favorites, retweets, quotes, replies, views, bookmarks), boolean
content flags (has media, is retweet/quote/reply), a language code, and a compact
`semantic_ids` field — but conspicuously *not* raw post text or a raw media embedding
in this specific request path. The most defensible reading, though not independently
proven by tracing the serving side, is that rich content representations are resolved
server-side from the semantic ID rather than streamed per-request from Home Mixer — the
wire request carries identifiers and counts, not content.

On runtime configuration, this report does not find anything that overturns the pattern
already established three times over: `home-mixer/params/param.rs`'s own header says its
defaults are "mirrored from config feature-switch defaults" as of a specific timestamp.
That header proves exactly one thing — that a real external feature-switch/GrowthBook
system exists and this file is a periodically-refreshed copy of its default values at
sync time. It proves nothing about current production values, nothing about
per-user/per-experiment overrides (which the `RecipientBuilder`/`FeatureSwitches`
machinery this repo does show is explicitly designed to support), and nothing about
decider or xDS-routing state. Every checked-in numeric weight, mode selector, and
percentage cited across all three prior reports inherits this same limit.

Under the Hood, the one user-facing transparency surface in this snapshot, turns out to
be a genuinely useful but narrowly-scoped instrument: it reports, per account, per
calendar month, how many of a user's posts carried or had removed each named safety
label on each day, and how many days an account label was active — compared against an
anonymous cohort of similar accounts. It is aggregate, monthly, and retrospective. It
cannot tell a user why one specific post was filtered on one specific request, cannot
show a Phoenix prediction or a VMRanker score, and does not expose ranking behavior at
all — it is a labeling-transparency report, not a ranking debugger, and this report is
careful not to oversell it as more than that. Its own label-catalog documentation
(`underTheHoodLabels.strato`) is, however, a genuinely valuable independent
cross-check: its plain-English descriptions of what `SPAM_HIGH_RECALL`, `NSFW_HIGH_PRECISION`,
and other labels *do* ("hidden from recommendations to non-followers," "shown behind
content warning") match, label for label, what this rapid track independently traced
through `visibility-filtering`'s Rust rule source — two independently-read parts of this
repository corroborating the same behavior.

Reproducibility, finally, is not one answer but nine different ones depending on exactly
what's being asked. Home Mixer's orchestration, the retrieval sources' wiring, and
visibility filtering's policy composition are all fully reproducible from this snapshot
— they're compiled, checked-in, testable Rust. The Phoenix *architecture* is
reproducible as a JAX model definition; a specific *trained checkpoint* is not — no
weights ship in this repository, and BDSM's operating thresholds are explicitly redacted
rather than merely absent. Production feature-switch state, VMRanker's server-side DPP
implementation, and the complete Botmaker/Scarecrow rule corpus are all, to varying
degrees of confirmed partiality, external to what this snapshot can prove.

## Phoenix model architecture

**Which model config is live**: `phoenix/xrex/configs/xrecsys_gen_recs.py` defines
`MODEL_CFGS["xrecsys_gen_recs"]` — 8 transformer layers, `emb_size=2560`, 20 query heads
/ 4 KV heads (grouped-query attention, `RecsysAttentionConfig`), `history_seq_len=1023`,
`candidate_seq_len=128`, causal + rotary attention, `total_samples=1e11` — this is, by
scale alone, the production configuration (a `gen_recs_nano` sibling config with 2 layers
and `total_samples=1e9` is clearly a local/test variant). It trains `RecsysGenRecsModel`
(`phoenix/xrex/models/recsys_gen_recs_model.py:114`), a subclass of the more general
`RecsysAggregatedModel` (`phoenix/xrex/models/recsys_model.py:1325`).

**Two structurally different objectives coexist in this codebase, and it matters which
one Home Mixer's `RankingScorer` inputs actually come from**:

- `RecsysGenRecsModel.loss()` (`recsys_gen_recs_model.py:530-679`) trains the model to
  predict the *embedding* of the next item in a user's action sequence, scored via an
  InfoNCE contrastive loss against the true next-item embedding plus sampled/global
  negatives (with a `log_q_correction` for sampled-softmax bias, a documented technique
  for large-vocabulary contrastive training). Evaluation metrics are retrieval metrics:
  top-1 accuracy at each sequence position, mean cosine similarity, L2 distance to the
  true target. This is a **generative retrieval** objective — "predict what the user
  engages with next, as a point in embedding space" — not a discrete action classifier.
- `RecsysAggregatedModel` (the base class) implements the machinery for genuinely
  multi-headed per-action prediction: `get_probs_and_labels`
  (`recsys_model.py:403-416`) applies `jax.nn.sigmoid` to a `logits` tensor with one
  slot per action type, and a separate continuous-action activation function
  (`recsys_model.py:1940-1986`) applies a per-head-configured activation
  (`sigmoid`/`softplus`, `Config.activation`) with an optional `output_cap`-bounded
  `tanh` squash, driven by `ContinuousActionLossConfig` (`recsys_model.py:195-227`,
  which also defines per-head loss type — MSE/MAE/Huber/Tweedie — and product-surface
  filtering, i.e. a continuous head's config can vary by which surface, e.g. Home
  Timeline vs. notifications, the prediction is for).

This snapshot does **not** contain a single file that names, by config identifier,
exactly which of these two model shapes is bound to the `PhoenixCluster` string values
(`"Experiment1Fou"`, `"Experiment2Fou"`, `"Experiment1Lap7"`) Home Mixer's
`PhoenixScorer`/`PhoenixSource` request — that binding is external cluster
configuration. What *is* directly established: `RankingScorer` consumes ~26
independently-valued action probabilities/continuous values per candidate
(`02_ranking.md`), which is architecturally consistent with `RecsysAggregatedModel`'s
per-head-sigmoid structure, not with `RecsysGenRecsModel`'s single-embedding-per-position
InfoNCE objective. STRONG_INFERENCE, not DIRECT: the ranking-serving path most plausibly
uses an aggregated multi-head model config (a sibling of, or descended from, the same
`RecsysAggregatedModel` base class), while `xrecsys_gen_recs` specifically is more
plausibly the retrieval/candidate-generation model feeding the SID-based retrieval
infrastructure established in `01_retrieval.md` — but this snapshot does not contain the
exact serving-config file that would make this a DIRECT claim rather than an inference
from loss-function shape.

**Shared architectural building blocks**, confirmed from `build_gen_recs_inputs`
(`recsys_gen_recs_model.py:396-486`) and `build_history_only`
(`:182-247`), apply to both model shapes since both extend the same base classes:

- **Sequence construction**: one concatenated sequence — `[user_token, history_tokens...,
  candidate_tokens...]` — attended over by a single causal transformer. This is a
  **single-sequence, decoder-style architecture**, not a two-tower architecture computing
  independent user/candidate embeddings and dot-producting them at the end (a genuine
  two-tower model, `recsys_two_tower_model.py`, exists elsewhere in this codebase for a
  different purpose — retrieval-serving evaluation, per `xrecsys_two_tower_evals.py` —
  and is not what this ranking-consumption path uses).
- **History items** are individually rich: each history position fuses a post-hash
  embedding, an author-hash embedding, a product-surface embedding, a *multi-hot* action
  embedding (a user can both favorite and reply to the same historical post — this is
  not a single categorical label per history item), and continuous action features
  (`block_history_reduce`, `recsys_gen_recs_model.py:221-236`).
  `history_seq_len=1023` (production config) bounds how much history the model attends
  to.
- **User representation**: a hashed-ID embedding (`block_user_reduce` over
  `user_hashes`), using an explicit feature-hashing scheme (`user_hash_scales`,
  `user_biases`, `user_modulus` — collision-tolerant hashing into a fixed-size table,
  `user_vocab_size=100,000,000` in the production config) rather than one row per
  literal user ID.
- **Candidate representation**: `project_candidates`/`block_candidate_reduce`
  (`recsys_gen_recs_model.py:364-393`) fuses post-hash, author-hash, product-surface, and
  a **multimodal embedding** (`mm_embs`, required — `"Gen recs model requires
  multimodal embeddings in candidate_seq"`, `:449`) per candidate. `candidate_seq_len=128`
  bounds how many candidates one forward pass scores at once — notably smaller than the
  35–50 candidates Home Mixer's own pipeline ultimately ranks, and far smaller than the
  request-side `PHOENIX_CLIENT_MAX_CANDIDATES=2800` cap
  (`home-mixer/util/phoenix_request.rs:11`) — the exact batching/chunking relationship
  between a >128-candidate Home Mixer request and this 128-length model input is not
  established from this snapshot (UNKNOWN — likely resolved server-side, not shown here).

**Multimodal/embedding inputs**: `mm_target_dim=1024` (production config) — candidates
carry a 1024-dimensional multimodal embedding into the model; `recsys_embedding.py` (334
lines, not deep-read beyond confirming its role as the shared hash-embedding-table
module both history and candidate paths call into) implements the actual hash-table
mechanics.

**Positional/time encoding**: `positions` are set from raw sequence index
(`recsys_gen_recs_model.py:502-503`, `positions[:, :, 0] = arange(T)`) combined with
`rotary=True` in the attention config — rotary position embeddings, keyed on position
index within the constructed sequence. Whether *timestamp*-aware (as opposed to purely
ordinal) positional information is also injected was not independently confirmed from
this file alone (`positions` is shaped `(B, T, 3)` with only the first of three
components explicitly set here — the other two dimensions' purpose is UNKNOWN from this
pass).

## What the model actually sees

Precise field-level map from `home-mixer/util/phoenix_request.rs` (full file, read) and
`home-mixer/models/candidate.rs`'s `as_tweet_info`/`as_score_info` (read):

| Home Mixer field | Request/proto field | Notes |
|---|---|---|
| `query.user_id`, `client_app_id`, `country_code`, `language_code`, `user_roles`, `ip_address`, `client_version` | `ClientContext` | Unconditional except `user_id == 0` short-circuits to `None` entirely |
| `query.user_demographics` (age bracket/gender/state), `user_age_in_years`, `user_inferred_gender(_score)`, `followed_grok_topics`, `followed_starter_packs`, IP-derived lat/long/DMA code, `user_installed_apps` | `UserContext` | All present unconditionally when demographics/location data was hydrated upstream |
| `query.device_network_type`, `time_zone`, `ip_address`, derived `country_code` enum | `DeviceFeature` | Part of the `CandidateSet`, not per-candidate |
| `query.scoring_sequence` | `sequences` (singular vec) | The viewer's action-history sequence — this is the model's history input |
| `query.columnar_scoring_sequence` | `columnar_sequences` | An alternate/columnar-format representation of the same history, sent alongside |
| candidate `tweet_id`/`retweeted_tweet_id` (resolved to "original" IDs) | `TweetInfo.tweet_id`, `.retweeting_tweet_id` | Retweets are represented as the *original* tweet plus a separate retweeting-tweet/author pair |
| candidate `quoted_tweet_id`/`quoted_user_id`, `in_reply_to_tweet_id` | `TweetInfo.quoted_*`, `.in_reply_to_tweet_id` | Direct pass-through |
| `followed_ids.contains(author) \|\| author == viewer` | `TweetInfo.is_author_followed_by_user`, `AuthorInfo.is_followed_by_user` | Viewer→author follow direction |
| `candidate.author_follows_viewer`, **only for non-retweets** | `AuthorInfo.is_following_user` | **Author→viewer (mutual-follow) direction — this is the S00/S01 `BidirectionalFollowHydrator` output reaching the model directly** |
| `candidate.min_video_duration_ms` | `TweetInfo.min_video_duration_ms` | |
| `fav_count`, `repost_count`, `quote_count`, `reply_count`, `view_count`, `bookmark_count` | `TweetInfo.*_count` | Raw engagement counts reach the model as numeric features, not just embeddings |
| `candidate.language_code` | `TweetInfo.language_code` (enum) | |
| `has_media`, `is_retweet`/`is_quote`/`is_reply` (derived from ID presence) | `TweetInfo.tweet_bool_features` | Boolean content flags |
| `candidate.semantic_ids` | `TweetInfo.semantic_ids` | The compact SID representation established in `01_retrieval.md`'s Phoenix-rankall admission tracing |

**What is conspicuously absent from this specific request path**: raw post text, a raw
media embedding, and topic-ID data are **not** set in `as_tweet_info`'s field
construction (confirmed by reading the full function — only the fields listed above are
populated; everything else uses `..Default::default()`). STRONG_INFERENCE, not proven by
tracing the serving side in this pass: rich content representation is resolved
server-side from `semantic_ids`/`tweet_id` lookups (consistent with the model
architecture's requirement for a multimodal embedding per candidate, which must come
from *somewhere*, and with the SID system's established role as a compact content
identifier) rather than streamed per-request in the wire proto. This snapshot does not
contain the server-side code that would make this DIRECT.

**This closes the S00/S01 bidirectional-follow model-use boundary precisely**: DIRECT,
not inferred — `author_follows_viewer` (mutual/reciprocal follow, set by
`BidirectionalFollowHydrator`, S00/S01) reaches the model as `AuthorInfo.is_following_user`,
conditioned on the candidate not being a retweet — the identical eligibility condition
`RankingScorer`'s separate, local bidirectional-follow score boost already uses
(`02_ranking.md`, `bidirectional_boost_eligible`). The signal is therefore used **twice**,
independently: once inside the model itself (as an input feature, presumably influencing
every prediction head's output), and again inside `RankingScorer` (as an explicit
post-hoc weight boost on the reply/dwell heads) — these are two separate, compounding
uses of the same underlying relationship, not one mechanism described twice.

## What Phoenix predicts

Restated from `02_ranking.md` with the model-side confirmation now available:
`recsys.proto`'s `ActionName` enum defines ~200 distinct action types spanning organic
Home Timeline engagement (favorite/reply/retweet/quote/bookmark/share/mute/block/report/
video-quality-view/photo-expand/open-link/click/dwell/follow and many more), notification
events, search-relevance events, and ads engagement/conversion events — **one shared
vocabulary across multiple product surfaces**, not a Home-Timeline-specific list. The
`xrecsys_gen_recs` config caps the model's actual discrete output to `ACTION_TYPE_MAP_LEN
= 60` slots (rounded up to `OUTPUT_VOCAB_K = 64`) — meaning only a subset of the ~200
defined action types is actually predicted by any one model instance, not all of them.
`ContinuousActionName` is a separate, much smaller enum: `DWELL_TIME`,
`CLICK_DWELL_TIME`, `ACTIVE_SECS_5M_RESIDUAL_NORM`, and `BRIDGE_PROBABILITY` — the first
three match `RankingScorer`'s continuous heads exactly; `BRIDGE_PROBABILITY` is defined
in the proto but **not** referenced anywhere in `RankingScorer`'s consumption
(`02_ranking.md`) — a continuous output the model can produce that Home Mixer's ranking
formula does not currently use, at least not under the checked-in weight configuration
(its weight, if any, was not found).

## How Phoenix is trained

**One training example** (`xrecsys_gen_recs` config, `PhoenixDataset`,
`recsys_gen_recs_model.py`/`xrecsys_gen_recs.py`): a user's action-history sequence
(≤1023 items, each a post/author/surface/multi-hot-action/continuous-feature tuple) plus
a batch of candidate items (≤128) with their multimodal embeddings, drawn from
`aggregated_kafka` or `offline_kafka_dump_with_embeddings` dataset sources
(`DATASET_TYPES`, `xrecsys_gen_recs.py:35-38`).

**Objective and negatives**: for the `gen_recs` config specifically, an InfoNCE
contrastive loss between predicted and true next-item embeddings, with configurable
**global negatives** (`num_global_negatives=128` in production) drawn via a
`CandidateNegativeFilter`/`CandidateNegativeMode` mechanism — `filter_impression_negatives`
defaults to filtering negatives via `VQV_DWELL_10S` (a specific engagement-based
negative-sampling heuristic, not raw random sampling) and a `log_q_correction` to correct
for sampled-softmax bias (a standard technique when negatives aren't drawn uniformly).
The base `RecsysAggregatedModel`'s discrete/continuous multi-head path uses per-head
losses instead (binary cross-entropy-style for sigmoid heads, implied by the sigmoid
activation and `get_probs_and_labels`'s label-derivation logic; MSE/MAE/Huber/Tweedie for
continuous heads per `ContinuousActionLossConfig`) — this repo does not show a single,
unified end-to-end training script combining both objectives into one training run in
one file read this pass.

**Masking/sequence construction**: causal attention (`causal=True`,
`RecsysAttentionConfig`) — a position can only attend to earlier positions in the
constructed sequence, consistent with the user-then-history-then-candidates ordering.

**Checkpointing**: `CheckpointConfig` (`xrecsys_gen_recs.py:321-332`) — checkpoints every
500 steps, keeps every 100th checkpoint plus the last 10, verifies checksums, supports
resuming (`from_checkpoint=True`). No actual trained checkpoint/weights file ships in
this repository — only the training configuration and code that would produce one.

**Production vs. synthetic data, precisely separated**: the real dataset path
(`offline_kafka_dump_with_embeddings`/`aggregated_kafka`, reading from
`settings.GEN_RECS_OFFLINE_DATA_PATH`/`GEN_RECS_OFFLINE_ARTIFACTS_DIR`, environment-driven
paths with no baked-in values) is real production-shaped code, but requires real
Kafka-derived data this repository does not include. Separately,
`phoenix/reference/oss_recsys_synth.py` (not opened this pass, name and location
established from the earlier retrieval macro's directory survey) exists specifically to
generate synthetic data for local reproduction — the repository is explicit, through this
separation, that the checked-in *architecture* is runnable standalone with synthetic
data, while the *production data pipeline* requires infrastructure this snapshot does not
provide.

**Reproducibility split, stated precisely**: someone can reproduce the model
*architecture* (transformer config, embedding scheme, loss functions, training loop
shape) and train a toy/nano version end-to-end with synthetic data from this repository
alone. Nobody can reproduce X's actual *trained production model* from this
repository — that requires the real Kafka-sourced training data, the real multimodal
embedding infrastructure, and compute this snapshot does not include or specify beyond
config-level hyperparameters.

## Runtime configuration hierarchy

Synthesizing the pattern independently confirmed across all three prior reports (not
re-investigated fresh this pass beyond checking for a config-reload mechanism, which was
not found):

```
hardcoded Rust/Scala/Python constant
  (e.g. NEGATIVE_SCORES_OFFSET, MAX_FOLLOWERS_THRESHOLD, HighPageRankThreshold=54)
        │  — changing this requires a code change and redeploy; no runtime override path found
        ▼
checked-in param default (home-mixer/params/param.rs, "mirrored from config
  feature-switch defaults; last sync <timestamp>")
        │  — a periodically-refreshed COPY of an external default; this repo shows only
        │    the copy, not the live source
        ▼
feature-switch / GrowthBook override (xai_feature_switches::Params,
  RecipientBuilder-based matching — account age, phone verification, resurrection
  status, product/request-type, datacenter, per S01)
        │  — can differ per user/segment/experiment; this repo shows the MATCHING
        │    MACHINERY (how a request is bucketed) but not any live override values
        ▼
decider / xDS-routing gate (RouteGate::decider_only, e.g.
  "enable_phoenix_xds_traffic", "enable_vf_rust_should_drop_tweet")
        │  — a separate boolean-ish runtime toggle layer, distinct from numeric
        │    feature-switch values, gating which SERVER/PATH handles a request
        ▼
request/viewer-specific match (RecipientBuilder inputs resolved per request)
        → the final value actually used for THIS request
```

This is not a strict linear pipeline for every value — some behaviors (Botmaker/Scarecrow
rule `isActive` flags, abuse-enforcement-service's YAML rules) sit in a parallel,
differently-shaped config system (rule files with their own `isActive`/expiry fields,
also explicitly "mirrored from GrowthBook" for abuse-enforcement-service) rather than the
`xai_feature_switches::Params` hierarchy above.

**Values repeatedly cited across all four rapid reports that are runtime-overridable at
some layer above the hardcoded-constant floor**: essentially every weight in
`RankingScorer`'s `ScoringWeights` (favorite/reply/retweet/... weights, `OonWeightFactor`,
bidirectional-follow boosts), `ValueModelMode`, `EnableMpnScoring`, `VMRankerValueModelId`,
every retrieval source's `Enable*` flag, `EnableXaiVfClient`, cold-start thresholds,
new-user thresholds, and the decider gates governing xDS routing for Phoenix
retrieval/prediction and VMRanker. None of these has a confirmed production value in
this snapshot.

## Checked-in defaults vs live production

**What the "mirrored from config feature-switch defaults" header proves**: that a real
external feature-switch system exists, that this file is a snapshot of that system's
*default* values (not necessarily any particular user's or experiment's actual served
value) as of the stated sync timestamp, and that the checked-in defaults were at some
point consistent with that external system. **What it does not prove**: that the sync is
current, that no experiment currently overrides any given default for any segment of
traffic, that the decider/xDS layer routes any given request through the path the default
implies, or that per-user/per-experiment variation is absent — the `RecipientBuilder`
matching machinery this repo *does* show (S01) is specifically designed to support
per-request variation, which is direct evidence that such variation is architecturally
expected, not evidence of what it currently is.

**Is actual runtime configuration published anywhere in this snapshot?** No — no
GrowthBook export, decider-state dump, or experiment-assignment table was found anywhere
in this repository across all four rapid-track reports.

| Behavior | Checked-in default | Override mechanism | Production state knowable? | Reason |
|---|---|---|---|---|
| Retrieval source enablement (`EnableTweetMixerSource`, `EnablePhoenixMOESource`, etc.) | Mixed — some `true`, some `false` | feature-switch | No | Mirrored default only (`01_retrieval.md`) |
| Ranking mode (`ValueModelMode`) | `"weighted"` | feature-switch | No | Same |
| Action weights (favorite/reply/report/etc.) | Specific checked-in floats | feature-switch | No | Same |
| OON factor (`OonWeightFactor`) | `0.75` | feature-switch | No | Same |
| VMRanker/DPP (`VMRankerValueModelId`, `VMRankerDppTheta`) | `"dpp"`, `0.65` | feature-switch | No | Same; server-side DPP execution itself is external regardless |
| Ads blender internals | Not independently re-verified this pass | feature-switch (presumed) | No | Out of this macro's re-scope; established structurally in S02 |
| Rust VF selection (`EnableXaiVfClient`) | `true` | feature-switch | No | Same pattern (`03_eligibility_labels_visibility.md`) |
| New-user behavior thresholds | `0` (both new-user OON and Phoenix-cluster thresholds) — currently unreachable | feature-switch | No | Mechanism proven inert at default; production override state unknown |
| Cold-start slot/threshold params | `ColdStartSlotMin=15`, `SlotMax=16`, follower cap `1,000` | feature-switch | No | Same |
| Major experimentation gates (xDS deciders, `enable_vf_rust_should_drop_tweet`) | Branch logic only, no value shown | decider | No | Deciders are a separate runtime layer this repo never exposes a value for |

## Experiments and per-user variation

The `RecipientBuilder`/`FeatureSwitches` matching machinery (S01, re-confirmed structurally
by `RankingScorer`'s own test helpers constructing `FeatureSwitches`/`RecipientBuilder`
instances) is explicitly designed around per-request attributes — account age,
phone-verification status, resurrection status, product/request type, datacenter — which
is direct evidence the system supports differential treatment by user/segment/experiment.
Scarecrow's `PhoenixMoeCodivertViewerIs{Control,Treatment}` flags and `AuthorIsControl`/
`AuthorIsTreatment` author-rules bucketing (`02_ranking.md`'s cold-start section) are a
second, independent piece of evidence: an actual A/B experiment structure (viewer arm ×
author corpus) is wired into the checked-in ranking code, not merely hypothesized.
Whether any *specific* experiment is currently running, and for whom, is UNKNOWN — this
repo shows the capability and its checked-in wiring, never a live assignment.

## External service boundaries

| Service | Request this repo sends | Response expected | Visible locally | Hidden |
|---|---|---|---|---|
| `RetrievalDispatch`/xrecsys Phoenix retrieval | tweet-ID-free retrieval query, cluster ID, sequence, max results | ranked candidate tweet IDs | Call site, cluster resolution, retry/fallback param plumbing | Actual retrieval algorithm, index-to-live-serving connection (`01_retrieval.md`) |
| `PredictionDispatch`/Phoenix model serving | `PredictNextActionsRequest` (this report's field map above) | per-action logits/probabilities, per-continuous-head values | Full request shape; model architecture (this report) | Which exact trained checkpoint is loaded; live cluster→config binding |
| VMRanker server-side value model/DPP | `RankRequest` (candidate scores, phoenix_scores subset, DPP theta/max-rank, optional head weights) | per-candidate re-ranked score | Full request shape (`02_ranking.md`) | DPP kernel/similarity computation; how theta is actually applied |
| Gizmoduck | user ID batch + `QueryFields` (SAFETY, LABELS, etc.) | account safety flags, user labels, `allow_for_you_recommendations` and other account fields | Consumption sites across Home Mixer/VF/Scarecrow | The write path for `allow_for_you_recommendations`; internal Gizmoduck logic entirely |
| Social graph service | block/mute/follow relationship queries | boolean relationship flags | Consumption sites (S01, VF) | Internal implementation |
| External ad system | (S02's territory, not re-traced this pass) | — | Blending mechanism only | Ad selection/pricing itself |
| TweetMixer | `TweetMixerRequest` (client context, product context, max results) | scored candidates | Full request shape (`01_retrieval.md`) | Internal retrieval algorithm entirely — "UNKNOWN internals" already flagged |
| Botmaker/Scarecrow rule loader | — | rule definitions | A checked-in 20-rule subset (`03_eligibility_labels_visibility.md`) | Completeness of the corpus; live activation state |
| Abuse-enforcement-service upstream detectors | — | `score.labels`/`score.model_version` | Rule *consumption* of these labels | The detector models themselves (`inauthentic_detection_v45`, `cluster_spam_extended`, etc.) — named but not present in this snapshot |

This table is where "the open-source algorithm stops" becomes concrete: every row's
"Hidden" column is either a trained artifact (weights, thresholds), a live runtime value
(cluster bindings, config state), or another service's internal implementation this
repository documents the *interface* to but not the *behavior* of.

## Under the Hood transparency

Deep-read `under-the-hood/thrift/uth_serving.thrift` (full, 150 lines) and
`under-the-hood/strato/lib/underTheHoodLabels.strato` (first ~100 lines).

**What it exposes**: a per-user, per-calendar-month aggregate report
(`UthUserMonthAggregate`). For each month bucket: how many of the user's posts were
"eligible" (counted) each day (`eligiblePostAgg`); for each post-safety label, a
per-day count of posts that *carried* that label and posts that had it *removed* that
day (`UthPostLabelAggregate` → `UthDayCarriedRemoved`); for each account-level label, the
list of days within the month the account carried it (`UthAccountLabelAggregate`). A
separate `UthReferenceMonthAggregate` provides the same shape aggregated across an
anonymous cohort, bucketed by follower-count class (`UthFollowerClass`: `<1K`, `1K–10K`,
`10K–100K`, `≥100K`) and other cohort dimensions, with summary statistics (mean, p10
through p99) rather than per-user data — letting a user compare their own label rates to
similar accounts.

**What it does not expose, all confirmed by absence from the served schema**: no
per-post reasoning ("this specific post was filtered because X"), no ranking scores of
any kind (Phoenix predictions, `RankingScorer` output, VMRanker output), no retrieval
information (which source found a post, whether it was excluded from an index), and no
real-time data — the report is monthly-bucketed and explicitly dated
(`UthDaysIncluded.generatedAtMs`/`completeThroughDay` fields imply batch generation with
a completion lag, not live query). A `UthBrandSafetyAggregate`/`UthBrandSafetyCategory`
type exists in the schema but is explicitly commented **"experimental-only / unused
now"** and **"not served in reportJson"** — a dead field, structurally present but
inert.

**Raw vs. grouped**: labels are reported by name (a `label: String` field, not a raw
numeric ID), grouped into day-level carried/removed counts — genuinely aggregate, not a
raw per-post log a user could reconstruct individual filtering decisions from.

**Independent corroboration of this rapid track's VF findings**: `underTheHoodLabels.strato`'s
plain-English per-label descriptions match, label for label, what
`03_eligibility_labels_visibility.md` independently traced through
`visibility-filtering`'s Rust source: `SPAM_HIGH_RECALL`'s documented effect is "hidden
from recommendations to non-followers" (matching the OON-only drop this rapid track
confirmed via `tweet_label::SPAM_HIGH_RECALL_DROP`); `NSFW_HIGH_PRECISION`/
`NSFW_CARD_IMAGE`/`GORE_AND_VIOLENCE_HIGH_PRECISION` are documented as "shown behind
content warning" *and* "hidden from recommendations to non-followers" (matching the
exact interstitial-in-network/drop-OON duality independently confirmed in the corrected
`03` report's label-chain table); `SPAM` is documented as "not shown on X" (matching the
`base_home_rules()` universal-drop placement independently found in `registry.rs`). Two
separately-read parts of this repository — a Rust rule engine and a Strato transparency
schema — describe the same behavior consistently, which is meaningfully stronger
corroboration than either source alone.

**Verdict**: Under the Hood is real, working, aggregate label-transparency tooling — not
a ranking debugger, not a per-decision explainer, and explicitly not currently exposing
its (dead) brand-safety feature. It answers "how often has my content/account carried
label X this month, compared to similar accounts" and nothing about *why* or about
ranking.

## Reproducibility

| Component | Verdict | Explanation |
|---|---|---|
| Home Mixer orchestration | **YES** | Fully checked-in, compiled Rust; S01 established the complete stage sequence, this repository builds and (per prior passes' testing) runs |
| Retrieval components (Thunder, SimClusters ANN mechanics, retrieval source wiring) | **YES** (mechanics) / **PARTIALLY** (live data) | The code is complete; Thunder needs a live Kafka feed, SimClusters needs precomputed cluster embeddings this repo doesn't ship |
| Phoenix model architecture | **YES** | Full JAX model definitions, configs, and a runnable `gen_recs_nano` variant sized for local reproduction |
| A Phoenix training run | **PARTIALLY** | Architecture and training loop are real and runnable; the real dataset requires Kafka-sourced production data this repo doesn't include, though a synthetic-data path (`phoenix/reference/oss_recsys_synth.py`) exists for this exact purpose |
| X's actual trained production model | **NO / NOT FROM SNAPSHOT** | No checkpoint ships; cluster→config binding is external; training data is external |
| Current production feature-switch state | **NO / NOT FROM SNAPSHOT** | No live config export anywhere in this repository, confirmed by four independent rapid-track passes |
| VMRanker's exact behavior | **NO / NOT FROM SNAPSHOT** | Request shape is fully known (`02_ranking.md`); server-side DPP/value-model implementation is not in this snapshot |
| Full moderation behavior | **PARTIALLY** | VF's policy composition is fully reproducible (compiled Rust, tested); a real but explicitly partial subset of Botmaker/Scarecrow rules is reproducible; the complete rule corpus and BDSM's operating thresholds are not |
| A production-equivalent For You feed | **NO** | Requires the untrained-in-this-repo model checkpoint, live production feature-switch state, live external service behavior (VMRanker DPP, retrieval serving), and the complete (not partial) safety-label rule corpus — no single missing piece, but the combination is definitively not reproducible from this snapshot alone |

## Failure/degraded-operation pattern

The systemic pattern across all four rapid reports, not repeating individual tables:

- **Fails open (degrades quality, not availability)**: almost every *request-time*
  per-candidate/per-source/per-stage failure in the candidate pipeline (S01's
  framework-wide `update_all` semantics — a failing hydrator/scorer/source contributes
  nothing rather than failing the request); Home Mixer's VF RPC-chunk failures; VF's
  index-admission Rust-branch failures; Redis cache read failures (cache mode simply
  never activates); Gizmoduck author-hydration timeouts inside VF (with an optional
  stale-serve fallback).
- **Fails closed (removes/restricts rather than defaulting to safe)**: VF's
  missing-individual-result-within-a-successful-response case; VF's server-side
  unresolved-author case; the generic `FilterAllRule` backing every non-Timeline VF
  safety level (a maximally strict placeholder, not a real policy, for surfaces Home
  Mixer doesn't use).
- **Silently reduces candidate diversity without failing anything**: `SimclustersSource`'s
  single-signal-`?`-abort semantics (corrected in `01_retrieval.md` — one failed
  engagement signal zeroes the *entire* source's contribution, not just that signal's);
  any retrieval source's `enable()` gate returning false for structural reasons (no
  engagement signals, `in_network_only`, etc.).
- **Preserves prior score/state rather than blanking it**: `VMRanker`'s whole-call
  failure (leaves `RankingScorer`'s score exactly as computed); `PhoenixScorer`'s
  model-call failure (leaves `phoenix_scores` at its prior value, empty on a fresh
  request); cache-mode's reuse of stale-but-real Phoenix predictions re-weighted with
  live parameters.
- **Fails boot/service startup (fail-hard, not degraded)**: nearly every boot-time client
  constructor across the codebase panics on construction failure (S01's established
  asymmetry — request-time is graceful, boot-time is not), the one confirmed exception
  being `ThunderCapiClient`'s graceful `None` degradation.
- **Depends on external, unpublished semantics this repo cannot resolve**: Strato's
  `.fetch`/`.v` failure behavior on the legacy VF index-admission branch (the one
  genuinely unresolved failure-mode question from `03`'s corrections); VMRanker's
  server-side behavior on any input; the actual Phoenix model-serving cluster's behavior
  beyond what the client-side retry/fallback code shows.

**The one surprising inconsistency worth calling out**: index-time safety
(`shouldDropPostByVF`) and request-time RPC failures both fail open, but for different
reasons and at different granularities — index-time failure means a post *might* still
get indexed when it shouldn't (a false negative on exclusion, universal in scope);
request-time RPC failure means a post that already passed retrieval/ranking simply keeps
whatever `visibility_reason` it had before (`None`, i.e. effectively Allow) rather than
being blocked pending a retry. Both are "fail open" in the sense of favoring
availability over caution, but they fail open at structurally different points in the
pipeline with different blast radii — one affects every future viewer, the other affects
one request.

## What is directly knowable

- Home Mixer's complete orchestration, stage ordering, and failure semantics (S01, this
  track's `01`/`02`/`03`).
- The checked-in weight formulas, mode selectors, and their exact interactions in
  `RankingScorer`/`VMRanker` (`02_ranking.md`).
- Visibility filtering's complete rule composition, evaluation algorithm, and a large,
  independently-tested set of exact rule behaviors (`03_eligibility_labels_visibility.md`).
- A real, 20-rule, non-trivial subset of Botmaker/Scarecrow's checked-in rule
  definitions, with exact conditions/actions/thresholds (`03`, corrected).
- BDSM's architecture, training objective, and enforcement-pipeline *structure* (not its
  tuned thresholds).
- Phoenix's model architecture (both the retrieval-flavored and ranking-flavored
  variants), training loss shapes, and exact request-to-input-field mapping (this
  report).
- Under the Hood's exact data shape and its independent corroboration of the VF findings
  (this report).

## What remains unknowable from this snapshot

- Live feature-switch/GrowthBook values for any parameter cited across all four rapid
  reports.
- Which exact `PhoenixCluster`/model-config binding serves live ranking traffic.
- The trained weights of any production model (Phoenix, BDSM, or otherwise).
- BDSM's real operating-point thresholds (deliberately redacted).
- The complete Botmaker/Scarecrow rule corpus beyond the 20-rule checked-in subset.
- VMRanker's and the Phoenix retrieval-serving cluster's internal implementations.
- What sets `Gizmoduck.allow_for_you_recommendations = false` (S01-F008, still open
  after four passes).
- Legacy-branch (`shouldDropTweetV2`) exception-propagation semantics at index-admission
  time.
- Whether any specific experiment, A/B arm, or decider gate is currently live for any
  segment of traffic.

## Material findings

1. **Two structurally different Phoenix model objectives coexist in this codebase — a
   contrastive next-item-embedding retrieval model (`RecsysGenRecsModel`) and a
   multi-head discrete/continuous action classifier (`RecsysAggregatedModel`) — and this
   snapshot does not name which exact config serves Home Mixer's ranking path.**
   Significance: HIGH. Evidence class: DIRECT (both model shapes' existence and loss
   functions); STRONG_INFERENCE (that the ranking path uses the multi-head shape, from
   architectural fit with `RankingScorer`'s consumption pattern, not a named binding).
   Source: `phoenix/xrex/models/recsys_gen_recs_model.py:530-679` (InfoNCE loss),
   `phoenix/xrex/models/recsys_model.py:403-416,1940-1986` (sigmoid/continuous head
   activation).

2. **The S00/S01 bidirectional-follow model-use question is directly resolved:
   `author_follows_viewer` reaches the Phoenix model as `AuthorInfo.is_following_user`,
   gated to non-retweets — the same eligibility condition `RankingScorer`'s separate,
   local bidirectional boost uses, meaning the signal is used twice, independently.**
   Significance: HIGH. Evidence class: DIRECT.
   Source: `home-mixer/models/candidate.rs:202-211`.

3. **Discrete engagement heads are independently-sigmoided binary probabilities from a
   shared transformer representation; continuous heads have per-head-configurable
   activation and loss type, sometimes bounded via a `tanh` output cap — "continuous"
   does not mean "raw unbounded regression" for every such head.**
   Significance: HIGH. Evidence class: DIRECT.
   Source: `phoenix/xrex/models/recsys_model.py:195-227` (`ContinuousActionLossConfig`),
   `:403-416` (`get_probs_and_labels`), `:1940-1986` (activation dispatch).

4. **Raw post text and raw media embeddings are not present in the specific
   `PredictNextActionsRequest` Home Mixer sends — the wire request carries identifiers,
   counts, booleans, and a semantic ID, not content.**
   Significance: MEDIUM. Evidence class: DIRECT (the absence, confirmed by reading the
   full `as_tweet_info` field construction); STRONG_INFERENCE (that content is instead
   resolved server-side from the semantic ID — plausible given the model's multimodal
   embedding requirement, not independently proven by tracing the serving side).
   Source: `home-mixer/models/candidate.rs:167-215`, `home-mixer/util/phoenix_request.rs:98-118`.

5. **`param.rs`'s "mirrored from config feature-switch defaults" header, repeated
   verbatim across every rapid-track report's checked-in-defaults section, proves the
   existence of an external system and a sync timestamp — it proves nothing about
   current values, per-user variation, or decider state, and this repository contains no
   live-configuration export anywhere.**
   Significance: HIGH (foundational to every other report's evidence discipline).
   Evidence class: DIRECT (what the header literally states);
   UNKNOWN (actual production values, confirmed absent by a repo-wide pattern across
   four independent passes, not a single grep).
   Source: `home-mixer/params/param.rs:1`, and the same pattern independently
   re-confirmed for `abuse-enforcement-service`'s YAML rules
   (`03_eligibility_labels_visibility.md`).

6. **Under the Hood is real, working, aggregate/monthly label-transparency tooling that
   cannot explain any single filtering decision or expose any ranking signal — and its
   label-catalog documentation independently corroborates, label for label, this rapid
   track's VF findings.**
   Significance: MEDIUM–HIGH. Evidence class: DIRECT.
   Source: `under-the-hood/thrift/uth_serving.thrift` (full schema),
   `under-the-hood/strato/lib/underTheHoodLabels.strato:1-100`.

7. **A `UthBrandSafetyCategory`/`UthBrandSafetyAggregate` feature is present in Under the
   Hood's schema but explicitly, structurally dead — commented "experimental-only /
   unused now" and confirmed "not served in reportJson."**
   Significance: LOW. Evidence class: DIRECT.
   Source: `under-the-hood/thrift/uth_serving.thrift:36-42,63-67,76-77,104-106`.

8. **A `ContinuousActionName` value (`BRIDGE_PROBABILITY`) is defined in the model's
   output vocabulary but not consumed anywhere in `RankingScorer`'s checked-in weight
   configuration — a model output with no traced ranking consequence, structurally
   parallel to the untraced Scarecrow labels found in `03`.**
   Significance: LOW–MEDIUM. Evidence class: DIRECT (the definition and the absence from
   `RankingScorer`'s weight list, per `02_ranking.md`'s complete head inventory).
   Source: `phoenix/crates/serving/xai-recsys-proto/proto/recsys.proto:437-442`.

9. **The production Phoenix training config (`xrecsys_gen_recs`) is real, at-scale
   (`total_samples=1e11`), and structurally distinct from its `gen_recs_nano` sibling —
   this repository does distinguish production-shaped from test-shaped configuration
   explicitly, rather than shipping only one ambiguous config.**
   Significance: MEDIUM. Evidence class: DIRECT.
   Source: `phoenix/xrex/configs/xrecsys_gen_recs.py:136-190`.

10. **A candidate-batch-size mismatch exists between the model's configured
    `candidate_seq_len=128` and Home Mixer's much larger `PHOENIX_CLIENT_MAX_CANDIDATES=2800`
    request-side cap — the reconciliation mechanism (chunking, server-side truncation, or
    a different serving-time config) is not shown in this snapshot.**
    Significance: LOW–MEDIUM. Evidence class: DIRECT (both numbers, independently
    confirmed); UNKNOWN (the reconciliation mechanism).
    Source: `phoenix/xrex/configs/xrecsys_gen_recs.py:140`,
    `home-mixer/util/phoenix_request.rs:11`.

## Final handoff for synthesis

Facts the final human-readable synthesis **must preserve**, drawn from this and all
three prior rapid reports:

- Retrieval determines the *candidate pool*; ranking determines *order*; visibility
  filtering determines *what's actually shown* — these are three separate systems with
  three separate failure/override semantics, not one pipeline that can be described as a
  single black box.
- Ranking weights multiply *predicted probabilities/continuous values*, never raw
  engagement counts — a weight ratio is not an exchange rate, and this repository's own
  source comments say so directly.
- Checked-in defaults are not proven production values, anywhere in this repository,
  confirmed independently across four separate investigative passes covering retrieval,
  ranking, visibility, and now model/runtime configuration.
- Ranking and visibility filtering are separate systems with separate outcomes — a
  candidate can rank highly and still never reach the client.
- `Interstitial` is not `Drop` — an interstitialed post is delivered to the client with a
  flag, not removed; conflating the two misdescribes roughly a dozen VF rules.
- In-network and out-of-network content receive genuinely different eligibility and
  visibility treatment at multiple independent layers (retrieval gating, ranking's OON
  discount, VF's two-policy structure) — not one uniform "algorithm."
- External services — VMRanker's DPP kernel, the Phoenix retrieval-serving cluster, the
  full Botmaker/Scarecrow rule corpus — have their *request/response interfaces*
  documented in this repository but not their *internal behavior*.
- Cached-mode ranking reuses stale Phoenix predictions but re-runs local
  weighting/diversity logic with live parameters — it is not a frozen replay of a prior
  ranking.
- Public rule definitions exist in this repository exactly where they were actually
  found and read (visibility-filtering's full policy, abuse-enforcement-service's full
  YAML rules, a 20-rule Scarecrow subset) — the synthesis must not claim broader public
  rule coverage than what was independently verified, and must not repeat this rapid
  track's own earlier, corrected error of concluding "no rules are public" from an
  incomplete directory search.
- The Phoenix model's *architecture* is public and reproducible in miniature; its
  *trained weights* and *live cluster bindings* are not.

Common misconceptions the synthesis **must avoid**:

- "The algorithm is just likes minus reports" — the weighted-sum formula has ~26 heads,
  several structurally different scoring modes, diversity/OON/cold-start layers, and (in
  the non-default configuration) a completely different dwell-regret formula.
- "A label existing means it affects the feed" — `03`'s corrected report found several
  checked-in Scarecrow-written labels (`AGATHA_SPAM`, `RISKY_HIGH_VIZ_REPLY`,
  `COPYPASTA_SPAM`) with no confirmed VF consumer at all.
- "Interstitial means removed" — it does not (see above).
- "Botmaker rules are entirely secret" or, the opposite overcorrection, "the checked-in
  Botmaker rules are the complete production rule set" — both are false; a real,
  partial, unknown-completeness subset is public.
- "This repository proves what production actually does" — it proves what the checked-in
  *code* does with checked-in *default* values; production state was not found anywhere
  in this snapshot.

## Source coverage note

**Deep-read this pass**: `phoenix/xrex/configs/xrecsys_gen_recs.py` (full);
`phoenix/xrex/models/recsys_gen_recs_model.py` lines 1-729 (model construction, forward
pass, loss function — the remainder, ~210 lines, is supporting/test-adjacent code not
read); `phoenix/xrex/models/recsys_model.py` — targeted sections (lines 195-230, 380-420,
1940-1990; the base model class's full 3,178 lines were not read linearly, only the
head-activation and probability/label-derivation logic materially needed for B1/B4);
`phoenix/xrex/data/recsys/constants.py` (full); `phoenix/crates/serving/xai-recsys-proto/proto/recsys.proto`
lines 229-442 (`ActionName`/`ContinuousActionName` enums); `home-mixer/util/phoenix_request.rs`
(full); `home-mixer/models/candidate.rs` lines 125-216 (`as_tweet_info`/`as_score_info`
and their immediate context); `under-the-hood/thrift/uth_serving.thrift` (full);
`under-the-hood/strato/lib/underTheHoodLabels.strato` lines 1-100 (of 285 total).

**Mechanically searched/surveyed, not deep-read**: full directory listing of
`under-the-hood/` (26 files); `phoenix/xrex/models/` directory listing (10 files, 2
opened); `phoenix/xrex/configs/` directory listing (confirming `xrecsys_gen_recs.py` as
the production-scale config by comparing sibling configs' `total_samples` values, not by
reading every config file).

**Intentionally not exhaustively read**: `phoenix/xrex/models/recsys_model.py`'s
remaining ~3,100 lines (the base model's full transformer/attention/embedding
implementation beyond the specific head-activation logic this report needed);
`phoenix/xrex/models/{recsys_attention,recsys_embedding,recsys_two_tower_model,recsys_sid_retrieval_model}.py`
(confirmed to exist and their approximate role from naming/imports, not opened);
`phoenix/xrex/train/trainer_gen_recs.py` and the rest of `phoenix/xrex/train/` (the
actual training-loop driver code — config shape was read, the driver itself was not);
`phoenix/reference/oss_recsys_synth.py` (confirmed to exist from the earlier retrieval
macro's directory survey, not opened this pass); `under-the-hood/scalding/*.scala` (11
files — the offline aggregation jobs that presumably populate the `uth_serving.thrift`
structures; only the served schema and label catalog were read, not the jobs that
compute them); `under-the-hood/strato/columns/{featureSwitches,graphql/*,mh/*}.strato`
and `underTheHoodReport.strato`/`underTheHoodReport.User.strato` (the actual serving
endpoints and access-control wiring — only the data schema and label documentation were
read); no attempt was made to locate or read a config-reload/hot-update mechanism for
`xai_feature_switches` beyond confirming none was found via the files already read
across all four rapid-track reports.
