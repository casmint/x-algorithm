# Glossary

A quick-reference companion to `HOW_FOR_YOU_WORKS.md`. Each entry says what the thing is,
roughly where it sits in the system, and — where it matters — what it is commonly
confused with.

---

**Home Mixer** — The application that orchestrates a For You (or Ranked Following, or
Following) response end to end. It is not a thin coordinator that "calls out" for
everything: a substantial share of the pipeline — RankingScorer's scoring, all
pre-scoring and post-selection filters, and the selectors that assemble the final
response — runs as ordinary code directly inside the Home Mixer process, with no RPC
involved. Other stages use remote dependencies — Phoenix, VMRanker, visibility
filtering, and the backends behind several retrieval sources (though not all: the
retrieval-source abstraction itself covers a mix of remote calls and at least one local
cache path — see §3). It is *not* the same thing as Phoenix — Home Mixer is the
orchestrator, Phoenix is one of several things it calls.

**Phoenix** — The machine-learning model that predicts how likely a viewer is to do
various things (favorite, reply, retweet, report, watch, ...) with a given candidate post.
It has a ranking-facing side (`PredictNextActions`, called by `PhoenixScorer`) and a
retrieval-facing side (`RetrieveTopKCandidates`, called by the Phoenix retrieval
sources) — these are two different services with two different jobs, not one thing doing
double duty. Phoenix predicts; it does not decide what to show. It is **not** "the
algorithm" — the feed you see is the product of Phoenix plus at least five other
independent systems.

**Phoenix rankall** — Shorthand for `phoenix-rankall`, the continuously-running,
per-request-independent ingestion pipeline that decides whether a post is admitted into
Phoenix's *retrieval* index at all. It runs once per post (on creation, and again each
time its favorite count crosses a power-of-two threshold), not once per viewer request.
Community posts, replies, and retweets are excluded from its mainstream indices
regardless of engagement. This is a completely different mechanism from visibility
filtering, even though both can result in a post never being shown — rankall's decision
is made once, for everyone, before any request exists; visibility filtering's decision is
made per viewer, per request.

**Phoenix ranking / `PredictNextActions`** — The gRPC service `PhoenixScorer` calls to get
per-candidate action predictions during scoring. Distinct from Phoenix retrieval.

**Phoenix retrieval / `RetrieveTopKCandidates`** — The gRPC service `PhoenixSource`,
`PhoenixTopicsSource`, and `PhoenixMOESource` all call to pull candidates out of the index
`phoenix-rankall` built. All three sources use this identical mechanism; they differ only
in which index cluster they query and under what request conditions they're allowed to
run.

**Thunder** — A standalone in-memory service that indexes recent posts by author and
serves them to Home Mixer as the in-network retrieval source. No ranking model is
involved — results are recency-sorted. It is the only retrieval source not disabled by
an "in-network-only" request flag, because it's already inherently in-network.

**TweetMixer** — An external recommendation service Home Mixer calls as a client. Its
internal retrieval algorithm is not part of this repository — only the request/response
contract is. Disabled by default in the checked-in configuration.

**SimClusters** — An out-of-network retrieval source that finds posts similar to ones the
viewer recently engaged with, using a precomputed nearest-neighbor embedding space. It is
seeded by *recent engagement*, not a static long-term interest profile — a viewer with no
recent engagement signals gets zero SimClusters candidates.

**PhoenixTopics** — `PhoenixTopicsSource`: the same retrieval mechanism as Phoenix
retrieval generally, restricted to requests that are browsing a specific topic, and told
which topic entities to filter for. Not a separate algorithm from `PhoenixSource`.

**PhoenixMOE** — `PhoenixMOESource`: an alternate Phoenix retrieval variant pointed at a
different index cluster, off by default. "MOE" is never expanded anywhere in this
repository; "mixture of experts" is a plausible but unconfirmed reading of the acronym.

**CachedPosts** — `CachedPostsSource`: not a retrieval mechanism at all. When a large
enough recently-scored candidate set exists in a short-lived cache, this source re-serves
it verbatim instead of any of the other six sources running. See also **caching**.

