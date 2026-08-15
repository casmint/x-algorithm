# S00 Run Log — Repository Documentation, Published Claims & Reproduction Boundary

## Remediation — independent audit response

This run log was updated after an independent audit of the original S00 pass identified four issues, all addressed on branch `analysis/s00-review` as a follow-up commit (not an amendment of the original S00 commit). Summary of each issue and its resolution; full detail in the dedicated subsections below and in the specialist report's "Remediation note" / "Composite-claim discipline" sections.

1. **False negative-search statement in S00-F013.** The original finding claimed a repository-wide search for "cron" returned only the README's own sentence. This was false: five `cron = "0 * * * *"` Bazel job definitions exist in `agatha/scalding/{data,labels/nsfw,labels/rate_based_labels,labels/spam_suspended,quantile}/BUILD.bazel`. A corrected, multi-term search was re-run (see "Corrected cron/configuration-sync search" below) and additionally surfaced a materially relevant piece of evidence the original search missed entirely: `home-mixer/params/param.rs:L1` and two `abuse-enforcement-service` rule YAML files carry self-reported "mirrored from ...; last sync ..." header comments. S00-F013 and S00-C023 were rewritten; the corrected conclusion keeps the production-sync *mechanism* `UNKNOWN` while upgrading the *marker-of-mirroring* sub-claim to `CONFIRMED`/`DIRECT`.
2. **Insufficient baseline self-check.** Self-check #13 in the original run originally described only a 4-file spot-check rather than the required all-2,016-object verification. A full, non-sampled re-verification was performed using three independent methods (see "Full 2,016-object baseline verification" below). Result: **zero mismatches, zero missing objects** across all methods.
3. **Composite-claim overclaims in `S00_claim_matrix.csv`.** All 42 original rows were re-audited against a strict discipline rule (no row may be `CONFIRMED`/`DIRECT` merely because one part is verified). 12 rows were narrowed/split, producing 15 new atomic rows (`S00-C043`–`S00-C057`); final matrix has 57 rows. Full detail in the specialist report's "Composite-claim discipline" section.
4. **Under-cited S00-F007 evidence chain.** The full hop-by-hop chain from `BidirectionalFollowHydrator` through `PredictionDispatch::predict_with_fallback` was traced and cited with exact paths/line ranges/symbols, and the DIRECT-vs-not-yet-DIRECT boundary (request construction vs. trained-model behavioral impact) was made explicit. See "Strengthened S00-F007 evidence chain" below.

No upstream source file was modified for this remediation. No file outside `_analysis/` was touched. `pass_behavior_trace`, `pass_discovery`, and `pass_adversarial_verify` were not changed. S01 was not started.

## Snapshot

- Snapshot ID: `2026-08-15_c65aa17`
- Upstream commit: `c65aa179db7bdd61e2c2821eac87f208a105c053`
- Upstream Git tree: `1d4c89941bfcd2ea3aab7c780f7447342e304e42`

## Workspace state

**Initial `git status --short`** (run before any `_analysis/` modification): empty output — no uncommitted changes, no untracked files at session start. (The `_analysis/` directory itself was already committed/present as tracked content prior to this session, per the conversation's initial `gitStatus` context showing only `?? _analysis/` at the very start of the broader session; by the time S00's own `git status --short` was run, the working tree was clean.)

**Initial `python3 _analysis/tools/validate_coverage.py` result**:

```
ALL 30 COVERAGE VALIDATION CHECKS PASSED
EXIT_CODE=0
```

Run *before* any coverage-ledger edits, per the pass instructions' validator caveat (Section 25). All 30 bootstrap checks passed, including `all_baseline_sha256_match_snapshot` and `snapshot_upstream_tree_equals_reconstructed` (tree `1d4c89941bfcd2ea3aab7c780f7447342e304e42` matched on both sides) — confirming the frozen upstream objects still match the recorded snapshot before review began.

## Assignment

**Expected S00 files** (per task specification):
```
CODE_OF_CONDUCT.md
LICENSE
README.md
docs/BIDIRECTIONAL_BOOST_CHANGE.md
```

