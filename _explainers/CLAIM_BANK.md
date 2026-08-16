# Claim Bank

A reusable library of pre-checked claims for future guides, diagrams, and short-form
content. Each entry gives safe public wording, its evidence class (see
`EDITORIAL_RULES.md`), the master-synthesis section it derives from, the caveat that must
travel with it, and an unsafe version to never write.

Draw from this bank first. Only write a new claim from scratch when nothing here covers
it — and when you do, add it here afterward so the next writing session doesn't have to
re-derive it.

---

## CORE ARCHITECTURE

**1.**
SAFE: "Home Mixer is the orchestrator that assembles your For You feed — it's not one
model, it's a system that runs its own logic and calls out to several others in a
specific order."
CLASS: DIRECT · MASTER: §1 · CAVEAT: Don't imply Home Mixer is "just" a coordinator — a
substantial share of the real work (RankingScorer, filters, BlenderSelector) runs as its
own local code.
UNSAFE: "Home Mixer is the algorithm."

**2.**
SAFE: "RankingScorer — the component that turns Phoenix's predictions into one score per
post — runs locally, inside Home Mixer, with no remote call."
CLASS: DIRECT · MASTER: §1, §6 · CAVEAT: This was a corrected error in an earlier
internal draft (glossary once implied the opposite) — always state locality explicitly,
don't assume it's obvious.
UNSAFE: "Home Mixer calls out to RankingScorer."

**3.**
SAFE: "Phoenix predicts how you might react to a post; it doesn't decide whether you see
it. Deciding is split across several other systems — RankingScorer, VMRanker, and
visibility filtering."
CLASS: DIRECT · MASTER: §1 · CAVEAT: Don't undersell Phoenix's importance while making
this point — everything downstream runs on its predictions.
UNSAFE: "Phoenix is X's algorithm."

**4.**
SAFE: "Gizmoduck is queried live, synchronously, on every single request — unlike most of
the other safety systems, which run continuously in the background and only leave labels
behind for Gizmoduck and visibility filtering to read later."
CLASS: DIRECT · MASTER: §1, §10 · CAVEAT: Never group Gizmoduck with the background
label-producing systems (Agatha, BDSM, Grox, Botmaker/Scarecrow) — this exact
miscategorization was flagged and fixed in adversarial review.
UNSAFE: "All the safety systems run in the background."

**5.**
SAFE: "The organic post pipeline — retrieval through ranking through visibility
filtering — is itself just one of several inputs to an outer pipeline that also blends in
ads, Who to Follow suggestions, and prompts."
CLASS: DIRECT · MASTER: §2, §12 · CAVEAT: None beyond standard scoping.
UNSAFE: "Ranking decides the whole feed, including ads."

---

## RETRIEVAL

**6.**
SAFE: "Up to seven separate systems can each contribute candidate posts to your feed —
but only the ones enabled for a given request actually run."
CLASS: DIRECT · MASTER: §3 · CAVEAT: Don't imply all seven always run — several are
gated by feature switches, engagement history, or cache state.
UNSAFE: "Seven services run on every request."

**7.**
SAFE: "Thunder finds recent posts from people you follow — no model, no ranking, just
recency, plus a specific rule that surfaces conversations between two people you follow
even if only one of them is in your own follow list."
CLASS: DIRECT · MASTER: §3 · CAVEAT: None.
UNSAFE: "Thunder ranks your follows' posts by quality."

**8.**
SAFE: "SimClusters is a completely separate system from Phoenix's own retrieval — it
finds posts similar to things you've recently engaged with, using its own,
independently-built similarity search."
CLASS: DIRECT · MASTER: §3 · CAVEAT: With zero recent engagement signals, a viewer gets
zero SimClusters candidates — there's no fallback long-term interest profile.
UNSAFE: "SimClusters and Phoenix retrieval are the same system."

**9.**
SAFE: "This repository's own shipped reference implementation for Phoenix's retrieval
search is a two-tower model — one tower encodes you, a simpler tower encodes each
candidate post, and the closest matches by vector similarity are selected."
CLASS: SHIPPED REFERENCE IMPLEMENTATION · MASTER: §3; residual report §"Synthesis
impact" item 2 · CAVEAT: The trained checkpoint and the real post-vector table aren't in
this repository — this describes the architecture, not confirmed production behavior.
UNSAFE: "This is exactly how Phoenix retrieval works in production."

