# Final Residual Deep-Dive
## Phoenix Serving and Two-Tower Retrieval

Scope: exactly two prior-flagged blind spots — (A) Phoenix serving batching/chunking
reconciling Home Mixer's 2800-candidate cap against the model's declared
`candidate_seq_len`, and (B) the shipped two-tower retrieval model's internals. Builds
on `_analysis/rapid/01_retrieval.md`, `04_model_runtime_boundaries.md`, and
`05_gap_closure.md`; does not re-derive their findings except where corrected here.
Source only, evidence-gathering pass — no synthesis files edited.

## Executive result

**A — serving batching: RESOLVED** (mechanism). The engine does not chunk or batch a
single request's candidates across multiple forward passes. One `PredictNextActions`
RPC carries exactly one `CandidateSet`; the server truncates that candidate list to the
first `candidate_seq_len` entries (in whatever order Home Mixer sent them) when building
the model's fixed-size input tensor, and the reply path only returns a prediction for
that same truncated prefix — everything past `candidate_seq_len` silently receives no
response entry at all. Separately, the server does **dynamic cross-request batching**:
it opportunistically groups multiple concurrently-arriving *users'* requests into one
GPU/TPU forward pass (up to a configured `batch_size`), which is a throughput
optimization orthogonal to per-request candidate truncation and does not affect
per-request semantics. The exact numeric value of `candidate_seq_len` used in live
production is not established (a training-config value of 64 and a separate,
independently-settable launch-time default of 1400 both exist in this repo — see below)
— that specific number is UNKNOWN, but the *mechanism* is fully traced end to end.

**B — two-tower retrieval: RESOLVED** (architecture, training objective, and the
serving-side top-k search are all directly present in this repository). The user tower
is a full transformer (the same `RecsysAggregatedModel` backbone the ranking model
uses) over the viewer's action history plus user features, mean-pooled and L2-normalized
into one query vector. The item tower is a much shallower MLP/projection tower over an
author-embedding and (in the shipped `xrecsys_two_tower` config) a **Semantic-ID token,
explicitly not a raw post embedding** (`use_post_embedding=False`, `use_post_sid=True`),
also L2-normalized. Similarity is a plain dot product between L2-normalized vectors,
i.e. cosine similarity. Training is a temperature-scaled, in-batch + global-negative
contrastive (InfoNCE-style) loss on `SERVER_TWEET_FAV` as the positive action for one
model head (there is a second, broader "immersive" head trained on a wider engagement
set). Crucially, **the ANN/top-k lookup itself is checked into this repository**: at
serving time the query embedding is dot-producted against a full, resident,
checkpoint-loaded table of precomputed item embeddings (tens of millions of rows), and
the top-k selection is done by a custom CUDA radix-select kernel
(`phoenix/xrex/cuda/top_k_by_key/`) — this is exact brute-force top-k over the resident
corpus, not a call out to an external approximate-nearest-neighbor service, and not a
quantized/graph-based ANN index either.

## A. PredictNextActions serving path

### End-to-end call graph

```
Home Mixer (PhoenixScorer::score)
  build_prediction_request()                          [home-mixer/util/phoenix_request.rs]
    candidates.iter().take(PHOENIX_CLIENT_MAX_CANDIDATES=2800)   <- first truncation, client-side
    -> PredictNextActionsRequest{ candidate_sets: [CandidateSet{ candidates: Vec<TweetInfo> (<=2800) }], sequences, ... }
        |
        v  gRPC
RecsysPredictorImpl::predict_next_actions          [xai-recsys-engine/src/python.rs:1121]
  predict_next_actions_inner()
    - reject if checkpoint_loading                  -> Status::unavailable
    - reject if inflight_semaphore exhausted         -> Status::resource_exhausted
    - reject if deadline-admission shed              -> Status::resource_exhausted (see A3)
    - reject if candidate_sets.len() != 1            -> Status::invalid_argument
    - reject if no CandidateSet present               -> Status::invalid_argument
    - handle_request(candidate_set, sequence, ...)
        -> InputBuffer::compute_for_item() / compute_from_columnar_bytes()   [xai-recsys/src/util.rs]
             candidates_to_process = candidate_set.candidates.len().min(candidate_seq_len)  <- second truncation, server-side
             .take(candidates_to_process)  (preserves original order, first N kept)
        -> PredictRequestItem{ candidate_set (full, untruncated Vec), input_buffer (truncated tensor), sender: oneshot }
        -> enqueued onto an mpsc channel (request_queue.rs), timeout = enqueue_timeout_ms
    - await oneshot result (or cancellation/deadline)
        |
        v  (async, on a Python/JAX worker loop, not shown fully in this crate)
RequestQueue::dequeue()  [xai-recsys-engine/src/request_queue.rs]
    - opportunistic FIFO batch fill, no forced wait window (see "Dynamic request batching")
RankingBatchPrep::compute_batch_inputs_rust_quick()   [python.rs:1584]
    - length_of_input = request.items.len().min(batch_size)
    - per-row copy_from_slice of each item's InputBuffer into a [batch, candidate_seq_len, ...] tensor
    - (JAX forward pass — happens in Python code calling this Rust-built batch, not itself in this crate)
PredictRequestBatch::reply()  [python.rs:389]
    - zips items[i] (original enqueue order) with responses.outer_iter()[i]  <- per-request row match, exact
    - within one row: zips response.outer_iter() (candidate_seq_len rows, fixed)
                       with item.candidate_set.candidates.iter() (full untruncated Vec, up to 2800)
                       -> stops at min(candidate_seq_len, candidates sent)  <- THE reconciliation point
    - sender.send(Ok(CandidateDistributionSet{ candidate_distributions: <=candidate_seq_len entries }))
        |
        v
Home Mixer (PhoenixScorer::score, resumed)
    candidates.iter().map(|c| phoenix_scores: predictions.candidate_scores(&c.get_original_tweet_id()))
```

