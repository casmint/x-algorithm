# S02 — Home Feed Filters, Selection, Blending & Ads

## Scope and snapshot

- Upstream repository: `xai-org/x-algorithm`, branch `main`
- Upstream commit: `c65aa179db7bdd61e2c2821eac87f208a105c053`
- Upstream Git tree: `1d4c89941bfcd2ea3aab7c780f7447342e304e42`
- Snapshot identifier: `2026-08-15_c65aa17`
- Baseline tracked files: 2,016
- Pass: **S02 — Home feed filters, selection, blending, ads** (per `_analysis/passes/README.md`)
- Accepted cumulative analysis through S01 consulted as prior evidence (not re-audited): `ae818b5ea1a9e12322b4f1a8e40ab8ec5dd9dfe6`
- **Ownership determination is not a straightforward `primary_specialist == "S02"` query.** That query returns **zero rows** — see S02-F001. `_analysis/tools/build_specialist_map.py` maps every `home-mixer` file's `primary_specialist` to `S01` unconditionally; `S02` (like `S06`/`S17`/`S18`) can only ever be *appended* as a secondary pass, never `passes[0]`. This pass's working set is therefore the **62 files** where `specialist_passes` contains `"S02"` (all `primary_specialist == "S01"`) — the only non-empty, tool-derived signal tied to S02 at all, and the same set S01's own report already described as "explicitly deferred to S02 per the pass charter." This substitution is documented in every artifact this pass produced and is never conflated with "S02-primary" in the coverage-ledger sense (see "Coverage/accounting" below — the ledger itself was **not** modified by this pass, for the same reason).
- This report documents component-audit-level (`COMPONENT_REVIEWED`/`TRIAGED`) findings. No behavior-trace, discovery, or adversarial-verification pass has been performed; `pass_behavior_trace`, `pass_discovery`, `pass_adversarial_verify` remain `NO` for every file this pass touched.
- Per the task's explicit instruction, this pass is lean, not exhaustive: 14 material findings recorded in `S02_findings.jsonl`, not a claim-per-observation matrix. Mechanical component facts live in `S02_feed_composition_inventory.csv`.
- A number of files central to answering this pass's charter — the actual non-post blending sources (`AdsSource`, `WhoToFollowSource`, `PromptsSource`, `PushToHomeSource`, `JetfuelFrameSource`, `FeedSurveySource`, `ScoredPostsSource`, `ReverseChronPostsSource`) and the served-history side effects that feed several S02-owned filters — are **not** S02-tagged in the map (they carry `S01;S05`, tagged `D03`; see S02-F002). This pass read them directly as necessary supporting/boundary context to answer the central question, cited them as evidence throughout, but did **not** claim S02 review credit for them in `S02_file_review.csv` or the coverage ledger — consistent with the task's explicit instruction to read supporting files without marking them reviewed for another specialist.

## Executive feed-composition model

A feed response is built in two layers. **Layer 1** (S01's territory) produces a flat, unordered `Vec<FeedItem>` per source, concatenated with no interleaving. **Layer 2** (this pass's territory) is a `Selector` that partitions that flat list by `FeedItem` variant (Post / Ad / WhoToFollow / Prompt / PushToHome / Frame / FeedSurvey), blends the Post+Ad partitions through one of several ad-adjacency-aware algorithms, then inserts the remaining variants at fixed, param-derived slot positions via a strictly ordered sequence of list-insert calls — not a unified priority/ranking model. Four distinct `Selector` implementations exist (`BlenderSelector`, `FollowingBlenderSelector`, `TopKScoreSelector`, `PassthroughSelector`), and which one runs is a property of which `CandidatePipeline` is executing, which in turn is a property of which surface (For You / Ranked Following / Following / Reverse Chron / Phoenix Scores) the request is for. Filtering happens in two temporally distinct stages relative to selection — pre-selection (operates on the full candidate set, sequential, order-dependent) and post-selection (operates only on the already-selected top-K/blended set) — and the filters in each stage answer genuinely different questions: pre-selection filters are almost entirely eligibility/dedup/data-quality gates; post-selection filters are almost entirely adjacency-repair, visibility-consequence, or final-shape gates.

## For You blending

`ForYouCandidatePipeline` (home-mixer/candidate_pipeline/for_you_candidate_pipeline.rs) is constructed with, in declared order: 2 query hydrators (served-history, past-request-timestamps), **7 sources** — `ScoredPostsSource` (wraps `PhoenixCandidatePipeline::execute`, in-process, synchronous await — S01-F006), `AdsSource`, `WhoToFollowSource`, `PromptsSource`, `PushToHomeSource`, `JetfuelFrameSource`, `FeedSurveySource` — 1 pre-selection filter (`PushToHomeDedupFilter`), selector `BlenderSelector`, 1 post-selection filter (`AdAdjacentServedFilter`), and 9 side effects. `result_size() = FOR_YOU_MAX_RESULT_SIZE = 47` (`RESULT_SIZE`(35) + `FEED_MODULE_SLOTS`(4) + `MAX_JETFUEL_FRAMES_PER_RESPONSE`(8)) — the truncation the *whole pipeline* applies after `BlenderSelector::select` returns, which is larger than any individual ad blender's own internal `RESULT_SIZE`(35) truncation, meaning up to 12 non-post items (WTF/prompts/PTH/frames/survey) can be layered on top of a 35-item post+ad blend before the outer 47-item cap applies (S02-F013).

