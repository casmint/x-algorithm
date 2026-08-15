# S01 — Candidate Framework + Home Mixer Orchestration

## Scope and snapshot

- Upstream repository: `xai-org/x-algorithm`, branch `main`
- Upstream commit: `c65aa179db7bdd61e2c2821eac87f208a105c053`
- Upstream Git tree: `1d4c89941bfcd2ea3aab7c780f7447342e304e42`
- Snapshot identifier: `2026-08-15_c65aa17`
- Baseline tracked files: 2,016
- Pass: **S01 — Candidate framework + Home Mixer orchestration** (per `_analysis/passes/README.md`)
- Accepted S00 analysis head consulted as prior evidence (not re-audited): `ae68bca41ccd680b46695bbfc15b67fea69e8e87`
- S01-primary ownership, verified against `_analysis/passes/file_specialist_map.csv` before any review began: **227 files**, matching the framework's expected workload exactly. Files: 216 under `home-mixer/`, 11 under `candidate-pipeline/`.
- This report documents component-audit-level (`COMPONENT_REVIEWED`/`TRIAGED`) findings only. No behavior-trace, discovery, or adversarial-verification pass has been performed; `pass_behavior_trace`, `pass_discovery`, `pass_adversarial_verify` remain `NO` for every S01 file in the coverage ledger.
- Per the task's explicit instruction, this pass is lean, not exhaustive: no S01 equivalent of S00's row-per-claim matrix was produced. Evidence is captured in `S01_pipeline_inventory.csv` (mechanical component census) and `S01_findings.jsonl` (13 material findings), not in prose duplication.

## Executive architecture

A For You / Scored Posts request enters through one of **five gRPC services** implemented in `home-mixer/server.rs` (`ScoredPostsService`, `ForYouFeedService`, `RankedFollowingFeedService`, `FollowingFeedService`, `PhoenixScoresService`), each backed by one of **six** `CandidatePipeline` implementations. Every request first passes through the shared `QueryBuilder::build`, which fetches viewer account state (Gizmoduck, 200ms timeout, fails open) and resurrection timestamp (same pattern), computes feature-switch targeting, and constructs a single shared `ScoredPostsQuery` struct used by all six pipelines.

The **Post Pipeline** (`PhoenixCandidatePipeline`) retrieves candidates from 7 sources (not the 3 README names), hydrates them through 12 candidate hydrators, filters through 18 pre-scoring filters, scores through 3 scorers in strict sequence (`PhoenixScorer` → `RankingScorer` → `VMRanker`), selects the top-K, hydrates/filters again post-selection (6 hydrators, 3 filters — visibility filtering lives here), and fires 8 side effects in the background. The **Blending Pipeline** (`ForYouCandidatePipeline`) is *not* a wrapper around the Post Pipeline in any structural sense: it is an entirely independent `CandidatePipeline` instance whose own `ScoredPostsSource` happens to `.await` the Post Pipeline's full execution synchronously, in-process, as one of 7 concurrent candidate sources (the others being ads, Who-to-Follow, prompts, push-to-home, Jetfuel frames, and a feed survey). This exact "peer-source composition" pattern recurs twice more: `RankedFollowingCandidatePipeline` also wraps `PhoenixCandidatePipeline` via the same `ScoredPostsSource`, and `FollowingCandidatePipeline` wraps a sixth, unranked pipeline (`ReverseChronPostsPipeline`) via `ReverseChronPostsSource`.

The execution engine itself (`candidate-pipeline/candidate_pipeline.rs`) runs query hydrators, sources, candidate hydrators, and post-selection hydrators **concurrently** within each stage (`tokio::join_all`), but runs **filters and scorers strictly sequentially** in declared array order — meaning filter/scorer order is directly causal to the result, not a documentation nicety. Failures are pervasively designed to degrade gracefully at request time (a failing hydrator/scorer/source silently contributes nothing for that unit rather than failing the request) while being designed to crash-and-restart at boot time (`.expect()` panics on nearly every client constructor).

S01 also surfaced three components that are either miswired or entirely disconnected from the compiled crate, one of which silently neuters a filter the README documents as functioning.

## Service/request entry points

Five `tonic` gRPC services, all registered in `HomeMixerServer::register` (`home-mixer/server.rs:L922-L978`):

