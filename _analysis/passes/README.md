# Specialist Pass Plan

These are **independent first-pass specialists**. Their job is evidence extraction and local understanding, not grand conclusions. Cross-component behavior is handled afterward.

| Pass | Scope | Main components |
|---|---|---|
| S00 | Snapshot, docs, build/repro boundaries | root, `docs/`, repo-wide build metadata |
| S01 | Candidate framework + Home Mixer orchestration | `candidate-pipeline/`, Home Mixer core/hydration/clients/pipelines |
| S02 | Home feed filters, selection, blending, ads | Home Mixer filters/selectors/ads/frames/side effects |
| S03 | In-network retrieval | `thunder/` + Home Mixer Thunder source integration |
| S04 | SimClusters OON retrieval | `simclusters/` + integration call sites |
| S05 | Phoenix ranking/retrieval semantics | Phoenix model/features/retrieval/ranking + Home Mixer Phoenix scoring/weights |
| S06 | Phoenix training, inference & serving infrastructure | Phoenix xrex training/eval/inference, Rust serving, data/artifacts |
| S07 | Retrieval index & admission | `phoenix-rankall/`, `phoenix-rankall-strato/` |
| S08 | Diversity / reranking | `vm-ranker/` + related Home Mixer selectors/scorers |
| S09 | Grox content understanding | `grox/` |
| S10 | Media understanding | `media-model-proxy/`, `clip/`, `adult-content/`, `pnsfwmedia/` |
| S11 | Account signals / reputation | `agatha/`, `bdsm/`, `user-cred-v2/` |
| S12 | Botmaker compiler/runtime | `botmaker/` |
| S13 | Label rules and aggregation | `botmaker-rules/`, `scarecrow/`, `safety-label-user-agg/` |
| S14 | Visibility policy | `visibility-filtering/`, `visibility-filtering-client/` + VF integration call sites |
| S15 | Abuse enforcement | `abuse-enforcement-service/` |
| S16 | Transparency reporting | `under-the-hood/` |
| S17 | Config/defaults/experiments/constants census | cross-repo files tagged D17/config + behavioral call sites |
| S18 | Ops/repro/failure/observability census | cross-repo D18/D19 plus service/storage/fallback boundaries |

`file_specialist_map.csv` assigns every baseline file to one or more specialist passes. Specialists must not mark secondary-domain work complete; they only fill their assigned local review.

## Second wave: behavior traces

After component specialists finish, fresh agents trace behavior end-to-end without relying on component reports as truth:

- **B01 Candidate entrance:** every way a post can enter the For You candidate set.
- **B02 Candidate exclusion:** every way it can be removed before scoring, after scoring, after selection, or before indexing.
- **B03 Score pressure:** every factor that can raise/lower ordering, including model outputs, multipliers, boosts, penalties, and rerankers.
- **B04 Label lifecycle:** creation -> storage -> aggregation -> expiry/removal -> visibility/enforcement/transparency.
- **B05 Account reputation:** behavior/graph inputs -> account scores/labels -> downstream consequences.
- **B06 New user/new author:** cold-start paths, exploration, dedicated models, thresholds.
- **B07 In-network vs OON:** retrieval, filtering, scoring, diversity, and source asymmetries.
- **B08 Negative feedback:** prediction, direct user controls, reports/blocks/mutes, reputation effects, anti-coordination assumptions.
- **B09 Legal/geo/special cases:** all jurisdiction/country/election/language/product-specific behavior.
- **B10 Failure/degraded modes:** missing services, timeouts, cache staleness, retries, fallback and fail-open/closed behavior.
- **B11 Monetization/access:** ads, subscriptions, premium/verification/access gating, non-organic insertion.
- **B12 Public-vs-production boundary:** every unpublished runtime dependency needed to know actual production behavior.

## Third wave: discovery and falsification

Only after S- and B-passes:

1. Discovery agents search for non-obvious interactions, contradictions, bugs, dormant systems, and surprising special cases.
2. Independent adversarial agents try to falsify each significant finding.
3. Synthesis may then produce a human-readable report.

This order prevents a compelling early theory from steering the entire repository review.