Each of the 7 sources is independently `enable()`-gated (see inventory) — none runs unconditionally on every request. `PushToHomeSource` and `PushToHomeDedupFilter` both gate on `query.push_to_home_post_id.is_some()`, a deep-link/push-notification-triggered request shape, not a general-request source. `FeedSurveySource` and `WhoToFollowSource` each require both a global param *and* a per-request eligibility flag (`feed_survey_eligible`, `who_to_follow_eligible`) whose own upstream computation is outside S02's owned files.

## BlenderSelector algorithm

`BlenderSelector::select` (home-mixer/selectors/blender_selector.rs) runs, in exactly this order:

1. `partition_feed_items` — buckets the input `Vec<FeedItem>` by variant into `posts`, `ads`, `wtf_modules`, `prompts`, `push_to_home` (`Option`), `frames`, `feed_survey` (`Option`).
2. `blender.blend(posts, ads)` — `blender` is chosen per-request by `query.params.get(AdsBlenderType)`: `"safe_gap"` → `SafeGapAdsBlender`; `"time_gap"` → `TimeGapAdsBlender { config: ... }` (constructed fresh from 4 query params); any other value (including unset) → `PartitionOrganicAdsBlender`, the default.
3. `insert_prompts` — stacks every prompt at increasing indices starting at 0 (front of the list).
4. `insert_who_to_follow` — inserts the (at most one) WTF module at `min(WHO_TO_FOLLOW_POSITION-1, len) = 5`.
5. `pin_push_to_home` — inserts at literal index 0, unconditionally displacing whatever prompts/WTF were just placed one slot lower (S02-F003).
6. `insert_frames` — delegates to `frames::plan`, which sorts pinned frames by rank, slots recurring frames at computed intervals, caps at `MAX_JETFUEL_FRAMES_PER_RESPONSE = 8`.
7. `insert_feed_survey` — inserts the single survey marker at `min(FEED_SURVEY_POSITION-1, len) = 11`.

None of steps 3–7 renumber the `.position` field of items placed in step 2 (S02-F004) — organic post/ad `FeedItem.position` values reflect their index within the smaller post+ad-only blend, not the final returned list's index. `non_selected` is reconstructed from a simple count difference (`input_post_count - output_post_count`, `input_ad_count - output_ad_count`) as placeholder `ScoredPost::default()`/`AdIndexInfo::default()` items — it does not preserve which specific candidates were dropped, only how many.

`BlenderSelector::score` always returns `0.0` — the selector does not itself rank; ordering is entirely a consequence of blend-then-insert mechanics, not a scored sort.

## Ads path

`AdsSource` (home-mixer/sources/ads_source.rs, read as supporting context) is gated on `EnableAdsSource` param AND `!query.is_preview` — ads never appear on preview requests. It forwards a rich `ClientContext` (country/language/IP/user-agent/device IDs) plus optional DSP context (Google SDK signals) to an external `AdIndexClient`; the response's `ad_info` list is converted to `FeedItem::Ad` **verbatim**, with no local re-ranking — whatever order/eligibility the external ad-index service returned is what Home Mixer receives. `ProductSurface` in the request differs by `RequestType` (`RankedFollowing` → `HomeTimelineRankedFollowing`; `Following` → `HomeTimelineLatest`; else → `HomeTimelineRanking`), mirrored identically in `AdsInjectionLoggingSideEffect`'s `display_location`/`product_surface` mapping (read as supporting context).

Three interchangeable ad-blending algorithms exist, selected per-request by the `AdsBlenderType` param (S02-F005):