| Service | Pipeline(s) behind it | README documents it? |
|---|---|---|
| `ScoredPostsService` | `PhoenixCandidatePipeline` (direct) | Yes (implicitly, as "the model") |
| `ForYouFeedService` | `ForYouCandidatePipeline` → `PhoenixCandidatePipeline` | Yes (the documented request path) |
| `RankedFollowingFeedService` | `RankedFollowingCandidatePipeline` → `PhoenixCandidatePipeline`, forces `in_network_only=true` at the server layer | No |
| `FollowingFeedService` | `FollowingCandidatePipeline` → `ReverseChronPostsPipeline` (unranked), forces `in_network_only=true` at the server layer | No |
| `PhoenixScoresService` | `PhoenixScoresPipeline`, takes caller-supplied `seed_candidate_post_ids` instead of retrieving candidates | No |

`QueryBuilder::build` (`home-mixer/server.rs:L74-L162`) is the single shared construction path for every endpoint. It validates `viewer_id != 0`, force-samples tracing for `TRACE_USER_IDS` (checked-in empty per S00), concurrently fetches `ViewerData` and resurrection time (both fail open on timeout/error), evaluates feature switches against a `RecipientBuilder` (account age, phone-verification, resurrection status, product/request-type, datacenter), and constructs the query. **`in_network_only` is computed as `proto_query.in_network_only || viewer_data.allow_for_you_recommendations == Some(false)`** — an account-status override on top of whatever the client requested (S01-F008).

Debug variants of every endpoint (`get_debug_*`) additionally accept `feature_switch_overrides` from the caller and apply them directly to that request's `Params` (S01-F011) — this repository does not establish that endpoint's access-control boundary.

A hardcoded 2-user-ID allowlist (`params::TEST_USER_IDS`) short-circuits pipeline execution entirely, consistently, in **all five** server structs (S01-F010).

## Candidate-pipeline execution semantics

`candidate-pipeline/candidate_pipeline.rs`'s `CandidatePipeline::execute_stages` (`L97-L148`) defines the single execution sequence every pipeline instance runs:

```
hydrate_query (concurrent)
  → hydrate_dependent_query (concurrent; empty unless a pipeline overrides dependent_query_hydrators())
    → fetch_candidates / sources (concurrent)
      → hydrate / candidate hydrators (concurrent)
        → filter / pre-scoring filters (SEQUENTIAL, declared order)
          → score / scorers (SEQUENTIAL, declared order)
            → select (single selector)
              → hydrate_post_selection / post-selection hydrators (concurrent, selected candidates only)
                → filter_post_selection / post-selection filters (SEQUENTIAL)
                  → truncate to result_size() → finalize() hook → side effects (tokio::spawn, fire-and-forget)
```

Every stage first filters components by `.enable(&query)`; a disabled component simply does not run — no error, no placeholder.

**Failure semantics (S01-F004), established by reading the trait default implementations directly, not inferred from names:**

- `Hydrator`/`Scorer`'s default `update_all` (`candidate-pipeline/hydrator.rs:L52-L58`, `candidate-pipeline/scorer.rs:L50-L56`) only applies an update `if let Ok(value) = result` — an `Err` for a given candidate is a **silent no-op for that candidate**: it is neither dropped nor does it fail the request; it simply keeps whatever field values it already had.
- `Source::run`'s errors are absorbed by `fetch_candidates`'s `results.into_iter().flatten()` (`candidate_pipeline.rs:L256-L271`) over `Vec<Result<Vec<C>, String>>`: a failing source contributes **zero candidates** and is silently skipped; other sources' results are unaffected.
- `QueryHydrator` follows the same `if let Ok` pattern at the whole-query level (`candidate_pipeline.rs:L208-L224`).
- `Filter` has **no fallibility at the trait level at all** — `filter()` returns a total `FilterResult{kept, removed}` partition, not a `Result`.
- `SideEffect`s run via `tokio::spawn` with `let _ = join_all(...).await` (`candidate_pipeline.rs:L396-L409`) — results are explicitly discarded; a side effect cannot affect the response under any circumstance.
- A hydrator/scorer returning the wrong-length `Vec` triggers a length-mismatch guard in the trait's default `run()` wrapper, converting the **entire batch** to `Err` for that stage invocation — still governed by the same silent-skip `update_all` semantics, so even this defensive guard cannot escalate to a request failure.

This directly resolves **S00-F008**: see "S00 carry-forward resolutions" below.

## PhoenixCandidatePipeline construction

