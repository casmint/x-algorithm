# Cross-Cutting Audit Lenses

Domain review answers **where** behavior lives. These lenses answer **what every specialist must actively look for**.

1. **L01 — Defaults / feature switches / experiments:** declared value, source of truth, runtime override, treatment/control/shadow paths.
2. **L02 — Weights / thresholds / hardcoded constants:** units, sign, normalization, comparison semantics, sentinel/redacted values.
3. **L03 — Reachability / dead or orphaned code:** declaration is not proof of execution; trace registration, construction, enable checks, and consumers.
4. **L04 — Failure / fallback behavior:** timeout, missing data, stale cache, exception/error, fail-open/closed, retry, default object.
5. **L05 — Safety / moderation lifecycle:** label creation, scope, TTL/expiry, storage, aggregation, removal, enforcement, visibility effect.
6. **L06 — Geographic / legal / political special cases:** country, jurisdiction, election, legal request, locale, age, language.
7. **L07 — Privacy / security / authorization:** viewer/account identifiers, auth boundaries, sensitive logs, external calls, access-control assumptions.
8. **L08 — Monetization / subscription / access:** ads, subscriber-only content, premium/verification, paid status, product-specific gating.
9. **L09 — New-user / new-author / cold-start behavior:** history thresholds, age/impression thresholds, dedicated models, exploration.
10. **L10 — In-network vs out-of-network asymmetry:** source quotas, score multipliers, filters, reply/retweet handling, topic paths.
11. **L11 — Negative feedback / reputation propagation:** report, block, mute, not-interested, suspensions, graph effects, prediction vs raw count semantics.
12. **L12 — Storage / cache / retention / expiry:** stale reads, TTL, invalidation, event ordering, deduplication, persistence.
13. **L13 — Omitted / external / redacted dependencies:** internal services, unpublished config, prompts, rules, model artifacts, feature-store data.
14. **L14 — Tests / reproducibility / docs mismatch:** what can compile/run, synthetic vs production data, untestable paths, comments contradicting implementation.
15. **L15 — Performance / load shedding:** deadlines, batching, caching, queueing, admission, degraded modes that can alter behavior.
16. **L16 — Model/data provenance:** feature definitions, labels, dataset construction, leakage, serving/training parity, checkpoint/artifact path.
17. **L17 — Transparency / explainability / appeal:** what a user can observe vs what actually changes distribution.
18. **L18 — Update drift:** code synced/generated from elsewhere, checked-in default timestamp, stale mirrors, config/code divergence.

A domain report is incomplete if it merely narrates the happy path and does not address applicable lenses.
