# Quickstart / Validation Guide: CLI and Remote Parity (079)

How to prove this unit works end to end. Each scenario maps to a user story in
[spec.md](./spec.md); the interfaces are in [contracts/](./contracts).

## Prerequisites

```powershell
uv sync --locked
```

The terminal host runs credential-free against a built-in demo model, so scenarios 1–4 need
no network and no API key. Scenario 5 needs the `net` extra's `httpx`, which the dev
dependency group already installs.

## Gates

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy                      # bare — passing paths makes it report falsely
uv run pytest -q                 # 60s per-test timeout
```

Targeted, while iterating:

```powershell
uv run pytest tests/unit/test_commands.py tests/unit/test_cli_*.py -q
uv run pytest tests/integration/test_cli_us*.py tests/integration/test_cli_boundary.py -q
uv run pytest tests/integration/test_cli_remote*.py -q
```

Do not run the full suite concurrently with multi-agent work — `test_examples_smoke.py`
times out under load.

## Scenario 1 — a conversation that remembers (US1)

```powershell
uv run loopplane chat
```

```
> my favourite colour is teal
...
> what is my favourite colour
...
> quit
```

**Expect**: the second answer reflects the first turn. Both turns belong to one conversation.
Before this unit each line started a new conversation and the second answer could not
know.

With a store, the conversation survives the process:

```powershell
uv run loopplane --store ./sessions chat      # say something, then quit
uv run loopplane --store ./sessions sessions  # note the id
uv run loopplane --store ./sessions resume <id>
```

**Expect**: `resume` drops into an interactive prompt continuing that conversation, not a
one-line report. Without `--store`, `resume` prints a public-safe explanation and exits `1`.

## Scenario 2 — approving a tool from the terminal (US2)

Needs a host whose model requests a gated tool; the integration suite wires one with a
scripted model. By hand, run any configuration where a tool requires approval:

```
> do the thing that needs the tool
[approve] read_file — <input summary>  [y/n/a/never]
> y
...
```

**Expect**: the prompt shows the tool name and the input summary and nothing else — no raw
tool input, no path, no credential. `a` allows every equivalent request for the rest of the
conversation; `never` denies them. An unrecognized answer denies this one request.

A question from the agent prompts the same way and the next line is the answer.

**Expect on abandonment**: press Ctrl-C or type `quit` while a request is pending — the run
does not hang; the pending approval is denied and the pending question cancelled.

## Scenario 3 — interrupting a running turn (US3)

```
> <something that streams for a while>
^C
[interrupted]
> hello again
```

**Expect**: the first turn stops, the prompt returns, and the next line continues the *same*
conversation. Pressing Ctrl-C at an idle prompt still ends the conversation, exactly as
before this unit.

## Scenario 4 — the command surface (US4, US5)

```
> /help
> /sessions
> /permission
> /history
> /cost
> /compact
```

**Expect**: `/help` lists every command available here with a one-line summary. `/sessions`
lists only your own conversations. `/permission` shows the current mode and plan state with
no rule expressions. `/history` shows role and block count per entry, never message text.
An unknown command answers `unknown command: /x` and the conversation continues.

Cross-surface equality: run the same command against the web/API host and compare.

```powershell
curl -X POST http://<host>/v1/commands -H "Authorization: Bearer <token>" `
     -H "Content-Type: application/json" -d '{"command":"/help"}'
```

**Expect**: the same text the terminal printed.

## Scenario 5 — driving a remote agent (US6, US7)

Start a server (any existing `create_app` deployment), then:

```powershell
$env:LOOPPLANE_TOKEN = "<token>"
uv run loopplane remote --url http://<host>
```

```
> hello from the terminal
...
> /cost
...
> /compact
/compact: not available over a remote connection
> quit
```

**Expect**:
- turns stream with the same rendering as the local path;
- an approval or question from the remote agent prompts and is answered in the terminal;
- `/compact` is refused *before* anything is sent to the server;
- the credential never appears in any output, including failures.

Attach to an existing conversation:

```powershell
uv run loopplane remote --url http://<host> --session <id>
```

**Expect**: a conversation you do not own is indistinguishable from one that does not
exist — the same public-safe failure either way.

Interrupt a remote turn with Ctrl-C. **Expect**: the turn stops, the terminal states that
interruption ended the live remote connection, and the conversation is still listed by
`loopplane remote … ` → `/sessions` on a fresh connection.

Reconnection: drop the network mid-turn (stop the server's connection, sleep the machine).
**Expect**: `[reconnecting…]`, then the stream resumes with no repeated and no missing
output. If the conversation ended during the break, a public-safe explanation and a clean
exit. If reconnection keeps failing, it stops after a bounded number of attempts and says so.

## Scenario 6 — nothing regressed without the new surface (FR-030, SC-009)

In an environment with no `LOOPPLANE_TOKEN`, no `--url`, and `httpx` uninstalled:

```powershell
uv run loopplane run "hello"
uv run loopplane sessions
uv run loopplane --help
```

**Expect**: identical behavior to before this unit. `loopplane remote --url …` in that same
environment reports what capability is missing, in public-safe terms, and exits `1`.

## Rollback

The unit is one revertable commit. Reverting restores `chat`'s per-turn conversations, drops
the `remote` subcommand, and returns the command registry to four commands with no
classification. No data is written that would outlive the revert: no schema changed, no
record shape changed, no stored setting was introduced.
