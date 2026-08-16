# Gap Closure — Remaining Questions Before Human Synthesis

Bonus pass, per the task instructions: not a new forensic S-pass, not a coverage-ledger
update, not the start of synthesis. Builds on `_analysis/reports/specialists/S01`/`S02`
and `_analysis/rapid/01`–`04`; does not restate them except where a claim changes.
`coverage_ledger.csv`, `analysis/full-audit`, and source were not touched.

## Executive result

The single most consequential new fact this pass found: `phoenix/reference/` (its own
`README.md`, `oss_bench/bench.py`, and `retrieve_then_rank.py`, plus
`phoenix/xrex/inference/launch_inference.py` and `phoenix/xrex/configs/xrecsys.py`) is a
previously under-read part of this repository that names, in the repo's **own shipped
benchmark/quickstart tooling**, which model-config *family* is paired with which gRPC
service type: `"ranking"` (the service `PredictNextActions` belongs to — Home Mixer's
`PhoenixScorer` path) defaults to `home_direct_packed_aggregated_kafka`;
`"retrieval"` (`RetrieveTopKCandidates`) defaults to `xrecsys_two_tower_aggregated_kafka`.
Neither is `xrecsys_gen_recs` — the config `04_model_runtime_boundaries.md` deep-read and
treated as the most-likely production candidate via architectural inference. This is not
proof of X's live production binding (still genuinely external — see below), but it is
**DIRECT, not inferred**, evidence of which config family this repository itself
documents and exercises for each service type, and it meaningfully narrows and corrects
Rapid 04's STRONG_INFERENCE. Full detail and exact evidence class breakdown below.

Section 2 (neglected retrieval sources) mostly reconfirms and deepens Rapid 01 rather
than correcting it — the one genuine addition is that `PhoenixSource`/`PhoenixTopicsSource`/
`PhoenixMOESource` are now confirmed, by full read of all three source files, to funnel
through the *identical* `RetrievalDispatch::retrieve_with_fallback` call with the same
argument shape, differing only in cluster-ID param, enable-gate, and (Topics-only)
topic-entity filtering — not three structurally different mechanisms. "MOE" is not
defined anywhere in this repository; this report does not guess it.

Section 3 (runtime configuration) did not find a mechanism this repo shows for going
from a checked-in default to a live value — the `RecipientBuilder` matching-key list is
now fully enumerated from source (see table), which sharpens "per-user variation is
architecturally supported" into "matching happens on these specific ~15 attributes,"
but no production value for any parameter was found, consistent with every prior pass.

