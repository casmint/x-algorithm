# Content Map

Provenance and dependency map between `_analysis/synthesis/HOW_FOR_YOU_WORKS.md` (the
master synthesis) and everything planned in `_explainers/`.

Purpose: make it hard for a future writing session to invent a claim without knowing
which section of the master supports it. When drafting any artifact, find its row(s)
below first, then write from that section — not from memory of the system, and not from
source.

Section numbers and titles below are exact, from the master synthesis as of commit
`a895c97`.

---

## Forward map: master section → derivative content

### §1 — The biggest misconception to unlearn: Phoenix is not "the algorithm"

- **Core concepts:** Phoenix predicts, doesn't decide; Home Mixer is the orchestrator;
  three-way split of orchestrator / local in-process logic (RankingScorer, filters,
  BlenderSelector) / remote dependencies (Phoenix, VMRanker, VF, most retrieval
  backends); Gizmoduck is a live per-request dependency, not a background system.
- **Safest reusable claims:** "Phoenix predicts; other systems decide." "RankingScorer
  runs locally inside Home Mixer, with no remote call." "Gizmoduck is queried live, on
  every request — it's not a background label store like the other safety systems."
- **Likely diagram(s):** 01 (full pipeline — this section is its narrative spine)
- **Likely guide(s):** 5-minute guide, 20-minute guide, "Phoenix is the algorithm" myth
  page
- **Practical implication:** None that follows legitimately — this is architectural
  orientation, not something a poster can act on.
- **Required caveats:** Don't let "Phoenix predicts" imply Phoenix is unimportant —
  everything downstream depends on what it predicts. Don't collapse the three categories
  (orchestrator / local / remote) into just "Home Mixer vs. everything else."
  Gizmoduck must never be grouped with the background safety-label producers (Agatha,
  BDSM, Grox, Botmaker/Scarecrow) — this was a corrected error in an earlier synthesis
  draft (see `ADVERSARIAL_REVIEW.md` AR-002).
- **Checked-in numeric defaults involved:** No.
- **Live production state unknown:** N/A (architectural fact, not a tunable value).

### §2 — The whole journey, once, before the detail

- **Core concepts:** the full request path in order; which stages run concurrently
  (retrieval sources, hydration) vs. strictly sequentially (pre-scoring filters, the
  three scorers); the organic pipeline is itself just one input to an outer ad/WTF/prompt
  blending pipeline; side effects fire after the response and cannot change it.
- **Safest reusable claims:** "Whichever retrieval sources are enabled run at the same
  time; their results are just concatenated — no priority order." "Filters and scorers
  run in a strict, fixed sequence because later stages depend on what earlier stages
  wrote." "Side effects (logging, cache writes) can only affect a future request, never
  the current one."
- **Likely diagram(s):** 01 (full pipeline — direct source)
- **Likely guide(s):** 5-minute guide, 20-minute guide
- **Practical implication:** None directly — this is a map, not a mechanism to exploit.
- **Required caveats:** Concurrency among retrieval sources doesn't mean "first source
  wins" or "more sources = better odds" in any simple sense — it means their candidate
  pools are pooled without ranking priority at that step.
- **Checked-in numeric defaults involved:** Top 50 kept after scoring; truncated to 35
  organic posts before blending.
- **Live production state unknown:** Whether these exact numbers (50, 35) are live today.

### §3 — Retrieval: where posts come from

- **Core concepts:** seven candidate sources, only enabled ones run; Thunder (in-network,
  recency-based); SimClusters (engagement-seeded similarity search); Phoenix retrieval
  family (`PhoenixSource`/`PhoenixTopicsSource`/`PhoenixMOESource`, one dispatch
  mechanism, three configurations); `phoenix-rankall` as index-admission (separate layer
  from serving-time search); the two-tower retrieval model; TweetMixer (external,
  disabled by default); CachedPostsSource (reuse, not retrieval); universal 48-hour age
  filter.
