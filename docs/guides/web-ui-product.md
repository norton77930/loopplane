# Web UI product

**Covered units:** 018, 023, 025, 026, 027, 028, 029, 030, 031, 032, 074, 075, 076, 077,
080, 081.

What the bundled single-page app actually gives you, and the rule that shapes all of it:
**the browser never owns enforcement**. This guide is navigational:
[`../capabilities.md`](../capabilities.md) and [`../api-reference.md`](../api-reference.md)
are the authorities — where they disagree with this page, they win.

For how to run and build the app, see [Web frontend](../web-frontend.md); for the API it
speaks to, see [Web / API host](../web-api-host.md) and
[Platform & deployment](platform-and-deployment.md).

## The security posture, stated once

The SPA is a client of the public `/v1` API and nothing more:

- It **never** receives provider credentials, raw permission rules, budget caps or rates,
  private filesystem paths, or MCP resource content.
- It **never** decides whether a tool call is allowed. It can *request* a posture; the host
  decides.
- Everything it shows is a projection the host chose to expose, scoped to the
  authenticated owner.

If a feature below sounds like it moves control into the browser, it does not — read the
sentence after it.

## Conversation surface

| Capability | Unit |
| --- | --- |
| Markdown rendering, collapsible tool cards, theming, two-pane shell, stop control | 025 |
| Reasoning stream, question options, token-usage signals | 026 |
| Model selection and file attachments | 028 |
| i18n, syntax highlighting, command palette, cost estimate | 029 |
| Message actions — copy, regenerate, per-block code copy | 031 |
| Interaction resilience — real modals with focus traps, retry, toasts, skeletons, empty and onboarding states | 032 |

Model selection (028) picks from a host-provided catalog; the browser cannot introduce a
model the host has not registered, and it never carries the provider key.

## Sessions

Session management (030) covers titles, rename, delete, and sidebar grouping, backed by
real persistence rather than local state. Unit 074 extended it with draft sessions, a model
preference, star / fork / search, and bulk delete. Per-message editing and in-session
message search are deliberately **not** shipped
([`../capabilities.md`](../capabilities.md#scope-boundaries-out-of-scope--deferred)).

## Inspection (027)

Read-only panels over the runtime's metadata-only observability: what the agent did, which
tools ran, what the event stream contained. Inspection surfaces *metadata*; it is not a
back door into content the host has not exposed.

## Capability management (075, 076, 081)

Unit 027's read-only inspection became a read-write settings surface over owner-scoped
`/v1/capabilities/*` routes: memory, skills (including import), MCP configuration,
projects/workspaces, schedules, and model defaults.

The hardening that followed is the interesting part:

- **076** — durable, hashed, owner-scoped capability state; shared read-only host
  capabilities; principal-safe runtime activation; managed MCP reconnect; catalog-only
  model defaults; and a **host mutation gate** (`mutations_enabled` /
  `runtime_activation_enabled` default to off, so a deployment opts into browser-driven
  mutation).
- **081** — structurally unsafe browser-managed MCP endpoints are rejected *before*
  persistence; stale principal-scoped adapters retire through existing lease-safe gateway
  primitives; the legacy mutable settings surface was removed.

Net effect: a browser can manage capabilities only where the host has explicitly enabled
it, and only in shapes the host validated first.

## Agent controls (077)

The controls that make the agent's posture visible and, where allowed, adjustable:

- An owner-scoped **execution-posture projection** (safe to render, enum-only where it
  concerns enforcement).
- Optional **one-run permission selection** — host-approved, and `bypassPermissions` is
  never selectable from the browser.
- **Mutable plan state** reported through the existing approval path.
- **Authoritative exact cost** (session and monthly) plus **enum-only budget posture** —
  see [Cost governance](cost-governance.md).
- **Structured bounded non-image upload** handoff, and metadata-only artifact/context
  references.
- **Deterministic localized follow-up suggestions** with zero hidden work — the
  suggestions cost no extra model call.

Explicit deny remains authoritative regardless of what the browser asks for.

## Live channel (074)

A WebSocket live channel carries assistant output, tool progress, approval prompts, and
abort — bidirectionally, with reconnect replay — beside the existing REST + SSE contract.
Backend-owned contract fixtures generate a deterministic `generated.ts`, so the client's
types are derived from the server contract rather than hand-maintained.

## Accessibility and presentation (080)

A presentation-only refactor: a responsive conversation shell, full-page modular settings,
adaptive inspection, local (non-CDN) accessible icons, bilingual chrome, and hardening for
keyboard and focus order, live regions, high zoom, forced colors, and reduced motion. No
backend, dependency, public-contract, or default change.

## Login (023) and the SPA foundation (018)

Unit 018 is the from-scratch SPA over the web/API host; unit 023 adds the token login flow
that establishes the principal every later feature scopes to.

## Where to go next

- [Web frontend](../web-frontend.md) — running, building, and testing the app.
- [Platform & deployment](platform-and-deployment.md) — auth, tenancy, and streaming.
- [Desktop GUI](../desktop-gui.md) — the Electron shell over a local sidecar.
- [`../api-reference.md`](../api-reference.md) — the exact public names and signatures.
