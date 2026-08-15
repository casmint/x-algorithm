# S02 Run Log — Home Feed Filters, Selection, Blending & Ads

## Snapshot

- Snapshot ID: `2026-08-15_c65aa17`
- Upstream commit: `c65aa179db7bdd61e2c2821eac87f208a105c053`
- Upstream Git tree: `1d4c89941bfcd2ea3aab7c780f7447342e304e42`
- Accepted cumulative-analysis head consulted as prior evidence: `ae818b5ea1a9e12322b4f1a8e40ab8ec5dd9dfe6` (`analysis: finalize S01 evidence cleanup`)

## Stage 1 — branch setup

Workspace verification before any branch operation:

```
git status --short          -> empty (clean)
git branch --show-current   -> analysis/s01-review
git rev-parse HEAD          -> ae818b5ea1a9e12322b4f1a8e40ab8ec5dd9dfe6  (matches expected exactly)
git log -5 --oneline --decorate:
  ae818b5 (HEAD -> analysis/s01-review, origin/analysis/s01-review) analysis: finalize S01 evidence cleanup
  5f33d38 analysis: complete S01 candidate pipeline orchestration audit
  ae68bca (origin/analysis/s00-review, analysis/s00-review) analysis: finalize S00 consistency cleanup
  91926a9 analysis: remediate S00 independent audit findings
  13a0798 analysis: complete S00 repository documentation audit
```

`git branch --list 'analysis/full-audit' 'analysis/s02-review'` and `git ls-remote --heads origin 'analysis/full-audit' 'analysis/s02-review'` all returned empty — neither branch existed locally or remotely.

Created and pushed `analysis/full-audit` at the exact accepted S01 head:

```
git branch analysis/full-audit ae818b5ea1a9e12322b4f1a8e40ab8ec5dd9dfe6
git push -u origin analysis/full-audit
git rev-parse analysis/full-audit         -> ae818b5ea1a9e12322b4f1a8e40ab8ec5dd9dfe6
git rev-parse origin/analysis/full-audit  -> ae818b5ea1a9e12322b4f1a8e40ab8ec5dd9dfe6
```

Created `analysis/s02-review` from `analysis/full-audit`:

```
git switch -c analysis/s02-review analysis/full-audit
git branch --show-current  -> analysis/s02-review
git rev-parse HEAD         -> ae818b5ea1a9e12322b4f1a8e40ab8ec5dd9dfe6
```

`analysis/full-audit` was not moved again at any point during this pass.

## Framework reading

