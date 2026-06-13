# Contract: Human Approval

**Feature**: [../spec.md](../spec.md) | **Requirements**: FR-110–FR-116, FR-023, FR-055 |
**Date**: 2026-06-13

The policy boundary every tool execution crosses, and the machinery for structured human
interaction.

## Policy decision (FR-110)

Before executing **any** call, the Tool Gateway obtains a decision: **allow**, **deny**, or
**ask**. Decision sources are consulted in deterministic order:

1. **Autonomous-invocation gate** — a skill whose execution profile forbids autonomous
   invocation refuses a model-initiated call outright (FR-055). This is capability gating,
   not a permission: no rule, session memory, or reviewer decision overrides it;
2. **Session approval memory** — a session-scoped decision previously made for this tool in
   this session (FR-113);
3. **Skill approval requirement** — a skill whose profile requires approval forces at least
   an "ask" (FR-055); a persistent allow rule never satisfies it — only an explicit human
   decision does (a remembered session-scoped approval above, or the reviewer below);
4. **Persistent permission rules** — matched per the precedence below (FR-114);
5. **Reviewer escalation** — an "ask" goes to the human reviewer (below); if no reviewer
   channel is attached, "ask" resolves as **deny** with reason "no reviewer available".

## Denial semantics (FR-111)

A denial produces an error-marked Tool Result with category `policy-denial` carrying the
denial reason (a default reason is supplied when none is given). The result returns to the
model and **the run continues**. Policy denials are never counted as execution failures
(FR-104).

## Ask escalation (FR-112)

- An "ask" emits an `approval-requested` event with a unique `request_id`, the call and
  tool identity, and an input summary.
- The call **holds** until a matching `approval-decision` arrives or the reviewer channel
  closes.
- The resolution is emitted as `approval-resolved` with its source (reviewer, rule,
  session-memory, disconnect) for auditability (SC-005).

## Decision scopes (FR-113)

| Scope | Effect |
|---|---|
| once | Applies to this call only |
| session | Remembered in session approval memory; the same tool is not re-asked for the remainder of the session |

## Persistent rules (FR-114)

Permission Rules ([../data-model.md](../data-model.md)) match by tool-name pattern with
deterministic precedence:

1. a more local scope overrides a broader scope (session-local > project > user);
2. within one scope, **deny overrides allow**;
3. no matching rule → fall through to the next decision source.

## Disconnect (FR-115)

If the reviewer channel closes while requests are pending, **all** pending requests resolve
as denied (resolution source `disconnect`), in-flight work cancels cleanly, and nothing
hangs (see [run-lifecycle.md](./run-lifecycle.md) disconnect semantics).

## Non-permission questions (FR-116)

Structured questions from the agent to the user (`question-asked` / `question-answer`) use
the **same** request/response matching machinery — unique `request_id`, exactly-one
resolution, disconnect cancels pending questions — but carry no policy effect.