- **`PartitionOrganicAdsBlender`** (default): computes `actual_ads = min(ads.len(), spacing-derived max, safe_posts/2)`, groups safe (non-`MediumRisk`) posts into equal-size groups, and for each ad in supply order tries to place it as an (above-post, ad, below-post) triple in the next group, subject to three adjacency checks (`should_drop_bsr_low`, `should_drop_handle`, keyword match against tokenized ad-adjacency-control keywords). An ad failing any check is skipped (not retried elsewhere); the placement loop only advances past a group once a triple is successfully formed. **If every ad fails every check (`placed_ads == 0`), all ads are dropped and the response falls back to score-sorted posts only** (S02-F006) — even though `AdsSource` returned eligible ads. The final list is truncated to `RESULT_SIZE = 35`, and the last item is popped if it is an ad (an ad is never the final item).
- **`SafeGapAdsBlender`** (param `"safe_gap"`): finds "safe gaps" (index positions where neither neighboring post is `MediumRisk`), computes an ideal spacing target from the first ad's `insert_position`, and binary-searches (`partition_point`) for the nearest safe gap to each ideal target. **It does not call `should_drop_bsr_low`, `should_drop_handle`, or any keyword check at all** — the only content-safety exclusion is the `MediumRisk` gap exclusion (S02-F005). This is a genuine, code-level asymmetry between two interchangeable, param-selected strategies for the same surface.
- **`TimeGapAdsBlender`** (param `"time_gap"`): identical adjacency-check machinery to `PartitionOrganicAdsBlender`, but spacing is computed from predicted per-post dwell time (`predicted_dwell_sec`, clamped) rather than post count, plus an additional `min_organic_gap` floor on the number of organic posts between ads. Shares the same all-ads-dropped fallback (S02-F006).

Post-selection, `AdAdjacentServedFilter` (home-mixer/filters/ad_adjacent_served_filter.rs) further constrains ad placement against the viewer's `served_ids`: for every ad adjacent to a previously-served post, it searches outward (near side first, then far side) for an eligible, non-served, non-ad-adjacent, brand-safety-compatible post to swap in. **It never drops an organic post; it drops the ad only when no swap candidate exists anywhere in the list** (S02-F007) — its own unit tests assert this explicitly. It is gated off for `is_bottom_request` and a `RequestContext` denylist (PullToRefresh, Launch, Signup, ForegroundTruncate, Gap) in addition to its feature-switch param, so it does not run on every request even when enabled.

What Home Mixer does **not** do: ad ranking, auction logic, budget pacing, or bid selection are entirely delegated to the external `ad_index` service behind `AdIndexClient` — none of that logic is present in this repository. This pass makes no claim about production ad-auction behavior; that boundary is routed to B11/B12.

## Who to Follow

`WhoToFollowSource` (read as supporting context) is gated on `EnableWhoToFollowModule` param AND `query.who_to_follow_eligible`. It builds a product-context request that differs by `RequestType` (`Following` → `HomeReverseChronWhoToFollowProductContext`; else → `HomeWhoToFollowProductContext`), excludes up to 200 previously-served WTF-recommended user IDs read from `query.served_history` (a third, independent consumer of the served-history write path alongside `PreviouslyServedPostsFilter` and `AdAdjacentServedFilter`), and truncates the response to `MAX_WHO_TO_FOLLOW_USERS = 3`. `BlenderSelector` inserts the resulting single `WhoToFollowModule` `FeedItem` at index 5 (displaced to 6 if a push-to-home post is also present). `FollowingBlenderSelector` (Following surface) only inserts WTF at all when `input_post_count > FOLLOWING_WHO_TO_FOLLOW_MIN_POSTS (10)` — a minimum-organic-content gate absent from the For You/Ranked Following path.

## Prompts

`PromptsSource` (read as supporting context) is gated only on `EnablePrompts` param. `DisplayLocation` differs by `RequestType` (`Following` → `HOME_LATEST_TIMELINE`; else → `HOME_TIMELINE`). Unlike WTF, there is no local cap on how many prompts the source can return — `BlenderSelector::insert_prompts` handles an arbitrary count by stacking each at increasing front-of-list indices, and every prompt's `FeedItem.position` field is hardcoded to the constant `PROMPTS_POSITION (0)` regardless of its actual stack index (part of S02-F004).

## Push to Home

`PushToHomeSource` (read as supporting context) is the only source gated on a request-shape field rather than a feature-switch param: `query.push_to_home_post_id.is_some()`. It fetches the focal tweet's core data via a TES client and, if the tweet is a root (not itself a reply), fetches up to `MAX_REPLIERS = 3` in-network top-repliers via a reply-mixer client for a "facepile" UI element — gracefully degrading to an empty facepile (logged warning, not a request failure) if the reply-mixer call fails. `BlenderSelector::pin_push_to_home` places the resulting single `FeedItem` at literal index 0, after prompts/WTF have already been inserted, so it always ends up ahead of them (S02-F003). `PushToHomeDedupFilter` runs pre-selection to remove any organic occurrence of the same tweet elsewhere in the candidate list, preventing a duplicate.

## Frames and surveys