**Actual S00 files** (grepped from `_analysis/passes/file_specialist_map.csv` before any review):
```
CODE_OF_CONDUCT.md,[root],S00,S00,DOC_CONTEXT_VERIFY_AGAINST_CODE,D00
LICENSE,[root],S00,S00,FULL_SOURCE_REVIEW,D00
README.md,[root],S00,S00,DOC_CONTEXT_VERIFY_AGAINST_CODE,D00
docs/BIDIRECTIONAL_BOOST_CHANGE.md,docs,S00;S17,S00,DOC_CONTEXT_VERIFY_AGAINST_CODE,D00;D05;D17
```

Match: **exact**, 4/4. `docs/BIDIRECTIONAL_BOOST_CHANGE.md` carries a secondary specialist tag (`S17`) but its `primary_specialist` is `S00`, and S00 owns first review per the task's explicit assignment; the S17 co-tag is a downstream obligation (config/experiments census), not a reason to withhold S00 review here. No mapping discrepancy found; nothing to report as a framework error.

Cross-checked against `_analysis/domains/file_domain_map.csv` (all 4 rows: `primary_domain=D00`, `docs/BIDIRECTIONAL_BOOST_CHANGE.md` additionally `secondary_domains=D05;D17`) and `_analysis/coverage_ledger.csv` (all 4 rows `review_status=UNREVIEWED`, `pass_component_audit=NO` at session start) — consistent with the specialist map.

## Examination accounting

