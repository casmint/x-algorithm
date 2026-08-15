# Coverage Framework Validation

Validation is against frozen baseline `2026-08-15_c65aa17`.

- **PASS** `baseline_manifest_count` — 2016
- **PASS** `baseline_manifest_unique` — 2016
- **PASS** `domain_map_exact_path_set` — domain=2016 manifest=2016
- **PASS** `specialist_map_exact_path_set` — pass=2016 manifest=2016
- **PASS** `coverage_ledger_exact_path_set` — ledger=2016 manifest=2016
- **PASS** `manual_classification_queue_empty` — 0
- **PASS** `domain_catalog_count` — 20
- **PASS** `all_files_have_domain`
- **PASS** `all_domain_ids_valid`
- **PASS** `all_assignment_confidence_high`
- **PASS** `all_files_have_review_treatment`
- **PASS** `primary_domain_partition_is_2016`
- **PASS** `all_files_have_specialist`
- **PASS** `all_specialist_ids_valid`
- **PASS** `component_catalog_covers_all_top_components`
- **PASS** `all_review_states_still_unreviewed`
- **PASS** `no_false_pass_completion`
- **PASS** `generated_get_boundary_treatment`
- **PASS** `symlink_get_reference_treatment`
- **PASS** `analysis_not_in_baseline`
- **PASS** `exactly_one_baseline_symlink`
- **PASS** `all_baseline_objects_present` — []
- **PASS** `all_baseline_sha256_match_snapshot` — []
- **PASS** `snapshot_tree_match_recorded` — True
- **PASS** `snapshot_upstream_tree_equals_reconstructed` — 1d4c89941bfcd2ea3aab7c780f7447342e304e42 vs 1d4c89941bfcd2ea3aab7c780f7447342e304e42
- **PASS** `snapshot_file_count_consistent`
- **PASS** `snapshot_symlink_count_consistent`
- **PASS** `snapshot_bytes_consistent`
- **PASS** `snapshot_text_count_consistent`
- **PASS** `snapshot_line_count_consistent`

Result: **ALL 30 CHECKS PASSED**. This validates snapshot/coverage bookkeeping only; it does not claim behavioral review has occurred.
