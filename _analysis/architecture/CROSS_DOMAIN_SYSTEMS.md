# Cross-Domain Systems Requiring Joint Review

These are the places most likely to produce mistakes if specialists only read their own directory.

| Bridge | Why it crosses domains | Required joint passes |
|---|---|---|
| **Home Mixer** | Owns orchestration but also contains source wiring, hydration, filters, scoring weights, selectors, ads/blending, and side effects. | S01 + S02 + S03/S05/S08/S14 as applicable |
| **Phoenix** | One codebase contains retrieval, ranking, feature preparation, training, inference, serving, and model/data infrastructure. | S05 + S06 |
| **Phoenix RankAll Strato -> Visibility Filtering** | Index admission can consult visibility logic before request-time ranking, creating an earlier eligibility boundary. | S07 + S14 |
| **Home Mixer -> Visibility Filtering** | VF is consumed after ranking/selection in the documented request path; this boundary separates order from showability. | S01/S02 + S14 |
| **Grox/media models -> labels/VF** | Content understanding produces scores/labels/features whose impact depends on downstream rule/policy consumers. A classifier output alone is not a visibility action. | S09/S10 + S13/S14 |
| **Agatha/BDSM/UserCred -> enforcement/labels** | Account-level scores only matter where later rules or services consume them; prestige/reputation must be traced to actual consequences. | S11 + S13/S15/S14 |
| **Botmaker -> Scarecrow -> Botmaker Rules** | Compiler/runtime semantics, published rules, and event-driven execution are split across three trees. | S12 + S13 |
| **Safety-label-user-agg** | Converts post-level labels into account-level labels, potentially changing later visibility/enforcement scope. | S13 + S14/S15 |
| **Abuse Enforcement -> label storage/VF** | Enforcement can write account/post state that later changes visibility. Decision and serving effects live in different components. | S15 + S14 |
| **Under the Hood -> labeling/enforcement** | Transparency reports consume label history; reported labels must be checked against actual visibility/enforcement semantics and omissions. | S16 + S13/S14/S15 |
| **Config/experiments -> all behavioral code** | Checked-in code can be dormant, treatment-only, shadow-only, or runtime-overridden. | S17 + every affected specialist |
| **Caches/storage/failure paths -> policy decisions** | Stale/missing data can alter ranking, visibility, or enforcement even when normal-path logic is correct. | S18 + affected specialist |

## Rule

No cross-domain finding may be finalized by only one side of a bridge. For example, finding a label writer is not enough: its reader, scope, expiry, and concrete serving/enforcement effect must also be traced.
