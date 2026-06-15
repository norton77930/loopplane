# LoopPlane examples

Most examples are public-safe and run **in-process with the scripted model** — no
provider credentials, no network. Run any one with `python examples/<name>.py`. The two
provider quickstarts (unit 020) are the exception: they drive a **real** model and need a
provider API key in the environment; without one they print a message and exit.

| Example | What it shows |
|---|---|
| `examples/host_quickstart.py` | Embed the runtime through the host interface (unit 002). |
| `examples/run_summary_consumer.py` | A consumer built on the public extension surface only. |
| `examples/loop_quickstart.py` | Define and run one loop via `run_loop` (unit 003). |
| `examples/scheduler_quickstart.py` | The local scheduler and triggers (unit 004). |
| `examples/packs_quickstart.py` | Reusable validators and evaluators (unit 005). |
| `examples/review_quickstart.py` | A human-review workflow (unit 006). |
| `examples/recall_quickstart.py` | Memory recall and a knowledge index (unit 007). |
| `examples/toolkit_quickstart.py` | Tool discovery, registry, and manifests (unit 008). |
| `examples/governance_quickstart.py` | Sandbox, policy, and cost governance (unit 009). |
| `examples/inspect_quickstart.py` | Observability and debug data contracts (unit 010). |
| `examples/webapi_quickstart.py` | The web/API host transport (unit 011). |
| `examples/studio_quickstart.py` | The local desktop/studio host (unit 012). |
| `examples/orchestration_quickstart.py` | Register subagents, coordinate, aggregate (unit 013). |
| `examples/hooks_quickstart.py` | Observe and gate the agent with lifecycle hooks (unit 015). |
| `examples/plugins_quickstart.py` | Discover, enable, and load a manifest-bundle plugin (unit 016). |
| `examples/cli_quickstart.py` | Drive the `loopplane` CLI core programmatically (unit 017). |
| `examples/anthropic_quickstart.py` | Drive a real Claude turn via the Anthropic adapter (unit 020). |
| `examples/openai_quickstart.py` | Drive a real GPT turn via the OpenAI adapter (unit 020). |

New to LoopPlane? Start with [Getting started](../docs/getting-started.md).
