# Real-Model Validation Procedure

The automated suite runs entirely against the scripted model substitute; at
least one real model integration is validated **manually, outside CI** (spec
Assumptions). This document is that procedure. It is provider-neutral:
any model whose API streams text and tool calls can sit behind the boundary.

Credentials live in environment variables only — never in code, config, or
this repository.

## 1. Implement the model boundary

Write an adapter satisfying `loopplane.model.ModelBoundary`
(contracts/model-boundary.md):

| Boundary obligation | Your adapter maps it from |
|---|---|
| `stream_turn(request)` yields `TextIncrement` | provider streaming text deltas |
| … yields `ReasoningIncrement` | provider reasoning/thinking deltas, when exposed |
| … yields `ToolCallRequest(call_id, tool_name, input)` | provider tool-use blocks; pass the input through raw — the Gateway validates it |
| … ends with `TurnEnd(stop_reason, usage)` | provider stop reason + token usage (input, output, cached, reasoning) |
| `context_capacity()` | the model's context window size |
| raise `ContextOverflowError` | the provider's context-too-long error, so the loop can compact and retry exactly once |
| any other failure | let it propagate; the loop terminates the run as `unrecoverable-error` |

Build the request from `ModelRequest`: `context` is a list of role+blocks
messages (text, tool-call, tool-result, summary-marker blocks), `tools` are
the Gateway-registered descriptors (name, description, JSON Schema).

## 2. Run the validation script

Assemble exactly the quickstart harness (docs/quickstart.md) with your
adapter in place of `ScriptedModel`, the baseline internal tools registered
(`loopplane.tools.InternalToolAdapter`), and a working directory you can
inspect.

## 3. Checklist

Record pass/fail for each scenario. Every assertion below is about the
**normalized event stream**, so a passing run looks identical in shape to
the scripted golden runs.

| # | Scenario | Expected |
|---|---|---|
| 1 | Plain prompt ("say hello") | `user-input` → `assistant-output-increment`(s) → `turn-completed` with non-zero usage → `run-terminated` reason `natural-completion`; history = user + assistant |
| 2 | Tool-using prompt ("read file X and summarize it") | `tool-call-started`/`tool-call-completed` pair between two turns; coherent four-entry history |
| 3 | Unknown tool (prompt the model to call a tool you did not register, or script the request) | error-marked result with category `unknown-tool`; the run continues |
| 4 | Mid-stream cancel (call `controller.cancel(session_id)` while output streams) | run ends promptly with reason `cancelled`, no exception to the caller, partial output retained |
| 5 | Turn budget (create the session with `turn_budget=1` and a tool-hungry prompt) | reason `turn-budget-exhausted` after exactly one turn |
| 6 | (If memory/skills enabled) durable records stay verbatim | the checkpoint `user-input` records contain exactly what was typed — no injected content |

## 4. Record the result

Note the model identifier, date, and checklist outcomes in your validation
log (kept outside this repository if it names internal systems). The
integration is considered validated when scenarios 1–4 pass.

## 5. Per-provider opt-in live checks

The bundled adapters each ship an **opt-in, secret-gated** live smoke test in
`tests/live/test_live_models.py`. Each is skipped unless its provider API key and
an explicit model name are set in the environment, and all are excluded from the
default gates (no `secrets.` reference in CI):

| Provider | Env vars |
|---|---|
| Anthropic | `ANTHROPIC_API_KEY` + `LOOPPLANE_ANTHROPIC_MODEL` |
| OpenAI | `OPENAI_API_KEY` + `LOOPPLANE_OPENAI_MODEL` |
| Gemini (native) | `GEMINI_API_KEY` + `LOOPPLANE_GEMINI_MODEL` |

Run one, e.g.:

```powershell
$env:GEMINI_API_KEY="..."; $env:LOOPPLANE_GEMINI_MODEL="gemini-2.5-flash"; uv run pytest tests/live -q
```
