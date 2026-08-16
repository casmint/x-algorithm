# How X's For You Recommendation System Works
## A source-grounded guide to the August 2026 public algorithm snapshot

This document explains, in plain language, what happens between the moment someone opens
the For You tab on X and the moment a feed of posts appears on their screen. It is based
entirely on a source-code snapshot of `xai-org/x-algorithm` (commit `c65aa179`,
2026-08-15) and on two independent internal research tracks that read that snapshot: a
slower, file-by-file forensic audit (specialist reports "S00" through "S02," covering
documentation claims, Home Mixer orchestration, and feed blending) and a faster
behavior-tracing pass across the rest of the system (five "Rapid" reports covering
retrieval, ranking, safety/visibility, and model/runtime boundaries). Where the two
tracks overlap, they agree; where the rapid track went further, its more detailed reading
is used and flagged as a correction where it narrows something the forensic pass or an
earlier rapid pass left open.

Two things this document is not. It is not a claim about what X's production systems are
doing on any given day — this repository shows code and its checked-in default values,
not live configuration, live model weights, or live feature-switch state, and this
document says so explicitly wherever the distinction matters. And it is not a security or
policy audit — it describes mechanisms, not intentions, and does not speculate about why
any individual choice was made unless the source itself says why.

---

## 1. The biggest misconception to unlearn: Phoenix is not "the algorithm"

If you've heard anything about how X's recommendation system works, you've probably heard
the name "Phoenix." It's tempting to treat Phoenix as a synonym for "the algorithm" — one
model that looks at a post and decides whether you see it. That's wrong, and it's wrong in
a way that makes everything else about this system hard to understand until you unlearn
it.

Phoenix is one component: a machine-learning model that predicts how likely you are to do
things — favorite a post, reply to it, watch its video, report it — if it were shown to
you. It does not decide what candidates to consider in the first place, it does not
compute a final score by itself, it does not decide whether a post is safe to show you,
and it has no say over ads, "Who to Follow" modules, or the other non-post items that
appear interleaved in your feed. Phoenix predicts; other systems decide.

The system that actually assembles your feed is called **Home Mixer**, and the orchestra
metaphor needs one important twist to be accurate: some sections are musicians Home Mixer
directs from a distance, over a call, and others are its own hands playing an instrument
directly. Mixing up which is which — assuming everything Home Mixer touches is a remote
call, or that Home Mixer itself does no ranking or filtering — is the easiest way to
misunderstand this system:

- **Home Mixer** is the orchestrator, and it's more than a conductor waving a baton — a
  substantial share of the actual work happens *inside* the Home Mixer process itself, as
  ordinary code, not as a call to some other service. It receives your request, gathers
  everything it needs to know about you, and both runs local logic and calls out to remote
  services, in a specific order, to assemble the final response.
- **Retrieval systems** (seven of them, described in the next section) go find posts that
  *might* be worth showing you. This is a pool-building step, not a ranking step. Their
  backing mechanism varies source by source — some are calls to separate services, one
  re-serves from an in-process cache — covered in §3.
- **Phoenix ranking** — a remote call — takes that pool and predicts, for each post, the
  probability you'll do each of roughly two dozen different things with it.
- **RankingScorer runs locally, inside Home Mixer, with no remote call.** It converts
  Phoenix's predictions into a single number per post by multiplying each predicted
  probability by a weight and summing the results, then layers on adjustments for things
  like how many posts from the same author already rank above it. The filters that run
  before and after it are the same way: Home Mixer's own local removal logic, not calls to
  anywhere else.
- **VMRanker** — a remote call to a separate service — can apply **DPP** (determinantal
  point process) diversity selection to the already-scored list, re-selecting a diverse
  subset from it so your feed isn't dominated by five near-duplicate posts about the same
  topic (whether it actually does, on a given call, is a separate question — see §8).
- **Visibility filtering** — another remote call — is a completely separate check, run
  after ranking, that decides whether a given post is even allowed to reach you at all — a
  post can score extremely well and still never be shown.
- **BlenderSelector**, back inside Home Mixer itself, takes the surviving, ranked organic
  posts and weaves in ads, "Who to Follow" suggestions, prompts, push-to-home content, and
  other non-post items to build the response you actually receive.
