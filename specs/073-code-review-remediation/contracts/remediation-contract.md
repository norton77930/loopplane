# Contract: Code Review Remediation

## Final Review Gates

The feature is not verified until the following gates have current evidence:

- `uv sync --locked`
- `uv run ruff check`
- `uv run ruff format --check src tests`
- `uv run mypy src`
- `uv run pytest`
- `npm --prefix apps/web run typecheck`
- `npm --prefix apps/web test`
- `npm --prefix apps/web run build`
- `npm --prefix apps/desktop run typecheck`
- `npm --prefix apps/desktop test`
- `git diff --check`
- changed-file `openspec/` scan
- public-safety scan over changed files

## Public-Safe Error Contract

MCP adapter and web-fetch error outputs must preserve failure class while
omitting sensitive details.

Required properties:

- The output identifies a stable class such as external server call failure,
  external server resource failure, invalid URL, timeout, transport failure, or
  non-success response.
- The output does not include raw exception type names.
- The output does not include raw exception messages.
- The output does not include query strings from input URLs.
- The output does not include token-like, key-like, password-like, signature,
  or credential values injected by tests.

## Web Fetch Bounding Contract

The web-fetch adapter must retain only bounded content.

Required properties:

- Content returned to the Gateway is at most the adapter content cap plus a
  short truncation marker.
- Content stored in the session fetch cache is the same bounded content that is
  returned.
- Within-cap content remains unchanged except for existing metadata formatting.
- Oversized content is deterministic and testable with an injected fetcher.

## Spec Task Audit Contract

Verified feature rows and task checkboxes must be auditable.

Required properties:

- New verified features should have no unchecked task boxes unless an explicit
  exception exists.
- Historical verified features with unchecked tasks must be listed in a durable
  public-safe exception artifact.
- The audit must fail for newly introduced verified/incomplete drift that is
  not covered by the exception artifact.
