# Quickstart: Worker Drain Handoff

Two coordinators share one in-memory store. Only the worker that is leaving
starts drain.

```python
from loopplane.webapi.admission import AdmissionCoordinator, InMemoryAdmissionStore

store = InMemoryAdmissionStore()
leaving = AdmissionCoordinator(store, holder_id="old")
replacement = AdmissionCoordinator(store, holder_id="new")
```

1. `leaving` holds the principal and runs the current body.
2. Call `leaving.begin_drain()` during that body. The body still finishes.
3. After the hold exits, `replacement.hold(principal)` succeeds.
4. `leaving.hold(principal)` raises the existing capacity rejection until
   `leaving.end_drain()`.

Confirm drain was never required for the old tests: a coordinator that does not
call `begin_drain` admits as it did in unit 085.

```powershell
uv run pytest tests/unit/test_webapi_admission.py -q --tb=line -k "drain or admission_conflict"
```