- **Safety and reputation systems** — Agatha, BDSM, UserCredV2, Grox, and
  Botmaker/Scarecrow/abuse-enforcement-service — mostly don't sit in this per-request
  pipeline at all: they run continuously, in the background, producing labels and account
  state that visibility filtering and other systems consume when a request does come in
  (we'll unpack each of these individually in §10). **Gizmoduck is the exception**, not a
  member of that background group: it's a live account-state service that Home Mixer's
  query construction and visibility filtering both query synchronously, on every single
  request.

The distinction worth holding onto isn't just "Phoenix is not the algorithm" — it's three
separate categories: **Home Mixer the orchestrator**, the **local, in-process logic it
runs directly** (RankingScorer, most filters, BlenderSelector), and the **remote
dependencies it calls out to** (Phoenix, VMRanker, visibility filtering, and the backends
behind several retrieval sources). Keeping those three apart, rather than collapsing
everything into "the algorithm," is the single
most useful thing this document can give you before the detail starts.

*Primary evidence: S01 (Home Mixer orchestration), Rapid 01–04 (per-system detail).*

---

## 2. The whole journey, once, before the detail

Before going stage by stage, here is the full path a request takes, roughly in order.
Some of these steps happen at the same time as each other ("concurrently"); others must
happen strictly in sequence because a later step reads what an earlier one wrote. The
repository's own execution engine makes this distinction explicit, and it matters: a
scorer running out of order would read stale data, so the code enforces the order below
exactly.

```
 viewer opens For You
        |
        v
 Home Mixer builds a "query": who is this viewer, who do they follow,
 what have they recently done, what feature-switch bucket are they in
        |                                          (mostly concurrent lookups)
        v
 up to seven candidate sources run at once — whichever are enabled for this
 request — each contributing posts to one pool
        |                                          (concurrent)
        v
 candidate hydration: fill in details about each candidate (block/mute state,
 follow direction, engagement counts, safety flags already on record, etc.)
        |                                          (concurrent)
        v
 pre-scoring filters: remove posts that should never reach a scorer at all
 (duplicates, self-tweets, blocked authors, muted keywords, a specific legal
 exclusion list, subscriber-only content you can't see, etc.)
        |                                          (sequential, eighteen filters
        |                                           in a fixed declared order)
        v
 Phoenix predicts your likely reactions to each surviving candidate
        |
        v
 RankingScorer turns those predictions into one score per candidate
        |                                          (sequential — each of these three
        v                                           scorers reads what the previous
 VMRanker may re-select a diverse top set via DPP                one wrote)
        |
        v
 top 50 candidates by score are kept, everything else is discarded
        |
        v
 visibility filtering runs on those 50 (per-viewer, per-post safety/eligibility check)
        |
        v
 survivors are truncated to 35 organic posts
        |
        v
 BlenderSelector interleaves ads, Who to Follow, prompts, push-to-home content,
 frames, and a feed survey marker into the organic list
        |
        v
 served-history and logging side effects fire in the background (they cannot
 change this response — only future ones)
        |
        v
 response is returned to the client
```

A few things about this diagram are worth calling out precisely, because they're the
parts most likely to be mischaracterized. Whichever of the seven candidate sources are
enabled for a given request genuinely run at the same time and their results are simply
concatenated — there's no interleaving quota or priority order at that step, so which
source found a post has no bearing on its final rank. The pre-scoring filters and the
three scorers, by contrast, run strictly one after another in a fixed declared order,
because each one can depend on state a previous stage set. Visibility filtering happens
*after* the ranked list has already been narrowed to
the top 50 — it does not run on the whole candidate pool, only on the posts that already
made the cut on quality grounds. And the whole organic pipeline above (everything up to
"truncated to 35") is itself just one of several sources feeding a second, outer pipeline
that does the ad/WTF/prompt blending — Phoenix and its scorers never see an ad, a Who to
Follow card, or a prompt; those are added afterward by a completely separate mechanism.

*Primary evidence: S01 (execution-stage ordering and concurrency), S02 (blending layer).*

---

## 3. Retrieval: where posts come from

Nothing gets ranked, filtered, or shown unless some retrieval source finds it first. This
makes retrieval the least glamorous and most consequential part of the system: it defines
the ceiling on what your feed can possibly contain, no matter how good the ranking model
is.

`PhoenixCandidatePipeline` — the pipeline behind a normal For You request — defines seven
candidate sources. For each request, it evaluates every source's own enable condition
first, then runs whichever sources are enabled concurrently among themselves; a disabled
source simply doesn't run, contributing nothing. Two default to disabled and won't
necessarily contribute anything unless a feature switch turns them on; the rest run by
default, subject to further per-source gates described below (and, for cache mode's
effect on all six live sources at once, in §13).

| Source | In/out of network | What it does | Enabled by default? |
|---|---|---|---|
| Thunder | In-network | Looks up recent posts from people you follow | Yes |
| SimClusters | Out-of-network | Finds posts similar to things you recently engaged with | Yes |
| PhoenixSource | Out-of-network | Queries Phoenix's own retrieval index | Yes |
| PhoenixTopicsSource | Out-of-network | Same mechanism, restricted to a topic you're browsing | No dedicated switch — runs only on topic-scoped requests |
| PhoenixMOESource | Out-of-network | An alternate Phoenix retrieval variant, a separate index | No |
| TweetMixerSource | Out-of-network | Calls an external recommendation service | No |
| CachedPostsSource | Neither | Re-serves a recently-computed result instead of retrieving fresh | Only when a valid cache exists |

**Thunder** is the simplest of the group and the one most people would guess exists: a
standalone in-memory service that keeps a rolling window of recent posts, organized by
author, fed continuously by a stream of post-creation and deletion events. When you open
For You, Home Mixer already knows who you follow (from its own social-graph lookup) and
hands that list to Thunder, which returns the most recent posts from those authors — no
model, no ranking, just recency. It also surfaces a specific kind of second-degree
content: a reply from someone you follow, replying to *someone else* you follow, even if
that second person isn't in your own follow list, so mutual conversations between people
you follow show up as a unit. Thunder keeps roughly 48 hours of history by default and
caps how many posts it stores per author.

**SimClusters** works entirely differently. It is not a static "you like sports" profile
attached to your account — it's item-to-item similarity, seeded fresh on every request by
posts you've *recently* engaged with. For each of your recent favorites or other
engagement signals, Home Mixer asks a nearest-neighbor search service to find other posts
that live near that one in a precomputed embedding space. If you have no recent engagement
signals at all, you get zero SimClusters candidates — there is no fallback interest
profile to lean on. Results are capped to roughly the last two days by an internal age
window, in addition to the universal cutoff described below.

**Phoenix retrieval** — the mechanism behind `PhoenixSource`, `PhoenixTopicsSource`, and
`PhoenixMOESource` — is the least intuitive of the three because it works two steps
removed from any individual request. Before your feed request even exists, a separate,
continuously-running ingestion pipeline (internally called `phoenix-rankall`) watches a
stream of post-creation and favorite events and decides, for each post, whether it's
admitted into a retrieval index at all. This decision happens once per post, for every
future viewer, entirely independent of any single request. Two rules matter most here and
are genuinely surprising if you haven't seen them: **replies, retweets, and posts from
community groups are excluded from the mainstream indices outright**, regardless of how
much engagement they get — with one narrower exception: a separate branch triggered only
by favorite events, `search_unfiltered`, is evaluated *before* the reply exclusion runs
and does admit replies (though still not community posts or retweets) into that narrower
branch. Whether `search_unfiltered` is consumed by any live Phoenix retrieval-serving path
is unknown from this snapshot, so this isn't a claim that Phoenix definitely retrieves
replies — only that a flat "Phoenix can never index replies" would be too strong.
Separately, a post's favorite count only re-triggers indexing when it
crosses a *power-of-two* threshold (1, 2, 4, 8, 16, 32...), not on every single like — so a
post's second index update happens at its second favorite, but its third happens only at
its fourth. Posts that fail internal safety checks are also excluded from the mainstream
indices at this stage — there are two independent mechanisms that do this, both covered in
the safety section below. All three Phoenix
retrieval sources — the plain one, the topic-scoped one, and the mixture-style one — use
the *identical* underlying dispatch mechanism; they differ only in which cluster of the
index they query and under what conditions they're allowed to run, not in three separate
algorithms. "MOE" is never expanded or defined anywhere in this snapshot; the most
plausible reading, based on how the parameter names around it are structured, is "mixture
of experts," but this repository never confirms that, so it should be read as an unlabeled
alternate retrieval variant rather than a confirmed acronym.

**TweetMixerSource** calls an entirely external service this repository doesn't include
the internals of — only the request Home Mixer sends and the shape of the response it
gets back are visible here. It's disabled by default.

**CachedPostsSource** is structurally different from the other six: rather than retrieving
anything, it re-serves a set of already-scored candidates from a short-lived cache (more
on this in the caching section below). When it's active, none of the other six sources
run at all.

One universal rule bounds all of this: regardless of which source found a post, or how
long that source's own index retains data, **every candidate is subject to a single,
unconditional 48-hour age filter** applied after all seven sources have contributed.
Phoenix's retrieval index keeps some categories of content — video, for instance — for
much longer than 48 hours internally, but none of that extra retention matters for a
normal feed request, because the age filter removes anything older regardless of source.

*Primary evidence: Rapid 01 (all seven sources, index-admission rules); S01 (source
wiring and merge behavior).*

---

## 4. What the system knows about you and the post

Once candidates are pooled, they go through a "hydration" step where Home Mixer fills in
the details each downstream stage will need — this is concurrent, not sequential, since
these lookups don't depend on each other.

On the viewer side, this includes your recent action history, your follow graph (who you
follow and, separately and importantly, who follows *you back* — the two directions are
tracked independently), account metadata like follower count and account age, your
blocks and mutes, and any safety-relevant labels already attached to your account.

On the post side, it includes engagement counts (favorites, retweets, quotes, replies,
views, bookmarks), the post's language, whether it's a reply/retweet/quote and to whom,
whether it has media, any topic or "semantic ID" classification already computed for it,
and safety labels already attached to it or its author.

One boundary is worth stating precisely because it's easy to get wrong: in the specific
request Home Mixer sends to Phoenix for scoring, the wire format carries identifiers,
counts, and boolean flags — not raw post text and not a raw media file or embedding.
The most likely explanation, based on how the model is built, is that richer content
representation is resolved on the serving side from a compact "semantic ID" rather than
streamed fresh with every request — but this repository doesn't contain the server-side
code that would prove that explanation rather than merely make it plausible. What it does
prove directly is the absence: text and media aren't in this specific request.

*Primary evidence: Rapid 04 (request field mapping); S01/S00 (hydration wiring).*

---

## 5. Phoenix: predicting what you'll do

Phoenix is a prediction system, not a single scalar recommender. For each candidate post,
it returns roughly two dozen separate numbers, one per possible action: how likely you are
to favorite it, reply to it, retweet it, click it, share it, follow the author, report it,
mark it "not interested," and several more — plus a handful of continuous predictions like
how many seconds you'd likely spend watching it. Most of the discrete predictions (will
you favorite this?) come from a shared internal representation that gets pushed through an
independent sigmoid per head, meaning each action's probability is computed separately even
though they all draw on the same underlying model output. The continuous predictions (how
long will you watch this?) use their own, per-head-configurable activation and loss shape,
sometimes bounded so they can't produce nonsensical values.

