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
one link — and shows more of it than an earlier pass through this material found.
**Botmaker** is a large, general-purpose, compiled-rule event-processing engine (an
ANTLR-defined DSL, hundreds of Java/Scala files implementing the runtime). **Scarecrow**
is the specific, named production deployment of Botmaker for spam/abuse. A first pass
through this repository, searching only `botmaker/`, concluded no concrete rule
definitions were checked in — that was wrong. A separate top-level directory,
`botmaker-rules/scarecrow/`, contains 20 real, checked-in `.bot` rule definitions (every
one read for this report) plus 53 supporting `.df` derived-feature files. These are not
toy examples: they carry real IDs, real numeric thresholds, real expiry dates, and
`isActive: 'true'` on every single one. They directly consume Grox's spam score, Agatha's
health scores, URL-reputation verdicts, and NSFW media-classification scores, and they
write real tweet/user labels — `SPAM`, `SPAM_HIGH_RECALL`, `NSFW_HIGH_PRECISION`,
`NSFW_HIGH_RECALL`, `NSFW_CARD_IMAGE`, `NSFW_NEAR_PERFECT`, `GORE_AND_VIOLENCE_HIGH_PRECISION`,
`MALICIOUS_URL`, `AGATHA_SPAM`, `AGATHA_SPAM_TOP_USER`, `RISKY_HIGH_VIZ_REPLY`,
`COPYPASTA_SPAM`, and others — via the exact same `SetUserLabel`/`TweetRtfApplyLabel`
primitives already established. Several of those exact label names are, by name, the
same ones VF's `tweet_label_drops.rs`/`user_label_drops.rs` consume — a real,
independently-verifiable producer-to-consumer chain, not merely a plausible one (full
table below). This does **not** mean the complete production rule corpus is public: this
is a checked-in *subset*, and whether it's the whole thing, whether `isActive: 'true'` in
this snapshot equals currently-live in production, and whether an external rule/package
system layers more rules on top, are all genuinely unknown from this repository. The
corrected posture is neither "no rules are public" nor "all rules are public" — it's "a
real, non-trivial, exact-label-traceable subset is public."

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
question is even asked. A second, independent Grox output reaches Scarecrow directly:
`GroxTweetProcessor.bot` (id `25026`, `isActive: 'true'`, event `health_side_effect`,
sub-event `groxScore`) reads a Grox-produced `spamScore` and, at `spamScore >= 0.97`
(skipping conversation-author self-replies and high-PageRank/skip-listed/gray-verified
accounts), writes a tweet-level `RISKY_HIGH_VIZ_REPLY` label with a 14-day TTL. That
exact label name was **not found anywhere in visibility-filtering's rule set** (direct
grep) — its downstream consequence, if any, is not traced in this snapshot; the name
itself ("risky high-visibility reply") is suggestive of a reply-ranking/downranking
consumer rather than a Drop/Interstitial one, but this report does not assume that from
the name alone. **Media understanding** contributes a parallel, narrower signal:
a small classifier (`pnsfwmedia`) that scores an individual piece of media as NSFW by
combining a frozen CLIP image embedding with two *account-level* signals — a
calibrated NSFW score from **Agatha** and a separate text-based NSFW user score — meaning
a media classification here is not purely about the pixels, it's blended with the
uploading account's own history.

**Account reputation systems** in this snapshot present three genuinely different
pictures of "does a score matter," and Agatha's picture changes materially once
`botmaker-rules/scarecrow/` is included. **Agatha** computes graph/behavior-derived
user-level scores; its thrift schema (`FlattenedBlinkScore`, `UserPrediction`) has no
direct consumer anywhere in this repository *by those type names* — but its *named
health-signal features* absolutely do. Two checked-in, `isActive: 'true'` Scarecrow bot
rules call `GetUserHealthScores(userId, ["AgathaAllSpamReportsPerFav", "AgathaSpamSuspended", ...])`
with real numeric thresholds (e.g. `AgathaSpamSuspended > 0.98`) and, on match, write real
labels — `AGATHA_SPAM` (a tweet label, 7-day TTL) and `AGATHA_SPAM_TOP_USER` (a user
label, via `SetUserLabel`, also 7-day TTL). That is a real, traced, checked-in
producer→consumer chain from Agatha's health scores to concrete account/tweet actions —
correcting an earlier conclusion that no consumer existed. What this chain does **not**
do, importantly: neither `AGATHA_SPAM` nor `AGATHA_SPAM_TOP_USER` appears anywhere in
visibility-filtering's rule set by that exact name — they are not the generic `SPAM`/
`SPAM_HIGH_RECALL` labels VF drops on, and this report does not assume they're
equivalent merely because the names sound related. Agatha's calibrated NSFW score
separately resurfaces inside the media-NSFW classifier (`agatha_calibrated_nsfw_score`),
a second, independent consumption path. **BDSM** (Behavioral Detection Sequence Model)
is the opposite case: a fully-specified, self-documenting transformer over a user's
action sequence, an 8-head bot/spam classifier, with its *own* dedicated
results-processing pipeline that performs graduated enforcement — CAPTCHA/liveness
challenges for borderline cases, suspension for high-confidence ones — and an explicit,
git-committed note that its actual decision thresholds are redacted from this public
release (shipped as an obviously-invalid `9.99` sentinel) specifically so the detection
boundary can't be reverse-engineered. **UserCredV2** is the most pervasively-consumed
case, and more so than first established: a PageRank-style credibility score computed by
propagating "mass" along the real follow graph (Flock edges), log-transformed into a
bounded 0–100 score. `abuse-enforcement-service`'s YAML rules query it directly by name
(`cred.score >= 50.0`). Inside Scarecrow, the connection is one layer removed but just as
concrete: the derived feature `IsHighPageRankUser` — used as a skip-gate in nearly every
one of the 20 checked-in Scarecrow bot rules — is itself implemented as
`GetUserCredV2(userId).score >= 54` (with a `PREDICTED_HIGH_PAGE_RANK` label and a
>25,000-follower fallback for users without a cred score). That means UserCredV2 doesn't
just sit exposed as a callable function — it is the literal mechanism gating whether the
large majority of Scarecrow's checked-in enforcement rules apply to a given account at
all. This is about as close to "score demonstrably changes an outcome" as this kind of
tracing gets.

