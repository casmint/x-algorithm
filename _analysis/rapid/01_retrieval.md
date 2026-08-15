# Retrieval — How Posts Enter the Candidate Pool

Rapid-track macro covering S03 (Thunder), S04 (SimClusters), and S07 (Phoenix
retrieval index / rankall admission) as one investigation, per
`_analysis/rapid/README.md`. Builds on S01's orchestration model
(`_analysis/reports/specialists/S01_candidate_pipeline_home_mixer.md`) and S02's
feed-composition context; does not re-derive them.

## Plain-English summary

Every "For You" or "Scored Posts" request in Home Mixer runs `PhoenixCandidatePipeline`,
which pulls candidates from **seven parallel sources** before any of them are scored by
the Phoenix ranking model. Understanding "how does a post get seen at all" means
understanding these seven sources, because a post that no source returns can never be
ranked, no matter how good it is.

Three of the seven are the retrieval systems this report focuses on. **Thunder** is the
in-network path: a standalone Rust service that keeps an in-memory index of recent posts
by author, fed continuously by a Kafka stream of tweet-create/delete events. When a
request comes in, Home Mixer already knows who the viewer follows (from its own
social-graph client, established in S01), and sends that follower list straight to
Thunder, which just looks up and returns the most recent posts from those authors —
no ranking model, no embeddings, just "who does this person follow, what did they
recently post." Thunder has its own retention window (2 days by default) and its own
per-author caps, and it explicitly also returns some second-degree content: replies made
by people the viewer follows to *other* people the viewer follows, so conversations
between mutuals surface even if the reply's author line is one hop removed.

**SimClusters** is the out-of-network path built from what the viewer already engaged
with, not from a static "you like sports" profile. For each of the viewer's recent
favorites/engagements, Home Mixer asks a SimClusters ANN (approximate nearest neighbor)
service to find *other* posts that are similar in an offline-computed embedding space —
literally "people who engaged with things similar to this tweet also engaged with these
other tweets," restricted to a 48-hour candidate age window and capped per underlying
cluster. This is item-to-item similarity retrieval, not "look up which static interest
cluster this user belongs to and pull its top posts" — the wiring here is entirely keyed
by recent post-level engagement signals, so a viewer with no recent engagement signals
gets zero SimClusters candidates by construction.

**Phoenix retrieval** is the third, most opaque-from-this-repo path, and it's the one
this macro spends the most effort de-mystifying: before Phoenix's ranking model can score
a post, that post has to already be *admitted* into a retrieval index built entirely
outside of any single user's request, by a separate ingestion pipeline
(`phoenix-rankall`) that consumes post-creation and favorite events off Kafka. Two things
control admission: the type of event (a post being created always tries to enter one
index; a post crossing favorite-count thresholds — 1, 32 — tries to enter others), and a
set of hard exclusions applied before the **mainstream** index-build branches run:
**community posts, replies, and retweets are excluded from `post_creation`/`1fav`/
`32fav`/topic/`video`/`imagine` admission**, regardless of how many favorites they get.
Posts that fail visibility/NSFW checks are also dropped from those mainstream indices
(NSFW posts with video get diverted into a segregated NSFW-video index instead). A
narrower, earlier branch (`search_unfiltered`, favorite-triggered only) excludes
community posts and retweets but **not** replies, and is not one of the snapshot windows
this report traced — whether it feeds any retrieval path Home Mixer actually queries is
unresolved (see Phoenix section and findings below), so this report does not claim
replies are categorically absent from Phoenix retrieval end to end.

The other four wired sources matter too, and it would be misleading to describe
retrieval as "Thunder + SimClusters + Phoenix" without them. **TweetMixerSource** and
two more Phoenix-retrieval variants — **PhoenixTopicsSource** (topic-request-only) and
**PhoenixMOESource** (a mixture-of-experts retrieval variant) — are fully wired
out-of-network sources that share the same enable-gate shape as the sources above but
are **not documented in the repo's README** at all (this was already flagged in S01 as
S01-F003; this report confirms their retrieval mechanics and closes S01-F008's
uncertainty about their `in_network_only` behavior). And **CachedPostsSource** is a
seventh, structurally different source: when a viewer has a large enough set of
recently-scored candidates sitting in Redis (≥500, from a request in roughly the last 3
minutes), the request skips retrieval entirely and just re-serves that stale, already-
scored set.