If you have no recent action history at all, Phoenix doesn't error out — it explicitly
returns empty predictions for you, and downstream scoring proceeds with everything
effectively at zero. If the model call fails outright, nothing gets written and every
candidate simply keeps whatever prediction values it already had (nothing, on a fresh
request) — the request continues rather than failing.

**Which exact model config Phoenix is running in production is genuinely unknown from
this snapshot**, and this is worth being precise about, because an earlier reading of
this material got it wrong before a closer look corrected it. The repository's own
shipped benchmark and quickstart tooling — the actual runnable scripts you'd use to try
this yourself — pair a config family called `home_direct_packed*` with the ranking
service (the one `PhoenixScorer` calls) and a different family, `xrecsys_two_tower*`, with
the retrieval service (the one the retrieval sources above call). A third config that
exists in the codebase, `xrecsys_gen_recs`, trains on a different objective entirely (it
learns to predict the *embedding* of the next thing you'll engage with, rather than
classifying discrete actions) and does not appear in any of the repository's own
launch/benchmark/quickstart tooling for either service. None of this proves what X's
actual production deployment uses — this is a statement about what the repository's own
shipped reference tooling documents as the pairing, not an independently verified claim
about live traffic.

*Primary evidence: Rapid 02 (prediction heads, consumption); Rapid 04 and Rapid 05 (model
architecture, config-family pairing).*

---

## 6. RankingScorer: turning predictions into a score

This is the section where a very common misreading happens, so it's worth stating the
correct framing before the numbers: **RankingScorer's weights multiply predicted
probabilities, not raw counts of past engagement.** A weight of -234 on "report" does not
mean "one report cancels out 468 likes" in any literal transactional sense — reports are
astronomically rarer than favorites in the underlying data the model was trained on, so
for the model's *predicted probability* of a report (which will itself be a tiny fraction,
not 1.0) to move the score at all, the weight attached to it has to be large. The ratio
between two weights is not an exchange rate between two kinds of events, and the source
code itself states this caution directly, in a comment, for exactly this reason.

Here are the major checked-in weights, as they appear in the repository today:

| Action | Weight | Sign |
|---|---|---|
| Favorite | 0.5 | positive |
| Reply | 5.0 (+15.0 more for eligible mutual-follow original posts — see below) | positive |
| Retweet | 1.0 | positive |
| Click | 0.4 | positive |
| Open external link | 0.2 | positive |
| Share | 2.0 | positive |
| Share via DM | 5.0 | positive |
| Share via copy-link | 20.0 (the largest positive weight) | positive |
| Quote | 5.0 | positive |
| Follow the author | 4.0 | positive |
| Not interested | -43.2 | negative |
| Block the author | -31.2 | negative |
| Mute the author | -58.8 | negative |
| Report | -234.0 (the largest-magnitude weight of any kind) | negative |

A handful of other heads exist in the code but are currently weighted at exactly zero
under checked-in defaults — profile clicks, the discrete dwell head (superseded by a
continuous version), quoted-video-quality-view, and a couple of others — meaning they're
wired up and predicted, but contribute nothing to today's score regardless of what Phoenix
predicts for them. On the continuous side, predicted watch time carries a small weight
(0.004) that's multiplied against however many seconds Phoenix thinks you'll spend on the
post, and "scrolled past without dwelling" carries the smallest negative weight in the
whole table (-0.02).

**A concrete, illustrative example** (using the checked-in defaults above, not any claim
about production): suppose Phoenix predicts, for one candidate post, an 8% chance you'll
favorite it, a 1% chance you'll reply, a 2% chance you'll retweet it, and a 0.05% chance
you'll report it. The positive contributions would be roughly `0.5 × 0.08 = 0.04` from
favorite, `5.0 × 0.01 = 0.05` from reply, and `1.0 × 0.02 = 0.02` from retweet — about 0.11
combined. The report contribution would be roughly `-234.0 × 0.0005 ≈ -0.117` — enough, in
this made-up example, to roughly cancel out the positive side entirely, even though the
*predicted probability* of a report is 160 times smaller than the predicted probability of
a favorite. That's the whole point of the large negative weight: it exists specifically so
that a small but real predicted risk of a strongly negative outcome can meaningfully offset
several smaller positive signals, without ever functioning as a literal "N likes per
report" exchange rate. (The real formula applies one more normalization step after this —
compressing net-negative totals toward a small value near zero rather than leaving them
deeply negative — which this example skips for clarity; it's a smoothing step, not a
change to which direction a post's score moves.)

*Primary evidence: Rapid 02 (weight table and formula, `ranking_scorer.rs`).*

---

## 7. Network position, boosts, and cold start

After the weighted sum, several independent adjustments run on top of it, in a fixed
order.

