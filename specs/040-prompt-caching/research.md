# Phase 0 Research: Anthropic Prompt Caching

## Decision 1 — Breakpoint placement: stable prefix only (tools + the first message)

- **Decision**: When caching is enabled, attach `cache_control: {"type":
  "ephemeral"}` to exactly two stable boundaries:
  1. the **last tool definition** in the `tools` list (when tools are present) —
     the end of the tools segment, which renders first and is fixed across turns;
  2. the **last content block of the first message** (`messages[0]`) — but only
     when there are **two or more** messages, so the marked block is strictly
     *before* the rolling last message.
  Never mark the rolling last message. At most 2 breakpoints (well under the
  Anthropic max of 4).
- **Rationale**: Anthropic caching is a **prefix match** — the cache key is the
  exact rendered bytes up to each breakpoint, in render order `tools → system →
  messages`. A breakpoint only pays off if the bytes *before* it are identical on
  the next request; a breakpoint that moves every turn caches nothing and wastes
  a ~1.25x write. In LoopPlane's Anthropic request the stable bytes are: the tool
  set (frozen for the run) and the **first message** (the leading
  instructions/first user turn, which never changes as the conversation grows —
  new turns are appended after it). LoopPlane assembles the system prompt as the
  leading message via `build_messages` (there is no top-level `system` key in the
  request — confirmed in `adapter.py`), so the first-message breakpoint *is* the
  system/instructions stable boundary. The growing tail (latest user/assistant/
  tool-result turns) is deliberately left unmarked. Earlier breakpoints remain
  valid read points as the conversation grows, so cache hits accrue every turn.
- **Why the first message, not "a longer stable history prefix"**: the brief
  permits up to a stable history prefix, but only `messages[0]` is *provably*
  stable turn-over-turn without tracking conversation identity inside a
  stateless mapping. Marking a deeper, supposedly-stable index risks landing on
  the rolling tail in short conversations. The first message is the safe,
  never-moving choice and already captures the bulk of the repeated prefix
  (instructions + first turn). It is gated on `len(messages) >= 2` precisely so
  it is never the rolling last message.
- **Why explicit block-level placement, not top-level auto-caching**: the API's
  top-level `cache_control` on `messages.create()` auto-places on the *last*
  cacheable block — which, in an agent loop, is the rolling tail. That would
  re-write the cache every turn and read nothing. Explicit block-level placement
  puts the breakpoint provably on the stable prefix.
- **4-breakpoint rule**: honored trivially — at most 2 are emitted (tools + first
  message). The helper has no path that adds more.
- **Below-minimum prefixes**: Opus 4.x requires ~4096 tokens before a prefix
  caches; shorter prefixes silently don't cache (no error, `cache_read_input_
  tokens` stays 0). The breakpoint is harmless in that case; correctness is
  unaffected. (Re-derived for LoopPlane from the Anthropic prompt-caching
  reference — Constitution IX.)

## Decision 2 — Default on/off: default **True** (caching on), off path byte-identical

- **Decision**: `AnthropicConfig.prompt_caching` defaults to **`True`**.
- **Rationale**: Caching is a near-pure win for the repeated-turn agent-loop
  shape — a cache read is ~0.1x input price and a write ~1.25x, so two turns
  sharing a prefix already break even, and an agent loop re-sends the prefix on
  every turn. Defaulting on delivers the cost savings without the embedder having
  to opt in.
- **Why default-on is safe here (no existing test needed updating)**: the only
  exact-shape assertions in the suite are in `tests/unit/test_anthropic_
  mapping.py`, and they assert on `build_messages(...)` / `build_tools(...)`
  **directly** — which this unit keeps byte-identical (the breakpoints are
  applied by a *separate* opt-in overlay, never inside those two functions). The
  integration suites (`test_us2/us3/us4`, `test_webapi_multimodal`) build the
  Anthropic model with the **default** config but assert only on the normalized
  increments and `TokenUsage`, never on the request `kwargs` shape — so turning
  caching on by default does not change any assertion they make. The
  provider-stub `message_start` carries `cache_read_input_tokens=0`, which the
  decoder maps unchanged. Therefore default-on requires **no edit to any existing
  test**; the new caching tests are purely additive. (The off path is proven
  byte-identical by a dedicated new test, satisfying Constitution X.)
- **Alternatives considered**: default **False** (rejected — would forgo the
  savings by default and contradict "near-pure win"; only justified if an
  existing shape assertion forced it, which it does not). Putting the toggle on
  the runtime core / `RuntimeConfig` (rejected — caching is a per-adapter request
  detail; it belongs on `AnthropicConfig` alongside `accepts_media` /
  `max_output_tokens`, not in the runtime core, per the brief).

## Decision 3 — Apply as a pure overlay, not inside `build_messages` / `build_tools`

- **Decision**: Add `apply_prompt_caching(messages, tools)` to
  `anthropic/mapping.py` that returns *new* lists with `cache_control` attached;
  leave `build_messages` / `build_tools` unchanged. The adapter calls the overlay
  only when `config.prompt_caching` is `True`.
- **Rationale**: Keeps the existing mapping output byte-identical (FR-006), so
  the unit-020 mapping tests stay green untouched and the off path is literally
  "don't call the overlay." The overlay copies (does not mutate in place) the
  block/tool dicts it marks, so a future caller that reuses the un-marked output
  is unaffected.
- **Alternatives considered**: threading a `cache` flag through `build_messages`/
  `build_tools` (rejected — changes their public signature and forces the
  unit-020 tests to special-case the flag for no benefit).

## Decision 4 — OpenAI / OpenRouter / Ollama: confirmed automatic, no request change

- **Confirmation**: The OpenAI adapter sends **no** cache parameter — `adapter.py`
  builds `kwargs` with `model`, `messages`, `stream`, `stream_options`, optional
  `tools`, optional `max_tokens`; nothing cache-related. OpenAI caches
  automatically server-side. The existing `OpenAIStreamDecoder._apply_usage`
  already reads `usage.prompt_tokens_details.cached_tokens` and feeds it to
  `TokenUsage.cached_tokens` (`mapping.py`). OpenRouter and Ollama reuse this same
  `OpenAIModel` + mapping unchanged (unit 035), so they inherit the same
  passive-caching behavior. **No OpenAI-family request change is made by this
  unit** — it only confirms and documents the existing behavior, and a new test
  asserts the `cached_tokens` mapping from a stub usage chunk. (Gemini's implicit
  caching is likewise provider-managed and out of scope here.)

## Decision 5 — Offline-only tests; live cache-savings is opt-in

- **Decision**: All new tests are deterministic and offline — they assert
  `cache_control` placement on assembled dicts, byte-identity for the off path,
  and the OpenAI `cached_tokens` mapping from a stub chunk. No live calls.
- **Rationale**: Matches the 020/035/037 posture (offline stubs; opt-in
  secret-gated live checks). A real cache-savings observation (watching
  `cache_read_input_tokens` rise across two identical-prefix turns) is documented
  as an opt-in note in `docs/real-model-validation.md` §5 alongside the existing
  per-provider live checks — it is not run in the default gates.