**Abuse-enforcement-service** is the final decision point this repo shows clearly. Its
actual rule files (`enforcement_user.yaml`, `enforcement_post.yaml`) *are* checked in —
mirrored from a live GrowthBook config, dated in the file header — the same posture now
established for Scarecrow's `.bot` rules, though the two systems' rules were found in
different ways (abuse-enforcement-service's are the whole file; Scarecrow's checked-in
set is an explicitly partial subset of unknown completeness). Its production trigger is a Kafka consumer, not a per-request call —
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
decision, not a per-viewer one. The Rust-VF branch of this check explicitly fails open on
any caught exception (try/catch around both the decider fetch and the verdict fetch); the
legacy Scala branch's failure semantics on an actual fetch/execution exception are not
independently established from this snapshot — see the precise breakdown below. The
practical consequence, where it does fail open: a post that would only be dropped under the *stricter* OON policy
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
  Botmaker/Scarecrow rules — a checked-in SUBSET is public (botmaker-rules/scarecrow/,
  20 .bot rules read) — write account/tweet labels via SetUserLabel (Gizmoduck) /
  TweetRtfApplyLabel/SetLabel (Manhattan); completeness of the corpus and production
  isActive state are UNKNOWN
  Abuse-enforcement-service (Kafka-triggered, checked-in YAML rules) reads
  score.labels from named upstream detectors, writes suspend/label/challenge
  UserCredV2 (follow-graph PageRank-style score) gates OUT of enforcement in BOTH
  abuse-enforcement-service (direct) AND Scarecrow (via IsHighPageRankUser, which
  is itself implemented as GetUserCredV2(userId).score >= 54) — not a VF rule input
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
- **The decider fetch itself fails open**: `useRust = try { decider.fetch(...) }
  catch { case _ => false }` — if the decider lookup throws, `useRust` becomes `false`
  and the legacy branch runs instead; this is DIRECT regardless of which branch handles
  the post.
- **The Rust-VF branch explicitly fails open on a caught verdict-fetch exception**:
  `verdictOpt = try { fetch(...).v } catch { case _ => None }`, then
  `verdictOpt.getOrElse(false)` — a caught exception or a successfully-returned-but-empty
  verdict both resolve to "don't drop." DIRECT.
  - **On the legacy branch**, the code is `#Tweet<visibility/service/shouldDropTweetV2>.fetch(...).v.getOrElse(false)`
    — **not** wrapped in a local try/catch. DIRECT: a *successful* fetch that legitimately
    returns no verdict (`.v` is `None`) becomes `false` (don't drop) via `.getOrElse`.
    UNKNOWN: what happens if the legacy `.fetch(...)` call itself throws — whether Strato's
    `.fetch`/`.v` accessor pattern fails open, fails closed, or propagates an exception
    that aborts the whole enclosing job/record is not established from this snapshot, and
    this report does not claim fail-open behavior for that specific case without
    published evidence of Strato's fetch semantics.
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
estimates) — DIRECT, these are real, well-typed outputs. **No consumer of those specific
thrift *types* was found by that name** (`grep` across `.scala`/`.rs`/`.strato`/`.py`
outside `agatha/` for `FlattenedBlinkScore`/`UserPrediction`/`UserQuantilePrediction`
returned nothing) — but Agatha's *named health-signal features* are consumed directly,
concretely, and repeatedly by checked-in Scarecrow rules:

- `AgathaSpamProduction__ApplySearchTopTweetLabel.bot` (id `20998`, `isActive: 'true'`,
  event `tweet`): calls `GetUserHealthScores(spammerId, ["AgathaAllSpamReportsPerFav",
  "AgathaSpamSuspended"])`, and on `AgathaAllSpamReportsPerFav > 0.9975` OR
  `AgathaSpamSuspended > 0.98` (skipping high-PageRank/skip-listed/gray-verified
  accounts) writes a tweet-level `AGATHA_SPAM` label with a 7-day TTL via
  `SetTweetRtfApplyLabelWithExpirationMs`.
- `ProductionAgatha__FilterOutOrganicNotifications.bot` (id `21278`, `isActive: 'true'`,
  event `new_send_notification_write`): calls `GetUserHealthScores(spammerId,
  ["AgathaSpamSuspended", "AgathaAllSpamReportsPerFav", "AgathaSpamReportsPerFav"])`, and
  on any of three thresholds (`>0.99`/`>0.999`/`>0.999` respectively) writes a
  user-level `AGATHA_SPAM_TOP_USER` label via `SetUserLabel` (7-day TTL), plus a
  6-day "remediation fatigue" suppression so the same user can't re-trigger it
  immediately.