**Being out-of-network (someone you don't follow) applies a discount** — 0.75× by default
for ordinary requests, a steeper 0.5× for topic-scoped ones. A detail that's easy to miss:
by current checked-in default, this same discount also applies to *in-network* replies
and retweets, not just out-of-network content — meaning a reply from someone you do
follow can, under today's default configuration, be discounted the same way as a stranger's
original post.

**A mutual-follow (bidirectional-follow) boost** exists for original posts — not replies,
not retweets — from someone who follows you back. Under checked-in defaults, this adds
+15.0 to the reply weight (on top of the base 5.0) but +0.0 to the dwell weight, so
currently only the reply-weight side of this mechanism has any effect.

**Author diversity** shrinks a candidate's score the more posts from the same author
already rank above it in the current batch — but it's a decaying discount with a floor,
not a hard cap: the first post from an author gets no discount, the second is discounted
to about 62.5% of its score, the third to about 44%, converging toward a 25% floor rather
than ever reaching zero. Repeatedly seeing one author is therefore a real, designed
possibility, not a bug — the mechanism suppresses repetition, it doesn't eliminate it.

**Cold start** is a mechanism aimed at giving small accounts a chance. Once per request,
it looks for the single best eligible low-follower, low-impression, recent post and raises
its score — but only as a floor, and only against its *pre-adjustment* score at that point
in the pipeline. Concretely, under checked-in defaults, that floor is set to whatever
score currently occupies a specific rank position in the batch (position 16, zero-indexed
as rank 15). It is important to be precise here: **this floors one candidate's score to at
least what a mid-pack post is currently scoring — it does not assign or guarantee that
candidate a final position anywhere in the feed.** Author-diversity and out-of-network
adjustments that run afterward, and VMRanker's diversity selection after that, can still
move the boosted candidate up or down from wherever this floor initially placed it. A
new/small account's post getting this floor is not a promise it lands at position 16 in
what you actually see.

*Primary evidence: Rapid 02 (`ranking_scorer.rs`, `author_cold_start.rs`).*

---

## 8. VMRanker and the DPP diversity layer

After RankingScorer produces its number, the scored list is sent to a separate service
called VMRanker. An earlier stage of this same research effort had described VMRanker's
server-side behavior as external and unpublished; that was wrong, and it's worth
correcting explicitly, because the actual code changes the picture meaningfully. VMRanker
is a standalone service checked into this same repository, and its diversity-selection
algorithm — a determinantal point process, or DPP — is fully readable Rust source, not a
black box.

Under DPP mode (the checked-in default value model), VMRanker does not compute a new
predictive score at all. It sorts the incoming candidates by the score Home Mixer already
sent, keeps up to a configured pool size, looks up an embedding for each candidate,
builds a similarity kernel from those embeddings, and uses a quality/diversity trade-off
parameter (theta) to greedily select a subset that is both high-scoring and mutually
dissimilar — the goal being a feed that isn't five near-identical posts about the same
story. Selected candidates keep their original RankingScorer score exactly; candidates
that aren't selected come back with a score of exactly zero. So this stage is better
understood as a diversity-aware selection mask layered on top of RankingScorer's
ordering, not a second opinion from an independent model.

One specific, non-obvious behavior is worth flagging without overstating its likely
frequency: if a candidate has no precomputed embedding on file, the code generates a
random unit vector on the spot and uses that for the similarity comparison. This
repository doesn't say how often that happens in practice, so it shouldn't be read as a
routine occurrence — only as a documented fallback that exists.

The runtime picture here has two independent unknowns worth separating clearly. Home
Mixer, by checked-in default, *requests* DPP-based selection on every call. But the
VMRanker server's own flag controlling whether it actually runs DPP defaults to `false`
in the checked-in configuration — if that flag is off, the server simply echoes the
incoming scores back unchanged, and the whole mechanism becomes a no-op regardless of what
Home Mixer asked for. Whether that server flag is set to `true` in X's actual production
deployment, and what the live embedding store contains, are both genuinely unknown from
this snapshot — but the *algorithm* itself, unlike most of the systems this document
describes as "external," is fully public.

*Primary evidence: Rapid 02/04 (VMRanker correction, `vm-ranker/dpp.rs`).*

---

## 9. Visibility filtering: ranking is not the final word

Everything up to this point has been about scoring a post highly. Visibility filtering
(VF) is a structurally separate question: given a specific viewer and a specific post, is
this post even allowed to be shown, in this context, at all? A post can be the
highest-scoring candidate in the entire batch and still never reach the client, because VF
runs *after* the top-50 selection and can remove candidates the scoring stages already
approved.

It helps to separate several places content can be excluded, because they are genuinely
different mechanisms with different scopes and different failure behavior:

- **Index-time exclusion** happens before any request exists at all — a post can be kept
  out of Phoenix's retrieval index entirely, for every future viewer, based on viewer-less
  safety checks run once when the post is created or newly favorited. Two independent
  mechanisms do this (Grox/UPA content-flag admission, and a separate visibility-filtering
  check called `shouldDropPostByVF`) — both covered in §10.
- **A pre-ranking filter** removes a candidate before Phoenix ever scores it — blocks,
  mutes, duplicates, a specific legal exclusion list, and similar checks.
- **A ranking penalty** (the out-of-network discount, author diversity) doesn't remove a
  candidate, it just lowers where it lands.
- **Post-ranking visibility filtering** runs on the already-selected top 50 and can still
  remove a candidate at this late stage, or flag it for an interstitial instead of
  removing it.

VF evaluates every candidate under one of two policies, and which one applies depends on
whether the post is in-network or out-of-network relative to the viewer: **TimelineHome**
(more permissive — mainly account-state issues, blocks/mutes, legal takedowns, and hard
NSFW cases) or **TimelineHomeRecommendations** (out-of-network content, meaningfully
stricter — everything TimelineHome checks, plus roughly two dozen additional drop rules
covering spam, abuse, malicious URLs, and NSFW/violence labels that simply don't apply to
in-network content at all). The practical consequence is genuinely surprising the first
time you see it: **the exact same post, carrying the exact same labels, can be visible to
people who follow the author and invisible to people who don't** — this repository's own
tests assert exactly that, side by side, for several labels.

VF produces exactly one of three outcomes per post, and evaluation follows a precise,
tested order: rules run in the order they're declared; an **Allow** verdict changes
nothing and evaluation simply continues to the next rule; the **first Interstitial**
verdict encountered is provisionally remembered, but evaluation *keeps going* past it — a
later rule could still upgrade that provisional result to a Drop; the **first Drop**
immediately ends evaluation — every rule after it in the list simply never runs, and that
Drop is final regardless of any Interstitial recorded earlier. If evaluation reaches the
end of the list without hitting a Drop, the final verdict is whatever Interstitial was
recorded first, or Allow if none was.

**Interstitial is not the same as Drop, and conflating them is a real mistake this
document is careful to avoid.** An interstitialed post is still delivered to the client —
Home Mixer's own filtering logic explicitly does not remove it — carrying a flag the
client uses to decide how to render it (typically, a content warning the viewer has to
tap through). Only a Drop verdict causes Home Mixer to actually remove the post from the
response before it's sent. A related filter separately removes any post whose ancestor,
quoted post, or retweet target was independently Dropped — so a reply to a dropped tweet
disappears too, even if the reply itself, considered alone, would have been Allowed.

A handful of built-in exceptions matter for how this plays out day to day: an author
viewing their own content is essentially never dropped by an author-state rule, and
several out-of-network-only rules explicitly allow the content through if the viewer
already follows the author — these rules exist to suppress *discovery* of borderline
content by strangers, not to erase it for people who already chose to follow the account.

*Primary evidence: Rapid 03 (visibility filtering, full rule engine and evaluation
semantics).*

---

## 10. Where the safety labels come from

Visibility filtering doesn't generate the labels it checks — it consumes labels other
systems produce. Understanding the feed means understanding, at least roughly, that
production chain, and this repository shows more of it, more precisely, than it might
first appear:

```
 detectors / models   (Grox, Agatha, BDSM, media classifiers, external URL-reputation)
        │
        ▼
 rule / enforcement systems   (Botmaker/Scarecrow, abuse-enforcement-service)
        │
        ▼
 labels / account state   (written onto posts and onto Gizmoduck account records)
        │
        ▼
 consumers   (visibility filtering, index admission, other systems not traced here)
```

**Grox** is a content-understanding system: an LLM-based classifier that watches posts
crossing an engagement threshold and writes boolean flags — is this NSFW, is it gore, is
it spam-like — into a shared content-annotation record. That exact record is what
Phoenix's index-admission logic consults when deciding whether a post is allowed into the
mainstream retrieval indices at all, meaning Grox's classification can gate whether a
post ever becomes retrievable by Phoenix, before any individual viewer's request exists.

Phoenix rankall runs a **second, structurally different index-admission safety check**
alongside the Grox/UPA one above: `shouldDropPostByVF`, a full visibility-filtering
evaluation under the stricter `TimelineHomeRecommendations` policy, run once per post with
no viewer at all, at the point a post is considered for the relevant Phoenix retrieval
indices. This is *not* the ordinary per-viewer, per-request VF check described in §9 — it
runs earlier and without a viewer, and a post it excludes cannot later be retrieved
through the affected Phoenix indices for any viewer, though other retrieval systems
(Thunder, SimClusters) never call VF at retrieval time and are unaffected by this check.
Its failure behavior is specific, not a blanket rule, so it shouldn't be summarized as
"index-time VF always fails open": a decider-lookup exception falls through to a legacy
code path rather than proving a universal drop; a Rust-VF verdict-fetch exception
explicitly resolves to don't-drop (fail open); a missing/`None` Rust verdict also resolves
to don't-drop; and the legacy branch's own fetch/execution exception behavior is unknown
from this snapshot.

**Agatha** computes graph- and behavior-derived reputation scores about accounts. It has
no direct consumer under its own formal output types anywhere in this repository — but its
*named health-signal features* absolutely do have consumers: two checked-in Scarecrow
rules read specific Agatha scores by name and, past specific thresholds, write labels
called `AGATHA_SPAM` and `AGATHA_SPAM_TOP_USER`. It's important to be precise about what
this does and doesn't establish: **neither of those two exact label names appears
anywhere in visibility filtering's rule set** — they are not the same thing as the
generic `SPAM`/`SPAM_HIGH_RECALL` labels VF does act on, and this document does not assume
they're equivalent just because the names sound related. So Agatha demonstrably feeds a
real rule and a real label, but that label's effect on your For You feed specifically is
not established by anything in this repository.

**BDSM** — Behavioral Detection Sequence Model — is, despite the acronym, not an NSFW or
adult-content model at all. It's an anti-bot, inauthentic-behavior detector: a transformer
that reads a user's recent sequence of actions and classifies them across eight
categories (things like FollowBot, LikeBot, EngagementAmplifier). It has its own
dedicated enforcement pipeline that can issue CAPTCHA-style challenges for borderline
cases or trigger suspension for high-confidence ones. Its actual operating thresholds are
deliberately redacted in this public release — shipped as an obviously invalid sentinel
value — specifically so the detection boundary can't be reverse-engineered from the
published code.

**UserCredV2** is a PageRank-style credibility score computed by propagating "mass" along
the real follow graph, log-transformed into a bounded 0–100 value. It is the most
pervasively consumed reputation score this document traces: it's used directly, by name,
as a skip gate in abuse-enforcement-service's rules ("skip enforcement if this account's
credibility score is high enough"), and — one layer removed but just as concretely — it's
also the literal implementation behind a derived feature called `IsHighPageRankUser`,
which acts as a skip-gate in the large majority of Scarecrow's checked-in enforcement
rules. In other words, a high UserCredV2 score doesn't just sit there as a callable
function — it's the mechanism deciding whether most of the safety rules in this snapshot
apply to a given account at all.

**Botmaker** is a general-purpose, compiled-rule event-processing engine — not a ranking
system, not itself a source of any specific rule. **Scarecrow** is the specific,
production-flavored deployment of Botmaker used for spam and abuse. An earlier reading of
this repository, searching only the generic `botmaker/` directory, concluded no concrete
rules were checked in at all. That conclusion was wrong: a separate directory,
`botmaker-rules/scarecrow/`, contains 20 real rule definitions, every one read for this
document, complete with real thresholds, real expiry dates, and every single one marked
active. These are not placeholder examples — they consume Grox's spam score, Agatha's
health scores, URL-reputation verdicts, and NSFW media scores, and they write real labels.
This does not mean the complete production rule corpus is public — 20 rules is a subset of
unknown completeness relative to whatever X actually runs — but "no rules are public" and
"all rules are public" are both wrong; the honest description is a real, non-trivial,
partial, exact-label-traceable subset.

**abuse-enforcement-service** is a checked-in Rust service whose actual rule files are
present in this repository, mirrored from a live external configuration system with dated
sync headers. It runs as a Kafka consumer, not a per-request check — it reacts to accounts
or posts some upstream detector already flagged, rather than evaluating every user on
every request. Its output vocabulary is small and fixed: suspend (temporary or
permanent), add a label, or issue a challenge.

**Gizmoduck** is the account-state service — it's where account-level safety flags, user
labels, and suspension/deactivation state live. Unlike the systems above, it's queried
live and synchronously on every single request, not produced in the background — both
Home Mixer's query construction and visibility filtering's per-candidate evaluation read
from it directly (see §1). Follow, block, and mute relationships are *not* part of
Gizmoduck; those come from a separate social-graph client. Gizmoduck is a consumption
point, not a detector itself: Scarecrow writes labels *into* Gizmoduck, and visibility
filtering *reads* account state *from* it.

*Primary evidence: Rapid 03 (full safety-label ecosystem, all producer-consumer chains).*

---

## 11. Label to consequence, concretely

Here is what happens for several specific, independently-confirmed labels — meaning both
the system that writes the label and the visibility-filtering rule that reads it were
directly read in this repository, not inferred from similar-sounding names.

| Label | In-network | Out-of-network |
|---|---|---|
| `SPAM` | Dropped | Dropped (this one applies both ways) |
| `SPAM_HIGH_RECALL` | Allowed | Dropped |
| `NSFW_HIGH_PRECISION` / `NSFW_HIGH_RECALL` (account-level) | Allowed | Dropped |
| `NSFW_CARD_IMAGE` | Shown behind an interstitial | Dropped |
| `GORE_AND_VIOLENCE_HIGH_PRECISION` | Shown behind an interstitial | Dropped |
| `MALICIOUS_URL` | Allowed | Dropped |

The two interstitial rows are worth sitting with, because they capture the general shape
of this system well: the *exact same post*, carrying the *exact same label*, is shown to
people who follow the author (with a warning they can tap through) and removed entirely
for people who don't. This isn't a bug or an inconsistency — it reflects a deliberate
design choice, visible directly in the rule set, that these labels exist to restrict
*algorithmic discovery* of borderline content, not to erase it for an audience that
already opted in by following the account.

It's equally important to say what this repository does *not* establish. Several labels
that are demonstrably written by real, active Scarecrow or abuse-enforcement-service rules
— `AGATHA_SPAM`, `AGATHA_SPAM_TOP_USER`, `RISKY_HIGH_VIZ_REPLY`, `COPYPASTA_SPAM` — do not
appear anywhere in visibility filtering's rule set under those exact names. Their
existence as real, active labels is confirmed; their consequence for your For You feed
specifically is not. It would be a mistake to assume any label that sounds spam-adjacent
automatically results in a drop — some very plausibly feed a different system entirely
(search demotion, notification filtering) that this snapshot doesn't show reaching Home
Mixer at all.

*Primary evidence: Rapid 03 (exact producer→consumer label table, independently verified
by string match on both ends).*

---

## 12. Beyond posts: ads and the rest of the feed

Up to now, this document has described how organic posts get selected. What you actually
receive from a For You request is not just those posts — it's a composite response built
by an outer pipeline (`ForYouCandidatePipeline`) that treats the entire organic-post
pipeline described above as just one of seven inputs, alongside ads, "Who to Follow"
suggestions, prompts, push-to-home content (when you tapped a notification), sports/event
"frames," and an occasional feed-survey marker.

`BlenderSelector` is the component that assembles the final composite list. It first
blends organic posts with ads using one of several interchangeable strategies, selectable
per request:

- A **partition-based** approach (the default) groups posts and tries to place each ad in
  a safe slot, subject to several content-adjacency checks — and if every ad fails every
  check, all of them are silently dropped and the response falls back to posts alone.
- A **safe-gap** strategy finds gaps between posts that aren't flagged as elevated-risk and
  places ads there — notably, this strategy skips the additional content-adjacency checks
  the partition approach applies, a real difference in strictness between two
  interchangeable, switch-selected options.
- A **time-gap** strategy spaces ads using predicted watch time rather than post count.

After the ad blend, `BlenderSelector` inserts the remaining item types at fixed positions:
prompts stack at the very front, a Who to Follow module goes at a specific slot a bit
further in, a push-to-home post (if present) gets pinned ahead of everything else, sports
frames are slotted at computed intervals, and a feed-survey marker goes near the end of
the visible window. The execution order in code is prompts, then Who to Follow, then
push-to-home, then frames, then the feed survey — so push-to-home is actually inserted
*after* prompts and Who to Follow, not before them, but because it's pinned at the very
front of the list, it displaces those earlier insertions forward by a slot rather than
sitting behind them. None of this is a unified ranking — it's a sequence of insert
operations at fixed positions, not a scored blend.

One repair mechanism worth naming specifically: `AdAdjacentServedFilter` runs after the
blend and checks whether an ad ended up next to a post you've already seen recently. When
that happens, it searches for a different eligible post to swap into that slot instead —
and **it only ever drops the ad itself if no swap candidate can be found anywhere in the
list; it never drops an organic post to fix an ad-adjacency problem.**

*Primary evidence: S02 (full blending mechanics, ad-blender comparison).*

---

## 13. Caching: a 180-second shortcut, not a frozen feed

If a viewer has a large enough set of recently-scored candidates sitting in a short-lived
cache — at least 500 of them, from a request within roughly the last three minutes — a new
request can skip retrieval entirely and reuse that set instead of calling any of the seven
retrieval sources fresh.

The important nuance here is what caching does and doesn't skip. It skips fresh
*retrieval* (none of the seven sources run) and it skips a fresh *Phoenix inference call*
(the reused candidates keep whatever prediction values Phoenix produced the first time,
up to about 180 seconds earlier). It does **not** skip RankingScorer or VMRanker — both of
those run again, in full, using whatever ranking weights and diversity parameters are
active for the *current* request. That means a feature-switch weight change deployed
within that 180-second window can genuinely change the relative order of a cached
response, even though the underlying model predictions never changed. A cached response is
best understood as "stale predictions, freshly re-weighted" — not a frozen replay of an
earlier ranking.

*Primary evidence: Rapid 01/02 (cache population, activation, and rescoring behavior).*

---

## 14. What happens when things fail

A recurring theme across this whole system is that it degrades quality far more often
than it fails outright. A single broken component almost never fails your request; it
just quietly contributes less.

| What fails | What happens |
|---|---|
| One retrieval source (e.g., Thunder is unreachable) | That source contributes zero candidates; the other six are unaffected; the request continues |
| Phoenix's model call | No predictions are written this round; every candidate keeps whatever prediction values it had before (nothing, on a fresh request) |
| VMRanker's whole call | RankingScorer's score is left exactly as it was — the final ranking simply becomes "whatever RankingScorer produced" |
| Visibility filtering's whole RPC batch (up to 50 posts) | Fails open — the candidate is kept, since it never got an updated verdict |
| Visibility filtering's response is missing one specific post ID | Fails closed for that post — it's treated as dropped |
| Visibility filtering can't resolve a post's author server-side | Fails closed — treated as a Drop |
| SimClusters — any single engagement signal's lookup fails | Aborts the *entire* SimClusters contribution for that request, not just the failed signal |
| A background side effect (logging, cache-writing) | Cannot affect the current response under any circumstance — its only possible effect is on a future request |
| A boot-time client construction (server startup) | Generally fails hard and crashes the process — the one confirmed exception is Thunder's optional proxy client, which degrades gracefully instead |

The general shape: almost everything that can go wrong *during* a request degrades
gracefully — a component contributes nothing rather than blocking the response. Almost
everything that can go wrong *at server startup* is fail-hard by contrast, on the
reasoning that a partially-initialized server shouldn't serve traffic at all.

*Primary evidence: S01 (framework-wide failure semantics), Rapid 01–04 (per-system
specifics).*

---

## 15. Feature switches: why "checked-in default" isn't "what you get"

Nearly every number in this document — every weight, every threshold, every percentage —
is a **checked-in default value** read directly from the source code. It is not a live
production value, and this repository is explicit about that distinction in its own
comments: the file holding these defaults literally says it's "mirrored from config
feature-switch defaults" as of a specific timestamp, meaning it's a periodically-refreshed
copy of an external system's defaults, not the live system itself.

The mechanism that would let a specific value differ per user or per experiment is called
a **feature switch**, and this repository shows the *matching machinery* clearly, even
though it never shows a live value. A request can be matched against roughly fifteen
concrete attributes: your user ID, country, language, which client app and version you're
using, your account roles, the datacenter serving the request, your account's age (in
days, and separately in minutes, for very new accounts), whether you have a verified phone
number, what kind of request this is (For You, Ranked Following, etc.), and whether your
account was recently "resurrected" after a period of inactivity. That's the complete set
of things the matching system can key on from Home Mixer's side — there's no exposed
device-type field, no city-level location, and no raw random seed visible here, so any
percentage-based rollout the external system does must derive its own randomness
internally, in a way this repository doesn't show.

