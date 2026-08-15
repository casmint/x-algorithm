# Eligibility & Visibility — Why a High-Scoring Post May Still Not Be Shown

Rapid-track macro combining the behaviorally-relevant parts of S09 (Grox content
understanding), S10 (media understanding), S11 (account signals/reputation), S12
(Botmaker), S13 (label rules/aggregation), S14 (visibility filtering), and S15 (abuse
enforcement) into one investigation, per `_analysis/rapid/README.md`. Builds on
`01_retrieval.md` and `02_ranking.md`; does not re-derive them.

## Plain-English summary

A post surviving retrieval and scoring highly is not the same as a post being shown.
There are at least five structurally different places a post (or its author) can be
excluded, and they are not interchangeable: it can be kept out of the retrieval index
entirely before any request exists; it can be dropped by a pre-scoring eligibility
filter inside Home Mixer before Phoenix ever sees it; it can be scored normally but then
removed by a post-scoring visibility check; it can be kept but shown behind an
interstitial instead of directly; or the *account* itself can lose eligibility for
algorithmic recommendation altogether, silently affecting every future request.

The system that makes the final per-viewer, per-post call is **visibility filtering
(VF)**, and this repository ships its complete production Rust implementation —
`visibility-filtering/` — not just a client stub. VF runs as a distinct request stage,
after Phoenix scoring and after the top-50 selection (established in `02_ranking.md`),
against exactly the top 50 already-ranked candidates. It receives, for each candidate,
the viewer's identity and relationship to the author (block, mute, mutual-follow,
country), the author's account-safety flags (suspended, deactivated, protected, NSFW),
and any post- and account-level safety labels currently on record. It runs a fixed,
ordered list of rules and produces exactly one of three outcomes per post: **Allow**
(no change), **Interstitial** (shown, but the client is told to render a warning/blur
before the content), or **Drop** (removed from Home Mixer's own filter, never reaches
the client). A crucial, easy-to-miss detail: Home Mixer's own filter (`VFFilter`) only
removes a candidate when VF's answer is specifically `Drop`. `Interstitial` is *kept* —
the whole point of an interstitial is that the content still travels to the client, just
with a flag attached so the client can choose how to render it. Conflating "interstitial"
with "removed" is a real mistake this report is careful to avoid.

VF's rule set is *not* the same for every post. Every candidate is evaluated under one
of two policies depending on whether it's in-network or out-of-network:
`TimelineHome` (in-network, more permissive — mainly blocks/mutes/account-state/legal
takedowns/hard NSFW) or `TimelineHomeRecommendations` (out-of-network, meaningfully
stricter — everything from `TimelineHome` plus roughly two dozen additional drop rules
covering NSFW/spam/abuse/malicious-URL/geo-restricted-media labels that simply don't
apply to in-network content at all). This means the exact same post, with the exact same
labels, can be visible to people who follow the author and invisible to people who don't
— confirmed directly by this repository's own tests, several of which literally assert
"in-network X should allow" and "OON X should drop" side by side. A closely related and
genuinely important exemption pattern recurs throughout the rule set: an account's own
author viewing their own content is essentially never dropped by an author-state rule,
and several of the OON-only drop rules (abusive-high-recall author, do-not-amplify)
explicitly *don't* apply if the viewer already follows that author — the rules are built
to suppress *discovery*, not to erase content from people who already chose to follow it.

Where do the labels VF checks come from? This repository shows the whole chain, not just
one link. **Botmaker** is a large, general-purpose, compiled-rule event-processing
engine (an ANTLR-defined DSL, hundreds of Java/Scala files implementing the runtime) —
but critically, the *rules themselves* are not checked into this repository; only the
engine that would run them is. **Scarecrow** is the specific, named production
deployment of Botmaker for spam/abuse: it wires the generic engine to concrete actions
like `SetUserLabel` (writes an account-level safety label directly onto the user's
Gizmoduck record, default 7-day expiration) and `SetLabel`/`SetLabelWithTtl` (writes a
more general namespaced label into a Manhattan-backed store, default 26-hour TTL). Both
of those exact storage locations are the ones VF reads from at request time — this
repository shows the write side (Scarecrow's actions) and the read side (VF's
`safety_label_source`/Gizmoduck hydrator) converging on the same stores, which is about
as concrete as "label exists → label limits visibility" evidence gets in this snapshot.

A second, largely independent aggregation pipeline exists specifically for one narrow
purpose: escalating post-level content classifications into account-level NSFW labels.
`safety-label-user-agg` watches for newly-applied post safety labels, and when triggered,
scans a small recent window of the author's other posts (config-bounded to at most 10
posts, at most 60 days old) counting how many also carry a matching label. If enough do,
it writes exactly one of two possible account labels — `POSSIBLY_NSFW_ACCOUNT` or
`NSFW_HIGH_PRECISION` — back onto the author's Gizmoduck record, attributed to "Grox,"
with at most a 7-day expiry. That allowlist of exactly two output labels is hardcoded;
the pipeline cannot produce any other kind of account label no matter what the external
rule config says. This is a good example of the evidence discipline this report tries to
hold throughout: it would be easy to assume a "post label aggregation" system is a
general spam/abuse escalator, but tracing the actual code shows it is narrowly scoped to
NSFW classification only.

**Grox** is the content-understanding system that produces much of the raw material
these downstream systems consume: it's an LLM-based (Gemma/Grok-family model) classifier
that watches posts crossing engagement/traction thresholds and writes boolean content
flags — `isNsfw`, `isGore`, `isViolent`, `isSpam`, `isSoftNsfw`, `isAdult` — plus topic
tags directly into `UnifiedPostAnnotations`, a Manhattan-stored record. That exact record
type is what `phoenix-rankall`'s index-admission logic reads to decide NSFW admission
(confirmed in the corrected `01_retrieval.md`) — meaning Grox's classification can gate
whether a post ever enters Phoenix's retrieval index at all, before any viewer-specific
question is even asked. **Media understanding** contributes a parallel, narrower signal:
a small classifier (`pnsfwmedia`) that scores an individual piece of media as NSFW by
combining a frozen CLIP image embedding with two *account-level* signals — a
calibrated NSFW score from **Agatha** and a separate text-based NSFW user score — meaning
a media classification here is not purely about the pixels, it's blended with the
uploading account's own history.

**Account reputation systems** in this snapshot present three genuinely different
pictures of "does a score matter." **Agatha** computes graph/behavior-derived
user-level scores (`FlattenedBlinkScore`, `UserPrediction`) with a real, well-defined
output shape — but this snapshot shows *no* direct consumer of those specific output
types anywhere else in the repository, except indirectly: its calibrated NSFW score
resurfaces as a named feature (`agatha_calibrated_nsfw_score`) inside the media-NSFW
classifier described above, reached through an intermediate feature store this repo
doesn't show the plumbing for. **BDSM** (Behavioral Detection Sequence Model) is the
opposite case: a fully-specified, self-documenting transformer over a user's action
sequence, an 8-head bot/spam classifier, with its *own* dedicated results-processing
pipeline that performs graduated enforcement — CAPTCHA/liveness challenges for
borderline cases, suspension for high-confidence ones — and an explicit, git-committed
note that its actual decision thresholds are redacted from this public release (shipped
as an obviously-invalid `9.99` sentinel) specifically so the detection boundary can't be
reverse-engineered. **UserCredV2** is the clearest, most directly-traced case: a
PageRank-style credibility score computed by propagating "mass" along the real follow
graph (Flock edges), log-transformed into a bounded 0–100 score — and this repository
shows, by name, that both Scarecrow's rule engine and the abuse-enforcement-service's
own YAML rules query this exact score as an input, using it as a **skip gate**: a
sufficiently high-credibility account (score ≥ 50, or "is_high," or a high follower
count) is explicitly exempted from several enforcement rule branches before they're even
evaluated. That is about as close to "score demonstrably changes an outcome" as this
kind of tracing gets.

