# Contract: the `loopplane` terminal surface (unit 079)

The CLI's contract is its subcommands, their options, its exit codes, and what it is allowed
to print. Everything below the "after 079" heading is additive except where marked.

## Subcommands

| Invocation | Before 079 | After 079 |
| --- | --- | --- |
| `loopplane run <prompt>` | one-shot run, render, exit | unchanged |
| `loopplane chat` | a new conversation per line | **one continuing conversation**, with approvals, questions, and mid-turn interrupt (behavior change, FR-001) |
| `loopplane sessions` | list durable sessions | unchanged |
| `loopplane resume <id>` | load a durable session and report its size | resumes it **interactively**, continuing the conversation (FR-003) |
| `loopplane remote` | — | **new**: drive a conversation on a remote server |
| `loopplane --help` | usage | usage, including `remote` |

Global option `--store <dir>` keeps its meaning and applies to `chat`, `sessions`, `resume`.

### `loopplane remote`

```
loopplane remote --url <server> [--token <value>] [--session <id>]
```

| Option | Source | Required | Notes |
| --- | --- | --- | --- |
| `--url` | argument | yes | the server root; the client appends the `/v1` prefix |
| `--token` | argument or `LOOPPLANE_TOKEN` | yes | never rendered, never logged, never included in an error |
| `--session` | argument | no | attach to an existing owned conversation; omitted means open a new one |

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | the command completed |
| `1` | the command ran but could not complete its work (unresumable session, unreachable server, rejected credential, missing optional capability) |
| `2` | usage error (no subcommand, missing required option) |

`1` is the existing failure code used by `resume`; `remote` reuses it rather than
introducing new codes.

## Interactive input grammar

Applies to `chat`, interactive `resume`, and `remote` alike.

| Input | Effect |
| --- | --- |
| empty line | ignored |
| `quit` / `exit` | end the conversation and return |
| `/<command> [args]` | dispatched against the shared command surface, never sent to the model |
| anything else | submitted as a turn |

While a permission request is pending, the next line answers it:

| Input | Decision |
| --- | --- |
| `y` / `yes` | allow, this request only |
| `n` / `no` | deny, this request only |
| `a` / `always` | allow, for the rest of the conversation |
| `never` | deny, for the rest of the conversation |
| anything else | deny, this request only (the safe default) |

While a question is pending, the next line is the answer; an empty line answers with an
empty string rather than hanging.

## Interrupt

| Situation | Effect |
| --- | --- |
| idle at the prompt | end the conversation and return (**unchanged** behavior) |
| a turn is running, local | cancel the turn, print `[interrupted]`, return to the prompt with the conversation open |
| a turn is running, remote | cancel the turn; the server ends the live remote session; the terminal reports that and returns (research R8) |
| a permission request is pending | the pending request is denied; nothing is left waiting |

## What the terminal may print

Unchanged from unit 017's rule, extended to the remote path:

- assistant text, verbatim from `assistant-output-increment`
- `[tool <name>] <outcome>` — never raw tool input or output
- `[run <reason>, <n> turn(s)]`
- `[<severity>] <message>` for diagnostics
- approval prompts carrying only `tool_name` and `input_summary`
- question prompts carrying the question text and its options
- `[interrupted]`, `[reconnecting…]`, and public-safe failure lines

It must never print a credential, a private filesystem path, an internal identifier, or raw
exception text — on either the local or the remote path.

## Compatibility

- `run`, `sessions`, and `--store` are byte-identical.
- `chat`'s per-line grammar is unchanged; what changes is that turns now share a
  conversation, and that a pending approval or question consumes the next line.
- With no `LOOPPLANE_TOKEN`, no `--url`, and no optional network capability installed, every
  pre-079 invocation behaves exactly as before (FR-030).