Jetfuel frames are gated on a `TopicTimeline`-level `enabled` check plus `EnableJetfuelFrames`, and only apply to requests whose `query.topic_ids` contains one of 4 hardcoded sports topic IDs (soccer/NFL/MLB/baseball; home-mixer/frames/catalog.rs). Each catalog `TopicTimeline` carries `FrameDef`s that are individually `Pinned{rank}` (renders once, `Cadence::FirstResponseOnly` — suppressed on `is_bottom_request`) or `EveryNItems{first_slot,interval}` (recurring, `Cadence::EveryResponse`). `frames::plan` (home-mixer/frames/plan.rs) dedups by `(route, occurrence)`, sorts pinned frames by rank, slots recurring frames at computed intervals, and truncates the combined result to `MAX_JETFUEL_FRAMES_PER_RESPONSE = 8`; a route absent from the catalog is silently dropped, not errored. `JetfuelFrameSource` itself (not S02-tagged) was not independently opened this pass; its role and its use of `frames::served::resume_index` for occurrence continuation is inferred from the consumer-side files (`catalog.rs`, `plan.rs`, `served.rs`) that S02 does own, and is flagged as an open question in `S02_file_review.csv`.

`FeedSurveySource` (read as supporting context) is trivial: gated on `EnableFeedSurvey` param AND `query.feed_survey_eligible`, it emits exactly one empty-payload `FeedSurvey` marker `FeedItem` when enabled — the client is expected to render the actual survey UI from this marker alone. `BlenderSelector` inserts it at index 11.

## Pre-selection filters

`PhoenixCandidatePipeline`'s 18 pre-scoring filters run strictly sequentially in this exact declared order (home-mixer/candidate_pipeline/phoenix_candidate_pipeline.rs L345-373): `DropDuplicatesFilter` → `CoreDataHydrationFilter` → `AgeFilter` → `SelfTweetFilter` → `OONRetweetReplyFilter` → `OONNsfwSimclustersFilter` → `RetweetDeduplicationFilter` → `IneligibleSubscriptionFilter` → `PreviouslySeenPostsFilter` → `PreviouslySeenPostsBackupFilter` → `PreviouslyServedPostsFilter` → `MutedKeywordFilter` → `AuthorSocialgraphFilter` → `Brazil2026ElectionFilter` → `VideoFilter` → `TopicIdsFilter` → `NewUserMinEngagementFilter` → `InventoryHoldoutFilter`. Nine of these (`DropDuplicatesFilter`, `CoreDataHydrationFilter`, `AgeFilter`, `SelfTweetFilter`, `RetweetDeduplicationFilter`, `MutedKeywordFilter`, `AuthorSocialgraphFilter`, `Brazil2026ElectionFilter`, and — modulo its data-empty no-op — `PreviouslySeenPostsBackupFilter`) have **no `enable()` override at all** and therefore run unconditionally on every request through this pipeline, consistent with S01's broader finding that unconditional components are common, not exceptional.

Several filters' predicates are narrower or broader than their names suggest:

- **`OONRetweetReplyFilter`** drops OON retweets/replies *and* any reply (in-network or not) with empty `ancestors` — a data-quality guard bundled into an OON-named filter (S02-F008).
- **`TopicIdsFilter`**'s excluded-topics mode fails **closed**: a candidate with no topic-classification data (`filtered_topic_ids` is `None` or empty) is removed, not kept, whenever the request carries `excluded_topic_ids` (S02-F009) — the opposite default from its own inclusion-mode fallback.
- **`RetweetDeduplicationFilter`** (PhoenixCandidatePipeline) and **`FollowingRetweetDeduplicationFilter`** (ReverseChronPostsPipeline) are two different algorithms despite the similar name: the former is order-dependent keep-first on a canonical id; the latter always prefers a native tweet over a retweet of it, keep-first only among retweets.
- **`InvalidConversationModuleFilter`** (FollowingCandidatePipeline pre-selection) delegates to `select_conversation_modules`, which collapses each reply thread down to one "focal" (deepest) reply plus its now-non-redundant ancestors, dropping shallower replies and retweets of dropped roots — a thread-collapse mechanism, not a narrow "invalid content" removal (S02-F010).

`ReverseChronPostsPipeline`'s pre-selection filters (`FollowingRetweetDeduplicationFilter`, `SelfReplyChainFilter`) and `FollowingCandidatePipeline`'s single pre-selection filter (`InvalidConversationModuleFilter`) are unconditional (no `enable()` override) confirmed by direct read.

## Post-selection filters

