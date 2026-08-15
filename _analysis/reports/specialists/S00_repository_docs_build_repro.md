# S00 — Repository Documentation, Published Claims & Reproduction Boundary

## Scope and snapshot

- Upstream repository: `xai-org/x-algorithm`, branch `main`
- Upstream commit: `c65aa179db7bdd61e2c2821eac87f208a105c053`
- Upstream Git tree: `1d4c89941bfcd2ea3aab7c780f7447342e304e42`
- Snapshot identifier: `2026-08-15_c65aa17`
- Baseline tracked files: 2,016
- Pass: **S00 — Snapshot, docs, build/repro boundaries** (per `_analysis/passes/README.md`)
- This report documents component-audit-level (`COMPONENT_REVIEWED`) findings only. No behavior-trace, discovery, or adversarial-verification pass has been performed on this material; those remain `NO` in the coverage ledger for every S00 file.

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
3. The README's central claim that "cron scripts... set the defaults in this repository's code to be the primary production values" has **no corresponding artifact anywhere in the snapshot** — it is asserted only in the README's own prose (S00-F013). This is the load-bearing assumption behind treating any checked-in default as production-representative, and it cannot be independently verified from this repository.
4. The root `LICENSE` (Apache-2.0) is accurate as far as it goes, but `phoenix/NOTICE` documents third-party BSD-3-Clause and Apache-2.0 code bundled within `phoenix/xrex/`, which a naive "the whole repo is one license" reading would miss (S00-F011).

None of these are treated as proof of malfeasance or of inaccurate public communication; they are recorded as evidence gaps and drift for downstream passes (S01, S02, S05, S06, S17, S18, and behavior traces B03/B09/B12) to resolve with deeper, component-specific evidence.

## What the repository claims to contain

`README.md` states the repository contains "the core code that determines which posts a viewer sees in the For You feed," combining in-network (Thunder) and out-of-network (Phoenix retrieval, SimClusters) content, filtering, and transformer-based ranking (S00-C001). The "What's not in this repo?" section explicitly discloses two categories of omission: Grox LLM prompt templates (`.j2` files) and "some botmaker rules" (S00-C025), citing gameability risk as the reason, with "Under the Hood" offered as a partial transparency substitute (S00-C026).

Both named omissions were independently checked. No `.j2` file exists anywhere under `grox/`, and `grox/flows/upa/prompts.py` contains a self-referential comment confirming the omission is intentional and documented in-repo (S00-F010) — an unusually direct piece of corroborating evidence. The `botmaker-rules/` omission claim cannot be similarly confirmed or refuted: 73 files exist under `botmaker-rules/scarecrow/{bot,derived-feature}`, but whether additional production rules exist beyond this set is unknowable from a single snapshot.

The "Deployment-related code" subsection specifically calls out `phoenix/` as designed to be runnable end-to-end, citing a Cargo workspace, `pyproject.toml`, and `QUICKSTART.md` (S00-C027). All three files exist at the named paths; S00 did not execute the quickstart (out of scope per pass instructions — reserved for S18).

## Architecture claims and verification

The README's Request Path diagram (S00-C010) describes a 7-stage `PhoenixCandidatePipeline`: query hydration → parallel candidate sources (Thunder in-network; Phoenix retrieval + SimClusters out-of-network) → candidate hydration → pre-scoring filters → scoring (`PhoenixScorer`, `RankingScorer`, `VMRanker`) → selection (`TopKScoreSelector`) → post-selection filters (`VFCandidateHydrator`, `VFFilter`, `DedupConversationFilter`). Every named file and directory in this diagram exists (`home-mixer/query_hydrators/`, `home-mixer/sources/`, `home-mixer/candidate_hydrators/`, `home-mixer/filters/`, `home-mixer/scorers/{phoenix_scorer,ranking_scorer,vm_ranker}.rs`, `home-mixer/selectors/top_k_score_selector.rs`, `home-mixer/candidate_hydrators/vf_candidate_hydrator.rs`, `home-mixer/filters/vf_filter.rs`, `home-mixer/filters/dedup_conversation_filter.rs`). This confirms **structural** accuracy (files exist, are named as claimed) but S00 did not independently re-derive the exact runtime execution order or conditional stage-skipping logic within the `candidate-pipeline` execution engine — that belongs to S01.