### Candidate batching/chunking

**There is no chunking.** A `PredictNextActionsRequest` is rejected outright unless it
contains exactly one `CandidateSet` (`python.rs:995-1005`, `m != 1` ->
`Status::invalid_argument("Request must contain exactly one candidate set.")`). Within
that one set, the server does not split the candidate list into multiple sequential
forward passes. Instead:

1. **Client-side truncation** (Home Mixer, before the RPC is even sent):
   `build_tweet_infos()` does `candidates.iter().take(PHOENIX_CLIENT_MAX_CANDIDATES)`
   where `PHOENIX_CLIENT_MAX_CANDIDATES = 2800`
   (`home-mixer/util/phoenix_request.rs:11,108-118`). No sort precedes this `.take()` in
   any file this pass read — whatever order the post-retrieval, post-filter candidate
   slice is in when `PhoenixScorer::score` is called is the order sent. This pass did not
   find (and did not exhaustively search for) an explicit pre-scoring sort elsewhere in
   the pipeline; Rapid 01/S01 did not identify one either.
2. **Server-side truncation** (inside the serving engine, one process, one forward
   pass): `InputBuffer::new_with_candidates` computes
   `candidates_to_process = candidate_set.candidates.len().min(candidate_seq_len)` and
   then `.iter().take(candidates_to_process)` — the first `candidate_seq_len` candidates,
   in received order, are hashed/embedded into the model's fixed-size
   `[candidate_seq_len, ...]` tensor slots; nothing beyond that index is ever written into
   the tensor at all (`phoenix/crates/common/xai-recsys/src/util.rs:340-409`).