`PhoenixCandidatePipeline`'s 3 post-selection filters run, in order, after the 6 post-selection hydrators (including `FollowingRepliedUsersHydrator` and `MutualFollowJaccardHydrator`, both S02-tagged and confirmed to run here, not pre-scoring, per home-mixer/candidate_pipeline/phoenix_candidate_pipeline.rs L419-422) on the top-50 (`TOP_K_CANDIDATES_TO_SELECT`) selected set: `VFFilter` → `AncillaryVFFilter` → `DedupConversationFilter`. `VFFilter` drops candidates whose upstream visibility-filtering result is `Action::Drop` or any non-`Allow` `FilteredReason` (deep VF semantics are S14's territory; this file only consumes the precomputed field). `AncillaryVFFilter` drops candidates flagged `drop_ancillary_posts`. `DedupConversationFilter` keeps only the highest-scored candidate per `conversation_id` (min-ancestor-id, or the candidate's own tweet id if no ancestors) — a distinct mechanism from `InvalidConversationModuleFilter` despite the naming overlap (S02-F010).

`ForYouCandidatePipeline`'s single post-selection filter is `AdAdjacentServedFilter` (see "Ads path" above). `PhoenixScoresPipeline`'s single post-selection filter is `ResultSizeFilter`, which truncates the caller-supplied, already-scored `seed_candidate_post_ids` set to a param-controlled limit (`PhoenixScoresResultSize`) via a simple `split_off` — no reordering, no adjacency logic; this operates on the debug/programmatic `PhoenixScoresService` endpoint, not a normal feed surface.

## Following / Ranked Following / Reverse Chron differences

These three are structurally distinct, confirmed by direct construction-site reads, not collapsed into one "Following feed":

- **Ranked Following** (`RankedFollowingCandidatePipeline`): sources = `[ScoredPostsSource, AdsSource]` only. Selector = `BlenderSelector` — the **same type** For You uses, not a dedicated implementation. Because no source on this pipeline ever produces WTF/Prompt/PushToHome/Frame/FeedSurvey `FeedItem`s, `BlenderSelector`'s corresponding insertion steps are all no-ops in practice; the selector's effective behavior degrades to `blender.blend(posts, ads)` (S02-F011). `result_size() = RANKED_FOLLOWING_MAX_RESULT_SIZE = 38`.
- **Following** (`FollowingCandidatePipeline`): sources = `[ReverseChronPostsSource (wraps ReverseChronPostsPipeline), AdsSource, WhoToFollowSource, PromptsSource]` — no PushToHome, no JetfuelFrame, no FeedSurvey. Pre-selection filter = `InvalidConversationModuleFilter`. Selector = `FollowingBlenderSelector`, a distinct implementation using `FollowingAdBlender` (the only ad blender that groups posts into conversation units and never places an ad inside one — S02-F012). `result_size() = FOLLOWING_PIPELINE_RESULT_SIZE = 102`; internally `ReverseChronPostsPipeline::result_size() = FOLLOWING_POST_FETCH_SIZE = 91 = FOLLOWING_MAX_RESULT_SIZE(100) - FOLLOWING_ADS_TOP_K(9)`, reserving an implicit 9-ad budget within the 100-item surface cap (S02-F013).
- **Reverse Chron** (`ReverseChronPostsPipeline`): the unranked post source `FollowingCandidatePipeline` wraps. Its own pre-selection filters, `FollowingRetweetDeduplicationFilter` and `SelfReplyChainFilter`, are unconditional and specific to this pipeline — not shared with `PhoenixCandidatePipeline`'s pre-scoring filter set.
- **Phoenix Scores** (`PhoenixScoresPipeline`): takes caller-supplied `seed_candidate_post_ids` instead of retrieving candidates (S01-F009); its sole S02-owned component is the post-selection `ResultSizeFilter`.

## Deduplication and already-served behavior

Three structurally independent seen/served-suppression mechanisms coexist on the ForYou path (S02-F014, the required resolution for S01-F001):

1. **`PreviouslySeenPostsBackupFilter`** — reads `query.impressed_post_ids`, which is permanently empty per S01-F001's wiring finding (`ImpressedPostsQueryHydrator` constructed but never added to the active query-hydrator `Vec`). This pass confirms the filter-level consequence directly: it early-returns `kept: all` whenever the field is empty, which is always. **Confirmed permanent no-op.**
2. **`PreviouslySeenPostsFilter`** — reads `query.seen_ids` (plus bloom-filter entries), which is populated **directly from the client-supplied `proto_query.seen_ids` field** at query construction (home-mixer/server.rs L116) — not from any query hydrator, and therefore entirely unaffected by S01-F001's wiring gap. This is a same-request, client-declared "I already rendered these" signal (typical of infinite-scroll clients). **Active, unconditional.**
3. **`PreviouslyServedPostsFilter`** — reads `query.served_ids`, populated across requests by `UpdateServedHistorySideEffect` (S01-primary, read as supporting context) writing every selected `FeedItem` (posts, ads, WTF, prompts, PTH, frames, survey) to server-side served-history storage after each response, then read back via served-history query hydration on later requests. Gated on `EnableServedFilterAllRequests` param OR (`is_bottom_request` AND not `ForegroundTruncate`) — primarily a pagination/scroll-down mechanism. **Active, conditionally gated.**

`AdAdjacentServedFilter` separately consumes the same `served_ids` for its swap-repair logic (see "Ads path"), and `WhoToFollowSource` separately consumes `served_history` to exclude previously-recommended WTF users — a fourth, non-post consumer of the same write path. `related_post_ids_iter` (home-mixer/util/candidates_util.rs, read as supporting context), the shared helper behind filters 1–3's "is this candidate related to a seen/served ID" check, considers only `tweet_id`, `retweeted_tweet_id`, and `in_reply_to_tweet_id` — the immediate parent, not the full ancestor chain.

Same-request exact-duplicate dedup is handled separately by `DropDuplicatesFilter` (exact `tweet_id`), `RetweetDeduplicationFilter` (canonical id = `retweeted_tweet_id` or own id, order-dependent keep-first), and post-selection `DedupConversationFilter` (highest-score-per-conversation).

## Side effects and future-request state

Traced as supporting context (S01-primary files, not independently claimed as S02-reviewed):

- **`UpdateServedHistorySideEffect`** writes every *selected* (not non-selected) `FeedItem` to served-history storage, gated on `is_prod() && EnableUrtMigrationComponents`. It builds distinct entry shapes per `FeedItem` variant (posts include the full ancestor chain, not just the leaf tweet; ads carry `impression_id`; WTF carries recommended user IDs). This is the write side of `PreviouslyServedPostsFilter`, `AdAdjacentServedFilter`, and `WhoToFollowSource`'s exclusion logic (see above).
- **`TruncateServedHistorySideEffect`** caps served history at `MAX_RESPONSES = 50` entries, deleting older ones — retention/cache-size management, gated the same way plus `served_history.len() > 50`.
- **`PublishSeenIdsToKafkaSideEffect`** publishes `query.seen_ids` (the client-supplied field, not the server-computed served history) as `Impression` records to Kafka, gated on `is_prod() && !seen_ids.is_empty() && EnablePublishSeenIdsToKafka` — a genuinely separate downstream consumer of the client-declared seen-IDs signal, distinct from same-request filtering.
- **`ServedAdHistoryCacheSideEffect`** writes ad-specific serving state to a short-TTL (5-minute) cache keyed by user+request-time, gated on `is_prod() && !is_preview`. This pass did not trace its consumer(s) — likely ad-frequency-capping, outside S02's owned files.
- **`AdsInjectionLoggingSideEffect`** logs the full timeline composition (selected + non-selected post/ad counts, per-item promoted flag, position, brand-safety verdict, slimmed ad-adjacency-control info, subscription level, IP/user-agent) to Kafka for ads measurement/audit, gated on `is_prod() && EnableAdsInjectionLogging`. `DisplayLocation`/`ProductSurface` mapping matches `AdsSource`'s request-side mapping exactly.

All side effects run via the framework's fire-and-forget `tokio::spawn` after response finalization (S01-F004/F005) — none can affect the *current* response; their observable effect is exclusively on future requests (served-history/dedup state) or external systems (Kafka, ad-history cache).

## Failure and degraded modes

- **Source failure**: framework-level per-source isolation (S01-F004) applies uniformly — a failing `AdsSource`, `WhoToFollowSource`, `PromptsSource`, etc. contributes zero candidates for that request without affecting other sources.
- **Ad blender failure mode (not an error, a policy outcome)**: `PartitionOrganicAdsBlender` and `TimeGapAdsBlender` silently drop **all** supplied ads if every adjacency check fails for every ad (S02-F006) — this is a normal return path, not a `Result::Err`.
- **`PushToHomeSource`**: TES lookup failure returns `Err` for the whole source (zero candidates that request); reply-mixer facepile failure degrades gracefully to an empty facepile list with a logged warning, not a source failure.
- **Query hydrator timeouts** (`FollowedGrokTopicsQueryHydrator`, `FollowedStarterPacksQueryHydrator`, both 300ms): timeout maps to `Err` for the whole hydrator, absorbed per the framework's silent-skip semantics (S01-F004) — the query proceeds without that field populated.
- **`AdAdjacentServedFilter`**: no external call; its "failure" mode is semantic (no eligible swap candidate found), handled internally as the ad-drop fallback, never a request failure.

## Runtime gating and experiments

`AdsBlenderType` (String param, `"safe_gap"`/`"time_gap"`/default) is the single highest-leverage experiment switch this pass found: it changes which of three materially different ad-adjacency-safety algorithms runs per request (S02-F005), including one variant (`safe_gap`) that skips content-adjacency checks entirely. `TimeGapConfig`'s 4 fields (`t_sec`, `clamp_lo`, `clamp_hi`, `min_organic_gap`) are all independently query-param-sourced, meaning the time-gap variant's actual spacing behavior is itself further parameterized beyond the blender-selection switch. This pass did not trace `AdsBlenderType`'s or `TimeGapConfig`'s production values (S17 territory) — only the code paths each value selects.

## Dormant / inert / orphaned components

- **`PreviouslySeenPostsBackupFilter`**: confirmed inert (S02-F014, carry-forward of S01-F001) — unconditionally enabled, always a no-op.
- **`PopularTopicsAuthorDedupFilter`**: not declared in `filters/mod.rs` (module-tree absent, corroborating S01-F002 at the filter-semantics level) — and even restored, its predicate (`served_type == ServedType::ForYouPopularTopics`) could never match without `PopularTopicsSource` (also module-tree-absent per S01-F002) supplying candidates with that `served_type`. Double-dormant by two independent mechanisms.
- **`PassthroughSelector`**: this pass found no construction site for it across the 6 pipelines it read; flagged as an open question in `S02_file_review.csv` rather than guessed at (this pass did not run an exhaustive repository-wide grep for it, so absence-of-evidence is not asserted as evidence-of-absence here).

## S01 carry-forward resolutions

| S01 item | S02 resolution | Status |
|---|---|---|
| **S01-F001** (`PreviouslySeenPostsBackupFilter` inert via orphaned `ImpressedPostsQueryHydrator`) | Confirmed at the filter level; additionally established that two other active, independently-wired seen/served mechanisms exist (client-supplied `seen_ids`, server-persisted `served_history`/`served_ids`) that are unaffected by the same wiring gap. "This filter is inert" ≠ "the system has no other seen/served dedup" (S02-F014). | CONFIRMED / RESOLVED |
| **S01-F002** (three module-tree-absent components, incl. `PopularTopicsAuthorDedupFilter`) | Corroborated directly (no `pub mod` line in `filters/mod.rs`); additionally established the filter's predicate has a second, independent reason it could never fire (its only served_type producer is also absent). | CONFIRMED / REFINED |
| **S01-F006** (ForYouCandidatePipeline peer-source composition; Phoenix model never sees ads/WTF/prompts) | Traced the full downstream consequence: `BlenderSelector` is the mechanism that composes the Phoenix-scored posts with the 6 injected non-post sources, via partition-then-insert, not a unified ranking. | CONFIRMED / EXTENDED |
| **S01-F007** (six previously-unplaced filters located) | This pass established the actual business logic of `AdAdjacentServedFilter`, `PushToHomeDedupFilter`, `FollowingRetweetDeduplicationFilter`, `SelfReplyChainFilter`, `InvalidConversationModuleFilter`, `ResultSizeFilter` — see "Pre-selection filters"/"Post-selection filters"/"Ads path" above. | CONFIRMED / EXTENDED |

## Important findings

14 findings recorded in `S02_findings.jsonl` (`S02-F001`–`S02-F014`); see that file for full evidence citations. Significance distribution: 3 HIGH, 7 MEDIUM, 4 LOW; 13 `DIRECT`/1 `STRONG_INFERENCE`; 13 `CONFIRMED`/1 `PARTIALLY_CONFIRMED`.

- **S02-F001/F002** (methodology): the specialist-map tool structurally cannot assign S02 primary ownership, and separately mistags the actual blending-source files as S05 territory.
- **S02-F005** (HIGH): `SafeGapAdsBlender` omits the ad-adjacency-safety checks the other two blenders apply — a real, code-level policy asymmetry between three param-selected, interchangeable strategies.
- **S02-F014** (HIGH): the required S01-F001 distinguishing answer — one dead mechanism, two live ones.
- The remaining 11 are MEDIUM/LOW naming-mismatch, ordering-interaction, and documentary findings — see `S02_findings.jsonl`.

## Public snapshot vs production boundary

- `AdsBlenderType`'s and every other `params.get(...)`-read param's actual production value is unestablished from this snapshot (S17 territory), consistent with S00/S01's prior findings on feature-switch defaults vs. runtime overrides.
- The external `ad_index` service's ranking/auction/pacing logic is entirely outside this repository — this pass establishes only the request Home Mixer sends and the response shape it receives, not what the external service does with it.
- `query.who_to_follow_eligible` and `query.feed_survey_eligible`'s own upstream computation was not traced (outside S02's owned files); this pass establishes only that these flags gate their respective sources.
- `AdIndexClient`, `WhoToFollowClient`, `PromptsClient`, `TESClient`, `ReplyMixerClient`, `ServedHistoryClient` internal implementations (S01-primary, `TRIAGED` by S01) were not independently opened by this pass; only their call sites and request/response shapes as consumed by S02-owned code were traced.