The Blending Pipeline (`ForYouCandidatePipeline`, `BlenderSelector`, `home-mixer/ads/partition_organic_blender.rs`) similarly exists at the claimed paths (S00-C008). The Labeling Path diagram's components (`grox/`, `media-model-proxy/`, `clip/`, `agatha/`, `bdsm/`, `user-cred-v2/`, `scarecrow/`, `botmaker/`, `botmaker-rules/scarecrow/`, `abuse-enforcement-service/`, `safety-label-user-agg/`, `visibility-filtering/`) all exist (S00-C012).

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

This is the section where S00 found the most consequential evidence gap. The README states (S00-C023): "many tunable values are read from a configuration system rather than written into the code... we run cron scripts that set the defaults in this repository's code to be the primary production values." Two things were established:

- A runtime-override mechanism genuinely exists and is wired into checked-in code: `home-mixer/params/param.rs` binds every `param!()` default to a named key read via the `xai_feature_switches` crate, and `abuse-enforcement-service` implements a full `GrowthBookClient`/`GrowthBookWriter` integration, including a protected admin API for writing config (S00-F009). This is `DIRECT` evidence that checked-in defaults are runtime-overridable in at least two distinct, independently-implemented ways across the repository.
- **No cron script, scheduled job, or sync-tooling artifact of any kind exists in the snapshot.** A repository-wide search for the string "cron" returns exactly one hit: the README sentence itself (S00-F013). The mechanism that is supposed to keep checked-in defaults matching "primary production values" is therefore asserted only in prose and cannot be independently verified. This caveat propagates to every other S00 finding that treats a checked-in default as production-representative (most notably S00-F004, the bidirectional-boost value).

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
3. Populates a new field, `author_follows_viewer`, which — via `home-mixer/models/candidate.rs`'s feature-conversion method — is mapped into `xai_recsys_proto::AuthorInfo.is_following_user` and thereby becomes an **input feature to the Phoenix ranking model itself**, a materially different consumption path from the documented post-hoc weight boost in `ranking_scorer.rs`.

None of this is described in either S00-assigned document. The doc explicitly frames itself as a historical, illustrative example ("here's what you might've seen... rolled out in July 2026"), and the snapshot postdates it by roughly three weeks, so continued evolution is expected and not inherently a defect — but a reader treating the diff as a live description of current behavior would be materially misled about what the file does today.

**Historical/production-rollout claims (not verifiable from source):** the July 10 A/B test's existence, its specific boost-value assignment (5/10/15/20) and population percentages, the July 13 broad rollout to boost=20, and the World Cup-feedback motivation for the July 24 change to boost=15 are all recorded `UNKNOWN` in the claim matrix. The one exception is the July 24 change's **numeric end state** (`BidirectionalFollowReplyWeightBoost = 15.0`), which is independently `DIRECT`-confirmable in the current snapshot and does match the doc's stated outcome (S00-F004) — though, per the cron-sync gap above (S00-F013), this confirms only that the checked-in default equals 15.0, not that 15.0 was or is the value actually served in production.

## Omitted/private/redacted dependencies

