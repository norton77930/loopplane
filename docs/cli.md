# The `loopplane` CLI

`loopplane.cli` (unit 017) is a thin terminal host over the public Host Application
Interface. After `pip install loopplane` the `loopplane` command runs the agent from
your shell, rendering each run from the **normalized event stream**. It is
**credential-free by default** (a built-in demo model, no network), executes no tool
itself, and is additive — installing without invoking it changes nothing.

## Commands

```sh
loopplane run "summarize the plan"   # one-shot: render the response + outcome, exit
loopplane chat                       # interactive: prompt -> run -> render, repeat
loopplane --store ./sessions sessions   # list durable sessions
loopplane --store ./sessions resume <id> # resume a durable session
loopplane --help
```

`chat` ends on EOF or `quit`; Ctrl-C cancels without a traceback. `run` exits 0 on
success, 2 on a usage error.

## Rendering

The CLI prints only public-safe metadata and assistant text: assistant output, a
`[tool <name>] <outcome>` marker (never raw tool I/O), and a final
`[run <reason>, <n> turn(s)]`. No secret, private path, or raw exception appears.

## Using a real model

By default the CLI uses a built-in demo model that runs offline. To use a real model,
point `LOOPPLANE_MODEL` at an importable `module:function` that builds a
`loopplane.model.ModelBoundary`, and keep your credentials in the environment (read by
your builder, never by the CLI):

```sh
export LOOPPLANE_MODEL="my_providers:build_anthropic"
export ANTHROPIC_API_KEY="..."
loopplane run "hello"
```

With no `LOOPPLANE_MODEL`, or a bad reference, the CLI falls back to the demo model —
it never prints or echoes a credential.

## Programmatic core

The CLI's core (`run_once`, `chat_loop`, `EventRenderer`, `select_model`, `dispatch`)
is importable and credential-free; see
[`examples/cli_quickstart.py`](../examples/cli_quickstart.py).
