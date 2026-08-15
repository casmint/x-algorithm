# S01 Run Log — Candidate Framework + Home Mixer Orchestration

## Snapshot

- Snapshot ID: `2026-08-15_c65aa17`
- Upstream commit: `c65aa179db7bdd61e2c2821eac87f208a105c053`
- Upstream Git tree: `1d4c89941bfcd2ea3aab7c780f7447342e304e42`
- Accepted S00 head consulted as prior evidence: `ae68bca41ccd680b46695bbfc15b67fea69e8e87`

## Workspace verification (before any review)

```
git status --short          -> empty (clean)
git branch --show-current   -> analysis/s00-review
git rev-parse HEAD          -> ae68bca41ccd680b46695bbfc15b67fea69e8e87  (matches expected exactly)
git log -4 --oneline --decorate:
  ae68bca (HEAD -> analysis/s00-review, origin/analysis/s00-review) analysis: finalize S00 consistency cleanup
  91926a9 analysis: remediate S00 independent audit findings
  13a0798 analysis: complete S00 repository documentation audit
  3cd83ba (origin/main, origin/HEAD, main) clean baseline for analysis
```

`git branch --list 'analysis/s01-review'` and `git ls-remote --heads origin 'analysis/s01-review'` both returned empty — the branch did not exist locally or remotely. Created via `git switch -c analysis/s01-review`.

## Framework reading

Read in full before touching S01 source: `_analysis/README.md`, `_analysis/methodology/README.md`, `_analysis/review/DEFINITION_OF_DONE.md`, `_analysis/passes/README.md`, `_analysis/domains/AUDIT_LENSES.md`, `_analysis/architecture/README.md`, `_analysis/architecture/CROSS_DOMAIN_SYSTEMS.md`, plus the finalized S00 outputs (`_analysis/reports/specialists/S00_repository_docs_build_repro.md`, `_analysis/evidence/S00_findings.jsonl`) for carry-forward context. S00 was not re-audited.

## S01 ownership determination

```python
# _analysis/passes/file_specialist_map.csv, primary_specialist == "S01"
```
Result: **227 files** — exactly matching the framework's expected workload; no discrepancy, no stop condition. Breakdown: 216 `home-mixer/`, 11 `candidate-pipeline/`. Review treatments: 221 `FULL_SOURCE_REVIEW`, 6 `TEST_EVIDENCE`. Full path list saved to a scratch file and used as the authoritative denominator throughout the pass.

## Coverage strategy (Phases A–F, per task instructions)

- **Phase A (machine inventory)**: classified all 227 files by directory (`filters/` 29, `query_hydrators/` 21, `candidate_hydrators/` 21, `sources/` 19, `clients/` 19, `side_effects/` 18, `util/urt/` 15+2, `util/` 14, `candidate_pipeline/` 7, root `home-mixer/` 10, `models/` 8, `scorers/` 7, `ads/`+`tests/` 12, `selectors/` 5, `frames/` 5, `params/` 3, `bin/` 1) and by line count (largest: `ranking_scorer.rs` 1708, `brazil_2026_election_filter.rs` 1573, `topic_ids_filter.rs` 1502, `param.rs` 1146, `phoenix_candidate_pipeline.rs` 1070). Total 41,305 lines across all 227 files.
- **Phase B (entry points/execution engine)**: deep-read all 11 `candidate-pipeline/` framework files, all 6 pipeline construction files, `server.rs` and its 4 sibling `*_server.rs` files, `main.rs`, `lib.rs`, `dark_traffic_setup.rs`, `models/query.rs`.
- **Phase C (execution graph)**: traced the full request path from gRPC entry through `QueryBuilder::build` through each pipeline's `execute_stages()` to side effects, for all 6 pipelines and all 5 servers.
- **Phase D (leaf/helper files in context)**: for every hydrator/source/filter/scorer/side-effect file, ran an `enable()`-presence grep sweep per directory and cross-referenced against the exact construction site(s) found in Phase B/C's pipeline reads, recorded in `S01_pipeline_inventory.csv`.
- **Phase E (tests/config for intended behavior)**: `home-mixer/candidate_pipeline/phoenix_candidate_pipeline.rs`'s own `#[cfg(test)] mod tests` (a full `execute()` integration test against `PhoenixCandidatePipeline::mock()`) was read as supporting evidence of intended pipeline behavior, not substituted for production-path review, consistent with methodology invariant 7 / DEFINITION_OF_DONE.
- **Phase F (account for every remaining file)**: performed a mechanical `mod.rs`-vs-directory-listing orphan sweep across all 15 relevant directories (see "Orphan sweep" below), then closed out every remaining unexamined file with an honest `TRIAGED` row (role inferred from filename/directory/construction-site context, explicitly marked as not independently opened) rather than fabricating depth. Verified 227/227 accounted for with zero duplicates/omissions before writing the coverage ledger.