Built in `home-mixer/candidate_pipeline/phoenix_candidate_pipeline.rs::build_with_clients` (`L186-L464`). Full ordered inventory in `S01_pipeline_inventory.csv` (rows 1–82). Summary: 17 query hydrators, 7 sources, 12 candidate hydrators, 18 pre-scoring filters, 3 scorers, 1 selector (`TopKScoreSelector`), 6 post-selection hydrators, 3 post-selection filters, 8 side effects. `result_size() = params::RESULT_SIZE = 35`.

One query hydrator (`ImpressedPostsQueryHydrator`) is constructed at `L278-280` but bound to an underscore-prefixed local and never added to the active `query_hydrators` Vec — see S01-F001.

## Exact stage order

The order **is** exactly the sequence above, confirmed directly from `execute_stages`, resolving **S00-C045**. README's 7-stage diagram is directionally correct but collapses two materially different execution models into informal groupings: candidate sources/hydrators run concurrently (order-independent within a stage) while pre-scoring filters and scorers run strictly sequentially (order-dependent — `PhoenixScorer` sets prediction fields the sequentially-later `RankingScorer` reads, whose output the sequentially-later `VMRanker` reads). README's "post-selection filters" grouping (`VFCandidateHydrator`, `VFFilter`, `DedupConversationFilter`) actually spans two separate stage *types* — a concurrent post-selection **hydrator** stage followed by a sequential post-selection **filter** stage — which the diagram does not distinguish (S01-F005).

## Candidate sources and merge behavior

`PhoenixCandidatePipeline`'s 7 sources (declared order = `thunder_source, tweet_mixer_source, simclusters_source, phoenix_source, phoenix_topics_source, phoenix_moe_source, cached_posts_source`) are evaluated for their `enable()` gate and, for whichever pass, run concurrently; results are merged by simple concatenation (`collected.append(&mut candidates)` per source, `candidate_pipeline.rs:L264-L267`) — there is no interleaving or per-source quota at the merge point itself; ordering is entirely determined downstream by scoring/selection.

**This resolves S00-C043 (SimClusters wiring): `SimclustersSource::new(simclusters_ann_client, core_data_hydrator.clone())` is directly constructed and included in the sources `Vec` — CONFIRMED.** It also surfaces a new, materially significant gap: **`TweetMixerSource`, `PhoenixTopicsSource`, and `PhoenixMOESource` are three additional, fully-wired, request-gated candidate sources that README's Candidate Sources table and request-path diagram never name** (S01-F003). README's claim that Thunder, Phoenix retrieval, and SimClusters are *the* out-of-network sources is therefore incomplete, not merely under-specified.

A per-source failure contributes zero candidates without affecting other sources' contributions (see "Candidate-pipeline execution semantics" above) — directly answers the task's Section D question about source-failure isolation.

## Query hydration

Two-tier capability exists at the framework level (`query_hydrators()` then `dependent_query_hydrators()`, the latter running only after the former fully completes), but `PhoenixCandidatePipeline` does not override `dependent_query_hydrators()`, so it inherits the trait's empty default — all 17 of its query hydrators run in a single concurrent batch, not two tiers. `ForYouCandidatePipeline`, `FollowingCandidatePipeline`, and `RankedFollowingCandidatePipeline` each construct their own, much smaller (2–3 hydrator) query-hydration set, independent of `PhoenixCandidatePipeline`'s — when one of these pipelines' sources awaits `PhoenixCandidatePipeline::execute()`, that inner execution runs its own full 17-hydrator pass on the (already partially-hydrated, then cloned) query object, i.e. query hydration happens twice, at two different layers, with two different hydrator sets, on what is structurally the same Rust type.

## Candidate hydration

12 hydrators, all concurrent, all consuming/producing `PostCandidate`. `BidirectionalFollowHydrator` is the S00-carried-forward component of most interest: its failure semantics are now fully resolved (S01-F004 / S00-F008 below). `BroadcastLivenessHydrator` is fully implemented but absent from `candidate_hydrators/mod.rs` and independently hardcodes `enable() -> false` (S01-F002) — it is not part of the compiled crate under this snapshot.

## Pre-scoring filtering boundary