**Abuse-enforcement-service** is the final decision point this repo shows clearly, and
unlike Botmaker's rules, its actual rule files (`enforcement_user.yaml`,
`enforcement_post.yaml`) *are* checked in — mirrored from a live GrowthBook config, dated
in the file header. Its production trigger is a Kafka consumer, not a per-request call —
meaning it evaluates entities some upstream detector already flagged, not every user on
every request. Its rules read a `score.labels` set (populated by named upstream models —
`inauthentic_detection_v45`, `cluster_spam_extended`, and others this repo doesn't trace
further) and translate them into one of a small, fixed action vocabulary: suspend
(temporary or permanent, tagged with a policy name like `PlatformManipulation` or `Cse`
for child-safety cases), add an account or post label with a TTL (frequently
`SpamHighRecall` — the exact label name VF's OON policy already drops on), or issue a
CAPTCHA/Arkose/liveness challenge. The user-level rule file ends with an unconditional
"suspend" fallback for anything that reaches the bottom unmatched; the post-level file
notably does *not* have that same fallback — it ends with an unconditional skip instead.
That asymmetry is stated exactly as observed, without assuming why it exists.

A recurring structural theme worth internalizing: **index-time safety and request-time
visibility filtering are related but not identical.** The corrected retrieval report
already established that `phoenix-rankall`'s admission logic calls a
`shouldDropPostByVF`-style check before writing to the mainstream index. This macro
traces that call precisely: it evaluates at the stricter `TimelineHomeRecommendations`
(OON) safety level, with **no viewer context at all** — it's a universal, once-per-post
decision, not a per-viewer one — and it fails open (treats an unavailable dependency as
"don't drop") exactly like the client-side RPC-failure path in Home Mixer does. The
practical consequence: a post that would only be dropped under the *stricter* OON policy
(say, flagged `SpamHighRecall`) is excluded from Phoenix's retrieval index for every
viewer, even those who would have seen it fine under the more permissive in-network
policy — meaning Thunder (which never calls VF at retrieval time) can still surface that
exact post to a follower, while Phoenix's retrieval-based sources categorically cannot,
for anyone. Index exclusion and request-time filtering really are two different gates
with two different scopes.

Finally, the carried-forward Gizmoduck question from `01_retrieval.md` (S01-F008): this
snapshot does not reveal what writes `allow_for_you_recommendations = false`. No code
anywhere in this repository sets that field. The only new context this macro can add is
structural, not causal: the field sits, in the Gizmoduck-generated account schema,
immediately adjacent to a long run of literal user-facing privacy/personalization
toggles (`allow_ads_personalization`, `allow_xai_data_sharing`,
`allow_xai_personalization`, `hide_subscriptions_on_profile`, and others) — not adjacent
to the account-*enforcement* flags (`is_suspended`, `is_deactivated`, `is_erased`) this
macro traced elsewhere. That schema-neighborhood observation is suggestive that this is
a user-controllable preference rather than a punitive flag, but it is **not** a write
path, and this report does not claim to know the actual mechanism. It remains explicitly
UNKNOWN.

## Control points at a glance

```
POST/ACCOUNT LIFECYCLE                                    SCOPE / TIMING
──────────────────────────────────────────────────────────────────────────
Post created / favorited
        │
        ▼
Grox (LLM content classification)  ──► UnifiedPostAnnotations (Manhattan)
        │                                        │
        ▼                                        ▼
phoenix-rankall admission filter          isNsfwPost/isCommunityPost/etc.
  (community/reply/retweet drop,          used at INDEX-ADMISSION TIME
   shouldDropPostByVF @ TimelineHomeRecommendations,     universal, no viewer,
   no viewer context)                     fails open
        │
        ▼
Phoenix retrieval index  ◄── a post excluded here is unavailable to
                              PhoenixSource/PhoenixTopicsSource/PhoenixMOESource
                              for EVERY viewer — but Thunder/SimClusters/
                              TweetMixer are separate systems, unaffected
──────────────────────────────────────────────────────────────────────────
Request arrives at Home Mixer
        │
        ▼
Pre-scoring eligibility filters (per-request, per-viewer)   S01/S02 + this macro:
  block / mute / muted keyword / self-tweet / duplicate /   REMOVED BEFORE RANKING
  Brazil-2026 list / subscriber-only / age / new-user-min-  (never scored by Phoenix)
  engagement / inventory-holdout
        │
        ▼
Ranking (Phoenix + RankingScorer + VMRanker — 02_ranking.md)   DOWNWEIGHTED, not removed
        │
        ▼
Top-50 selection (TopKScoreSelector)
        │
        ▼
VFCandidateHydrator → visibility-filtering (per-viewer, per-post)   REMOVED/FLAGGED
  in-network → TimelineHome policy        AFTER RANKING, before final truncation
  OON/ancestors/quotes → TimelineHomeRecommendations policy (stricter)
        │
        ├── Allow ─────────────► kept, unchanged
        ├── Interstitial ──────► kept, client renders warning/blur — NOT a drop
        └── Drop ───────────────► VFFilter removes it; AncillaryVFFilter also
                                   removes posts whose ancestor/quote/retweet was Drop
        │
        ▼
Truncate to 35 → organic result → S02 blending
──────────────────────────────────────────────────────────────────────────
ACCOUNT-LEVEL, ORTHOGONAL TO ANY SINGLE POST
  Botmaker/Scarecrow rules (external rule defs, not in this repo) write account
  labels/suspensions via SetUserLabel (Gizmoduck) / SetLabel (Manhattan)
  Abuse-enforcement-service (Kafka-triggered, checked-in YAML rules) reads
  score.labels from named upstream detectors, writes suspend/label/challenge
  UserCredV2 (follow-graph PageRank-style score) gates OUT of enforcement at
  high credibility; used as an evaluable Botmaker/AES signal, not a VF rule input
  Gizmoduck.allow_for_you_recommendations forces in_network_only=true (S01-F008) —
  write path UNKNOWN from this snapshot
```

## Before retrieval / index admission

Established precisely in the corrected `01_retrieval.md` and re-traced here with full
evidence for the VF call specifically. `phoenix-rankall-strato/lib/eventProcessing.strato`'s
`shouldDropPostByVF(postId)`:

```
useRust = decider("enable_vf_rust_should_drop_tweet")  (fetch failure -> false)
if useRust:
    verdict = fetch #<visibility/xai/shouldDropTweet>(postId, {safetyLevel = TimelineHomeRecommendations})
              (fetch failure -> None)
    return verdict.getOrElse(false)
else:
    return fetch #Tweet<visibility/service/shouldDropTweetV2>(postId, {safetyLevel = TimelineHomeRecommendations, forUserId = None})
              .getOrElse(false)
```

Key properties, all DIRECT from this one function:

- **No viewer context at all** (`forUserId = None` on the legacy path; the Rust path
  takes only a `postId` and a fixed safety level) — this is a universal, once-per-post
  decision, structurally different from every other VF call traced in this report, which
  are all per-viewer.
- **Evaluated at the stricter `TimelineHomeRecommendations` policy** — the same policy
  set used for out-of-network content at request time, including all the OON-only
  drop rules (spam/abuse/NSFW/malicious-URL labels) that don't apply in-network.
- **Fails open on any exception at every layer** (`catch { case _ => false }` on the
  decider fetch, `catch { case _ => None }` on the verdict fetch, `.getOrElse(false)` on
  the missing verdict) — an unavailable VF dependency at index-admission time means
  admission proceeds, not that the post is blocked.
- Gated by decider `enable_vf_rust_should_drop_tweet` between the same Rust VF service
  Home Mixer's `XaiVfClient` calls at request time, or a legacy Scala
  `shouldDropTweetV2` endpoint — this repository does not show which is live in
  production.

**Consequence**: a post dropped by this check is excluded from every mainstream
Phoenix-rankall index (`post_creation`, `1fav`, `32fav`, video, etc.) for every future
viewer — it can never become a `PhoenixSource`/`PhoenixTopicsSource`/`PhoenixMOESource`
candidate. It remains fully retrievable via Thunder (in-network) and SimClusters (if it
still gets favorited by someone whose engagement seeds an ANN query) — those systems
have no equivalent admission-time VF check. This is the concrete, evidenced form of
"index exclusion != request-time filtering": the *scope* of the exclusion (universal, no
viewer) is broader than any single request-time VF call, but the exclusion only applies
to one specific retrieval mechanism, not to the post's existence or its reachability
through other paths.

## Home Mixer pre-scoring eligibility

Building on S01/S02's inventory; this section adds precise removal-vs-keep and
fail-open/closed behavior for the filters most relevant to "why didn't I see this post."
All of these run in the pre-scoring filter stage — sequential, before any scorer sees the
candidate (S01) — so a candidate removed here never reaches Phoenix at all, distinct from
being scored low or dropped by VF afterward.

| Filter | Trigger | Fail-open/closed | Evidence |
|---|---|---|---|
| `AuthorSocialgraphFilter` | block/mute (from Home Mixer's own socialgraph query hydrator, not VF) | Hydrator failure leaves the flag unset → filter effectively fail-open for that candidate (framework default, S01) | STRONG_INFERENCE (not independently re-read this pass beyond confirming the file exists — same framework pattern established for VF) |
| `MutedKeywordFilter` | candidate text matches a viewer's muted keyword | Not independently re-traced this pass; a query-hydrator failure upstream would leave the muted-keyword set empty → fail-open (no keywords to match) | STRONG_INFERENCE |
| `SelfTweetFilter` | `candidate.author_id == query.user_id` | No dependency, cannot fail | DIRECT — `home-mixer/filters/self_tweet_filter.rs:13-16` |
| `IneligibleSubscriptionFilter` | candidate is subscriber-only content (`subscription_author_id` set) and viewer is not in `query.user_features.subscribed_user_ids` | Depends on upstream subscription-list hydration; not independently traced | DIRECT (filter logic) — `home-mixer/filters/ineligible_subscription_filter.rs:8-28` |
| `Brazil2026ElectionFilter` | author (or retweeted/quoted author, or reply ancestor) is in a hardcoded, checked-in list of 665 Brazilian electoral-court-reported accounts — **unless the viewer already follows that author** | No external dependency (static list); cannot fail | DIRECT — `home-mixer/filters/brazil_2026_election_filter.rs:1359-1361` (`is_excluded_author` requires membership in the list **and** absence from `followed_user_ids`); list size confirmed by test at line ~1366 (`assert_eq!(...len(), 665)`) |
| `RetweetDeduplicationFilter` | duplicate retweets of the same source post in one batch | No external dependency | Not independently re-read this pass; role established by S01 |
| `NewUserMinEngagementFilter` | (per S01) applies to accounts below an engagement-history threshold | Not independently re-read this pass | STRONG_INFERENCE, carried from S01 |
| `InventoryHoldoutFilter` | (per S01) an experiment-holdout mechanism | Not independently re-read this pass | STRONG_INFERENCE, carried from S01 |

**The Brazil filter's follow-exemption is the one genuinely new, precise finding here**:
the legal requirement is specifically about *algorithmic recommendation*, and the
checked-in implementation reflects that distinction directly in code — a viewer who
already follows a listed account still sees their organic posts; the filter only removes
them from being algorithmically surfaced to non-followers (`brazil_2026_election_filter.rs:1359-1374`,
also dropping retweets/quotes of listed authors and replies whose conversation
ancestors trace back to one).

**Redundancy with VF**: `IneligibleSubscriptionFilter` (Home Mixer) and VF's
`DropExclusiveTweetContentRule` (`visibility-filtering/rules/socialgraph_rules.rs:65-97`)
appear to enforce an overlapping "subscriber-only content" boundary at two different
layers — this repo does not establish whether they check the exact same underlying data
or are two independent, defense-in-depth checks; not resolved further in this pass.

## Account signals and reputation

**Agatha** (`agatha/`): a Scalding-batch graph/behavior scoring system. Its thrift schema
(`agatha/thrift/agatha.thrift`) defines `FlattenedBlinkScore{userId, label, score}` and
richer `UserPrediction`/`UserQuantilePrediction` types carrying a `featureClass`, a
`label` string, and either moments or quantiles (distributional, not just point
estimates) — DIRECT, these are real, well-typed outputs. **No consumer of these specific
thrift types was found anywhere else in this snapshot** (`grep` across `.scala`/`.rs`/
`.strato`/`.py` outside `agatha/` for `FlattenedBlinkScore`/`UserPrediction`/
`UserQuantilePrediction` returned nothing) — this is the clearest example in this macro
of "system produces a score" without a demonstrated feed consequence *by that name*.
The one indirect link found: `pnsfwmedia/model_experimental.py` consumes a feature named
`source_user.hss.user_health_scores.agatha_calibrated_nsfw_score` — an Agatha-attributed
score reached through an intermediate "Health Signal Service" (HSS) feature store this
repo doesn't show the write-side plumbing for. STRONG_INFERENCE that this is Agatha's
output reaching a real consumer; not DIRECT, since the HSS feature-store connection
itself isn't traced.

**BDSM** (`bdsm/`): a transformer over a user's recent action-event sequence (time-aware
RoPE keyed on real timestamps, not token position; 8 classification heads — FollowBot,
LikeBot, EngagementAmplifier, ReplySpamBot, TweetSpamBot, RTBot, MultiActionBot,
LegitimateUser). This is the one system in this macro with its own complete,
self-documented, checked-in **enforcement pipeline**
(`bdsm/runtime/score_results_sink_focal.py`, 1689 lines, not read in full — targeted
sections read): per-head thresholds live in a `SinkPolicy`, with the actual production
values explicitly redacted (shipped as an out-of-range `9.99` sentinel — the README
states this is deliberate, to avoid publishing the detector's evasion boundary). The
pipeline supports graduated action — CAPTCHA/Arkose/"liveness" challenge as a softer
alternative to suspension, with a documented, dated policy change in the CLI help text
("'dry_run' = suspend as today... 'challenge' = suppress suspension... because dry_run
showed too many false positives on legit-scored users, 2026-07-15") — and mentions an
external "enforcement service" that can be configured to ignore certain signals
("`spam_bounce_would_challenge` (enforcement service ignores it)"), consistent with
`abuse-enforcement-service` being that downstream consumer, though this exact wiring was
not independently traced end to end.

**UserCredV2** (`user-cred-v2/`): the most directly-traced reputation system in this
macro. Input: the real follow graph, sourced from Flock edges
(`user-cred-v2/Edge.scala:13-19`, `fromFlockEdge`). Mechanism: each valid user starts
with `mass = 1.0` (`UserMass.calcInitMass`); an iterative mass-propagation process (not
itself opened in this pass — the 9 files present are the data types and a
`UserCredV2App` entry point, not the full offline job) produces a final `mass`, and
`UserCredV2.fromMass` log-transforms it into a bounded `[0, 100]` score
(`score = clamp(165.2 + 7.07 * ln(mass), 0, 100)`, `user-cred-v2/UserCredV2.scala:13-19`)
— structurally a PageRank-style network-authority score. **Directly consumed**:
`scarecrow/legacy/StratoRegistry.scala:120-135` registers `GetUserCredV2` as a callable
Botmaker function (`"Takes a user ID and returns their UserCred V2 score, mass, and
snapshot timestamp"`), and `abuse-enforcement-service/service-lib/rules/enforcement_user.yaml:25-31`
uses `cred.is_high`/`cred.score >= 50.0` as an unconditional **skip** gate ("pagerank_skipped")
before several enforcement branches — high-credibility accounts are explicitly exempted
from parts of the automated enforcement pipeline. This is the one reputation system in
this macro where "score demonstrably changes an outcome" is proven, by name, in checked-in
code, not merely plausible.

## Content understanding

**Grox** (`grox/`): an LLM-based (Gemma-family — `grox/flows/upa/constants.py`'s
`GEMMA_UPA = "oai-gemma4-26b-upa"`) content classifier, triggered when a post crosses a
"min traction" threshold on a Kafka stream (`POST_MIN_TRACTION_STREAM_FOR_GROX`,
`grox/flows/upa/constants.py:1`). `TaskPublishUnifiedPostAnnotationsManhattan`
(`grox/flows/upa/task_write.py:29-70`) writes boolean flags — `isNsfw`, `isGore`,
`isViolent`, `isSpam`, `isSoftNsfw`, `isAdult` — plus content tags, directly into
`UnifiedPostAnnotations` in Manhattan. This is the **exact record type** consumed by
`phoenix-rankall-strato`'s `isNsfwPost`/topic-filtering logic at index-admission time
(confirmed in `01_retrieval.md`'s corrected finding #1 discussion and re-verified here)
— Grox's classification can gate Phoenix retrieval-index admission before any viewer
question is asked. Whether `UnifiedPostAnnotations`'s boolean flags *also* feed VF's
separate `SafetyLabelType` label system (the one `visibility-filtering/rules/*.rs`
consumes) was **not established** in this pass — these could be the same underlying
signal reaching two consumers through different pipelines, or two structurally separate
classification systems; UNKNOWN. A separate Grox flow, `reply_spam/`, exists
specifically for reply-spam and coordinated-spam detection
(`classifier_coordinated_spam.py`, `task_spam_detection.py`) — not deep-read, noted for
completeness.

**Media understanding**: `media-model-proxy` (`media-model-proxy/`) is explicitly,
per its own README, a thin **proxy/infrastructure layer** — it loads media from
Blobstore and forwards inference requests to DeepBird prediction services, returning raw
model responses to the caller; it does not itself store or interpret scores
(`media-model-proxy/README.rst:15-17`, `"Media Model Proxy does not publish/store model
scores for consumption... The caller is responsible"`) — its actual consumers ("Media
Analysis Service") are external to this snapshot, so MMP itself is not a decision point.
`pnsfwmedia/model_experimental.py` is a small, concrete NSFW-media classifier: frozen
CLIP image embedding → BatchNorm → Dense(50, relu) → Dense(1, sigmoid), fused with two
account-level features — `source_user.hss.user_health_scores.agatha_calibrated_nsfw_score`
(Agatha) and a separate `nsfw_text_user_score` — meaning this specific media
classification is not purely visual; it's blended with the uploading account's own
history. This snapshot does not show where `pnsfwmedia`'s own output score is written or
consumed downstream — plausibly it feeds the same `ContainNsfwMedia`/`NsfwHighPrecision`-
family labels VF already consumes, but that link was **not independently traced**.

## Botmaker and Scarecrow

**Does Botmaker rank posts? No.** Botmaker is a general-purpose, event-driven rule
engine — not a ranking system, not a retrieval system. It compiles a custom DSL (ANTLR
grammar, `botmaker/src/antlr/com/twitter/botmaker/antlr/BotMaker.g`) into a Boolean
condition AST plus an action AST per rule; on each incoming event, every applicable
rule's condition is evaluated concurrently (`Future.join` across `ruleEvaluators`,
`botmaker/src/scala/com/twitter/botmaker/rule/EventEvaluator.scala:12-31`), each rule
individually timeout-bounded and exception-isolated
(`RuleEvaluator.evaluate`/`raiseWithin`, `botmaker/.../RuleEvaluator.scala:51-67`) — a
`VIOLATED` condition triggers that rule's action; a failed or timed-out rule is
`ABORTED`/`ABORTED_IGNORED` and simply doesn't fire, without affecting other rules for
that event.

**Critically, this repository ships the engine, not the rules.** No standalone rule
definition files exist anywhere under `botmaker/` — only Java/Scala engine code, an
ANTLR grammar, and a `Loader` abstraction (`botmaker/.../loader/Loader.scala`) whose
`fetch()` is abstract, implying rules load from an external package/config system not
included in this snapshot. This is a meaningful contrast with visibility-filtering,
whose actual policy *is* checked in as compiled Rust, and with abuse-enforcement-service,
whose actual YAML rules *are* checked in.

**Scarecrow** (`scarecrow/`) is the named, concrete Botmaker deployment for spam/abuse —
not a separate engine, a specific application of the generic one. Its `legacy/` registry
files wire in the concrete actions Botmaker rules can invoke:

- `SetUserLabel(userId, labelType, reason, expirationInMs, forceSet, ..., actor)` —
  writes an account-level label directly onto Gizmoduck (`downstreams: Set(Gizmoduck)`),
  default expiry `now + 7 days`. Gated by dark-mode: if `systemConfigs.darkMode` is on,
  the action is a silent no-op that returns success without writing anything
  (`scarecrow/legacy/ActionerRegistry.scala:52-54`) — a real, checked-in shadow-mode
  mechanism, whose current on/off state this snapshot cannot show.
- `SetLabel`/`SetLabelWithTtl(namespace, key, label, ttlSecs, updateCache)` — writes to a
  Manhattan-backed label store, default TTL 26 hours
  (`scarecrow/legacy/SpamLabelStoreRegistry.scala:55-104`).
- `GetUserCredV2`, `GetUserHealthScores` — read-side functions exposing UserCredV2 and a
  related "Health Signal Service" score to rule conditions (see Account signals above).

**What Scarecrow actually does, concretely**: it's the mechanism by which upstream
detection (BDSM scores, Grox classifications, Agatha-derived HSS features, and whatever
external signals its rule config references) gets translated into the exact account- and
tweet-level labels visibility-filtering later reads. This report did not find the
specific rule conditions that decide *when* `SetUserLabel`/`SetLabel` fire (those live in
the unpublished rule config) — only the action primitives and their write targets.

## Label storage and aggregation

**`safety-label-user-agg`** (3 files, all read) is a narrowly-scoped post→account label
escalation pipeline, triggered on `TweetSafetyLabelEvent(actionType=Applied)`:

1. Loads a config-driven rule set (`PostLabelCountCondition{windowSize,
   minimumMatchingPosts, maxPostAgeDays, mediaOnly, postLabels}` — a real "N of the last
   M posts within X days carry label Y" pattern, `safety-label-user-agg/postToUserLabelRules.strato:11-16`).
2. Hard config bounds, all checked-in constants: `maxConfiguredWindowSize = 10`,
   `maxConfiguredMinimumMatchingPosts = 11`, `maxConfiguredPostAgeDays = 60`,
   `maxConfiguredUserLabelTtlDays = 7` (`postToUserLabelRules.strato:100-108`).
3. **`allowedApplyUserLabels` is a hardcoded allowlist of exactly two output labels**:
   `POSSIBLY_NSFW_ACCOUNT` and `NSFW_HIGH_PRECISION`
   (`postToUserLabelRules.strato:96-99`) — any other value in the external rule config
   is silently rejected. This pipeline can only ever escalate toward NSFW account
   classification, never toward spam/abuse/other categories, regardless of what its
   input config might attempt.
4. Certain accounts are **excluded from this specific aggregation** — already-NSFW-user/
   NSFW-admin-flagged accounts, high-PageRank/grey-badge accounts, and accounts already
   carrying certain labels (`isExcluded`, `safety-label-user-agg/safetyLabelToUserLevelAggregationV2Processor.strato:56-58`).
5. Output labels are written via `gizmoduckSetUserLabelsColumn.put(userId, labels)` with
   `byUser = "Grox"`, `source = "Grox"` — directly attributing this specific
   aggregation's output to the Grox content-understanding system named above
   (`safetyLabelToUserLevelAggregationV2Processor.strato:92-106`).

## Abuse enforcement

`abuse-enforcement-service/` is a checked-in Rust service with its actual production
rules present as YAML (mirrored from GrowthBook, dated headers:
`enforcement_user.yaml` last synced 2026-08-12, `enforcement_post.yaml` 2026-08-06).
Production trigger is a Kafka consumer ("The production path is the Kafka consumer,"
`abuse-enforcement-service/service-lib/src/service.rs:462`) — this service reacts to
upstream-flagged entities, it does not itself scan every user/post.

**Rule evaluation, user-level** (`enforcement_user.yaml`, all 26 rules read): ordered,
apparent first-match semantics (not independently confirmed from the engine code this
pass, inferred from rule ordering — allowlist/not-found/high-follower/pagerank skip
gates all precede action rules). Skip gates first: allowlisted, user not found, follower
count ≥ a stated **mock** value ("Prod uses a different follower count floor; this is a
mock value to reduce gaming" — `enforcement_user.yaml:19`), UserCredV2 high/≥50, already
suspended/deactivated. Then a long list of model-labeled action rules
(`inauthentic_detection_v45_*`, `cluster_spam_extended_*`, `cluster_spam_*`,
`anchor_campaign_*`, `llm_slop_user`, `SpamEmbeddingMajorityPoster`) mapping to
suspend/label/challenge actions. **The final rule is an unconditional
`act_suspend` (`when: "true"`)** — a catch-all applied to anything reaching the bottom of
the list unmatched by a more specific rule. Given the Kafka-triggered, already-flagged
invocation model, this reads as "default to suspending an entity a detector flagged but
no specific rule branch classified," not "suspend every user" — STRONG_INFERENCE, not
independently confirmed by tracing the Kafka producer side.

**Rule evaluation, post-level** (`enforcement_post.yaml`, all 15 rules read): same
allowlist/not-found/credibility skip-gate shape, then action rules writing only
`SpamHighRecall` or `RiskyHighVizReply` post labels via `act_add_post_labels_v2` — and
one severe exception, `act_suspend_ncmec_reported_content_author`
(`"cse_reports_embedding_v2" in score.labels"` → **permanent** suspension, policy `Cse`)
— a child-safety-specific rule distinguished from every other (temporary,
`PlatformManipulation`-policy) suspension in this system. **Unlike the user-level file,
the post-level file's final rule is an unconditional skip**, not an unconditional
action — a deliberate, precise asymmetry between the two rule sets as checked in.

**Action vocabulary** (`abuse-enforcement-service/service-lib/src/decision.rs:1-24`):
`SuspendUser{perm, policy}`, `AddLabelsV2{labels, ttl_msec}`,
`AddPostLabelsV2{labels, ttl_msec}`, `Arkose`, `Captcha`, `SpamLivenessCheck` — a small,
fixed set, each with its own dedup class (`CLASS_SUSPEND`/`CLASS_CHALLENGE`/`CLASS_LABEL`)
used for per-entity action rate-limiting (not independently traced in this pass).

**Direct label-to-VF link**: `SpamHighRecall`, the most common post-label action output
here, is exactly the `SafetyLabelType` name VF's OON-only policy drops on
(`tweet_label::SPAM_HIGH_RECALL_DROP`, confirmed with a test asserting "in-network
SpamHighRecall should allow... OON SpamHighRecall should drop," `visibility-filtering/rules/registry.rs:419-454`).
This is the clearest, most concrete "producer → consumer" chain traced in this entire
macro: abuse-enforcement-service writes the label, VF reads the identical label name and
acts on it, with a directly-observed behavioral consequence (OON drop, in-network allow).

## Visibility filtering

Deep-read in full: `visibility-filtering/filter.rs`, `filter_tweets.rs`, `rules/mod.rs`,
`rules/registry.rs` (912 lines including tests, all read), `rules/socialgraph_rules.rs`,
`rules/user_rules.rs` (first 140 lines; rest is tests), `hydration/gizmoduck_hydrator.rs`
(first 100 lines), `hydration/fallback_cache.rs` (first 80 lines), `safety_label_source/source.rs`
(first 60 lines), plus `visibility-filtering-client/vf_client.rs` and `models.rs` in
full, and `home-mixer/candidate_hydrators/vf_candidate_hydrator.rs`,
`home-mixer/filters/{vf_filter,ancillary_vf_filter}.rs` in full.

**What VF receives**: viewer identity (`viewer_id`, may be absent/logged-out — several
rules explicitly allow when `viewer.viewer_id().is_none()`), country code (from
`TwitterContextViewer.request_country_code`, forwarded to the RPC — confirmed by test
`get_result_forwards_country_code`), and a batch of tweet IDs at a specified
`SafetyLevel`. Server-side, per candidate: author account-safety flags (suspended,
deactivated, protected, NSFW-user, NSFW-admin, erased, offboarded — all sourced from
Gizmoduck's `QueryFields::SAFETY`), author user-labels (Gizmoduck's `QueryFields::LABELS`
— the exact labels Scarecrow/abuse-enforcement-service write), viewer↔author relationship
(blocks, mutes, mutes-retweets-from, follows, viewer-super-follows — sourced from a
socialgraph client, not independently re-read this pass), tweet-level safety labels
(from a Manhattan/Twemcache-backed `SafetyLabelSource` with a young-tweet-favoring TTL:
≤5-minute-old tweets get up to a 30s cache TTL, older tweets get 60s —
`visibility-filtering/safety_label_source/source.rs:14-33`), and exclusive/subscriber
content metadata.

**Rule evaluation order and outcome combination**
(`visibility-filtering/rules/mod.rs:86-110`, confirmed by direct unit tests): every rule
in the selected policy's list runs, in declared order, unconditionally (no early exit on
Interstitial) — but **any `Drop` immediately short-circuits and wins**, overriding any
prior `Interstitial` vote. If no rule drops, the **first** `Interstitial` vote (not the
last, not the most severe) becomes the verdict. `Allow` is the default if nothing fires.
This is exact, tested behavior, not inferred.

**Two policies, materially different in size and strictness**
(`visibility-filtering/rules/registry.rs:101-170`): `timeline_home_policy()` = a ~26-rule
`base_home_rules()` list (author suspended/deactivated/erased/offboarded, protected
author, block, mute, muted-retweets, several tweet-label drops including spam/PDNA/
bounce/for-emergency-use-only/FOSNR-hateful-violent-abuse-civic, nullcast, stale/legal/
local-law takedowns, sensitive-viewer age gating, exclusive-content drop, and NSFW
interstitials). `timeline_home_recommendations_policy()` = the *same* 26 rules plus
~25 more (DMCA/geo-restricted media, NSFW author flags, tweet NSFW flags, NSFW/gore/
spam/malicious-URL/do-not-amplify/FOSNR-abuse-insults tweet labels, and a matching set of
*user*-level label drops: NSFW high-recall/high-precision user, spam-high-recall user,
compromised/read-only user, impersonation-high-precision user, NSFW avatar/banner-image
user, abusive-high-recall user, NSFW-near-perfect user, do-not-amplify-non-follower
user). A generic `FilterAllRule` (unconditional `Drop`) backs every *other* declared
`SafetyLevel` (search, explore, etc.) — Home Mixer never sends those levels, but this
means, as currently coded, any caller using a non-Timeline safety level gets a
maximally-strict, content-blind drop rather than a real policy; this snapshot does not
show real rule sets for those surfaces.

**Follow/self/author exceptions, all directly tested**: an author viewing their own
content is exempted from every `AuthorFlagDropRule` (suspended/deactivated/erased/
offboarded/NSFW-user/NSFW-admin, `visibility-filtering/rules/user_rules.rs:22-33`).
FOSNR-family labels never drop the author viewing their own post regardless of follow
state. Several OON-only label drops (`AbusiveHighRecallRule`, `DoNotAmplifyNonFollowerRule`)
explicitly allow if the *viewer already follows the author* — the OON restriction exists
specifically to suppress algorithmic discovery of borderline accounts to non-followers,
not to hide them from people who already chose to follow. Malicious-URL and several
other OON-only drops similarly exempt the author's own view.

**Action semantics — ALLOW vs INTERSTITIAL vs DROP**:

- `Allow`: no consequence anywhere downstream.
- `Interstitial`: **kept** by Home Mixer's `VFFilter` (`should_drop` only matches
  `Action::Drop`; `Interstitial`/`Downrank`/`Tombstone`/`Avoid`/`NotEvaluated` are all
  *not* dropped, `home-mixer/filters/vf_filter.rs:22-29`) — the candidate proceeds to
  the served response carrying its `visibility_reason` (which encodes the interstitial
  marker), for the client to render appropriately. This repo does not show client-side
  rendering, only that Home Mixer deliberately does not remove it.
- `Drop`: removed by `VFFilter`. `AncillaryVFFilter`
  (`home-mixer/filters/ancillary_vf_filter.rs`) separately removes a candidate whose
  **ancestor, quoted, or retweeted post** (not the candidate itself) was independently
  computed to be a VF `Drop` (via `should_drop_ancillary` in the hydrator,
  `home-mixer/candidate_hydrators/vf_candidate_hydrator.rs:139-178`) — so a reply to a
  dropped tweet, or a retweet of a dropped tweet, is also removed even if the reply/
  retweet itself is individually Allow.
- `Downrank`/`Tombstone`/`Avoid`: these `Action` variants exist in the proto/model layer
  (`visibility-filtering-client/models.rs:58-67`) but **no VF rule in this snapshot was
  observed producing them**, and Home Mixer's own `VFFilter` treats any of them
  (wrapped in `SafetyResult`) the same as `Allow` (not dropped). Whether any other
  system produces or consumes these variants is UNKNOWN from this snapshot.
- **Legacy client path**: when `EnableXaiVfClient` is off (checked-in default `true`,
  so this is the non-default path), `StratoVfClient` returns flat `FilteredReason`
  variants (e.g. `AuthorBlockViewer`, `ReportedTweet`) with no `Action` wrapper at all —
  Home Mixer's `VFFilter::should_drop`'s catch-all (`Some(_) => true`) treats **every**
  non-`SafetyResult` reason as an unconditional drop. There is no interstitial concept
  on this legacy path as consumed by Home Mixer.

**Batching, timeouts, failure modes** — three distinct, precisely different failure
behaviors, all directly evidenced:

1. **Missing result for a specific tweet ID within an otherwise-successful RPC response**
   fails **closed**: `results_to_map`'s `or_insert_with(|| Ok(Some(FilteredReason::UnspecifiedReason)))`
   (`visibility-filtering-client/vf_client.rs:318-330`, explicitly commented "missing
   response ids fail closed" in its own test) — `UnspecifiedReason` is a non-`SafetyResult`
   reason, so `VFFilter` drops it.
2. **A whole RPC chunk (up to 50 tweets, `XAI_VF_MAX_BATCH_SIZE`) failing** (timeout,
   `DeadlineExceeded`, `Unavailable`, etc.) fails **open** at the Home Mixer layer:
   `rpc_error_map` returns `Err` for every tweet in that chunk
   (`vf_client.rs:333-346`); `VFCandidateHydrator::hydrate` maps that to a per-candidate
   hydration `Err`; per S01's framework-wide `update_all` semantics, that candidate's
   `visibility_reason` update is silently skipped, leaving it at its pre-hydration
   default (`None`) — and `VFFilter::should_drop(&None) == false`, so the candidate is
   **kept**, unfiltered.
3. **Server-side "unresolved author"** (the VF server itself couldn't resolve an
   author_id for a tweet) fails **closed**, server-internally:
   `Verdict::unresolved_author()` = `Drop(UnspecifiedReason)`
   (`visibility-filtering/rules/mod.rs:77-84`, `filter.rs:80-87`).

Batching: 50 tweets per chunk, chunks dispatched concurrently (`join_all`), 400ms default
per-chunk timeout (`XAI_VF_DEFAULT_TIMEOUT_MS`). Gizmoduck author hydration (server-side)
has its own 150ms timeout and an optional stale-value fallback cache (3 modes: Disabled/
Shadow/ServeStale, `visibility-filtering/hydration/fallback_cache.rs:16-30`) — on a
Gizmoduck timeout with `ServeStale` enabled, VF can serve a recently-cached (possibly
outdated) set of author-safety flags rather than treating them as unknown; whether
`ServeStale` is the production mode is UNKNOWN from this snapshot.

**Whether VF runs only on the top-K or elsewhere too**: confirmed only for the primary
ScoredPosts/ForYou path — `VFCandidateHydrator` is a *post-selection* hydrator (S01),
meaning it runs on the already-ranked, already-truncated-to-50 candidate set, not the
full pre-scoring pool. Whether any other Home Mixer pipeline (`ReverseChronPostsPipeline`,
`PhoenixScoresPipeline`) also calls VF was not re-verified in this pass.

## ALLOW vs INTERSTITIAL vs DROP

Restated precisely, since this is one of the most consequential distinctions in this
report: **Allow** = no visible change. **Interstitial** = the post is delivered to the
client with a flag; Home Mixer's own filtering logic does not remove it — removal, if
any, is a client-side rendering choice this repo doesn't show. **Drop** = removed before
the client ever receives it, either directly (the post itself was `Drop`) or ancillary
(an ancestor/quote/retweet target was `Drop`, so the dependent post is removed too, even
if it was itself `Allow`). Nothing in the checked-in Home Mixer VF-consumption code
distinguishes `Downrank`/`Tombstone`/`Avoid` from `Allow` — those outcomes, if VF ever
produces them, currently have no observed effect on the served candidate set.

## Viewer-specific controls: blocks, mutes, follows

- **Block**: `ViewerBlocksAuthorRule` — drops with `AuthorBlockViewer`, only for
  logged-in viewers (`visibility-filtering/rules/socialgraph_rules.rs:7-23`).
- **Mute**: `ViewerMutesAuthorRule` — drops with `ViewerMutesAuthor`, same logged-in
  requirement (`socialgraph_rules.rs:45-63`). `MutedRetweetsRule` separately drops
  retweets specifically from a muted-retweets-from-author relationship, only for actual
  retweets (`socialgraph_rules.rs:25-43`).
- **Both fail open for logged-out viewers**: every socialgraph rule explicitly returns
  `Allow` when `viewer.viewer_id().is_none()` — block/mute relationships are simply not
  evaluated for anonymous viewing.
- **Follow**: no single "follow" rule exists; instead, follow status is a *conditional
  exemption* baked into several otherwise-stricter OON rules (author-viewing-self,
  FOSNR-family, abusive-high-recall, do-not-amplify — see Visibility filtering section
  above) and, separately, into the Brazil-2026 filter's exclusion logic. Following an
  account does not bypass hard drops (suspension, legal takedown, block) but does bypass
  several *discovery-suppression*-flavored OON label drops.

## Account-level For You eligibility

Carried forward from S01-F008, re-examined for any new write-path evidence:
`home-mixer/server.rs`'s `QueryBuilder::build` computes
`in_network_only = proto_query.in_network_only || viewer_data.allow_for_you_recommendations == Some(false)`.
A repo-wide search (`.rs`/`.proto`/`.thrift`/`.strato`, whole repository, not just
home-mixer) for `allow_for_you_recommendations`/`AllowForYouRecommendations` found:

- The one home-mixer consumption site (already known from S01).
- The field's definition inside a large, wholly-generated Thrift schema
  (`thunder/schema/user.rs`, field #70 of the Gizmoduck `Account` struct) — purely
  structural, no behavior.

**No write path exists anywhere in this snapshot.** The only new context available: the
field sits, in that generated schema's field ordering, among a long run of literal
user-facing preference toggles (`allow_ads_personalization`, `allow_media_tagging`,
`allow_xai_data_sharing`, `allow_xai_personalization`, `hide_subscriptions_on_profile`,
`hide_verified_checkmark`, and similar) — not adjacent to the enforcement-flavored
fields this macro traced elsewhere (`is_suspended`, `is_deactivated`, `is_erased`,
labels). This is schema-neighborhood evidence only — **POSSIBLE**, not DIRECT, that this
is a user-controllable privacy/personalization setting rather than a punitive
enforcement flag. This report does **not** conclude it means suspension, spam, or NSFW
enforcement, and states the write mechanism as **UNKNOWN**.

## Legal/geo/special cases

- **Brazil 2026 election filter**: see Home Mixer pre-scoring eligibility above — a
  static, checked-in, 665-account exclusion list with a follow-based exemption, citing
  Brazilian Electoral Court regulation directly in source comments
  (`home-mixer/filters/brazil_2026_election_filter.rs:7-11`).
- **DMCA / geo-restricted media**: VF drop rules (`DropTweetsWithDmcaMediaRule`,
  `DropTweetsWithGeoRestrictedMediaRule`) apply only under the OON
  (`TimelineHomeRecommendations`) policy — in-network content with the same media flags
  is allowed (`visibility-filtering/rules/registry.rs:266-293,635-675`, both directly
  tested). Geo-restriction is keyed to the viewer's `country_code` matching a
  per-tweet `geo_deny_list`.
- **Legal/local-law takedowns**: `DropLegalTakendownPostRule`/`DropLocalLawsTakendownPostRule`
  apply under *both* policies (part of `base_home_rules()`), i.e., a legal takedown is
  not an OON-only restriction — it applies to in-network viewing too. Internals of these
  rules (`visibility-filtering/rules/tes_rules.rs`, 614 lines) were not deep-read this
  pass beyond their registry placement.
- **Sensitive/age-gated content**: `SensitiveViewerLoggedOutDropRule`/
  `SensitiveViewerUnderageDropRule`/`SensitiveViewerNoStatedAgeDropRule`
  (`visibility-filtering/rules/nsfw_age_gating.rs`, 654 lines, not deep-read beyond
  registry placement and naming) also apply under both policies — age/login-state gating
  on sensitive content is not OON-specific.
- **Exclusive/subscriber content**: `DropExclusiveTweetContentRule` applies under both
  policies, with exemptions for the conversation's root author, viewers who
  super-follow the author, and (for non-retweets) the post's own author
  (`visibility-filtering/rules/socialgraph_rules.rs:65-97`, all paths directly tested).
- **Child-safety (CSE/NCMEC)**: the one enforcement path in this macro with a
  **permanent** suspension outcome (`abuse-enforcement-service/service-lib/rules/enforcement_post.yaml:71-76`,
  policy tag `Cse`) — distinguished explicitly from every other (temporary,
  `PlatformManipulation`-policy) suspension rule in the same file.

## Failure and degraded modes

Consolidating every failure path traced in this macro, all against the rule "never say
'request fails' unless the framework actually propagates failure" (per S01, it does not,
anywhere in this chain):

| Component | Failure | Consequence |
|---|---|---|
| Phoenix-rankall index-admission VF check (`shouldDropPostByVF`) | decider fetch fails, verdict fetch fails, or exception at any layer | Fails open — admission proceeds as if VF said "don't drop" |
| Home Mixer VF RPC (whole chunk, ≤50 tweets) | timeout/unavailable/etc. | Fails open — candidate's `visibility_reason` update is skipped, `VFFilter` keeps it |
| Home Mixer VF RPC (individual tweet missing from a successful response) | — | Fails closed — `UnspecifiedReason` → dropped |
| VF server-side author resolution | can't resolve author_id | Fails closed, server-internally — `Verdict::unresolved_author()` = Drop |
| Gizmoduck author-safety/label lookup inside VF | timeout (150ms) | Depends on `FallbackCacheMode`: `Disabled` → presumably empty/default `AuthorFeatures` (fail-open-ish, not independently confirmed); `ServeStale` → serves a recent cached value; `Shadow` mode's actual effect on the served result not independently traced |
| Scarecrow `SetUserLabel` action | `darkMode` config on | Silent no-op — reports success but writes nothing (shadow mode, checked in, production state UNKNOWN) |
| Abuse-enforcement-service | not itself request-time; Kafka consumer — no request-time failure mode traced in this pass | n/a |
| Redis/cache paths inside VF's `SafetyLabelSource` | not independently traced this pass | UNKNOWN |

## Checked-in config vs production state

Every one of the following is a checked-in default or a checked-in rule set; none is
confirmed as the live production value:

- `EnableXaiVfClient` default `true` (`home-mixer/params/param.rs:1135-1139`) — the new
  Rust VF path with full `Action` semantics (Allow/Drop/Interstitial/etc.) is the
  checked-in default; the legacy strato path (unconditional-drop-on-any-reason) is the
  non-default fallback.
- `enable_vf_rust_should_drop_tweet` decider (phoenix-rankall index-admission) — this
  snapshot shows the branch logic, not the decider's live value.
- `abuse-enforcement-service`'s YAML rules are explicitly "mirrored from GrowthBook
  dynamic config" as of specific sync timestamps (2026-08-12, 2026-08-06) — a snapshot,
  not necessarily current.
- BDSM's per-head operating-point thresholds are deliberately, explicitly redacted in
  this public release (shipped as `9.99` sentinels) — not merely undisclosed, actively
  substituted with an invalid placeholder.
- Botmaker/Scarecrow's actual rule *conditions* (which specific behaviors trigger
  `SetUserLabel`/`SetLabel`) are not present in this snapshot at all — only the engine
  and the action primitives.
- Scarecrow's `darkMode` config state (shadow vs. live label writes) is UNKNOWN.
- VF's `FallbackCacheMode` (Disabled/Shadow/ServeStale) live setting is UNKNOWN.

## Material findings

1. **Interstitial is not a drop — Home Mixer deliberately keeps interstitialed
   candidates and passes the flag through to the client.**
   Significance: HIGH. Evidence class: DIRECT.
   Claim: `VFFilter::should_drop` only removes a candidate when the wrapped `Action` is
   specifically `Drop`; `Interstitial` (and `Downrank`/`Tombstone`/`Avoid`/
   `NotEvaluated`) are all left in the served result.
   Source: `home-mixer/filters/vf_filter.rs:22-29`, confirmed by
   `visibility-filtering-client/vf_client.rs:301-316` (`result_to_reason` wraps
   `Interstitial` distinctly from `Drop`).
   Caveat: client-side rendering behavior for the interstitial flag is not in this
   snapshot.

2. **VF policy is genuinely different for in-network vs. out-of-network content — roughly
   25 additional drop rules apply only to OON/algorithmic distribution, several with
   explicit follower/author exemptions.**
   Significance: HIGH. Evidence class: DIRECT (both rule lists and multiple exemptions,
   each independently unit-tested in the checked-in source).
   Source: `visibility-filtering/rules/registry.rs:101-170` (policy composition),
   `:334-508,584-632,819-911` (in-network-allow/OON-drop and follower/author-exemption
   tests).

3. **Three structurally different VF failure behaviors coexist: RPC-chunk failure fails
   open, missing-result-within-a-response fails closed, and server-side
   unresolved-author fails closed — conflating any two of these misdescribes the
   system.**
   Significance: HIGH. Evidence class: DIRECT.
   Source: `visibility-filtering-client/vf_client.rs:318-346` (client-side
   fail-closed/fail-open split, with the fail-closed test explicitly commented "missing
   response ids fail closed"); `home-mixer/candidate_hydrators/vf_candidate_hydrator.rs:110-130`
   plus the framework's default `update_all` (S01) for the RPC-failure fail-open path;
   `visibility-filtering/rules/mod.rs:77-84` for server-side fail-closed.

4. **Botmaker's actual rule definitions are absent from this repository — only the
   engine that would execute them is present — a materially different transparency
   posture than visibility-filtering (rules checked in as compiled Rust) or
   abuse-enforcement-service (rules checked in as YAML).**
   Significance: HIGH. Evidence class: DIRECT (absence confirmed by extension-type
   census across `botmaker/`; no `.rules`/`.bot`/rule-text files found, only
   `.java`/`.scala`/`.g`/`.thrift`/build files).
   Caveat: negative claim scoped to this repository snapshot only; rules plausibly exist
   in an external, unpublished config/package system this repo's `Loader` abstraction
   implies.

5. **A directly-traced write→read chain exists from abuse-enforcement-service's
   `SpamHighRecall` post-label action to visibility-filtering's OON drop rule of the
   identical name — the clearest end-to-end producer-to-consumer link in this macro.**
   Significance: HIGH. Evidence class: DIRECT.
   Source: `abuse-enforcement-service/service-lib/rules/enforcement_post.yaml:46-51`
   (action writes `SpamHighRecall`), `visibility-filtering/rules/registry.rs:150-153`
   (`tweet_label::SPAM_HIGH_RECALL_DROP` wired into the OON-only rule list), test at
   `:419-454` confirming the exact in-network-allow/OON-drop behavior.

6. **UserCredV2's follow-graph-derived reputation score is a directly-named, checked-in
   skip gate in both Scarecrow's rule engine and abuse-enforcement-service's YAML rules
   — one of the few reputation scores in this macro with a proven behavioral
   consequence, not merely a plausible one.**
   Significance: MEDIUM–HIGH. Evidence class: DIRECT.
   Source: `user-cred-v2/UserCredV2.scala:13-19` (score formula),
   `user-cred-v2/Edge.scala:13-19` (Flock/follow-graph input),
   `scarecrow/legacy/StratoRegistry.scala:120-135` (`GetUserCredV2` Botmaker function),
   `abuse-enforcement-service/service-lib/rules/enforcement_user.yaml:25-31`
   (`pagerank_skipped` gate on `cred.is_high || cred.score >= 50.0`).

7. **Post-to-account NSFW label aggregation (`safety-label-user-agg`) is hard-capped to
   producing exactly two output labels regardless of external rule configuration —
   narrower in scope than its name might suggest.**
   Significance: MEDIUM. Evidence class: DIRECT.
   Source: `safety-label-user-agg/postToUserLabelRules.strato:96-99`
   (`allowedApplyUserLabels = Set("POSSIBLY_NSFW_ACCOUNT", "NSFW_HIGH_PRECISION")`).

8. **Index-time post-safety admission (`shouldDropPostByVF`) is viewer-less and
   universally scoped at the stricter OON policy — meaning a post can be permanently
   excluded from Phoenix retrieval for every future viewer based on a single,
   context-free evaluation, while remaining fully reachable through Thunder or
   SimClusters.**
   Significance: HIGH. Evidence class: DIRECT (the call site, safety level, and
   fail-open behavior); STRONG_INFERENCE (that this creates a real behavioral asymmetry
   with Thunder/SimClusters, which is established from `01_retrieval.md`'s independent
   confirmation that neither calls VF).
   Source: `phoenix-rankall-strato/lib/eventProcessing.strato:246-264`.

9. **Scarecrow's account-label-write action (`SetUserLabel`) has a checked-in, silent
   dark-mode no-op path — a shadow-testing mechanism that could make a rule appear to
   fire (metrics/logs) without actually writing the label VF would act on.**
   Significance: MEDIUM. Evidence class: DIRECT (the code path);
   UNKNOWN (current dark-mode configuration state).
   Source: `scarecrow/legacy/ActionerRegistry.scala:52-54`.

10. **`allow_for_you_recommendations`'s write path remains entirely unestablished in
    this snapshot; its position in the Gizmoduck schema (adjacent to user-preference
    toggles, not enforcement flags) is new but weak supporting context, not resolution.**
    Significance: MEDIUM (carried forward as an explicit open question from S01-F008).
    Evidence class: UNKNOWN (write path); POSSIBLE (schema-neighborhood inference).
    Source: `thunder/schema/user.rs:5969,6042,6472,6798-6799` (field definition only);
    repo-wide search confirmed no other reference.

## What remains unknown

- What actually sets `Gizmoduck.allow_for_you_recommendations = false` — no write path
  in this snapshot (S01-F008, still open).
- Botmaker/Scarecrow's actual rule conditions — only the engine and action primitives
  are checked in.
- Whether Grox's `UnifiedPostAnnotations` boolean flags feed VF's separate
  `SafetyLabelType` label system, or are consumed only by phoenix-rankall's admission
  logic — not traced.
- Where `pnsfwmedia`'s own classifier output is written or consumed downstream.
- Agatha's direct consumers beyond the one indirect HSS-feature-store link found.
- BDSM's exact operating-point thresholds (deliberately redacted in this release) and
  its precise wiring to `abuse-enforcement-service` (plausible from README text, not
  independently traced end to end).
- `VFCandidateHydrator`'s exact socialgraph-relationship data source
  (`viewer_blocks_author`/`viewer_mutes_author`/etc.) — not independently re-opened this
  pass; assumed to parallel Home Mixer's own socialgraph query hydrators (S01) but not
  confirmed identical.
- VF's `FallbackCacheMode` and Scarecrow's `darkMode` live configuration states.
- Abuse-enforcement-service's rule-evaluation order semantics (first-match vs.
  all-evaluated) — inferred from rule ordering and skip-gate placement, not confirmed
  by reading the evaluation engine itself.
- Whether VF runs on any Home Mixer pipeline besides the primary
  ScoredPosts/ForYou path.
- Full internals of `nsfw_age_gating.rs` (654 lines) and `tes_rules.rs` (614 lines) —
  registry placement and test-confirmed behavior established; line-by-line logic not
  read.
- Deep internals of Grox's `reply_spam`/`ptos`/`mm_emb` flows beyond the UPA flow traced
  here.

## What the final macro needs to answer

Explicit handoff to the final synthesis macro (Phoenix training/model architecture,
runtime configuration/experiments, operational/public-vs-production boundary,
transparency tooling):

- Whether any of the checked-in defaults surveyed across all four rapid reports
  (retrieval, ranking, eligibility) reflect actual production values — this requires
  the GrowthBook/feature-switch/decider runtime state this snapshot never exposes.
- `value_model_gate.rs`/dwell-regret production rollout state (from `02_ranking.md`).
- A consolidated view of every place this repository explicitly marks something as
  redacted, mirrored, or externally-sourced (BDSM's thresholds, abuse-enforcement's
  GrowthBook mirror, Botmaker's absent rules, param.rs's feature-switch mirror) — a
  useful index for understanding this snapshot's overall transparency boundary.
- Whether the transparency/public-repository tooling itself (if any exists in this
  snapshot) documents which of these systems are actively serving production traffic.

## Source coverage note

**Deep-read in full**: `home-mixer/candidate_hydrators/vf_candidate_hydrator.rs`,
`home-mixer/filters/{vf_filter,ancillary_vf_filter,self_tweet_filter,ineligible_subscription_filter}.rs`;
`visibility-filtering/{filter,filter_tweets}.rs`, `rules/{mod,registry,socialgraph_rules}.rs`;
`visibility-filtering-client/{vf_client,models}.rs`; `botmaker/src/scala/com/twitter/botmaker/rule/{EventProcessor,EventEvaluator,RuleResult}.scala`
plus the first ~140 lines of `RuleEvaluator.scala`; `scarecrow/legacy/{ActionerRegistry,SpamLabelStoreRegistry,StratoRegistry(partial),DownstreamServices(partial)}.scala`;
`user-cred-v2/{UserCredV2,Edge,UserMass(partial)}.scala`;
`safety-label-user-agg/{safetyLabelToUserLevelAggregationV2Processor.strato,postToUserLabelRules.strato(first ~120 lines)}`;
`abuse-enforcement-service/service-lib/rules/{enforcement_user,enforcement_post}.yaml` (both
in full), `service-lib/src/decision.rs`; `grox/flows/upa/{constants.py,task_write.py(first ~90 lines)}`;
`bdsm/README.md` in full plus targeted grep sections of `score_results_sink_focal.py`;
`media-model-proxy/README.rst`; `pnsfwmedia/model_experimental.py` (first ~60 lines);
`phoenix-rankall-strato/lib/eventProcessing.strato`'s `shouldDropPostByVF` function and
surrounding context; `home-mixer/filters/brazil_2026_election_filter.rs` (header, list-size
test, `is_excluded_author`/`should_remove`/`filter` logic — not the full 665-entry list
body); `agatha/thrift/agatha.thrift` in full.

**Mechanically searched/surveyed, not deep-read**: full directory listings and file-size
census for `agatha/` (90 files), `bdsm/` (46 files), `botmaker/` + `botmaker-rules/`
(565 files combined), `grox/` (165 files), `media-model-proxy/` (97 files),
`user-cred-v2/` (9 files, most opened), `visibility-filtering/` (63 files),
`scarecrow/` (32 files); repo-wide greps for `allow_for_you_recommendations`,
`shouldDropPostByVF`, `FlattenedBlinkScore`/`UserPrediction`, and `UserCredV2` consumer
sites.

**Intentionally not exhaustively read**: `visibility-filtering/rules/{nsfw_age_gating,
nsfw_interstitial,tes_rules,tweet_flag_rules,tweet_label_drops,user_label_drops}.rs`
(1,000+ combined lines — role and effect established via `registry.rs`'s construction
site and its extensive, directly-cited unit tests, not read line-by-line);
`bdsm/runtime/score_results_sink_focal.py` beyond targeted grep sections (1,689 lines);
`bdsm/runtime/{model,heads,loss,feature_norm}.py` (model architecture internals — role
established from README, not independently verified against source); the ~313 Java
files under `botmaker/src/java/` (the DSL compiler/runtime internals beyond what
`rule/*.scala` already established); `grox/core/` (165-file LLM orchestration framework
underlying every Grox flow — only the UPA flow's write path was traced);
`abuse-enforcement-service/service-lib/src/service.rs` beyond its entry-point signatures
(2,598 lines; the actual per-request evaluation loop, rate limiting, and dedup-cache
mechanics were not read); `agatha/scalding/`, `agatha/hub/` (the actual mass-propagation
job and PMI feature-extraction internals — only the thrift output schema was read);
`user-cred-v2/UserCredV2App.scala` (the offline job entry point); the full 665-entry
Brazil-2026 account ID list body.
