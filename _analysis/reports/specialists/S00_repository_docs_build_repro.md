# S00 — Repository Documentation, Published Claims & Reproduction Boundary

## Scope and snapshot

- Upstream repository: `xai-org/x-algorithm`, branch `main`
- Upstream commit: `c65aa179db7bdd61e2c2821eac87f208a105c053`
- Upstream Git tree: `1d4c89941bfcd2ea3aab7c780f7447342e304e42`
- Snapshot identifier: `2026-08-15_c65aa17`
- Baseline tracked files: 2,016
- Pass: **S00 — Snapshot, docs, build/repro boundaries** (per `_analysis/passes/README.md`)
- This report documents component-audit-level (`COMPONENT_REVIEWED`) findings only. No behavior-trace, discovery, or adversarial-verification pass has been performed on this material; those remain `NO` in the coverage ledger for every S00 file.
- **Remediation note:** this report was revised after an independent audit identified four issues in the original S00 pass: (1) a false negative-search claim in S00-F013 (a repository-wide "cron" search actually returns real, if unrelated, hits — see the corrected "Experiments and runtime configuration boundary" section); (2) an insufficiently exhaustive baseline-integrity self-check (now redone as a full, non-sampled 2,016-object verification — see `S00_run.md`); (3) several composite claims in `S00_claim_matrix.csv` that were marked `CONFIRMED`/`DIRECT` despite bundling unverified material sub-parts (17 rows split off, 11 originals narrowed — see "Composite-claim discipline" below); and (4) an under-cited evidence chain for S00-F007. All four are corrected in this revision; corrections are called out inline below rather than silently merged into the original prose.

## Assigned files

Per `_analysis/passes/file_specialist_map.csv` (verified against the CSV before any review began):

```
CODE_OF_CONDUCT.md
LICENSE
README.md
docs/BIDIRECTIONAL_BOOST_CHANGE.md
```

This matches the task specification exactly; no mapping discrepancy was found.

## Executive result

The four S00-assigned documents describe a coherent, internally-plausible architecture that is **structurally well-supported** by the frozen snapshot: every top-level component, pipeline stage file, filter, hydrator, scorer, and selector named in `README.md` and `docs/BIDIRECTIONAL_BOOST_CHANGE.md` exists at the exact path claimed, and several specific numeric/behavioral claims (the 48-hour age cutoff, the deterministic inventory-holdout hash, the bidirectional-boost weight values, the report/favorite weight ratio) were independently confirmed against source.

At the same time, S00 identified concrete gaps between documentation and code that later passes must carry forward:

1. A pre-scoring filter (`Brazil2026ElectionFilter`) that is registered unconditionally in the live pipeline is **not listed** in the README's own filter table, even though the same README describes it prominently elsewhere (S00-F001, S00-F002).
2. The bidirectional-follow-boost hydrator's **current** checked-in implementation has diverged from the diff literally reproduced in `docs/BIDIRECTIONAL_BOOST_CHANGE.md` — it now also feeds a follow-relationship signal into the Phoenix model's feature set via a second, undocumented mechanism (S00-F006, S00-F007).
3. The README's central claim that "cron scripts... set the defaults in this repository's code to be the primary production values" splits into three sub-claims with materially different evidence (S00-F013, corrected): a config-mirroring **marker does exist** on `home-mixer/params/param.rs` and two `abuse-enforcement-service` rule files (self-reported "mirrored from ...; last sync ..." header comments), but whether that mechanism is specifically **cron**-based, and whether the synced values are exactly "the primary production values," remain unestablished from the published snapshot. Five unrelated `cron =` definitions do exist elsewhere in the repository (Agatha's hourly Scalding batch jobs) and must not be conflated with this claim.
4. The root `LICENSE` (Apache-2.0) is accurate as far as it goes, but `phoenix/NOTICE` documents third-party BSD-3-Clause and Apache-2.0 code bundled within `phoenix/xrex/`, which a naive "the whole repo is one license" reading would miss (S00-F011).

None of these are treated as proof of malfeasance or of inaccurate public communication; they are recorded as evidence gaps and drift for downstream passes (S01, S02, S05, S06, S17, S18, and behavior traces B03/B09/B12) to resolve with deeper, component-specific evidence.

## What the repository claims to contain

`README.md` states the repository contains "the core code that determines which posts a viewer sees in the For You feed," combining in-network (Thunder) and out-of-network (Phoenix retrieval, SimClusters) content, filtering, and transformer-based ranking (S00-C001). The "What's not in this repo?" section explicitly discloses two categories of omission: Grox LLM prompt templates (`.j2` files) and "some botmaker rules" (S00-C025), citing gameability risk as the reason, with "Under the Hood" offered as a partial transparency substitute (S00-C026).

