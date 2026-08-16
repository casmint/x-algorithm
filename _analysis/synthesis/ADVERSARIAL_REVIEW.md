# Adversarial Review of Human Synthesis

Reviewed against: `analysis/full-audit` (S00, S01, S02), `_analysis/rapid/01`–`05` on
`analysis/rapid-understanding`. Target: `_analysis/synthesis/HOW_FOR_YOU_WORKS.md` and
`_analysis/synthesis/GLOSSARY.md` at `analysis/human-synthesis` HEAD `0334fbe`.

## Verdict

**READY AFTER MATERIAL CORRECTIONS.**

The great majority of the document's dense factual content — the ranking-weight table and
its arithmetic, the label producer→consumer table, the VF Allow/Interstitial/Drop
semantics and failure-mode breakdown, the corrected VMRanker/DPP narrative in the main
text, the model-config-family correction from Rapid 05, the feature-switch matching-key
enumeration — was checked line-by-line against the ground-truth reports and is accurate,
precisely scoped, and appropriately hedged. This is a carefully-built document.

But it is not ready as-is. One finding (AR-001) is a direct, unresolved self-contradiction
between two glossary entries about the single most foundational architectural distinction
the document claims to teach ("keeping these as separate systems in your head... is the
single most useful thing this document can give you"), and it is echoed by an imprecise
sentence in the main text's own orienting section. A second foundational-section claim
(AR-002) misdescribes Gizmoduck as background-only when the document's own Section 2
diagram and Section 9 VF discussion both depend on Gizmoduck being queried synchronously,
per request. A third (AR-003) reproduces, in the glossary only, exactly the VMRanker
"whose default?" ambiguity the main text went to unusual lengths to correct. These three
sit in the parts of the document a skimming reader is most likely to rely on (Section 1,
the glossary), so they carry more weight than their count suggests.

## Findings

### AR-001 — BLOCKER
**Document(s):** GLOSSARY.md ("Home Mixer" and "RankingScorer" entries); HOW_FOR_YOU_WORKS.md §1
**Quoted wording:**
> Home Mixer — ... It doesn't rank or filter anything itself; it calls out to retrieval
> sources, Phoenix, RankingScorer, VMRanker, and visibility filtering in a fixed order...

versus, four entries later in the same file:

> RankingScorer — ... Runs entirely inside Home Mixer — no external call.

**Problem:** These two glossary entries directly contradict each other. "It doesn't rank
... anything itself; it calls out to ... RankingScorer" asserts RankingScorer is an
external thing Home Mixer invokes; "Runs entirely inside Home Mixer — no external call"
asserts the opposite. Only one can be true, and per S01/Rapid 02 it's the second: the
weighted-sum formula, author-diversity discount, OON discount, cold-start floor, and
`offset_score` compression all execute as ordinary Rust code inside the Home Mixer
process, with no RPC. The same problem applies to "filter... itself": 18 pre-scoring
filters and 3 post-selection filters (`DropDuplicatesFilter`, `AgeFilter`,
`SelfTweetFilter`, `VFFilter`, `AncillaryVFFilter`, `DedupConversationFilter`, etc.) are
Home Mixer's own local removal logic — they read fields (some of which were populated by
an earlier RPC, e.g. VF's verdict) but the *filtering decision itself* is local code, not
a call-out. The main text's Section 1 orchestra framing ("Home Mixer ... calls out to the
other systems below in a specific order") lists RankingScorer in the same breath as
Phoenix, VMRanker, and visibility filtering — three things that genuinely are separate
services reached by RPC — without ever drawing the line the task explicitly anticipated:
orchestrator vs. local in-process component vs. remote service call.
**Ground truth:** S01: "`RankingScorer` is where the actual point-scoring happens,
entirely inside Home Mixer, no external call" (Rapid 02); S01's pipeline inventory: 18
pre-scoring filters + 3 post-selection filters are constructed directly in
`phoenix_candidate_pipeline.rs`, running as declared-order Rust `Filter` trait
implementations inside the same process, not RPC clients.
**Recommended correction:** Rewrite the Home Mixer glossary entry to something like: "Home
Mixer orchestrates the pipeline: it constructs the query, invokes remote services
(retrieval sources, Phoenix, VMRanker, visibility filtering) over RPC, and also runs a
substantial amount of ranking/filtering logic itself, in-process (RankingScorer, all
pre-scoring and post-selection filters)." Apply the same distinction to Section 1's
orchestra framing — the "sections of the orchestra" list should mark which
sections are Home Mixer's own local code versus separate services it calls out to.
**Evidence source:** S01 executive architecture section; Rapid 02 "RankingScorer" section
opening line; `S01_pipeline_inventory.csv` component-type column (implicit in S01's prose
description of the 18+3 filters as constructed directly in the pipeline file).

---

### AR-002 — HIGH
**Document:** HOW_FOR_YOU_WORKS.md §1
**Quoted wording:**
> Safety and reputation systems — Agatha, BDSM, UserCredV2, Grox, Botmaker/Scarecrow,
> abuse-enforcement-service, and Gizmoduck — don't sit in this per-request pipeline at
> all. They run continuously, in the background, producing labels and account state that
> visibility filtering and other systems consume when a request does come in.

**Problem:** This is true for Agatha, BDSM, UserCredV2, Grox, and Botmaker/Scarecrow
(genuinely background/event-driven batch or Kafka-consumer systems), and explicitly
confirmed true for abuse-enforcement-service ("Its production trigger is a Kafka
consumer... it reacts to entities some upstream detector already flagged," Rapid 03). It
is **not** true for Gizmoduck, which the synthesis's own Section 2 diagram implicitly
requires to run synchronously, per request: "Home Mixer builds a 'query': who is this
viewer, who do they follow, what have they recently done..." is exactly the step S01
identifies as making a live, per-request Gizmoduck call ("`QueryBuilder::build`... fetches
viewer account state (Gizmoduck, 200ms timeout, fails open)"). Separately, VF's own
server-side evaluation reads "author account-safety flags... user-labels... all sourced
from Gizmoduck's `QueryFields::SAFETY`/`QueryFields::LABELS`" with its own 150ms timeout,
per request, per candidate batch (Rapid 03). Gizmoduck is a live, synchronous, in-the-critical-path
dependency for every single request — the opposite of "doesn't sit in this per-request
pipeline at all."
**Ground truth:** S01 §"Service/request entry points" (`QueryBuilder::build`, Gizmoduck
200ms timeout); Rapid 03 §"Visibility filtering" ("What VF receives" — Gizmoduck
`QueryFields::SAFETY`/`LABELS`, 150ms timeout).
**Recommended correction:** Move Gizmoduck out of the "background systems" bullet in §1.
It should instead be described as a live, synchronously-queried account-state store that
both Home Mixer's query construction and VF's per-candidate evaluation read from on every
request — distinct from the genuinely background label-*producing* systems in that same
list.
**Evidence source:** S01 executive architecture / query-builder section; Rapid 03 "What VF
receives" paragraph.

---

### AR-003 — HIGH
**Document:** GLOSSARY.md ("VMRanker" and "DPP" entries)
**Quoted wording:**
> VMRanker — ... Under its default configuration, it implements a DPP-based diversity
> selection over the already-scored list rather than producing an independent predictive
> score.

> DPP — ... the specific algorithm VMRanker uses, under its default mode, to select a
> subset of candidates...

**Problem:** This is exactly the ambiguity the task flagged as high-risk: "under its
default configuration" doesn't say whose default. There are two different, independently
significant defaults here — Home Mixer's checked-in request default (`value_model_id =
"dpp"`, sent on every call) and the VMRanker **server's** own checked-in CLI default
(`--dpp-enabled = false`). If the server-side flag is off, "under its default
configuration" (read naturally, as a statement about the VMRanker service) is **false**:
the server does not construct a `DppContext` and simply echoes the incoming score back
unchanged — a no-op, not diversity selection. The main text's own Section 8 gets this
exactly right, with an entire paragraph built around separating the two defaults ("Home
Mixer, by checked-in default, *requests* DPP-based selection on every call. But the
VMRanker server's own flag... defaults to `false`..."). The glossary entries for the same
two terms don't carry that distinction over, creating a real risk that a reader who
consults only the glossary (its stated purpose: "a quick-reference companion") comes away
believing DPP selection is what the server does "by default," full stop.
**Ground truth:** Rapid 02 §"VMRanker and diversity" ("if the server has DPP enabled...";
"`--dpp-enabled` flag whose checked-in default is `false`"); Rapid 04 confirms the same
split explicitly in its "Checked-in defaults vs live production" table.
**Recommended correction:** Both glossary entries should say, in one added clause each,
which default they mean: "Under Home Mixer's checked-in *request* default it asks for DPP
selection; whether the VMRanker server's own checked-in default (`--dpp-enabled=false`)
actually performs it is a separate, unresolved question — see §8."
**Evidence source:** Rapid 02 VMRanker section; Rapid 04 "Checked-in defaults vs live
production" table.

---

### AR-004 — MEDIUM
**Document:** HOW_FOR_YOU_WORKS.md §10
**Quoted wording:**
> **Gizmoduck** is the account-record service/store — it's where account-level safety
> flags, user labels, and fields like your follow relationships and suspension state
> live.

**Problem:** Per Rapid 03's direct enumeration of what VF receives, viewer↔author
relationship data (blocks, mutes, mutes-retweets-from, **follows**, super-follows) is
"sourced from a socialgraph client," explicitly distinct from Gizmoduck (which supplies
`QueryFields::SAFETY`/`LABELS` — suspension/deactivation/NSFW flags and written labels).
Nothing in S00/S01/Rapid 01–05 attributes follow-relationship data to Gizmoduck itself.
The glossary's own Gizmoduck entry ("Holds account safety flags... user labels... and
various account metadata and preference fields") is notably more conservative and does
**not** make this follow-relationship claim — so this is also a main-text/glossary
inconsistency, with the glossary being the more accurate of the two.
**Ground truth:** Rapid 03 §"Visibility filtering," "What VF receives" paragraph
(socialgraph client vs. Gizmoduck `QueryFields`, explicitly separated).
**Recommended correction:** Drop "fields like your follow relationships" from the main-text
Gizmoduck description, or attribute it to the separate social-graph service the
ground-truth reports name.
**Evidence source:** Rapid 03 "What VF receives."

---

### AR-005 — MEDIUM
**Document:** GLOSSARY.md ("Grox" entry)
**Quoted wording:**
> A separate Grox rule also writes a tweet label consumed only by Scarecrow, independent
> of the retrieval-admission path.

**Problem:** This reverses the actual producer→consumer direction. Per Rapid 03, the
relevant mechanism is `GroxTweetProcessor.bot` — a **Scarecrow** bot rule — that
*consumes* Grox's `spamScore` output and, at `spamScore >= 0.97`, *writes* the tweet label
`RISKY_HIGH_VIZ_REPLY`. There is no "Grox rule" that "writes a tweet label consumed... by
Scarecrow" — Scarecrow is the writer here, not the consumer, and Grox is the upstream
signal source, not the label writer. Furthermore, per Rapid 03's own label-chain table,
`RISKY_HIGH_VIZ_REPLY` has **no confirmed consumer at all** in this snapshot ("not found
in VF's rule set... No confirmed For You consequence") — so "consumed only by Scarecrow"
also overstates what's established; Scarecrow wrote it, nothing is shown reading it.
**Ground truth:** Rapid 03 §"Content understanding" (Grox) and the "Inventory of the 20
checked-in Scarecrow rules" table, rule #1 (`GroxTweetProcessor`, event
`health_side_effect`/`groxScore`, output tweet `RISKY_HIGH_VIZ_REPLY`).
**Recommended correction:** "A Scarecrow rule (`GroxTweetProcessor`) separately consumes
Grox's spam score and writes a tweet label (`RISKY_HIGH_VIZ_REPLY`) with no confirmed
downstream consumer in this snapshot — independent of the retrieval-admission path
described above."
**Evidence source:** Rapid 03 Grox section and Scarecrow rule inventory table.

---

### AR-006 — MEDIUM
**Document:** HOW_FOR_YOU_WORKS.md §3
**Quoted wording:**
> `PhoenixCandidatePipeline` — the pipeline behind a normal For You request — runs seven
> sources concurrently every time it executes. Two default to disabled and won't
> necessarily contribute anything unless a feature switch turns them on; the rest run by
> default.

**Problem:** The first sentence, read on its own, states all seven sources "run... every
time it executes," which is not accurate to the framework's actual behavior: "Every stage
first filters components by `.enable(&query)`; a disabled component simply does not run —
no error, no placeholder" (S01). The very next sentences partially walk this back (two
disabled by default), but even among the five default-enabled sources, further per-request
gating removes more: `SimclustersSource` requires the viewer to have ≥1 engagement signal
(zero otherwise), and cache mode (`has_cached_posts`) disables all six live-retrieval
sources at once, leaving only `CachedPostsSource` active. The document does describe these
individual gates later in the same section and in §13, so the error is localized to this
one opening sentence's phrasing, not a document-wide pattern — but the literal claim
"[seven sources] run... every time it executes" is false as written.
**Ground truth:** S01 §"Candidate-pipeline execution semantics" (per-component `.enable()`
gating, disabled = no run); Rapid 01 "Cache mode... disables 100% of live retrieval, not a
subset" and SimClusters' `has_post_signals` gate.
**Recommended correction:** "...evaluates seven sources every time it executes, running
whichever pass their own enable-gate, concurrently among themselves."
**Evidence source:** S01 execution-semantics section; Rapid 01 IN/OON and cache-mode
tables.

---

### AR-007 — MEDIUM
**Document:** HOW_FOR_YOU_WORKS.md §3, §10
**Quoted wording (§3):**
> Posts that fail an internal safety check are also excluded from the mainstream indices
> at this stage (more on that in the safety section below).

**Problem:** Section 10 (the safety section this line points to) covers Grox's boolean
NSFW/gore/spam flags feeding index admission via `UnifiedPostAnnotations`, but never
surfaces the *second*, structurally distinct index-admission safety check Rapid 03 traces
in detail: `phoenix-rankall`'s `shouldDropPostByVF` call, which runs a **full
visibility-filtering evaluation** at the stricter `TimelineHomeRecommendations` policy,
with **no viewer context at all** (universal, once-per-post), and which Rapid 03 flags as
a HIGH-significance finding specifically because of its distinctive fail-open behavior
(decider-fetch exception → fail open; Rust-VF verdict exception → fail open; legacy-branch
exception behavior UNKNOWN) and its consequence (a post can be permanently excluded from
all three Phoenix retrieval sources for every viewer, while remaining fully reachable via
Thunder or SimClusters, which never call VF at retrieval time). The promised follow-through
in the safety section doesn't cover this mechanism at all — only the separate Grox→UPA
path.
**Ground truth:** Rapid 03 §"Before retrieval / index admission" and Material Finding #8.
**Recommended correction:** Either fold a short paragraph on this index-time VF check into
§10 (or a new short subsection), or soften §3's "more on that in the safety section below"
so it doesn't promise coverage the document doesn't deliver.
**Evidence source:** Rapid 03 index-admission VF section and finding #8.

---

### AR-008 — MEDIUM
**Document:** HOW_FOR_YOU_WORKS.md §3
**Quoted wording:**
> **replies, retweets, and posts from community groups are excluded from the mainstream
> indices outright**, regardless of how much engagement they get

**Problem:** This is correctly scoped to "mainstream indices" (not an unscoped "replies
are excluded from Phoenix" claim, so it does not repeat the earlier overstatement Rapid 01
explicitly corrected). But the document never surfaces the correction itself: Rapid 01's
single most consequential finding in this area is that a narrower, earlier branch
(`search_unfiltered`, favorite-events only, evaluated *before* the reply check runs)
excludes community posts and retweets but **not** replies, and that this branch's
downstream reachability from any live Phoenix retrieval path is UNKNOWN — meaning the
document cannot actually claim replies are categorically absent from Phoenix retrieval
end-to-end, only from the mainstream index-build branches. The synthesis's careful
scoping avoids being technically false, but it omits a caveat its own source material
treats as important enough to be a HIGH-significance, headline finding.
**Ground truth:** Rapid 01 Material Finding #1 and its "Two upstream triggers" /
"Admission has two branches" sections.
**Recommended correction:** Add one sentence noting the narrower `search_unfiltered`
exception and that whether it feeds any live retrieval path is unknown from this
snapshot.
**Evidence source:** Rapid 01 finding #1.

---

### AR-009 — LOW
**Document:** HOW_FOR_YOU_WORKS.md §2 (diagram)
**Quoted wording:**
> pre-scoring filters: remove posts that should never reach a scorer at all... |
> (sequential, sixteen-plus filters in a fixed declared order)

**Problem:** The exact, directly-established count is 18 pre-scoring filters (confirmed
independently in both S00's README cross-check — 17 named + `Brazil2026ElectionFilter` —
and S02's full sequential listing of all 18 by name). "Sixteen-plus" is unnecessarily
vague given the precise number is DIRECT evidence in two separate forensic passes, and it
understates the true value.
**Ground truth:** S00 "Filtering/visibility claims and verification"; S02 "Pre-selection
filters" (full 18-filter ordered list).
**Recommended correction:** "eighteen filters."
**Evidence source:** S02 pre-selection filters section.

## Cross-document inconsistencies

- **AR-001**: GLOSSARY.md's "Home Mixer" entry vs. its own "RankingScorer" entry — direct,
  unresolved self-contradiction about whether RankingScorer runs locally or is "called
  out to."
- **AR-003**: GLOSSARY.md's "VMRanker"/"DPP" entries are weaker/more ambiguous than
  HOW_FOR_YOU_WORKS.md §8's careful two-defaults treatment of the identical fact.
- **AR-004**: HOW_FOR_YOU_WORKS.md §10 claims Gizmoduck holds follow relationships;
  GLOSSARY.md's own Gizmoduck entry does not make this claim and is the more accurate of
  the two.
- No other main-text/glossary term definitions were found to conflict. Retrieval-source
  gating, IN/OON discount exceptions, VF's three-outcome model, and the label
  producer→consumer chain are all stated consistently across both documents everywhere
  they're repeated.

## Numeric/default audit

All fourteen ranking weights in §6's table (favorite 0.5, reply 5.0/+15.0, retweet 1.0,
click 0.4, open-link 0.2, share 2.0/DM 5.0/copy-link 20.0, quote 5.0, follow 4.0,
not-interested -43.2, block -31.2, mute -58.8, report -234.0) were checked individually
against `ranking_scorer.rs`'s values as reported in Rapid 02's authoritative table — all
match exactly, including the "largest positive"/"largest-magnitude negative" superlative
claims. The dwell-time weight (0.004) and not-dwelled weight (-0.02) also match. The
worked arithmetic example (0.5×0.08=0.04, 5.0×0.01=0.05, 1.0×0.02=0.02, sum≈0.11,
-234.0×0.0005≈-0.117, 160× ratio) is internally consistent and correctly computed.
Cold-start slot values (15/16, "position 16, zero-indexed as rank 15") are correct and
precisely worded to avoid implying a guaranteed final position. Cache thresholds (≥500
candidates, ~180-second TTL) and the 48-hour age filter are correct. The ~15-attribute
feature-switch matching-key enumeration in §15 was checked term-by-term against Rapid 05's
exhaustive `RecipientBuilder` list and matches, including the explicit absence claims (no
device type, no city, no random seed).

Two issues found: **AR-003** (VMRanker/DPP "default" ambiguity, glossary only) and
**AR-009** (filter count stated as "sixteen-plus" vs. the directly-established 18).

## Safety-label audit

The label→consequence table in §11 (`SPAM`, `SPAM_HIGH_RECALL`, `NSFW_HIGH_PRECISION`/
`NSFW_HIGH_RECALL`, `NSFW_CARD_IMAGE`, `GORE_AND_VIOLENCE_HIGH_PRECISION`, `MALICIOUS_URL`)
was checked row-by-row against Rapid 03's exact producer→VF-consumer table and matches
exactly, including which labels apply both-ways vs. OON-only vs.
interstitial-in-network/drop-OON. The document correctly declines to assert a For-You
consequence for `AGATHA_SPAM`, `AGATHA_SPAM_TOP_USER`, `RISKY_HIGH_VIZ_REPLY`, and
`COPYPASTA_SPAM`, matching Rapid 03's explicit "not found in VF's rule set" findings for
all four. Grox's "LLM-based" characterization is directly supported by source (Gemma-family
model named in `grox/flows/upa/constants.py`). No fabricated or semantically-inferred
producer/consumer chain was found in the main text.

One error found: **AR-005** — the glossary's Grox entry garbles the direction of the
`GroxTweetProcessor`→`RISKY_HIGH_VIZ_REPLY` chain, describing it backwards ("a Grox rule
writes a label consumed... by Scarecrow" when it is a Scarecrow rule that consumes Grox's
score and writes the label, to no confirmed consumer).

## Evidence-boundary audit

The Phoenix model-input discussion (§4, §5) correctly separates DIRECT evidence (text/media
absent from the specific `PredictNextActionsRequest` wire format) from inference (semantic-ID
resolution as the likely explanation), and explicitly flags the model-config-family claim
as "not an independently verified claim about live traffic" per Rapid 05's exact synthesis
instruction. The document does not reintroduce `xrecsys_gen_recs` as the production ranking
model, and correctly states the `home_direct_packed*`/`xrecsys_two_tower*` shipped-reference
pairing as a repository-tooling fact, not a production fact — this was one of the harder
corrections to get right (Rapid 04 had a STRONG_INFERENCE toward `xrecsys_gen_recs`, later
narrowed by Rapid 05) and the synthesis reflects the corrected version cleanly. The document
does not make any claim that a request field being present proves the model consumes it
(it simply doesn't raise the `author_follows_viewer`-reaches-the-model question at all in
the main text, which is a safe simplification, not an overreach).

## Readability issues

- **§1's list of unexplained proper nouns** (Agatha, BDSM, UserCredV2, Grox,
  Botmaker/Scarecrow, abuse-enforcement-service, Gizmoduck) appears before any of them is
  defined, asking the reader to hold seven unfamiliar names in working memory. A one-clause
  forward-pointer ("explained one by one in §10") would help; it's implicit from the
  document structure but never stated.
- **"Checked-in default" appears at very high density** in §7, §8, and §15 — clearly a
  deliberate and well-justified discipline given the subject matter, but in a few
  paragraphs (e.g. §7's cold-start paragraph) it qualifies nearly every clause, which can
  make the paragraph harder to parse than the underlying fact requires. Consider
  bracketing dense passages with one strong reminder at the start rather than qualifying
  each sentence.
- **§12's BlenderSelector prose lists insertion types in an order** ("prompts... a Who to
  Follow module... a push-to-home post... gets pinned ahead of everything else") that
  could be misread as final positional order rather than code-execution order (push-to-home
  is actually inserted *after* prompts/WTF in the code, at index 0, displacing them one
  slot down). "Ahead of everything else" resolves the ambiguity if read carefully, but a
  reader skimming the list could come away with the wrong final ordering. A parenthetical
  ("even though it's placed after them in the code") would remove the ambiguity entirely.
- **Section 10's producer→consumer diagram is a clean, accurate ASCII summary** but omits
  the separate index-time VF-admission path (AR-007) as its own branch — worth a small
  addendum given how distinctive that path's scope and failure semantics are.

## Things that were surprisingly correct

These were explicitly attacked per the task's high-risk list and verified to hold up —
recording them so they aren't relitigated:

- **Label producer→consumer table (§11)**: every row checked individually against Rapid
  03's exact-string-verified table; all six rows match exactly, including the
  in-network/OON split and the interstitial-vs-drop duality for `NSFW_CARD_IMAGE`/
  `GORE_AND_VIOLENCE_HIGH_PRECISION`.
- **VMRanker/DPP main-text treatment (§8)**: correctly separates Home Mixer's checked-in
  request default from VMRanker's own server-side `--dpp-enabled` default, and correctly
  states the DPP algorithm itself is fully published Rust, not external — this is a subtle
  distinction the document gets right in the body even though the glossary (AR-003) does
  not carry it over.
- **Model-config-family claim (§5)**: precisely reflects Rapid 05's correction
  (`home_direct_packed*`/`xrecsys_two_tower*` as the shipped reference pairing,
  `xrecsys_gen_recs` explicitly not reintroduced as the production ranking model), with
  the exact "not independently verified... live traffic" hedge Rapid 05's own synthesis
  instructions asked for.
- **Cold-start floor framing (§7)**: "floors one candidate's score to at least what a
  mid-pack post is currently scoring — it does not assign or guarantee that candidate a
  final position" is precisely worded and avoids every version of the "guaranteed slot 16"
  misreading the task anticipated.
- **VF Allow/Interstitial/Drop semantics and evaluation order (§9)**: rule-evaluation
  order, first-Interstitial-sticks/first-Drop-short-circuits semantics, and the
  ancestor/quote/retweet ancillary-drop behavior all match Rapid 03's tested behavior
  exactly.
- **Three-way VF failure taxonomy (§14)**: RPC-chunk failure (fail open), missing-ID-in-
  response (fail closed), unresolved-author (fail closed) are kept as three distinct rows
  rather than collapsed into a blanket "VF fails open" statement — exactly what the task
  warned against doing.
- **In-network reply/retweet OON-discount exception**: correctly flagged as a genuinely
  non-obvious current-default behavior in at least three places (§7, §16 walkthrough A,
  glossary IN/OON entries), matching Rapid 02's HIGH-significance finding #2 precisely.
- **Caching section (§13)**: "stale predictions, freshly re-weighted... not a frozen
  replay" is the exact correct conclusion from Rapid 02's cached-request-ranking section,
  including the mechanism (RankingScorer/VMRanker re-run with live weights against reused
  Phoenix predictions).
- **Feature-switch matching-key enumeration (§15)**: term-by-term match to Rapid 05's
  exhaustive `RecipientBuilder` list (~15 attributes), including the correct negative
  claims (no device type, no city/DMA, no raw random seed) and the cluster-selector
  two-layer-override callout.

## Required corrections before final

**MUST FIX:**
- AR-001 (glossary self-contradiction on Home Mixer vs. RankingScorer locality)
- AR-002 (Gizmoduck miscategorized as background-only in §1)
- AR-003 (glossary VMRanker/DPP "default" ambiguity)

**SHOULD FIX:**
- AR-004 (Gizmoduck/follow-relationships claim)
- AR-005 (Grox/RISKY_HIGH_VIZ_REPLY producer-consumer direction, glossary)
- AR-006 ("seven sources run... every time" phrasing)
- AR-007 (index-time VF-admission check missing from safety section despite the pointer)
- AR-008 (search_unfiltered/reply-admission caveat omitted)

**OPTIONAL:**
- AR-009 (filter count: "sixteen-plus" → "eighteen")
- Readability items (§1 forward-pointer, density of "checked-in default," §12 ordering
  clarity, §10 diagram addendum)