Read in full before touching S02 source: `_analysis/README.md`, `_analysis/methodology/README.md`, `_analysis/review/DEFINITION_OF_DONE.md`, `_analysis/passes/README.md`, `_analysis/domains/AUDIT_LENSES.md`, `_analysis/architecture/README.md`, `_analysis/architecture/CROSS_DOMAIN_SYSTEMS.md`, plus the accepted S01 report (`S01_candidate_pipeline_home_mixer.md`), `S01_findings.jsonl` (13 findings), and `S01_pipeline_inventory.csv` (169 rows) for carry-forward context. `S00_findings.jsonl` was consulted only where S01/S02 references required it (Brazil2026ElectionFilter's S00-F001/F002). Neither S00 nor S01 was re-audited.

## S02 ownership determination — the central methodological finding of this pass

`_analysis/passes/file_specialist_map.csv, primary_specialist == "S02"` returns **zero rows**. This was not assumed — it was queried directly (`awk -F',' 'NR>1 && $4=="S02"'`) and cross-checked against the full `primary_specialist` value distribution (`S00`:4, `S01`:227, `S03`:24, `S04`:232, `S05`:303, `S07`:52, `S08`:10, `S09`:165, `S10`:127, `S11`:145, `S12`:492, `S13`:108, `S14`:70, `S15`:31, `S16`:26 — `S02`, `S06`, `S17`, `S18` all absent).

Root cause traced to `_analysis/tools/build_specialist_map.py` (L12-47): `top_component` `"home-mixer"` maps to `COMPONENT["home-mixer"] = ["S01"]`, and `primary_specialist = passes[0]`. S02 is only ever appended later (`add(passes,"S02")`), conditionally, for rows where `D07`/`D08 in ds` or the path starts with `home-mixer/selectors/` or `home-mixer/ads/` — an appended entry can never become `passes[0]`. This makes `primary_specialist == "S02"` mathematically unreachable for any row the tool can generate, not a coincidental gap in this particular file set.

`awk -F',' 'NR>1 && $3 ~ /S02/'` (specialist_passes contains S02) returns exactly **62 rows**, all `primary_specialist == "S01"`. This 62-file set is the operational working set this pass used for `S02_file_review.csv`, the coverage-accounting sections of the report, and the coverage-ledger decision below. Recorded as finding S02-F001. A second, related finding (S02-F002) establishes that the 8 files most central to this pass's blending-composition question (the non-post/wrapping sources) are tagged `S01;S05` (domain `D03`) rather than `S01;S02` — a separate domain-mapping artifact, not the same root cause as S02-F001.

## Coverage strategy

- **Phase A (ownership + inventory)**: computed the 62-file working set (above); classified by directory (`ads/` 12, `candidate_hydrators/` 4, `candidate_pipeline/` 1, `filters/` 29, `frames/` 5, `query_hydrators/` 6, `selectors/` 5); pulled line counts from `_analysis/domains/file_domain_map.csv` (12,609 total lines across the 62 files — confirmed a genuinely lean scope, consistent with the task's "thorough but lean" instruction).
- **Phase B (central mechanism)**: deep-read `home-mixer/selectors/blender_selector.rs`, `following_blender_selector.rs`, `top_k_score_selector.rs`, `passthrough_selector.rs` in full; `home-mixer/candidate_pipeline/for_you_candidate_pipeline.rs` in full (the pipeline construction site naming all 7 ForYou sources, 1 pre-selection filter, selector, 1 post-selection filter, 9 side effects in declared order).
- **Phase C (ads)**: deep-read all 6 non-test `home-mixer/ads/*.rs` files in full (`mod.rs`, `partition_organic_blender.rs`, `safe_gap_blender.rs`, `time_gap_blender.rs`, `following_ad_blender.rs`, `util.rs`) — established the 3 param-selected For-You-family blenders' differing adjacency-check coverage (S02-F005) and the Following-surface conversation-unit-aware blender (S02-F012).
- **Phase D (all 29 filters)**: every file in `home-mixer/filters/` read in full (constant-heavy sections of `brazil_2026_election_filter.rs` and `topic_ids_filter.rs` — the 665-entry user-ID list and ~150-entry topic-ID catalog respectively — were read for structure/predicate logic, not transcribed entry-by-entry; both files' control-flow and test assertions were read completely).
- **Phase E (frames, query hydrators, remaining candidate hydrators)**: all 5 `frames/*.rs`, all 6 `query_hydrators/*.rs` (the S02-tagged subset), and all 4 `candidate_hydrators/*.rs` (the S02-tagged subset) read in full.
- **Phase F (necessary boundary reads, not claimed as S02-reviewed)**: to answer the task's central blending/ads/non-post-source questions, this pass additionally read in full — as supporting context only, per the task's explicit permission to read S01/S05 files to establish boundaries without marking them S02-reviewed — the 8 non-post/wrapping sources (`ads_source.rs`, `who_to_follow_source.rs`, `prompts_source.rs`, `push_to_home_source.rs`, `feed_survey_source.rs`, plus construction-site confirmation of `scored_posts_source`/`reverse_chron_posts_source` usage), 5 side effects (`served_ad_history_cache_side_effect.rs`, `update_served_history_side_effect.rs`, `truncate_served_history_side_effect.rs`, `publish_seen_ids_to_kafka_side_effect.rs`, `ads_injection_logging_side_effect.rs`), `util/conversation_grouping.rs`, `util/candidates_util.rs` (the `related_post_ids_iter` helper), `server.rs` (single line — `seen_ids` population from `proto_query.seen_ids`), `params/config.rs` (result-size/position constants), and `candidate_pipeline/{ranked_following_candidate_pipeline,following_candidate_pipeline}.rs` (construction-site confirmation of sources/selector/filters for the Following-family surfaces). None of these files' rows in `S02_file_review.csv` or `coverage_ledger.csv` were created or altered by this pass.
- **Phase G (verification of specific claims)**: `grep -n` sweeps confirmed exact filter/hydrator ordering inside `phoenix_candidate_pipeline.rs` (18 pre-scoring filters, 3 scorers, 6 post-selection hydrators, 3 post-selection filters, all in declared array order), confirmed `PopularTopicsAuthorDedupFilter` has no `pub mod` line in `filters/mod.rs`, confirmed `FollowingRetweetDeduplicationFilter`/`SelfReplyChainFilter` are wired into `reverse_chron_posts_pipeline.rs` and `ResultSizeFilter` into `phoenix_scores_pipeline.rs` exactly as the task's Section 11 framing stated, and confirmed no construction site for `PassthroughSelector` across the 6 pipeline files read (left as an open question, not asserted dormant).

## Searches / commands (representative)

- `awk -F',' 'NR>1 && $4=="S02"'` / `'NR>1 && $3 ~ /S02/'` over `file_specialist_map.csv` for the ownership census (S02-F001).
- `grep "util/urt"` / `grep "sources/"` cross-referenced between `file_domain_map.csv` and `file_specialist_map.csv` to establish the D03-mistagging pattern (S02-F002).
- Python line-count join between `file_domain_map.csv` and the 62-file working set (12,609 total lines).
- `grep -n "Box::new(...)" home-mixer/candidate_pipeline/phoenix_candidate_pipeline.rs` for exact filter/hydrator/scorer array order.
- `grep -rn "PopularTopicsAuthorDedupFilter" home-mixer/` to confirm zero references outside its own file (module-tree-absence corroboration).
- `grep -n "pub const" home-mixer/params/config.rs` for exact result-size/position constant values.
- Python git-blob-SHA1 cross-check (see "Baseline integrity" below).

## Artifacts written

- `_analysis/reports/specialists/S02_feed_filters_selection_blending_ads.md` (created)
- `_analysis/evidence/S02_findings.jsonl` (created — 14 lines, `S02-F001`–`S02-F014`)
- `_analysis/evidence/S02_feed_composition_inventory.csv` (created — 24 behaviorally-significant-component rows across ForYou/Following/RankedFollowing/PhoenixScores surfaces, not a per-file mechanical census)
- `_analysis/review/S02_file_review.csv` (created — 62 rows, one per S02-tagged file, verified zero duplicates/omissions/extras)
- `_analysis/review/S02_run.md` (this file)

**`_analysis/coverage_ledger.csv` was NOT modified** — see "Coverage ledger decision" below.

No other file under `_analysis/` was created or modified. No file outside `_analysis/` was modified.

## Coverage ledger decision

Task Section 25 instructs: "Update ONLY S02-primary rows in `_analysis/coverage_ledger.csv`... Do not alter S00/S01 coverage rows." Given S02-F001 (zero rows satisfy `primary_specialist == "S02"`, and all 62 files in this pass's working set carry `primary_specialist == "S01"`), these two instructions are in direct tension for every file this pass touched: there are no S02-primary rows to update, and every row this pass could otherwise touch is, by the ledger's own ownership column, an S01 row.

This pass resolved the tension conservatively: **zero edits to `coverage_ledger.csv`.** Editing S01-owned rows (even to add corroborating detail) risks overwriting or double-counting S01's legitimate `COMPONENT_REVIEWED`/`TRIAGED` markers and `pass_component_audit` flags, several of which (e.g. `blender_selector.rs`) S01 already set to `YES` as part of its own orchestration-level read. Leaving the ledger untouched is fully reversible and non-destructive; incorrectly modifying it would not be. This decision, and its root cause, is documented in the specialist report's "Coverage/accounting" section and flagged as an open methodology question for whoever next revises the mapping tooling or the ledger's update rules — not silently worked around.

## Baseline integrity verification

Before writing any artifact, confirmed the working tree was clean relative to the accepted S01 head (`git status --short` empty, `git diff --stat` empty). After writing all S02 artifacts, confirmed only `_analysis/` paths appear in `git status --short` (four new untracked files, zero modified files).

Full baseline cross-check against the frozen commit, git-blob-SHA1 method (matching the process established in S00's remediation and reused unmodified by S01):

```python
manifest = {row['path']: row['git_blob_sha1'] for row in csv.DictReader(open('_analysis/snapshots/2026-08-15_c65aa17/file_manifest.csv'))}
# 2016 entries
tree = {path: blob_sha1 for path, blob_sha1 in parse('git ls-tree -r c65aa179db7bdd61e2c2821eac87f208a105c053')}
# 2016 entries
```

Result: `missing_from_tree: 0`, `missing_from_manifest: 0`, `sha1 mismatches: 0`. All 2,016 baseline objects match the frozen commit exactly. The bootstrap validator (`_analysis/tools/validate_coverage.py`) was not re-run, consistent with S00/S01 precedent (its `all_review_states_still_unreviewed` check is a Phase-1 bootstrap assertion that is expected to diverge once any specialist pass advances ledger rows — not applicable here in any case, since this pass made zero ledger edits).

## Self-check result

1. **S02 ownership set computed, not assumed, and its zero-primary-rows property explicitly resolved**: confirmed via direct `awk` queries against `file_specialist_map.csv`, root-caused against `build_specialist_map.py`, documented as S02-F001.
2. **`S02_file_review.csv` has exactly one row per working-set file, no duplicates, no omissions, no extras**: confirmed programmatically — 62 rows, 62 unique paths, set-equality with the 62-file authoritative list verified (`missing from review: set()`, `extra in review: set()`).
3. **No supporting/non-S02-working-set file marked reviewed**: confirmed — every row in `S02_file_review.csv` was generated from the 62-file working-set list directly; the 8 non-post sources, 5 side effects, and other boundary files read for context appear only as citations/`supporting_files_examined` values in report prose and file-review rows, never as their own `S02_file_review.csv` row.
4. **Every `S02-F###` reference resolves**: confirmed — all findings referenced in the specialist report and inventory exist in `S02_findings.jsonl` with matching IDs; validated via `json.loads` over every line plus an ID-uniqueness check (14/14 unique, `S02-F001`–`S02-F014`, no gaps).
5. **Every referenced `S00-F###`/`S01-F###` ID resolves in existing artifacts**: confirmed by cross-checking `S00-F001`, `S00-F002` (Brazil2026ElectionFilter) against `_analysis/evidence/S00_findings.jsonl`, and `S01-F001`, `S01-F002`, `S01-F004`, `S01-F005`, `S01-F006`, `S01-F007`, `S01-F009` against `_analysis/evidence/S01_findings.jsonl` — all present, titles match this report's characterization of them.
6. **Valid JSONL**: confirmed via `json.loads` over every line of `S02_findings.jsonl`.
7. **Allowed enums only**: confirmed — all 14 `evidence_class` values are `DIRECT` (13) or `STRONG_INFERENCE` (1); all `status` values are `CONFIRMED` (13) or `PARTIALLY_CONFIRMED` (1); all `significance` values are `HIGH`(3)/`MEDIUM`(7)/`LOW`(4).
8. **No enable()-gated component described as unconditional**: every `enable_or_gate` value in the inventory and every `config_or_reachability`/gating clause in the file-review and report text was written from the component's own `enable()` implementation (or explicit absence of one), not inferred.
9. **No `DIRECT` claim whose caveat admits a material unverified consequence**: reviewed all 14 findings — S02-F004 is `STRONG_INFERENCE`/`PARTIALLY_CONFIRMED` specifically because its downstream-consumer consequence (URT marshaller behavior) was not independently verified; every other `DIRECT` finding's `runtime_caveats` bounds only genuinely out-of-scope questions (production param values, external service internals), not unverified consequences of the DIRECT claim itself.
10. **Ledger changed only for S02-primary rows**: trivially satisfied — the ledger was not changed at all (see "Coverage ledger decision" above); `git diff --stat` confirms zero modified files anywhere in the repository.
11. **S00/S01 artifact contents unchanged**: confirmed — `git status --short` shows only new untracked S02 files; no existing file under `_analysis/` was opened with Write/Edit during this pass.
12. **`pass_behavior_trace`/`pass_discovery`/`pass_adversarial_verify` remain `NO` everywhere**: trivially satisfied — the ledger was not modified.
13. **Frozen upstream source unchanged**: confirmed via the full 2,016-object git-blob-SHA1 cross-check above — zero mismatches, zero missing objects.

**Overall self-check result: ALL CHECKS PASSED.**