**10.**
SAFE: "Deciding whether a post is allowed into Phoenix's retrieval corpus at all
(`phoenix-rankall`) is a completely different layer from deciding what a specific
request's search actually pulls out of that corpus (the two-tower search) — one runs
once per post, for every future viewer; the other runs per request."
CLASS: DIRECT · MASTER: §3 · CAVEAT: Don't collapse these into one step.
UNSAFE: "Rankall and retrieval search are the same thing."

**11.**
SAFE: "Replies, retweets, and posts from community groups are excluded from Phoenix's
mainstream retrieval indices outright, regardless of engagement — with one narrower
exception (`search_unfiltered`, triggered only by favorite events) whose reach into any
live retrieval path is unknown from this snapshot."
CLASS: DIRECT (exclusion rule) / UNKNOWN (search_unfiltered's live reach) · MASTER: §3 ·
CAVEAT: Always carry the `search_unfiltered` caveat — don't state the exclusion as an
unqualified absolute.
UNSAFE: "Phoenix can never retrieve a reply."

**12.**
SAFE: "A post's favorite count only re-triggers a Phoenix index update at power-of-two
thresholds (1, 2, 4, 8, 16...), not on every single favorite."
CLASS: DIRECT · MASTER: §3 · CAVEAT: None.
UNSAFE: "Every like re-ranks your post instantly."

**13.**
SAFE: "Every retrieved candidate, regardless of which source found it, is subject to a
single unconditional 48-hour age filter after all sources have contributed."
CLASS: CHECKED-IN DEFAULT · MASTER: §3 · CAVEAT: Whether this exact window is live today
isn't confirmed.
UNSAFE: "Posts older than 2 days are always invisible everywhere on X."

**14.**
SAFE: "Being retrieved at all is a prerequisite to being ranked — no matter how good a
post might have scored, it can't appear if no retrieval source ever found it."
CLASS: DIRECT · MASTER: §3 · CAVEAT: This is a legitimate, bounded practical point — don't
extend it into specific instructions for triggering retrieval.
UNSAFE: "Do X to guarantee Phoenix retrieves your post."

---

## PHOENIX RANKING

**15.**
SAFE: "Phoenix predicts roughly two dozen separate possible outcomes per candidate post —
favorite, reply, retweet, click, report, watch time, and more — not one overall score."
CLASS: DIRECT · MASTER: §5 · CAVEAT: None.
UNSAFE: "Phoenix gives each post one quality score."

**16.**
SAFE: "If Phoenix's model call fails outright, nothing gets overwritten — every candidate
just keeps whatever prediction values it already had, and the request continues rather
than failing."
CLASS: DIRECT · MASTER: §5, §14 · CAVEAT: None.
UNSAFE: "If Phoenix goes down, your feed breaks."

**17.**
SAFE: "With no recent action history at all, Phoenix doesn't error — it returns empty
predictions, and scoring proceeds with everything effectively at zero."
CLASS: DIRECT · MASTER: §5 · CAVEAT: None.
UNSAFE: "New accounts get no feed at all."

**18.**
SAFE: "Phoenix's ranking service has a hard limit on candidates scored per request; going
over it leaves the excess candidates unscored entirely — not a lower score, no prediction
at all, silently."
CLASS: DIRECT (capacity/truncation behavior) / UNKNOWN (the real production limit) ·
MASTER: §5; residual report §"Synthesis impact" item 1 · CAVEAT: The checked-in numbers
shown (2,800 packed, 1,400 launcher default, 64 training default) are not confirmed as
what production actually runs.
UNSAFE: "Only the top 64 candidates ever get scored."

**19.**
SAFE: "The repository's own shipped benchmark and quickstart tooling pairs one config
family with the ranking service and a different one with retrieval — but this describes
what the repository's tooling documents, not what X's production deployment actually
runs."
CLASS: SHIPPED REFERENCE IMPLEMENTATION · MASTER: §5 · CAVEAT: Never name a specific
config as "the production model."
UNSAFE: "Phoenix in production runs `xrecsys_two_tower`."

**20.**
SAFE: "The specific request Home Mixer sends Phoenix for scoring carries identifiers,
counts, and flags — not raw post text and not a raw media file."
CLASS: DIRECT · MASTER: §4 · CAVEAT: The likely explanation (a semantic ID resolving to
richer content server-side) is STRONG INFERENCE, not proven by this repository.
UNSAFE: "Phoenix reads your tweet and decides if it likes it."

---

## RANKINGSCORER

**21.**
SAFE: "RankingScorer turns Phoenix's predictions into one number per post by multiplying
each predicted probability by a checked-in weight and summing the results."
CLASS: DIRECT · MASTER: §6 · CAVEAT: None.
UNSAFE: "RankingScorer counts your actual likes and replies."

**22.**
SAFE: "RankingScorer's weights multiply model-*predicted* probabilities, not raw counts
of past engagement — the ratio between two weights is not an exchange rate between two
kinds of events."
CLASS: DIRECT · MASTER: §6 · CAVEAT: This is the single most important caveat in the
project — see `EDITORIAL_RULES.md`'s practical-advice policy before using this claim
anywhere near specific numbers.
UNSAFE: "One report cancels out 468 likes."

**23.**
SAFE: "The checked-in scoring setup gives a report prediction a very large negative
weight — not because reports are common, but because Phoenix's predicted probability of a
report is tiny, so the weight has to be large for that small predicted risk to move the
score at all."
CLASS: CHECKED-IN DEFAULT · MASTER: §6 · CAVEAT: State the weight-vs-probability
distinction every time this claim appears.
UNSAFE: "Getting reported costs you 468 likes worth of reach."

**24.**
SAFE: "Under checked-in defaults, several predicted heads — like profile clicks and the
older discrete dwell signal — are wired up and predicted but weighted at exactly zero,
contributing nothing to today's score."
CLASS: CHECKED-IN DEFAULT · MASTER: §6 · CAVEAT: "Today's score" means the checked-in
default score, not necessarily production.
UNSAFE: "Profile clicks never matter to the algorithm."

**25.**
SAFE: "The checked-in scoring setup gives relatively more weight to a predicted reply
than a predicted favorite — reply weight is ten times favorite weight before any
mutual-follow boost is applied."
CLASS: CHECKED-IN DEFAULT · MASTER: §6 · CAVEAT: This is a ratio between weights on
predicted probabilities, not a claim that replies are worth 10x the "value" of a like in
any literal sense.
UNSAFE: "Replies are worth 10 likes."

---

## DIVERSITY / DPP

**26.**
SAFE: "VMRanker's diversity-selection algorithm (DPP) is fully public, readable source
code in this repository — not an unpublished external system, a correction to an earlier
internal misreading of this material."
CLASS: DIRECT · MASTER: §8 · CAVEAT: None.
UNSAFE: "VMRanker's algorithm is a secret black box."

**27.**
SAFE: "When DPP selection runs, selected candidates keep their exact original
RankingScorer score; unselected candidates come back with a score of exactly zero — it's
a diversity-aware selection mask on top of RankingScorer's ordering, not a second
independent model producing a new score."
CLASS: DIRECT · MASTER: §8 · CAVEAT: None.
UNSAFE: "VMRanker re-scores every post with its own model."

**28.**
SAFE: "Home Mixer's checked-in default asks VMRanker to run DPP diversity selection on
every call — but VMRanker's own server-side flag for actually performing it defaults to
off, meaning under checked-in defaults on both sides, the server would just echo scores
back unchanged."
CLASS: CHECKED-IN DEFAULT (two separate defaults) · MASTER: §8 · CAVEAT: Always name
which default (client request vs. server flag) — conflating them was flagged twice during
review.
UNSAFE: "DPP diversity selection always runs."

**29.**
SAFE: "Author diversity in ranking is a decaying discount with a floor, not a hard cap —
a second post from the same author is discounted, a third more so, converging toward
roughly a quarter of full score rather than ever reaching zero."
CLASS: CHECKED-IN DEFAULT · MASTER: §7 · CAVEAT: Seeing the same author repeated is a
designed possibility, not a bug.
UNSAFE: "The algorithm blocks a second post from the same author."

**30.**
SAFE: "If a candidate has no precomputed embedding on file for DPP's similarity
comparison, the code generates a random unit vector on the spot as a documented fallback —
this repository doesn't say how often that happens in practice."
CLASS: DIRECT (fallback exists) / UNKNOWN (frequency) · MASTER: §8 · CAVEAT: Don't
present this as a routine occurrence.
UNSAFE: "DPP usually falls back to random vectors."

---

## VISIBILITY FILTERING

**31.**
SAFE: "Visibility filtering is a structurally separate question from ranking: given a
specific viewer and a specific post, is this even allowed to be shown, in this context, at
all? A post can be the highest-scoring candidate in the whole batch and still never
reach the client."
CLASS: DIRECT · MASTER: §9 · CAVEAT: This is the project's single most important
myth-busting claim — anchor diagram 04 on it.
UNSAFE: "A high score guarantees your post gets shown."

**32.**
SAFE: "Visibility filtering evaluates a post under one of two policies depending on
whether it's in-network or out-of-network — the out-of-network policy is meaningfully
stricter, with roughly two dozen additional drop rules that simply don't apply to people
you follow."
CLASS: DIRECT · MASTER: §9 · CAVEAT: None.
UNSAFE: "Everyone sees the exact same moderation rules on every post."

**33.**
SAFE: "Interstitial and Drop are different outcomes: an interstitialed post is still
delivered to the client, flagged for a tap-through warning; only a Drop actually removes
the post from the response."
CLASS: DIRECT · MASTER: §9 · CAVEAT: Conflating these is one of the most common
misreadings this project exists to prevent.
UNSAFE: "An interstitial means the post was removed."

**34.**
SAFE: "The exact same post, carrying the exact same label, can be shown — with a warning —
to people who already follow the author, and dropped entirely for people who don't. This
repository's own tests assert exactly that, side by side, for several labels."
CLASS: DIRECT · MASTER: §9, §11 · CAVEAT: This is a deliberate design choice visible in
the rule set (restricting discovery, not erasing content for people who already opted
in), not a bug or inconsistency.
UNSAFE: "The algorithm is inconsistent about what it allows."

**35.**
SAFE: "A reply to a post that was independently Dropped disappears too, even if the reply
itself, considered alone, would have been Allowed."
CLASS: DIRECT · MASTER: §9 · CAVEAT: None.
UNSAFE: "Replies are always judged independently of their parent post."

---

## SAFETY / REPUTATION

**36.**
SAFE: "BDSM stands for Behavioral Detection Sequence Model — despite the acronym, it's an
anti-bot, inauthentic-behavior detector, not an NSFW or adult-content classifier."
CLASS: DIRECT · MASTER: §10 · CAVEAT: This exact confusion is common enough to warrant a
dedicated myth entry.
UNSAFE: "BDSM is X's adult-content filter."

**37.**
SAFE: "Botmaker is a general-purpose rule-processing engine; Scarecrow is the specific
production deployment of it used for spam and abuse — they are not the same thing, and an
earlier internal reading of this repository that concluded 'no concrete rules are checked
in' was wrong because it only looked in the generic Botmaker directory."
CLASS: DIRECT · MASTER: §10 · CAVEAT: 20 real, active Scarecrow rules are checked in —
this is a real, non-trivial, partial subset of unknown completeness relative to
production, not the whole rule corpus and not zero rules either.
UNSAFE: "None of X's spam rules are public." / "All of X's spam rules are public."

**38.**
SAFE: "Gizmoduck holds account-level safety flags and labels, and is queried live and
synchronously on every request — but it isn't a detector itself. Other systems (like
Scarecrow) write labels into it; visibility filtering reads from it."
CLASS: DIRECT · MASTER: §10 · CAVEAT: Gizmoduck does not hold follow/block/mute
relationships — those come from a separate social-graph client, a distinction an earlier
internal draft got wrong.
UNSAFE: "Gizmoduck decides who's a bot."