- **Safest reusable claims:** "Being retrieved at all is a prerequisite to being
  ranked — you can't be shown a post no source found." "Replies, retweets, and community
  posts are excluded from Phoenix's mainstream retrieval indices, regardless of
  engagement — with one narrower, unconfirmed-reach exception (`search_unfiltered`)."
  "A post's favorite count only re-triggers Phoenix index updates at power-of-two
  thresholds (1, 2, 4, 8, 16...), not on every like." "SimClusters needs at least one
  recent engagement signal from you — with none, you get zero SimClusters candidates."
  "`phoenix-rankall` decides what enters the retrieval corpus; a separate two-tower
  search decides what a specific request pulls out of it — these are different layers."
- **Likely diagram(s):** 02 (retrieval sources — primary), 06 (Phoenix two-tower
  retrieval — model-side zoom-in)
- **Likely guide(s):** "Where recommended posts actually come from"
- **Practical implication:** "Being retrieved is necessary but not sufficient" is a
  legitimate, source-grounded practical point. Do NOT extend it to specific posting
  advice about triggering retrieval.
- **Required caveats:** `search_unfiltered`'s live reachability is unknown — don't
  present "replies are excluded from Phoenix" as an unqualified absolute (AR-008). Don't
  conflate `phoenix-rankall` admission with the two-tower serving-time search — they are
  two different systems with two different questions.
- **Checked-in numeric defaults involved:** 48-hour age filter; Thunder's ~48-hour
  retention window; SimClusters' ~2-day internal age window.
- **Live production state unknown:** which Phoenix retrieval cluster each `Phoenix*Source`
  actually reaches at runtime; whether `search_unfiltered` feeds any live retrieval path;
  contents of the production post-vector table; the trained checkpoint itself.

### §4 — What the system knows about you and the post

- **Core concepts:** hydration step (concurrent lookups); viewer-side and post-side
  fields; the Phoenix scoring request carries identifiers/counts/flags, not raw text or
  media.
- **Safest reusable claims:** "The request Home Mixer sends Phoenix for scoring doesn't
  carry post text or media — only identifiers, counts, and flags." "The likely
  explanation is that a semantic ID stands in for richer content on the serving side —
  but this repository doesn't contain the code that would prove that, only the absence of
  text/media in the request."
- **Likely diagram(s):** 03 (ranking stack, as input framing)
- **Likely guide(s):** "How ranking actually works"
- **Practical implication:** None directly.
- **Required caveats:** Keep the "field present in request" vs. "model actually uses it"
  distinction intact — a field being absent is DIRECT evidence; the semantic-ID
  explanation for why is STRONG INFERENCE, not confirmed.
- **Checked-in numeric defaults involved:** No.
- **Live production state unknown:** What content representation the semantic ID
  actually resolves to server-side.

### §5 — Phoenix: predicting what you'll do

- **Core concepts:** ~24 separate action predictions per candidate, independent sigmoid
  heads; empty-history behavior (zeros, not an error); failed-call behavior (stale
  values persist); model-config-family pairing (`home_direct_packed*` for ranking,
  `xrecsys_two_tower*` for retrieval, both shipped-tooling facts, not production facts);
  per-request scoring capacity and silent truncation of excess candidates.
- **Safest reusable claims:** "Phoenix predicts roughly two dozen separate outcomes per
  post — it isn't one score." "If Phoenix's model call fails, nothing gets overwritten —
  candidates just keep whatever prediction they already had." "Phoenix's ranking service
  has a hard per-request scoring capacity; candidates beyond it get no prediction at all,
  silently — not a low score, no prediction."
- **Likely diagram(s):** 03 (ranking stack — primary)
- **Likely guide(s):** "How ranking actually works," "What the public repository does NOT
  tell us"
- **Practical implication:** None safely stateable at the individual-post level — this is
  model behavior, not a lever a poster controls.