## Cross-domain handoffs

- **S05**: `AdsSource`/`WhoToFollowSource`/`PromptsSource`/`PushToHomeSource`/`JetfuelFrameSource`/`FeedSurveySource`/`ScoredPostsSource`/`ReverseChronPostsSource` internals carry the `S05` secondary tag per the domain map (S02-F002) — deeper client/protocol semantics beyond what this pass needed for blending-composition tracing remain S05's to own if it chooses.
- **S14**: `VFFilter`/`AncillaryVFFilter`'s consumed `visibility_reason`/`drop_ancillary_posts` fields are computed by `VFCandidateHydrator` (S01-primary); this pass establishes only the consuming filter's predicate.
- **S17**: `AdsBlenderType`, `TimeGapConfig`'s four fields, and every `enable_or_gate` param named in `S02_feed_composition_inventory.csv` need production-value verification.
- **S18**: `ServedAdHistoryCacheSideEffect`'s consumer(s) were not traced; `AdsInjectionLoggingSideEffect`'s Kafka topic and downstream ads-measurement consumers are outside this repository.
- **B01/B02**: this report plus the inventory are a primary source for "every way a non-post item can enter/be excluded from the final feed."
- **B09**: `Brazil2026ElectionFilter`'s exact predicate (author/retweeted/quoted/ancestor, follow-exempted) and `TopicIdsFilter`'s fail-closed excluded-topics behavior (S02-F009) are both legal/geo-flavored content-suppression mechanisms worth B09's attention.
- **B10**: S02-F004 (position staleness), S02-F006 (all-ads-dropped fallback) are both silent degraded-mode behaviors, not errors.
- **B11**: the full "Ads path" section plus S02-F005/F006 are this pass's primary contribution to monetization/access tracing; the external ad-auction boundary is explicitly out of scope.