**39.**
SAFE: "UserCredV2, a PageRank-style credibility score computed from the real follow
graph, is used directly as a skip-gate in one enforcement system's rules, and — one layer
removed, as `IsHighPageRankUser` — as a skip-gate across the large majority of Scarecrow's
checked-in rules."
CLASS: DIRECT · MASTER: §10 · CAVEAT: None.
UNSAFE: "Follower count alone determines moderation exemptions."

**40.**
SAFE: "A label being actively written by a real, confirmed rule is not proof it has any
consequence for your feed — several confirmed labels (`AGATHA_SPAM`,
`AGATHA_SPAM_TOP_USER`, `RISKY_HIGH_VIZ_REPLY`, `COPYPASTA_SPAM`) don't appear anywhere in
visibility filtering's rule set under those exact names."
CLASS: DIRECT · MASTER: §10, §11 · CAVEAT: Don't assume a spam-adjacent-sounding label
automatically causes a drop — it might feed an entirely different system (search
demotion, notification filtering) this snapshot doesn't trace.
UNSAFE: "Any spam-related label means your post gets buried."

**41.**
SAFE: "`phoenix-rankall` runs a second, structurally distinct safety check at index-admission
time — a full visibility-filtering evaluation with no viewer at all, run once per post —
separate from the per-viewer visibility filtering that happens later, per request."
CLASS: DIRECT · MASTER: §10 · CAVEAT: Its failure behavior varies by exception type
(some fail open, some fail closed, one branch's behavior is unknown) — don't summarize it
as a single uniform rule.
UNSAFE: "Index-time visibility filtering always fails open."

**42.**
SAFE: "BDSM's real operating thresholds are deliberately redacted in this public
release — shipped as an obviously invalid sentinel value, specifically so the detection
boundary can't be reverse-engineered."
CLASS: DIRECT · MASTER: §10 · CAVEAT: This is a stronger statement than "unknown" — it's
intentionally hidden, and content should reflect that distinction.
UNSAFE: "BDSM's thresholds just haven't been documented yet."

---

## FEED BLENDING

**43.**
SAFE: "Ads, Who to Follow suggestions, and prompts are added after organic ranking is
completely finished — Phoenix and its scorers never see an ad or a Who to Follow card."
CLASS: DIRECT · MASTER: §12 · CAVEAT: None.
UNSAFE: "Ads compete with your posts for ranking score."

**44.**
SAFE: "Blending in ads and other modules is a sequence of insert operations at fixed
positions, not a unified scored ranking."
CLASS: DIRECT · MASTER: §12 · CAVEAT: Execution order in code isn't the same as final
visual order — a push-to-home post is inserted after prompts and Who to Follow in code
but pinned ahead of them in the final list.
UNSAFE: "Everything in your feed, including ads, is ranked by the same model."

**45.**
SAFE: "If an ad ends up next to a post you've already seen, a repair mechanism tries to
swap in a different post — and it only drops the ad if no swap can be found anywhere in
the list; it never removes an organic post to fix an ad-placement problem."
CLASS: DIRECT · MASTER: §12 · CAVEAT: None.
UNSAFE: "Organic posts get bumped to make room for ads."

---

## CACHING

**46.**
SAFE: "A cached response reuses Phoenix predictions from up to about three minutes
earlier, but RankingScorer and VMRanker both re-run in full, using whatever ranking
weights are active right now."
CLASS: CHECKED-IN DEFAULT · MASTER: §13 · CAVEAT: A feature-switch weight change deployed
within that window can genuinely change a cached response's order even though the
underlying predictions never changed.
UNSAFE: "A cached feed is a frozen replay of an earlier ranking."

**47.**
SAFE: "Caching skips fresh retrieval and a fresh Phoenix inference call — it does not
skip RankingScorer or VMRanker."
CLASS: DIRECT · MASTER: §13 · CAVEAT: None.
UNSAFE: "Caching means your feed doesn't update for 3 minutes."

---

## FAILURE MODES

**48.**
SAFE: "Almost everything that can go wrong during a request degrades gracefully — one
broken retrieval source contributes zero candidates while the others continue unaffected,
rather than the whole request failing."
CLASS: DIRECT · MASTER: §14 · CAVEAT: None.
UNSAFE: "The feed never has any component fail."

**49.**
SAFE: "Visibility filtering's failure behavior isn't one uniform rule: a whole failed RPC
batch fails open (candidates kept), but a response missing one specific post ID, or
unable to resolve a post's author, fails closed (treated as dropped) — three different
outcomes for three different failure shapes."
CLASS: DIRECT · MASTER: §14 · CAVEAT: Never collapse this into a single "VF fails open"
or "VF fails closed" statement — this exact collapse was specifically flagged as a
mistake to avoid.
UNSAFE: "Visibility filtering always fails open, so errors mean unsafe content gets
through."

**50.**
SAFE: "A background side effect — logging, cache-writing, served-history updates — can
never change the response you already received. Its only possible effect is on a future
request."
CLASS: DIRECT · MASTER: §14 · CAVEAT: None.
UNSAFE: "Your engagement on this load can retroactively change what you're seeing right
now."

---

## CONFIG / EXPERIMENTS

**51.**
SAFE: "Nearly every specific number in this material — every weight, every threshold,
every percentage — is a checked-in default read directly from source code, not a live
production value. The repository says so about itself, in its own comments."
CLASS: DIRECT · MASTER: §15 · CAVEAT: This claim should anchor essentially every other
numeric claim in this project.
UNSAFE: "These are the current live settings."

**52.**
SAFE: "This repository shows the full matching machinery a feature switch could use to
apply a different value per user or per experiment — user ID, country, language, client
version, account age, and about ten other attributes — but it never shows a single live
value that machinery would actually apply."
CLASS: DIRECT · MASTER: §15 · CAVEAT: There's no exposed device-type field, city-level
location, or raw random seed — so how any percentage rollout derives its randomness isn't
shown either.
UNSAFE: "We know exactly who gets which experiment."

**53.**
SAFE: "Which physical server cluster Phoenix routes a request to has the most
override-flexible mechanism this system documents — an ordinary feature switch, plus a
separately-gated 'decider' layer, plus a distinct override for very new accounts, all able
to change it independently."
CLASS: DIRECT · MASTER: §15 · CAVEAT: None.
UNSAFE: "Cluster routing is a simple, fixed lookup."

---

## PUBLIC VS. PRODUCTION

**54.**
SAFE: "A checked-in default is not a production value; a field appearing in a request is
not proof the model uses it; a model's architecture being public is not the same as its
trained weights being public."
CLASS: DIRECT (this is the master synthesis's own closing framing, safe to quote near-
verbatim) · MASTER: §17 · CAVEAT: This triad of distinctions should anchor the "What the
public repository does NOT tell us" guide directly.
UNSAFE: (any claim that erases one of these three distinctions)

**55.**
SAFE: "This repository never ships X's actual production model checkpoint, the live
values any feature switch would apply, or the offline process that built Phoenix's real
retrieval index for X's actual post corpus."
CLASS: UNKNOWN / NOT PUBLISHED · MASTER: §17 · CAVEAT: None — this is itself the caveat.
UNSAFE: "We know what model X runs today."

**56.**
SAFE: "What specifically sets an account's recommendation-eligibility flag to false isn't
shown anywhere in this snapshot — no code here writes to that field."
CLASS: UNKNOWN / NOT PUBLISHED · MASTER: §17 · CAVEAT: None.
UNSAFE: "We know why specific accounts get suppressed."

**57.**
SAFE: "A retrieval similarity score, a Phoenix action prediction, and a RankingScorer
score are three different numbers that happen to occur in sequence during one request —
not three names for the same thing."
CLASS: DIRECT · MASTER: §17 · CAVEAT: This is a good one-line corrective for readers who
conflate "the algorithm's score" into one number.
UNSAFE: "A post's score" (used without specifying which of the three).

---

Target was roughly 40–70 entries; this bank holds 57, spanning every required category.
Extend it as new artifacts surface claims worth reusing — don't let individual guides
invent their own unreviewed phrasing for a fact already covered here.