Section 4 found no outright contradictions between forensic and rapid tracks — only
one already-corrected item (VMRanker/DPP, resolved in Rapid 04 and explicitly not
reopened per this task's own instructions) and a handful of scope clarifications worth
recording so the synthesis doesn't accidentally cite a superseded framing.

## Phoenix serving/model binding

### What was searched

Grepped and read, repo-wide: `PhoenixCluster`, `PhoenixRetrievalCluster`,
`Experiment1Fou`/`Experiment2Fou`/`Experiment1Lap7`/`Experiment3Fou`/`Experiment6Fou`,
`PredictionDispatch`, `RetrievalDispatch`, `PredictNextActions`/`predict_next_actions`,
`RetrieveTopKCandidates`, model registry/config-mapping files under
`phoenix/xrex/inference/` and `phoenix/xrex/configs/`, and the full `phoenix/reference/`
directory (previously only partially surveyed — Rapid 04 explicitly flagged
`oss_recsys_synth.py` as "not opened this pass" and did not read `reference/README.md`,
`retrieve_then_rank.py`, or `launch_inference.py`/`service_registry.py` at all). Time
spent: ~70 minutes, at budget.

### A. What client cluster identifier does Home Mixer send?

**DIRECT.** Two separate, independently-resolved cluster identifiers exist, one per
service:

- **Ranking** (`PhoenixScorer::resolve_cluster`, `home-mixer/scorers/phoenix_scorer.rs:24-60`):
  starts from `PhoenixInferenceClusterId` (checked-in default not independently
  re-confirmed this pass; prior passes cite `"Experiment1Fou"`), parsed into a
  `PhoenixCluster` enum. Two overrides can replace it: (1) a new-user override —
  if `PhoenixRankerNewUserHistoryThreshold > 0` and the viewer's `scoring_sequence`
  action count is below it, the cluster switches to whatever
  `PhoenixRankerNewUserInferenceClusterId` names instead; (2) a **decider-gated A/B
  override**, but only when the *already-configured* cluster is `Experiment1Fou` or
  `Experiment2Fou` — if so, `override_qf_use_experiment2_fou` wins over
  `override_qf_use_experiment1_fou` wins over the configured value. This exact
  three-layer resolution order was not previously traced in any rapid report.
- **Retrieval** (`PhoenixSource::resolve_cluster`, `home-mixer/sources/phoenix_source.rs:19-53`):
  structurally identical mechanism, separate parameter names
  (`PhoenixRetrievalInferenceClusterId`, `PhoenixRetrievalNewUserHistoryThreshold`,
  `PhoenixRetrievalNewUserInferenceClusterId`, deciders
  `override_retrieval_use_experiment2_fou`/`_experiment1_fou`), a `PhoenixRetrievalCluster`
  enum (not the same Rust type as ranking's `PhoenixCluster`, though the variant names —
  `Experiment1Fou`, `Experiment2Fou` — overlap). `PhoenixTopicsSource` and
  `PhoenixMOESource` reuse this exact same `PhoenixRetrievalCluster` type but read their
  own distinct params (`PhoenixRetrievalTopicInferenceClusterId`,
  `PhoenixRetrievalMOEInferenceClusterId`) with **no** new-user/decider override logic
  of their own (only the base `PhoenixSource` has that layer).

Both dispatchers (`PredictionDispatch`, `RetrievalDispatch`) pass the resolved cluster
value as an opaque string/enum into an external client
(`xai_candidate_pipeline::component_library::clients::phoenix_{prediction,retrieval}_client`)
— the crate implementing what a `PhoenixCluster`/`PhoenixRetrievalCluster` string
actually routes to at the network layer is not vendored in this snapshot (confirmed
again this pass; same conclusion as three prior passes).

### B. Where is that cluster translated to a concrete serving deployment?

**UNKNOWN**, unchanged from Rapid 04 — the routing table from a cluster string to a
physical/logical server pool is not in this repository. What this pass adds: the
override *decision logic* upstream of that routing (A, above) is now fully read, so the
UNKNOWN is narrower and more precisely located — it is specifically "what does
`phoenix_{prediction,retrieval}_client` do with the resolved cluster string," not the
whole cluster-resolution mechanism.

### C. Where is the serving deployment bound to a model config/class/checkpoint?

**Mechanism: DIRECT. Live production binding: UNKNOWN. Documented default pairing:
DIRECT.** This is the section's central finding.

`phoenix/xrex/inference/launch_inference.py` is the actual, runnable Phoenix
inference-server entry point in this repository — not previously read by any prior
rapid or forensic pass. It takes `--config_name` (selects a `RecsysTrainer` entry from
`xrex.configs.xrecsys.CONFIGS` or `xrex.configs.xrecsys_two_tower.CONFIGS`) and
`--checkpoint_path`, constructs a `RankingModelRunner` or `RetrievalModelRunner`
depending on `--service_type` (`"ranking"` → `PredictNextActions`; `"retrieval"` →
`RetrieveTopKCandidates` — this mapping is stated directly in the argparse help text,
`launch_inference.py:487-494`), and serves gRPC on `--grpc_port`. This *is* the
cluster→config→checkpoint→server binding mechanism the prior three passes correctly
identified as missing — its shape is now shown. What it does not show is the specific
`--config_name`/`--checkpoint_path` values live production passes for any named
`PhoenixCluster` string — that invocation (a deployment manifest, launch script, or
orchestrator config) is not in this snapshot.

What *is* new and DIRECT: this repository's own shipped benchmark and quickstart
tooling — not a training config comment, an actual runnable driver — states the
config-family pairing for each service type without ambiguity:

- `phoenix/xrex/inference/oss_bench/bench.py:25-28`:
  `DEFAULT_CONFIG_NAME_BY_SERVICE = {"ranking": "home_direct_packed_aggregated_kafka",
  "retrieval": "xrecsys_two_tower_aggregated_kafka"}`.
- `phoenix/QUICKSTART.md` §§2-5: trains and serves
  `home_direct_packed_nano_offline_kafka_dump` for the ranking step
  (`--service_type ranking --config_name home_direct_packed_nano_offline_kafka_dump`)
  and `xrecsys_two_tower_nano_offline_kafka_dump` for the retrieval step, then drives
  both together with `reference/retrieve_then_rank.py` over the real production gRPC
  contract (`RecsysRetrievalPredictorStub.RetrieveTopKCandidates` then
  `RecsysPredictorStub.PredictNextActions`).
- `phoenix/xrex/configs/data_feeds.py:58-61` independently names a Home-specific
  training data feed per config family: `"home_direct_packed":
  "user_action_sequence_home_direct_packed"` (and a matching `_nano` feed), distinct
  from `"xrecsys_seqpack": "user_action_sequence_xrecsys"` — a second, independent
  piece of evidence (a data-pipeline binding, not a serving binding) that
  `home_direct_packed` is the Home-surface-specific config family, not a generic one.

**This corrects/narrows Rapid 04's framing, not its caution.** Rapid 04 correctly
declined to name a DIRECT production binding, but its deep-read and STRONG_INFERENCE
discussion centered on `xrecsys_gen_recs` (an `InfoNCE`/contrastive next-item-embedding
config) as the most-examined candidate for the ranking-consumption path, reasoning from
`RankingScorer`'s ~26-head consumption pattern fitting the *general*
`RecsysAggregatedModelConfig` shape. That base-class reasoning remains correct — but
this pass finds `home_direct_packed*`, not `xrecsys_gen_recs`, is the config family this
repository's own tooling actually wires to the `"ranking"` service type. `xrecsys_gen_recs`
does not appear in `oss_bench/bench.py`, `QUICKSTART.md`, or `retrieve_then_rank.py` at
all — three independent, runnable, documented paths in this repository, none of which
route through it. **Corrected framing for synthesis: this repository's shipped
reference/benchmark pairing is `home_direct_packed*` (ranking) /
`xrecsys_two_tower*` (retrieval); `xrecsys_gen_recs` is a third, separately-defined
config (contrastive retrieval objective) that exists in the codebase but is not
exercised by any launch/bench/quickstart path this pass found — still UNKNOWN whether it
serves any live traffic, and now less likely to be the ranking path specifically than
Rapid 04's phrasing implied.** Neither claim is proof of X's actual production
deployment; "shipped reference pairing" and "live production binding" remain two
different, both-legitimate, still-separately-unresolved questions — this pass resolves
the former, not the latter.

One additional, minor finding: `launch_inference.py`'s own `--config_name` default
(`"xrecsys_aggregated_kafka"`, `launch_inference.py:449`) does not match any actual key
in `CONFIGS` (keys are generated as `{base_name}_{dataset_type}`, and no base name in
`MODEL_CFGS` is literally `"xrecsys"` — see `phoenix/xrex/configs/xrecsys.py:316-396`).
Every real invocation found in this repository passes an explicit `--config_name`; a
synthesis reader should not treat that unused default as naming anything real.

### D. Which preprocessing path consumes TweetInfo/AuthorInfo?

**Still not fully resolved; new negative evidence narrows the AuthorInfo question.**
`phoenix/xrex/models/recsys_feature_prep.py` (1,073 lines, function signatures fully
surveyed this pass) operates entirely on already-tensorized batches (`jax.Array`s) —
proto-to-tensor conversion is not in this file, and no file matching `TweetInfo`/
`tweetInfo`/`AuthorInfo` was found under `phoenix/xrex/` at all (only
`phoenix/reference/retrieve_then_rank.py` and `phoenix/xrex/inference/oss_bench/bench.py`
construct raw `TweetInfo` protos, and only to build requests, not to consume them
model-side) — the proto-marshalling layer that turns a wire request into the tensors
`recsys_feature_prep.py` reads is external/not vendored, same UNKNOWN as before.

What this pass adds: `xrecsys.py`'s shared `ContextFeaturesConfig.categorical_features`
list (lines 591-664, used by every `RecsysAggregatedModelConfig`-based config including
`home_direct_packed`) explicitly enumerates `product_surface`, `post_age`, `timezone`,
`local_hour_of_day`, `local_day_of_week`, `author_is_nsfw`, and bucketed
`fav_count`/`reply_count`/`repost_count`/`quote_count`/`view_count` as named categorical
features — a close, DIRECT, model-config-level match to the raw engagement-count fields
`04_model_runtime_boundaries.md` found in the wire request (`TweetInfo.*_count`). This
is stronger evidence than the wire-request table alone: it confirms, at the shared
model-config definition (not just the request schema), that engagement counts are
consumed as bucketed embedded features, not merely carried in the wire format unused.

**AuthorInfo.is_following_user re-examined, per the task's explicit instruction.** A
repo-wide grep across `phoenix/xrex/models/*.py` and `phoenix/xrex/data/recsys/*.py` for
`is_following`, `reciprocal`, `mutual_follow`, and `bidirectional` returned **zero
hits**. The same explicit `ContextFeaturesConfig.categorical_features` enumeration named
above does not include any follow-relationship feature. **This is additional negative
evidence, not proof of non-consumption** — a follow signal could still be folded into an
unlabeled slot of `UserFeaturesConfig`, into the SID embedding, or into a part of the
model this pass did not read (`UserFeaturesConfig`'s own field list was not exhaustively
cross-checked against every wire field this pass). **Boundary preserved exactly as
Rapid 04 stated it: DIRECT that the field reaches the request; STRONG_INFERENCE/UNKNOWN
that the deployed model consumes it — this pass narrows the UNKNOWN slightly (one more
specific place it is confirmed absent from) without resolving it.**

### E. Where are the ~26 output heads constructed?

Not re-investigated this pass — already DIRECT in Rapid 04
(`recsys_model.py:403-416,1940-1986`, `get_probs_and_labels`/continuous-activation
dispatch) and unaffected by the config-family correction above, since that logic lives
in the shared `RecsysAggregatedModel` base class both `home_direct_packed` and
`xrecsys_gen_recs`-adjacent configs inherit from.

## Neglected retrieval sources

Time spent: ~40 minutes (under budget — Rapid 01 had already done most of the mechanical
work; this pass mainly closed the "what differentiates X from Y" question by reading all
three Phoenix-family source files in full, not partially).

### WHAT IS TWEETMIXER?

**Confirmed, not newly resolved: a pure external black box, same conclusion as Rapid 01.**
This pass ran an explicit repo-wide search (`find`/`grep` across every top-level
directory) for a TweetMixer service implementation and found none — no `tweet-mixer/`
directory exists alongside `thunder/`, `simclusters/`, `phoenix-rankall/`, etc. Only two
files in this entire repository reference it:
`home-mixer/sources/tweet_mixer_source.rs` (the client-side integration — request
construction, enable-gating, response mapping) and `home-mixer/candidate_pipeline/
phoenix_candidate_pipeline.rs` (wiring). `TweetMixerSource` calls an external
`TweetMixerClient` trait via Wily service discovery, self-applies a 48h age filter, and
maps the response to bare `PostCandidate`s — the retrieval *algorithm* behind
`get_recommendations` is not this repository's to show, and no algorithm-adjacent
directory hides it elsewhere. **Answer for the synthesis: TweetMixer is an opaque
external recommendation service Home Mixer calls as a client; this snapshot documents
only the request/response contract, never the ranking logic inside it — there is
nothing more to find here without a different snapshot.**

### WHAT ARE PHOENIX TOPICS?

**Mechanism, DIRECT (now from a full read of `phoenix_topics_source.rs`, not partial).**
`PhoenixTopicsSource` is not a separate retrieval system — it is the exact same
`RetrievalDispatch::retrieve_with_fallback` call `PhoenixSource` makes, with three
differences: (1) it only runs on topic-scoped requests
(`is_topic_request() && !is_bulk_topic_request()`, no independent `Enable*` flag —
the one Phoenix-family source with no feature-switch gate of its own, reconfirming
Rapid 01's finding 9); (2) it resolves a distinct cluster ID
(`PhoenixRetrievalTopicInferenceClusterId`); (3) it additionally sends
`topic_entity_ids` (resolved from `query.topic_ids` via `TopicIdExpansion::resolve_first`)
and a `topic_filter_mode` (from `TopicFilteringExperiment`/`TopicFilteringOverrideMap`,
i.e. its own local A/B override layer, independent of the cluster-selection deciders in
Section 1). **Candidates are surfaced because the request itself carries topic IDs the
viewer is browsing (e.g. a Topic Timeline surface) — not because of followed topics or
inferred-interest topics in the profile sense.** Whether the *index* this cluster reads
from is itself organized by SID/semantic clustering (as `01_retrieval.md`'s
`phoenix-rankall` Sid pipeline variant suggests for the mainstream indices) versus a
separate topic-specific index is not shown by this client-side file — that remains the
same external-serving UNKNOWN Section 1 already documents for `PhoenixSource` generally,
not a new gap specific to Topics.

### WHAT IS PHOENIX MOE?

**"MOE" is undefined anywhere in this repository — this report does not guess it, per
the task's explicit instruction.** A repo-wide search for "mixture of experts" / "MoE"
(case-sensitive and insensitive, across `.py`/`.rs`/`.md`) returned zero hits outside the
literal `MOE`/`Moe` abbreviation embedded in identifiers
(`EnablePhoenixMOESource`, `PhoenixRetrievalMOEInferenceClusterId`,
`PhoenixMoeCodivertViewerIsControl/Treatment`, `AuthorPhoenixMoeEnabled`). Mechanically,
`PhoenixMOESource` (`home-mixer/sources/phoenix_moe_source.rs`, full file read) is —
like Topics — the identical `retrieve_with_fallback` call, gated by
`EnablePhoenixMOESource` (checked-in default `false`, per Rapid 01) plus the same
topic/in-network/cache exclusions as `PhoenixSource`, resolving its own cluster ID
(`PhoenixRetrievalMOEInferenceClusterId`), and tagging output `ForYouPhoenixRetrievalMoe`.
No topic-entity or filter-mode fields are sent (unlike Topics). The `PhoenixMoeCodivertViewerIs{Control,Treatment}`
and `AuthorPhoenixMoeEnabled` params (already known from `02_ranking.md`'s cold-start
section) sit in `RankingScorer`, not in `PhoenixMOESource` itself, and describe a
viewer-arm × author-corpus A/B bucketing structure layered on top of whatever MOE
retrieval returns — consistent with, but not proof of, the common ML reading "Mixture of
Experts" (a retrieval index or model built from multiple specialist sub-models/experts).
**This reading is plausible and unconfirmed — POSSIBLE, not DIRECT — and the synthesis
should present it exactly that way, or simply leave the acronym unexpanded.**

### WHAT DIFFERENTIATES PHOENIXSOURCE FROM PHOENIXTOPICSSOURCE AND PHOENIXMOESOURCE?

**For the human-readable synthesis, stated plainly:** all three are the same retrieval
mechanism (`RetrievalDispatch` → external Phoenix retrieval serving) pointed at
different cluster identifiers under different trigger conditions — not three different
algorithms. `PhoenixSource` is the general-purpose default (on by default, runs on
ordinary Home Timeline requests). `PhoenixTopicsSource` runs only when the request is
about specific topics and additionally tells the server which topics via
`topic_entity_ids`. `PhoenixMOESource` is an alternate retrieval variant, off by default,
that a feature switch can turn on for ordinary (non-topic) requests, pointed at its own
cluster — functionally a shadow/experiment retrieval path, same shape as `PhoenixSource`
but a different destination. The genuine unresolved question is what each destination
cluster actually *is* (see Section 1) — this repository's client code cannot tell that
part of the story.

### Table addendum (fields not already in Rapid 01's per-source table)

| Source | Own A/B override layer? | Fields sent beyond base retrieval request | Served-type tag |
|---|---|---|---|
| `PhoenixSource` | Yes (new-user threshold + decider, Section 1A) | `client_context`, `user_context` | `ForYouPhoenixRetrieval` |
| `PhoenixTopicsSource` | Yes, separate (`TopicFilteringExperiment`/`TopicFilteringOverrideMap`) | `topic_entity_ids`, `topic_filter_mode` | `ForYouPhoenixRetrieval` (same tag as `PhoenixSource` — not distinguishable downstream by served_type alone) |
| `PhoenixMOESource` | No (uses base cluster param directly, no override layer read in its own file) | none beyond the base call | `ForYouPhoenixRetrievalMoe` (distinct) |

Note worth flagging to the synthesis: `PhoenixTopicsSource` and `PhoenixSource` share
the identical `served_type` enum value (`ForYouPhoenixRetrieval`) — a downstream
consumer inspecting only `served_type` cannot distinguish topic-triggered retrieval from
ordinary retrieval; `PhoenixMOESource` is the only one of the three that is
self-identifying downstream.

## Runtime configuration and per-user variation

Time spent: ~35 minutes (under budget — the goal was one table plus the matching-key
enumeration, not a config audit).

### What actually varies a request's matching bucket

`home-mixer/server.rs`'s `QueryBuilder::build` (`RecipientBuilder` construction, read in
full this pass) is the complete, exhaustive list of attributes any feature switch can
match on for a given request — nothing else is available to the matching layer from
Home Mixer's side:

`user_id`, `country` (`proto_query.country_code`), `language`, `client_app_id`,
`client_version` (optional), `user_roles`, plus seven **custom** keys:
`datacenter` (server-local, not per-request), `account_age_days`,
`account_creation_date`, `has_phone_number`, `product` (request type — ForYou/
RankedFollowing/Following/etc.), `user_resurrected_date` (optional),
`days_since_resurrection` (optional), `account_age_minutes` (optional),
`minutes_since_resurrection` (optional). **This is the complete input set** — there is
no explicit experiment-bucket ID, no DMA/city, no device-type field, and no raw random
seed passed into `RecipientBuilder` from this file; if the external `xai_feature_switches`
system does percentage-based bucketing, it must derive it internally (e.g. hashing
`user_id`) — that internal logic is not in this snapshot (same UNKNOWN as every prior
pass, now with the exact input boundary nailed down).

Separately, debug endpoints (`get_debug_*`, S01-F011) apply caller-supplied
`fs_overrides` directly via `results.override_fs(key, value)` **after** normal matching
— this pass confirms that override point precisely (`server.rs`, immediately after
`match_recipient`): a debug caller can force *any* named parameter to *any* value for
that one request, bypassing matching entirely. Access control on that endpoint remains
unestablished (S01-F011, unresolved).

### Table: behavioral knobs and override scope

| Parameter | Checked-in default | Consumer | Override system | Matches on | Global? | Per-user? | Per-country? | Per-client/product? | Per-experiment? | Debug-overridable? | Reload semantics | Production value visible? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `EnablePhoenixSource`/`EnableTweetMixerSource`/`EnablePhoenixMOESource`/`EnableSimclustersSource` | Mixed (`true`/`true`/`false`/`false`) | Retrieval sources' `enable()` | feature-switch (`xai_feature_switches::Params`) | RecipientBuilder set above | Yes | Yes (via user_id/account_age/etc.) | Yes (country) | Yes (product/client_app_id/client_version) | Presumed yes (external bucketing logic not shown) | Yes (`get_debug_*`) | Static per request; refresh cadence external | No |
| `in_network_only` (not itself a `param!`, but downstream of one path) | n/a — computed, not defaulted | `QueryBuilder::build` | Client request OR server-forced (`RankedFollowingFeedService`/`FollowingFeedService`) OR `viewer_data.allow_for_you_recommendations` (Gizmoduck, external) | n/a | — | Yes, via account-status path | No | Yes, via server-forced surfaces | No | No (computed, not a param) | Per-request | Partially (Gizmoduck-side logic external) |
| `ValueModelMode` | `"weighted"` | `RankingScorer` | feature-switch | RecipientBuilder set | Yes | Yes | Yes | Yes | Presumed yes | Yes | Static | No |
| Action weights (favorite/reply/report/...) | Specific checked-in floats | `RankingScorer` | feature-switch | RecipientBuilder set | Yes | Yes | Yes | Yes | Presumed yes | Yes | Static | No |
| `OonWeightFactor` | `0.75` | `RankingScorer` | feature-switch | RecipientBuilder set | Yes | Yes | Yes | Yes | Presumed yes | Yes | Static | No |
| `EnableRanking` | `true` | `RankingScorer::enable` | feature-switch | RecipientBuilder set | Yes | Yes | Yes | Yes | Presumed yes | Yes | Static | No |
| `EnableVMRanker` | `true` | `VMRanker::enable` | feature-switch | RecipientBuilder set | Yes | Yes | Yes | Yes | Presumed yes | Yes | Static | No |
| `VMRankerValueModelId` | `"dpp"` | `VMRanker` request | feature-switch | RecipientBuilder set | Yes | Yes | Yes | Yes | Presumed yes | Yes | Static | No |
| `VMRankerDppTheta`/`VMRankerDppMaxSelectedRank` | `0.65` / `150` | `VMRanker` request | feature-switch | RecipientBuilder set | Yes | Yes | Yes | Yes | Presumed yes | Yes | Static | No |
| `EnableMpnScoring` | `false` | `RankingScorer` | feature-switch | RecipientBuilder set | Yes | Yes | Yes | Yes | Presumed yes | Yes | Static | No |
| `AdsBlenderType` | `"partition_organic_low_risk"` (falls through to `PartitionOrganicAdsBlender`, the code default, since it doesn't literally match `"safe_gap"`/`"time_gap"`) | `BlenderSelector` | feature-switch | RecipientBuilder set | Yes | Yes | Yes | Yes | Presumed yes | Yes | Static | No |
| `EnableXaiVfClient` | `true` | VF client selection | feature-switch | RecipientBuilder set | Yes | Yes | Yes | Yes | Presumed yes | Yes | Static | No |
| New-user thresholds (`PhoenixRankerNewUserHistoryThreshold`, `PhoenixRetrievalNewUserHistoryThreshold`) | `0` (both — mechanism inert at default) | `PhoenixScorer`/`PhoenixSource` cluster resolution | feature-switch | RecipientBuilder set | Yes | Yes | Yes | Yes | Presumed yes | Yes | Static | No |
| Cold-start params (`ColdStartImpressionThreshold`, slot min/max) | `1000` / `15` / `16` (per Rapid 04) | `RankingScorer` | feature-switch | RecipientBuilder set | Yes | Yes | Yes | Yes | Presumed yes | Yes | Static | No |
| Cluster selectors (`PhoenixInferenceClusterId`, `PhoenixRetrievalInferenceClusterId`, topic/MOE variants) | `"Experiment1Fou"`-family strings (per prior passes) | `resolve_cluster` (Section 1A) | feature-switch **plus** decider override **plus** new-user override — a 3-layer stack unique to this parameter | RecipientBuilder set (for the FS layer); decider gate is separate infra | Yes | Yes | Yes | Yes | Yes — explicit `override_qf_use_experiment{1,2}_fou`/`override_retrieval_use_experiment{1,2}_fou` decider flags exist specifically for this | Yes | Static (FS layer); decider layer's own reload semantics not shown | No |
| Brazil election filter (`Brazil2026ElectionFilter`) | Unconditional construction (S00/S01) | Pre-scoring filter | **No `enable()` override found** — this is the one behavior in this table that is NOT feature-switch-gated at all | n/a | Always on | Always on | Always on (not country-scoped in code, despite the name) | Always on | No | n/a (no gate to override) | Compiled-in | Yes, trivially — it always runs |

The Brazil filter row is worth calling out specifically for the synthesis: it is the one
"important behavioral knob" in this list that **cannot** vary by user/country/experiment
in the checked-in source at all, despite reading like a country-specific gate by name —
S00/S01 already established this; this pass re-confirms no `enable()` override exists
and it is unconditionally wired into `PhoenixCandidatePipeline`.

**Answer to the section's framing question**: for every row except the Brazil filter and
the cluster-selector row, "the checked-in default is X" and "what's actually served"
differ by exactly one layer of indirection this repository shows the *shape* of
(feature-switch matching on ~15 concrete request attributes, refreshed from an external
system at some unknown cadence) but never the *content* of (no live values, anywhere,
confirmed across five independent passes now). The cluster-selector row is the sole
exception with a **second**, independently-gated override layer (decider-based A/B) on
top of the standard feature-switch layer — meaning cluster selection specifically can
vary by at least two independent runtime mechanisms, not one, which the synthesis should
flag as the single most override-flexible parameter in the whole system.

## Supersession / reconciliation ledger

| Older claim | Source | Newer evidence | Final synthesis truth | Confidence | Notes |
|---|---|---|---|---|---|
| VMRanker's server-side DPP algorithm is external/unpublished | Implicit in earlier framing prior to `02_ranking.md`'s VMRanker section | `04_model_runtime_boundaries.md` explicitly corrects this: `vm-ranker/dpp.rs` is checked-in, full algorithm | VMRanker's DPP *algorithm* is public; only its live `--dpp-enabled` state and embedding-store contents are not | HIGH | Already resolved before this pass began; task explicitly says not to reopen it — listed here only so the ledger is complete, not as a new finding |
| Ranking-path model config is most-plausibly `xrecsys_gen_recs` (STRONG_INFERENCE) | `04_model_runtime_boundaries.md`, "Phoenix model architecture" section | This pass: `oss_bench/bench.py`, `QUICKSTART.md`, `data_feeds.py` all name `home_direct_packed*` for the `"ranking"` service type; `xrecsys_gen_recs` appears in none of the three | The repository's own shipped, runnable reference/benchmark tooling pairs `home_direct_packed*` with ranking and `xrecsys_two_tower*` with retrieval; `xrecsys_gen_recs` is a third config not exercised by any such path found | MEDIUM-HIGH (DIRECT that the shipped tooling names this pairing; still not DIRECT proof of X's live production binding — that remains genuinely unknown) | Correction, not contradiction — Rapid 04 was explicit that its conclusion was STRONG_INFERENCE, not DIRECT, and flagged exactly this class of gap as open; this pass closes it as far as the snapshot allows |
| `AuthorInfo.is_following_user` reaches the request (DIRECT) but internal model consumption is unproven (STRONG_INFERENCE/UNKNOWN) | `04_model_runtime_boundaries.md` | This pass: no follow-relationship feature name found anywhere in `phoenix/xrex/models/`'s categorical feature enumeration or a targeted grep for `is_following`/`reciprocal`/`mutual_follow`/`bidirectional` | Same boundary preserved exactly; this pass adds one more specific place the signal is confirmed absent from, without resolving the UNKNOWN | HIGH (on what was searched); the boundary itself is unchanged | Not a contradiction — an incremental narrowing in the same direction Rapid 04 already pointed |
| Retrieval sources beyond Thunder/SimClusters/Phoenix are under-documented by README (S01-F003), and their retrieval mechanics were only "placed," not deeply explained (Rapid 01's own stated limitation) | S01, `01_retrieval.md` | This pass reads `phoenix_topics_source.rs`/`phoenix_moe_source.rs` in full | `PhoenixTopicsSource`/`PhoenixMOESource` mechanics fully resolved as identical-dispatch variants of `PhoenixSource` (Section 2 above) | HIGH, DIRECT | Extension, not correction — Rapid 01's per-source table was already accurate on gating/limits; this pass adds the "why are these three separate types" answer it had flagged as future work |
| No contradictions found between S00/S01/S02 forensic claims and Rapid 01-04 | — | This pass's cross-read of S01/S02/Rapid 01-04 in full | Confirmed — no claim in S01 or S02 is contradicted by any rapid-track finding; every S0x→Rapid relationship found is EXTENDS or REFINES, never CONTRADICTS | HIGH | The forensic/rapid split appears to have worked as designed: forensic passes stayed conservative and rapid passes went deeper into the same files without finding daylight between the two |

No instance of "request-field-present mistaken for model-field-consumed," "checked-in
default described as production behavior," "Interstitial confused with Drop," or
"IN/OON inconsistency" was found in the four rapid reports on re-read — each report was
already explicit about that exact distinction wherever it applied (this is itself worth
telling the synthesis: the discipline held across all four prior passes, not something
this pass had to repair).

## Human-question gap test

25 questions a technically curious non-X reader would plausibly ask, checked against all
five reports (S01, S02, Rapid 01-05):

| # | Question | Status | Worth another S-pass? |
|---|---|---|---|
| 1 | Where does the first candidate come from? | ANSWERED | — |
| 2 | Why did I see someone I don't follow? | ANSWERED (OON retrieval sources + ranking's OON discount, not a bug) | — |
| 3 | Why might I repeatedly see one author? | ANSWERED (author-diversity discount exists but asymptotes to a floor, not zero — `02_ranking.md`) | — |
| 4 | How does a report affect ranking? | ANSWERED (weight ≈ -234 on predicted report probability, not a raw penalty per report — `02_ranking.md`) | — |
| 5 | Can a mutual follow help? | ANSWERED at the request-boundary and RankingScorer level; PARTIAL at the model-internals level | No — Section 1D of this pass already re-tried and hit the same wall; further search would not plausibly close it from this snapshot |
| 6 | Does X send the model the actual text? | ANSWERED — no, not in the specific request path traced (`04_model_runtime_boundaries.md`), content is SID-mediated (this pass upgrades this from wire-level inference to config-level DIRECT, Section 1D) | — |
| 7 | How are NSFW posts treated differently for followers/non-followers? | ANSWERED (`03_eligibility_labels_visibility.md`'s interstitial-in-network/drop-OON duality) | — |
| 8 | Can a high-ranked post still disappear? | ANSWERED (visibility filtering runs after ranking, is a separate system — `03`) | — |
| 9 | Does blocking someone affect recommendations? | ANSWERED (S01/`03`, consumption sites established) | — |
| 10 | Can cached feeds change order? | ANSWERED (`01_retrieval.md`'s cached-post path + `02_ranking.md`'s cached-request ranking section) | — |
| 11 | What happens if Phoenix is down? | ANSWERED (fails open, prior/empty predictions, `04`'s failure pattern section) | — |
| 12 | What exactly does DPP remove? | ANSWERED (`02_ranking.md`, VMRanker section) | — |
| 13 | What is TweetMixer? | ANSWERED, definitively external (Section 2 of this pass) | No — exhaustively searched, genuinely not in this repo |
| 14 | What changes for a new account? | ANSWERED (new-user thresholds, cold-start mechanism — `02`/`04`), though production threshold values remain UNKNOWN | — |
| 15 | Are weights the same for every user? | ANSWERED — architecturally no (feature-switch matching), but this pass is the first to enumerate exactly which ~15 attributes matching can key on (Section 3) | — |
| 16 | Can an experiment change ranking weights? | ANSWERED yes, mechanism shown; which experiment is live is UNKNOWN | No — production state is out of scope for a source-only repository by construction |
| 17 | What is known only from defaults? | ANSWERED — essentially everything numeric in every report, now stated in one table (Section 3) | — |
| 18 | Which moderation rules are actually public? | ANSWERED (`03`'s 20-rule Scarecrow subset, full VF policy, full abuse-enforcement YAML) | — |
| 19 | What is genuinely missing from the repository? | ANSWERED cumulatively across all five reports' "what remains unknown" sections | — |
| 20 | What is Phoenix Topics/MOE? | ANSWERED this pass (Section 2) | — |
| 21 | Does the model see raw engagement counts or just ratios? | ANSWERED this pass — bucketed categorical embeddings, DIRECT (Section 1D) | — |
| 22 | Why does Home Mixer send 2800 candidates when the model config caps at 128/64? | PARTIALLY ANSWERED — both numbers confirmed (`04`, and this pass's `home_direct_packed` base config showing `candidate_seq_len=64`, even smaller than `xrecsys_gen_recs`'s 128); the batching/chunking reconciliation mechanism is UNKNOWN | No — this is an external serving-engine implementation detail (`xai-recsys-engine`'s batching logic is in this repo but was not read this pass under the time budget; see below) — **borderline**, flagged not pursued |
| 23 | Can a debug/internal caller see live feature-switch values my request would get? | PARTIALLY ANSWERED — the override mechanism is shown (Section 3), the *read* side (can a caller query current values, not just set overrides) was not traced | No — S01-F011's access-control question already covers this territory and was explicitly left to S17/S18 |
| 24 | Is there a single global on/off switch for the whole recommendation algorithm? | UNANSWERED — no such kill-switch was found or looked for across any pass (individual scorer/source kill-switches exist, e.g. `PHOENIX_RANKER_KILL_SWITCH_DECIDER`, but no single one covering everything) | No — would require a targeted new search with low expected payoff; not attempted |
| 25 | Does the order candidates are retrieved in (Thunder first, Phoenix second, etc.) matter for the final feed? | ANSWERED no — merge is simple concatenation, scoring alone determines order (`01_retrieval.md`) | — |

21 ANSWERED, 3 PARTIALLY ANSWERED (#5, #22, #23), 1 UNANSWERED (#24) — questions #14 and
#16 are marked ANSWERED in the table above (their unresolved point is a live production
value, not the question itself) and are counted as ANSWERED here, not PARTIAL. None of
the partial/unanswered items are recommended for a further pass; each has an explicit
reason above.

## Remaining genuine unknowns

Carried forward, not newly discovered except where marked:

- The live cluster-string→deployment routing table (Section 1B) — architecturally
  external, not found in any form.
- X's actual live production model config/checkpoint for either service type — this
  pass narrows *which config family this repo documents as the reference pairing*
  (Section 1C) but does not and cannot prove that's what's deployed.
- Whether the deployed ranking model internally consumes `AuthorInfo.is_following_user`
  (Section 1D, narrowed not resolved).
- The `xai-recsys-engine`'s request-batching/chunking behavior reconciling Home Mixer's
  2800-candidate cap against the model's 64/128-candidate sequence capacity (human
  question 22) — `phoenix/crates/serving/xai-recsys-engine/` exists and was not read this
  pass; **new, not previously flagged this specifically** (Rapid 04 flagged the mismatch
  as UNKNOWN but had not identified this specific crate as the likely place to look).
- Live feature-switch/decider values for any parameter in Section 3's table.
- The complete Botmaker/Scarecrow rule corpus beyond the 20-rule checked-in subset
  (unchanged from `03`).
- BDSM's real operating thresholds (unchanged, deliberately redacted).
- What sets `Gizmoduck.allow_for_you_recommendations = false` (S01-F008, still open
  after five passes).
- The literal meaning of "MOE" in `PhoenixMOESource` (Section 2 — actively searched and
  confirmed genuinely absent from this snapshot, not merely unread).

## Questions deliberately left unresolved

Per the task's explicit "do not extend the investigation" instruction, these are listed,
not pursued:

- Whether `xai-recsys-engine`'s batching logic (human question 22) is worth a dedicated
  read — plausible payoff, not attempted here.
- Whether `phoenix/xrex/models/recsys_two_tower_model.py` (now confirmed as the actual
  shipped retrieval-service model family, not merely "for a different purpose" as
  Rapid 04 phrased it) deserves the same depth of read `recsys_gen_recs_model.py`
  received in Rapid 04 — its architecture (two-tower vs. single-sequence decoder) is
  materially different and would change how the synthesis describes Phoenix retrieval's
  model-serving side specifically (as opposed to the index-admission side `01_retrieval.md`
  already covers well). Not read this pass.
- Whether `xrecsys_gen_recs`'s contrastive objective is used anywhere in this repo's own
  tooling at all (it appears in no launch/bench/quickstart path found) — if genuinely
  orphaned/unused-by-shipped-tooling, that itself would be worth stating in synthesis
  more strongly than "not proven to be the ranking path"; not confirmed as orphaned vs.
  simply out of this pass's search scope.
- Whether a global kill-switch exists (human question 24) — not searched for.
- `under-the-hood/scalding/*.scala` and the Strato serving/access-control layer
  (already flagged unread in Rapid 04, still unread).

## Synthesis instructions

The final human-readable synthesis should treat these documents as authoritative for the
following topics, in this priority order when documents disagree (none currently do, per
Section 4's reconciliation ledger):

- **S01**: pipeline framework, orchestration, execution-order semantics, failure
  mechanics, service/pipeline inventory.
- **S02**: feed blending, ads-path mechanics, non-post source composition, feed-level
  filters.
- **Rapid 01**: retrieval — all seven candidate sources' mechanics, gating, and limits;
  Phoenix index-admission rules.
- **Rapid 02 + Rapid 04's VMRanker correction**: ranking formula, weights, VMRanker/DPP,
  diversity, cold-start.
- **Rapid 03 (corrected)**: labels, moderation rule inventory, visibility-filtering
  policy, Interstitial-vs-Drop semantics.
- **Rapid 04**: Phoenix model architecture (shared base-class mechanics — head
  construction, activation functions, training objective shapes), Under the Hood,
  reproducibility matrix, the general runtime-configuration-hierarchy *shape*.
- **Rapid 05 (this report)**: which specific model-config family (`home_direct_packed*`
  vs. `xrecsys_two_tower*` vs. `xrecsys_gen_recs`) is documented as serving which gRPC
  service type in this repository's own reference tooling (supersedes Rapid 04's
  `xrecsys_gen_recs`-centered STRONG_INFERENCE specifically on this one point — Rapid 04
  remains authoritative on everything else in the model-architecture section);
  Phoenix/Topics/MOE source differentiation; the exact `RecipientBuilder` matching-key
  enumeration; the two-layer (feature-switch + decider) override structure specific to
  cluster selection.

The synthesis should explicitly state, once, near wherever it discusses "which model
serves ranking": that this repository documents a shipped reference pairing
(`home_direct_packed*` for ranking, `xrecsys_two_tower*` for retrieval) via its own
benchmark and quickstart tooling, but that this is not independently verified as X's live
production binding — the same DIRECT-mechanism/UNKNOWN-production-value distinction this
entire rapid track has maintained throughout should apply here too, not a stronger claim
than the evidence supports.

## Source coverage note

**Newly deep-read this pass**: `phoenix/reference/README.md` (full), `phoenix/reference/
retrieve_then_rank.py` (full), `phoenix/xrex/inference/launch_inference.py` (full),
`phoenix/xrex/inference/service_registry.py` (full), `phoenix/xrex/inference/oss_bench/
bench.py` (full), `phoenix/xrex/configs/xrecsys.py` (full, 742 lines), `phoenix/xrex/
configs/config_registry.py` (full), `phoenix/xrex/configs/data_feeds.py` (targeted grep),
`phoenix/QUICKSTART.md` (targeted grep for config/service-type references),
`home-mixer/scorers/phoenix_scorer.rs` (full), `home-mixer/sources/phoenix_source.rs`
(full), `home-mixer/sources/phoenix_topics_source.rs` (full), `home-mixer/sources/
phoenix_moe_source.rs` (full), `home-mixer/server.rs` (targeted — `RecipientBuilder`
construction site), `home-mixer/params/param.rs` (targeted greps across ~20 named
params), `phoenix/xrex/models/recsys_feature_prep.py` (function-signature survey, not
full line-by-line read).

**Mechanically searched, not deep-read**: repo-wide greps for `PhoenixCluster`,
`Experiment{1,2,3,6}Fou`/`Experiment1Lap7`, `PredictionDispatch`, `PredictNextActions`/
`predict_next_actions`, `RetrieveTopKCandidates`, `TweetMixer` (confirming no internal
service directory exists), `MOE`/"mixture of experts" (confirming no acronym definition
exists), `is_following`/`reciprocal`/`mutual_follow`/`bidirectional` across
`phoenix/xrex/models/` and `phoenix/xrex/data/recsys/`.

**Intentionally not read this pass, flagged for a future pass if one is ever run**:
`phoenix/crates/serving/xai-recsys-engine/` (the batching/chunking logic that would
close human question 22); `phoenix/xrex/models/recsys_two_tower_model.py` and
`recsys_two_tower_evals.py` (now confirmed as the shipped retrieval-model family, not
independently deep-read for its own architecture the way `recsys_gen_recs_model.py` was
in Rapid 04); `under-the-hood/scalding/*.scala`; the full `xai-recsys-server/src/lib.rs`
(806 lines — only grepped for config/cluster-related symbols, which returned nothing
relevant, confirming it is a generic gRPC/HTTP server-bootstrap crate rather than
model-config-aware); `phoenix/xrex/inference/{gen_recs_services,serving_services,
sid_services,serving_filters_runner,status_server}.py` (named/located, not opened).
