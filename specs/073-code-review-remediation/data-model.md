# Data Model: Code Review Remediation

## ReviewFinding

Represents one finding from `docs/code-review-001-072.md`.

- `id`: stable finding id such as `P0-1`
- `priority`: P0, P1, P2, or P3
- `surface`: affected area, for example CI, desktop, MCP adapter, web fetch, or
  Spec Kit audit
- `evidence`: command output or file references from the review
- `acceptance_evidence`: test or verification command that proves closure
- `status`: planned, in-progress, fixed, verified, or deferred-with-rationale

## ModelVisibleError

Represents error text that may be returned to a user or model.

- `surface`: MCP tool call, MCP resource read, web fetch validation, web fetch
  timeout, web fetch transport, or web fetch status
- `safe_message`: stable public-safe message
- `disallowed_content`: raw exception messages, tracebacks, full URLs with
  query strings, credentials, tokens, keys, signed URLs, private paths

## WebFetchContentBound

Represents adapter-level response bounding before cache/output.

- `max_content_chars`: maximum retained text content for a fetch result
- `was_truncated`: whether adapter-level truncation happened
- `cached_content`: bounded content only
- `display_url`: public-safe URL representation with no query secret exposure

## SpecTaskAuditException

Represents a durable public-safe exception for historical task drift.

- `feature`: feature directory, for example `015-loopplane-hook-system`
- `reason`: why unchecked historical task boxes are not treated as current
  incomplete work
- `evidence`: reference to board milestone, commit history, or explicit review
  report section
- `scope`: historical-only or current-blocking

## GateResult

Represents a final-review command outcome.

- `command`: exact command run
- `result`: pass, fail, skipped, or warning
- `notes`: concise public-safe explanation
- `finding_ids`: review findings addressed by the gate
