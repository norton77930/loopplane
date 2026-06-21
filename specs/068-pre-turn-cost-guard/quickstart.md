# Quickstart: Pre-Turn Cost Guard Validation

## Prerequisites

- Python environment managed by `uv`
- Existing LoopPlane test dependencies installed

## Focused Validation

Run the new focused tests after implementation:

```powershell
uv run pytest -q tests/unit/test_pre_turn_cost_guard.py
```

Expected outcomes:

- An estimated over-budget turn terminates with `budget-exceeded` before the model is called.
- An estimate equal to or below remaining budget allows the model call.
- Missing pricing, model id, max-output estimate, or usable request estimate fails open.
- Default-off behavior performs no pre-turn estimate or denial.

## Regression Validation

Run the existing budget and cost-surfacing coverage:

```powershell
uv run pytest -q tests/unit/test_budget_caps.py tests/unit/test_cost_surfacing.py
```

Expected outcomes:

- Existing post-turn `BudgetChecker.record_turn` behavior is unchanged.
- `budget-exceeded` remains the only budget termination reason.
- Read-only session cost surfacing still reflects actual recorded spend only.

## Full Gate

Before final review:

```powershell
uv run ruff check
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q
```

The final board validation also requires `git diff --check`, `openspec/` scan, and public-safety
scan.