18 filters run sequentially (S00 previously examined only `PhoenixCandidatePipeline`'s copy of this list and confirmed `Brazil2026ElectionFilter`'s position; S01 did not re-derive that finding, only its place in the now-fully-resolved execution-order model). One of the 18, `PreviouslySeenPostsBackupFilter`, is present, unconditionally enabled, and executes on every request — but is a **permanent no-op** given `ImpressedPostsQueryHydrator`'s orphaned wiring (S01-F001), since its only data dependency (`query.impressed_post_ids`) is always empty.

## Scoring and selector boundary

3 scorers run **sequentially, not concurrently** — `PhoenixScorer` → `RankingScorer` → `VMRanker` — confirmed directly from `candidate_pipeline.rs`'s scorer loop (a plain `for` loop, not `join_all`). `TopKScoreSelector` then sorts by score and truncates. S01 did not re-derive `RankingScorer`'s weighted-sum formula (S00/S05 territory) but did confirm `VMRanker`'s failure mode precisely: a whole-call RPC failure (xDS or DNS) returns `Err` for every candidate, which — per the framework's default `update_all` — means **none of `VMRanker`'s per-candidate updates are applied**, and `execute_stages()` proceeds to selection regardless (DIRECT). Whether this means candidates specifically retain `RankingScorer`'s score field, and that `TopKScoreSelector` therefore operates on `RankingScorer`'s ordering, was not independently traced field-by-field (which score field each scorer writes/reads, and `TopKScoreSelector`'s exact comparison logic) — that stronger consequence is a plausible **STRONG_INFERENCE**, not DIRECT, and is a concrete downstream obligation for S05/S08 (S01-F012).

## Post-selection / visibility boundary

6 post-selection hydrators run concurrently on the **already-selected** (top-K) candidate set only — `VFCandidateHydrator` (the visibility-filtering lookup) among them — followed by 3 sequential post-selection filters (`VFFilter`, `AncillaryVFFilter`, `DedupConversationFilter`). This confirms the README's "ranking and visibility are separate mechanisms" design claim structurally: visibility filtering genuinely runs as a distinct, later stage operating on a smaller candidate set, not interleaved with pre-scoring filtering or scoring. Deep visibility-policy semantics belong to S14; S01 establishes only that this boundary exists exactly where README says it does.

## ForYouCandidatePipeline and blending composition

**Resolves S00-C044.** `ForYouCandidatePipeline` does not subclass, wrap, or otherwise structurally embed `PhoenixCandidatePipeline`. It is a fully independent `CandidatePipeline<ScoredPostsQuery, FeedItem>` with its own 2 query hydrators, 7 sources, 1 pre-selection filter, `BlenderSelector`, 1 post-selection filter, and 9 side effects — and **zero scorers, zero candidate hydrators of its own** (`hydrators()` and `scorers()` both return `&[]`). One of its 7 sources, `ScoredPostsSource`, directly and synchronously `.await`s `ScoredPostsServer::run_pipeline`, which directly `.await`s `PhoenixCandidatePipeline::execute(query)` — an ordinary in-process Rust function call, not an RPC. The other 6 sources (ads, WTF, prompts, push-to-home, Jetfuel frames, feed survey) run concurrently alongside this nested execution. `BlenderSelector` then interleaves the pre-ranked organic-post `FeedItem`s with the unranked injected content; **the Phoenix model never sees or scores ads/WTF/prompts** (S01-F006).

The identical "peer-source composition" pattern recurs for `RankedFollowingCandidatePipeline` (via `ScoredPostsSource`, same `PhoenixCandidatePipeline`) and `FollowingCandidatePipeline` (via `ReverseChronPostsSource`, wrapping the separate, unscored `ReverseChronPostsPipeline`). Deep ad/WTF/prompt injection *policy* (positioning, ad-adjacency rules, blending ratios) is S02's domain; S01 establishes only the composition mechanism and invocation boundary.

## Runtime gating and reachability

S00 found that not every stage has an individual feature-switch gate (`Brazil2026ElectionFilter` being the confirmed counterexample). S01's systematic `enable()` sweep across all query_hydrators/candidate_hydrators/sources/filters/side_effects (recorded per-component in `S01_pipeline_inventory.csv`'s `enable_or_gate` column) found this pattern is common, not exceptional: core social-graph safety hydrators (`BlockedUserIdsQueryHydrator`, `MutedUserIdsQueryHydrator`, `SubscribedUserIdsQueryHydrator`), most pre-scoring dedup/eligibility filters (`DropDuplicatesFilter`, `AgeFilter`, `SelfTweetFilter`, `AuthorSocialgraphFilter`, `VFFilter`, and others), and several post-selection hydrators run **unconditionally** — no local switch exists to disable them short of a code change. Distinguishing this from "constructed but not active": every unconditional component S01 examined is genuinely reachable and executes on every request (no additional gate elsewhere was found), except the three components covered by S01-F002, which cannot run regardless of any switch because they are absent from the compiled module tree, and `ImpressedPostsQueryHydrator` (S01-F001), which is compiled but never added to any pipeline's active component list.

