# Editorial Rules

This defines the evidence policy every future explainer must follow. It's the single
most important file in this project — diagrams and guides get redesigned, but the rules
about what we're allowed to claim shouldn't drift artifact by artifact.

## Evidence classes

Every factual claim in this project belongs to exactly one of these classes. Public-
facing copy doesn't need to print the class label on every sentence, but the writer must
know, for each claim they write, which class it belongs to — because the class
determines which words are allowed around it.

**DIRECT PUBLIC MECHANISM**
Something the source code plainly does, stated without inference. Example: "the request
Home Mixer sends to Phoenix for scoring carries identifiers and counts, not raw post
text." This is the strongest class — write it plainly, no extra hedging needed.

**CHECKED-IN DEFAULT**
A specific numeric or configuration value read directly from source, that could be
overridden per-request by a feature switch or decider the repository shows the mechanism
for but not the live value of. Example: the out-of-network discount is 0.75× "by
checked-in default." Always carry the phrase "checked-in default" (or equivalent) when
stating a specific number.

**SHIPPED REFERENCE IMPLEMENTATION**
A model, config, or code path that exists, is runnable, and is what the repository's own
tooling (quickstart scripts, benchmarks, launchers) actually uses or documents — but
isn't independently confirmed to be what production runs. Example: the
`home_direct_packed*`/`xrecsys_two_tower*` config pairing. State it as "the repository's
own shipped reference tooling pairs X with Y," not "X is the production model."

**STRONG INFERENCE**
A conclusion the source code makes plausible but doesn't itself prove. Example: that a
semantic ID resolves to richer content representation server-side, to explain why raw
text isn't in the scoring request. Always attach the reasoning, not just the conclusion —
"the most likely explanation, based on how the model is built, is X — but this repository
doesn't contain the code that would prove it."

**UNKNOWN / NOT PUBLISHED**
The repository is genuinely silent. Example: the live per-request Phoenix scoring
capacity; the trained model checkpoint; which decider value maps to which physical
cluster. State plainly that this isn't knowable from this snapshot — don't guess, and
don't imply the checked-in default is a stand-in for the real value.

**LIVE PRODUCTION CLAIM**
A statement about what X's systems are actually doing right now, for real users, today.
**This project makes none of these, ever.** Every sentence that could be read as one
needs to be rewritten until it can't be. This is the class that separates this project
from speculation about X's current behavior.

## Core rules

These follow directly from the evidence classes above and from the master synthesis's own
closing distinctions (§17):

- A checked-in default is not a live production value.
- A shipped reference model is not a confirmed production model.
- A field appearing in a request is not proof the model that receives it actually
  consumes it.
- Source code existing is not proof it's enabled in production.
- A service supporting a feature (e.g., VMRanker supporting DPP) is not proof that
  feature is active — check whether it's the *client's* request default or the *server's*
  own operating default; these can and do differ (see VMRanker/DPP in
  `EDITORIAL_RULES.md`'s companion table below and `CLAIM_BANK.md`).
- A label existing and being actively written is not proof it has any feed consequence —
  several confirmed, actively-written labels (`AGATHA_SPAM`, `RISKY_HIGH_VIZ_REPLY`,
  `COPYPASTA_SPAM`) have no confirmed consumer in visibility filtering.
- Two similar-sounding label or system names are not necessarily the same thing (BDSM ≠
  adult content; Botmaker ≠ Scarecrow; `AGATHA_SPAM` ≠ the generic `SPAM` VF label).
- Retrieval inclusion is not ranking success — being found by a source is a prerequisite,
  not an outcome.
- Ranking success is not visibility — a post can score highest in the batch and still be
  Dropped by visibility filtering.
- A visibility-filtering "Allow" verdict is not a guarantee of final display — later
  pipeline stages (truncation, blending) still apply.
- The out-of-network discount is a score reduction, not a removal.
- A Phoenix prediction is not a final ranking score — RankingScorer's weighted sum is a
  separate, later number.
- A retrieval similarity score is not a Phoenix ranking-side action prediction — they
  come from different services with different jobs.
- Interstitial is not Drop — an interstitialed post still reaches the client.
- `phoenix-rankall`'s corpus-admission decision is not the same event as a specific
  request's retrieval-time search — one happens once per post, for everyone, before any
  request exists; the other happens per request.
- Public algorithm code is not live configuration — the repository shows mechanism, not
  today's settings.

## Vocabulary rules

**Use:**
- "the checked-in default is..."
- "the public repository shows..."
- "the shipped reference implementation..."
- "the source allows..."
- "the analyzed snapshot..."
- "the live production value is not published..."
- "the repository's own tooling documents..."

**Avoid**, unless the behavior is genuinely direct and correctly scoped:
- "X definitely does..."
- "the algorithm rewards..."
- "X gives you X points when..."
- "the algorithm decides..." (attribute the decision to the specific component that
  actually makes it — RankingScorer, visibility filtering, `phoenix-rankall` — not to a
  monolithic "algorithm")

## Practical-advice policy

This is the strictest rule in the project, because it's the one most likely to get
violated by accident in service of making content "useful."

**Allowed**, when correctly scoped and hedged:
- "The public code suggests..."
- "The checked-in scoring setup gives relatively more weight to predicted replies than
  predicted favorites..."
- "Repeated posts from one author face a diversity discount that grows with each
  additional post already ranked above it, though it never reaches zero..."
- "Being retrieved at all is a prerequisite to being ranked — a post no source finds
  can't be shown, regardless of how good it might have scored."

**Explicitly banned**, in any form, on any artifact in this project:
- "Get 10 replies to boost reach by 10x."
- "One report cancels 468 likes."
- "Copy-link shares are worth exactly 40 likes."
- "Do X and the algorithm will reward you."
- Any formulation that turns a RankingScorer weight ratio into a literal exchange rate
  between raw engagement events.
- Any formulation that promises a specific outcome ("guaranteed reach," "guaranteed
  visibility") from a specific action.

**Why this matters, precisely:** RankingScorer's weights multiply *model-predicted
probabilities or values*, not raw event counts (§6 of the master synthesis). A weight of
-234 on "report" exists specifically because Phoenix's *predicted probability* of a
report is astronomically small relative to a favorite — so the weight has to be large for
a tiny predicted risk to matter at all when the score is summed. The ratio between two
weights (e.g., -234 vs. 0.5) is not an exchange rate between two kinds of events, and the
source code says so directly, in a comment, for exactly this reason. Turning it into "1
report = 468 likes" both misreads the arithmetic and implies a false level of precision
and determinism that the underlying model — probabilistic, per-viewer, per-request, and
running against live configuration nobody outside X can see — does not support. Live
configuration can also change any of these numbers at any time, which this project cannot
observe.

Every future artifact touching RankingScorer's weight table must link back to this
section rather than re-deriving its own framing.

## How to use evidence classes without labeling everything

Public-facing prose should read naturally — a QUICK piece especially shouldn't look like
a legal document. The internal discipline is: before publishing a sentence, ask "which
evidence class is this?" and make sure the sentence's *wording* matches that class (see
Vocabulary rules above), even if the class name itself never appears. GUIDE and MASTER-
adjacent pieces can be more explicit about hedging; QUICK pieces should still be
technically true, just less densely qualified — trim adjacent context, never trim
accuracy.