This is a real, checked-in, exact-threshold producer→consumer chain from Agatha's health
scores to concrete labels — correcting an earlier pass's conclusion that no consumer
existed. **What it does not establish**: neither `AGATHA_SPAM` nor
`AGATHA_SPAM_TOP_USER` appears anywhere in visibility-filtering's rule set by that exact
name (confirmed by direct grep across `visibility-filtering/`) — they are *not* the
generic `SPAM`/`SPAM_HIGH_RECALL` labels VF's rules act on, and this report does not
assume equivalence merely because the names sound related. Whatever consumes
`AGATHA_SPAM`/`AGATHA_SPAM_TOP_USER` (a notification-filtering system, a search system,
or something else) is not shown reaching For You/VF in this snapshot. Separately,
Agatha's calibrated NSFW score also resurfaces as a named feature
(`agatha_calibrated_nsfw_score`) inside the media-NSFW classifier described below — a
second, independent consumption path, reached through an intermediate "Health Signal
Service" (HSS) feature store this repo doesn't show the write-side plumbing for
(STRONG_INFERENCE that this is genuinely Agatha's output, not DIRECT, since the
HSS-store connection itself isn't traced).

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

**UserCredV2** (`user-cred-v2/`): the most pervasively-consumed reputation system in this
macro, more so than an earlier pass established. Input: the real follow graph, sourced
from Flock edges (`user-cred-v2/Edge.scala:13-19`, `fromFlockEdge`). Mechanism: each
valid user starts with `mass = 1.0` (`UserMass.calcInitMass`); an iterative
mass-propagation process (not itself opened in this pass — the 9 files present are the
data types and a `UserCredV2App` entry point, not the full offline job) produces a final
`mass`, and `UserCredV2.fromMass` log-transforms it into a bounded `[0, 100]` score
(`score = clamp(165.2 + 7.07 * ln(mass), 0, 100)`, `user-cred-v2/UserCredV2.scala:13-19`)
— structurally a PageRank-style network-authority score. **Two separate, directly-traced
consumers**: `abuse-enforcement-service/service-lib/rules/enforcement_user.yaml:25-31`
uses `cred.is_high`/`cred.score >= 50.0` directly as an unconditional **skip** gate
("pagerank_skipped"). Inside Scarecrow, the connection was previously understated: it is
not merely that `scarecrow/legacy/StratoRegistry.scala:120-135` registers `GetUserCredV2`
as a *callable* Botmaker function — the derived feature `IsHighPageRankUser`
(`botmaker-rules/scarecrow/derived-feature/IsHighPageRankUser.df:3-9`), which is used as
a skip-gate in the *large majority* of the 20 checked-in Scarecrow bot rules (every URL-
quality, NSFW, Agatha-spam, and copypasta rule read for this report includes an
`IsHighPageRankUser`/equivalent check), is itself implemented as
`GetUserCredV2(userId).score >= HighPageRankThreshold` where
`HighPageRankThreshold = 54` (`derived-feature/HighPageRankThreshold.df:2`) — falling
back to a `PREDICTED_HIGH_PAGE_RANK` label or a >25,000-follower heuristic only when no
cred score is available. UserCredV2 is not just exposed to Scarecrow's rules; it is the
literal mechanism gating whether nearly all of Scarecrow's checked-in enforcement
actions apply to a given account at all. This is about as close to "score demonstrably
changes an outcome" as this kind of tracing gets, now established through two
independent, checked-in code paths rather than one.

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

**Correction from an earlier pass through this material**: a first search for Botmaker
rule definitions covered only `botmaker/` and concluded none were checked in. That search
missed a separate top-level directory, `botmaker-rules/scarecrow/`, which contains real,
concrete rule definitions:

- `botmaker-rules/scarecrow/bot/` — **20 `.bot` files, every one read for this report.**
  Each is a complete rule: an `id`, a triggering `event`, a `condition` (the compiled
  DSL's Boolean expression), an `action` (what it does when the condition is true), an
  `expiry` date, and — critically — `isActive: 'true'` on **every single one of the 20**.
- `botmaker-rules/scarecrow/derived-feature/` — 53 `.df` files, supporting reusable
  functions the `.bot` rules call (e.g. `IsHighPageRankUser`, `ApplyNsfwUserLabelOrCreateReport`).
  Not all read; the ones materially affecting a rule's meaning were opened (see Account
  signals above for `IsHighPageRankUser`/`HighPageRankThreshold`, and below for
  `ApplyNsfwUserLabelOrCreateReport`).

**This means the correct transparency posture is neither "no rules are public" nor "all
production rules are public."** DIRECT: this checked-in set exists, contains real
conditions/actions/thresholds/expiries, and every rule read is marked active. UNKNOWN:
whether this is the *complete* production rule corpus, whether `isActive: 'true'` in the
repository is proof of current live activation (rather than a stale snapshot value, the
same caveat already applied to every other "mirrored from config" artifact in this
report), and whether an external rule/package system layers additional rules on top —
`botmaker/`'s `Loader` abstraction (`botmaker/.../loader/Loader.scala`, `fetch()`
abstract) is consistent with rules also being loadable from an external system, which
would coexist with, not contradict, a checked-in subset.

### Inventory of the 20 checked-in Scarecrow rules

Every `.bot` file grouped by family, with event, upstream signal, and output label/action:

| # | Rule (id) | Event | Upstream signal | Output |
|---|---|---|---|---|
| 1 | `GroxTweetProcessor` (25026) | `health_side_effect`/`groxScore` | Grox `spamScore >= 0.97` | tweet `RISKY_HIGH_VIZ_REPLY`, 14d TTL |
| 2 | `AgathaSpamProduction__ApplySearchTopTweetLabel` (20998) | `tweet` | Agatha `AgathaAllSpamReportsPerFav>0.9975` OR `AgathaSpamSuspended>0.98` | tweet `AGATHA_SPAM`, 7d TTL |
| 3 | `ProductionAgatha__FilterOutOrganicNotifications` (21278) | `new_send_notification_write` | Agatha `AgathaSpamSuspended>0.99` / `AgathaAllSpamReportsPerFav>0.999` / `AgathaSpamReportsPerFav>0.999` | user `AGATHA_SPAM_TOP_USER` (`SetUserLabel`), 7d TTL + 6d remediation-fatigue suppression |
| 4 | `BBQDuplicateTextProd` (21711) | `bqbm_scheduled_queries` | BigQuery duplicate-text-cluster job output | tweet `COPYPASTA_SPAM`, rate-limited 100k/min |
| 5 | `BBQDuplicateTextRepliesProd` (21599) | `bqbm_scheduled_queries` | same, reply-text-cluster variant | tweet `COPYPASTA_SPAM` |
| 6 | `FollowFromActorWithPinnedLowQualityOrBadUrl` (20732) | `follow` | pinned tweet contains BAD/LOW_QUALITY URL verdict | user `SPAM_HIGH_RECALL` (`SetUserLabel`), 7d TTL |
| 7 | `LQ_Tweets_With_LQ_URL_Verdict_At_Mention_To_NonFollower` (5239) | `url_event` | LOW_QUALITY URL verdict, mentions non-followers | tweet `SPAM_HIGH_RECALL` |
| 8 | `LQ_Tweets_With_LQ_URL_Verdict_At_Mention_To_NonFollower_v2` (6754) | `url_event` | LOW_QUALITY in chain, last hop not GOOD/WHITELIST | tweet `SPAM_HIGH_RECALL` |
| 9 | `PinnedLowQualityOrBadUrl` (20719) | `user_modification` | newly-pinned tweet has BAD/LOW_QUALITY URL | user `SPAM_HIGH_RECALL` (`SetUserLabel`), 7d TTL |
| 10 | `rtf_tweets_on_unsafe_verdict` (20790) | `url_reputation_change` | URL verdict == `UNSAFE` (backfill) | tweet `SEARCH_BLACKLIST` + `DO_NOT_AMPLIFY` + `UNSAFE_URL` + `MALICIOUS_URL` |
| 11 | `tweet_rtf_or_unrtf_on_bad_verdict` (2002) | `url_reputation_change` | URL verdict == `BAD` (backfill) | tweet `SPAM` |
| 12 | `Tweet_Search_Blacklist_RTF_All_UNSAFE_URL_Sources` (20789) | `url_event` | chain verdict matches `.*UNSAFE` (real-time) | tweet `SEARCH_BLACKLIST` + `UNSAFE_URL` + `DO_NOT_AMPLIFY` + `MALICIOUS_URL` |
| 13 | `Tweet_Spam_High_Recall_RTF_All_Bad_URL_Sources` (3226) | `url_event` | chain verdict matches `.*BAD` (real-time) | tweet `SPAM` (exact BAD) or `SPAM_HIGH_RECALL` (other `*BAD`) |
| 14 | `NSFW_Card_Image_Media_To_URL_Verdict` (7429) | `media_update` | `CARD_IMAGE` + `IsNearPerfectNsfw` | URL-reputation-store verdict `NSFW_CARD_IMAGE`, 7d |
| 15 | `NSFW_Card_Image_URL_to_Tweet_Verdict` (7413) | `url_reputation_change` | verdict == `NSFW_CARD_IMAGE` | tweet `NSFW_CARD_IMAGE` (propagates the URL verdict to every tweet containing that URL, ≤5,000 safeguard) |
| 16 | `NSFW_Grok_Generated_Image_To_URL_Verdict` (24493) | `media_update` | `GROK_GENERATED_IMAGE` + `IsHighPrecisionNsfw`/`IsNearPerfectNsfw` | `GrokMediaNsfwDetection` label, 75d TTL (feeds #17) |
| 17 | `NSFW_Grok_Share` (24603) | `grok_share` | any shared Grok media carries `GrokMediaNsfwDetection` | URL-reputation-store verdict `NSFW_CARD_IMAGE` for the share URL (→ #15) |
| 18 | `nsfw_user_write_user_label` (22358) | `health_side_effect`/`nsfw_user` | (upstream NSFW-user classifier, unnamed in this rule) | user `NSFW_HIGH_PRECISION` + `NSFW_HIGH_RECALL` (via `ApplyNsfwUserLabelOrCreateReport`) |
| 19 | `NsfwTweetMediaProcessor` (22418) | `health_side_effect`/`nsfw_tweet_media` | per-media NSFW `label`/`score` (label 3, score>0.99 / label 3 / label 4) | user `NSFW_NEAR_PERFECT` / `NSFW_HIGH_PRECISION` / `NSFW_HIGH_RECALL` (via `ApplyNsfwUserLabel`) |
| 20 | `ViolenceAndGore_ImageModel_MTT` (20616) | `media_update` | violence/gore precision (image ≥0.6) or raw score (video ≥0.95, avatar/banner ≥0.85) | tweet `GORE_AND_VIOLENCE_HIGH_PRECISION` (images/video, if not high-PageRank/verified) or routed to manual review (avatar/banner always; images/video for high-PageRank/verified accounts) |

**Grouped into families**: Agatha spam (#2, #3) · Grox reply-quality (#1) · URL quality/
spam (#6–13, the largest family — 8 rules translating an external URL-reputation
store's verdicts into tweet/user labels) · NSFW/media (#14–19) · violence/gore (#20) ·
duplicate-content/copypasta, BigQuery-batch-driven (#4, #5).

**Recurring patterns across nearly all 20 rules**: (1) a skip-gate combining
`IsHighPageRankUser` (== UserCredV2 ≥ 54, see Account signals), an `AutoExpiringTempSkipList`,
and `IsUserGrayVerified`/`IsUserGoldVerified` — meaning high-credibility, verified, or
explicitly-skip-listed accounts are structurally exempted from most of these rules before
their core condition is even reached; (2) most write with a **7-day TTL** by default,
several via `SetUserLabel`/`SetTweetRtfApplyLabelWithExpirationMs`; (3) several
NSFW-family rules route to **manual human review** (`CreateRtpReportAsyncProd`) instead
of automatic labeling for exactly the accounts the skip-gate would otherwise exempt, or
for avatar/banner images unconditionally (`ApplyNsfwUserLabelOrCreateReport.df:1-91`,
`ViolenceAndGore_ImageModel_MTT.bot`'s avatar/banner branch) — automatic labeling and
human review are deliberately, precisely partitioned by account type and media category,
not a simple binary.

**Scarecrow's action primitives**, confirmed exactly as before: `SetUserLabel` (Gizmoduck,
default 7-day expiry, silently a no-op under `darkMode`,
`scarecrow/legacy/ActionerRegistry.scala:52-54`), `SetLabel`/`SetLabelWithTtl` (Manhattan,
default 26-hour TTL, `scarecrow/legacy/SpamLabelStoreRegistry.scala:55-104`),
`TweetRtfApplyLabel`/`TweetRtfRemoveLabel` (used pervasively across the 20 rules above,
writing directly to the tweet-level "RTF" label store — the same family of tweet safety
labels VF's `safety_label_source` reads), and `GetUserCredV2`/`GetUserHealthScores`
(read-side, see Account signals).

### Exact producer → VF-consumer label chains

Only rows where the checked-in Scarecrow/abuse-enforcement-service output label name was
independently confirmed, by exact string, against a real VF rule (`grep`-verified in
`visibility-filtering/rules/{tweet_label_drops,user_label_drops,nsfw_interstitial}.rs`).
Rows are included only when both producer and consumer were directly read.

| Rule (producer) | Upstream signal | Label written | Storage/primitive | VF consumer | For You consequence | Evidence |
|---|---|---|---|---|---|---|
| `tweet_rtf_or_unrtf_on_bad_verdict` (2002), `Tweet_Spam_High_Recall_RTF_All_Bad_URL_Sources` (3226) | URL verdict `BAD` | tweet `SPAM` | `TweetRtfApplyLabel` | `tweet_label::SPAM_DROP` — in **`base_home_rules()`, both policies** | Drop, **in-network and OON alike** | DIRECT |
| 7 Scarecrow rules (#7,8,9,12,13 tweet-scoped; #6,9 user-scoped) + `abuse-enforcement-service`'s `act_add_labels_v2`/`act_add_post_labels_v2` | URL/model verdicts, `score.labels` | `SPAM_HIGH_RECALL` (tweet and/or user) | `TweetRtfApplyLabel` / `SetUserLabel` / AES `AddLabelsV2` | `tweet_label::SPAM_HIGH_RECALL_DROP` (tweet) / `user_label::SPAM_HIGH_RECALL_USER_DROP` (user) — **OON only** | Drop out-of-network; allowed in-network | DIRECT |
| `nsfw_user_write_user_label` (22358), `NsfwTweetMediaProcessor` (22418) | health-side-effect NSFW classifiers | user `NSFW_HIGH_PRECISION`, `NSFW_HIGH_RECALL` | `SetUserLabel` (via `ApplyNsfwUserLabelOrCreateReport`/`ApplyNsfwUserLabel`) | `user_label::NSFW_HIGH_PRECISION_USER_DROP`, `user_label::NSFW_HIGH_RECALL_USER_DROP` — **OON only** | Drop out-of-network; allowed in-network | DIRECT |
| `NsfwTweetMediaProcessor` (22418) | per-media NSFW label 3 + score>0.99 | user `NSFW_NEAR_PERFECT` | `ApplyNsfwUserLabel` | `user_label::NSFW_NEAR_PERFECT_USER_DROP` — **OON only** | Drop out-of-network; allowed in-network | DIRECT |
| `NSFW_Card_Image_URL_to_Tweet_Verdict` (7413), fed by #14/#16/#17 | Grok/card-image NSFW classifiers | tweet `NSFW_CARD_IMAGE` | `TweetRtfApplyLabel` | `NSFW_CARD_IMAGE_INTERSTITIAL` (in-network) **and** `tweet_label::NSFW_CARD_IMAGE_DROP` (OON) — same label, two different actions by policy | **Interstitial in-network, Drop OON** | DIRECT |
| `ViolenceAndGore_ImageModel_MTT` (20616) | violence/gore precision/raw-score model | tweet `GORE_AND_VIOLENCE_HIGH_PRECISION` | `TweetRtfApplyLabel` | `GORE_AND_VIOLENCE_INTERSTITIAL` (in-network) **and** `tweet_label::GORE_AND_VIOLENCE_HIGH_PRECISION_DROP` (OON) | **Interstitial in-network, Drop OON** | DIRECT |
| `rtf_tweets_on_unsafe_verdict` (20790), `Tweet_Search_Blacklist_RTF_All_UNSAFE_URL_Sources` (20789) | URL verdict `UNSAFE` | tweet `MALICIOUS_URL` (bundled with `SEARCH_BLACKLIST`/`DO_NOT_AMPLIFY`/`UNSAFE_URL`) | `TweetRtfApplyLabel` | `tweet_label::MALICIOUS_URL_DROP` — **OON only** | Drop out-of-network; allowed in-network | DIRECT (for `MALICIOUS_URL`) |
| same two rules | — | tweet `DO_NOT_AMPLIFY` | `TweetRtfApplyLabel` | `tweet_label::DO_NOT_AMPLIFY_DROP` — **OON only** | Plausible drop out-of-network — **not fully confirmed**: VF also has a separate *user*-level `DO_NOT_AMPLIFY_NON_FOLLOWER_USER_DROP`; this repo does not independently prove the tweet-level RTF store these rules write into is the same store `tweet_label::DO_NOT_AMPLIFY_DROP` reads, only that both use the identical label string at the tweet-level scope | DIRECT (label name/scope match); not independently verified at the storage-wire level |
| `abuse-enforcement-service/enforcement_post.yaml` | `score.model_version`-tagged upstream signals | tweet `RiskyHighVizReply` | `act_add_post_labels_v2` | **not found** in VF's rule set | No confirmed For You consequence in this snapshot | DIRECT (absence) |
| `GroxTweetProcessor` (25026) | Grox `spamScore` | tweet `RISKY_HIGH_VIZ_REPLY` | `TweetRtfApplyLabel` | **not found** in VF's rule set | No confirmed For You consequence in this snapshot | DIRECT (absence) |
| `AgathaSpamProduction__ApplySearchTopTweetLabel` (20998), `ProductionAgatha__FilterOutOrganicNotifications` (21278) | Agatha health scores | tweet `AGATHA_SPAM`, user `AGATHA_SPAM_TOP_USER` | `SetTweetRtfApplyLabelWithExpirationMs` / `SetUserLabel` | **not found** in VF's rule set | No confirmed For You consequence in this snapshot | DIRECT (absence) |
| `BBQDuplicateTextProd`/`BBQDuplicateTextRepliesProd` | BigQuery duplicate-text job | tweet `COPYPASTA_SPAM` | `TweetRtfApplyLabel` | **not found** in VF's rule set | No confirmed For You consequence in this snapshot | DIRECT (absence) |

The table is deliberately as important for its negative rows as its positive ones: this
report already warned against assuming `AGATHA_SPAM == SPAM` from semantic similarity —
tracing the exact strings confirms they are genuinely different labels with genuinely
different (and, for `AGATHA_SPAM`/`RISKY_HIGH_VIZ_REPLY`/`COPYPASTA_SPAM`, currently
untraced) consequences.

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
(`visibility-filtering/rules/mod.rs:86-110`, confirmed by direct unit tests). Precisely,
in declared order: an `Allow` verdict from a rule changes nothing and evaluation
continues to the next rule; the **first** `Interstitial` verdict is retained
provisionally (recorded as the current `worst`, but only if no `Interstitial` has been
recorded yet), and evaluation **continues** past it — a later rule can still override
that provisional interstitial; the **first `Drop` immediately returns from the function**
— every rule after it in the list simply does not run, and that `Drop` is final
regardless of any `Interstitial` recorded earlier. If the loop reaches the end without a
`Drop`, the verdict is whatever `Interstitial` was recorded first (or `Allow` if none
was). Net effect: `Drop` always wins and short-circuits remaining evaluation; among
non-`Drop` outcomes, the first `Interstitial` wins over any later one; `Allow` never
overrides anything. This is exact, tested behavior
(`drop_short_circuits_later_rules`, `first_interstitial_decided_by_sticks_without_short_circuit`,
`drop_after_interstitial_wins`, `visibility-filtering/rules/mod.rs:163-232`), not
inferred.

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
| Phoenix-rankall index-admission VF check (`shouldDropPostByVF`) — decider fetch | any exception | DIRECT fail open — falls back to the legacy branch |
| Phoenix-rankall index-admission VF check — Rust-VF verdict fetch | caught exception, or a successful-but-empty verdict | DIRECT fail open — admission proceeds |
| Phoenix-rankall index-admission VF check — legacy verdict fetch | successful fetch returning no verdict | DIRECT fail open (`.getOrElse(false)`) |
| Phoenix-rankall index-admission VF check — legacy verdict fetch | fetch/execution throws | UNKNOWN — no local try/catch observed; Strato `.fetch`/`.v` failure semantics not established from this snapshot |
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
- Botmaker/Scarecrow's rule *conditions* are checked in for a real, 20-rule subset
  (`botmaker-rules/scarecrow/bot/`), each marked `isActive: 'true'` — but whether that
  flag reflects current live production activation, and whether this 20-rule set is the
  complete production corpus or one slice of a larger external rule/package system, are
  both UNKNOWN.
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

4. **A real, checked-in subset of Botmaker/Scarecrow rule definitions exists in
   `botmaker-rules/scarecrow/` (20 `.bot` rules, all read) — an earlier pass through this
   material, which searched only `botmaker/`, incorrectly concluded no rules were
   public. The corrected posture is a checked-in subset with unknown completeness, not
   an absence of rules and not proof of the full corpus.**
   Significance: HIGH. Evidence class: DIRECT (the 20 rules exist, are readable, contain
   real conditions/actions/thresholds/expiries, and are marked `isActive: 'true'`).
   UNKNOWN: whether this is the complete production rule set; whether `isActive: 'true'`
   in the repository equals current live production activation; whether an external
   rule/package system adds more rules (`botmaker/`'s abstract `Loader.fetch()` is
   consistent with, but does not prove, such a system).
   Source: `botmaker-rules/scarecrow/bot/*.bot` (20 files), `botmaker-rules/scarecrow/derived-feature/*.df`
   (53 files, key ones opened: `IsHighPageRankUser.df`, `HighPageRankThreshold.df`,
   `ApplyNsfwUserLabelOrCreateReport.df`).

5. **`SpamHighRecall`/`SPAM_HIGH_RECALL` is a directly-traced write→read chain to
   visibility-filtering's OON drop rule of the identical name — and, once
   `botmaker-rules/scarecrow/` is included, no longer the only one: `SPAM` (dropped even
   in-network), `NSFW_HIGH_PRECISION`/`NSFW_HIGH_RECALL`/`NSFW_NEAR_PERFECT` (user-level,
   OON-only), `NSFW_CARD_IMAGE` and `GORE_AND_VIOLENCE_HIGH_PRECISION` (interstitial
   in-network, drop OON), and `MALICIOUS_URL` (OON-only) all have equally direct,
   exact-name producer→consumer chains from checked-in Scarecrow rules — see the full
   table above.**
   Significance: HIGH. Evidence class: DIRECT.
   Source: `abuse-enforcement-service/service-lib/rules/enforcement_post.yaml:46-51`
   (action writes `SpamHighRecall`), `visibility-filtering/rules/registry.rs:150-153`
   (`tweet_label::SPAM_HIGH_RECALL_DROP` wired into the OON-only rule list), test at
   `:419-454` confirming the exact in-network-allow/OON-drop behavior; full label-chain
   table in the Botmaker/Scarecrow section above.

6. **UserCredV2's follow-graph-derived reputation score is a directly-named, checked-in
   skip gate in abuse-enforcement-service's YAML rules, and — more pervasively than
   first established — is the literal implementation of `IsHighPageRankUser`, the
   skip-gate used across nearly all 20 checked-in Scarecrow bot rules
   (`GetUserCredV2(userId).score >= 54`) — one of the few reputation scores in this macro
   with a proven behavioral consequence, not merely a plausible one.**
   Significance: MEDIUM–HIGH. Evidence class: DIRECT.
   Source: `user-cred-v2/UserCredV2.scala:13-19` (score formula),
   `user-cred-v2/Edge.scala:13-19` (Flock/follow-graph input),
   `scarecrow/legacy/StratoRegistry.scala:120-135` (`GetUserCredV2` Botmaker function),
   `botmaker-rules/scarecrow/derived-feature/IsHighPageRankUser.df:3-9` and
   `HighPageRankThreshold.df:2` (the pervasive skip-gate's actual implementation),
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
   SimClusters. Its fail-open behavior is DIRECT for the decider fetch and the Rust-VF
   verdict fetch, but the legacy branch's behavior on an actual fetch exception (as
   opposed to a successful empty result) is UNKNOWN.**
   Significance: HIGH. Evidence class: DIRECT (the call site, safety level, decider
   fail-open, and Rust-VF verdict fail-open); UNKNOWN (legacy-branch exception
   propagation); STRONG_INFERENCE (that this creates a real behavioral asymmetry with
   Thunder/SimClusters, which is established from `01_retrieval.md`'s independent
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
- Whether the 20 checked-in Scarecrow `.bot` rules are the complete production rule
  corpus, or one slice of a larger set loaded from an external package/config system;
  whether `isActive: 'true'` in the repository equals current live activation.
- What consumes `AGATHA_SPAM`, `AGATHA_SPAM_TOP_USER`, `RISKY_HIGH_VIZ_REPLY`, and
  `COPYPASTA_SPAM` — all confirmed written by checked-in rules, none found anywhere in
  visibility-filtering's rule set; their actual downstream systems (notification
  filtering, search, reply-ranking, or something else) are not shown in this snapshot.
- Whether the tweet-level `DO_NOT_AMPLIFY` label Scarecrow's URL-verdict rules write is
  stored in the same location `tweet_label::DO_NOT_AMPLIFY_DROP` reads (label-name and
  scope match confirmed; storage-wire identity not independently verified).
- Whether Grox's `UnifiedPostAnnotations` boolean flags feed VF's separate
  `SafetyLabelType` label system, or are consumed only by phoenix-rankall's admission
  logic — not traced.
- Where `pnsfwmedia`'s own classifier output is written or consumed downstream.
- Agatha's consumers beyond the two checked-in Scarecrow rules and the one indirect
  HSS-feature-store link found — whether Agatha's raw `FlattenedBlinkScore`/
  `UserPrediction` thrift outputs (as opposed to the named health-signal features
  Scarecrow consumes) reach any other consumer remains untraced.
- BDSM's exact operating-point thresholds (deliberately redacted in this release) and
  its precise wiring to `abuse-enforcement-service` (plausible from README text, not
  independently traced end to end).
- Legacy-branch (`shouldDropTweetV2`) failure semantics on an actual fetch/execution
  exception at index-admission time — the successful-empty-result case fails open
  (DIRECT); exception propagation is UNKNOWN.
- Which of the 53 `.df` derived features under `botmaker-rules/scarecrow/` were not
  opened, and whether any of them materially change the meaning of a rule beyond what
  was established for the ones read (`IsHighPageRankUser`, `HighPageRankThreshold`,
  `ApplyNsfwUserLabelOrCreateReport`).
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
  redacted, mirrored, partial, or externally-sourced (BDSM's thresholds,
  abuse-enforcement's GrowthBook mirror, Scarecrow's partial-and-unknown-completeness
  rule subset, param.rs's feature-switch mirror) — a useful index for understanding this
  snapshot's overall transparency boundary.
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
body); `agatha/thrift/agatha.thrift` in full;
**`botmaker-rules/scarecrow/bot/` — all 20 `.bot` rule files, in full, this pass**
(`AgathaSpamProduction__ApplySearchTopTweetLabel`, `BBQDuplicateTextProd`,
`BBQDuplicateTextRepliesProd`, `FollowFromActorWithPinnedLowQualityOrBadUrl`,
`GroxTweetProcessor`, `LQ_Tweets_With_LQ_URL_Verdict_At_Mention_To_NonFollower`(`_v2`),
`NSFW_Card_Image_Media_To_URL_Verdict`, `NSFW_Card_Image_URL_to_Tweet_Verdict`,
`NSFW_Grok_Generated_Image_To_URL_Verdict`, `NSFW_Grok_Share`, `NsfwTweetMediaProcessor`,
`nsfw_user_write_user_label`, `PinnedLowQualityOrBadUrl`, `ProductionAgatha__FilterOutOrganicNotifications`,
`rtf_tweets_on_unsafe_verdict`, `tweet_rtf_or_unrtf_on_bad_verdict`,
`Tweet_Search_Blacklist_RTF_All_UNSAFE_URL_Sources`,
`Tweet_Spam_High_Recall_RTF_All_Bad_URL_Sources`, `ViolenceAndGore_ImageModel_MTT`);
**`botmaker-rules/scarecrow/derived-feature/{ApplyNsfwUserLabelOrCreateReport,IsHighPageRankUser,HighPageRankThreshold}.df`
in full, this pass**; targeted `grep`-verified exact-line lookups (not full line-by-line
reads) into `visibility-filtering/rules/{tweet_label_drops,user_label_drops,nsfw_interstitial}.rs`
this pass, confirming the exact `SafetyLabelType`/`LabelValue` constants used in the
label-chain table above.

**Mechanically searched/surveyed, not deep-read**: full directory listings and file-size
census for `agatha/` (90 files), `bdsm/` (46 files), `botmaker/` (492 files) +
`botmaker-rules/` (73 files, of which the 20 `.bot` + 3 `.df` above were deep-read this
pass), `grox/` (165 files), `media-model-proxy/` (97 files), `user-cred-v2/` (9 files,
most opened), `visibility-filtering/` (63 files), `scarecrow/` (32 files); repo-wide
greps for `allow_for_you_recommendations`, `shouldDropPostByVF`,
`FlattenedBlinkScore`/`UserPrediction`, `UserCredV2` consumer sites, and — this pass —
`RISKY_HIGH_VIZ_REPLY`, `AGATHA`, `COPYPASTA`, `SEARCH_BLACKLIST`, `UNSAFE_URL`, and
`DoNotAmplify`/`DO_NOT_AMPLIFY` across `visibility-filtering/` and `home-mixer/`.

**Intentionally not exhaustively read**: `visibility-filtering/rules/{nsfw_age_gating,
nsfw_interstitial,tes_rules,tweet_flag_rules,tweet_label_drops,user_label_drops}.rs`
line-by-line (1,000+ combined lines — role and effect established via `registry.rs`'s
construction site, its extensive directly-cited unit tests, and this pass's targeted
constant lookups); `bdsm/runtime/score_results_sink_focal.py` beyond targeted grep
sections (1,689 lines); `bdsm/runtime/{model,heads,loss,feature_norm}.py` (model
architecture internals — role established from README, not independently verified
against source); the ~313 Java files under `botmaker/src/java/` (the DSL compiler/
runtime internals beyond what `rule/*.scala` already established); the remaining 50 of
53 `.df` files under `botmaker-rules/scarecrow/derived-feature/` (only the three
materially load-bearing ones for the rules read were opened, per this macro's explicit
scope); `grox/core/` (165-file LLM orchestration framework underlying every Grox flow —
only the UPA flow's write path was traced); `abuse-enforcement-service/service-lib/src/service.rs`
beyond its entry-point signatures (2,598 lines; the actual per-request evaluation loop,
rate limiting, and dedup-cache mechanics were not read); `agatha/scalding/`,
`agatha/hub/` (the actual mass-propagation job and PMI feature-extraction internals —
only the thrift output schema was read); `user-cred-v2/UserCredV2App.scala` (the offline
job entry point); the full 665-entry Brazil-2026 account ID list body.
