# Audit Methodology

The goal is coverage, not a fast narrative.

## Invariants

1. **Freeze the upstream evidence.** Every finding names the upstream commit it was verified against.
2. **Do not edit upstream source for analysis.** Analysis artifacts live under `_analysis/`.
3. **Establish a denominator.** `coverage_ledger.csv` contains every file in the snapshot. Files are not considered reviewed merely because a model read neighboring files.
4. **Separate passes.**
   - component audit: understand each component on its own
   - behavioral trace: follow end-to-end behavior across component boundaries
   - discovery: hunt for non-obvious interactions, oddities, bugs, special cases, and transparency gaps
   - adversarial verification: try to falsify every important finding
5. **Cite evidence precisely.** Findings should name file paths, symbols, and line ranges where stable.
6. **Distinguish code from production reality.** Runtime configuration, internal services, omitted rules/prompts, experiments, and deployment state can make a checked-in code path differ from production behavior.
7. **Do not promote speculation.** Use the evidence classes below.

## Evidence classes

- `DIRECT` — follows directly from published code/config at this snapshot.
- `STRONG_INFERENCE` — multiple code paths support it, but an unpublished/runtime detail could change the conclusion.
- `POSSIBLE` — plausible interpretation; evidence is incomplete.
- `UNKNOWN` — the published snapshot cannot answer it.

## High-significance finding gate

A significant finding should not be treated as final until:
- its exact source path/symbol has been traced;
- enabling/reachability conditions are checked;
- runtime overrides and missing dependencies are considered;
- an independent adversarial pass has attempted to disprove it.

## Update rule

When upstream changes, do not rerun the whole project blindly.

1. Record the new upstream commit/tree.
2. Diff old snapshot -> new snapshot.
3. Map changed files/symbols to findings and behavior traces.
4. Mark affected findings `STALE_PENDING_REVIEW`.
5. Audit newly introduced files/components.
6. Re-verify affected conclusions.

## Current phase

Snapshot freeze and coverage-map construction are complete. All baseline files remain `UNREVIEWED`; domain assignment is triage/ownership only. Specialist passes are the next phase.