- **Required caveats:** The model-config pairing is "the repository's own shipped
  reference tooling documents this pairing," never "this is what production runs."
  Capacity numbers (2,800 packed, 1,400 launcher default, 64 training default) are
  checked-in values, not confirmed production settings — don't present any of them as
  "the" real number.
- **Checked-in numeric defaults involved:** Yes — 2,800 candidate pack limit, 1,400
  launcher-default scoring capacity, 64 training-config declared capacity.
- **Live production state unknown:** Which model config is actually deployed; the real
  per-request scoring capacity in production; what happens downstream to a
  capacity-truncated candidate.

### §6 — RankingScorer: turning predictions into a score

- **Core concepts:** weighted sum of predicted probabilities/values; the full checked-in
  weight table; explicit warning against reading weights as an exchange rate between
  raw events; worked numeric example; smoothing/normalization step on net-negative
  totals.
- **Safest reusable claims:** "RankingScorer's weights multiply predicted probabilities,
  not raw counts of past engagement." "A weight of -234 on report doesn't mean '1 report
  cancels 468 likes' — reports are predicted at a much smaller probability than
  favorites, so the weight has to be large for a small predicted risk to matter." "The
  checked-in scoring setup gives relatively more weight to predicted replies than
  predicted favorites."
- **Likely diagram(s):** 03 (ranking stack — primary; this is the "Σ(prediction ×
  weight)" box)
- **Likely guide(s):** "How ranking actually works," "One report cancels hundreds of
  likes" myth page
- **Practical implication:** This is the single most tempting section to over-translate
  into growth-hacking advice. See `EDITORIAL_RULES.md`'s practical-advice policy before
  writing anything derived from this section.
- **Required caveats:** Never state the weight table as raw-event exchange rates. Always
  attach "checked-in default, not confirmed production value" to the weight table itself.
- **Checked-in numeric defaults involved:** Yes — the full weight table (favorite 0.5
  through report -234.0), dwell weight 0.004, not-dwelled weight -0.02.
- **Live production state unknown:** Whether these exact weight values are live today.

### §7 — Network position, boosts, and cold start

- **Core concepts:** out-of-network discount (0.75×/0.5× topic-scoped) — and that it also
  applies to in-network replies/retweets under current defaults; mutual-follow boost
  (+15.0 reply weight for original posts only); author diversity decay (not a hard cap,
  floor ~25%); cold-start floor mechanism (position-16 floor, pre-adjustment only, not a
  guaranteed final slot).
- **Safest reusable claims:** "Repeated posts from one author face a decaying diversity
  discount, not a hard limit — it never reaches zero." "Cold start floors one small
  account's score to what a mid-pack post is currently scoring — it doesn't guarantee
  that post a place in the feed; later adjustments can still move it anywhere."
  "In-network replies and retweets can, under today's checked-in default, get the same
  discount as a stranger's post — this is a real, non-obvious wrinkle, not a bug in this
  document."
- **Likely diagram(s):** 03 (ranking stack — the "adjustments" box)
- **Likely guide(s):** "How ranking actually works"
- **Practical implication:** "Posting once beats reposting the same point five times back
  to back, because of author diversity" is a defensible, bounded practical read. Do NOT
  turn the cold-start floor into "new accounts are guaranteed visibility."
- **Required caveats:** Cold start = floor on pre-adjustment score, not a placement
  guarantee — this exact distinction is one of the master synthesis's most carefully
  worded passages; don't simplify it away.
- **Checked-in numeric defaults involved:** Yes — 0.75×/0.5× OON discount, +15.0 mutual
  boost, ~62.5%/~44%/→25% diversity decay curve, rank-15 cold-start floor position.
- **Live production state unknown:** Whether these values are live today.

### §8 — VMRanker and the DPP diversity layer

- **Core concepts:** VMRanker is a checked-in, fully public Rust service, not an external
  black box (this corrects an earlier internal research error); DPP mode as a
  diversity-aware selection mask, not a second predictive model; two independent
  defaults — Home Mixer's request default (asks for DPP every call) vs. VMRanker
  server's own flag default (`--dpp-enabled=false`); random-vector fallback for
  candidates with no embedding.
