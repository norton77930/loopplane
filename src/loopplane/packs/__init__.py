"""LoopPlane validator & evaluator packs (feature 005).

Reusable, deterministic, public-safe implementations of the Phase-3 Validator and
Evaluator Protocol contracts. A pack is a pure callable that reads only the
public ``RunOutcome`` / ``LoopState`` surface (through the shared outcome reader)
and returns a Phase-3 ``ValidationResult`` / ``EvaluationResult``. Packs never
start or drive runs and never reach into Phase-1/2/3 internals (FR-040, FR-041).
"""

from loopplane.packs.combinators import all_of, any_of, threshold_gate
from loopplane.packs.evaluators import (
    label_evaluator,
    length_evaluator,
    scoring_evaluator,
)
from loopplane.packs.reader import OutcomeView, read_outcome
from loopplane.packs.validators import (
    PackConfigError,
    TextMode,
    artifact_presence_validator,
    json_schema_validator,
    rule_validator,
    text_validator,
)

__all__ = [
    "OutcomeView",
    "PackConfigError",
    "TextMode",
    "all_of",
    "any_of",
    "artifact_presence_validator",
    "json_schema_validator",
    "label_evaluator",
    "length_evaluator",
    "read_outcome",
    "rule_validator",
    "scoring_evaluator",
    "text_validator",
    "threshold_gate",
]