## Orphan sweep methodology

For every directory with a `mod.rs` (`clients`, `ads`, `frames`, `scorers`, `selectors`, `side_effects`, `models`, `util`, `util/urt`, `query_hydrators`, `candidate_hydrators`, `sources`, `filters`, `candidate_pipeline`, `params`), a Python script extracted `mod\s+(\w+);` declarations from `mod.rs` and diffed them against the actual `.rs` files present in that directory (excluding `mod.rs` itself and test subdirectories). Three undeclared files were found:

- `home-mixer/sources/popular_topics_source.rs` (`PopularTopicsSource`) — not declared in `sources/mod.rs`.
- `home-mixer/filters/popular_topics_author_dedup_filter.rs` (`PopularTopicsAuthorDedupFilter`) — not declared in `filters/mod.rs`.
- `home-mixer/candidate_hydrators/broadcast_liveness_hydrator.rs` (`BroadcastLivenessHydrator`) — not declared in `candidate_hydrators/mod.rs`.

Each was cross-checked with a repository-wide `grep -rn "<SymbolName>"` across `home-mixer/` to confirm zero other references (construction sites, re-exports, or alternate `mod` declarations). See S01-F002. Separately, `ImpressedPostsQueryHydrator` **is** declared in `query_hydrators/mod.rs` (compiles fine) but is constructed-and-discarded (bound to an underscore-prefixed local, never pushed to the active `query_hydrators` Vec) in `phoenix_candidate_pipeline.rs` — a different failure mode (pipeline-wiring gap, not module-tree absence) — traced to its concrete downstream consequence: `PreviouslySeenPostsBackupFilter`'s sole data dependency (`query.impressed_post_ids`) is always empty. See S01-F001.

## Key files deep-read (representative, not exhaustive — see `S01_file_review.csv` for the full 227-row account)

- `candidate-pipeline/{candidate_pipeline,hydrator,scorer,source,filter,selector,side_effect,query_hydrator,pipeline_summary,util,lib}.rs` (all 11, full reads)
- `home-mixer/candidate_pipeline/{phoenix_candidate_pipeline,for_you_candidate_pipeline,following_candidate_pipeline,ranked_following_candidate_pipeline,reverse_chron_posts_pipeline,phoenix_scores_pipeline,mod}.rs` (all 7, full reads)
- `home-mixer/{server,scored_posts_server,for_you_server,following_feed_server,ranked_following_feed_server,phoenix_scores_server,dark_traffic_setup,main,lib}.rs`
- `home-mixer/models/query.rs`
- `home-mixer/sources/{scored_posts_source,reverse_chron_posts_source,popular_topics_source}.rs`
- `home-mixer/candidate_hydrators/broadcast_liveness_hydrator.rs`
- `home-mixer/filters/previously_seen_posts_backup_filter.rs`
- `home-mixer/query_hydrators/impressed_posts_query_hydrator.rs`
- `home-mixer/scorers/vm_ranker.rs`, `home-mixer/scorers/phoenix_scorer.rs`
- `home-mixer/bin/pipeline_components_json.rs`
- all 6 `mod.rs` orphan-sweep targets plus `clients/mod.rs`, `scorers/mod.rs`, `params/mod.rs`, `models/mod.rs`

## Searches / commands (representative)

- `python3 -c "..."` over `_analysis/passes/file_specialist_map.csv` for the S01-primary count and breakdown.
- Per-directory `for f in home-mixer/<dir>/*.rs; do grep -c "fn enable" "$f"; done` sweeps across `query_hydrators/`, `candidate_hydrators/`, `sources/`, `filters/`, `side_effects/` (5 sweeps, ~110 files).
- `grep -rn "<Symbol>" home-mixer/ --include=*.rs` for every construction/usage-site confirmation (SimClusters wiring, six previously-unplaced filters, three module-tree orphans, `broadcast_is_live` field readers/writers, `impressed_post_ids` field readers/writers).
- Python `mod.rs`-vs-`os.listdir()` diff script across 15 directories for the orphan sweep.
- `wc -l` sweeps for file-size triage (identifying `value_model_gate.rs` as a 537-line unread file worth flagging for S05/S08).