One parameter — which specific server cluster Phoenix routes a request to — has an
unusually flexible override structure: on top of the ordinary feature-switch layer, it can
also be redirected by a separate, independently-gated mechanism called a **decider**, and
by a new-account-specific override that switches the cluster for viewers with very little
history. This makes cluster selection the single most override-flexible parameter this
document covers, with two independent runtime mechanisms able to change it rather than
one.

None of this should be read as evidence that any specific default cited elsewhere in this
document *is* what's currently live — only that the architecture is built to allow it to
vary, and that this repository documents the shape of that variability without exposing
any of its actual current values.

*Primary evidence: Rapid 05 (`RecipientBuilder` matching-key enumeration, cluster
override layers).*

---

## 16. "Why did I see this post?" — three walk-throughs

**A. A post from someone you follow.** Thunder returns it because you follow the author
and it's recent. It goes through pre-scoring filters (nothing removes it — it's not a
duplicate, not from a blocked account, not on the legal exclusion list). Phoenix predicts
your likely reactions; RankingScorer scores it, and because it's in-network, no
out-of-network discount applies (unless it happens to be a reply or retweet, in which case
the current checked-in default *does* apply the same discount out-of-network content gets
— a real, non-obvious wrinkle). It survives to the top 50, passes the more permissive
in-network visibility policy, and reaches your feed.

