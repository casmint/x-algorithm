# Architecture Coverage Map

**Status: documented baseline, not yet independently verified.**

This map is derived from the frozen repository's root `README.md` plus the source layout. Each arrow is a hypothesis that later passes must confirm against implementation, runtime controls, and call sites.

## 1. For You request path

```text
Viewer request
    |
    v
Home Mixer / candidate-pipeline                         [D01]
    |
    +--> Query hydration: history, follows, blocks,
    |    mutes, seen state, topics, params              [D01 D07 D17]
    |
    +--> Candidate sources
    |      +-- Thunder: followed accounts              [D02]
    |      +-- Phoenix retrieval: OON model            [D03]
    |      +-- SimClusters: cluster similarity         [D03]
    |
    +--> Candidate hydration                            [D01 D16]
    |
    +--> Pre-scoring eligibility filters                [D07]
    |
    +--> Phoenix action predictions                     [D05]
    |
    +--> RankingScorer: weighted/controlled scoring     [D05 D17]
    |
    +--> VMRanker / selection / diversity               [D06]
    |
    +--> Visibility Filtering + conversation cleanup    [D12 D07]
    |
    +--> Blending: ads / Who to Follow / prompts/etc.   [D08]
    |
    +--> Side effects / served-state / event logging    [D18]
    v
For You response
```

### Questions the implementation audit must answer

- Which sources are actually wired and enabled by checked-in defaults?
- Which stages are optional, experiment-gated, shadow-only, or unreachable?
- What order do filters, scoring, reranking, and visibility checks truly execute in?
- Which failures fail open, fail closed, return empty/default data, or fall back?
- Which defaults can be overridden by unpublished runtime configuration?

## 2. Retrieval-index path

```text
Post / engagement events
    |
    v
phoenix-rankall-strato                                 [D04 D12]
    |  eligibility / event routing / VF consultation
    v
phoenix-rankall index maintenance                      [D04]
    |
    v
Phoenix retrieval query                                [D03]
```

This path must be audited separately from request-time filtering: content can be excluded before it ever becomes a retrieval candidate.

## 3. Labeling, reputation, and enforcement path

```text
POST / MEDIA signals                    ACCOUNT / GRAPH signals
        |                                       |
        +-- Grox                                 +-- Agatha
        +-- media-model-proxy                    +-- BDSM
        +-- CLIP / adult / pNSFW                 +-- UserCred V2
        |                                       |
        v                                       v
Content/account scores & features                 [D09 D10]
        |
        +--> Scarecrow + Botmaker rules           [D11]
        +--> safety-label-user-agg                 [D11]
        +--> abuse-enforcement-service             [D13]
        |
        v
Stored account/post labels                        [D11 D13 D16]
        |
        +-----------------> Visibility Filtering  [D12]
        |                         |
        |                         v
        |                    request/index decisions
        |
        +-----------------> Under the Hood         [D14]
```

Critical audit point: **ranking and visibility are separate mechanisms**, but the same signals or labels may influence eligibility at multiple stages. Cross-domain tracing must not assume a single "algorithm score."

## 4. Model lifecycle

```text
Datasets / event streams
      |
      +--> Phoenix training/eval -----------------> ranking/retrieval artifacts
      +--> CLIP/adult/media training -------------> media artifacts
      +--> Agatha/BDSM jobs ----------------------> account signals/models
      |
      v
Serving / batch / stream systems                  [D15 D16]
      |
      v
Features, predictions, labels consumed above
```

The public snapshot explicitly omits some production material, including Grox prompts and some Botmaker rules, and does not uniformly include deployment/build infrastructure outside components designed to run publicly. These are **known evidence boundaries**, not permission to guess missing behavior.

## 5. Control plane cutting across every path

`D17 Configuration, experiments & runtime controls` is deliberately cross-cutting. Checked-in defaults, feature switches, GrowthBook/config sources, experiment IDs, policy YAML, model thresholds, and external config can change whether code shown above is live.

No behavioral claim is final until its reachability and runtime-control path are checked.