**RankingScorer** — The component that turns Phoenix's per-action predictions into one
number per candidate, by multiplying each predicted probability by a checked-in weight
and summing, then applying author-diversity, out-of-network, and cold-start adjustments
on top. Runs entirely inside Home Mixer — no external call. Not the same thing as
Phoenix (which predicts) or VMRanker (which runs after it).

**VMRanker** — A separate Rust service that runs after RankingScorer. Two different
defaults matter here, and they're easy to conflate: Home Mixer's checked-in *request*
default asks VMRanker for DPP-based diversity selection on every call, but the VMRanker
*server's* own checked-in default (`--dpp-enabled=false`) means the server doesn't
actually run DPP unless that flag is on — when it's off, the checked-in implementation
just echoes the incoming scores back unchanged. See §8 for the full picture. Its full
server-side algorithm is checked into this repository — it is **not** an external,
unpublished system, a correction worth stating explicitly since an earlier reading of
this material described it that way.

**DPP** — Determinantal point process: the algorithm VMRanker's server runs, when it
runs it, to select a subset of candidates that is jointly high-scoring and mutually
dissimilar (as measured by embedding similarity), rather than just taking the top N by
score. Home Mixer's checked-in request default asks for DPP selection on every call; the
VMRanker server's own checked-in default (`--dpp-enabled=false`) means it doesn't
actually run unless that flag is on — see **VMRanker**. When it does run, selected
candidates keep their prior score; rejected ones are returned with a score of exactly
zero.

**VF / Visibility Filtering** — The system that decides, per viewer and per post, whether
a post is allowed to be shown at all — a check entirely separate from ranking. Runs after
the top-50 candidates are already selected. Produces Allow, Interstitial, or Drop per
post. Not the same thing as ranking: a post can score highly and still be Dropped by VF.

**VF policy** — One of two rule sets VF evaluates a post under, depending on whether it's
in-network or out-of-network relative to the viewer. See **TimelineHome** and
**TimelineHomeRecommendations**.

**TimelineHome** — The more permissive VF policy, applied to in-network content. Mainly
covers account-state issues (suspended/deactivated authors), blocks/mutes, legal
takedowns, and hard NSFW cases.

**TimelineHomeRecommendations** — The stricter VF policy, applied to out-of-network
content (and ancestors/quotes/retweets pulled in from outside the follow graph).
Everything TimelineHome checks, plus roughly two dozen additional drop rules for spam,
abuse, malicious URLs, and NSFW/violence labels that simply don't apply in-network.

**Gizmoduck** — The account-state service. Unlike the genuinely background label-producing
systems below, it's queried live and synchronously on every request — by Home Mixer's own
query construction and, separately, by visibility filtering's per-candidate evaluation.
Holds account safety flags (suspended, deactivated, NSFW-flagged), user labels written by
Scarecrow and other systems, and various account metadata and preference fields — but
*not* follow/block/mute relationships, which come from a separate social-graph client. It
is a consumption point, not a detector — nothing in this repository writes new detection
logic *inside* Gizmoduck itself.

**Botmaker** — A general-purpose, compiled-rule event-processing engine. It is not itself
a source of any specific rule, not a ranking system, and not the same thing as
**Scarecrow**. Think of it as the engine a rule set runs on, not the rule set itself.

**Scarecrow** — The specific, named production deployment of Botmaker used for spam and
abuse detection. A real, 20-rule checked-in subset of its production rules exists in this
repository (`botmaker-rules/scarecrow/`), each with real thresholds and marked active.
This is a partial, not necessarily complete, public rule corpus — "no rules are public"
and "all production rules are public" are both wrong readings.

**Agatha** — A batch system computing graph- and behavior-derived account reputation
scores. Its own formal output types have no directly-traced consumer in this repository,
but specific named health-signal features it produces are consumed by two checked-in
Scarecrow rules, which write labels called `AGATHA_SPAM` and `AGATHA_SPAM_TOP_USER` —
labels that do not appear anywhere in visibility filtering's rule set under those exact
names, so their specific effect on For You is not established here.