- **Safest reusable claims:** "VMRanker's diversity algorithm (DPP) is fully public,
  readable source code — not an unpublished black box." "Selected candidates keep their
  original score exactly; unselected candidates come back at exactly zero — DPP doesn't
  recompute a new score." "Home Mixer's checked-in default asks VMRanker to run DPP on
  every call, but VMRanker's own checked-in server flag for actually doing so defaults to
  off — these are two separate defaults, and conflating them was a documented error in an
  earlier draft (see `GLOSSARY.md` correction / AR-003)."
- **Likely diagram(s):** 03 (ranking stack — the DPP box, explicitly marked optional)
- **Likely guide(s):** "How ranking actually works," "DPP definitely runs in production"
  myth page
- **Practical implication:** None safely stateable.
- **Required caveats:** Always name *which* default (Home Mixer's request default vs.
  VMRanker server's own flag) when discussing DPP — this exact ambiguity was flagged
  twice in adversarial review (main text got it right, glossary initially didn't).
- **Checked-in numeric defaults involved:** Yes — Home Mixer requests DPP by default;
  VMRanker's own `--dpp-enabled` flag defaults to `false`.
- **Live production state unknown:** Whether the VMRanker server flag is `true` in
  production; contents of the live embedding store.

### §9 — Visibility filtering: ranking is not the final word

- **Core concepts:** VF as a structurally separate question from ranking; four distinct
  exclusion mechanisms (index-time, pre-ranking filter, ranking penalty, post-ranking VF)
  with different scopes/failure modes; TimelineHome vs. TimelineHomeRecommendations
  policies; Allow/Interstitial/Drop evaluation order and semantics; Interstitial ≠ Drop;
  ancestor/quote/retweet cascade removal; author-viewing-own-content and
  already-following exceptions.
- **Safest reusable claims:** "A post can be the highest-scoring candidate in the whole
  batch and still never reach the client — visibility filtering runs after scoring and
  can remove it anyway." "Interstitial means the post is still delivered, with a warning
  the viewer can tap through — it is not the same as being removed." "The exact same
  post, with the exact same label, can be shown (with a warning) to people who follow the
  author and dropped entirely for people who don't — this isn't a bug, it's how the rule
  set is built." "Out-of-network content is checked against a meaningfully stricter
  policy than in-network content."
- **Likely diagram(s):** 04 (ranking vs. visibility — primary)
- **Likely guide(s):** "How Visibility Filtering works," "Why didn't a highly-ranked post
  necessarily appear?"
- **Practical implication:** None safely stateable at the individual-post level.
- **Required caveats:** Never say "Allow" means guaranteed final display — allow just
  means VF raised no objection at that stage; BlenderSelector and truncation still apply
  afterward. Never conflate index-time exclusion (viewer-less, pre-request) with
  per-request VF (per-viewer, post-ranking).
- **Checked-in numeric defaults involved:** No specific weights; VF runs on the top-50
  candidates specifically (a checked-in pipeline constant, see §2).
- **Live production state unknown:** Whether the full rule set shown here is complete or
  a subset of what's live.

### §10 — Where the safety labels come from

- **Core concepts:** the detector → enforcement → label/state → consumer chain; Grox
  (content classifier, feeds index admission); the second, structurally distinct
  index-time VF check (`shouldDropPostByVF`, viewer-less, stricter policy, specific
  fail-open/fail-closed behavior per exception type); Agatha (reputation scores, no
  direct consumer of its formal outputs, but named features feed two Scarecrow rules);
  BDSM (anti-bot, NOT adult-content, despite the name; redacted thresholds); UserCredV2
  (PageRank-style credibility, pervasive skip-gate); Botmaker (generic rule engine) vs.
  Scarecrow (its production spam/abuse deployment, 20 public rules); abuse-enforcement-
  service (Kafka consumer, not per-request); Gizmoduck (live account-state store, queried
  synchronously per request, NOT a detector, does not hold follow/block/mute
  relationships).
- **Safest reusable claims:** "BDSM stands for Behavioral Detection Sequence Model — it's
  an anti-bot detector, not an adult-content classifier, despite the acronym." "Botmaker
  is the general rule engine; Scarecrow is the specific spam/abuse rule deployment built
  on it — they are not the same thing." "Gizmoduck holds account state and is queried
  live on every request — it doesn't detect anything itself; Scarecrow and others write
  labels into it, and visibility filtering reads from it." "A real, 20-rule subset of
  Scarecrow's production spam/abuse rules is checked into this repository, with exact
  thresholds — but this is a subset of unknown completeness relative to what X actually
  runs, not the whole rule corpus."
- **Likely diagram(s):** 05 (safety/reputation flow — primary)
- **Likely guide(s):** "How safety labels reach the feed"
- **Practical implication:** None safely stateable.
- **Required caveats:** Don't imply every detector feeds every enforcement system — only
  draw arrows for relationships the master synthesis actually establishes. A label
  existing (e.g. `AGATHA_SPAM`, `RISKY_HIGH_VIZ_REPLY`) is not proof it has any feed
  consequence — several confirmed, actively-written labels have no confirmed VF
  consumer.
- **Checked-in numeric defaults involved:** BDSM's real thresholds are deliberately
  redacted (sentinel values) — not just unknown, intentionally hidden.
- **Live production state unknown:** BDSM's real thresholds; completeness of the public
  20-rule Scarecrow subset relative to production.

### §11 — Label to consequence, concretely

- **Core concepts:** the exact producer→consumer label table (`SPAM`,
  `SPAM_HIGH_RECALL`, `NSFW_HIGH_PRECISION`/`NSFW_HIGH_RECALL`, `NSFW_CARD_IMAGE`,
  `GORE_AND_VIOLENCE_HIGH_PRECISION`, `MALICIOUS_URL`) with in-network/OON outcomes;
  labels with no confirmed feed consequence (`AGATHA_SPAM`, `AGATHA_SPAM_TOP_USER`,
  `RISKY_HIGH_VIZ_REPLY`, `COPYPASTA_SPAM`).
- **Safest reusable claims:** the exact table rows, stated as-is, are safe to reuse
  verbatim — they were independently verified by string match on both producer and
  consumer sides.
- **Likely diagram(s):** 04 (ranking vs. visibility, as a worked example), 05 (safety
  flow, as concrete instances)
- **Likely guide(s):** "How safety labels reach the feed," "Why didn't a highly-ranked
  post necessarily appear?"
- **Practical implication:** None.
- **Required caveats:** Never extrapolate from this table to a label not in it —
  "sounds spam-adjacent" is explicitly not sufficient grounds to assume a drop.
- **Checked-in numeric defaults involved:** No.
- **Live production state unknown:** Whether this exact rule set is what's live.

### §12 — Beyond posts: ads and the rest of the feed

- **Core concepts:** `ForYouCandidatePipeline` as an outer pipeline treating the organic
  pipeline as one of seven inputs; `BlenderSelector`; three interchangeable ad-blend
  strategies (partition-based/default, safe-gap, time-gap) with a real strictness
  difference; fixed-position insertion for prompts/WTF/push-to-home/frames/survey
  (execution order ≠ final visual order, because push-to-home is pinned to the front);
  `AdAdjacentServedFilter`'s ad-only repair behavior.
- **Safest reusable claims:** "Ads, Who to Follow, and prompts are inserted after organic
  ranking is already finished — Phoenix and its scorers never see them." "None of the
  non-post insertion is a scored blend — it's a sequence of insert operations at fixed
  positions." "If an ad-adjacency repair can't find a swap, the ad gets dropped — an
  organic post is never sacrificed to fix an ad-placement problem."
- **Likely diagram(s):** 01 (full pipeline, later stages)
- **Likely guide(s):** 20-minute guide (as a closing stage)
- **Practical implication:** None.
- **Required caveats:** Don't imply this blending is unified ranking — it explicitly
  isn't.
- **Checked-in numeric defaults involved:** No specific numbers highlighted.
- **Live production state unknown:** Which ad-blend strategy is live for a given request.

### §13 — Caching: a 180-second shortcut, not a frozen feed

- **Core concepts:** cache activation threshold (≥500 candidates, ~3 min old); what
  caching skips (retrieval, fresh Phoenix inference) vs. what it doesn't (RankingScorer,
  VMRanker both re-run with current weights).
- **Safest reusable claims:** "A cached response reuses old predictions but re-scores
  them with whatever ranking weights are active right now — it's stale predictions,
  freshly re-weighted, not a frozen replay."
- **Likely diagram(s):** 01 (as an annotation/side note)
- **Likely guide(s):** 20-minute guide
- **Practical implication:** None.
- **Required caveats:** None beyond standard checked-in-default framing.
- **Checked-in numeric defaults involved:** Yes — ≥500 candidates, ~180-second window.
- **Live production state unknown:** Whether these exact thresholds are live.

### §14 — What happens when things fail

- **Core concepts:** general degrade-gracefully pattern during requests vs. fail-hard
  pattern at server startup; specific per-system failure table (retrieval source down,
  Phoenix call fails, VMRanker call fails, VF batch fails [open], VF missing one post ID
  [closed], VF can't resolve author [closed], SimClusters signal-lookup failure aborts
  the whole SimClusters contribution, background side effects never affect the current
  response).
- **Safest reusable claims:** "Almost everything that can go wrong during a request
  degrades gracefully — a broken component contributes nothing rather than blocking your
  feed." "Visibility filtering's failure behavior isn't one uniform rule — a whole failed
  RPC batch fails open (kept), but a missing single post ID in an otherwise-successful
  response fails closed (dropped) — these are two different rows, not one blanket
  statement."
- **Likely diagram(s):** none dedicated; useful as a sidebar/footnote on diagram 01
- **Likely guide(s):** "What the public repository does NOT tell us" (as a "what's robust"
  counterpoint), 20-minute guide
- **Practical implication:** None.
- **Required caveats:** Don't collapse the VF failure table into "VF fails open" —
  that's a specifically flagged wrong simplification.
- **Checked-in numeric defaults involved:** No.
- **Live production state unknown:** N/A (this is architecture, not a tunable).

### §15 — Feature switches: why "checked-in default" isn't "what you get"

- **Core concepts:** every number in the document is a checked-in default, not a live
  value; feature-switch matching keys (~15 attributes: user ID, country, language,
  client app/version, account roles, datacenter, account age in days/minutes, verified
  phone, request type, "resurrected" status); no device type, city, or raw random seed
  exposed; decider as a second, independently-gated override layer; Phoenix cluster
  routing as the single most override-flexible parameter (feature switch + decider + new-
  account override).
- **Safest reusable claims:** "Nearly every specific number in this material — every
  weight, every threshold — is a checked-in default read from source code, not a live
  production value, and the repository says so about itself." "The matching machinery for
  per-user/per-experiment overrides is fully visible; the live values it would apply
  never are."
- **Likely diagram(s):** none dedicated; this is the conceptual backbone of every
  "checked-in default" badge across all six diagrams
- **Likely guide(s):** "What the public repository does NOT tell us"
- **Practical implication:** None — this is the section most directly warning against
  practical over-claiming from any other section.
- **Required caveats:** This section IS the caveat — every other artifact's numeric
  claims should point back here rather than re-explaining the checked-in-vs-live
  distinction each time.
- **Checked-in numeric defaults involved:** N/A — this section is about the mechanism of
  defaults, not a specific default itself.
- **Live production state unknown:** Everything the matching machinery could apply —
  by definition, this section's entire subject.

### §16 — "Why did I see this post?" — three walk-throughs

- **Core concepts:** three worked examples tying every mechanism above together — an
  in-network post, an out-of-network discovery, and a high-scoring post that still gets
  dropped by VF.
- **Safest reusable claims:** each walkthrough, summarized faithfully, is directly safe
  to reuse.
- **Likely diagram(s):** 04 (ranking vs. visibility — walkthrough C is this diagram's
  headline example)
- **Likely guide(s):** "Why did I see this post?" practical piece — this section IS its
  primary source
- **Practical implication:** This section is the closest thing the master synthesis has
  to consumer-facing practical content already, and should anchor that entire artifact
  family.
- **Required caveats:** Same as §§3–11 individually, since each walkthrough draws on them.
- **Checked-in numeric defaults involved:** Via reference to §§6–7.
- **Live production state unknown:** Via reference to §15.

### §17 — What we can and cannot know

- **Core concepts:** the explicit "directly established" vs. "not knowable from this
  snapshot" lists; the closing set of sharp distinctions (checked-in default ≠
  production value, field-in-request ≠ model-uses-it, architecture-public ≠
  weights-public, label-exists ≠ feed-consequence, similar-names ≠ same-label,
  interstitial ≠ drop, index-exclusion ≠ per-request-filter, retrieval/Phoenix/
  RankingScorer scores are three different numbers).