## Artifacts written

- `_analysis/reports/specialists/S01_candidate_pipeline_home_mixer.md` (created)
- `_analysis/evidence/S01_findings.jsonl` (created — 13 lines, `S01-F001`–`S01-F013`)
- `_analysis/evidence/S01_pipeline_inventory.csv` (created — 169 rows across 6 pipelines + framework)
- `_analysis/review/S01_file_review.csv` (created — 227 rows, one per S01-primary file, verified zero duplicates/omissions)
- `_analysis/review/S01_run.md` (this file)
- `_analysis/coverage_ledger.csv` (modified — S01-primary rows only; see below)

No other file under `_analysis/` was created or modified. No file outside `_analysis/` was modified.

## Unresolved questions / downstream obligations

See the main report's "Unknowns" and "Cross-domain handoffs" sections for the full list. Highest-priority items: (1) what sets `Gizmoduck.allow_for_you_recommendations = Some(false)` (S11/S14/S15); (2) `value_model_gate.rs`'s full contents, unread (S05/S08); (3) whether the three module-tree-absent components (S01-F002) are active in any unpublished build variant, unanswerable from this snapshot; (4) deep `ads/` blending-policy semantics, explicitly deferred to S02 per the pass charter.

## Self-check result

1. **Exactly 227 S01-primary files, computed not assumed**: confirmed via Python census of `file_specialist_map.csv`; matches the framework's expected workload.
2. **`S01_file_review.csv` has exactly one row per S01-primary file, no duplicates, no omissions, no extras**: confirmed programmatically — 227 rows, 227 unique paths, set-equality with the authoritative path list verified.
3. **No supporting/non-S01-primary file marked reviewed**: confirmed — every row in `S01_file_review.csv` was generated either from the S01-primary path list directly or from `S01_pipeline_inventory.csv` rows whose `source_path` was independently checked against the S01-primary set before inclusion.
4. **Every `S01-F###` reference resolves**: confirmed — all findings referenced in the specialist report exist in `S01_findings.jsonl` with matching IDs.
5. **Every referenced `S00-C###`/`S00-F###` ID resolves in existing S00 artifacts**: confirmed by cross-checking `S00-F001`, `S00-F002`, `S00-F006`, `S00-F007`, `S00-F008`, `S00-C043`, `S00-C044`, `S00-C045`, `S00-C046` (all referenced in this report's "S00 carry-forward resolutions" table) against `_analysis/evidence/S00_findings.jsonl` and `_analysis/evidence/S00_claim_matrix.csv` — all present.
6. **Unique S01 finding IDs**: confirmed — 13/13 unique, `S01-F001`–`S01-F013`, no gaps.
7. **Valid JSONL**: confirmed via `json.loads` over every line.
8. **Allowed enums only**: confirmed — all `evidence_class` values are `DIRECT` (13/13); all `status` values are `CONFIRMED` (13/13); all `significance` values are `HIGH`/`MEDIUM`/`LOW`.
9. **No finding marked `DIRECT` where its wording extends beyond direct evidence**: each finding's `runtime_caveats` array explicitly bounds what was *not* established (e.g. S01-F002 does not claim the three orphaned components will never activate; S01-F008 does not claim what Gizmoduck-side logic sets the flag; S01-F003 does not claim the three new sources' retrieval semantics; S01-F007 does not extend to the six filters' internal business logic).
10. **Coverage ledger changed only for S01-primary rows**: verified via `git diff --stat` restricted to `_analysis/coverage_ledger.csv`, cross-checked row-by-row against the 227-path list (see below).
11. **`pass_behavior_trace`/`pass_discovery`/`pass_adversarial_verify` remain `NO` everywhere**: confirmed — S01 did not set any of these fields to `YES` for any row, including the 227 it touched.
12. **No frozen upstream source changed**: confirmed via full 2,016-object baseline verification (git-history diff restricted to non-`_analysis/` paths, git tree identity, manual SHA-256, git blob SHA1 cross-check — see below).

**Overall self-check result: ALL CHECKS PASSED.**