**BDSM** — Behavioral Detection Sequence Model. Despite the acronym, this is **not** an
NSFW or adult-content model — it's an anti-bot / inauthentic-behavior detector, a
transformer classifying a user's recent action sequence across eight categories (bot-like
following, liking, replying, retweeting, and similar). Its real operating thresholds are
deliberately redacted in this public release.

**Grox** — An LLM-based content-understanding system that classifies posts (NSFW, gore,
spam-like, and similar boolean flags) once they cross an engagement threshold. Its output
feeds Phoenix's retrieval-index admission logic directly. Separately, a checked-in
Scarecrow rule (`GroxTweetProcessor`) consumes Grox's spam score and writes a tweet label,
`RISKY_HIGH_VIZ_REPLY` — no downstream consumer of that label is confirmed in this
snapshot.

**UserCredV2** — A PageRank-style account credibility score computed from the real follow
graph. The most pervasively-consumed reputation score this system traces: used directly
as a skip gate in abuse-enforcement-service's rules, and — one layer removed — it is the
literal implementation behind `IsHighPageRankUser`, a skip-gate used across nearly all 20
checked-in Scarecrow rules.

**abuse-enforcement-service** — A checked-in Rust service whose actual production rule
files (mirrored from an external config system) are present in this repository. Runs as a
Kafka consumer reacting to already-flagged accounts/posts, not a per-request check. Its
output vocabulary is small: suspend, add a label, or issue a challenge.

**Under the Hood** — The one user-facing transparency surface described in this
repository. It's a monthly, per-account, per-label aggregate report (how many of your
posts carried or lost a given safety label, compared to a similar-account cohort). It is
**not** a ranking debugger — it exposes no Phoenix predictions, no RankingScorer or
VMRanker output, and cannot explain why any single post was filtered.

**GrowthBook** — The external configuration system several checked-in files in this
repository describe themselves as periodically mirrored copies of (via "mirrored from
...; last sync ..." header comments). Its actual live contents are not part of this
snapshot.

**Feature Switch** — The general mechanism by which a checked-in default value can be
overridden per request, based on matching a request's attributes (user ID, country,
language, client version, account age, and similar — roughly fifteen concrete attributes
in total). This repository shows the matching machinery in detail; it never shows a live
override value.

**Decider** — A separate, boolean-style runtime toggle layer, distinct from ordinary
feature switches, used in a few places in this system to gate which server or code path
handles a request (for example, whether a Phoenix cluster override applies, or whether an
index-admission check uses a Rust or legacy code path). Like feature switches, this
repository shows the gate's existence and logic but never its live value.

**IN / in-network** — A post from an account the viewer follows. In-network content gets
the more permissive `TimelineHome` visibility policy and, for original posts, no
out-of-network ranking discount (though by current checked-in default, in-network
*replies and retweets* do still receive the same discount out-of-network content gets).

**OON / out-of-network** — A post from an account the viewer does not follow. Subject to
a ranking discount (0.75× by default, 0.5× for topic requests) and the stricter
`TimelineHomeRecommendations` visibility policy with roughly two dozen additional drop
rules.

**Interstitial** — A visibility-filtering outcome where the post is still delivered to
the client but flagged so the client can render a warning (typically a tap-through
content notice) before showing it. **Not** the same as a Drop — the content still reaches
the client. Confusing the two misdescribes a large share of the moderation-relevant rules
in this system.

**Drop** — A visibility-filtering outcome where the post is removed by Home Mixer before
the response is ever sent to the client. The only VF outcome that actually results in the
viewer never receiving the post.

**Semantic ID / SID** — A compact identifier attached to a post, used by Phoenix's
retrieval and (most plausibly) ranking paths as a stand-in for richer content
representation, rather than sending raw post text or media with every request. The
system that resolves a semantic ID into whatever content representation the model
actually uses is not shown in this repository — only the identifier's existence and its
presence in requests is directly established.
