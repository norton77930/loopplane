# The `loopplane` CLI

`loopplane.cli` (units 017 and 079) is a thin terminal host over the public Host
Application Interface. After `pip install loopplane` the `loopplane` command runs the
agent from your shell, rendering each run from the **normalized event stream**. It is
**credential-free by default** (a built-in demo model, no network), executes no tool
itself, and is additive — installing without invoking it changes nothing.

## Commands

```sh
loopplane run "summarize the plan"        # one-shot: render the response + outcome, exit
loopplane chat                            # interactive: one continuing conversation
loopplane --store ./sessions sessions     # list durable conversations
loopplane --store ./sessions resume <id>  # pick one up and keep talking
loopplane remote --url https://host       # drive an agent on a remote server
loopplane --help
```

`run` exits 0 on success and 2 on a usage error. `resume` and `remote` exit 1 when
they cannot do their work (no store, unreachable server, rejected credential).

## Interactive conversations

`chat` and `resume` hold **one** conversation: every line you type is a turn in it, so
the agent carries earlier turns forward. `quit`, `exit`, or end of input closes it.

While a turn is running, `Ctrl-C` **cancels that turn** and returns you to the prompt
with the conversation intact. At an idle prompt, `Ctrl-C` ends the conversation, as it
always has.

### Approvals and questions

When the agent asks permission to use a tool, the request appears in the terminal and
your next line answers it:

```
[approve] read_file — <input summary>  [y/n/a/never]
```

| Answer | Meaning |
| --- | --- |
| `y` / `yes` | allow, this request only |
| `n` / `no` | deny, this request only |
| `a` / `always` | allow for the rest of the conversation |
| `never` | deny for the rest of the conversation |
| anything else | deny this request (the safe default) |

A question from the agent shows its text and options; your next line is the answer.
Leaving with a request pending never strands the run — pending approvals deny and
pending questions cancel.

## Commands inside a conversation

A line starting with `/` is answered by the host, never sent to the model. The same
commands behave identically here, in the web/API host, and in the desktop composer,
because all three share one definition.

| Command | What it shows | Available remotely |
| --- | --- | --- |
| `/help` | the commands available where you are | yes |
| `/cost` | this conversation's and this month's spend | yes |
| `/model` | the models the host advertises | yes |
| `/memory [query]` | matching memory entries | yes |
| `/sessions` | your own conversations | yes |
| `/permission` | the current permission and plan posture | yes |
| `/history` | this conversation's shape (role + block count) | yes |
| `/compact` | compact this conversation's history | **no** |

`/compact` is the only command that changes anything, and its effect cannot be
verified from a remote view (history crosses the wire as metadata only), so it is
refused over a remote connection — before anything is sent.

## Driving a remote agent

```sh
export LOOPPLANE_TOKEN="..."
loopplane remote --url https://your-loopplane-host
loopplane remote --url https://your-loopplane-host --session <id>   # attach
```

The terminal becomes a client of an existing LoopPlane web/API host: it opens a
conversation (or attaches to one you already own), streams it, answers its approvals
and questions, and interrupts it — with the same rendering and the same input grammar
as a local conversation.

Three things are worth knowing:

- **Interrupting remotely ends the live connection.** That is the server's existing
  behavior, not something the terminal chooses. The conversation itself survives: it
  stays listed and its history stays available.
- **A dropped stream reconnects on its own**, resuming from the last event you saw, so
  nothing is repeated and nothing is missed. Attempts are spaced and bounded; after a
  few failures it stops and says so. (If the server keeps no replay buffer it sends no
  event ids, and a reconnect then resumes from wherever the server chooses — the
  no-loss guarantee is the server's, and it depends on the server's configuration.)
- **A turn takes as long as it takes.** There is no read deadline on a turn, so a long
  model call will not be mistaken for a lost connection. Connecting still fails fast.

If the server publishes its API under something other than `/v1`, pass the prefix when
building the endpoint programmatically; the `remote` subcommand assumes the default.

The credential comes only from `--token` or `LOOPPLANE_TOKEN`, is held in memory, and
never appears in any output — including failures. Remote operation needs the optional
`net` extra (`pip install "loopplane[net]"`); without it, remote says what is missing
and every other command keeps working.

## Rendering

The CLI prints only public-safe metadata and assistant text: assistant output, a
`[tool <name>] <outcome>` marker (never raw tool I/O), approval and question prompts
carrying only what you need to decide, and a final `[run <reason>, <n> turn(s)]`. No
secret, private path, or raw exception appears — on either the local or the remote
path.

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

The CLI's core (`run_once`, `chat_loop`, `resume_loop`, `remote_loop`, `EventRenderer`,
`LineSource`, `select_model`, `dispatch`) is importable and credential-free; see
[`examples/cli_quickstart.py`](../examples/cli_quickstart.py).