**B. An account you don't follow, that you've never heard of.** SimClusters surfaces it
because it resembles something you recently engaged with, or Phoenix's own retrieval
index surfaces it independently. Because it's out-of-network, RankingScorer applies a
0.75× discount to its score by default. It still scores well enough to make the top 50.
Now it faces the stricter `TimelineHomeRecommendations` visibility policy — roughly two
dozen additional drop rules that simply don't apply to people you follow. If it clears
those, it reaches your feed; if not, it's gone, regardless of how well it scored.

**C. A post that scores extremely well but never reaches you.** It's retrieved normally,
Phoenix predicts strong engagement for it, RankingScorer gives it a high score, and it
comfortably makes the top 50. But somewhere along the way — maybe the account carries an
NSFW label and you don't follow them, maybe a URL in the post was flagged as malicious —
visibility filtering evaluates it under the stricter out-of-network policy and returns
Drop. Home Mixer's own filter removes it before the response is even assembled. You never
see it, and nothing about its high score changes that outcome. This is the single
clearest illustration of why ranking and visibility filtering have to be understood as two
separate systems rather than one pipeline: a post's rank tells you how good the model
thought it was; visibility filtering tells you whether it was allowed to reach you at all,
and the second question is answered entirely independently of the first.

---

## 17. What we can and cannot know