A recurring theme worth internalizing: **wired is not the same as enabled**, and
**enabled-by-default is not the same as what's live in production**. `EnableTweetMixerSource`
and `EnablePhoenixMOESource` both default to `false` in the checked-in source; only
`EnablePhoenixSource` and `EnableSimclustersSource` default to `true`. This report states
checked-in defaults precisely and does not claim they reflect current production values —
that determination requires the feature-switch/GrowthBook layer this snapshot doesn't
expose (S17's territory, per S01).

Finally: a **retrieval score is not a ranking score**. None of the seven sources write a
persistent score onto `PostCandidate` that survives into Phoenix's scoring stage —
SimClusters' cosine-similarity score is used only internally, to threshold and order
candidates *within* `SimclustersSource` before it hands off bare `tweet_id`s. Every
candidate, regardless of which source found it, enters the scoring stage on equal
footing; retrieval determines the *pool*, not the *order* of the final feed.

## End-to-end map

```
                         ScoredPostsQuery (built once per request, S01)
                                        |
      +-----------+-----------+--------+--------+-----------+-----------+
      |           |           |                 |           |           |
 ThunderSource TweetMixer  Simclusters      PhoenixSource PhoenixTopics PhoenixMOE  CachedPostsSource
      |         Source      Source               |         Source       Source          |
      |           |           |                   \          |          /              |
   Thunder     TweetMixer  SimClusters       RetrievalDispatch (prod client + optional xDS path,
   gRPC svc     client      ANN gRPC          keyed by inference-cluster-id param)         |
      |        (external)   (Wily-              |                                    Redis GET
  in-memory     mechanism   discovered)     Phoenix retrieval / xrecsys serving       (cache_key =
  post index    unknown        |            index  <-- built by phoenix-rankall          user_id +
  fed by            |     seeded by viewer's   ingestion pipeline (separate         topic_ids +
  Kafka          -- OON --  recent engagement   process, ~always running)          in_network_only +
  tweet_events                signals               ^                                exclude_videos)
      |                          |                   |
   -- IN --                -- OON --        Kafka: post-creation + favorite events
                                             (favorite events rate-limited to power-
                                              of-2 thresholds: 1, 2, 4, 8, ... favs)
                                                      |
                                          admission filter (before any index write):
                                          drop community posts, replies, retweets,
                                          NSFW/VF-failed posts (NSFW+video diverted
                                          to a separate nsfw_video index instead)
                                                      |
                                          per-index-name snapshot windows
                                          (post_creation, 1fav, 32fav, video,
                                           nsfw_video, evergreen_video, imagine, ...)
                                                      |
                              (connection from snapshot -> live serving index is
                               external/unpublished from this repo — UNKNOWN)

  All 7 sources' results are concatenated (no interleaving/quota at merge) into one
  candidate list, then pass through a single, unconditional, 48-hour AgeFilter that
  applies uniformly regardless of source or served_type (S01), before scoring.
```

## All wired Home Mixer candidate sources

`PhoenixCandidatePipeline`'s 7 sources, declared order, from
`home-mixer/candidate_pipeline/phoenix_candidate_pipeline.rs:316-324`. "Checked-in
default" values are from `home-mixer/params/param.rs`; whether they match production is
UNKNOWN (S17's territory, consistent with S01).

| Source | IN/OON/cache | Mechanism | Enable conditions (source-read) | Candidate limit (checked-in default) | Pre-Phoenix score carried? | Requires Phoenix retrieval index? | Requires follow graph? | Disabled by `in_network_only`? | Disabled by `has_cached_posts`? | Main external dependency | Failure consequence | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ThunderSource` | IN | Looks up recent posts by followed-author IDs from Thunder's in-memory index; recency-sorted, capped per author | `!query.has_cached_posts` only | 1200 (600 if video request); Thunder-side hard caps `MAX_POSTS_TO_RETURN`/`MAX_VIDEOS_TO_RETURN` | No (no score field set) | No | Yes (following list passed in request) | **No** — no `in_network_only` check in `ThunderSource::enable` | Yes | Thunder gRPC service (or CAPI proxy) | `Err` → 0 candidates this request; other sources unaffected | DIRECT |
| `TweetMixerSource` | OON | Calls external `TweetMixerClient.get_recommendations`; self-applies a 48h age filter | `EnableTweetMixerSource` (**default `false`**) `&& !in_network_only && !has_cached_posts` | 800 | No | Unknown (client internals external) | No | Yes | Yes | `TweetMixerClient` (external crate, mechanism not in this snapshot) | `Err` → 0 candidates | DIRECT (gating); UNKNOWN (internals) |
| `SimclustersSource` | OON | ANN cosine-similarity retrieval seeded by the viewer's recent engagement-signal tweet IDs | `EnableSimclustersSource` (default `true`) `&& !in_network_only && !has_cached_posts &&` viewer has ≥1 engagement signal | 800 interleaved cap; 10,000 per-request ANN budget across signals | No (ANN score used only internally for a >0.5 threshold + ordering, not retained) | No | No (keyed by follow list only indirectly, via being in-network eligible at all) | Yes | Yes | SimClusters ANN gRPC service (Wily service discovery) | Any single signal's `Err` aborts the whole source via `result?` inside the per-signal results loop → **0 candidates for the entire request**, not just that signal | DIRECT |
| `PhoenixSource` | OON | `RetrievalDispatch` (prod client + optional xDS path) queries the Phoenix retrieval index for the resolved inference cluster | `EnablePhoenixSource` (default `true`) `&& (!is_topic_request \|\| is_bulk_topic_request) && !in_network_only && !has_cached_posts` | 1000 (pre `quality_factor::apply`, an external multiplier) | No | **Yes** | No | Yes | Yes | Phoenix retrieval client (xDS/prod gRPC) + external xrecsys serving stack | `Err` → 0 candidates (whole call fails together) | DIRECT (gating/mechanism); UNKNOWN (xrecsys internals) |
| `PhoenixTopicsSource` | OON | Same `RetrievalDispatch` mechanism, topic-entity-filtered, topic-specific inference cluster | `is_topic_request() && !is_bulk_topic_request() && !in_network_only && !has_cached_posts` (no separate `Enable*` flag found) | 1000 (same param as `PhoenixSource`) | No | Yes | No | Yes | Yes | Same as `PhoenixSource` | Same | DIRECT |
| `PhoenixMOESource` | OON | Same `RetrievalDispatch` mechanism, MOE-specific inference cluster | `EnablePhoenixMOESource` (**default `false`**) `&& (!is_topic_request \|\| is_bulk_topic_request) && !in_network_only && !has_cached_posts` | 200 | No | Yes | No | Yes | Yes | Same as `PhoenixSource` | Same | DIRECT |
| `CachedPostsSource` | cache | Returns `query.cached_posts` verbatim — no live retrieval at all | `query.has_cached_posts` (set upstream by `CachedPostsQueryHydrator` when Redis has ≥500 cached candidates for this key) | Whatever was cached (up to `MaxPostsToCache`, written by the caching side-effect) | **Yes** — cached `PostCandidate`s retain whatever score they had when originally computed | No | No | Only source active when `has_cached_posts` | n/a | Redis (populated by a prior *non-cached* request's `RedisPostCandidateCacheSideEffect`) | `source()` is infallible; upstream Redis failure just means `has_cached_posts` never becomes `true` | DIRECT |

## Thunder — in-network retrieval

Thunder is a standalone Rust service (`thunder/`), not a Home Mixer submodule. It runs
in two roles selected by the `--is-serving` flag (`thunder/main.rs:88-114`,
`thunder/kafka_utils.rs:21-102`):

- **Feeder** (`is_serving=false`): consumes the raw `tweet_events` Kafka topic, applies a
  first filtering/transform pass (drops `nullcast` posts; computes `is_reply`/`is_retweet`
  flags; checks video eligibility via `is_eligible_video`, requiring ≥5s duration —
  `thunder/kafka/tweet_events_listener.rs:55-74,209-267`), and republishes a compact
  `InNetworkEvent` stream to the `innetwork_post` topic. It does not serve requests.
- **Server** (`is_serving=true`): consumes `innetwork_post` (the feeder's output) via
  `start_tweet_event_processing_v2`, builds the in-memory `PostStore` from it, and serves
  the gRPC `InNetworkPostsService`.

**Storage** (`thunder/posts/post_store.rs`): a `DashMap<post_id, CompactPost>` plus three
separate per-author `VecDeque` indices — `original_posts_by_user`,
`secondary_posts_by_user` (replies/retweets), `video_posts_by_user` — each capped at
`MAX_POSTING_LIST_SIZE = 5000` per author and trimmed on insert (`post_store.rs:157-228`,
`config.rs:1-14`). A background auto-trim task runs every 2 minutes, evicting anything
older than `retention_seconds` (default 172,800s = 48h, `args.rs:48-49`) or over the
per-author cap (`post_store.rs:477-604`). Deletes are tracked via `mark_as_deleted` and
posts are removed from the primary map immediately (`post_store.rs:112-126`).

**Query mechanics** (`thunder/thunder_service.rs:149-320`): `get_in_network_posts`
rate-limits by a global QPS quota (`REJECTED_REQUESTS`), truncates the caller's
`following_user_ids`/`exclude_tweet_ids` to `MAX_INPUT_LIST_SIZE = 10,000`, and — this is
the important structural detail — for each followed author pulls **both** their original
posts (`original_posts_by_user`) **and** their replies/retweets
(`secondary_posts_by_user`), the latter filtered so that a reply only counts if it's
replying to an *original* post or to another reply-chain that ultimately traces back to a
followed user (`post_store.rs:335-363`). This is how Thunder surfaces "someone I follow
replied to someone else I follow" conversations, not just top-level posts. Results are
sorted purely by recency and truncated (`thunder_service.rs:322-326`,
`score_recent`) — Thunder does no learned ranking; `algorithm` is effectively
always "recent" (any other value logs an error and falls back).

**Home Mixer integration** (`home-mixer/sources/thunder_source.rs`):
`ThunderSource::enable` only checks `!query.has_cached_posts` — **there is no
`in_network_only` check inside Thunder's own gate**. Home Mixer already resolved the
follow list via its own social-graph hydrator (S01) and sends it as
`following_user_ids`; Thunder does not own or compute the social graph itself. A
debug-only fallback exists (`thunder_service.rs:184-216`): if the caller sends an empty
following list *and* sets `debug=true`, Thunder will fetch the list itself from Strato —
this path is not exercised by production Home Mixer requests, which always populate the
list.

**CAPI/proxy fallback** (S01-F013, confirmed here): `thunder_source.rs:44-70` — if a
`ThunderCapiClient` was constructed at boot and the `enable_thunder_capi_home_mixer`
decider is on for the request, Thunder is queried via that client instead of the direct
gRPC channel; otherwise a channel is resolved from a configured/deciderable
`ThunderCluster` (default `"amp"`) via `get_random_channel`, and a missing channel is a
hard `Err` for the whole source. S01 already established `ThunderCapiClient` is the one
boot-time client in its examined set that degrades gracefully to `None` (with a logged
warning) rather than panicking — this report adds that at *request* time, its absence
just means the direct-channel path is always used; it is not itself a failure mode.

**Age/limits**: Thunder's own retention (48h default) plus Home Mixer's separate,
universal `AgeFilter` (48h, `params::MAX_POST_AGE`, applied post-merge to every source's
output alike, `phoenix_candidate_pipeline.rs:348`) both bound how old an in-network post
can be by the time it's scored.

**Exclusions inside Thunder vs. Home Mixer**: Thunder excludes only a small hardcoded
blacklist of three bot/test accounts (`thunder_service.rs:29-37`) and whatever the caller
passes in `exclude_tweet_ids`. All other exclusion/filtering (visibility, blocked/muted
users, previously-seen, NSFW, etc.) happens later in Home Mixer's shared filter stack
(S01/S02), uniformly across all 7 sources — Thunder does not duplicate that logic.

**A dormant path**: `thunder/o2/mod.rs` implements a full S3-compatible object-store
client (`O2Client`), and `thunder/args.rs:73-76` defines `--o2-bucket`/`--o2-prefix` CLI
args for it — but nothing in `thunder/main.rs` or elsewhere constructs an `O2Client` or
reads those args. Thunder's only bootstrap path in this snapshot is the Kafka catchup
loop in `main.rs:88-114` (wait for all `kafka_num_threads` to report low lag, then
`finalize_init`). This looks like a snapshot-restore mechanism that either isn't wired
yet or lives in a part of the deployment this repo doesn't include (see finding below).

**A parallel, separate in-network mechanism** (context, not deep-audited here):
`FollowingNightOwlSource` (`home-mixer/sources/following_night_owl_source.rs`) feeds the
*unranked* `ReverseChronPostsPipeline` behind `FollowingCandidatePipeline` (the
chronological "Following" tab, S01), querying a **different** real-time search backend
("Night Owl") with a 365-day recall window and recency ranking — not Thunder. It exists
so a reader shouldn't assume Thunder is the only in-network retrieval mechanism in the
repository; it is the one used by `PhoenixCandidatePipeline` specifically.

## SimClusters — interest-based OON retrieval

**What it represents, concretely**: a SimCluster is a precomputed cluster in an offline
community-detection/embedding pipeline (`simclusters/simclusters_v2/`, batch Scalding
jobs — not on the live serving path and not deep-read here). Both posts and clusters get
embedded into the same space; a post's embedding is a sparse weighted vector over cluster
IDs (`SimClustersEmbedding`).

**Home Mixer's live path is item-to-item, not a static viewer profile.**
`SimclustersSource::source` (`home-mixer/sources/simclusters_source.rs:95-136`) builds
its seed IDs from `post_signal_ids(query)` — the viewer's `explicit_engagement_signals`
and `implicit_engagement_signals` (populated by query hydrators established in S01),
i.e., **posts the viewer recently engaged with**, most-recent-first, deduplicated. If a
viewer has zero engagement signals, `has_post_signals` returns `false` and the source is
disabled entirely (`simclusters_source.rs:88-93,139-147`) — this is not a fallback to a
static interest profile, it is zero candidates.

**Retrieval mechanics** (`home-mixer/sources/simclusters_source.rs` +
`simclusters/simclustersann/candidate_source/SimClustersANNCandidateSource.scala` +
`OptimizedApproximateCosineSimilarity.scala`): for each seed post ID, a `Query` is built
against a fixed embedding type (`LOG_FAV_LONGEST_L2_EMBEDDING_TWEET` for the seed,
`LOG_FAV_BASED_TWEET` for candidates, `MODEL_20M_145K_2020`,
`simclusters_source.rs:175-196`). The serving side looks up the seed's embedding, takes
its top `maxScanClusters` (50) clusters by weight, fetches each cluster's precomputed
top-tweets list, and computes a cosine-similarity score between the seed and each
candidate restricted to a configured age window (`maxTweetCandidateAgeHours = 48`,
`minTweetCandidateAgeHours = 0`) and per-cluster cap (`maxTopTweetsPerCluster = 800`),
returning up to `maxNumResults = 200` per seed
(`OptimizedApproximateCosineSimilarity.scala:30-105`). Home Mixer then filters each
seed's results to `score > POST_ANN_MIN_SCORE (0.5)`, caps per-seed results at
`MAX_SANN_CANDIDATES / num_seeds`, interleaves round-robin across seeds
(`interleave_by_post_id`), and truncates the merged list to `MAX_RESULTS = 800`
(`simclusters_source.rs:96-121,198-221`).

**Score is not carried forward**: the resulting `PostCandidate` only sets `tweet_id` and
`served_type: ForYouSimclusters` (`simclusters_source.rs:122-129`) — the ANN cosine score
is used purely to threshold/order candidates inside `SimclustersSource` and is discarded
before the candidate reaches scoring. `author_id` and everything else come from
`CoreDataCandidateHydrator`, run inline inside the source itself
(`simclusters_source.rs:131-134`); any candidate that hydration fails to resolve an
`author_id` for is dropped right there (`.retain(|c| c.author_id != 0)`).

**Dedup/enable/gates**: `EnableSimclustersSource` (default `true`), plus
`!query.in_network_only && !query.has_cached_posts && has_post_signals(query)`
(`simclusters_source.rs:88-93`) — this directly resolves the `in_network_only`
uncertainty S01-F008 left open for this source: SimClusters is unconditionally disabled
in in-network-only mode. Deduplication is local to the interleave step
(`seen: HashSet<tweet_id>`); there is a separate downstream filter,
`OONNsfwSimclustersFilter` (`home-mixer/filters/oon_nsfw_simclusters_filter.rs`), that
drops SimClusters-sourced candidates specifically when `in_network=false &&
nsfw_author=true` — gated on the same `EnableSimclustersSource` flag.

**Failure/external dependency**: the client (`home-mixer/clients/simclusters_ann_client.rs`)
resolves the `simclusters-ann` service via Wily DNS at boot (hard `Err` if 0 endpoints
found), applies a 600ms per-request timeout, and wraps the channel in a retrying client
for idempotent requests. At request time, `source()` runs all per-signal ANN lookups
concurrently via `join_all`, but then iterates the results with `let candidates =
result?;` inside a plain `for` loop (`simclusters_source.rs:108-112`) — the `?` returns
early on the **first** `Err` encountered, discarding any other signals' already-fetched
results too. So a single failed signal aborts `SimclustersSource::source` as a whole,
which — per S01's framework-level "a failing source contributes zero candidates"
semantics — means **zero SimClusters candidates for the entire request**, not just a
reduced set missing that one signal's contribution.

## Phoenix retrieval index / rankall admission

This is the most consequential, least README-documented mechanism in this macro: a post
can be permanently excluded from Phoenix's retrieval index (and therefore from
`PhoenixSource`/`PhoenixTopicsSource`/`PhoenixMOESource`) **before any user ever
requests a feed**, by a batch ingestion pipeline that runs continuously and
independently of Home Mixer.

**Two upstream triggers** feed this pipeline over Kafka:

- **Post creation**: `phoenix-rankall-strato/stream_forwarders/postCreationEventForwarder.strato`
  forwards post-creation events (not independently opened; inferred from its role as the
  paired forwarder to `phoenixRankAllCandidateProcessor.strato`'s `PostCreation` event
  source — STRONG_INFERENCE, not independently read).
- **Favorites**: `phoenix-rankall-strato/columns/favoriteEventProcessor.strato:82-160`
  consumes raw Favorite events and **rate-limits re-triggering per tweet to power-of-two
  favorite-count thresholds** (1, 2, 4, 8, 16, 32, ...) via a cache
  (`tweetUpdateThresholdsCache`, `favoriteEventProcessor.strato:14-64`) — so a viral post
  doesn't generate an indexing event on every single favorite, only when its count crosses
  the next power of two.

**Admission has two branches with different exclusion rules**
(`phoenix-rankall-strato/columns/phoenix_rank_all/phoenixRankAllCandidateProcessor.strato:381-487`).

*Branch 1 — `search_unfiltered` (favorite events only, runs first, before the reply
check)*: `if (eventSource == Fav && !isCommunityPost && !isRepost) { buildSearchUnfilteredIndex(...) }`
(`phoenixRankAllCandidateProcessor.strato:433-435`) — this excludes community posts and
retweets/reposts, but **is evaluated before `isReply` is computed and does not itself
exclude replies**. `search_unfiltered` is not among the snapshot windows
`phoenix-rankall/src/config/mod.rs` builds for the `Main`/`Topic`/`Sid` pipeline variants
this report traced (`config/mod.rs:139-191`), so whether it is written to a
retrieval-relevant index/store at all, and whether any live Phoenix retrieval path Home
Mixer queries can consume it, is **UNKNOWN** from this snapshot.

*Branch 2 — mainstream indices*, evaluated after `search_unfiltered`, applied to every
event before any of the following index-build functions run:

1. Post metadata/author lookup fails → dropped (`numMissingMetadata`/`numMissingAuthorId`).
2. **Community posts → always dropped**, regardless of engagement (`numSkippedCommunity`).
3. **Replies → always dropped** (`numSkippedReplies`).
4. **Retweets/reposts → always dropped** (`numSkippedReposts`).
5. Visibility-filter drop or NSFW → dropped from the mainstream indices; **if** it also
   has an eligible immersive video **and** the triggering event was a favorite **and**
   it's NSFW, it's instead admitted only to a segregated `nsfw_video` index plus a
   metadata dump — otherwise fully skipped (`numSkippedPosts`).
6. Otherwise, **admitted**: a `Fav` event builds the `1fav` index (≥1 favorite) plus a
   backup copy, a `32fav` index (≥32 favorites), up to six topic-filtered index variants
   (`1fav_topic*`), and — if it has immersive video — `video`/`imagine` indices, plus
   metadata dumps; a `PostCreation` event builds only the `post_creation` index (plus
   `video` if applicable) and a metadata dump.

**Post creation alone is sufficient** for the `post_creation` index — no engagement
required — but is still subject to branch 2's community/reply/retweet/visibility
exclusions. DIRECT: replies, retweets, and community posts are excluded from every
mainstream index-build branch/window this report traced (`post_creation`, `1fav`,
`32fav`, topic variants, `video`, `imagine`). DIRECT, narrower: the `search_unfiltered`
branch excludes community posts and retweets but not replies. This report does **not**
claim "`PhoenixSource` can never return a reply" or "replies can only ever enter via
Thunder/SimClusters/TweetMixer" — that would require proving the live Phoenix retrieval
serving stack cannot consume `search_unfiltered`, which this snapshot does not show.

**Index storage and windows** (`phoenix-rankall/src/config/mod.rs:139-191`): the `Main`
pipeline variant (`phoenix-rankall/src/processor/main_processor.rs`) writes per-index-name
snapshot windows with independent retention — `post_creation` (24h), `1fav` (24h and 48h
windows both kept), `32fav` (24h), `video` (up to 720h/30 days), `nsfw_video` (48h/168h),
`evergreen_video`/`evergreen_nsfw_video` (5 years). **A separate `Sid` pipeline variant**
(`phoenix-rankall/src/processor/sid_processor.rs`) additionally hydrates admitted posts
with a Semantic ID via an external `SidClient` service and writes its own, slightly
different window set (notably: no `32fav` or `post_creation` windows in the Sid pipeline
— `config/mod.rs:176-187`) — the exact relationship between "written to a Sid window"
and "retrievable by `PhoenixSource`" is not established in this snapshot (the connection
from these on-disk snapshot windows to the live `xrecsys` serving process
`phoenix/xrex/inference/sid_retrieval_runner.py`/`sid_post_index.py` reads is external —
**UNKNOWN**). SID lookup failure does not drop the record — it's kept with an empty SID
and left for a periodic backfill retry loop (`sid/backfill.rs`,
`sid_processor.rs:184-205`, confirmed by test `rpc_failure_yields_empty_post_sid_not_drop`).
There's also a distinct `SidTailProcessor` (`sid_tail_processor.rs`) building a `tail`
index specifically for **low-follower authors** (`author_followers_count < max_author_followers`,
default 1000) with an optional minimum-favorite floor — apparently a dedicated
long-tail/small-account discovery mechanism, separate from the mainstream fav/creation
indices.

**Effectively capped at 48h regardless of index retention**: even though `video` is kept
for 30 days and `evergreen_video` for 5 years in these snapshot windows, Home Mixer's
universal, unconditional `AgeFilter` (48h, see Thunder section) runs on every candidate
from every source before scoring, with no exception for served type. Any Phoenix-sourced
candidate older than 48h is therefore dropped downstream regardless of how long the index
itself retains it — the long retention windows appear to serve the retrieval/embedding
corpus, not literal feed eligibility, though this repo does not show how the retrieval
model itself uses that longer-lived corpus (UNKNOWN/external).

## Cached-post path

Fully resolved end to end from `home-mixer/candidate_hydrators/cached_posts_query_hydrator.rs`
and `home-mixer/side_effects/redis_post_candidate_cache_side_effect.rs`:

- **Population**: after a normal (non-cached) request finishes, `RedisPostCandidateCacheSideEffect`
  (enabled only when `is_prod() && !query.has_cached_posts`) takes the union of selected +
  non-selected candidates with `weighted_score > 0.0`, sorts by score descending, truncates
  to `MaxPostsToCache`, zstd-compresses, and writes to Redis with a **180-second TTL**,
  keyed by `(user_id, topic_ids, in_network_only, exclude_videos)`.
- **Activation**: `CachedPostsQueryHydrator` reads that same key with a 300ms timeout.
  Cache mode activates only if the decompressed set has **≥500 candidates**
  (`MIN_CACHED_POSTS_THRESHOLD`); otherwise `has_cached_posts` stays `false`.
- **What stops running**: every one of the other six sources' `enable()` bodies includes
  `!query.has_cached_posts` (confirmed by direct read, table above) — cache mode disables
  **all live retrieval**, not just some of it. S01 also separately established
  `BidirectionalFollowHydrator` and `PhoenixScorer` both skip on `has_cached_posts`, so
  cached requests skip most of hydration and scoring too, not only retrieval.
- **Rescoring**: `CachedPostsSource` itself is a verbatim pass-through — candidates come
  back with their original `weighted_score` already set, no rescoring inside the source.
  Downstream, `PhoenixScorer::enable` explicitly returns `false` when
  `query.has_cached_posts` (`home-mixer/scorers/phoenix_scorer.rs:65-68`), so cached
  candidates reuse their previously-computed Phoenix model prediction fields rather than
  getting a fresh inference call. But `RankingScorer::enable` and `VMRanker::enable` gate
  only on `EnableRanking`/`EnableVMRanker` respectively (`ranking_scorer.rs:734-736`,
  `vm_ranker.rs:24-26`) — **neither checks `has_cached_posts`** — so on the current
  checked-in wiring, cache mode bypasses live retrieval and fresh Phoenix model inference,
  while later local weighting/reranking (`RankingScorer`, `VMRanker`) may still execute
  again against the reused Phoenix fields. Whether that reruns with the *current* request's
  feature-switch weights, and what that means for the final order of a cached response,
  is resolved precisely in the ranking macro (`_analysis/rapid/02_ranking.md`), not here.
- **Staleness**: up to 180 seconds stale by construction (Redis TTL), and reflects
  whatever candidate pool existed at the time of the *original* request — no new posts
  from any of the seven sources can appear during a cache-mode response.
- **Failure**: a Redis GET error or timeout on the read side is an `Err` from the query
  hydrator, which — per S01's framework-wide `if let Ok` semantics — means the update is
  silently skipped: `has_cached_posts` simply stays at its default `false`, i.e., cache
  mode fails open into a normal full-retrieval request, not into an error.

## IN vs OON behavior

`in_network_only`'s three origins (client request / server-forced for
`RankedFollowingFeedService`+`FollowingFeedService` / `viewer_data.allow_for_you_recommendations
== Some(false)`) were already established in S01 (S01-F008). This macro closes the
per-source uncertainty S01-F008 left open by reading every retrieval source's `enable()`
body directly (not inferred from names):

| Source | Checks `!in_network_only`? |
|---|---|
| `ThunderSource` | **No** — always runs when `!has_cached_posts`, regardless of `in_network_only` |
| `TweetMixerSource` | Yes (confirmed by S01; re-confirmed here) |
| `SimclustersSource` | **Yes** (newly confirmed — closes S01-F008 for this source) |
| `PhoenixSource` | **Yes** |
| `PhoenixTopicsSource` | **Yes** |
| `PhoenixMOESource` | **Yes** |
| `CachedPostsSource` | n/a (orthogonal gate) |

In other words: **among the six live retrieval sources, every out-of-network one is
uniformly disabled by `in_network_only`; Thunder is the only one not disabled by it.**
`CachedPostsSource` is the structurally separate cache-only path — it does not gate
directly on `in_network_only` either, but its Redis key incorporates `in_network_only`
upstream (via `CachedPostsQueryHydrator`'s `cached_posts_key`), so cached and
non-cached-mode candidate sets never mix across that flag. This is now confirmed
directly rather than inferred, closing S01-F008's stated gap.

## Failure/degraded modes

Building on S01's framework-wide model (a failing source contributes zero candidates,
never fails the request):

| Condition | Consequence |
|---|---|
| Thunder gRPC unavailable | `ThunderSource` → 0 candidates this request; other 6 sources unaffected; in-network content entirely absent from that response unless SimClusters/TweetMixer happen to surface a followed author's post out-of-network-style (they don't specifically target followed authors, so this is not a real substitute) |
| Thunder CAPI client absent at boot | No request-time effect — falls back to direct-channel path transparently (S01-F013, confirmed here) |
| SimClusters ANN client / Wily DNS down at boot | Constructor returns hard `Err`; boot-time failure (fail-hard, consistent with S01's boot-time asymmetry finding) |
| SimClusters ANN request timeout/error (any single signal) | Aborts `SimclustersSource::source` entirely via early-return `?` on the first `Err` seen while iterating `join_all`'s results — **0 candidates from SimClusters for the whole request**, not a partial/reduced set |
| Phoenix retrieval client / xDS path failure | Whole `PhoenixSource`/`PhoenixTopicsSource`/`PhoenixMOESource` call fails together → 0 candidates from that source for this request; exact xDS-vs-prod fallback retry semantics live in the external `RetrievalDispatch`/`retrieve_with_fallback` implementation, not vendored in this snapshot — **UNKNOWN** internals, only the call site and `max_retries`/`enable_fallback` params are visible here |
| Phoenix rankall / SID lookup service down | Indexing record is still written with an empty SID (not dropped), retried later by a periodic backfill loop — a lag/staleness effect on retrieval eligibility, not a hard failure |
| Phoenix rankall ingestion pipeline lagging or down | New posts/favorite-threshold crossings stop entering the index until it catches up — **other sources (Thunder, SimClusters, TweetMixer) are unaffected** and can still surface the same post through their own independent mechanisms; Phoenix retrieval's view of "what's indexable" and Thunder/SimClusters' view are entirely independent systems with no shared eligibility state |
| Redis cache read failure/timeout | Fails open — cache mode simply never activates for that request; falls through to full retrieval |
| Redis cache write failure (caching side-effect) | Fire-and-forget side effect (S01); failure is silently discarded, no effect on the response that triggered it, only means a *later* request within the TTL window won't find a warm cache |

## Important source-vs-README differences

- README documents Thunder, Phoenix retrieval, and SimClusters as *the* out-of-network
  sources; `TweetMixerSource`, `PhoenixTopicsSource`, and `PhoenixMOESource` are three
  additional, fully-wired sources absent from that documentation (S01-F003, reconfirmed
  with full retrieval-mechanics detail in this report).
- README does not distinguish "wired" from "enabled by checked-in default": two of the
  seven sources (`TweetMixerSource`, `PhoenixMOESource`) default to **disabled**
  (`EnableTweetMixerSource=false`, `EnablePhoenixMOESource=false`) in the checked-in
  source, meaning a reader of the source tree alone would overestimate how much OON
  traffic they carry absent knowledge of the live feature-switch state (UNKNOWN here).
- The repository's README does not mention that replies and retweets are excluded from
  Phoenix's *mainstream* retrieval indices at ingestion time — this is only visible from
  the `phoenix-rankall-strato` admission logic, not from anything in `home-mixer/`; nor
  does it mention the narrower `search_unfiltered` branch that admits replies.

## Material findings

1. **Phoenix retrieval's mainstream indices exclude replies, retweets, and community
   posts at ingestion — an admission wall, not a scoring penalty — but a narrower,
   earlier favorite-only branch (`search_unfiltered`) excludes only community posts and
   retweets, not replies.**
   Significance: HIGH. Evidence class: DIRECT (both branches' exclusion sets, read
   directly); UNKNOWN (whether `search_unfiltered` feeds any live retrieval path).
   Claim: `phoenixRankAllCandidateProcessor.strato`'s `executeOp` routes
   `isReply`/`isRepost`/`isCommunityPost` posts to a skip counter before any *mainstream*
   index-build function runs (`post_creation`, `1fav`, `32fav`, topic variants, `video`,
   `imagine`), for both `Fav` and `PostCreation` event sources. A separate, earlier branch
   for favorite events only, `buildSearchUnfilteredIndex`, checks `!isCommunityPost &&
   !isRepost` but runs before `isReply` is computed and does not exclude replies.
   `search_unfiltered` is absent from the snapshot window configs
   (`phoenix-rankall/src/config/mod.rs:139-191`) this report traced.
   Source: `phoenix-rankall-strato/columns/phoenix_rank_all/phoenixRankAllCandidateProcessor.strato:429-479`
   (mainstream exclusions), `:433-435` (`search_unfiltered` branch).
   Caveat: this governs only the Phoenix-index-backed sources (`PhoenixSource`,
   `PhoenixTopicsSource`, `PhoenixMOESource`) for the mainstream indices specifically;
   Thunder and SimClusters have no such exclusion and can and do surface replies/retweets;
   whether `search_unfiltered` is itself queryable by any live Phoenix retrieval path is
   unresolved and should not be assumed either way.

2. **SimClusters retrieval is item-to-item (recent-engagement-seeded), not a static
   viewer interest profile.**
   Significance: HIGH. Evidence class: DIRECT.
   Claim: every ANN query's `sourceEmbeddingId` is built from a recently-engaged
   `tweet_id` (`InternalId::TweetId(signal_id)`), never from a user-level embedding ID;
   a viewer with zero recent engagement signals gets zero SimClusters candidates.
   Source: `home-mixer/sources/simclusters_source.rs:88-93,139-196`.
   Caveat: the live path is item-based; the repository does contain unrelated
   user-embedding ("InterestedIn") batch jobs under `simclusters/simclusters_v2/`, but
   nothing in `home-mixer/` wires them into request-time retrieval — not deep-audited
   further, consistent with the task's "prioritize the live path" instruction.

3. **Neither SimClusters' cosine score nor any other source's retrieval score survives
   into Phoenix scoring — retrieval score and ranking score are different things.**
   Significance: MEDIUM. Evidence class: DIRECT.
   Claim: `SimclustersSource`'s output `PostCandidate` literal sets only `tweet_id` and
   `served_type`; none of the other six sources set a score field either.
   Source: `home-mixer/sources/simclusters_source.rs:122-129` (and the equivalent
   literals in `thunder_source.rs`, `tweet_mixer_source.rs`, `phoenix_source.rs`,
   `phoenix_topics_source.rs`, `phoenix_moe_source.rs`).
   Caveat: `CachedPostsSource` is the one exception — its candidates retain whatever
   score was computed the *first* time they went through the full pipeline.

4. **`in_network_only` uniformly disables every out-of-network source and never affects
   Thunder — closes S01-F008's open per-source uncertainty.**
   Significance: HIGH. Evidence class: DIRECT.
   Claim: `SimclustersSource`, `PhoenixSource`, `PhoenixTopicsSource`, `PhoenixMOESource`
   all check `!query.in_network_only` directly in `enable()`; `ThunderSource` does not
   check it at all.
   Source: table in "IN vs OON behavior" above; primary sources
   `home-mixer/sources/{simclusters,phoenix,phoenix_topics,phoenix_moe,thunder}_source.rs`.

5. **Cache mode (`has_cached_posts`) disables 100% of live retrieval, not a subset.**
   Significance: HIGH. Evidence class: DIRECT.
   Claim: all six non-cache sources include `!query.has_cached_posts` in their `enable()`
   gate; only `CachedPostsSource` runs, returning a Redis-stored set up to 180 seconds
   stale, activated only once ≥500 candidates are cached for that exact
   `(user_id, topic_ids, in_network_only, exclude_videos)` key.
   Source: `home-mixer/candidate_hydrators/cached_posts_query_hydrator.rs`,
   `home-mixer/side_effects/redis_post_candidate_cache_side_effect.rs`, and the `enable()`
   bodies in each of the six retrieval sources.

6. **Favorite-triggered Phoenix indexing is rate-limited to power-of-two thresholds, not
   every favorite.**
   Significance: MEDIUM. Evidence class: DIRECT.
   Claim: `favoriteEventProcessor.strato` only forwards a favorite event to the indexing
   pipeline when the tweet's favorite count crosses the next power of two since the last
   trigger (cached per-tweet), meaning `32fav`-index admission specifically requires
   crossing 32, not merely reaching it via many small increments being individually seen.
   Source: `phoenix-rankall-strato/columns/favoriteEventProcessor.strato:14-64,117-149`.

7. **A dormant S3 object-store bootstrap path exists in Thunder but is never invoked.**
   Significance: LOW–MEDIUM. Evidence class: DIRECT (existence of dead code);
   STRONG_INFERENCE (that it's meant as a snapshot-restore mechanism).
   Claim: `thunder/o2/mod.rs` defines a full `O2Client` (get/put/list/head against an
   S3-compatible store) and `thunder/args.rs` defines matching CLI args
   (`--o2-bucket`/`--o2-prefix`), but no call site in `thunder/main.rs` or anywhere else
   in `thunder/` constructs an `O2Client` or reads those two args.
   Source: `thunder/o2/mod.rs:1-177`, `thunder/args.rs:73-76`, absence confirmed via
   `grep -rn "O2Client\|o2_bucket\|o2_prefix" thunder --include="*.rs"`.
   Caveat: could be active in an internal build variant not in this snapshot, or a
   planned-but-unshipped feature — cannot be determined from this repo alone.

8. **Universal 48-hour age cutoff makes Phoenix's multi-day/multi-year index retention
   largely invisible to standard feed serving.**
   Significance: MEDIUM. Evidence class: DIRECT (the filter is unconditional);
   STRONG_INFERENCE (that this makes long retention windows serving-invisible, since
   this repo doesn't show how the retrieval model itself consumes the older corpus).
   Claim: `AgeFilter` (48h) is constructed unconditionally in
   `PhoenixCandidatePipeline::build_with_clients` with no per-served-type exception, yet
   `phoenix-rankall`'s `video`, `evergreen_video`, and `evergreen_nsfw_video` snapshot
   windows retain data for 30 days to 5 years.
   Source: `home-mixer/candidate_pipeline/phoenix_candidate_pipeline.rs:348`,
   `phoenix-rankall/src/config/mod.rs:141-156`.

9. **PhoenixTopicsSource has no dedicated `Enable*` feature-switch gate — only request
   shape controls it.**
   Significance: LOW. Evidence class: DIRECT.
   Claim: unlike every other Phoenix-family source, `PhoenixTopicsSource::enable`
   contains no `query.params.get(Enable...)` check — its only gates are
   `is_topic_request()`/`!is_bulk_topic_request()`/`!in_network_only`/`!has_cached_posts`.
   Source: `home-mixer/sources/phoenix_topics_source.rs:25-30`.

## What remains unknown

- The exact wire connecting `phoenix-rankall`'s on-disk snapshot windows (built by the
  `Main`/`Sid`/`Topic`/`Metadata` pipeline variants) to what `PhoenixRetrievalClient`
  actually reads at request time — the serving side (`phoenix/xrex/inference/sid_retrieval_runner.py`,
  `sid_post_index.py`) was not traced in this macro.
- `RetrievalDispatch`/`retrieve_with_fallback`'s internal retry/fallback semantics
  between the `prod` client and an optional xDS path — defined in an external crate
  (`xai_candidate_pipeline::component_library::egress`) not vendored in this snapshot;
  only the call site, `max_retries` and `enable_fallback` params are visible.
- Whether `PhoenixRetrievalInferenceClusterId`'s checked-in default (`"Experiment1Fou"`)
  and `phoenix-rankall`'s `score_prefix` default (`"phoenix.HomeExperiment1Lap7."`) name
  the same underlying model/index generation — the naming resemblance
  (`Experiment1Fou`/`Experiment1Lap7`) is suggestive but not independently confirmed by
  a shared identifier anywhere in this snapshot. POSSIBLE, not DIRECT.
- Production values of every `Enable*`/threshold feature-switch referenced in this
  report (all only have checked-in defaults visible here) — consistent with S01/S17.
- `TweetMixerClient`'s internal retrieval mechanism — the trait and its default gRPC/Wily
  wiring pattern is visible, but the algorithm behind `get_recommendations` lives outside
  this snapshot.
- Whether `postCreationEventForwarder.strato` forwards *every* post creation
  unconditionally, or applies its own upstream filtering before reaching
  `phoenixRankAllCandidateProcessor` — file not independently opened; inferred from its
  paired role with the `PostCreation` event-source branch.
- The exact scope of `phoenix-rankall`'s `Topic`/`Metadata`/`MmMetadata`/`Ads` pipeline
  variants beyond their window configs — not traced beyond `config/mod.rs`.
- Whether `SidTailProcessor`'s long-tail `tail` index is actually queried by any of the
  three Home Mixer `Phoenix*Source`s, or serves a separate (e.g. author-discovery)
  surface not covered by this macro.

## What ranking still needs to answer

Explicit handoff to the next macro (Phoenix scoring + weighting + VMRanker/diversity,
covering the old S05/S08 territory):

- `RankingScorer`'s weighted-sum formula and `AuthorColdStart`'s new-author boost
  thresholds (flagged unread by S01; still unread here).
- `PhoenixScorer` → `RankingScorer` → `VMRanker`'s exact score-field handoff — S01
  established the stage order and `VMRanker`'s whole-call failure mode but flagged the
  field-by-field consequence as STRONG_INFERENCE, not DIRECT (S01-F012).
- **Precisely what happens on a cached (`has_cached_posts`) request inside all three
  scorers**: this report established only the `enable()` gates (`PhoenixScorer` skips,
  `RankingScorer`/`VMRanker` do not check `has_cached_posts` at all) — not what
  `RankingScorer`/`VMRanker` actually do when they run against reused Phoenix prediction
  fields instead of freshly-inferred ones, or whether that can change a cached response's
  final order relative to the original request that populated the cache.
- Whether/how a candidate's originating source (Thunder vs. SimClusters vs. Phoenix
  retrieval vs. TweetMixer) factors into scoring at all, given none of them pass a
  score forward — is `served_type` itself a scoring feature, and if so how heavily
  weighted per source.
- `value_model_gate.rs` (537 lines, flagged unread by S01, still unread) and VMRanker's
  DPP/diversity internals.
- Whether the SimClusters/Phoenix-retrieval/Thunder candidate pools receive materially
  different treatment inside `RankingScorer`/`VMRanker` (e.g. source-specific
  calibration), which this retrieval-focused macro did not investigate.

## Source coverage note

**Deep-read in full**: `home-mixer/sources/{thunder,simclusters,tweet_mixer,phoenix,
phoenix_topics,phoenix_moe,cached_posts,reverse_chron_posts,following_night_owl}_source.rs`;
`home-mixer/util/egress.rs`; `home-mixer/clients/simclusters_ann_client.rs`;
`home-mixer/filters/oon_nsfw_simclusters_filter.rs`;
`home-mixer/candidate_hydrators/cached_posts_query_hydrator.rs`;
`home-mixer/side_effects/redis_post_candidate_cache_side_effect.rs`;
`home-mixer/filters/age_filter.rs`; `home-mixer/params/param.rs` (first ~220 lines);
relevant slice of `home-mixer/candidate_pipeline/phoenix_candidate_pipeline.rs`
(construction site, L180-464); `thunder/main.rs`, `thunder/thunder_service.rs`,
`thunder/posts/post_store.rs`, `thunder/config.rs`, `thunder/args.rs`,
`thunder/kafka_utils.rs`, `thunder/kafka/tweet_events_listener.rs`,
`thunder/kafka/tweet_events_listener_v2.rs`, `thunder/strato_client.rs`, `thunder/o2/mod.rs`;
`simclusters/simclustersann/controllers/GetTweetCandidatesGrpcController.scala`,
`simclusters/simclustersann/candidate_source/{SimClustersANNCandidateSource,
OptimizedApproximateCosineSimilarity}.scala`; `phoenix-rankall/src/main.rs`,
`phoenix-rankall/src/pipeline/mod.rs`, `phoenix-rankall/src/config/mod.rs`,
`phoenix-rankall/src/processor/{main_processor,sid_processor,sid_tail_processor}.rs`;
`phoenix-rankall-strato/columns/phoenix_rank_all/phoenixRankAllCandidateProcessor.strato`,
`phoenix-rankall-strato/columns/favoriteEventProcessor.strato`,
`phoenix-rankall-strato/columns/kafka/indexingEventKafkaTopic.strato`.

**Mechanically searched/surveyed, not deep-read**: full `thunder/`, `simclusters/`, and
`phoenix-rankall*`/`phoenix/` directory trees (via `find`/`wc -l`) to map scope and
identify the live-path files above versus batch/offline/training code; `home-mixer/params/param.rs`
grepped for all `Enable*`/`*MaxResults` param declarations relevant to the 7 sources.

**Intentionally not exhaustively read**: `thunder/schema/*.rs` (large generated/protocol
schema files, `tweet.rs` 5,471 lines, `user.rs` 14,750 lines — only the specific fields
consumed by the listener/deserializer were checked, not read in full); all of
`simclusters/simclusters_v2/` (batch Scalding/Summingbird jobs computing the offline
embeddings SimClusters ANN serves from — confirmed off the live request-time path, not
audited); the `phoenix/xrex/` Python training/serving stack (the actual model-serving
side of Phoenix retrieval — the connection from `phoenix-rankall`'s snapshots to live
serving is flagged UNKNOWN above rather than traced); `phoenix-rankall`'s `Topic`/
`Metadata`/`Analysis` processor variants beyond their window configs; `RetrievalDispatch`/
`PredictionDispatch` internals (external crate, not in this snapshot).
