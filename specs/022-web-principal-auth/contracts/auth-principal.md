# Contract: Principal authentication boundary

The web/API auth boundary, now **identity-bearing** (unit 011 evolved). Pluggable,
fail-safe, default-deny — unchanged posture, plus a principal.

## Surface

```python
@dataclass(frozen=True)
class Principal:
    id: str

Authenticator = Callable[[str | None], Awaitable[Principal | None]]   # CHANGED from -> bool
DENY_ALL: Authenticator                                               # returns None
def token_authenticator(tokens: Mapping[str, str]) -> Authenticator   # reference verifier
def make_auth_dependency(auth: Authenticator) -> Callable[..., Awaitable[Principal]]
```

## Obligations

1. **Identity (FR-001/FR-002)**: a successful verify yields a `Principal` with an opaque
   `id`; the route receives it via `Depends`. No roles/permissions are defined here.
2. **Default-deny + fail-safe (FR-003)**: absent an injected authenticator every request
   is denied; a verifier returning `None` **or raising** denies; denial is a fixed `401`
   whose body never contains the credential.
3. **No credential store (FR-004)**: the host persists no credentials. `token_authenticator`
   maps an injected `{token: principal_id}` and accepts only `Bearer <token>`; everything
   else → `None`. Embedders may inject any verifier.
4. **No leak (FR-009)**: neither the `401` nor any other response/error echoes the
   credential or the principal token.

## Breaking change

The return type changes from `bool` to `Principal | None`. This is a **breaking change to
the unit-011 web/API auth surface** (not the 001/002 runtime contracts); recorded in the
changelog. Embedders with a boolean verifier must return a `Principal`/`None`.

## Test matrix

| Case | Expected |
|---|---|
| no authenticator | every route `401` |
| `Bearer good` (mapped) | admitted; route sees `Principal(id=...)` |
| `Bearer bad` / missing / non-bearer | `401`, credential not echoed |
| verifier raises | `401` (fail-safe) |