- **Safest reusable claims:** the entire "not knowable" list is directly reusable,
  verbatim in spirit, as the backbone of `EDITORIAL_RULES.md` and the "what this
  repository does NOT tell us" guide.
- **Likely diagram(s):** all six (every diagram's "Provenance" and "What this must NOT
  imply" sections should trace back to this section's distinctions)
- **Likely guide(s):** "What the public repository does NOT tell us" — this section IS
  that guide's spine
- **Practical implication:** This section is the strongest possible source for
  "growth-hacking is not what this document supports" framing.
- **Required caveats:** N/A — this section is itself the caveat layer.
- **Checked-in numeric defaults involved:** N/A.
- **Live production state unknown:** This entire section enumerates exactly that.

---

## Reverse map: artifact → master sections used

| Artifact | Master sections |
|---|---|
| Diagram 01 — Full For You pipeline | §§1–2, §12, §13, §14 (failure notes) |
| Diagram 02 — Retrieval sources | §3 |
| Diagram 03 — Ranking stack | §§4–8 |
| Diagram 04 — Ranking vs. Visibility | §§9, 11, 16 (walkthrough C) |
| Diagram 05 — Safety/reputation signal flow | §§10–11 |
| Diagram 06 — Phoenix two-tower retrieval | §3 (retrieval-serving paragraphs), plus
  `PHOENIX_SERVING_AND_RETRIEVAL.md`'s "Synthesis impact" §2 |
| 5-minute guide | §§1–2, 16 |
| 20-minute guide | §§1–15 (full walk, compressed) |
| "Where recommended posts actually come from" | §3 |
| "How ranking actually works" | §§4–8 |
| "How Visibility Filtering works" | §§9, 11 |
| "How safety labels reach the feed" | §§10–11 |
| "What the public repository does NOT tell us" | §§5, 8, 14–15, 17 |
| "Why did I see this post?" | §16, drawing on §§3–11 |
| "Why didn't a highly-ranked post necessarily appear?" | §9, §16 walkthrough C |
| Myth: "Phoenix is the algorithm" | §1 |
| Myth: "One report cancels hundreds of likes" | §6 |
| Myth: "X globally ranks every tweet" | §§2–3 |
| Myth: "A high score guarantees visibility" | §9, §16 walkthrough C |
| Myth: "All OON recommendations come from one recommender" | §3 |
| Myth: "Checked-in weights prove today's production settings" | §15, §17 |
| Myth: "DPP definitely runs in production" | §8 |
| Myth: "The model reads tweet text and decides if it likes it" | §4, §5 |

Every artifact in `ROADMAP.md` should trace to at least one row above before it moves
past PLANNED status.