## Cached-post and alternate request paths

Distinct request-mode discriminators identified on `ScoredPostsQuery`, each with a traceable code consequence:

- **`has_cached_posts`**: gates `BidirectionalFollowHydrator::enable` (skips hydration) and `PhoenixScorer::enable` (skips Phoenix inference entirely) — set by `CachedPostsQueryHydrator`; consumed by `CachedPostsSource`.
- **`in_network_only`**: forced `true` server-side for `RankedFollowingFeedService`/`FollowingFeedService`, or set from the client request, or forced by `viewer_data.allow_for_you_recommendations == Some(false)` (S01-F008) — read by `PhoenixScorer` to choose `ProductSurface::HomeTimelineRankedFollowing` vs `HomeTimelineRanking`.
- **`seed_candidate_post_ids`**: populated only by `PhoenixScoresService`; consumed exclusively by `SeedCandidatesSource` in `PhoenixScoresPipeline`, which retrieves nothing and instead scores exactly the caller-supplied tweet IDs (S01-F009).
- **`is_bulk_topic_request()`** (`topic_ids.len() > 6`) and **`is_topic_request()`**: distinct logging/metric surfaces (`SURFACE_TOPICS` in `scored_posts_server.rs`) though S01 did not trace every downstream consequence.
- **`TEST_USER_IDS`**: a hardcoded 2-ID allowlist that bypasses pipeline execution entirely across all five servers (S01-F010).

## Failure and degraded-mode behavior

Summarized from the sections above and `S01-F004`/`S01-F012`/`S01-F013`:

