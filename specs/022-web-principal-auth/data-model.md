# Data Model: Web Principal Authentication & Per-Principal Session Scoping (unit 022)

## `Principal` — `webapi/auth.py`

```python
@dataclass(frozen=True)
class Principal:
    id: str
```

An authenticated caller's identity; the unit of ownership. Opaque `id`; **no roles or
permissions** in this unit.

## `Authenticator` (changed) — `webapi/auth.py`

```python
Authenticator = Callable[[str | None], Awaitable[Principal | None]]   # was -> bool
DENY_ALL: Authenticator        # returns None (deny every request)
```

A verifier over the request credential (the authorization header value): a `Principal`
admits, `None` denies, a raised exception denies. The web/API ships no credential store.

### Reference verifier

```python
def token_authenticator(tokens: Mapping[str, str]) -> Authenticator:
    """Bearer <token> -> Principal(id=tokens[token]); unknown/missing -> None.
    Dev/demo/tests only; real deployments inject their own."""
```

### Dependency (changed)

```python
def make_auth_dependency(auth: Authenticator) -> Callable[..., Awaitable[Principal]]
# resolves a Principal; raises 401 (fixed detail, no credential) on None/raise.
# Injected per route:  principal: Principal = Depends(require)
```

## `SessionEntry.owner` (added) — `webapi/sessions.py`

```python
@dataclass
class SessionEntry:
    session: Session
    events: MemoryObjectReceiveStream[str]
    close: anyio.Event
    owner: str                 # NEW — the principal id that opened it
```

`run_session(...)` records `owner` and passes `principal_id=owner` into `host.session(...)`
so the live session's durable metadata also carries the owner.

## `principal_id` metadata field (added, optional, default `None`)

Threaded additively so behavior is unchanged when unset:

| Location | Change |
|---|---|
| `checkpoint/records.py` `SessionMetaPayload` | `principal_id: str \| None = None` |
| `checkpoint/base.py` `SessionSummary` | `principal_id: str \| None = None` |
| `checkpoint/file.py` `list_sessions` | populate `principal_id=meta.payload.principal_id` |
| `checkpoint/sqlite.py` `list_sessions` | populate `principal_id=meta.payload.principal_id` |
| `checkpoint/recorder.py` `SessionRecorder` | `principal_id` param → written into `SessionMetaPayload` |
| `controller/controller.py` `_Session`, `create_session`, `_assemble` | `principal_id: str \| None = None` → recorder + the in-memory `list_sessions` summary |
| `host/host.py` `run`, `session` | `principal_id: str \| None = None` → `controller.create_session(principal_id=...)` |

`controller.resume` is **not** changed (the durable meta already carries the owner; the
web/API gates resume by the listed owner).

## Web/API ownership enforcement — `webapi/app.py`

| Operation | Scoping rule |
|---|---|
| `POST /sessions` (open) | tag `SessionEntry.owner = principal.id`; pass `principal_id` to `host.session` |
| `GET /sessions` (list) | return only summaries where `summary.principal_id == principal.id` |
| interactive routes (events/submit/approvals/questions/cancel) | live `_require`: entry missing **or** `entry.owner != principal.id` → **404** |
| durable routes (history/resume/artifacts) | owner from `host.list_sessions()[…].principal_id`; not owned → **404** |

## Public surface — `webapi/__init__.py`

`__all__` gains `Principal` and `token_authenticator`; `docs/api-reference.md` webapi
section matches (unit-014 drift). The `Authenticator` return-type change is recorded in
`CHANGELOG.md` as a breaking change to the 011 surface.