Both named omissions were independently checked, and are now tracked as two separate claim rows given their materially different evidence (S00-C025 for Grox, S00-C050 for botmaker-rules — split per composite-claim discipline, see below). No `.j2` file exists anywhere under `grox/`, and `grox/flows/upa/prompts.py` contains a self-referential comment confirming the omission is intentional and documented in-repo (S00-F010) — an unusually direct piece of corroborating evidence, so S00-C025 remains `CONFIRMED`/`DIRECT`. The `botmaker-rules/` omission claim (S00-C050) cannot be similarly confirmed or refuted and is downgraded to `UNKNOWN`/`POSSIBLE`: 73 files exist under `botmaker-rules/scarecrow/{bot,derived-feature}`, but whether additional production rules exist beyond this set is unknowable from a single snapshot — the published set does not itself establish that a larger production set exists.

The "Deployment-related code" subsection specifically calls out `phoenix/` as designed to be runnable end-to-end, citing a Cargo workspace, `pyproject.toml`, and `QUICKSTART.md` (S00-C027). All three files exist at the named paths; S00 did not execute the quickstart (out of scope per pass instructions — reserved for S18).

## Architecture claims and verification

The README's Request Path diagram (S00-C010) describes a 7-stage `PhoenixCandidatePipeline`: query hydration → parallel candidate sources (Thunder in-network; Phoenix retrieval + SimClusters out-of-network) → candidate hydration → pre-scoring filters → scoring (`PhoenixScorer`, `RankingScorer`, `VMRanker`) → selection (`TopKScoreSelector`) → post-selection filters (`VFCandidateHydrator`, `VFFilter`, `DedupConversationFilter`). Every named file and directory in this diagram exists (`home-mixer/query_hydrators/`, `home-mixer/sources/`, `home-mixer/candidate_hydrators/`, `home-mixer/filters/`, `home-mixer/scorers/{phoenix_scorer,ranking_scorer,vm_ranker}.rs`, `home-mixer/selectors/top_k_score_selector.rs`, `home-mixer/candidate_hydrators/vf_candidate_hydrator.rs`, `home-mixer/filters/vf_filter.rs`, `home-mixer/filters/dedup_conversation_filter.rs`). This confirms **structural** accuracy (files exist, are named as claimed) but S00 did not independently re-derive the exact runtime execution order or conditional stage-skipping logic within the `candidate-pipeline` execution engine — that belongs to S01 (split out as S00-C045, `DEFERRED`/`UNKNOWN`). Separately, the README's "stages can be switched on/off individually" claim (S00-C011) does not hold universally: `Brazil2026ElectionFilter` has no local param gate at all (S00-C046, `CONTRADICTED`, see S00-F001).

The Blending Pipeline (`ForYouCandidatePipeline`, `BlenderSelector`, `home-mixer/ads/partition_organic_blender.rs`) similarly exists at the claimed paths (S00-C008; its functional composition — "finds/ranks/filters" and "wraps and adds ads/WTF/prompts" — is split out as S00-C044, `PARTIALLY_CONFIRMED`). The Labeling Path diagram's components (`grox/`, `media-model-proxy/`, `clip/`, `agatha/`, `bdsm/`, `user-cred-v2/`, `scarecrow/`, `botmaker/`, `botmaker-rules/scarecrow/`, `abuse-enforcement-service/`, `safety-label-user-agg/`, `visibility-filtering/`) all exist (S00-C012).

Two architecture claims required deeper spot-checks:

- **Retrieval-index → visibility-filtering bridge** (S00-C014): `phoenix-rankall-strato/lib/eventProcessing.strato` does consult a `visibility/shouldDropTweet` path, confirming the bridge documented in `_analysis/architecture/README.md` exists at the code level — but the consultation is itself wrapped in a decider-flag check (`enable_vf_rust_should_drop_tweet`) whose value is not established by this snapshot (S00-F012). "Consulting visibility filtering first" is therefore `STRONG_INFERENCE`, not `DIRECT`.
- **DPP reranking** (S00-C015): `vm-ranker/scoring/dpp_model.rs` exists, directly corroborating the README's determinantal-point-process claim.

## Ranking/scoring claims and verification

