# Roadmap

The artifact plan for the explainers project. Every artifact below traces to at least one
row in `CONTENT_MAP.md` and must respect `EDITORIAL_RULES.md`. This is not a locked
specification — if a better information architecture emerges during Phase 2+, restructure
it, but don't drop the underlying commitments (provenance, evidence discipline, no
growth-hacking framing).

**Status key:** PLANNED (not started) · WIREFRAME (structural draft exists, not prose-
final) · DRAFT (written, not reviewed) · REVIEWED (checked against
`EDITORIAL_RULES.md`/`CLAIM_BANK.md`) · FINAL (ready for polish/publication).

**Priority key:** P0 (do first — highest leverage for correcting the biggest
misconceptions) · P1 (do next) · P2 (valuable, not urgent) · BACKLOG (real, but needs
Phase 2+ groundwork first).

---

## DIAGRAMS

### D1. Full For You pipeline
- **Purpose:** whole-system orientation map; entry point for everything else.
- **Audience:** everyone.
- **Format:** diagram + short walkthrough.
- **Main question:** what happens, in order, between opening the app and seeing a feed?
- **Master sections:** §§1–2, §12, §13, §14.
- **Primary danger:** implying local Home Mixer logic (RankingScorer, filters,
  BlenderSelector) is a remote call, or vice versa.
- **Prerequisites:** none.
- **Priority:** P0 · **Status:** WIREFRAME (`diagrams/01-for-you-pipeline.md`)

### D2. Retrieval sources
- **Purpose:** explain what determines the ceiling of what can appear in a feed.
- **Audience:** readers curious where posts actually come from.
- **Format:** diagram + walkthrough.
- **Main question:** how does a post become eligible for my feed at all?
- **Master sections:** §3.
- **Primary danger:** collapsing `phoenix-rankall` admission and two-tower search into
  one step; overstating `search_unfiltered`'s reach.
- **Prerequisites:** D1.
- **Priority:** P0 · **Status:** WIREFRAME (`diagrams/02-retrieval-sources.md`)

### D3. Ranking stack
- **Purpose:** explain how a score is actually computed.
- **Audience:** readers who want real technical understanding of ranking.
- **Format:** diagram + walkthrough + warning callout.
- **Main question:** how does a candidate's score get calculated?
- **Master sections:** §§4–8.
- **Primary danger:** reading weight ratios as engagement-event exchange rates (the
  single most important danger in the whole project).
- **Prerequisites:** D1.
- **Priority:** P0 · **Status:** WIREFRAME (`diagrams/03-ranking-stack.md`)

### D4. Ranking vs. Visibility Filtering
- **Purpose:** correct the most consequential misconception — high score ≠ shown.
- **Audience:** everyone; the most shareable diagram in the suite.
- **Format:** diagram + one-line headline framing.
- **Main question:** does a high score guarantee a post gets shown?
- **Master sections:** §9, §11, §16 (walkthrough C).
- **Primary danger:** conflating Interstitial with Drop; conflating index-time exclusion
  with per-request VF.
