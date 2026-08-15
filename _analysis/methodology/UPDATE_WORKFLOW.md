# Upstream Update Workflow

The analysis fork should remain syncable with `xai-org/x-algorithm` while `_analysis/` stays fork-specific.

For each upstream update:

1. Fetch/sync upstream into the fork.
2. Record the new upstream commit and Git tree **before analysis**.
3. Generate a new file manifest and diff it against `2026-08-15_c65aa17`.
4. Categorize paths as `ADDED`, `REMOVED`, `MODIFIED`, or unchanged.
5. Run domain classification on new/changed paths. Any new top-level component or unexpected path pattern is a hard manual-review item, not silently ignored.
6. Map changed files to specialist passes, behavior traces, and existing findings/evidence references.
7. Mark affected conclusions `STALE_PENDING_REVIEW`.
8. Review additions and changed code; re-run affected cross-domain traces.
9. Re-run adversarial verification on any conclusion whose evidence changed.
10. Only then advance the analysis baseline.

Do **not** replace the old snapshot. Historical findings must remain tied to the exact commit they described.