The README's "common misconception" explanation — that action weights scale predicted probabilities, not raw engagement counts, illustrated with a "report has 468 times higher weight than a like" example (S00-C002) — was checked against `home-mixer/params/param.rs`. The current checked-in constants are `ReportWeight = -234.0` (L468) and `FavoriteWeight = 0.5` (L308); their magnitude ratio is **exactly** 468. The matching source comment ("...the weights do not multiply raw engagement counts.") is present verbatim in both `param.rs:L285` and `ranking_scorer.rs:L424`, confirming the README's claim that comments were added to those two specific files (S00-C003). This is recorded as finding S00-F003: the doc's illustrative number is not an arbitrary pedagogical figure — it is traceable to the live checked-in weight pair.

The `Final Score = Σ(weight_i × P(action_i))` formula (S00-C018) is implemented in `RankingScorer::apply`. The three named post-formula adjustments (author-diversity decay, out-of-network discount, new-author boost) were confirmed to exist by directory/file structure but their exact multiplier curves, floors, and thresholds were **not** individually re-derived in S00 — this is explicitly deferred to S05/S08, consistent with S00's scope boundary (S00 verifies documentation claims at a structural level; S05 owns the full ranking-semantics audit).

## Filtering/visibility claims and verification

The Pre-Scoring Filters table (17 entries, S00-C019) was checked directly against the actual filter `Vec` constructed in `phoenix_candidate_pipeline.rs` (L345–L370). All 17 named filters are present in the pipeline **and** the table's implied ordering (`AuthorSocialgraphFilter` then `VideoFilter`) is preserved. However, the live pipeline contains an 18th pre-scoring filter — `Brazil2026ElectionFilter` — sitting exactly between those two, which does not appear in the README table at all (S00-F002, `CONTRADICTED` in the claim matrix). `home-mixer/filters/mod.rs` also declares six additional filter modules not present in this table (`ad_adjacent_served_filter`, `following_retweet_deduplication_filter`, `invalid_conversation_module_filter`, `push_to_home_dedup_filter`, `result_size_filter`, `self_reply_chain_filter`); S00 did not determine which pipeline stage these belong to, so this is flagged for S02 rather than asserted as a further contradiction.

The Post-Selection Filters (`VFFilter`, `AncillaryVFFilter`, `DedupConversationFilter`, S00-C021) all exist. `visibility-filtering/rules/registry.rs` contains a `SafetyLevel::TimelineHomeRecommendations` policy with its own rule `Vec`, consistent with the README's claim of an out-of-network-only rule subset that "can only drop."

`InventoryHoldoutFilter`'s "chosen deterministically per post and viewer" claim (part of S00-C019) was independently confirmed: `holdout_bucket()` computes a SplitMix64-style hash mix of `post_id` and `viewer_id`, reduced mod 100, compared against a configured percentage — genuinely deterministic and per-(post, viewer). `AgeFilter`'s "older than 48 hours" claim matches `MAX_POST_AGE: u64 = 48 * 60 * 60` exactly (`home-mixer/params/config.rs:L36`).

## Labeling/enforcement/transparency claims and verification

S00 confirmed structural existence only for this section, consistent with pass scope (deep labeling-lifecycle audit belongs to S09–S16 and behavior traces B04/B05). `visibility-filtering/rules/registry.rs`, `scarecrow/`, `botmaker/`, `botmaker-rules/scarecrow/{bot,derived-feature}` (73 files), `abuse-enforcement-service/`, `safety-label-user-agg/`, `visibility-filtering-client/`, and `under-the-hood/{scalding,strato,thrift}` all exist at the paths and with the general shape the README describes. No claim in this area was contradicted; several are recorded `PARTIALLY_CONFIRMED`/`DEFERRED` pending the owning specialists' full component audits.

## Experiments and runtime configuration boundary

This is the section where S00 found the most consequential evidence gap, and the section corrected after independent audit. The README states (S00-C023 / S00-C053 / S00-C054 / S00-C055): "many tunable values are read from a configuration system rather than written into the code... we run cron scripts that set the defaults in this repository's code to be the primary production values." Three things were established, and they must not be conflated with each other:

1. **A runtime-override mechanism genuinely exists and is wired into checked-in code** (S00-C023, `CONFIRMED`/`DIRECT`): `home-mixer/params/param.rs` binds every `param!()` default to a named key read via the `xai_feature_switches` crate, and `abuse-enforcement-service` implements a full `GrowthBookClient`/`GrowthBookWriter` integration, including a protected admin API for writing config (S00-F009). This is `DIRECT` evidence that checked-in defaults are runtime-overridable in at least two distinct, independently-implemented ways across the repository.
2. **A distinct config-mirroring marker exists on the exact files the README describes** (S00-C053, `CONFIRMED`/`DIRECT`, new after remediation): `home-mixer/params/param.rs:L1` carries the self-reported header `// mirrored from config feature-switch defaults; last sync 2026-08-12T04:09:22Z`, and `abuse-enforcement-service/service-lib/rules/enforcement_post.yaml:L1` / `enforcement_user.yaml:L1` carry the analogous `# mirrored from GrowthBook dynamic config; last sync <timestamp>` headers. These three files are the only "mirrored from ...; last sync ..." artifacts found repository-wide. This is direct, textual, self-reported evidence that *some* process asserts having periodically synced these exact files — materially stronger than "no evidence at all" — but the header is metadata stamped on the target file, not the sync mechanism's own source code, so the script/job/trigger that produces it is not published.
3. **Whether that mechanism is specifically cron-based, and whether it represents "primary production values," remain unestablished** (S00-C054 `UNKNOWN`, S00-C055 `UNKNOWN`/`POSSIBLE`). A corrected, broadened repository-wide search (terms: `cron`, `scheduled`, `schedule`, `sync`, `synchronize`, `generated`, `param.rs`, `feature_switch`, `xai_feature_switches`, `production values`, `defaults`, `config`, `configuration`) found exactly five `cron = "0 * * * *"` definitions, all in `agatha/scalding/{data,labels/nsfw,labels/rate_based_labels,labels/spam_suspended,quantile}/BUILD.bazel` — hourly `scalding_job` Bazel targets owned by `agatha-owners@twitter.com`, depending on Agatha's own offline batch feature/label-extraction jobs. **These are Agatha's own batch-labeling jobs and are unrelated on their face to home-mixer parameter syncing; they must not be read as corroborating the README's cron claim.** No cron/script/workflow artifact implementing the param.rs/enforcement-rules mirroring itself was found. Separately, `param.rs`'s header says "mirrored from config feature-switch defaults," not literally "primary production values" — plausible given the shared `xai_feature_switches` mechanism, but an interpretive gap rather than an established equivalence.

**Corrected framing (supersedes the original S00 statement):** *the snapshot contains scheduled/cron jobs (five, all in Agatha, all unrelated to home-mixer parameter defaults), and a self-reported config-mirroring marker does exist on `param.rs` and two `abuse-enforcement-service` rule files with specific "last sync" timestamps — but S00 found no published artifact specifically implementing the README-described process that synchronizes production configuration values into the checked-in home-mixer parameter defaults, and no evidence that the mechanism (whatever it is) is cron-triggered.* This caveat propagates to every other S00 finding that treats a checked-in default as production-representative (most notably S00-F004, the bidirectional-boost value) — those findings are strengthened somewhat by point 2 above relative to the original "zero evidence" framing, but remain short of proof.

## Special/legal/geographic claims

`Brazil2026ElectionFilter` (S00-C004) was audited to the reachability chain described in the pass instructions:

- **DECLARED / EXPORTED / CONSTRUCTED / CALLED**: confirmed. The struct is defined in `home-mixer/filters/brazil_2026_election_filter.rs`, exported via `home-mixer/filters/mod.rs`, and constructed with `Box::new(Brazil2026ElectionFilter)` directly in the pipeline's filter `Vec`.
- **ENABLE CONDITION**: the filter does not override `Filter::enable()`, so it inherits the trait's default implementation, which unconditionally returns `true` (`candidate-pipeline/filter.rs:L21-23`). Unlike `BidirectionalFollowHydrator` (which is explicitly gated by a named, independently-overridable param), there is **no local feature-switch gate** on this filter in the checked-in code.
- **CHECKED-IN DEFAULT / POSSIBLE RUNTIME OVERRIDE**: because there is no param controlling enablement, there is nothing for a runtime feature-switch system to override at this layer — though the pipeline construction itself, or an upstream request-routing decision, could still exclude this filter from being invoked for a given request in ways not visible in this file alone.
- **ACTUAL PRODUCTION STATE**: not established by this snapshot. S00 makes no claim about whether, when, or for which users this filter has executed in production, nor does it draw any legal conclusion about the underlying Brazilian electoral-law predicate the code's comments cite.

Separately, the filter's exclusion logic (`is_excluded_author`/`should_remove`) was read directly: a hardcoded static set of ~150+ user IDs (each with a source-code comment giving the associated handle) is excluded from a candidate's author, retweeted-user, quoted-user, and thread-ancestor-user fields — unless the viewer follows that account, matching the README's stated exception exactly.

## Bidirectional-follow change document audit

Per the pass instructions, historical narrative and implementation claims in `docs/BIDIRECTIONAL_BOOST_CHANGE.md` were assessed separately.