- **Prerequisites:** D3.
- **Priority:** P0 · **Status:** REVIEWED (`assets/src/d4-ranking-vs-visibility*.svg` —
  desktop light/dark, mobile, and social renders all exist and have been visually
  QA'd — 10-second test, grayscale test, small-size test — against
  `diagram-design/D4_PRODUCTION_SPEC.md`, `CLAIM_BANK.md`, and `EDITORIAL_RULES.md`; see
  `assets/README.md`. Not yet FINAL — awaits a human visual sign-off pass beyond this
  phase's self-QA before publication polish.)

### D5. Safety/reputation signal flow
- **Purpose:** make the codename ecosystem navigable without conflating similar names.
- **Audience:** readers trying to parse Agatha/BDSM/Grox/Botmaker/Scarecrow/Gizmoduck.
- **Format:** diagram + codename decoder.
- **Main question:** where do the labels visibility filtering checks come from?
- **Master sections:** §§10–11.
- **Primary danger:** implying every detector feeds every rule system; implying a label
  existing proves it has a feed consequence.
- **Prerequisites:** D4.
- **Priority:** P1 · **Status:** WIREFRAME (`diagrams/05-safety-label-flow.md`)

### D6. Phoenix two-tower retrieval
- **Purpose:** model-side zoom-in on how retrieval search actually works.
- **Audience:** technically curious readers wanting model-architecture depth.
- **Format:** diagram + walkthrough.
- **Main question:** how does Phoenix's retrieval search decide what's close to a viewer?
- **Master sections:** §3 (retrieval-serving paragraphs); residual report "Synthesis
  impact" item 2.
- **Primary danger:** presenting the shipped reference model as confirmed production;
  calling the search "ANN" when it's documented as exact top-k.
- **Prerequisites:** D2.
- **Priority:** P1 · **Status:** WIREFRAME (`diagrams/06-phoenix-two-tower-retrieval.md`)

---

## GUIDES

### G1. How X's For You feed works — 5 minutes
- **Purpose:** correct mental model, fast, for a reader with no technical background.
- **Audience:** general public.
- **Format:** ~600–900 word article, QUICK layer.
- **Main question:** what actually happens to make my feed?
- **Master sections:** §§1–2, §16.
- **Primary danger:** simplifying so far that a QUICK claim becomes technically wrong —
  QUICK trades depth for speed, never accuracy for speed.
- **Prerequisites:** D1, D4.
- **Priority:** P0 · **Status:** PLANNED

### G2. How X's For You feed works — 20 minutes
- **Purpose:** meaningful technical understanding across the whole pipeline.
- **Audience:** technically curious readers, GUIDE layer.
- **Format:** ~3,000–4,000 word article, structured by pipeline stage.
- **Main question:** how does each stage of the pipeline actually work?
- **Master sections:** §§1–15 (full walk, compressed).
- **Primary danger:** drifting into practical-advice territory while explaining
  RankingScorer's weights — see `EDITORIAL_RULES.md`.
- **Prerequisites:** G1, all six diagrams.
- **Priority:** P1 · **Status:** PLANNED

### G3. Where recommended posts actually come from
- **Purpose:** deep-dive on retrieval specifically.
- **Audience:** readers who want to understand OON discovery.
- **Format:** ~1,200–1,800 word guide.
- **Main question:** how does X find posts from accounts I don't follow?
- **Master sections:** §3.
- **Primary danger:** overstating what `search_unfiltered` covers; implying SimClusters
  and Phoenix retrieval are related.
- **Prerequisites:** D2, D6.
- **Priority:** P1 · **Status:** PLANNED

### G4. How ranking actually works
- **Purpose:** deep-dive on Phoenix + RankingScorer + VMRanker.
- **Audience:** readers who want the real mechanics, without growth-hacking framing.
- **Format:** ~1,500–2,000 word guide.
- **Main question:** how does a post's score actually get computed?
- **Master sections:** §§4–8.
- **Primary danger:** the weight-table-as-exchange-rate misreading; this guide is the
  highest-risk artifact in the project for that specific failure mode.
- **Prerequisites:** D3.
- **Priority:** P1 · **Status:** PLANNED

### G5. How Visibility Filtering works
- **Purpose:** deep-dive on VF's rule structure and evaluation semantics.
- **Audience:** readers who want to understand moderation/eligibility mechanics.
- **Format:** ~1,200–1,600 word guide.
- **Main question:** what determines whether an already-ranked post is allowed to show?
- **Master sections:** §9, §11.
- **Primary danger:** conflating Interstitial and Drop; treating the published rule
  subset as complete.
- **Prerequisites:** D4.
- **Priority:** P1 · **Status:** PLANNED

### G6. How safety labels reach the feed
- **Purpose:** deep-dive on the detector→enforcement→label→consumer chain.
- **Audience:** readers who want to understand the safety/reputation ecosystem.
- **Format:** ~1,500–2,000 word guide.
- **Main question:** who decides a post is unsafe, and how does that reach my feed?
- **Master sections:** §§10–11.
- **Primary danger:** implying a label existing proves feed consequence; the
  BDSM-is-adult-content and Botmaker-is-Scarecrow name confusions.
- **Prerequisites:** D5.
- **Priority:** P2 · **Status:** PLANNED

### G7. What the public repository does NOT tell us
- **Purpose:** make the public-vs-production boundary its own first-class artifact.
- **Audience:** everyone, especially readers tempted to treat this project's other
  content as proof of live behavior.
- **Format:** ~1,000–1,500 word guide, structured as two lists (established / unknown).
- **Main question:** what can't be known from this snapshot, no matter how carefully it's
  read?
- **Master sections:** §5, §8, §14–15, §17 (§17 is this guide's spine).
- **Primary danger:** none specific to this guide — it exists to prevent the danger in
  every other artifact. Get this one right and it protects the rest.
- **Prerequisites:** none — can be written early, independent of other guides.
- **Priority:** P1 · **Status:** PLANNED

---

## PRACTICAL / "WHAT THIS MEANS"

### PR1. What the open-source code actually suggests affects recommendation
- **Purpose:** a single, tightly bounded summary of legitimate, source-grounded
  practical takeaways — explicitly framed against growth-hacking content.
- **Audience:** posters wanting grounded understanding, not hacks.
- **Format:** ~800–1,200 words, structured as a short list, each item with its caveat
  attached inline.
- **Main question:** what does the code actually suggest, carefully bounded?
- **Master sections:** §3 (retrieval prerequisite), §6–7 (weights and adjustments), §9
  (visibility as a separate gate).
- **Primary danger:** this is the single highest-risk artifact for violating the
  practical-advice policy — every sentence must be checked against
  `EDITORIAL_RULES.md`'s banned-formulation list before publishing.
- **Prerequisites:** G4, G5, `CLAIM_BANK.md`.
- **Priority:** P1 · **Status:** PLANNED

### PR2. Posting takeaways, carefully bounded
- **Purpose:** narrower companion to PR1, focused specifically on posting behavior
  (frequency, reply engagement, diversity discount).
- **Audience:** posters.
- **Format:** ~600–900 words.
- **Main question:** does how I post affect my reach, and how, specifically?
- **Master sections:** §6–7.
- **Primary danger:** same class of risk as PR1 — must not become a growth-hacking
  equation.
- **Prerequisites:** PR1.
- **Priority:** P2 · **Status:** PLANNED

### PR3. Why did I see this post?
- **Purpose:** walk a reader through the actual reasoning path for a typical
  recommendation.
- **Audience:** general public.
- **Format:** ~800–1,000 words, using the master's own three walkthroughs as its spine.
- **Main question:** why does a specific kind of post show up in my feed?
- **Master sections:** §16 (primary source), drawing on §§3–11.
- **Primary danger:** implying these three walkthroughs are exhaustive of all the reasons
  a post could appear.
- **Prerequisites:** D1–D4.
- **Priority:** P1 · **Status:** PLANNED

### PR4. Why didn't a highly-ranked post necessarily appear?
- **Purpose:** the mirror image of PR3 — the VF-drop scenario, treated as its own piece.
- **Audience:** general public, especially posters confused by inconsistent reach.
- **Format:** ~600–900 words.
- **Main question:** my post scored well — why might it not have reached people?
- **Master sections:** §9, §16 walkthrough C.
- **Primary danger:** implying a dropped post's author did something wrong — this
  describes mechanism, not culpability.
- **Prerequisites:** D4.
- **Priority:** P1 · **Status:** PLANNED

---

## MYTHS / MISCONCEPTIONS

Each entry below is a short (~300–500 word) myth-vs-code page: state the myth, state what
the code actually shows, cite the section.

### M1. "Phoenix is the algorithm"
Master §1. Primary correction: Phoenix predicts; Home Mixer and five-plus other systems
decide. Prerequisite: D1. **Priority: P0 · Status: PLANNED**

### M2. "One report cancels hundreds of likes"
Master §6. Primary correction: weights multiply predicted probabilities, not raw counts;
no literal exchange rate exists. Prerequisite: D3. **Priority: P0 · Status: PLANNED**

### M3. "X globally ranks every tweet"
Master §§2–3. Primary correction: only retrieved candidates are ever scored; there's no
single global ranking pass over all posts. Prerequisite: D1, D2. **Priority: P1 · Status:
PLANNED**

### M4. "A high score guarantees visibility"
Master §9, §16 walkthrough C. Primary correction: visibility filtering is a separate,
later gate that can remove even the top-scoring candidate. Prerequisite: D4. **Priority:
P0 · Status: PLANNED**

### M5. "All out-of-network recommendations come from one recommender"
Master §3. Primary correction: SimClusters, Phoenix retrieval (three source variants),
and TweetMixer are independent systems with different mechanisms. Prerequisite: D2.
**Priority: P2 · Status: PLANNED**

### M6. "Checked-in weights prove today's production settings"
Master §15, §17. Primary correction: every specific number in this material is a
checked-in default; the repository shows the override machinery, never a live value.
Prerequisite: G7. **Priority: P1 · Status: PLANNED**

### M7. "DPP definitely runs in production"
Master §8. Primary correction: two separate defaults exist (Home Mixer's request default
vs. VMRanker's own server flag, which defaults to off) — conflating them was a real error
caught in review. Prerequisite: D3. **Priority: P2 · Status: PLANNED**

### M8. "The model simply reads tweet text and decides whether it likes it"
Master §4–5. Primary correction: the scoring request carries identifiers/counts/flags,
not raw text or media; Phoenix predicts ~24 separate outcomes, not one verdict.
Prerequisite: D3. **Priority: P1 · Status: PLANNED**

---

## FAQ / QUESTION-DRIVEN EXPLAINERS

### F1. "Does reporting a post really hurt it that much?"
- **Format:** ~300–400 word FAQ entry. **Master sections:** §6. **Danger:** same
  exchange-rate misreading as M2 — should link to M2 rather than re-explain it.
  **Prerequisites:** M2. **Priority:** P2 · **Status:** PLANNED

### F2. "Do ads replace posts from people I follow?"
- **Format:** ~300–400 word FAQ entry. **Master sections:** §12. **Danger:** implying ads
  compete with organic posts for ranking score, when they're inserted afterward.
  **Prerequisites:** none. **Priority:** P2 · **Status:** PLANNED

### F3. "Can I see why a specific post was recommended to me?"
- **Format:** ~300–500 word FAQ entry, referencing "Under the Hood" (the one confirmed
  public transparency surface) and being explicit about what it does and doesn't expose.
  **Master sections:** GLOSSARY.md "Under the Hood" entry, §17. **Danger:** overselling
  Under the Hood as a ranking debugger — it explicitly isn't one.
  **Prerequisites:** G7. **Priority:** P2 · **Status:** PLANNED

### F4. "Is the algorithm the same for everyone?"
- **Format:** ~400–600 word FAQ entry. **Master sections:** §15. **Danger:** implying
  specific knowledge of who gets which experiment — the matching machinery is public, the
  live assignments are not. **Prerequisites:** G7. **Priority:** P2 · **Status:** PLANNED

---

## SHORT / SHAREABLE CONTENT

### S1. One-card "ranking vs. visibility" graphic
- **Format:** single-image card, derived directly from D4. **Master sections:** §9, §16.
  **Danger:** losing the Interstitial-vs-Drop distinction in a compressed visual.
  **Prerequisites:** D4. **Priority:** P1 · **Status:** BACKLOG (needs visual-design
  phase, not this one)

### S2. "Six things the public code actually shows" card set
- **Format:** short-form list, one fact per card, drawn from master §17's "directly
  established" list. **Master sections:** §17. **Danger:** compressing a hedged claim
  into an unhedged one-liner. **Prerequisites:** G7. **Priority:** P2 · **Status:**
  BACKLOG

### S3. "Six things nobody can know from this code" card set
- **Format:** companion to S2, drawn from master §17's "not knowable" list. **Master
  sections:** §17. **Danger:** same as S2, in the opposite direction — don't overstate
  certainty about what's unknown either. **Prerequisites:** G7. **Priority:** P2 ·
  **Status:** BACKLOG

### S4. Codename decoder card
- **Format:** single reference card, one line per proper noun (Agatha, BDSM, Grox,
  Gizmoduck, Botmaker, Scarecrow, UserCredV2, abuse-enforcement-service). **Master
  sections:** §10, GLOSSARY.md. **Danger:** the BDSM/Botmaker-Scarecrow confusions this
  entire family exists to prevent — must not reintroduce them through oversimplification.
  **Prerequisites:** D5. **Priority:** P2 · **Status:** BACKLOG

---

## INTERACTIVE / FUTURE

These require a presentation layer this phase doesn't build. Recorded here as backlog so
Phase 4 has a starting list, not because any of them should start now.

### I1. "Why did X show me this?" decision explorer
- **Purpose:** interactive walk through PR3/PR4's decision tree with branching questions.
  **Master sections:** §16, drawing on §§3–11. **Danger:** an interactive tool implies
  more certainty/completeness than the underlying material supports — needs explicit
  "illustrative, not a live debugger" framing throughout. **Prerequisites:** PR3, PR4, all
  six diagrams. **Priority:** BACKLOG

### I2. Interactive full pipeline
- **Purpose:** clickable version of D1, expanding into D2/D3/D4/D5/D6 in place.
  **Master sections:** all. **Danger:** scope creep — could become a second analysis
  effort if not tightly bounded to what's already in the diagram suite. **Prerequisites:**
  all six diagrams, all guides. **Priority:** BACKLOG

### I3. Filterable ranking-weight explorer
- **Purpose:** let a reader explore the full RankingScorer weight table interactively.
  **Master sections:** §6. **Danger:** the highest-risk item in the entire roadmap for
  accidentally becoming a growth-hacking calculator — must never let a user "compute" a
  hypothetical score from raw event counts; interaction should be limited to exploring
  checked-in weights, not simulating outcomes. **Prerequisites:** G4, M2.
  **Priority:** BACKLOG

### I4. Service/codename encyclopedia
- **Purpose:** searchable, expanded version of `GLOSSARY.md` plus D5.
  **Master sections:** all safety/architecture sections. **Danger:** drifting out of sync
  with `GLOSSARY.md` if maintained separately — should be generated from or tightly
  linked to the master glossary, not a fork of it. **Prerequisites:** D5, G6.
  **Priority:** BACKLOG

---

## Summary

**37 artifacts** across seven families (6 diagrams, 7 guides, 4 practical pieces, 8
myths, 4 FAQ entries, 4 short/shareable pieces, 4 interactive/future concepts). This
exceeds the initial 15–25 estimate because the union of explicitly requested strong
candidates across all seven families already totals 29 before FAQ/short/interactive
additions — breadth was prioritized over hitting a specific count. Six are WIREFRAME
(this phase's diagrams); everything else is PLANNED or BACKLOG. Nothing beyond the six
diagram wireframes should move past PLANNED in this phase.

---

## Phase progression

**PHASE 1 (this phase):** Foundation — purpose, roadmap, content map, editorial rules,
claim bank, visual language, six diagram wireframes. Complete as of this document.

**PHASE 2:** Core diagrams + short explainer.
- Review and refine the six diagram wireframes against real reader feedback.
- Choose visual art direction (colors, typography, icon set) — the first place
  `VISUAL_LANGUAGE.md`'s semantics get an actual visual system.
- Produce polished versions of D1–D4 first (the four highest-priority diagrams).
- Write G1 (5-minute guide).
- Draft the "Myths vs. Code" family (M1–M8), since myth-busting is high-leverage and
  doesn't require the full guide set to exist first.

**PHASE 3:** Practical guides + myth-busting completion.
- G2–G7 (the remaining guides).
- PR1–PR4 (practical pieces), written strictly against `EDITORIAL_RULES.md`'s practical-
  advice policy.
- Remaining diagrams (D5, D6) polished.
- F1–F4 (FAQ entries).

**PHASE 4:** Interactive/site presentation.
- A real home for this content (site structure, navigation between QUICK/GUIDE/MASTER
  layers).
- I1–I2 as the first interactive concepts, tightly scoped.

**PHASE 5:** Short/shareable derivatives.
- S1–S4 and any additional short-form content, once the underlying guides and diagrams
  are stable enough to compress without drift.

This is planning only. Phase 2 does not start in this session.