Confirmed omissions (per README's own disclosure, S00-C025): Grox `.j2` prompt templates (self-corroborated in source, S00-F010) and an unspecified subset of botmaker rules (plausible but not independently verifiable). Additional omission-adjacent evidence found during S00 but not claimed by either assigned document: the external GrowthBook service consulted by `abuse-enforcement-service` is itself entirely unpublished (only the client/writer code is present) — this is a missing dependency in the sense of "the config server this component depends on is not part of the repository," distinct from the README's named omission list.

## Reproducibility boundary

`phoenix/` is the one component the README explicitly claims is end-to-end runnable, backed by a Cargo workspace (`phoenix/Cargo.toml`), a Python build target (`phoenix/pyproject.toml`), and `phoenix/QUICKSTART.md`. All three exist. S00 did not execute the quickstart or attempt a build — the pass instructions reserve deep reproduction/failure auditing for S18, and S00's role is limited to establishing the boundary. Most other named components (`home-mixer/`, `visibility-filtering/`, `abuse-enforcement-service/`, etc.) are Rust crates/services without an equivalent "runs standalone with synthetic data" claim in the README; the README itself acknowledges that "code may not necessarily include build- or deployment-related files or generally self-explanatory infrastructure imports (e.g. `xai_service_runner` or `xai_kafka`)" (S00-C027), which S00 treats as an explicit, self-disclosed reproducibility boundary rather than an omission to be second-guessed.

**Downstream obligation for S18:** actually attempt the `phoenix/QUICKSTART.md` flow and report whether it succeeds unmodified from this snapshot; catalogue which other components have any standalone build/test entry point versus which assume internal infrastructure (`xai_service_runner`, `xai_kafka`, and similarly-named internal crates observed by name only, not audited for completeness in S00).

## Documentation/code contradictions

1. **`Brazil2026ElectionFilter` omitted from the Pre-Scoring Filters table** despite running in that exact pipeline stage and being described in detail elsewhere in the same README (S00-F002).
2. **`docs/BIDIRECTIONAL_BOOST_CHANGE.md`'s reproduced diff no longer matches the current file** it purports to describe, missing a second gating param, a cache-based enable condition, and a new Phoenix-feature consumption path for the same underlying signal (S00-F006, S00-F007).
3. **No corroborating artifact for the README's cron-sync claim** (S00-F013) — an absence, not a positive contradiction, but material to how much trust any "checked-in default = production value" statement in this repository deserves.

No claim in the four assigned documents was found to be affirmatively false against the checked-in source; all identified issues are omissions, gaps, or drift rather than direct falsehoods.

## Public Snapshot vs Production Reality

Material reasons the checked-in repository may not fully reconstruct actual production behavior, each grounded in specific repository evidence gathered during S00:

- **Runtime feature-switch overrides (confirmed mechanism, unconfirmed values).** `home-mixer/params/param.rs` binds every tunable via `xai_feature_switches::param!()`; the bidirectional-boost hydrator's own unit tests exercise `xai_feature_switches::FeatureSwitches::override_fs(...)` directly, proving the override mechanism is real and exercised even in test code. No production override state is visible from the snapshot.
- **External GrowthBook config service (confirmed dependency, unpublished server-side state).** `abuse-enforcement-service` implements a full read/write `GrowthBookClient`/`GrowthBookWriter` integration with a protected admin endpoint (S00-F009). The actual config values GrowthBook serves are external and unpublished.
- **Decider-gated cross-service calls (confirmed gate, unconfirmed value).** `phoenix-rankall-strato`'s visibility-filtering consultation is wrapped in decider flag `enable_vf_rust_should_drop_tweet` (S00-F012); decider state is not part of this snapshot.
- **Claimed but unverifiable production-sync process.** The README's cron-based default-sync claim has zero corresponding artifact in the snapshot (S00-F013) — this is the largest single gap identified in S00, since it underlies the credibility of every checked-in default as a stand-in for a production value.
- **Explicitly disclosed omissions.** Grox `.j2` prompt templates (self-corroborated, S00-F010) and an unspecified subset of botmaker rules (plausible, unverifiable) are missing by the repository owner's own design, per the README's "What's not in this repo?" section.
- **Undocumented in-flight feature expansion.** The `EnableAllAuthorFollowHydration`/`author_follows_viewer` mechanism (S00-F006, S00-F007) shows the checked-in code already contains functionality beyond what either S00-assigned document describes, suggesting the two-document narrative (README + bidirectional-boost doc) is not necessarily a complete account of everything active in this exact area even within the published snapshot itself.

## Cross-domain obligations

Per `_analysis/architecture/CROSS_DOMAIN_SYSTEMS.md`, S00's findings feed the following bridges and specialists:

- **S01 + S02**: Brazil2026ElectionFilter/pipeline-table discrepancy (S00-F001, S00-F002); BidirectionalFollowHydrator failure-path framework semantics (S00-F008); the 6 unlabeled filter modules in `filters/mod.rs`.
- **S05 + S06**: `author_follows_viewer` as a Phoenix model input feature (S00-F007) — highest-priority item, since it's a materially different mechanism from the documented weight-boost path and appears nowhere in either S00-assigned document; hash-embedding and candidate-isolation Key Design Decision claims (S00-C029, S00-C030) not independently re-derived.
- **S06**: `phoenix/NOTICE` third-party licensing within `phoenix/xrex/` (S00-F011); `phoenix/QUICKSTART.md` end-to-end execution (deferred to S18, cross-owned with S06).
- **S07 + S14**: `phoenix-rankall-strato` → visibility-filtering decider-gated consultation (S00-F012).
- **S17 (config/experiments) + everyone**: the cron-sync evidentiary gap (S00-F013) and the two confirmed-but-distinct runtime-override mechanisms (`xai_feature_switches`, GrowthBook) (S00-F009) are cross-cutting and should inform every specialist's treatment of "checked-in default."
- **S18**: reproducibility boundary for `phoenix/` quickstart; cataloguing standalone-buildable vs internal-infrastructure-dependent components repository-wide.
- **B03 (score pressure) + B07 (in-network vs OON)**: bidirectional-boost mechanism and its newly-discovered second feature-input pathway.
- **B09 (legal/geo/special cases) + B12 (public-vs-production boundary)**: Brazil2026ElectionFilter production-activation status; all historical A/B-test/rollout-percentage claims in the bidirectional-boost doc.

## Material findings

13 findings recorded in `_analysis/evidence/S00_findings.jsonl` (S00-F001 through S00-F013); see that file for full evidence citations. Significance distribution: 4 HIGH (S00-F001, S00-F006, S00-F007, S00-F013), 6 MEDIUM (S00-F002, S00-F003, S00-F004, S00-F009, S00-F010, S00-F012), 3 LOW (S00-F005, S00-F008, S00-F011).

## Unknowns

Recorded as `UNKNOWN` in the claim matrix and not resolved in S00:

- Whether experiments running at "10% or more" of traffic are in fact always reflected in this repository, as the README's editorial policy claims (S00-C022).
- The cron/sync mechanism's existence, implementation, and actual behavior (S00-C023, S00-F013).
- All specific dates, percentages, and per-user boost-value assignments in the bidirectional-follow A/B test narrative (S00-C033, S00-C034).
- The causal (World Cup feedback) motivation for the July 24 boost change (part of S00-C035) — the numeric outcome is confirmed; the stated reason is not.
- Whether `botmaker-rules/` omits a large or small fraction of the production rule set (S00-C025).
- The Under the Hood tool's actual end-user behavior/availability, since it is an external product surface outside the repository (S00-C026, S00-C028).
- Whether `phoenix/QUICKSTART.md` actually succeeds end-to-end as claimed (S00-C027) — not executed in S00, downstream S18 obligation.

## Coverage accounting

- S00-assigned baseline files: 4 (`CODE_OF_CONDUCT.md`, `LICENSE`, `README.md`, `docs/BIDIRECTIONAL_BOOST_CHANGE.md`) — all 4 examined and marked `COMPONENT_REVIEWED`.
- Supporting (non-S00-coverage-changing) files examined for verification: approximately 45 distinct paths across `home-mixer/`, `candidate-pipeline/`, `visibility-filtering/`, `vm-ranker/`, `phoenix-rankall-strato/`, `phoenix/`, `grox/`, `abuse-enforcement-service/`, plus directory-existence checks for all 24 top-level components named in the README's Components section. Full list in `_analysis/review/S00_file_review.csv`'s `supporting_files_examined` column.
- Claims catalogued: 42 (`S00-C001`–`S00-C042`).
- Findings recorded: 13 (`S00-F001`–`S00-F013`).
- No file outside the four S00-assigned paths had its coverage-ledger review state changed.