This repository is genuinely detailed about mechanism and genuinely silent about live
state. It's worth ending on a clear list of both, because the temptation to blur them —
to read a checked-in default as a production fact, or a published algorithm as proof of
what's actually running — is the single easiest way to walk away from this material with
a wrong impression.

**Directly established by this snapshot:**
- Home Mixer's complete orchestration — which stages run concurrently, which run
  sequentially, and in what order.
- How each of the seven retrieval sources works, and Phoenix's index-admission rules.
- Thunder's full implementation and SimClusters' retrieval mechanics.
- RankingScorer's exact formulas and checked-in weight values.
- VMRanker's complete DPP diversity-selection algorithm.
- Visibility filtering's complete rule composition and evaluation order.
- A real, 20-rule subset of Scarecrow's spam/abuse rules, with exact conditions and
  thresholds.
- BDSM's architecture and enforcement-pipeline structure (not its live thresholds).
- Phoenix's model architecture and the repository's own shipped reference serving
  tooling.
- Under the Hood's actual data shape and what it does and doesn't expose to users.

**Not knowable from this snapshot, no matter how carefully it's read:**
- Any live feature-switch or decider value, for any parameter cited in this document.
- Which decider state or cluster string maps to which physical serving deployment.
- X's actual production model checkpoint — no trained weights ship in this repository.
- The complete Botmaker/Scarecrow rule corpus beyond the 20-rule subset that is public.
- BDSM's real, unredacted operating thresholds.
- What specifically sets an account's `allow_for_you_recommendations` flag to false — no
  code anywhere in this snapshot writes to that field.
- The internals of external services this repository only shows the client side of, such
  as TweetMixer's actual recommendation algorithm.
- The actual contents of VMRanker's live embedding store.

A few distinctions are worth keeping sharp any time this material comes up again: a
checked-in default is not a production value; a field appearing in a request is not proof
the model that receives it actually uses it; a model's architecture being public is not
the same as its trained weights being public; a label existing is not proof it has any
feed consequence; two similar-sounding label names are not necessarily the same label; an
interstitial is not a drop; being excluded from an index at creation time is not the same
as being filtered out of one specific request; and a retrieval score, a Phoenix
prediction, and a RankingScorer score are three different numbers that happen to occur in
sequence, not three names for the same thing. Every claim in this document tries to
respect those boundaries explicitly rather than blur them for a cleaner story.

*Primary evidence: Rapid 04/05 (reproducibility matrix, public-vs-production boundary,
consolidated across all prior passes).*
