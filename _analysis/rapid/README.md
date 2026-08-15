# Rapid Understanding Track

This directory holds the **expedited human-understanding track**, run in parallel with
(not in place of) the forensic S00–S18 ledger under `_analysis/`.

- **Goal**: produce an accurate, human-readable explanation of how `xai-org/x-algorithm`
  actually behaves, fast — not to re-derive per-file coverage-ledger completion.
- **Basis**: frozen upstream source `c65aa179db7bdd61e2c2821eac87f208a105c053`
  (tree `1d4c89941bfcd2ea3aab7c780f7447342e304e42`), the same snapshot S00–S02 audited.
- **Prior authority**: `_analysis/review`, `_analysis/reports/specialists`, and
  `_analysis/evidence` (S00–S02) remain the authoritative forensic record. Reports here
  build on that context and do not re-verify it.
- **Method**: trace real executable behavior and call chains — entry points, storage/index
  logic, integration points — rather than reviewing every file. Use searches/scripts to
  characterize large repetitive areas instead of reading them line by line.
- **What this is not**: reports in `_analysis/rapid/` do **not** mark any forensic pass
  (S03, S04, S07, …) complete, do not update `coverage_ledger.csv` or
  `file_specialist_map.csv`, and do not imply the per-file review discipline used
  elsewhere in `_analysis/` was applied here.
- **Evidence discipline**: every material claim still carries a source citation
  (path + symbol/line range) and an uncertainty class — DIRECT / STRONG_INFERENCE /
  POSSIBLE / UNKNOWN — consistent with the rest of `_analysis/`.

## Contents

- [`01_retrieval.md`](01_retrieval.md) — how a post can become a candidate before
  Phoenix scoring (Thunder, SimClusters, Phoenix retrieval/rankall admission, and the
  other wired candidate sources).
