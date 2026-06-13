# Contract: Policy Integration & the Layer Boundary

The governance layer decides allow/deny **at the gateway's policy seam**; the gateway keeps execution
(Constitution V), the Phase-1 engine keeps rule precedence, and the Phase-1 Human Approval boundary keeps
interactive approval.

## Integration seam (FR-001, FR-080)

```python
# A host plugs a composed governance decider into the gateway's decide stage:
gateway = ToolGateway(decide=sandbox_profile(permission=..., path=..., budget=...))
```

- The layer only **produces** `PolicyDecider`s; the gateway **consults** them before executing a tool and
  obeys the verdict (allow ⇒ execute; deny ⇒ block). The layer never calls the gateway, never executes a
  tool, and never starts a run (FR-002, FR-080, NFR-006).

## Boundary (FR-081, NFR-003, NFR-006)

```text
loopplane.governance  ──imports──►  loopplane.approval   (PolicyAllow/Deny/Verdict/Decider,
                                                          PermissionRule/RuleEffect/RuleScope/resolve_rules)
                      ──imports──►  loopplane.model      (ToolCallRequest, ToolDescriptor)
                      ──imports──►  loopplane.context    (RunContext — signature only)
                      ──imports──►  loopplane.events     (EventEmitter — signature only)
                      ──imports──►  (stdlib only otherwise)
```

Prohibited (asserted by the import + no-invoke audit, `test_governance_boundary.py`):

- The layer **never executes or OS-sandboxes a tool**: it returns verdicts only and holds no execution path;
  the audit asserts no `.invoke(` / `.run(` reference and no execution surface (FR-002, FR-080, NFR-006).
- It imports **no** `ToolGateway` implementation, **no** Phase-1 runtime control internal
  (`loopplane.controller`, `loopplane.gateway`), **no** Phase-2 host symbol, and **no** sibling layer
  (`engineering`, `scheduling`, `packs`, `review`, `recall`, `toolkit`) (FR-081, NFR-003).
- It does **not** orchestrate human approval: it imports no `InteractionBroker` / `ApprovalResolution`
  interaction symbol — that stays the Phase-1 Human Approval boundary (FR-082).

Allowed `loopplane.*` import prefixes: `loopplane.approval`, `loopplane.model`, `loopplane.context`,
`loopplane.events`, `loopplane.governance`. Everything else is a boundary violation.

## Non-duplication (FR-082, SC-009)

The layer contains no tool execution, no rule-precedence re-implementation, and no human-approval
orchestration. Rule precedence reuses `resolve_rules`; execution stays the gateway's; interactive approval
stays the Phase-1 Human Approval boundary's. The layer only decides allow/deny.