**Implementation claims (verifiable from source):**
- `BidirectionalFollowHydrator` exists, is registered in `candidate_hydrators/mod.rs`, and is constructed into the Phoenix pipeline's hydrator list (S00-C040) — `CONFIRMED`.
- `bidirectional_boost_eligible()` requires no `in_reply_to_tweet_id`, no `retweeted_tweet_id`, and `is_mutual_follow_author == Some(true)` — i.e., original posts from mutual follows only, excluding replies and reposts — exactly matching both the doc's diff and the current file (S00-C039) — `CONFIRMED`.
- Checked-in defaults: `BidirectionalFollowReplyWeightBoost = 15.0` (matches the doc's *later*, July 24 diff, not its initial July 13 diff), `BidirectionalFollowDwellWeightBoost = 0.0` (matches "not shipped more broadly"), `EnableBidirectionalFollowHydration = true` — all `CONFIRMED` against `param.rs`.

**The most significant finding in this document (S00-F006, S00-F007):** the *current* checked-in `bidirectional_follow_hydrator.rs` (215 lines) is not a literal match for the diff reproduced in the doc. Beyond the shown diff, the live file:
1. Reads a second param, `EnableAllAuthorFollowHydration` (checked-in default `true`), which expands the social-graph check from "authors the viewer already follows" to "all candidate authors" when true.
2. Adds a `!query.has_cached_posts` condition to `enable()`, skipping hydration for cached-post queries.
3. Populates a new field, `author_follows_viewer`, which becomes an **input feature to the Phoenix ranking model itself**, a materially different consumption path from the documented post-hoc weight boost in `ranking_scorer.rs`.

**Full evidence chain for point 3 (strengthened after independent audit, S00-F007):** `BidirectionalFollowHydrator` sets `PostCandidate.author_follows_viewer` (`home-mixer/models/candidate.rs:L61`) → `CandidateHelpers::as_tweet_info` (trait decl `L121-L126`, impl `L129`/`L167-L213`) reads it at `L202-L210` and maps it into `xai_recsys_proto::AuthorInfo.is_following_user` — a field that is itself part of the published proto schema (`phoenix/crates/serving/xai-recsys-proto/proto/recsys.proto:L1098-L1103`, `optional bool isFollowingUser = 4`) → `home-mixer/util/phoenix_request.rs`'s `candidate_to_tweet_info` (`L98-L106`) calls `as_tweet_info()` for every candidate, `build_tweet_infos` (`L108-L118`) maps the whole candidate list through it, and `build_prediction_request` (`L141-L151`) assembles the result into a `PredictNextActionsRequest` → `home-mixer/scorers/phoenix_scorer.rs`'s `PhoenixScorer::score` (`L76-L97`) calls `build_prediction_request(...)` and then `self.dispatch.predict_with_fallback(query, cluster, request).await`. This proves **`DIRECT`**, hop-by-hop in checked-in source, that the signal is placed into the candidate `TweetInfo` included in the Phoenix prediction request and that request is sent through `PhoenixScorer`'s prediction dispatch. It does **not** extend to a `DIRECT` claim that the trained model materially uses the field to alter predictions: `PredictionDispatch`/`predict_with_fallback` are declared and called in checked-in home-mixer source but *defined* in the external `xai_candidate_pipeline::component_library::egress` module (re-exported only, at `home-mixer/util/egress.rs:L1-L2`), which is not part of this published snapshot, so the actual network dispatch and any server-side handling are unverifiable from source. Separately, `phoenix/crates/common/xai-recsys/src/util.rs` — which *is* part of this snapshot — shows `impl InputBuffer::new_with_candidates` (`L340-L341`) and `impl InputBuffer::compute_for_item` (`L675`) reading exactly this field into `candidate_is_author_following`/`history_is_author_following` feature arrays (`L517-L521`, `L861-L865`), which is `STRONG_INFERENCE` (not yet `DIRECT` proof of trained-model behavioral impact) that the field is structurally wired as a model input feature on the Phoenix serving side.

None of this is described in either S00-assigned document. The doc explicitly frames itself as a historical, illustrative example ("here's what you might've seen... rolled out in July 2026"), and the snapshot postdates it by roughly three weeks, so continued evolution is expected and not inherently a defect — but a reader treating the diff as a live description of current behavior would be materially misled about what the file does today.

**Historical/production-rollout claims (not verifiable from source):** the July 10 A/B test's existence, its specific boost-value assignment (5/10/15/20) and population percentages, the July 13 broad rollout to boost=20, and the World Cup-feedback motivation for the July 24 change to boost=15 are all recorded `UNKNOWN` in the claim matrix. The one exception is the July 24 change's **numeric end state** (`BidirectionalFollowReplyWeightBoost = 15.0`), which is independently `DIRECT`-confirmable in the current snapshot and does match the doc's stated outcome (S00-F004) — though, per the cron-sync gap above (S00-F013), this confirms only that the checked-in default equals 15.0, not that 15.0 was or is the value actually served in production.

## Omitted/private/redacted dependencies

Confirmed omissions (per README's own disclosure, S00-C025): Grox `.j2` prompt templates (self-corroborated in source, S00-F010) and an unspecified subset of botmaker rules (plausible but not independently verifiable). Additional omission-adjacent evidence found during S00 but not claimed by either assigned document: the external GrowthBook service consulted by `abuse-enforcement-service` is itself entirely unpublished (only the client/writer code is present) — this is a missing dependency in the sense of "the config server this component depends on is not part of the repository," distinct from the README's named omission list.

## Reproducibility boundary

`phoenix/` is the one component the README explicitly claims is end-to-end runnable, backed by a Cargo workspace (`phoenix/Cargo.toml`), a Python build target (`phoenix/pyproject.toml`), and `phoenix/QUICKSTART.md`. All three exist (S00-C027, `CONFIRMED`/`DIRECT`, narrowed to file existence). The separate outcome claim that these together let "a small model be trained/served end-to-end" is split out as S00-C055 (`DEFERRED`/`UNKNOWN`) since S00 did not execute the quickstart or attempt a build — the pass instructions reserve deep reproduction/failure auditing for S18, and S00's role is limited to establishing the boundary. Most other named components (`home-mixer/`, `visibility-filtering/`, `abuse-enforcement-service/`, etc.) are Rust crates/services without an equivalent "runs standalone with synthetic data" claim in the README; the README itself acknowledges that "code may not necessarily include build- or deployment-related files or generally self-explanatory infrastructure imports (e.g. `xai_service_runner` or `xai_kafka`)" (S00-C027), which S00 treats as an explicit, self-disclosed reproducibility boundary rather than an omission to be second-guessed.

**Downstream obligation for S18:** actually attempt the `phoenix/QUICKSTART.md` flow and report whether it succeeds unmodified from this snapshot; catalogue which other components have any standalone build/test entry point versus which assume internal infrastructure (`xai_service_runner`, `xai_kafka`, and similarly-named internal crates observed by name only, not audited for completeness in S00).

## Documentation/code contradictions

1. **`Brazil2026ElectionFilter` omitted from the Pre-Scoring Filters table** despite running in that exact pipeline stage and being described in detail elsewhere in the same README (S00-F002).
2. **`docs/BIDIRECTIONAL_BOOST_CHANGE.md`'s reproduced diff no longer matches the current file** it purports to describe, missing a second gating param, a cache-based enable condition, and a new Phoenix-feature consumption path for the same underlying signal (S00-F006, S00-F007).
3. **Partial, not zero, corroboration for the README's cron-sync claim** (S00-F013, corrected): a config-mirroring marker with a "last sync" timestamp exists on the exact target file (`param.rs`) and two analogous `abuse-enforcement-service` rule files, but no artifact establishes the mechanism is specifically cron-based or that the synced values are exactly "primary production values." Material to how much trust any "checked-in default = production value" statement in this repository deserves, but less severe a gap than originally reported.

No claim in the four assigned documents was found to be affirmatively false against the checked-in source; all identified issues are omissions, gaps, or drift rather than direct falsehoods.

## Public Snapshot vs Production Reality

Material reasons the checked-in repository may not fully reconstruct actual production behavior, each grounded in specific repository evidence gathered during S00:

- **Runtime feature-switch overrides (confirmed mechanism, unconfirmed values).** `home-mixer/params/param.rs` binds every tunable via `xai_feature_switches::param!()`; the bidirectional-boost hydrator's own unit tests exercise `xai_feature_switches::FeatureSwitches::override_fs(...)` directly, proving the override mechanism is real and exercised even in test code. No production override state is visible from the snapshot.
- **External GrowthBook config service (confirmed dependency, unpublished server-side state).** `abuse-enforcement-service` implements a full read/write `GrowthBookClient`/`GrowthBookWriter` integration with a protected admin endpoint (S00-F009). The actual config values GrowthBook serves are external and unpublished.
- **Decider-gated cross-service calls (confirmed gate, unconfirmed value).** `phoenix-rankall-strato`'s visibility-filtering consultation is wrapped in decider flag `enable_vf_rust_should_drop_tweet` (S00-F012); decider state is not part of this snapshot.
- **Partially-evidenced production-sync process.** The README's cron-based default-sync claim now has a corresponding self-reported marker in the snapshot -- "mirrored from ...; last sync ..." headers on `param.rs` and two `abuse-enforcement-service` rule files (S00-F013, corrected) -- but the sync mechanism's own implementation, its cron/schedule status, and whether the synced values are exactly "primary production values" remain unpublished/unestablished. This is still the largest single gap identified in S00 bounding the credibility of every checked-in default as a stand-in for a production value, though less severe than "zero evidence."
- **Explicitly disclosed omissions.** Grox `.j2` prompt templates (self-corroborated, S00-F010) and an unspecified subset of botmaker rules (plausible, unverifiable) are missing by the repository owner's own design, per the README's "What's not in this repo?" section.
- **Undocumented in-flight feature expansion.** The `EnableAllAuthorFollowHydration`/`author_follows_viewer` mechanism (S00-F006, S00-F007) shows the checked-in code already contains functionality beyond what either S00-assigned document describes, suggesting the two-document narrative (README + bidirectional-boost doc) is not necessarily a complete account of everything active in this exact area even within the published snapshot itself.

## Cross-domain obligations

Per `_analysis/architecture/CROSS_DOMAIN_SYSTEMS.md`, S00's findings feed the following bridges and specialists:

- **S01 + S02**: Brazil2026ElectionFilter/pipeline-table discrepancy (S00-F001, S00-F002); BidirectionalFollowHydrator failure-path framework semantics (S00-F008); the 6 unlabeled filter modules in `filters/mod.rs`.
- **S05 + S06**: `author_follows_viewer` as a Phoenix model input feature (S00-F007) — highest-priority item, since it's a materially different mechanism from the documented weight-boost path and appears nowhere in either S00-assigned document; hash-embedding and candidate-isolation Key Design Decision claims (S00-C029, S00-C030) not independently re-derived.
- **S06**: `phoenix/NOTICE` third-party licensing within `phoenix/xrex/` (S00-F011); `phoenix/QUICKSTART.md` end-to-end execution (deferred to S18, cross-owned with S06).
- **S07 + S14**: `phoenix-rankall-strato` → visibility-filtering decider-gated consultation (S00-F012).
- **S17 (config/experiments) + everyone**: the corrected cron-sync evidentiary picture (S00-F013: a config-mirroring marker exists on `param.rs` and two `abuse-enforcement-service` files, but cron-specificity and the "production values" equivalence remain `UNKNOWN`) and the two confirmed-but-distinct runtime-override mechanisms (`xai_feature_switches`, GrowthBook) (S00-F009) are cross-cutting and should inform every specialist's treatment of "checked-in default." S17 should specifically attempt to locate the sync mechanism's own implementation, which S00 could not find published.
- **S18**: reproducibility boundary for `phoenix/` quickstart; cataloguing standalone-buildable vs internal-infrastructure-dependent components repository-wide.
- **B03 (score pressure) + B07 (in-network vs OON)**: bidirectional-boost mechanism and its newly-discovered second feature-input pathway.
- **B09 (legal/geo/special cases) + B12 (public-vs-production boundary)**: Brazil2026ElectionFilter production-activation status; all historical A/B-test/rollout-percentage claims in the bidirectional-boost doc.

## Material findings

13 findings recorded in `_analysis/evidence/S00_findings.jsonl` (S00-F001 through S00-F013); see that file for full evidence citations. Significance distribution: 4 HIGH (S00-F001, S00-F006, S00-F007, S00-F013), 6 MEDIUM (S00-F002, S00-F003, S00-F004, S00-F009, S00-F010, S00-F012), 3 LOW (S00-F005, S00-F008, S00-F011).

## Unknowns

Recorded as `UNKNOWN` in the claim matrix and not resolved in S00:

- Whether experiments running at "10% or more" of traffic are in fact always reflected in this repository, as the README's editorial policy claims (S00-C022).
- The sync mechanism's own implementation (script/job/trigger), whether it is cron-based, and whether its synced values are exactly "primary production values" (S00-C054, S00-C055, S00-F013) -- a self-reported marker of the mechanism's *effect* was found (S00-C053), but not the mechanism itself.
- Whether literally every pipeline stage is individually switchable (S00-C011/S00-C046): `Brazil2026ElectionFilter` is a direct, confirmed counterexample with no local param gate.
- Whether the README's Components-table one-line role descriptions are accurate for the ~20 directories S00 did not individually spot-check (S00-C047).
- Whether the Post Pipeline/Blending Pipeline and the 7-stage request path actually compose/execute exactly as diagrammed at runtime (S00-C044, S00-C045) -- file/symbol existence was confirmed, execution semantics were not.
- All specific dates, percentages, and per-user boost-value assignments in the bidirectional-follow A/B test narrative (S00-C033, S00-C034).
- The causal (World Cup feedback) motivation for the July 24 boost change (part of S00-C035) — the numeric outcome is confirmed; the stated reason is not.
- Whether `botmaker-rules/` omits a large or small fraction of the production rule set (S00-C025).
- The Under the Hood tool's actual end-user behavior/availability, since it is an external product surface outside the repository (S00-C026, S00-C028).
- Whether `phoenix/QUICKSTART.md` actually succeeds end-to-end as claimed (S00-C027) — not executed in S00, downstream S18 obligation.

## Composite-claim discipline (remediation methodology)

After independent audit, all 57 (then-42) claim-matrix rows were re-audited against a strict rule: **a composite claim may not be classified `CONFIRMED`/`DIRECT` merely because one part of it is directly verified.** Where a row bundled a well-evidenced part (typically file/directory/symbol existence) with a materially distinct, less-evidenced part (typically a functional, behavioral, historical, or forward-looking claim), the row was either split into atomic sub-claims with independently appropriate statuses, or downgraded to the weakest classification its material sub-claims required.

12 original rows were narrowed/split (`S00-C006`, `S00-C008`, `S00-C010`, `S00-C011`, `S00-C013`, `S00-C015`, `S00-C017`, `S00-C021`, `S00-C025`, `S00-C027`, `S00-C032` — the 11 rows the audit explicitly named — plus `S00-C036`, found during the full re-audit for the same reason and split accordingly), producing 15 new rows (`S00-C043`–`S00-C057`) with `downstream_passes` pointing at whichever specialist owns the unverified part. Two patterns recurred most often: (1) "component/file X exists" (kept `CONFIRMED`/`DIRECT`, narrowed) bundled with "X does/performs Y" (split off, downgraded to `PARTIALLY_CONFIRMED`/`STRONG_INFERENCE` or `DEFERRED`/`UNKNOWN`); (2) a currently-visible implementation mechanism bundled with an unverifiable historical or forward-looking policy claim (e.g. `S00-C032`'s "future updates will be published as diffs" split from its plain-language mechanism description into `S00-C056`). One split (`S00-C011`→`S00-C046`) surfaced a genuine `CONTRADICTED` sub-claim: the README's unqualified "stages can be switched on/off individually" does not hold for `Brazil2026ElectionFilter`, which has no local param gate at all.

No row now carries a `CONFIRMED`/`DIRECT` classification while its own notes admit a material unverified portion; unverified portions were relocated to their own rows instead.

## Coverage accounting

- S00-assigned baseline files: 4 (`CODE_OF_CONDUCT.md`, `LICENSE`, `README.md`, `docs/BIDIRECTIONAL_BOOST_CHANGE.md`) — all 4 examined and marked `COMPONENT_REVIEWED`.
- Supporting (non-S00-coverage-changing) files examined for verification: approximately 50 distinct paths across `home-mixer/`, `candidate-pipeline/`, `visibility-filtering/`, `vm-ranker/`, `phoenix-rankall-strato/`, `phoenix/` (including `phoenix/crates/common/xai-recsys/src/util.rs` and `phoenix/crates/serving/xai-recsys-proto/proto/recsys.proto`, added during remediation), `grox/`, `abuse-enforcement-service/` (including the corrected cron/config-mirroring search), plus directory-existence checks for all 24 top-level components named in the README's Components section. Full list in `_analysis/review/S00_file_review.csv`'s `supporting_files_examined` column.
- Claims catalogued: 57 (`S00-C001`–`S00-C057`; up from 42 after remediation — 12 rows narrowed in place, 15 new rows added, no row removed). Status counts: 21 `CONFIRMED`, 20 `PARTIALLY_CONFIRMED`, 5 `DEFERRED`, 4 `CONTRADICTED`, 7 `UNKNOWN`. Evidence-class counts: 25 `DIRECT`, 20 `STRONG_INFERENCE`, 1 `POSSIBLE`, 11 `UNKNOWN`.
- Findings recorded: 13 (`S00-F001`–`S00-F013`, unchanged in count; S00-F007 and S00-F013 substantively revised in content — see "Remediation note" above). Significance distribution unchanged: 4 HIGH, 6 MEDIUM, 3 LOW.
- Full 2,016-object baseline integrity re-verified during remediation via three independent methods (git-history diff, git tree identity, manual SHA-256 + git-blob-SHA1 cross-check against the snapshot manifest) — zero mismatches, zero missing objects. Full methodology and results recorded in `S00_run.md`.
- No file outside the four S00-assigned paths had its coverage-ledger review state changed.
