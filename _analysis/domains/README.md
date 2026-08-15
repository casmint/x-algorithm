# Audit Domain Map

This is the **coverage model**, not a set of conclusions about X.

Every one of the 2,016 files in snapshot `2026-08-15_c65aa17` is assigned to at least one audit domain in `file_domain_map.csv`. Cross-domain assignment is intentional: a file can belong to several investigations when its behavior crosses boundaries.

## Domain catalog

| ID | Domain | Core question |
|---|---|---|
| D00 | Repository metadata & explanatory docs | What does the published repository claim about itself? |
| D01 | Request pipeline & orchestration | How is a For You request assembled and executed? |
| D02 | In-network retrieval | How do followed-account posts enter the candidate pool? |
| D03 | Out-of-network retrieval | How are posts from outside the follow graph discovered? |
| D04 | Retrieval index & admission | What enters the retrieval index, and how is it maintained? |
| D05 | Ranking & score construction | How are model outputs converted into ordering pressure? |
| D06 | Selection, reranking & diversity | How does the ranked set become a slate? |
| D07 | Feed eligibility & non-VF filtering | What request-path rules remove or gate posts outside central VF policy? |
| D08 | Blending, ads & non-post insertion | What gets inserted/reordered outside organic post ranking? |
| D09 | Content & media understanding | What models/signals describe post text, images, video, spam, adult content, etc.? |
| D10 | Account behavior, credibility & reputation signals | What account-level behavior/graph signals are produced? |
| D11 | Label production, rules & aggregation | How are safety/policy labels generated and propagated? |
| D12 | Visibility policy & safety filtering | How do labels/context become ALLOW, INTERSTITIAL, DROP, or related outcomes? |
| D13 | Abuse enforcement & account actions | How do model scores/rules become labels, challenges, suspensions, or other enforcement? |
| D14 | Transparency & user-facing reporting | How does Under the Hood collect and expose label history? |
| D15 | Model training, evaluation & artifact production | How are published models trained/evaluated/packaged? |
| D16 | Data models, storage & service integration | What schemas, stores, caches, clients, and service plumbing connect domains? |
| D17 | Configuration, experiments & runtime controls | What defaults, switches, thresholds, experiment IDs, and overrides control behavior? |
| D18 | Observability, side effects & event recording | What is logged, emitted, cached, or recorded after/during serving? |
| D19 | Build, packaging & reproducibility | What can actually be built/run/reproduced from the public snapshot? |

## Classification rules

- `primary_domain` identifies the specialist who owns first review.
- `secondary_domains` force cross-domain consumers to inspect the same file when relevant.
- `classification_confidence` is about **assignment**, not whether the code is understood. All baseline paths currently classify at `HIGH`; this does **not** mean any file has been reviewed.
- `review_treatment` distinguishes normal source from generated code, tests, fixtures, docs, examples, assets, and build/reproduction material.
- Generated code is not discarded. It is traced to its schema/generator boundary and consumers.
- Test/fixture/example code is evidence about intended behavior, never substituted for production-path review.

## Files

- `file_domain_map.csv` — one row per baseline file; complete domain and structural assignment.
- `domain_summary.csv` — workload size by domain; cross-domain counts intentionally double-count shared files.
- `structural_summary.csv` — test/generated/schema/config/build/etc. census.
- `manual_attention.csv` — paths whose classification rules need human resolution. **Empty for this baseline.**
- `component_map.csv` — documented role, size, and domain ownership by top-level component.
- `cross_domain_components.csv` — components spanning multiple domains.

The classification is reproducible with `_analysis/tools/build_domain_map.py`.

### Provenance caveat

The structural flags are conservative bookkeeping aids. The baseline contains **no explicit `vendor/` or `third_party/` source tree**, so `is_vendor` is currently zero; that is not a completed third-party provenance/license audit. Likewise, generated-code detection uses explicit generated paths/markers and is refined during specialist review if another generator relationship is discovered.