## Unknowns

- Whether `JetfuelFrameSource` actually calls `frames::served::resume_index` for occurrence continuation — inferred from consumer-side files only, not independently opened (`JetfuelFrameSource` is S01;S05-tagged, not S02).
- Where (if anywhere) `PassthroughSelector` is constructed — no construction site found across the 6 pipeline files this pass read; not confirmed dormant, not confirmed live.
- `AdsBlenderType`'s and `TimeGapConfig`'s production values — routed to S17.
- `ServedAdHistoryCacheSideEffect`'s downstream consumer(s) — routed to S18.
- Whether an in-network reply's missing-ancestors case (the second `OONRetweetReplyFilter` disjunct, S02-F008) reflects a specific upstream hydration-failure mode — not traced (candidate-hydrator territory, S01).

## Coverage/accounting

- **S02-primary assigned files per `primary_specialist == "S02"`: 0** — this is a confirmed, direct fact about `_analysis/passes/file_specialist_map.csv`, not a gap in this pass's execution (S02-F001).
- **Operational S02 working set** (files where `specialist_passes` contains `"S02"`, all `primary_specialist == "S01"`): **62 files**, computed directly from `file_specialist_map.csv`. Breakdown: `home-mixer/ads/` 12 (incl. 6 test files), `home-mixer/candidate_hydrators/` 4, `home-mixer/candidate_pipeline/` 1, `home-mixer/filters/` 29, `home-mixer/frames/` 5, `home-mixer/query_hydrators/` 6, `home-mixer/selectors/` 5.
- **Files examined and reviewed: 62 / 62** (100% accounted for in `S02_file_review.csv`, one row each, zero duplicates, zero missing, zero extras — verified programmatically). `COMPONENT_REVIEWED`: 56 files (all non-test files, including all 29 filters, all 5 selectors, all 5 frames files, all 6 query hydrators, all 4 candidate hydrators, the ForYouCandidatePipeline construction file, and 6 of the 6 non-test ads files). `TRIAGED`: 6 files (the `home-mixer/ads/tests/*.rs` suite — read indirectly via the fully-read implementation files they test, per methodology invariant 7: tests support, not substitute for, implementation evidence).
- **Supporting/boundary files read but not claimed as S02-reviewed** (their coverage-ledger state, S01's or otherwise, was not touched): the 8 non-post/wrapping sources (S02-F002), 5 side effects (`ServedAdHistoryCacheSideEffect`, `UpdateServedHistorySideEffect`, `TruncateServedHistorySideEffect`, `PublishSeenIdsToKafkaSideEffect`, `AdsInjectionLoggingSideEffect`), `home-mixer/util/conversation_grouping.rs`, `home-mixer/util/candidates_util.rs`, `home-mixer/server.rs` (single line, `seen_ids` population), `home-mixer/candidate_pipeline/{ranked_following_candidate_pipeline,following_candidate_pipeline}.rs` (construction-site confirmation only), `home-mixer/params/config.rs` (constant values only).
- **Coverage ledger: not modified by this pass.** Because `primary_specialist == "S02"` is empty (S02-F001) and every file this pass reviewed carries `primary_specialist == "S01"`, updating `coverage_ledger.csv` rows for these 62 files would mean altering S01-owned rows — which the task explicitly prohibits ("Do not alter S00/S01 coverage rows"). This pass made the conservative, non-destructive choice to leave the ledger untouched rather than risk overwriting S01's legitimate ownership markers, and documents this reasoning here and in `S02_run.md` rather than silently deviating from the instruction. This is itself the practical consequence of S02-F001 and should be resolved by whoever next revises the mapping tooling or the ledger's update rules.
- Material findings: 14 (`S02-F001`–`S02-F014`); 3 HIGH, 7 MEDIUM, 4 LOW; 13 `DIRECT`/1 `STRONG_INFERENCE`.
