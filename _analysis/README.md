# X Algorithm Analysis

This directory is intentionally separate from upstream source.

## Frozen baseline

`2026-08-15_c65aa17` is the first evidence snapshot.

- **2,016 files**
- **379,995 approximate regular-text lines**
- supplied ZIP's reconstructed Git tree exactly matched upstream `main` commit `c65aa179db7bdd61e2c2821eac87f208a105c053`

See `snapshots/2026-08-15_c65aa17/README.md`.

## Coverage framework status

**Phase 1A — snapshot freeze: COMPLETE**  
**Phase 1B — architecture/domain coverage map: COMPLETE**  
**Deep behavioral review: NOT STARTED**

The current framework now contains:

- `coverage_ledger.csv` — all 2,016 files; review state remains `UNREVIEWED`.
- `domains/file_domain_map.csv` — every baseline file assigned to >=1 audit domain.
- `domains/component_map.csv` — component role/size/domain ownership.
- `domains/AUDIT_LENSES.md` — cross-cutting questions every specialist must check.
- `architecture/README.md` — documented end-to-end architecture hypotheses to verify.
- `architecture/CROSS_DOMAIN_SYSTEMS.md` — boundaries that require joint review.
- `passes/file_specialist_map.csv` — every baseline file assigned to >=1 specialist pass.
- `passes/README.md` — specialist, behavior-trace, discovery, and falsification sequence.
- `review/DEFINITION_OF_DONE.md` — exact meaning of file/domain/repository completion.
- `methodology/UPDATE_WORKFLOW.md` — how to handle future upstream changes without losing provenance.
- `tools/build_domain_map.py` and `tools/build_specialist_map.py` — reproducible coverage mapping.

## Important distinction

**Classified != reviewed.**

The mapping tells us who must inspect every file and which cross-component investigations must include it. It deliberately makes no claim that the implementation has already been understood or that the root README perfectly describes production behavior.

The next phase is specialist evidence extraction. No broad "what X's algorithm does" synthesis should be treated as final before the component and behavior-trace passes are complete.
