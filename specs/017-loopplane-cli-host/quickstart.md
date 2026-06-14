# Quickstart: The `loopplane` CLI

After `pip install loopplane`, a `loopplane` command is on your PATH.

## One-shot run (credential-free)

```sh
loopplane run "summarize the plan"
```

Prints the agent's response from the normalized event stream and a final outcome
line, then exits 0. With no provider configured it uses the built-in scripted demo
model — no API key, no network.

## Interactive chat

```sh
loopplane chat
> hello
... rendered response ...
> quit
```

Reads a prompt, runs it, renders the streamed output, repeats. EOF or `quit` ends the
session cleanly; Ctrl-C cancels without a traceback.

## Sessions

```sh
loopplane sessions            # list durable sessions (when a store is configured)
loopplane resume <id>         # continue a prior session
```

## Use a real model

Point the CLI at an importable `ModelBoundary` builder and set your credentials in the
environment:

```sh
export LOOPPLANE_MODEL="my_providers:build_anthropic"
export ANTHROPIC_API_KEY="..."     # read by your builder, never by the CLI
loopplane run "hello"
```

With no `LOOPPLANE_MODEL` (or a bad reference) the CLI falls back to the scripted demo
— it never prints or echoes a credential.

## Driving the core programmatically

The CLI's core is importable and credential-free; see
[`examples/cli_quickstart.py`](../examples/cli_quickstart.py).
