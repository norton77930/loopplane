# Contract: Event Replay Store

## Purpose

The Event Replay Store is a web/API transport replay boundary for session SSE frames. It stores
already-serialized public runtime event frames so a reconnecting client can catch up from a
`Last-Event-ID` sequence without changing runtime event contracts.

## Protocol

```python
@dataclass(frozen=True)
class EventReplayRecord:
    session_id: str
    sequence: int
    principal_id: str
    frame: str
    recorded_at: datetime


class EventReplayStore(Protocol):
    async def append(self, record: EventReplayRecord) -> None: ...

    def load_after(
        self,
        session_id: str,
        principal_id: str,
        sequence: int,
        *,
        limit: int,
    ) -> tuple[list[EventReplayRecord], list[str]]: ...

    def delete_session(self, session_id: str) -> None: ...
```

## Required Behavior

| Scenario | Expected behavior |
| -------- | ----------------- |
| Append then load | `load_after(session, owner, n)` returns only records with sequence greater than `n`, sorted ascending. |
| Owner mismatch | `load_after(session, other_owner, n)` returns no records and no private detail. |
| Unknown session | Returns `([], [])`. |
| Duplicate sequence | Backend preserves one record per `(session_id, sequence)` and does not return duplicates. |
| Retention exceeded | Backend retains only the configured newest window per session. |
| Corrupt stored entry | Skips the entry and returns a public-safe problem string. |
| Delete session | Removes replay records for that session; repeated deletes are harmless. |
| Missing optional dependency | Postgres backend construction raises a clear public-safe error naming the optional extra. |

## Web/API Reconnect Contract

| Scenario | Expected behavior |
| -------- | ----------------- |
| No durable store configured | Unit 058 behavior is unchanged. |
| Valid `Last-Event-ID` with durable store | Replays durable records after that sequence, then continues live or store-polled tailing. |
| Malformed `Last-Event-ID` | Starts live or retained-window replay without crashing. |
| Replay/live overlap | Emits each sequence at most once. |
| Non-owner session | Existing 404 scoping applies before any replay-store read. |
| Store append failure | Live stream continues; diagnostics stay public-safe. |
| Store read failure | Durable replay is skipped or degraded safely; no raw backend detail is exposed. |

## Non-Goals

- No new runtime event type or schema version.
- No replacement for the Runtime Event Bus.
- No frontend-specific event format.
- No distributed pub/sub or database notification requirement.
- No one-shot run-stream reconnect support.