- **Request-time**: per-candidate/per-source/per-unit failures degrade data quality, never availability. No single hydrator, source, or scorer failure can fail a request; a candidate simply proceeds with stale/unset fields, or a source simply contributes nothing. `VMRanker`'s whole-call failure is the clearest concrete instance directly established: none of its per-candidate updates are applied, and `execute_stages()` proceeds to selection regardless — whether that means candidates keep specifically `RankingScorer`'s score is a plausible but not independently field-traced consequence (STRONG_INFERENCE, routed to S05/S08 — see S01-F012).
- **Gizmoduck / resurrection-date fetches** (`server.rs::QueryBuilder::fetch_viewer_data`/`fetch_resurrection_time`): 200ms timeout, fail open to `ViewerData::default()` / `None` respectively.
- **Boot-time**: nearly every client constructor across the 7 boot-time constructor functions S01 read in full (all `prod()`/`new()` pipeline constructors and `HomeMixerServer::build`, within S01's 227 assigned files) is wrapped in `.expect(...)`, panicking the whole process on a single failed dependency. The only exception found in that sweep is `ThunderCapiClient`, which degrades gracefully to `None` with a logged warning, falling back to what `ThunderSource` calls a "proxy path" (S01-F013). Boot-time construction elsewhere in the repository, outside S01's ownership, was not examined.
- **Side effects**: entirely fire-and-forget; cannot affect the response by construction, and their own internal errors are discarded by the framework (`let _ = join_all(...)`) regardless of what an individual side effect does internally.

## S00 carry-forward resolutions

| S00 item | Resolution | Status |
|---|---|---|
| **S00-F001/F002** (`Brazil2026ElectionFilter` construction/stage, README table omission) | Confirmed unconditional construction and pipeline position exactly as S00 found; S01 did not re-derive further. Six other previously-unplaced filter modules are now all placed (S01-F007), closing that specific S00 open item. | CONFIRMED (no new evidence beyond S00) |
| **S00-F006/F007** (`BidirectionalFollowHydrator` divergence; `author_follows_viewer` feeds Phoenix) | Orchestration/gating fully traced: `enable()` gates on `EnableBidirectionalFollowHydration` + `!has_cached_posts`; failure semantics resolved (see S00-F008 row below). Model-side semantics remain S05/S06's. | CONFIRMED / PARTIALLY_RESOLVED (orchestration only) |
| **S00-F008** (Hydrator `Err` downstream handling) | **Fully resolved.** Per-candidate `Err` is silently absorbed by the framework's default `update_all`; the candidate is neither dropped nor does the request fail — it simply keeps its pre-hydration field values. Applies uniformly to every `Hydrator`/`Scorer` in the codebase, not just `BidirectionalFollowHydrator`. | CONFIRMED |
| **S00-C043** (SimClusters candidate-source wiring) | **Confirmed CONFIRMED/DIRECT.** `SimclustersSource` is constructed and included in `PhoenixCandidatePipeline`'s sources `Vec`. Also surfaced 3 additional undocumented sources (S01-F003). | CONFIRMED |
| **S00-C044** (Post Pipeline vs. Blending Pipeline composition) | **Resolved.** Peer-source composition via a synchronous, in-process, awaited call from one pipeline's `Source` into another pipeline's `execute()` — not structural wrapping/inheritance. Same pattern used 3 times across the 6 pipelines. | CORRECTED (README's "wraps" framing is an approximation of an architecturally different mechanism) |
| **S00-C045** (actual stage execution order) | **Resolved.** README's 7-stage order is directionally correct; concurrency-vs-sequential distinction within/across stages is the material refinement (S01-F005). | CONFIRMED (refined) |
| **S00-C046** (not every stage has an individual switch) | **Confirmed and generalized.** Unconditional (`enable()`-default) components are common across every stage type, not just `Brazil2026ElectionFilter`. | CONFIRMED |

## Important findings

13 findings recorded in `S01_findings.jsonl` (`S01-F001`–`S01-F013`); see that file for full evidence citations. Significance distribution: 6 HIGH, 5 MEDIUM, 2 LOW; all `CONFIRMED`/`DIRECT`.

- **S01-F001 / S01-F002** (HIGH): three components are unreachable in production under current wiring — one (`ImpressedPostsQueryHydrator`) is module-compiled but never added to an active pipeline, permanently neutering `PreviouslySeenPostsBackupFilter`; two more (`PopularTopicsSource`, `PopularTopicsAuthorDedupFilter`) plus a third (`BroadcastLivenessHydrator`) are absent from their `mod.rs` declarations entirely and are not part of the compiled crate, with two of the three additionally hardcoding `enable() -> false`. Reactivating `PopularTopicsSource` would require more than restoring its `mod.rs` line — it has no construction/wiring site anywhere in the current tree.
- **S01-F003** (HIGH): `PhoenixCandidatePipeline` has 7 candidate sources; README names 3. `TweetMixerSource`, `PhoenixTopicsSource`, `PhoenixMOESource` are wired into the pipeline and eligible to execute when their own `enable()` conditions pass — undocumented regardless of how often those conditions are actually true in production.
- **S01-F004** (HIGH): the framework-wide failure model — resolves S00-F008 and generalizes it to every hydrator/scorer/source in the codebase.
- **S01-F005** (HIGH): concurrency is stage-specific — hydrator/source stages concurrent, filters/scorers strictly sequential (order-dependent), the selector a single synchronous call, side effects concurrent-among-themselves inside a fire-and-forget spawn — resolves S00-C045.
- **S01-F006** (MEDIUM): the "wrapping" mechanism precisely characterized — resolves S00-C044.
- **S01-F007** (MEDIUM): all six of S00's unplaced filters located with DIRECT evidence; none orphaned.
- **S01-F008** (HIGH): `viewer_data.allow_for_you_recommendations` can silently force `in_network_only=true`, an undocumented account-status content-eligibility gate. (Its practical effect on each of the 5 out-of-network sources beyond `TweetMixerSource` is a plausible, not independently-verified, inference.)
- **S01-F009** (MEDIUM): 5 registered gRPC services backed by 6 candidate pipeline implementations; README documents only the two composing the For You feed.
- **S01-F010** (LOW): universal `TEST_USER_IDS` bypass across all five servers.
- **S01-F011** (MEDIUM): debug endpoints accept live, caller-supplied feature-switch overrides; access-control boundary unestablished.
- **S01-F012** (MEDIUM): `VMRanker`'s per-candidate updates are skipped on whole-call RPC failure, so the request continues without them — DIRECT; whether that means candidates keep specifically `RankingScorer`'s score is a separate, not-independently-traced inference (STRONG_INFERENCE, routed to S05/S08).
- **S01-F013** (LOW): within the 7 boot-time constructors S01 read in full, construction is fail-hard except `ThunderCapiClient`'s graceful degradation; not claimed as repository-wide.

## Cross-domain handoffs

- **S02** (feed filters/selection/blending, ads): deep semantics of `AdAdjacentServedFilter`, `PushToHomeDedupFilter`, `BlenderSelector`/`FollowingBlenderSelector` interleaving policy, the `ads/` blending modules (`partition_organic_blender.rs` and siblings, not independently opened in S01), `PreviouslySeenPostsBackupFilter`'s now-established dead-code status (S01-F001), and the six previously-unplaced filters' actual business logic (S01-F007 establishes only their placement).
- **S03** (Thunder / in-network retrieval): `ThunderSource`, `ThunderCapiClient`'s fallback path, `ReverseChronPostsPipeline`/`FollowingNightOwlSource`.
- **S04** (SimClusters): `SimclustersSource` internals; the dormant `PopularTopicsSource`'s Strato-backed topic-tweet retrieval (S01-F002).
- **S05** (Phoenix ranking/retrieval semantics): `RankingScorer`'s weighted-sum formula and adjustments (not re-derived in S01); `TweetMixerSource`/`PhoenixTopicsSource`/`PhoenixMOESource` internals (S01-F003); `PhoenixScoresRankingScorer`'s distinct formula; `AuthorColdStart`/`value_model_gate.rs` (not opened in S01 — flagged as a priority follow-up given `value_model_gate.rs`'s size, 537 lines).
- **S07/S08** (retrieval admission / diversity): `VMRanker`'s DPP internals and MPN/value-model fold-weight logic (`vm_ranker.rs` mentions `EnableMpnScoring`/`VMRankerValueModelId` that S01 did not fully trace).
- **S14** (visibility policy): `VFCandidateHydrator`/`VFFilter`/`AncillaryVFFilter` internals; S01 establishes only their stage placement and unconditional-enable status.
- **S11/S14/S15** (account signals / visibility / enforcement): what actually sets `ViewerData.allow_for_you_recommendations = Some(false)` on the Gizmoduck side (S01-F008) — entirely external/unpublished from this file.
- **S17** (config census): every `enable_or_gate` column entry in `S01_pipeline_inventory.csv` naming a param; the full ~190-entry `param.rs` census remains S17's job.
- **S18** (ops/repro/failure): boot-time fail-hard asymmetry (S01-F013); the `pipeline_components_json` diagnostic binary as a mechanical cross-check opportunity for this report's inventory; debug-endpoint access-control boundary (S01-F011).
- **B01/B02** (candidate entrance/exclusion): this report is the primary source for "every way a candidate can enter/be silently dropped at the orchestration layer" — see `S01_pipeline_inventory.csv` in full.
- **B03** (score pressure): scorer sequencing (S01-F005) and `VMRanker`'s failure-mode score fallback (S01-F012).
- **B06** (cold start): `AuthorColdStart`'s construction/sharing site confirmed; internal thresholds not traced (S05).
- **B07** (in-network vs. OON): `in_network_only`'s three distinct origins (client request, server-forced, account-status-forced) (S01-F008); the asymmetry between `RankedFollowingCandidatePipeline` (reuses ranked `PhoenixCandidatePipeline`) and `FollowingCandidatePipeline` (uses unranked `ReverseChronPostsPipeline`) despite both surfaces setting `in_network_only=true`.
- **B10** (failure/degraded modes): the full request-time-graceful vs. boot-time-fail-hard picture (S01-F004, S01-F012, S01-F013).
- **B12** (public-vs-production boundary): every `enable_or_gate` marked "gated" in the inventory has an unestablished runtime/production value (S17's territory); `viewer_data.allow_for_you_recommendations`'s actual production semantics are entirely external (S01-F008).

## Public snapshot vs production boundary

- **Runtime feature-switch state**: every "gated" component in `S01_pipeline_inventory.csv` has a checked-in enable/default in `param.rs` but an unestablished runtime/production value (consistent with S00's prior findings on `xai_feature_switches`/GrowthBook).
- **Gizmoduck's internal logic**: `ViewerData.allow_for_you_recommendations`, `has_phone_number`, `roles`, and other fields consumed by `QueryBuilder::build` are populated by an external, unpublished service; only the home-mixer-side consumption is visible from this snapshot.
- **The three module-tree-absent components** (S01-F002) could be restored to compilation with a one-line `mod.rs` change each; S01 makes no claim about whether an internal, unpublished build variant already does so.
- **`xai_candidate_pipeline::component_library`**: the actual client implementations behind every `Prod*Client` type (gRPC semantics, retry/backoff, connection pooling) live in an external crate dependency, not in this snapshot — S01 confirmed *where* each client is injected and *what* trait it implements, not its internal behavior.
- **Debug-endpoint access control** (S01-F011): whether `get_debug_*` RPCs are reachable only by internal callers is a network/auth-layer question this snapshot does not answer.

## Unknowns

- What specifically sets `Gizmoduck`'s `allow_for_you_recommendations = Some(false)` and under what account conditions (S01-F008) — routed to S11/S14/S15.
- `value_model_gate.rs`'s full contents and role (537 lines, not opened in S01) — routed to S05/S08.
- `AuthorColdStart`'s internal thresholds/formula for the "new-author boost" — routed to S05.
- Whether `TweetMixerSource`/`PhoenixTopicsSource`/`PhoenixMOESource` differ meaningfully in retrieval semantics from `PhoenixSource`, or represent experiment/shadow variants — routed to S04/S05/S07.
- Whether the three module-tree-absent components (S01-F002) are active in any unpublished internal build variant — cannot be established from this snapshot.
- Deep `ads/` blending-policy internals (`partition_organic_blender.rs` and 5 siblings, plus 6 test files) — not opened in S01, explicitly routed to S02.
- Full internal contents of 15 `util/urt/*` marshaller files and 5 `frames/*` files — role inferred from filenames/call sites only, not independently read; routed to S02.
- Debug-endpoint (`get_debug_*`) authentication/authorization boundary (S01-F011) — routed to S17/S18.
- Whether `PhoenixScoresRankingScorer`'s formula differs materially from `RankingScorer`'s — not traced; routed to S05.

## Coverage/accounting

- S01-primary assigned files: **227**, computed directly from `_analysis/passes/file_specialist_map.csv` (`primary_specialist == "S01"`), matching the framework's expected workload exactly. No discrepancy found; no stop condition triggered.
- Files examined and reviewed: **227 / 227** (100% accounted for in `S01_file_review.csv`, one row each, zero duplicates, zero missing, zero extras — verified programmatically).
  - `COMPONENT_REVIEWED`: 164 files — includes all 11 `candidate-pipeline/` framework files, all 6 pipeline construction files + `mod.rs`, all 5 server files + `main.rs`/`lib.rs`/`dark_traffic_setup.rs`, `models/query.rs`, the 6 `mod.rs` orphan-sweep targets, and 101 hydrators/sources/filters/scorers/side-effects whose role, pipeline membership, and `enable()` gating were confirmed via direct file inspection cross-referenced against the 6 pipeline construction sites.
  - `TRIAGED`: 63 files — predominantly `home-mixer/clients/*` (19, role inferred from construction-site injection but internal client logic not independently opened), `home-mixer/ads/*` (12, explicitly deferred to S02 per the pass charter), `home-mixer/util/urt/*` marshallers (14 of 15, presentation-layer, deferred to S02), `home-mixer/frames/*` (5), `home-mixer/models/*` (5 of 7), and a handful of individual utility/scorer files (`value_model_gate.rs`, `author_cold_start.rs`, `rescore.rs`, and similar) flagged as priority follow-ups for the owning specialist rather than guessed at.
- Supporting cross-domain files read but **not** marked reviewed for S01 (their coverage-ledger state was not touched): none required beyond what is already S01-primary — S01's assigned set already includes the full orchestration layer needed to answer this pass's questions. `_analysis/architecture/README.md` and `_analysis/architecture/CROSS_DOMAIN_SYSTEMS.md` were read as framework context, not as source.
- Claim-style evidence lives in `S01_pipeline_inventory.csv` (169 rows: 1 framework row + 78 `PhoenixCandidatePipeline` rows + 21 `ForYouCandidatePipeline` + 19 `FollowingCandidatePipeline` + 15 `RankedFollowingCandidatePipeline` + 12 `ReverseChronPostsPipeline` + 23 `PhoenixScoresPipeline`), not duplicated in prose.
- Material findings: 13 (`S01-F001`–`S01-F013`), all `CONFIRMED`/`DIRECT`; 6 HIGH, 5 MEDIUM, 2 LOW.
