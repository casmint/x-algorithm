# Definition of Fully Reviewed

"A model looked at the folder" does **not** count as reviewed.

## File-level states

A baseline file progresses through:

`UNREVIEWED -> TRIAGED -> COMPONENT_REVIEWED -> CROSS_TRACED -> VERIFIED`

A file may instead carry a structural treatment such as generated/test/fixture/example, but it still remains represented in the coverage ledger.

### `COMPONENT_REVIEWED` requires

For normal production source:

- the file's role is stated in plain language;
- externally meaningful symbols/entry points are identified;
- callers/registration and downstream consumers relevant to behavior are traced;
- config/enable/reachability conditions are recorded;
- failure/fallback behavior is checked where applicable;
- important constants/labels/thresholds are extracted;
- tests/docs are used as supporting evidence, not substituted for code.

For generated code:

- generator/schema/provenance is identified;
- behavioral consumers are traced;
- hand-editing is not assumed;
- generated implementation is deeply read only when generation semantics themselves matter.

For tests/fixtures/examples:

- intended behavior or invariant demonstrated by the artifact is recorded;
- whether production code actually enforces that behavior is checked separately.

For docs/config/build files:

- claims/defaults/dependencies are extracted;
- contradictions with implementation are explicitly searched for.

### `CROSS_TRACED` requires

The file has been included in every applicable end-to-end behavior trace, not only its component-local review.

### `VERIFIED` requires

Any material conclusions depending on the file survived an independent adversarial review looking for:

- alternate call paths;
- runtime overrides;
- hidden/missing dependencies;
- stale/dead code;
- opposite conditions or exclusions;
- unit/normalization mistakes;
- comments/docs that differ from execution.

## Domain-level completion

A domain can be called **FULLY REVIEWED** only when:

1. 100% of its assigned baseline files have an appropriate review treatment completed.
2. All entry points and exits to other domains are enumerated.
3. Runtime controls/defaults/experiments are traced.
4. Important data models, labels, weights, thresholds, and state transitions are inventoried.
5. Failure/degraded/stale-data behavior is documented.
6. Applicable cross-cutting lenses have explicit answers or `UNKNOWN` entries.
7. At least one domain report and one independent adversarial report exist.
8. Every significant finding has evidence references and an evidence class.
9. Known omissions/internal dependencies are listed instead of guessed.
10. Coverage tooling reports zero unaccounted baseline files.

## Whole-repository completion

"Everything analyzed" requires **all domains complete plus all end-to-end behavior traces complete**. Component coverage alone is insufficient because many consequential behaviors emerge only at boundaries.
