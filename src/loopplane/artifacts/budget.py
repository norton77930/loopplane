"""The aggregate retained-results budget (FR-092): when retained tool
results exceed the budget, the largest eligible results are replaced first
with their preview + reference form. Decisions are frozen: resume restores
them instead of re-deciding.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from loopplane.artifacts.store import ArtifactStore
from loopplane.gateway.sizing import measure_outputs
from loopplane.model.content import OutputBlock

DEFAULT_REPLACEMENT_BUDGET_BYTES = 1024 * 1024  # research A3


@dataclass(frozen=True)
class ReplacementDecision:
    artifact_reference: str
    replaced_call_id: str
    preview: str
    decided_at: datetime


class ReplacementLedger:
    def __init__(
        self, *, budget_bytes: int, store: ArtifactStore, session_id: str
    ) -> None:
        self._budget = budget_bytes
        self._store = store
        self._session_id = session_id
        self._retained: dict[str, tuple[int, list[OutputBlock]]] = {}
        self._replaced: set[str] = set()
        self._decisions: list[ReplacementDecision] = []

    @property
    def decisions(self) -> list[ReplacementDecision]:
        return list(self._decisions)

    def previews(self) -> dict[str, str]:
        """The replaced-call preview map prompt assembly applies."""
        return {
            decision.replaced_call_id: decision.preview for decision in self._decisions
        }

    def is_replaced(self, call_id: str) -> bool:
        return call_id in self._replaced

    def restore(self, decisions: Iterable[ReplacementDecision]) -> None:
        """Resume path: adopt previously recorded decisions verbatim; never
        re-decide (FR-092).
        """
        for decision in decisions:
            self._decisions.append(decision)
            self._replaced.add(decision.replaced_call_id)

    async def track(
        self, call_id: str, outputs: Sequence[OutputBlock]
    ) -> list[ReplacementDecision]:
        """Account for one retained tool result; return any new replacement
        decisions for the caller to record through the checkpoint boundary
        (FR-094).
        """
        self._retained[call_id] = (measure_outputs(list(outputs)), list(outputs))
        new_decisions: list[ReplacementDecision] = []
        while self._retained_total() > self._budget:
            eligible = {
                cid: size
                for cid, (size, _) in self._retained.items()
                if cid not in self._replaced
            }
            if not eligible:
                break
            largest = max(eligible, key=lambda cid: eligible[cid])
            _, blocks = self._retained[largest]
            reference, preview = await self._store.offload(
                session_id=self._session_id, call_id=largest, outputs=blocks
            )
            decision = ReplacementDecision(
                artifact_reference=reference,
                replaced_call_id=largest,
                preview=preview,
                decided_at=datetime.now(UTC),
            )
            self._decisions.append(decision)
            self._replaced.add(largest)
            new_decisions.append(decision)
        return new_decisions

    def _retained_total(self) -> int:
        return sum(
            size
            for call_id, (size, _) in self._retained.items()
            if call_id not in self._replaced
        )
