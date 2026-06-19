# Phase 0 Research: Configurable Proactive Auto-Compaction

## Seam verification (read before designing)

The brief asked to verify five seams first. Findings:

1. **Existing compaction** — `src/loopplane/loop/compaction.py` `compact_history`
   is **mechanical** (no model call): it builds a `SummaryDigest` (turn count +
   sorted tool names + up to 3 bounded user-intent excerpts) wrapped in a
   `SummaryMarkerBlock`, replacing the history prefix via
   `SessionHistory.replace_prefix`, and never splits a tool call from its result.
   It returns `False` when there is nothing worth compacting. **Reused verbatim.**

2. **Where it is invoked** — two call sites today:
   - **Reactive**: `loop.py` `AgentLoop.run` catches `ContextOverflowError` and
     calls `compact_history(history, keep_last=self._assembler.keep_last)`, then
     retries the turn exactly once (FR-008). Unchanged here.
   - **Proactive (ALREADY EXISTS)**: `assembly.py` `PromptAssembler.assemble`,
     after composing the request, calls `_estimate_tokens(request)` and — when the
     estimate **`> capacity`** (the model's *full* `context_capacity()`) — calls
     `compact_history(...)` and rebuilds once. **This is the seam this unit makes
     configurable.** The brief assumed proactive compaction did not exist; it
     does, but only fires at 100% of capacity. The unit's job is to let it fire at
     a configurable fraction.

3. **Capacity + size estimation (the crux)** — see Decision 2. A reusable size
   estimator **already exists**: `PromptAssembler._estimate_tokens`.

4. **Compaction events** — see Decision 4. Compaction emits **no** runtime event
   today.

5. **Config wiring** — `RuntimeConfig` (`host/config.py`) threads scalar flags
   (`plan_mode`, `allow_network`, `permission_rules`) through `assemble()`
   (`host/assembly.py`) into the `RuntimeController` constructor, which stores them
   and (for assembly-related ones like `assembly_keep_last`) passes them to the
   per-session `PromptAssembler`. The threshold follows the same path.

## Decision 1 — Make the existing proactive trigger configurable (don't add a new one)

- **Decision**: Add `compact_threshold: float | None = None` to
  `PromptAssembler.__init__`. Replace the existing proactive comparison
  `_estimate_tokens(request) > capacity` with
  `_estimate_tokens(request) > self._effective_capacity(capacity)`, where
  `_effective_capacity(capacity)` returns `int(capacity * threshold)` when a
  threshold is set and `capacity` when it is `None`. The rest of the proactive
  block (call `compact_history`, re-establish augmentations, rebuild) is unchanged.
- **Rationale**: The proactive path already exists; the only limitation is that it
  fires at the full capacity (where the model is about to reject anyway). A
  threshold multiplier is the **minimal additive** change: when `None`, the
  effective capacity *is* the full capacity, so the comparison is the exact
  `> capacity` shipped today → **default-off is byte-identical** (FR-002). When
  set, the same compaction simply runs earlier.
- **Why not a separate pre-send method or a loop-level check**: the assembler
  already owns proactive compaction sizing (its module docstring says so) and
  already has both `_estimate_tokens` and the `capacity` argument in hand. Adding
  the check anywhere else (e.g. in `AgentLoop`) would duplicate the estimate and
  the re-establishment logic and blur the assembler's ownership (Constitution IV).
- **Threshold `1.0`** equals the default trigger (`1.0 * capacity == capacity`);
  `(0, 1)` fires earlier; `None` is the explicit "use full capacity" off-state.

## Decision 2 — Size estimation: REUSE the existing `_estimate_tokens` heuristic

- **Decision**: Reuse `PromptAssembler._estimate_tokens` **unchanged** for the
  proactive size estimate. It already implements exactly the heuristic the brief
  proposed as a fallback: for each block in the assembled request, add
  `len(block.text)` for a `TextBlock` and a fixed `_NON_TEXT_BLOCK_COST = 50` for
  any non-text block, then integer-divide the total by `_chars_per_token`
  (default **4**) to approximate a token count.
- **Finding (the crux the brief asked about)**: there is **no exact tokenizer** in
  the runtime, and the gateway/artifacts/recall code does **not** expose a
  reusable token measurement for *assembled context* — the only size measurement
  for context sizing is `_estimate_tokens` itself. (The artifacts/replacement
  ledger measures **bytes** for the output-artifact threshold, a different
  concern; the recall budget is over recall candidates, not the assembled
  request.) So the reusable measurement to use **is** `_estimate_tokens` — it is
  the existing, documented, conservative heuristic, already driving today's
  full-capacity proactive check. No new tokenizer, no new dependency.
- **Rationale**: The estimate only needs to be a **safety-margin trigger**, not an
  exact budget. `chars ÷ 4` is the well-known rough English token ratio; it is
  cheap and pure. Crucially, the **reactive `ContextOverflowError` path remains
  the backstop**: if the heuristic under-counts and the model still overflows, the
  loop compacts and retries once (FR-007). So an approximate estimate is safe by
  construction.
- **Alternatives considered**: importing a provider tokenizer (rejected — pulls a
  dependency into the runtime core for a margin trigger, and would be
  provider-specific; the boundary is a plain `context_capacity()` int with no
  tokenizer); a bytes-based estimate (rejected — `chars ÷ 4` is already the
  in-use, documented choice and changing it would alter today's full-capacity
  trigger, breaking the byte-identity guarantee).

## Decision 3 — Cheap-model summarizer: DEFER to spec 042 (the secondary feature)

- **Decision**: **Do not** implement the cheap-model summarizer in this unit.
  Ship only the configurable threshold over the **mechanical** digest. Document
  the summarizer as a follow-on, **spec 042**.
- **Rationale (chosen conservatively, per the brief)**: a summarizer-model seam
  would put a **model call inside the loop's compaction path** — which today is a
  pure, synchronous, deterministic, offline-testable transform. That call brings
  real complexity and risk: a second `ModelBoundary` dependency, async error
  handling for a failed/slow summarizer (and a fallback to the mechanical digest),
  non-deterministic output that complicates testing, added latency on the
  compaction turn, and new event/observability questions. The brief is explicit:
  include it **only** if it is *cleanly* additive, and otherwise defer it. It is
  not cleanly additive — it changes the character of the compaction path — and the
  mechanical digest already frees space. So it is deferred.
- **Why this is safe to defer**: the threshold and the summarizer are orthogonal.
  Spec 042 can later add an optional `summarizer_model: ModelBoundary | None` that,
  when present, replaces the digest body — without touching the threshold shipped
  here. Nothing in this unit forecloses that.
- **Documented follow-on (spec 042 sketch)**: an optional summarizer
  `ModelBoundary` passed to the controller → the assembler; during compaction,
  when present, summarize the compacted span into the `SummaryMarkerBlock` body
  instead of the mechanical excerpts, with a deterministic mechanical fallback on
  any summarizer error and offline tests using a scripted summarizer. Out of scope
  here.

## Decision 4 — Compaction stays silent: no new event (Constitution VI)

- **Confirmation**: compaction emits **no** runtime event today. The reactive
  path calls `compact_history` and (on the assembler) `mark_compacted`, then
  retries — no `emitter` call. The proactive path in `assemble` likewise only
  mutates history and rebuilds the request. `SessionHistory.replace_prefix`
  deliberately does **not** invoke the recording hook (the durable stream is
  append-only and keeps the originals). A grep of `src/loopplane/events` for
  `compact`/`digest`/`SummaryMarker` finds nothing.
- **Decision**: the proactive path emits **no** event either. No new event type,
  no `SCHEMA_VERSION` bump, no content-model change (Constitution VI; FR-010).
  Adding a "compacted" diagnostic would be a VI contract change and is explicitly
  out of scope (a separate spec if ever wanted).

## Decision 5 — Validation: fail-fast on an invalid threshold

- **Decision**: `validate_config` rejects an `auto_compact_threshold` that is not
  `None` and not a finite number in `(0, 1]` with a public-safe `ConfigError`
  (`0`, negative, `> 1`, `NaN`, `inf`). `from_mapping` coerces the value to
  `float` (or `None`).
- **Rationale**: matches the existing fail-fast posture (`validate_config` already
  rejects duplicate tools, unknown approval references, and an inactive
  observability overlay). A nonsensical threshold should be a clear config error
  at assembly, never a silent no-op or a runtime surprise. `1.0` is **valid** (it
  equals the full-capacity trigger); `0` is **invalid** (it would try to compact
  on every turn down to nothing — bounded by `compact_history` returning `False`,
  but a degenerate and almost-certainly-unintended setting, so rejected).

## Decision 6 — Offline-only tests

- **Decision**: All new tests are deterministic and offline — a scripted model, a
  `RecordingModel` to capture each assembled request, and a `RuntimeController`
  with the threshold set. No live calls.
- **Rationale**: matches the existing compaction/overflow tests
  (`tests/integration/test_us4_memory_skills.py`) and the config-wiring tests
  (`tests/contract/test_host_config.py`). The trigger, the byte-identity, the
  backstop, the effective-capacity math, and the validation are all assertable
  without a real model.
