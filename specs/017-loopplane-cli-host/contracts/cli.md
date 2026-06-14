# Contract: CLI (`loopplane`)

The terminal surface. Credential-free by default; public-safe always.

## Commands

| Command | Behavior | Exit |
|---|---|---|
| `loopplane chat` | Interactive loop: read a prompt, run it, render the streamed output, repeat until EOF/`quit`. | 0 on clean exit |
| `loopplane run "<prompt>"` | Run one prompt, render the response + outcome, exit. | 0 success / 1 unrecoverable |
| `loopplane sessions` | List durable sessions (id + recency, public-safe) when a store is configured; otherwise a clear message. | 0 |
| `loopplane resume <id>` | Resume a durable session and continue. | 0 / clear message if no store |
| `loopplane --help` | Usage for all commands (argparse). | 0 |
| _(missing/invalid args)_ | Public-safe usage message. | 2 |

## Rendering (FR-004, FR-009)

The renderer consumes the normalized event stream and writes, metadata-safe:

- assistant output increments → the text;
- tool activity → `[tool <name>] <outcome>` (name + success/failure only — never raw
  tool input or output);
- termination → `[run <termination_reason>, <turns_taken> turn(s)]`.

No secret, credential, private path, or raw exception ever appears.

## Provider selection (FR-005, FR-006)

`select_model(env)` returns:

- the built-in **scripted demo** model when no provider is configured (no network);
- an imported `ModelBoundary` when `env["LOOPPLANE_MODEL"]` names a `module:function`
  builder and it imports successfully;
- otherwise the scripted demo, with a public-safe note (a bad reference never raises,
  never echoes a credential).

## Guarantees

- The CLI **executes no tool** and re-emits no event bus — it composes only
  `loopplane.host` (FR-008).
- Ctrl-C / EOF end cleanly with no traceback (FR-011).
- Installing the package without invoking `loopplane` changes nothing (FR-010/SC-005).
