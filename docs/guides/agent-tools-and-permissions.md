# Agent tools & permissions

**Covered units:** 033, 034, 036, 038, 039, 044, 045, 046, 047, 052, 054, 065, 066, 069.

What an agent can *do* in LoopPlane, and how you decide what it is allowed to do. This
guide is navigational: [`../capabilities.md`](../capabilities.md) and
[`../api-reference.md`](../api-reference.md) are the authorities — where they disagree with
this page, they win.

Two rules frame everything below:

- **Every tool call goes through the Tool Gateway.** Resolve → validate → decide → execute
  → normalize → size-manage. Nothing executes a tool outside it, so permission and
  governance have exactly one place to live.
- **Every capability here is additive and off unless you configure it.** An unset option
  leaves behavior byte-identical.

## The tool surface

The gateway-reachable tools are listed in full in
[`../capabilities.md`](../capabilities.md#internal-tools-and-model-providers). Grouped by
what they are for:

| Group | Tools | Unit |
| --- | --- | --- |
| Files | `read_file`, `write_file`, `edit_file`, `search_files`, `glob_files`, `grep` | 033 |
| Shell | `run_command` | core, sandboxable via 052 |
| Web | `web_fetch`, `web_search` | 034, 047 |
| Task state | `todo_write` | 044 |
| Notebooks | `notebook_edit` | 046 |
| Undo | `undo_file` | 054 |
| Interaction | `ask_user`, `exit_plan_mode` | core, 038 |
| Memory | `memory_write` | core |
| Uploads | `read_upload` | web/API host |
| Delegation | `spawn_subagent` | 043 (see the autonomy guide) |

File tools operate inside the run's working scope; `glob_files` and `grep` are read-only,
so they are cheap to allow even under a restrictive policy.

### Web tools and network egress (034, 047)

Network access is **default-deny**. `web_fetch` and `web_search` only work when the host
opts in (`RuntimeConfig.allow_network`) and the network policy admits the target. A
keyless reference search provider ships with the runtime (`ReferenceSearchProvider`, 047)
so `web_search` is usable without signing up for anything; a host may inject its own
`SearchProvider` instead. Fetched responses are size-limited and normalized to readable
text, and failures surface as public-safe errors.

### Sandboxed command execution (052)

`run_command` runs through an injectable `CommandExecutor`. The default is the verbatim
host executor — byte-identical to running the command yourself. Opting into
`LocalJailCommandExecutor` adds POSIX resource limits, an environment scrub, process-group
isolation, and a wall-clock timeout. It is POSIX-only (it raises on Windows).
`DockerCommandExecutor` is the opt-in container path: it needs `loopplane[docker]`,
a local image, and a daemon, and it does not fall back to the host. Network modes
other than none, syscall filters, and sandboxing tools other than `run_command`
stay out of scope; see
[`../capabilities.md`](../capabilities.md#scope-boundaries-out-of-scope--deferred).

### Undo (054)

When file snapshots are enabled, `undo_file` reverts a file to its pre-edit state. It is a
tool the model can call, so a bad edit is recoverable inside the run rather than only by
the human afterwards.

## Multimodal input (036, 069)

Content blocks extend what a turn can carry:

- **Images** (036) — `ImageBlock`, negotiated per provider through `accepts_media()`.
- **Documents / PDF** (069) — `DocumentBlock`, with native Anthropic and Gemini mappings
  (ADR 0011). An adapter without document support **fails before submission** rather than
  silently converting; that failure is the designed behavior, not a gap.

Structured output (045) is likewise a model-boundary capability — negotiated per provider,
not a gateway tool. See [`../model-providers.md`](../model-providers.md).

## Deciding what is allowed

Permission enforcement lives at the gateway's **decide** stage, and it is
**deny-wins**: if any decider says deny, the call is denied.

### Permission rule DSL (039)

A host supplies declarative rules — each one a tool name, an optional field match, and a
decision of `allow` / `deny` / `ask` — plus a default. `ask` reuses the existing approval
path, so a rule can route a specific call to a human without any new plumbing. Rules are
data, so they can come from configuration rather than code.

### Named permission modes (066)

`RuntimeConfig.permission_mode` expands one name into a preset rule set over that same
DSL: `acceptEdits`, `bypassPermissions`, `dontAsk`, `plan`. The default is `None`, which
is byte-identical to having no mode at all. Deny-wins still applies — a mode can never
override an explicit deny.

### Plan mode (038)

Plan mode makes the agent read-only until a human approves a plan: the agent investigates,
calls `exit_plan_mode` with its proposed plan, and only after approval does the mutating
work begin. It is implemented as a decide-stage policy plus one tool, reusing the approval
boundary rather than adding a second control path.

## Slash commands (065)

`/cost`, `/model`, `/memory`, and `/compact` are answered by the **host** — the CLI REPL
intercepts them, and the web host exposes `POST /v1/commands` — without a model round-trip.
They are host UX, deliberately outside the Tool Gateway and the Event Bus: a slash command
is not a tool call and never appears as one.

## Putting it together

A typical governed configuration:

1. Register the tool adapters you want (`InternalToolAdapter`, `WebToolAdapter`, …).
2. Pick a starting posture with `permission_mode`, then narrow it with explicit
   `permission_rules` for the calls you care about.
3. Leave `allow_network` off unless the agent genuinely needs the web.
4. Turn on plan mode for tasks where you want to see the plan before anything is written.
5. Add `LocalJailCommandExecutor` on POSIX hosts if `run_command` is exposed at all.
   `DockerCommandExecutor` is the opt-in alternative when a local image is available.

## Where to go next

- [Sandbox, policy & governance](../sandbox-policy-governance.md) — the decider system
  itself (unit 009).
- [Advanced tool gateway](../tool-gateway-advanced.md) — discovery, catalogs, manifests
  (unit 008).
- [Human review](../human-review.md) — review workflows over the approval boundary.
- [Cost governance](cost-governance.md) — budget caps that also participate in the decide
  stage.
- [`../api-reference.md`](../api-reference.md) — the exact public names and signatures.
