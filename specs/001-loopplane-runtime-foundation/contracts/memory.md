# Contract: Memory

**Feature**: [../spec.md](../spec.md) | **Requirements**: FR-070–FR-074 |
**Date**: 2026-06-13

Durable knowledge entries that survive across sessions and reach the model only through
prompt assembly.

## Entry shape

The Memory Entry entity in [../data-model.md](../data-model.md): a declared type, a
required name, a required description (used for relevance selection), and a body. Entries
are stored independently of any single session (FR-070).

## Store operations

| Operation | Semantics |
|---|---|
| scan | Discover entries from the configured location(s); a malformed entry is skipped with a `diagnostic` and never fails the run (FR-071) |
| list | Enumerate valid entries with type/name/description |
| select(prompt) | Return entries ranked by relevance to the prompt — deterministic lexical scoring with stable tie-breaking; on failure or no signal, fall back to deterministic type-priority ordering (FR-072, research A5) |
| write(entry) | Create or update an entry, idempotent by name; resulting state is immediately visible to subsequent scans |

## Injection contract (FR-073)

- Selected entries are injected **only** into the assembled model context for a turn.
- Durable history records the user's input **verbatim** — no injected content, ever.
- Injection participates in prompt assembly alongside skill advertisement; the assembled
  context is reproducible from (history, selected entries, advertised skills) for
  deterministic testing (NFR-001).

## Agent-writable memory (FR-074)

- The runtime ships a memory-write tool — declared name, description, and an input schema
  covering type/name/description/body — registered through the Internal Tool Adapter and
  governed by the full Tool Gateway pipeline ([tool-gateway.md](./tool-gateway.md)),
  including policy decisions.
- There is no privileged write path: the agent updates memory only through this tool.

## Gating

Memory is an optional subsystem: disabled by default, and when disabled the runtime's
behavior is byte-identical to a build with no memory at all (NFR-002, SC-007).