- **S00-assigned files**: 4 assigned, 4 examined in full (read completely, not sampled).
- **Supporting cross-domain files examined** (existence/content checks that do NOT change their coverage-ledger state): approximately 45 distinct repository paths, spanning `home-mixer/` (params, scorers, filters, candidate_hydrators, candidate_pipeline, models, selectors, ads), `candidate-pipeline/` (filter.rs trait definition), `visibility-filtering/` (rules/registry.rs), `vm-ranker/` (scoring/dpp_model.rs), `phoenix-rankall-strato/` (lib/eventProcessing.strato), `phoenix/` (NOTICE, Cargo.toml, pyproject.toml, QUICKSTART.md, xrex model/attention/embedding file existence), `grox/` (flows/*/prompts.py, directory structure, absence of `.j2` files), `abuse-enforcement-service/` (growthbook.rs, growthbook_writer.rs), `botmaker-rules/` (directory structure), `under-the-hood/` (directory structure), plus a directory-existence check for all 24 top-level components named in the README's Components section. Full itemization is in `_analysis/review/S00_file_review.csv`'s `supporting_files_examined` column.
- **Files deferred**: none among the 4 assigned files. All 4 reached `COMPONENT_REVIEWED`.
- **Reason for zero deferrals**: all four files are documentation/license artifacts short enough to read in full within this pass, and every symbol/path they name was independently locatable in the snapshot (existence-checkable), satisfying `DEFINITION_OF_DONE.md`'s docs/config/build-file criteria ("claims/defaults/dependencies are extracted; contradictions with implementation are explicitly searched for").

## Searches / commands

Representative commands used (not exhaustive; illustrative of method):

- `git status --short`, `python3 _analysis/tools/validate_coverage.py` (pre-review, Section 3).
- `grep -n ",S00," _analysis/passes/file_specialist_map.csv`, matching greps against `file_domain_map.csv` and `coverage_ledger.csv` to confirm assignment.
- Full `Read` of `README.md`, `CODE_OF_CONDUCT.md`, `LICENSE`, `docs/BIDIRECTIONAL_BOOST_CHANGE.md`.
- Existence/wiring checks for named symbols: `bidirectional_follow_hydrator.rs`, `brazil_2026_election_filter.rs`, and their registration in `mod.rs`/`phoenix_candidate_pipeline.rs`, via targeted `grep -n`.
- `for d in <24 component names>; do [ -d "$d" ] ...; done` to confirm every Components-table directory exists.
- Repository-wide `grep -rn "GrowthBook"` and `grep -rln "cron"` to establish the runtime-config and cron-sync evidence base (the latter returning only `README.md` itself).
- `find grox -iname "*.j2"` / `find grox -iname "templates" -type d` (both empty) to test the Grox-prompt-omission claim, followed by reading `grox/flows/upa/prompts.py` directly.
- `find . -iname "LICENSE*"` / `find . -iname "NOTICE*"` repository-wide, followed by full read of `phoenix/NOTICE`.
- Direct reads of `home-mixer/scorers/ranking_scorer.rs` (bidirectional boost logic, `ScoringWeights` struct), `home-mixer/params/param.rs` (all bidirectional-follow params, `ReportWeight`/`FavoriteWeight`, `EnableAllAuthorFollowHydration`, `MAX_POST_AGE`), `home-mixer/candidate_hydrators/bidirectional_follow_hydrator.rs` (full file, compared line-by-line against the doc's reproduced diff), `home-mixer/models/candidate.rs` (`author_follows_viewer` → `AuthorInfo.is_following_user` mapping), `home-mixer/filters/brazil_2026_election_filter.rs` (full exclusion logic), `candidate-pipeline/filter.rs` (`Filter::enable` trait default), `home-mixer/filters/inventory_holdout_filter.rs` (deterministic hash bucket logic), `phoenix-rankall-strato/lib/eventProcessing.strato` (VF consultation + decider gate).
- No broad/unscoped internet research performed; no external URLs fetched.

## Corrected cron/configuration-sync search (remediation, Issue 1)

The original search (`grep -rln "cron"` with implicit file-type filtering) missed real hits. It was redone as an unfiltered, case-insensitive, repository-wide search, followed by a broadened multi-term sweep as directed by the remediation instructions:

```
grep -rniIl "cron" . | grep -v "^./_analysis"
```
→ 5 files: `agatha/scalding/data/BUILD.bazel`, `agatha/scalding/labels/nsfw/BUILD.bazel`, `agatha/scalding/labels/rate_based_labels/BUILD.bazel`, `agatha/scalding/labels/spam_suspended/BUILD.bazel`, `agatha/scalding/quantile/BUILD.bazel` — each an hourly (`cron = "0 * * * *"`) `scalding_job` Bazel target owned by `agatha-owners@twitter.com`, depending on Agatha's own feature/label-extraction jobs (`active_user_features_job`, `nsfw`, etc.). **These are Agatha's own offline batch-labeling jobs and are structurally unrelated to home-mixer parameter syncing** — confirmed by reading each `BUILD.bazel` target's `dependencies` field, all of which point at other Agatha Scalding jobs, not at anything in `home-mixer/`.

Further terms searched, each repository-wide (excluding `_analysis/`):

- `scheduled` / `schedule` — many hits, overwhelmingly Scala/Python scheduling-framework code in `agatha/`, `botmaker/`, `grox/`, `simclusters/`, `under-the-hood/`, `phoenix/` unrelated to config-to-source sync; notably `under-the-hood/scalding/UthDailyAccountLabelsJob.scala` and `UthDailyPostsJob.scala` (used for S00-C049).
- `synchron` — hits limited to Botmaker/CUDA/data-loader code using "synchronize" in its ordinary (non-config) sense; no relevant hits.
- `mirrored` (broadened from `sync`) — **this located the key evidence**: `home-mixer/params/param.rs:L1` (`// mirrored from config feature-switch defaults; last sync 2026-08-12T04:09:22Z`), `abuse-enforcement-service/service-lib/rules/enforcement_post.yaml:L1` (`# mirrored from GrowthBook dynamic config; last sync 2026-08-06T16:20:00Z`), `abuse-enforcement-service/service-lib/rules/enforcement_user.yaml:L1` (`# mirrored from GrowthBook dynamic config; last sync 2026-08-12T16:22:21Z`). A further `grep -rniIE "sync[^a-z].{0,40}202[0-9]-[0-9]{2}-[0-9]{2}"` confirmed these are the only three "...; last sync <timestamp>" artifacts repository-wide.
- `xai_feature_switches` (repo-wide, not just `home-mixer/`) — confirms usage is concentrated in `home-mixer/` (18 files) plus one reference in `candidate-pipeline/candidate_pipeline.rs`; no hits elsewhere that would suggest a different/additional sync path.
- `primary production` / `production value` — only the README sentence itself, plus an unrelated `bdsm/runtime/sink_policy.yaml` comment ("The production values are configured internally and are not part of...") which explicitly self-discloses as out of scope for this repo and was not treated as evidence either way.
- `param.rs` (as a literal string, repo-wide) — only self-references (README, `_analysis/`, `docs/BIDIRECTIONAL_BOOST_CHANGE.md`); no external script/tool references `param.rs` by name.
- `"do not edit"` / `"auto-generated"` / `"generated by"` / `"codegen"` within `home-mixer/` — no hits; the `param.rs:L1` header is the only generation/sync marker on that file.
- CI/workflow-file search (`*.yml`/`*.yaml` filenames matching `cron|sync|workflow|ci|schedule`) — only `media-model-proxy/config/decider.yml` and its test-fixture symlink target, both decider config files unrelated to a build/sync pipeline.

**Conclusion (supersedes the original S00-F013):** the snapshot contains 5 scheduled/cron jobs, all in Agatha, all unrelated to home-mixer parameter defaults. Separately, `home-mixer/params/param.rs` and two `abuse-enforcement-service` rule files carry self-reported config-mirroring headers with specific "last sync" timestamps — real, direct evidence of *a* sync marker, though not of the mechanism's implementation, its cron status, or its exact equivalence to "primary production values." See `S00_claim_matrix.csv` rows `S00-C023`, `S00-C053`, `S00-C054`, `S00-C055` and `S00_findings.jsonl`'s corrected `S00-F013`.

## Full 2,016-object baseline verification (remediation, Issue 2)

Three independent, non-sampling methods were run against every one of the 2,016 baseline objects in `_analysis/snapshots/2026-08-15_c65aa17/file_manifest.csv`, all read-only:

**Method 1 — full git-history diff.** `git diff --name-status c65aa179db7bdd61e2c2821eac87f208a105c053 HEAD` (branch `analysis/s00-review`, which descends from the upstream commit via one intermediate baseline commit and the original S00 commit) returned 37 changed paths; **all 37 are under `_analysis/`** (`grep -v "^[AMD]\t_analysis/"` on the output was empty). This proves, using git's own object-level history, that zero non-`_analysis/` paths were touched anywhere in this repository's history since the upstream snapshot commit.

**Method 2 — git tree identity.** `git rev-parse c65aa179db7bdd61e2c2821eac87f208a105c053^{tree}` returns `1d4c89941bfcd2ea3aab7c780f7447342e304e42` — an **exact match** to the recorded upstream tree, computed directly from this repository's own git object database (stronger than the original snapshot-freeze method, which reconstructed the tree from a `.git`-less ZIP extraction via a temporary index).

**Method 3 — manual SHA-256 verification against the manifest.** A fresh Python script read all 2,016 rows of `file_manifest.csv`, and for each row: checked the path exists on disk (`os.path.lexists`, symlink-aware), computed SHA-256 of the object bytes (symlink target bytes for the one recorded symlink, file bytes otherwise — same method as `_analysis/tools/validate_coverage.py`'s `object_bytes()`, independently reimplemented rather than importing that module), and compared to the manifest's recorded `sha256`. Result:

```
Manifest row count: 2016
Checked: 2016
Missing: 0 []
Mismatches: 0 []
Symlinks in manifest: 1
RESULT: ALL 2016 BASELINE OBJECTS MATCH
```

**Method 4 — git blob SHA1 cross-check.** `git ls-tree -r c65aa179db7bdd61e2c2821eac87f208a105c053` was parsed into a `{path: blob_sha1}` map (2,016 entries) and cross-checked against the manifest's `git_blob_sha1` column: 0 manifest entries missing from the git tree, 0 `git_blob_sha1` mismatches, 0 git-tree entries absent from the manifest (i.e. the sets are identical, not just non-contradictory).

**Result: all four methods agree — the full 2,016-object baseline is unchanged and matches the recorded snapshot exactly. No mismatch was found; this section does not trigger the "STOP and report" condition.**

## Strengthened S00-F007 evidence chain (remediation, Issue 4)

The full hop-by-hop chain requested by the remediation instructions was traced and cited with exact paths, line ranges, and symbols (now recorded in both `S00_findings.jsonl`'s `S00-F007` and the specialist report's "Bidirectional-follow change document audit" section):

`BidirectionalFollowHydrator` (sets `PostCandidate.author_follows_viewer`, `home-mixer/models/candidate.rs:L61`) → `CandidateHelpers::as_tweet_info` (`candidate.rs:L121-L126` trait decl, `L129`/`L167-L213` impl, reads the field at `L202-L210`) → `xai_recsys_proto::AuthorInfo.is_following_user` (published proto field, `phoenix/crates/serving/xai-recsys-proto/proto/recsys.proto:L1098-L1103`) → `home-mixer/util/phoenix_request.rs`'s `candidate_to_tweet_info` (`L98-L106`) / `build_tweet_infos` (`L108-L118`) / `build_prediction_request` (`L141-L151`) → `PredictNextActionsRequest` → `home-mixer/scorers/phoenix_scorer.rs`'s `PhoenixScorer::score` (`L76-L97`) → `PredictionDispatch::predict_with_fallback` (called at `phoenix_scorer.rs:L94-L96`; declared/re-exported only, not defined, at `home-mixer/util/egress.rs:L1-L2` — the actual implementation lives in the external `xai_candidate_pipeline::component_library::egress` module, not part of this snapshot). Additionally, `phoenix/crates/common/xai-recsys/src/util.rs`'s `impl InputBuffer::new_with_candidates` (`L340-L341`, reads the field at `L517-L521`) and `impl InputBuffer::compute_for_item` (`L675`, reads it at `L861-L865`) show the field being extracted into per-candidate and per-history feature arrays — evidence (not yet proof of trained-model behavioral impact) that it is wired as a model input feature.

The finding's `status`/`evidence_class` remain `CONFIRMED`/`DIRECT` for the precise, bounded claim ("the signal is placed into the candidate TweetInfo included in the Phoenix prediction request and that request is sent through PhoenixScorer's prediction dispatch") and explicitly do **not** extend to a `DIRECT` claim about the trained model's actual use of the feature, which remains an S05/S06 obligation.

## Claim-matrix composite-discipline re-audit (remediation, Issue 3)

All 42 original rows in `S00_claim_matrix.csv` were re-read against the rule: *a composite claim may not be `CONFIRMED`/`DIRECT` merely because one part is directly verified; split or downgrade to the weakest evidence/status the material sub-claims require.* The 11 rows the audit explicitly named (`S00-C006`, `S00-C008`, `S00-C010`, `S00-C011`, `S00-C013`, `S00-C015`, `S00-C017`, `S00-C021`, `S00-C025`, `S00-C027`, `S00-C032`) were reviewed, plus all remaining 31 rows for the same pattern. One additional violation was found beyond the named list (`S00-C036`, which bundled a confirmed-true sub-claim with a since-superseded historical value). Disposition:

- **Split (12 rows → 15 new atomic rows, `S00-C043`–`S00-C057`):** each split kept the well-evidenced part (existence/structure, `CONFIRMED`/`DIRECT`, narrowed wording) under the original ID, and moved the unverified/behavioral/historical/forward-looking part to a new ID with an independently appropriate status. `S00-C011` is both narrowed in place (kept `PARTIALLY_CONFIRMED`/`STRONG_INFERENCE`, since the Enable*-switch pattern genuinely exists but is not universal) **and** split off a `CONTRADICTED` sub-claim (`S00-C046`): the README's unqualified "stages can be switched on/off individually" is directly falsified by `Brazil2026ElectionFilter`, which has no local param gate at all.
- **Confirmed already compliant (no change):** the remaining 30 rows were checked and found to already either (a) carry a genuinely single, atomic, fully-verified claim, or (b) already reflect rule B ("downgrade to the weakest required classification") rather than falsely claiming `CONFIRMED`/`DIRECT` — e.g. `S00-C018`, `S00-C031`, `S00-C035` were already `PARTIALLY_CONFIRMED`/`STRONG_INFERENCE` with their DIRECT-confirmed sub-parts noted as such, not overclaimed at the row level.

Final result: 57 rows, 0 rows classified `CONFIRMED`/`DIRECT` while their own notes admit an unverified material portion (verified programmatically, see final self-check below).

## Artifacts written

- `_analysis/reports/specialists/S00_repository_docs_build_repro.md` (created in original pass; revised in remediation — cron/sync section, F007 evidence chain, composite-claim discipline section, updated counts throughout)
- `_analysis/evidence/S00_claim_matrix.csv` (created in original pass at 42 rows; remediated to 57 rows, `S00-C001`–`S00-C057` — 12 rows narrowed in place, 15 new rows added, 0 removed)
- `_analysis/evidence/S00_findings.jsonl` (created in original pass at 13 lines; remediated — `S00-F007` and `S00-F013` substantively rewritten in place, still 13 lines, `S00-F001`–`S00-F013`, all IDs unchanged)
- `_analysis/review/S00_file_review.csv` (created in original pass — 4 rows, one per S00-assigned file; unchanged in remediation, no edit needed since it already correctly hedged claims)
- `_analysis/review/S00_run.md` (this file — remediation sections added)
- `_analysis/coverage_ledger.csv` (modified in original pass and again in remediation — exactly the 4 S00-assigned rows updated in each case; see below)

No other file under `_analysis/` was created or modified. No file outside `_analysis/` was modified at any point, including during remediation.

## Unresolved questions

Carried forward as `downstream_passes` in the claim matrix and findings; summarized here by owner:

- **S01/S02**: `Brazil2026ElectionFilter` vs. README table omission; the 6 unlisted filter modules in `home-mixer/filters/mod.rs`; `BidirectionalFollowHydrator`'s framework-level error-handling semantics.
- **S05/S06**: `author_follows_viewer` as an undocumented Phoenix model input feature; candidate-isolation (no cross-attention) and hash-based embedding Key Design Decision claims not independently re-derived; `phoenix/NOTICE` third-party licensing scope.
- **S07/S14**: `phoenix-rankall-strato`'s decider-gated visibility-filtering consultation — gate value not established.
- **S17**: the sync mechanism's own implementation (script/job/trigger) behind the "mirrored from ...; last sync ..." headers on `param.rs` and the two `abuse-enforcement-service` rule files was not found published; whether it is cron-based and whether it represents "primary production values" remain `UNKNOWN` (S00-C053/S00-C054/S00-C055, corrected S00-F013). Two distinct, independently-confirmed runtime-override mechanisms (`xai_feature_switches` in home-mixer, GrowthBook in abuse-enforcement-service) should inform how every specialist treats "checked-in default."
- **S18**: whether `phoenix/QUICKSTART.md` actually succeeds end-to-end was not executed in S00.
- **B09/B12**: all specific dates, percentages, and per-user value assignments in the bidirectional-follow A/B-test narrative, and the Brazil2026Election filter's actual production-activation status, remain unverifiable from the published snapshot alone.

## Self-check result (post-remediation)

Re-run after all remediation edits, superseding the original pass's self-check. Section-numbered per the task's original Section 26 checklist, plus the remediation's 10-point consistency audit:

1. **Exactly four S00-assigned paths in `file_specialist_map.csv`**: confirmed via `grep -c ",S00," _analysis/passes/file_specialist_map.csv` → `4`. Unchanged by remediation (specialist map was not touched).
2. **`S00_file_review.csv` contains exactly those four unique paths**: confirmed — 4 data rows, paths match exactly, no duplicates. Unchanged by remediation (only cell text updated, no rows added/removed).
3. **No baseline source file outside `_analysis/` was modified**: confirmed via `git status --short` and full 2,016-object baseline verification (see above) — zero non-`_analysis/` changes across all four independent methods.
4. **No non-S00 coverage-ledger row changed**: confirmed via `git diff` on `_analysis/coverage_ledger.csv` (cumulative, original commit + remediation) — only the same 4 S00 rows appear in the diff.
5. **All S00 JSONL lines parse as valid JSON**: confirmed via Python `json.loads` over every line — 13/13 parsed, no errors, after the `S00-F007`/`S00-F013` rewrite.
6. **All claim-matrix IDs unique**: confirmed via Python CSV read + set-membership check — **57/57 unique**, `S00-C001`–`S00-C057` (up from 42 after remediation; no gaps, no duplicates — the renumbering bug encountered mid-remediation, where a buggy chained-substitution script produced a duplicate `S00-C050`, was caught by this exact check, and the claim matrix was restored from the prior commit and rebuilt correctly before proceeding).
7. **All finding IDs unique**: confirmed — 13/13 unique, `S00-F001`–`S00-F013` (unchanged count; two findings' content substantively revised).
8. **All evidence classes use the allowed enum**: confirmed for both the claim matrix (57/57 rows) and findings file (13/13 lines) (`DIRECT`/`STRONG_INFERENCE`/`POSSIBLE`/`UNKNOWN` only).
9. **All verification statuses use the allowed enum**: confirmed for both files (`CONFIRMED`/`PARTIALLY_CONFIRMED`/`CONTRADICTED`/`DEFERRED`/`UNKNOWN` only).
10. **Every material finding contains at least one source evidence reference**: confirmed — all 13 findings have a non-empty `source_evidence` array, including the rewritten `S00-F007`/`S00-F013`.
11. **Every `COMPONENT_REVIEWED` S00 ledger row has `pass_component_audit=YES`, correct upstream commit, and a corresponding file-review record**: confirmed for all 4 rows (unchanged from original pass).
12. **`pass_behavior_trace`, `pass_discovery`, `pass_adversarial_verify` remain `NO` for every baseline file**: confirmed — remediation did not set any of these fields to `YES` for any row.
13. **Full 2,016-object baseline integrity**: confirmed via all four independent methods described above (git-history diff, git tree identity, manual SHA-256, git blob SHA1 cross-check) — zero mismatches, zero missing objects, not sampled.
14. **`git diff --check` (CRLF-aware, per the repository's established convention)** passes on the remediation changes: `git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --check` reports no errors.
15. **`git status --short` shows only intended `_analysis/` changes**: confirmed.
16. **No claim marked `CONFIRMED`/`DIRECT` while its own notes admit a material unverified portion**: checked programmatically with a keyword scan (`not verified`, `did not trace`, `did not read`, `deferred to`, `not established`, etc.) over every `CONFIRMED`/`DIRECT` row's `notes` field. The scan flagged 3 rows (`S00-C006`, `S00-C015`, `S00-C021`) as containing such language; manual review of all 3 confirmed the flagged phrase in each case describes a *different*, explicitly cross-referenced split-off claim ID (`S00-C043`, `S00-C048`, `S00-C051`/`S00-C052` respectively) — not an unverified portion of the row's own narrowed claim text. No row was found to genuinely violate the rule.
17. **Every finding's evidence chain supports the wording of its claim**: confirmed by re-reading `S00-F007` and `S00-F013` against their `verification_evidence` arrays — the DIRECT/not-yet-DIRECT boundary in `S00-F007` and the marker-exists-vs-mechanism-unknown boundary in `S00-F013` are both explicit in the `claim`, `evidence_class`, and `notes` fields together, not just implied by significance.

Note on the bootstrap validator: `_analysis/tools/validate_coverage.py` was run once, before any ledger edit (Section 2, Workspace state above), and passed all 30 checks including `all_review_states_still_unreviewed` and `no_false_pass_completion`. Per Section 25 of the task instructions, this validator is expected to now report a different result on `all_review_states_still_unreviewed` if re-run after this session's ledger update, because that check is a Phase-1 bootstrap assertion, not a progress-aware validator. It was intentionally **not** re-run after the ledger update, and the validator itself was not modified.