3. **Reply-side truncation, independently**: `PredictRequestBatch::reply()` builds each
   user's response by `response.outer_iter().zip(item.candidate_set.candidates.iter())`
   — `response` (the model's per-row output) has exactly `candidate_seq_len` rows
   (fixed by tensor shape); `item.candidate_set.candidates` is the **original, untruncated**
   list Home Mixer sent (up to 2800). Rust's `.zip()` stops at the shorter iterator, so
   this produces exactly `min(candidate_seq_len, candidates_sent)` `NextActionDistribution`
   entries, always corresponding to the first N candidates by request order
   (`python.rs:408-465`).

So the "reconciliation" between 2800 and a much smaller `candidate_seq_len` is: **the
tail past `candidate_seq_len` is silently truncated, twice (input truncation and
independently at reply time, both landing on the identical prefix since both key off the
same underlying `Vec` order)** — not chunked into further forward passes, not rejected,
not an error.

### Model capacity reconciliation

**"2800" is X, "64/128" is Y, the serving engine does Z, therefore —**

- **2800** (`PHOENIX_CLIENT_MAX_CANDIDATES`) is a **client-side (Home Mixer) hard cap** on
  how many `TweetInfo` entries get serialized into the request at all — not a model
  parameter, not read from any Phoenix config, a plain Rust constant in
  `home-mixer/util/phoenix_request.rs`.
- **64** is `home_direct_packed`'s (the shipped ranking reference config, per Rapid 05)
  **training-time `candidate_seq_len`** — the number of candidate slots the model was
  *trained* with (`phoenix/xrex/configs/xrecsys.py:242,320,360-374` all set
  `"candidate_seq_len": 64` for the `home_direct_packed*` family). **128** is
  `xrecsys_gen_recs`'s training-time value, a different, not-shipped-as-ranking-reference
  config per Rapid 05.
- **Z, newly found this pass**: `phoenix/xrex/inference/launch_inference.py` — the actual
  runnable inference-server entry point — exposes `--candidate_seq_len` as an
  **independent CLI flag at serving/launch time**, `default=1400`
  (`launch_inference.py:425`), which gets folded into `base_overrides` as
  `f"candidate_seq_len={args.candidate_seq_len}"` (`launch_inference.py:405`) and passed
  through to the Rust engine's `ModelConfig::from_params` via the Python binding
  (`python.rs:3219,3305`, `xai-recsys/src/model_config.rs:207-216,236-237`). In other
  words, **the value actually enforced by the truncation logic above is a deployment-time
  parameter, independently overridable from whatever candidate_seq_len the checkpoint was
  trained with** — the model's transformer/attention stack does not hard-code a sequence
  length; rotary position embeddings and a variable-shape tensor make this override
  mechanically possible (this pass did not verify whether serving a checkpoint at a
  different `candidate_seq_len` than it trained at changes prediction quality — that is a
  correctness/quality question this repo's code does not itself answer).
- **Therefore**: 2800 and 64/128 are not directly comparable numbers in the first place —
  one is a client request-shaping cap, the other is a training-config default that this
  repo's own launch tooling does not treat as fixed at serving time. The repository's
  shipped launch script's own default (1400) is already ~22x the training config's 64,
  which substantially narrows — without fully closing — the gap Rapid 04/05 flagged.
  **What remains missing**: the actual `--candidate_seq_len` value (if any override is
  passed at all) used by whatever process serves live `PredictNextActions` traffic. This
  snapshot does not contain a deployment manifest or launch invocation naming that value —
  consistent with every prior pass's finding that live deployment configuration is
  external.

### Dynamic request batching

Server-side batching **does** exist, and it is a batching of *concurrent users' whole
requests* into one model forward pass — not a way of handling one oversized request.
Mechanism (`xai-recsys-engine/src/request_queue.rs`):

- Each accepted `PredictNextActionsRequest` becomes one `PredictRequestItem` pushed onto
  an `mpsc::Sender<PredictRequestItem>` (`channel_size`, default 2048 per
  `launch_inference.py:511`).
- A background task (`RequestQueue::new`'s `background_task`) blocks on the first item,
  then **opportunistically drains whatever is already sitting in the channel** via
  non-blocking `try_recv()` until either the buffer reaches `batch_size` capacity or the
  channel is empty — **there is no additional wait/timeout window to let more requests
  arrive**; batching only combines whatever happened to already be queued at the moment
  the consumer looks.
- **Batching key**: none beyond "arrived on this model server's queue" — one queue per
  running server process (one process serves one model/cluster), so batching is
  implicitly per-deployed-model, not keyed by any request attribute.
- **Max batch size**: the constructor's `batch_size` parameter (traces back to
  `--bs_per_device`-derived `inference_batch_size`/bucket values in
  `launch_inference.py:330,354`), a deployment-time value, not found hard-coded here.
- **Timeout/window**: none for *forming* a batch (see above); separately,
  `enqueue_timeout_ms` (default 1000ms, `launch_inference.py:517`) bounds how long a
  single request will wait to even get *into* the channel before being rejected
  (`BATCHING_TIMEOUT_DROP`, `python.rs:1352-1356`) if the channel itself is full — a
  backpressure mechanism, not a batch-fill wait.
- **Does it affect semantics or only throughput?** Only throughput. Each row of the batch
  tensor is independently populated from one request's own `InputBuffer`
  (`RankingBatchPrep::compute_batch_inputs_rust_quick`, `python.rs:1584-1600` onward, one
  `par_chunks_exact_mut` row per item), and `reply()` demultiplexes results back to the
  correct request purely by matching `items[i]` to `responses.outer_iter()[i]` in the
  same order they were read out of the batch — no cross-request mixing of candidates or
  scores. This is orthogonal to, and does not interact with, the per-request
  `candidate_seq_len` truncation described above.

### Output reassembly

Within one request, output rows map to the **first N candidates in the order Home Mixer
sent them** — not to any recomputed priority or the original retrieval order specifically
(retrieval order is whatever order candidates were in by the time
`build_prediction_request` was called; this pass did not find a re-sort at that call
site). On the Home Mixer side, `PhoenixScorer::score` does not consume the response
positionally — it looks each of its own candidates up by tweet ID:
`predictions.candidate_scores(&c.get_original_tweet_id())`
(`home-mixer/scorers/phoenix_scorer.rs:106-115`). The `candidate_scores` method itself is
defined in the external `xai_candidate_pipeline` crate, not vendored in this snapshot —
**DIRECT** that lookup is by tweet ID (not index), **UNKNOWN** exactly what value it
returns for a tweet ID absent from the response (a truncated-away candidate) — plausibly
an empty/default score vector given the surrounding code treats the call as infallible,
but this repo does not contain that implementation to confirm.

### Failure/edge cases

| Condition | Behavior | Evidence |
|---|---|---|
| Empty `candidate_sets` (no `CandidateSet` object at all) | `Status::invalid_argument("Request does not contain any candidates.")` | `python.rs:1026-1032`, DIRECT |
| More than one `CandidateSet` | `Status::invalid_argument("...exactly one candidate set.")` | `python.rs:995-1005`, DIRECT |
| `CandidateSet` present but its `.candidates` list is empty | No error — proceeds with an all-zero-padded tensor and returns an empty `candidate_distributions` list | inferred from `InputBuffer::new_with_candidates`'s `candidates_to_process = 0.min(...) = 0` path; not independently exercised via a test in this pass — STRONG_INFERENCE |
| Candidate list larger than `candidate_seq_len` | Silent truncation to the first `candidate_seq_len`, no error, no partial-failure signal — see above | DIRECT |
| Server loading a new checkpoint | Every new request rejected with `Status::unavailable`, existing in-flight requests unaffected | `python.rs:944-955`, DIRECT |
| Concurrent-request cap (`max_inflight_requests`, default 2560) exceeded | `Status::resource_exhausted` | `python.rs:957-968`, DIRECT |
| Load-balancer ticket unavailable (`LoadGauge`) | `Status::resource_exhausted` | `python.rs:1007-1019`, DIRECT |
| Queue (channel) full past `enqueue_timeout_ms` | `Status::resource_exhausted("...queue full")`, counted as `BATCHING_TIMEOUT_DROP` | `python.rs:1348-1356`, DIRECT |
| Deadline-admission shedding (EWMA-estimated service time implies the client's gRPC deadline can't be met) | Rejected upfront with `Status::resource_exhausted`, before any model work — a throughput-preserving early reject, not a partial response | `python.rs:970-993`, `admission.rs`, DIRECT |
| Item goes stale in queue (past `max_staleness`/its own deadline) before being dequeued | Dropped with `Status::deadline_exceeded`, that one request's oneshot gets an `Err`; other queued items unaffected | `request_queue.rs:17-25,55-58,73-77`, `python.rs:280-289` (`on_stale_drop`), DIRECT |
| Client cancels / gRPC deadline exceeded mid-flight | `tokio::select!` on a `CancellationToken`; request returns `Status::cancelled`, other requests in the same batch are unaffected (per-item oneshot, no shared failure) | `python.rs:936-1044,1363-1376`, DIRECT |
| Whole model forward pass fails (exception in the Python/JAX worker — not directly traced in this crate) | Not shown in this crate; per Rapid 04, Home Mixer's `PhoenixScorer::score` treats any `Err` from the dispatch as failing *all* candidates in that call, and `PostCandidate.phoenix_scores` simply keeps its prior/empty value — the request as a whole is not failed | `home-mixer/scorers/phoenix_scorer.rs:101-104`, `_analysis/rapid/04...` |
| `RetrieveTopKCandidates`: request with an empty `user_ids` | `request.user_ids.pop().unwrap()` — **an unhandled `Option::unwrap()`, i.e. a Rust panic**, not a graceful `Status` — notably inconsistent with the ranking path's explicit validation | `python.rs:2827`, DIRECT (code as written); this pass did not trace whether tonic/tokio's panic boundary converts this into a generic 500-class error to the caller or crashes the worker thread — UNKNOWN |

**One bad candidate does not fail the RPC** (there is no per-chunk concept to fail — the
whole truncated set is one tensor, one forward pass); **a wholly failed model call fails
the whole RPC** (propagates as an `Err`/gRPC error status), which Home Mixer then treats
as "no predictions this scoring call," per Rapid 04's already-established
framework-level semantics. This pass did not find any *partial*-success response shape
(there is no field for "these N candidates succeeded, these M failed") — success is
all-or-nothing at the RPC level, with candidate-count truncation being silent and
separate from failure handling.

### What remains unknown

- The actual `--candidate_seq_len` (and `--history_seq_len`, `--bs_per_device`) values
  passed to `launch_inference.py` for whatever process serves live `PredictNextActions`
  traffic — this snapshot has no deployment manifest.
- Whether serving a checkpoint trained at one `candidate_seq_len` (e.g. 64) with a
  different, larger runtime override (e.g. 1400) is something this codebase actually does
  in production, or whether the flag is only exercised for benchmarking/quickstart
  purposes (`oss_bench/bench.py`'s own default config names do not set
  `--candidate_seq_len` explicitly in the files this pass read — not independently
  confirmed either way).
- Exact behavior when `RetrieveTopKCandidates`'s `user_ids.pop().unwrap()` panics (client
  visible error class) — not traced past the panic call site itself.
- Whether there is a pre-scoring sort anywhere in Home Mixer's pipeline that would make
  "first `candidate_seq_len` in request order" a meaningful priority ordering rather than
  an arbitrary one — targeted grep only, not exhaustive.
- The exact return value/behavior of the external `candidate_scores(tweet_id)` lookup for
  a tweet ID that was truncated out of the response.

## B. Two-tower retrieval model

### Model architecture

`phoenix/xrex/models/recsys_two_tower_model.py` defines `RecsysTwoTowerModel` — a true
two-tower architecture (unlike the single-sequence decoder ranking model Rapid 04
examined): a **user tower** and a **candidate ("item") tower** are computed
independently and combined only via a final dot product, never attending to each other.
This confirms and extends Rapid 04's passing note that a genuine two-tower model exists
"for a different purpose" — this pass reads it directly.

### User/query tower

The user tower **reuses the same `RecsysAggregatedModel` transformer backbone** the
ranking model is built on (`self.user_tower: RecsysAggregatedModel`,
`recsys_two_tower_model.py:844`) — same hashed-ID embedding scheme, same
causal-attention transformer stack. It consumes (`build_user_inputs`,
`:853-1046`):

- **Action history** (`history_seq`): post-hash and author-hash embeddings, a multi-hot
  action embedding per history position, product-surface, and — when `use_post_sid` is
  set (it is, in the shipped config, see below) — a post Semantic-ID token per history
  item.
- **User/account features**: country, language, location, gender, age, installed apps —
  each individually feature-switchable at the config level
  (`enable_user_country_feature` etc., `xrecsys_two_tower.py:254-259`).
- **No explicit followed-accounts or timing/context field** was found feeding the user
  tower specifically in this file beyond what's embedded in history-item product-surface
  and timestamp features already covered by the shared `block_history_reduce` machinery —
  not independently re-verified against every wire field this pass.

The transformer output is mean-pooled over unmasked positions (or, when
`use_seqpack=True` — the shipped config's default, `xrecsys_two_tower.py:317` — pooled
via a segment-sum over packed variable-length sequences) into a single vector, then
**L2-normalized** (`recsys_two_tower_model.py:1299-1301`, `EPS=1e-12` floor).

### Item tower

`RecsysCandidateTower` (`:75-225`) is architecturally much shallower than the user
tower — no transformer, a small MLP/linear-projection stack over a small number of
per-candidate embedding tokens (`_concat_then_mlp`: two linear layers with a SiLU
nonlinearity; or `_project_then_sum`: a learned per-hash-slot linear projection summed
across slots; or plain mean-pooling — which combine mode is used is config-selected,
`enable_linear_proj`/`feature_prep_enabled`). Inputs, per the shipped
`xrecsys_two_tower*` config (`xrecsys_two_tower.py:308-315`):

- `use_post_embedding: False` — **no raw post content/multimodal embedding feeds the
  item tower in this config.**
- `use_post_sid: True`, `sid_num_levels: 6`, `sid_codebook_size: 256`,
  `sid_embed_dim: 1024`, `sid_cross_attn: True` — the item's content representation is
  its **compact hierarchical Semantic ID** (6 levels, 256-way each), not raw
  text/media/engagement-count features.
- Author-hash embeddings (always present, `num_author_hashes` tokens).
- Output is L2-normalized (`_l2_normalize_candidates`, same `EPS` floor as the user
  tower).

**Two candidate heads exist in the shipped config** (`num_candidate_heads: 2`,
`head_names: ["home", "immersive"]`, `xrecsys_two_tower.py:293-294`), each with its own
projection weights (`head_index` parameter threading through `_concat_then_mlp`/
`_project_then_sum`) but sharing the same underlying tower structure — the model
produces two different item-embedding spaces from the same input tokens, one per
product-surface family (mapped via `head_dataset_mapping`: `HOME` -> head 0,
`IMMERSIVE4Day`/`IMMERSIVE2Day`/`IMMERSIVENSFW` -> head 1).

**Vector dimensionality**: `emb_table_width: 1024` (both towers,
`xrecsys_two_tower.py:265`).

### Training objective

`compute_retrieval_loss` (`recsys_two_tower_model.py:505-838`) is a temperature-scaled,
softmax-style contrastive loss (computed via `logsumexp`, i.e. InfoNCE-shaped), with:

- **Positive pair**: a (user-history, candidate) pair is a valid positive only if the
  candidate carries at least one of a configured `positive_actions` set **and** none of
  `hard_negative_actions`/`soft_negative_actions` (`:618-636`). In the shipped combined
  base config, `positive_actions = [SERVER_TWEET_FAV]` for the "home" head — **the
  positive signal this pass directly confirms is "the user favorited this post,"** not a
  broader engagement definition, for the home-surface head specifically. A second,
  broader `immersive_positive_actions` set (favorite, reply, quote, retweet,
  video-quality-view, follow-author, bookmark, share — `xrecsys_two_tower.py:283-292`)
  trains the "immersive" head.
- **In-batch negatives**: other users' positive candidates within the same training
  batch, gathered via a `shard_map`'d matmul and explicit off-diagonal masking
  (`_pos_scores`/`_rearrange_negatives`, `:301-327,701-723`).
- **Global/sampled negatives**: a separate, config-sized pool
  (`num_global_negatives_per_example: 64` in the shipped base config,
  `xrecsys_two_tower.py:262`), corrected for sampled-softmax bias via a `log_q_correction`
  keyed on empirical tweet-appearance counts (`:650-690`) — same technique Rapid 04 found
  in the `xrecsys_gen_recs` ranking-adjacent config, confirmed here independently for the
  two-tower model.
- **Hard/soft negative actions**: candidates the user took a configured negative-signal
  action on (not read further to enumerate the exact action list in this pass) are folded
  into the denominator as explicit negatives rather than simply excluded
  (`true_neg_scores`, `:731-734`).
- **Optional user-user and item-item repulsion terms** (`apply_u2u_and_i2i_loss`, default
  `False` in the shipped base config, `:279`): when enabled, adds extra contrastive terms
  pushing distinct users' embeddings and distinct items' embeddings apart within a batch,
  folded into the same `logsumexp` denominator (`_sharded_u2u_and_i2i_matmul`,
  `:743-793`).
- **Safety-filter masking**: an optional hard mask (`safety_filter_apply_to_candidates`,
  `safety_filter_mode`) can exclude candidates carrying certain safety-label bits from
  ever counting as valid positives (`:593-608`) — a training-time safety mechanism
  distinct from the retrieval-index admission and visibility-filtering mechanisms
  documented elsewhere in this repository's analysis.

**Plain-English answer**: two items (or a user and an item) become close in retrieval
space when a real viewer favorited that post shortly after that history (for the "home"
head), pulled together by a contrastive loss that simultaneously pushes the query away
from everyone else's positive candidates in the same training batch, a separately-sampled
global negative pool, and (optionally) other users'/items' embeddings directly.

### Training data

Config-declared dataset path: `PhoenixDataset` with `path="/path/to/offline_kafka_dump"`
(a placeholder, environment/deployment-resolved — `xrecsys_two_tower.py:230-246`),
`dataset_type="aggregated_kafka"`, `num_kafka_partitions=1024` — the same
Kafka-sourced-data pattern Rapid 04 found for `xrecsys_gen_recs`, now confirmed for the
two-tower config too. **Training task, precisely**: predict, from a user's action-history
sequence, an embedding close to the embedding of a post that user will favorite (or, for
the immersive head, more broadly engage with) — this is retrieval-style "predict what
the user will engage with next," not generic "find items similar to history items"
similarity search; the supervision signal is real subsequent user actions, not a static
similarity graph.

### Serving / ANN lookup

**The checked-in serving path contains the top-k search itself — this is the single
most significant finding of Part B.**

`RetrievalModelRunner` (`phoenix/xrex/inference/model_runner.py:4243` onward) holds, in
resident process memory, a full table of precomputed item embeddings loaded from the
model checkpoint at startup (`self.state.post_embeddings.embeddings.x`, alongside
parallel `all_post_ids`/`all_author_ids`/`all_dataset_types` arrays,
`maybe_load_checkpoint`, `:4336-4354`) — up to `max_posts: 28_672_000` rows in the
shipped config (`xrecsys_two_tower.py:307`). At request time
(`RecsysTwoTowerModel.forward`, `recsys_two_tower_model.py:1306-1382`):

1. The user tower computes one query vector from the request's history/user features
   (no candidates are sent in a `RetrieveTopKCandidatesRequest` at all — only
   `user_ids`, `sequences`, `top_k`, optional topic filters, and an
   `eligible_posts_bloom_filter`, per `python.rs:2760-2880` — consistent with a genuine
   two-tower design where the query side needs no candidate information).
2. `compute_top_k`'s inner function does a plain matmul,
   `jnp.matmul(user_embedding.astype(bfloat16), post_embeddings.T)`, against the
   **entire** resident post-embedding table (sharded across an `"expert"` mesh axis with
   `jax.lax.all_to_all` to recombine partial results — a sharding/parallelism detail, not
   an approximation of the search itself).
3. `top_k_by_key` (`from xrex.cuda.top_k_by_key import top_k_by_key`,
   `recsys_two_tower_model.py:23`) selects the top-k scores. This is a **custom CUDA
   kernel checked into this repository**
   (`phoenix/xrex/cuda/top_k_by_key/src/top_k_by_key_radix_select_kernel.cu` and
   siblings) implementing a radix-select top-k — an **exact** top-k over the computed
   scores, not a quantized or graph-based approximate index (no FAISS/ScaNN/HNSW
   dependency was found in this file or its imports).
4. Optionally, the search can be restricted to a `dataset_type`-contiguous slice of the
   table for speed (`enable_dataset_slice_topk`, `_get_dataset_ranges`) — a performance
   optimization over which rows of the same brute-force search to scan, not a
   different search algorithm.
5. A **live-swap ("hotswap") mechanism** exists to replace the resident post-embedding
   table without restarting the server (`_on_post_hotswap`,
   `_prepare_live_swap_derived_state`/`_commit_live_swap_derived_state`,
   `:4356-4469`) — the index can be refreshed in place.

**So: yes, the checked-in serving path contains the ANN search itself**, in the specific
sense of "exact top-k over a resident, checkpoint-loaded embedding table via a
purpose-built CUDA kernel." What is **not** shown in this repository is the **offline
job that populates that embedding table in the first place** — i.e., the batch process
that runs the item tower over the full ~28.6M-post corpus to produce the embeddings the
checkpoint ships with. `RecsysCandidateModelConfig.make_post_embeddings()`
(`recsys_two_tower_model.py:260-286`) only defines an **empty placeholder** array shape
at model-construction time (`jnp.empty(...)`, filled with random values only under a
`DEBUG_ALLOW_RANDOM_INIT` env flag for local testing) — the real values are expected to
arrive via checkpoint load. That production embedding-population pipeline was not found
in the files this pass read and is not claimed to exist elsewhere in this repository —
**UNKNOWN/external**, consistent with every other "trained artifact" boundary this rapid
track has already established.

**`eligible_posts_bloom_filter`**: the retrieval request proto carries a bloom filter of
eligible post IDs, consumed server-side (`RetrieveRequestBatch::build_eligible_mask`,
`python.rs:630-673`) to mask out ineligible rows of the post table before/around the
top-k search. This pass found **no call site in `home-mixer/sources/phoenix_source.rs`,
`phoenix_topics_source.rs`, or `phoenix_moe_source.rs` that populates this field** — its
construction, if any, happens inside the external `RetrievalDispatch`/
`xai_candidate_pipeline` client crate, not in the Home Mixer source this pass can read.
Whether/how this bloom filter relates to `phoenix-rankall`'s index-admission rules
(Rapid 01) is **UNKNOWN** — they are plausibly two independent eligibility mechanisms
(index-admission controls what's ever *in* the resident table at all; the bloom filter
would control what's eligible *per query*), but this snapshot does not show them wired
together anywhere.

### Relation to rankall

Unchanged from Rapid 01/05, now sharpened: `phoenix-rankall` is an **ingestion/admission**
pipeline deciding whether a post is ever added to a retrieval-relevant index at all
(Kafka-driven, independent of any single request). This pass's finding is about a
**separate, later stage**: the two-tower serving engine's resident post-embedding table
and its top-k search over that table. This pass did not find a direct code-level link
between `phoenix-rankall`'s on-disk snapshot windows and the `all_post_ids`/
`post_embeddings` array `RetrievalModelRunner` loads from checkpoint — that connection
remains the same UNKNOWN Rapid 01 already flagged ("the exact wire connecting
`phoenix-rankall`'s snapshot windows to what the serving side reads at request time").
This pass narrows *where on the serving side* that connection would have to land (the
checkpoint's `post_embeddings` field), without proving the link itself.

### Relation to PhoenixSource/Topics/MOE

Unchanged from Rapid 01/05: `PhoenixSource`, `PhoenixTopicsSource`, and `PhoenixMOESource`
are Home Mixer's three client-side wrappers around the identical
`RetrievalDispatch`/`RetrieveTopKCandidates` call this pass traced server-side, differing
only in which cluster ID they target and under what request conditions they run. This
pass adds: whichever cluster string each of them resolves to presumably (STRONG_INFERENCE,
not proven) selects among differently-configured/differently-checkpointed instances of
the same `RetrievalModelRunner`/two-tower architecture — this repository does not name
that binding (same UNKNOWN as Rapid 05's Section 1B/C for the ranking side).

### Relation to SimClusters

No code-level connection found, and none expected: SimClusters (Rapid 01) is a wholly
separate system — offline-computed community-detection clusters, its own ANN service,
seeded per-request from the viewer's *recent engagement signal tweet IDs* rather than
from a learned user-tower embedding. The two-tower model computes its query embedding
from the model's own transformer over full action history, not from any SimClusters
cluster ID or embedding. Nothing in `recsys_two_tower_model.py` or `model_runner.py`
references SimClusters. This pass does not collapse the two systems; they remain
functionally parallel, independently-implemented out-of-network retrieval mechanisms.

### Reproducibility

| Component | Verdict | Notes |
|---|---|---|
| Model architecture (both towers, combine functions, loss) | **YES** | Full Haiku/JAX source, checked in |
| Training objective & config | **YES** | `compute_retrieval_loss` and `xrecsys_two_tower.py` configs are complete and readable |
| A toy/local training run | **YES (architecture)** / **PARTIALLY (data)** | Requires the same external Kafka-sourced data path as `xrecsys_gen_recs` (Rapid 04); a synthetic-data path is asserted to exist elsewhere in this repo (`oss_recsys_synth.py`, not independently reopened this pass) |
| The serving-side top-k search algorithm | **YES** | `top_k_by_key`'s CUDA kernel is checked into this repository — not external, not a third-party ANN library |
| A production-equivalent retrieval index | **NO** | Requires (a) a trained checkpoint with real `post_embeddings` (none ships), and (b) the offline job that populates those embeddings for the live post corpus (not found in this repository) |
| Live cluster->checkpoint binding | **NO** | Same external-configuration boundary as the ranking side (Rapid 05) |

## Synthesis impact

Checked against `_analysis/synthesis/HOW_FOR_YOU_WORKS.md` §§3-5, §17 and
`GLOSSARY.md`'s Phoenix/Phoenix-retrieval/Phoenix-rankall entries. No claim in the
current synthesis is contradicted by this pass — every finding below either fills in a
gap the synthesis already flagged as open or adds a fact the synthesis simply doesn't
mention yet.

1. **Candidate-count reconciliation (§5, the "which exact model config" paragraph doesn't
   currently address batching at all — no existing sentence to correct).**
   **SYNTHESIS SHOULD BE UPDATED** (addition, not correction). Recommend adding one
   sentence after the existing §5 paragraph on model-config pairing, e.g.: *"Separately,
   this repository shows that the number of candidates the model actually scores per
   request is capped and silently truncated to a configured limit — extra candidates
   beyond that limit receive no prediction at all, not a lower score — and that this
   per-request limit is itself a deployment-time setting the repository's own launch
   tooling allows overriding independently of the number the model was trained with."*

2. **Two-tower retrieval model internals (§3's Phoenix retrieval paragraph currently
   describes only the *index-admission* side, via `phoenix-rankall`; it says nothing
   about what the retrieval-serving model itself does with a query).**
   **SYNTHESIS SHOULD BE UPDATED** (addition). Current text (§3): *"Phoenix retrieval —
   the mechanism behind PhoenixSource, PhoenixTopicsSource, and PhoenixMOESource — is the
   least intuitive of the three because it works two steps removed from any individual
   request."* This remains accurate for the admission side. Recommend adding, after the
   existing paragraph on `search_unfiltered`/MOE: *"On the model side, the repository's
   own shipped reference pairing for this retrieval service is a two-tower model: one
   tower encodes the viewer's history into a single vector, a separate, much simpler
   tower encodes each candidate post from its author and a compact semantic identifier
   (not raw post text or engagement counts), and the two are compared by a simple dot
   product. At serving time this repository's own code does the full nearest-neighbor
   search itself, over a checkpoint-loaded table of precomputed post vectors, rather than
   depending on an external search service for that step — though the checkpoint's
   contents (and the process that produced them) are not included."*

3. **GLOSSARY.md's "Phoenix retrieval / RetrieveTopKCandidates" entry** (line ~42-44)
   currently reads: *"The gRPC service `PhoenixSource`, `PhoenixTopicsSource`, and
   `PhoenixMOESource` all call to pull candidates out of the index `phoenix-rankall`
   built."*
   **NO CHANGE NEEDED** to this sentence itself — it remains accurate. **Optionally
   extendable**: a short added clause noting the *model* behind this service is a
   two-tower architecture (see item 2) would round it out, but is not required for
   correctness.

4. **§17's "Directly established by this snapshot" list** already includes "Phoenix's
   model architecture and the repository's own shipped reference serving tooling" — this
   pass's findings slot under that existing bullet without needing new wording.
   **NO CHANGE NEEDED.**

5. **No existing synthesis sentence claims or implies that Phoenix's retrieval search is
   external** — so there is no incorrect sentence to fix on that specific point; this is
   purely new material (item 2 above covers it).

**Total: 2 sentences/paragraphs recommended for addition; 0 existing sentences found to
be factually wrong and in need of correction.**

## Exact source files read

**Deep-read this pass** (full or near-full function/section read, not skimmed):
`phoenix/crates/serving/xai-recsys-engine/src/python.rs` (targeted full-function reads:
lines 280-475, 588-680, 771-873, 884-1210 [`predict_next_actions_inner`/`handle_request`],
1379-1600, 1880-2300 [`RankingBatchPrep::compute_batch_inputs_rust_quick`], 2740-2920
[`retrieve_top_k_candidates_inner`], 3190-3720 [server construction, `dequeue`,
`compute_batch_inputs_rust_quick` wrapper] — file is 3765 lines total, remaining
sections are largely repeated per-field copy macros and the retrieval-side mirror of the
ranking batch-prep struct, not independently read line-by-line);
`phoenix/crates/serving/xai-recsys-engine/src/request_queue.rs` (full, 131 lines);
`phoenix/crates/serving/xai-recsys-engine/src/admission.rs` (lines 1-100 of 395);
`phoenix/crates/serving/xai-recsys-server/src/lib.rs` (lines 1-100 of ~300, confirming
generic server-bootstrap role, consistent with Rapid 05's prior conclusion);
`phoenix/crates/common/xai-recsys/src/util.rs` (lines 1-460 of 2017 — `InputBuffer`'s
candidate/history construction, `RetrievalInputBuffer::compute_for_item`);
`phoenix/crates/common/xai-recsys/src/model_config.rs` (full, 297 lines);
`home-mixer/util/phoenix_request.rs` (full, 152 lines);
`home-mixer/scorers/phoenix_scorer.rs` (full, 123 lines);
`home-mixer/sources/phoenix_source.rs` (lines 1-60 of file, cluster resolution — rest
already fully read in Rapid 05);
`phoenix/xrex/inference/launch_inference.py` (lines 280-520 of ~600 — argument parsing
and runner construction; not the full file);
`phoenix/xrex/inference/model_runner.py` (lines 4243-4650 of 4879 — the full
`RetrievalModelRunner` class through `reply_request`'s start; the much larger
`RankingModelRunner`/`BaseModelRunner` classes earlier in the file were not read this
pass, only grepped for structural landmarks);
`phoenix/xrex/models/recsys_two_tower_model.py` (lines 1-1382 of 1761 — architecture,
both towers, `compute_retrieval_loss`, and the serving `forward`/`compute_top_k`
function; the file's final ~380 lines, covering additional serving/reply-shaping helpers
after `forward`, were not read);
`phoenix/xrex/configs/xrecsys_two_tower.py` (lines 225-365 of 752 — dataset config,
shipped base config, and the start of `MODEL_CFGS`; remaining config variants not read).

**Targeted-read** (specific grep-located sections, not surrounding context):
`phoenix/crates/serving/xai-recsys-engine/src/request_metrics.rs` (lines 140-165, metric
docstrings corroborating the `candidate_seq_len` truncation semantics independently
derived from code); `home-mixer/models/query.rs` and
`home-mixer/query_hydrators/impression_bloom_filter_query_hydrator.rs` (confirming the
*impression* bloom filter is a distinct mechanism from `RetrieveTopKCandidatesRequest`'s
`eligible_posts_bloom_filter`).

**Searched-only** (grep/find, no file content read beyond match lines): repo-wide greps
for `PredictNextActions`/`RetrieveTopKCandidates`, `candidate_seq_len`,
`eligible_posts_bloom_filter`/`bloom_filter`, `faiss`/`scann`/`ann_search`/`top_k_search`,
`top_k_by_key`; `find` over `phoenix/crates/serving/xai-recsys-engine`,
`xai-recsys-server`, and `phoenix/xrex/cuda/top_k_by_key`.

## Final closure assessment

**MAYBE.** After this pass, the two specifically-assigned blind spots are closed as far
as this snapshot allows — the remaining gaps in both (live `candidate_seq_len` value;
the offline embedding-population job) are external-configuration/external-artifact
boundaries of the same kind this entire rapid+forensic track has repeatedly hit and
correctly declined to guess past, not unexplored code. Three items remain that are
*plausibly* answerable from checked-in code and were explicitly out of this pass's
assigned scope (per the task's stop condition, not investigated here):

1. **`BaseModelRunner`/`RankingModelRunner`'s full body in `model_runner.py`** (this pass
   read only `RetrievalModelRunner`, ~630 of the file's 4879 lines) — could show
   additional ranking-side batching/serving mechanics not visible from the Rust engine
   crate alone.
2. **The rest of `recsys_two_tower_model.py`** (lines 1383-1761, ~380 lines this pass did
   not read) — could contain additional serving-reply-shaping logic relevant to exactly
   how top-k results become the `ScoredCandidates` response.
3. **Whether any deployment/launch script or CI config in this repository names a
   concrete `--candidate_seq_len`/`--config_name`/`--checkpoint_path` invocation** beyond
   the generic argparse defaults and `QUICKSTART.md`'s toy example — not searched for in
   this pass beyond what Rapid 05 already covered.
