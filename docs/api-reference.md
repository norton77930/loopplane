# LoopPlane API Reference

This reference enumerates LoopPlane's **public surface** — every package that
declares `__all__`, with each public name and a one-line description. It is checked
against the code by `tests/contract/test_api_reference.py`: the documented names
equal each package's `__all__` per package, so this reference cannot silently
drift. Metadata only — names and descriptions, never source or internals.

For task-oriented guides see the [docs index](./README.md); to install and run see
[Getting started](./getting-started.md).

## Runtime foundation (unit 001)

The embeddable agent harness runtime: the model boundary, the conversation model,
normalized events, the agent loop, the runtime controller, the tool gateway,
skills, memory, checkpointing, artifacts, the approval boundary, and observability.

### `loopplane.model`

The model boundary and conversation content model, plus a deterministic scripted
model for offline tests.

- `ModelBoundary` — the model-provider interface the runtime calls.
- `ModelRequest` — a request submitted to the model boundary.
- `ModelIncrement` — one streamed increment from the model.
- `GenerationLimits` — per-generation token and output limits.
- `TokenUsage` — token-usage accounting for a turn.
- `Message` — a conversation message.
- `ContentBlock` — base type for message content blocks.
- `TextBlock` — a text content block.
- `ImageBlock` — an image content block.
- `DocumentBlock` — a document content block for model input.
- `OutputBlock` — an assistant output content block.
- `TextIncrement` — a streamed assistant text increment.
- `ReasoningIncrement` — a streamed assistant reasoning increment.
- `ToolCallBlock` — a tool-call content block, with optional provider metadata.
- `ToolCallRequest` — a requested tool call, with optional provider metadata.
- `ToolResultBlock` — a tool-result content block.
- `ToolDescriptor` — a tool's public descriptor (name and schema).
- `SummaryDigest` — a context-summary digest.
- `SummaryMarkerBlock` — a marker bounding a summarized region.
- `TurnEnd` — the end-of-turn marker.
- `ContextOverflowError` — raised when context capacity is exceeded.
- `ScriptedModel` — a deterministic scripted model for tests.
- `ScriptedTurn` — one scripted turn for `ScriptedModel`.
- `ScriptEntry` — an entry in a model script.
- `ScriptedFailure` — a scripted failure injection.
- `ScriptedOverflow` — a scripted context-overflow injection.
- `accepts_media` — whether a model accepts image input (duck-typed probe).
- `supports_structured_output` — whether a model supports native structured output (duck-typed probe).

### `loopplane.events`

The normalized Runtime Event Bus contract and its serialization (the single event
stream every consumer reads).

- `RuntimeEvent` — base normalized runtime event.
- `EventEmitter` — emits normalized runtime events.
- `EventSequencer` — assigns monotonic event sequence numbers.
- `EventSink` — consumer interface for runtime events.
- `SCHEMA_VERSION` — the runtime-event schema version.
- `TerminationReason` — why a run terminated.
- `serialize_event` — serialize a runtime event (public-safe).
- `deserialize_event` — reconstruct a runtime event from its serialized form.
- `UserInputEvent` — a user-input event.
- `UserInputPayload` — the user-input event payload.
- `AssistantOutputIncrementEvent` — an assistant output increment event.
- `AssistantOutputIncrementPayload` — its payload.
- `AssistantReasoningIncrementEvent` — an assistant reasoning increment event.
- `AssistantReasoningIncrementPayload` — its payload.
- `ToolCallStartedEvent` — a tool-call-started event.
- `ToolCallStartedPayload` — its payload.
- `ToolCallCompletedEvent` — a tool-call-completed event.
- `ToolCallCompletedPayload` — its payload.
- `TurnCompletedEvent` — a turn-completed event.
- `TurnCompletedPayload` — its payload.
- `RunTerminatedEvent` — a run-terminated event.
- `RunTerminatedPayload` — its payload.
- `DiagnosticEvent` — a diagnostic event.
- `DiagnosticPayload` — its payload.
- `ApprovalRequestedEvent` — a human-approval-requested event.
- `ApprovalRequestedPayload` — its payload.
- `ApprovalResolvedEvent` — a human-approval-resolved event.
- `ApprovalResolvedPayload` — its payload.
- `QuestionAskedEvent` — a question-asked event.
- `QuestionAskedPayload` — its payload.
- `QuestionAnsweredEvent` — a question-answered event.
- `QuestionAnsweredPayload` — its payload.
- `Question` — a question posed to a human.
- `ReplayStartedEvent` — an event-replay-started marker.
- `ReplayStartedPayload` — its payload.
- `ReplayCompletedEvent` — an event-replay-completed marker.
- `ReplayCompletedPayload` — its payload.

### `loopplane.loop`

The agent loop and conversation-history assembly.

- `AgentLoop` — the core agent loop.
- `PromptAssembler` — assembles the model prompt for a turn.
- `AugmentationProvider` — supplies prompt augmentations.
- `SessionHistory` — the in-session conversation history.
- `HistoryEntry` — one entry in the session history.
- `compact_history` — compact history within a budget.
- `partition_calls` — partition tool calls from a turn.
- `DEFAULT_KEEP_LAST` — default count of recent entries kept.

### `loopplane.controller`

The runtime controller and dispatcher that drive a session.

- `RuntimeController` — orchestrates a run over the agent loop.
- `Dispatcher` — dispatches consumer requests into the run.
- `SessionState` — the controller's session state.
- `ConsumerRequest` — a request from a consumer to the run.
- `SubmitInput` — submit user input to the run.
- `Cancel` — cancel the run.
- `QuestionAnswer` — answer a pending question.
- `ApprovalDecision` — a human approval decision.
- `BatchingSink` — a sink that batches emitted events.

### `loopplane.gateway`

The Tool Gateway — the single chokepoint that resolves, authorizes, and executes
tools and normalizes their output.

- `ToolGateway` — the tool execution chokepoint.
- `ToolAdapter` — the adapter SPI for a tool source.
- `ToolHandler` — a resolved, callable tool handler.
- `AdapterOutput` — normalized adapter output.
- `ErrorOutput` — a normalized adapter error.
- `PolicyDecider` — the permission decision interface.
- `allow_all` — a permissive default decider.
- `validate_input` — validate a tool call's input.
- `measure_outputs` — measure output size against the limit.
- `reduce_outputs` — reduce/truncate outputs to budget.
- `DEFAULT_CALL_TIMEOUT_SECONDS` — default per-call timeout.
- `DEFAULT_OUTPUT_LIMIT_BYTES` — default output size limit.

### `loopplane.tools`

The internal, web, and subagent-spawn tool adapters.

- `InternalToolAdapter` — the adapter for built-in internal tools.
- `WebToolAdapter` — the adapter for the web tools (web_fetch, web_search).
- `SearchProvider` — the host-injected web-search provider seam.
- `SearchResult` — a single web-search result (title, url, snippet).
- `ReferenceSearchProvider` — a bundled keyless reference web-search provider for `web_search` (spec 047).
- `SpawnSubagentAdapter` — the adapter for the model-driven one-shot `spawn_subagent` tool (depth-capped).
- `BackgroundTasksAdapter` — the adapter for the background-task tools (create/get/list/stop/output; spec 048).
- `BackgroundTaskSupervisor` — the per-run supervisor that owns + tracks background tasks (spec 048).
- `SchedulingToolsAdapter` — the adapter for the scheduling tools (create/get/list/cancel; spec 049).
- `ScheduleSupervisor` — the per-run supervisor that owns + fires scheduled child runs (spec 049).
- `SwarmToolsAdapter` — the adapter for the swarm/messaging tools (dispatch/get/list + message send/inbox; spec 050).
- `SwarmSupervisor` — the per-run supervisor that owns swarm members + their message inboxes (spec 050).
- `WorktreeToolsAdapter` — the adapter for the worktree tools (create/list/remove; spec 051).
- `WorktreeManager` — the per-run manager that owns + cleans up managed git worktrees (spec 051).
- `CommandExecutor` — the injectable seam for executing a run_command shell command (spec 052).
- `CommandResult` — a shell command's outcome (returncode, stdout, stderr; spec 052).
- `HostCommandExecutor` — the default executor: the current host-shell call verbatim (spec 052).
- `LocalJailCommandExecutor` — a POSIX local-subprocess jail (rlimits + env-scrub + confinement; spec 052).

### `loopplane.pricing` (unit 053)

Server-side pricing (gap G21, Phase A): pure token-usage → USD cost from host-supplied
rates. Metadata only — not wired into the runtime; no enforcement (G22 caps deferred).

- `PricingRate` — a model's per-token USD rates (input + output, exact decimals).
- `PricingTable` — a host-supplied model→rate table with a pure usage→USD `cost` (spec 053).

### `loopplane.budget` (units 055, 068)

USD budget enforcement (gap G22, Phase B; ADR 0005): wires 053's pricing into the Agent
Loop to enforce per-message / per-session USD caps. Default-off (no caps → byte-identical);
fail-soft on an unpriced model; a crossing terminates the run `budget-exceeded`.
Unit 068 adds an optional pre-turn estimate using `RuntimeConfig.pre_turn_max_output_tokens`;
when complete pricing, model id, max-output estimate, and a known cap are present, an over-budget
turn can be refused before the model call with the same `budget-exceeded` reason.

- `BudgetPostureSnapshot` — browser-safe enum-only tracking, pricing, and guard posture with no caps, rates, identities, or ledger details (unit 077).
- `UsdBudgetCaps` — the per-message / per-session USD caps (each `None` = that dimension off).
- `BudgetChecker` — the in-loop per-session USD accumulator + cap test, including the optional
  non-mutating pre-turn decision (specs 055 and 068).

### Platform fairness (unit 072)

In-process platform fairness (gap G20 tail; ADR 0013): a host-supplied,
default-off collaborator for tenant-scoped outstanding-work quota and fair
model-turn starts. It is process-local only; distributed fairness and durable
queues are deferred.

- `PlatformFairnessPolicy` — positive local limits for per-tenant outstanding
  work, active model calls, and the consecutive-start fairness window.
- `PlatformFairness` — the in-memory quota admission and model-turn permit gate.
- `PlatformFairnessGate` — the Protocol accepted by `RuntimeConfig.platform_fairness`.
- `PlatformFairnessRejected` — public-safe quota rejection; web/API maps it to
  `capacity exceeded`.

### `loopplane.ledger` (unit 062)

Durable per-user-monthly USD ledger (gap G22, Phase C; ADR 0010): an atomic
per-`(principal_id, month)` USD accumulator. Pure storage — the per-user-monthly cap
enforcement that consumes it lives in `loopplane.budget` (unit 063). Exact `Decimal`; the
`psycopg` import is deferred so the package imports without the `loopplane[postgres]` extra.

- `UsdLedger` — the ledger Protocol (`async add → new total`; sync `get`; keyed by `(principal_id, month)`).
- `FileUsdLedger` — the default JSON-file backend (single-process-honest).
- `SqliteUsdLedger` — a local SQLite backend (single-process-honest).
- `PostgresUsdLedger` — a PostgreSQL backend; the only cross-process-atomic one (`loopplane[postgres]`).

### `loopplane.adapters.mcp`

The MCP tool adapter boundary.

- `MCPToolAdapter` — a Tool Gateway adapter for MCP tool servers.
- `MCPServerConfig` — configuration for an MCP server.
- `translate_schema` — translate an MCP tool schema.
- `merge_layers` — merge MCP capability layers.

### `loopplane.adapters.anthropic`

The Anthropic (Claude) model-provider adapter.

- `AnthropicModel` — a model boundary backed by the Anthropic messages API.
- `AnthropicConfig` — configuration for the Anthropic adapter.

### `loopplane.adapters.openai`

The OpenAI (GPT) model-provider adapter.

- `OpenAIModel` — a model boundary backed by the OpenAI chat-completions API.
- `OpenAIConfig` — configuration for the OpenAI adapter.

### `loopplane.adapters.openai_compat`

OpenAI-compatible model providers (OpenRouter, Ollama) reusing the OpenAI adapter.

- `OPENROUTER_BASE_URL` — the OpenRouter API base URL.
- `OLLAMA_BASE_URL` — the default local Ollama OpenAI-compatible base URL.
- `openrouter_model` — build an `OpenAIModel` pointed at OpenRouter.
- `ollama_model` — build an `OpenAIModel` pointed at a local Ollama endpoint.

### `loopplane.adapters.gemini`

The native Google Gemini model-provider adapter.

- `GeminiModel` — a model boundary backed by the Google GenAI API.
- `GeminiConfig` — configuration for the Gemini adapter.

### `loopplane.skills`

The skill execution profile boundary.

- `Skill` — a declared skill.
- `LoadedSkill` — a loaded, resolved skill.
- `ExecutionProfile` — a skill's execution profile.
- `SkillAdvertiser` — advertises available skills to the model.
- `SkillToolAdapter` — exposes a skill as a gateway tool.
- `load_skills` — load skills from a source.
- `skill_profiles` — resolve skills to execution profiles.
- `substitute` — substitute closed variables in a skill.
- `CLOSED_VARIABLES` — the closed (non-substitutable) variable set.
- `DEFAULT_PROMPT_BUDGET_CHARS` — default skill prompt budget.
- `DEFAULT_SKILL_SIZE_CAP_BYTES` — default skill size cap.

### `loopplane.memory`

The runtime memory store and prompt augmentation.

- `MemorySnapshotAugmentation` — an immutable owner-scoped memory snapshot used for later-session prompt augmentation.
- `MemoryStore` — the memory store interface.
- `MemoryEntry` — a stored memory entry.
- `MemoryAugmentation` — a memory-derived prompt augmentation.
- `select_entries` — select memory entries for a prompt.

### `loopplane.checkpoint`

Durable session recording, checkpoint records, and session rebuild.

- `SessionRecorder` — records a session to durable records.
- `RecordingSink` — an event sink that records to the store.
- `CheckpointStore` — the checkpoint store interface (Protocol).
- `FileCheckpointStore` — the default filesystem checkpoint store.
- `SqliteCheckpointStore` — the optional SQLite checkpoint store.
- `PostgresCheckpointStore` — the optional PostgreSQL checkpoint store (`loopplane[postgres]`).
- `CheckpointRecord` — base checkpoint record.
- `RebuildResult` — the result of rebuilding a session.
- `rebuild_session` — rebuild a session from its records.
- `SessionSummary` — a session's summary.
- `SessionMetaRecord` — a session-metadata record.
- `SessionMetaPayload` — its payload.
- `UserInputRecord` — a user-input record.
- `UserInputRecordPayload` — its payload.
- `AssistantMessageRecord` — an assistant-message record.
- `AssistantMessageRecordPayload` — its payload.
- `ToolResultRecord` — a tool-result record.
- `ToolResultRecordPayload` — its payload.
- `ReplacementDecisionRecord` — an artifact-replacement decision record.
- `ReplacementDecisionRecordPayload` — its payload.
- `TerminationRecord` — a run-termination record.
- `TerminationRecordPayload` — its payload.
- `RECORD_KINDS` — the set of record kinds.
- `RECORD_SCHEMA_VERSION` — the record schema version.
- `serialize_record` — serialize a checkpoint record.
- `deserialize_record` — reconstruct a checkpoint record.

### `loopplane.artifacts`

The artifact store and replacement budgeting.

- `ArtifactStore` — the artifact store interface.
- `ArtifactMeta` — metadata for a stored artifact.
- `ReplacementLedger` — tracks artifact replacement budget.
- `ReplacementDecision` — a replace-or-keep decision.
- `make_artifact_handoff` — build a public-safe artifact handoff.
- `DEFAULT_REPLACEMENT_BUDGET_BYTES` — default replacement budget.

### `loopplane.approval`

The human approval boundary and permission-rule resolution.

- `HumanApproval` — the human approval boundary.
- `InteractionBroker` — brokers human interaction requests.
- `ApprovalResolution` — a resolved approval outcome.
- `ResolutionSource` — where a resolution came from.
- `PermissionRule` — a permission rule.
- `RuleEffect` — a rule's allow/deny effect.
- `RuleScope` — a rule's scope.
- `SkillConstraint` — a skill-execution constraint.
- `PolicyDecider` — the permission decision interface.
- `PolicyVerdict` — a permission verdict.
- `PolicyAllow` — an allow verdict.
- `PolicyDeny` — a deny verdict.
- `resolve_rules` — resolve permission rules to a verdict.

### `loopplane.observability`

The optional OpenTelemetry overlay.

- `maybe_attach` — attach the OpenTelemetry overlay if available.

## Host interface (unit 002)

The Host Application Interface that exposes the runtime to host applications.

### `loopplane.host`

- `AllowedWorkspaceContextProvider` — optional host-owned, principal-aware source of safe read-only workspace contexts.
- `CapabilityManagementConfig` — default-off durable capability mutation, runtime activation, MCP endpoint policy, schedule-runner, and allowed-context-provider configuration.
- `LoopPlaneHost` — the host-facing runtime entry point; managed-MCP upsert/delete operations are asynchronous, and `agent_controls(session_id)` returns the owner-routed browser-safe, non-durable execution posture used by unit 077.
- `RuntimeConfig` — programmatic runtime configuration.
- `Session` — a host-driven run session with idempotent asynchronous `aclose()` cleanup.
- `RunOutcome` — the terminal outcome of a run.
- `AssembledRuntime` — the assembled runtime components.
- `assemble` — assemble a runtime from configuration.
- `build_host` — build a host from configuration.
- `validate_config` — validate a runtime configuration.
- `ConfigError` — raised on invalid configuration.
- `MemoryConfig` — memory configuration.
- `StorageConfig` — storage configuration.
- `SkillsConfig` — skills configuration.
- `PlatformFairness` — in-process platform fairness collaborator (072).
- `PlatformFairnessPolicy` — platform fairness policy limits (072).
- `PlatformFairnessRejected` — platform fairness quota rejection (072).
- `ToolSpec` — a tool specification for the host.
- `ApprovalPolicy` — the host approval policy.
- `ApprovalDecision` — a host approval decision.
- `Prompt` — a run's input: text or a content-block sequence (036).
- `ContentBlock` — base type for a run's input content blocks (036).
- `TextBlock` — a text input block (036).
- `ImageBlock` — an image input block (036).
- `DocumentBlock` — a document input block (069).
- `TurnAuditEntry` — a public-safe record projected from a checkpointed turn.
- `checkpoint_records_to_audit_entries` — project checkpoint records into audit entries.
- `GenerationExpectation` — expected active-generation durable state for validation.
- `GenerationValidationResult` — public-safe active-generation validation result.
- `validate_active_generation` — validate active-generation proof data before Host startup.
- `DesktopActiveGenerationProvider` — Host-owned read-only active-generation validation provider.
- `DesktopPortableSnapshotProvider` — Host-owned portable snapshot provider for Desktop storage.
- `DesktopRuntimeStorageInitializer` — Host-owned Desktop runtime storage initialization provider.
- `DesktopStorageAuthorityFactory` — retains and validates canonical Desktop generation storage roots.
- `StorageAuthorityFactory` — factory protocol for acquiring retained storage authority leases.
- `StorageAuthorityLease` — retained storage-root validation and lifecycle protocol.
- `PortableSnapshotResult` — result of a portable snapshot export or validation.
- `PortableSnapshotUnavailable` — raised when portable snapshots are not injected.
- `UnavailablePortableSnapshotProvider` — default provider that declines portable snapshots.

## Loop-engineering & layers (units 003-013)

The additive layers composed on the runtime foundation and host interface.

### `loopplane.engineering` (unit 003)

The loop-engineering layer: loop definitions, the loop controller, triggers,
validators, evaluators, retry/repair, loop state, and loop events.

- `run_loop` — run one loop manually to a terminal outcome.
- `LoopDefinition` — a loop's full definition.
- `LoopDefinitionError` — raised on an invalid loop definition.
- `validate_definition` — validate a loop definition.
- `LoopController` — drives a loop's iterations.
- `LoopOutcome` — a loop's terminal outcome (events + state).
- `LoopState` — reconstructable loop state.
- `reconstruct_state` — rebuild loop state from loop events.
- `LoopEvent` — a normalized loop event.
- `LoopEventType` — the loop event type enum.
- `LoopEventSink` — a loop-event consumer.
- `LoopTerminal` — a loop's terminal status.
- `LOOP_EVENT_TYPES` — the set of loop event types.
- `TERMINAL_LOOP_EVENTS` — the terminal loop event types.
- `LOOP_SCHEMA_VERSION` — the loop-event schema version.
- `Trigger` — base loop trigger.
- `ManualTrigger` — a manual trigger.
- `IntervalTrigger` — an interval trigger contract.
- `ConditionTrigger` — a condition trigger contract.
- `InputSource` — supplies a loop iteration's input.
- `StaticInput` — a constant input source.
- `Prompt` — a loop input prompt.
- `HostRuntimeProfile` — selects the host for a loop run.
- `ObservationPolicy` — loop event-emission policy.
- `Validator` — the validator interface.
- `ValidationPolicy` — the validation policy.
- `ValidationResult` — a validation result.
- `ValidationStatus` — a validation status.
- `VALIDATION_STATUSES` — the set of validation statuses.
- `Evaluator` — the evaluator interface.
- `EvaluationPolicy` — the evaluation policy.
- `EvaluationResult` — an evaluation result.
- `RetryPolicy` — the retry policy.
- `RepairPolicy` — the repair policy.
- `RepairContext` — context for a repair attempt.
- `RepairInstructionSource` — supplies repair instructions.
- `BackoffContract` — the backoff interface.
- `ConstantBackoff` — a constant backoff.
- `NO_BACKOFF` — the no-backoff value.
- `StopCondition` — a loop stop condition.
- `StopPredicate` — a stop predicate.
- `stop_on_pass` — stop when validation passes.
- `stop_when_score_at_least` — stop at a score threshold.
- `max_iterations` — stop after N iterations.
- `NextAction` — the next loop action.
- `decide` — decide the next loop action.
- `ApprovalPolicy` — the loop approval policy.
- `ApprovalStatus` — an approval status.
- `ArtifactPolicy` — the loop artifact policy.
- `ArtifactRef` — a public-safe artifact reference.
- `RunReference` — a public-safe run reference.
- `ReviewDecision` — a human review decision.
- `ReviewResolver` — resolves a paused review.

### `loopplane.scheduling` (unit 004)

The local scheduler and trigger engine.

- `Scheduler` — the local scheduler.
- `SchedulerError` — raised on a scheduler error.
- `Clock` — the clock interface.
- `RealClock` — a wall-clock implementation.
- `VirtualClock` — an injectable virtual clock (tests).
- `TriggerRegistration` — a registered trigger.
- `TriggerKind` — the kind of a trigger.
- `TriggerState` — a trigger's state.
- `MissedRunPolicy` — policy for missed runs.
- `Predicate` — a condition predicate.
- `ConditionMode` — condition-watch mode.
- `LoopRunRef` — a reference to a scheduled loop run.
- `reconstruct_states` — rebuild trigger states from events.
- `validate_registration` — validate a trigger registration.
- `SchedulerEvent` — a scheduler event.
- `SchedulerEventType` — the scheduler event type enum.
- `SchedulerEventSink` — a scheduler-event consumer.
- `SCHEDULER_EVENT_TYPES` — the set of scheduler event types.
- `SCHEDULER_SCHEMA_VERSION` — the scheduler-event schema version.

### `loopplane.packs` (unit 005)

Reusable validators and evaluators.

- `read_outcome` — read the public outcome view.
- `OutcomeView` — a public-safe outcome view.
- `rule_validator` — a rule-based validator.
- `text_validator` — a text validator.
- `TextMode` — the text-validator match mode.
- `json_schema_validator` — a JSON-schema validator.
- `artifact_presence_validator` — an artifact-presence validator.
- `scoring_evaluator` — a scoring evaluator.
- `label_evaluator` — a labeling evaluator.
- `length_evaluator` — a length-based evaluator.
- `threshold_gate` — a score threshold gate.
- `all_of` — combine validators (all must pass).
- `any_of` — combine validators (any may pass).
- `PackConfigError` — raised on an invalid pack configuration.

### `loopplane.review` (unit 006)

Human review workflows over the approval boundary.

- `Reviewer` — the human reviewer interface.
- `ReviewRequest` — a review request.
- `build_review_request` — build a review request.
- `ReviewContext` — context for a review.
- `ReviewCause` — why a review was triggered.
- `ReviewQuestion` — a question posed in a review.
- `QuestionAsker` — asks a review question.
- `ReviewOutcome` — a review's outcome.
- `ReviewDecision` — a review decision.
- `to_phase3_decision` — map a review decision to the loop.
- `build_review_resolver` — build a review resolver.
- `resume_review` — resume a paused review.
- `inspect_paused` — inspect a paused review.
- `ReviewMemory` — approval/decision memory.
- `RememberMode` — how a decision is remembered.
- `ReviewKey` — a review's identity key.
- `default_review_key` — the default review-key derivation.
- `ReviewError` — raised on a review error.
- `ReviewEvent` — a review event.
- `ReviewEventType` — the review event type enum.
- `ReviewEventSink` — a review-event consumer.
- `REVIEW_EVENT_TYPES` — the set of review event types.
- `REVIEW_SCHEMA_VERSION` — the review-event schema version.
- `DEFAULT_OPTIONS` — the default review options.

### `loopplane.recall` (unit 007)

Memory recall and knowledge indexing as loop-aware context sources.

- `assemble_recall` — assemble recalled context.
- `RecallAssembly` — the assembled recall result.
- `RecallSource` — a recall source interface.
- `RecalledEntry` — one recalled entry.
- `build_recall_input` — build a loop input from recall.
- `conversation_recall` — recall from conversation history.
- `artifact_recall` — recall from artifacts.
- `ArtifactReader` — reads artifacts for recall.
- `memory_entry_recall` — recall from memory entries.
- `knowledge_recall` — recall from a knowledge index.
- `KnowledgeIndex` — the knowledge index interface.
- `InMemoryKnowledgeIndex` — an in-memory knowledge index.
- `KnowledgeEntry` — a knowledge-index entry.
- `QueryFn` — a query function.
- `default_query` — the default query function.
- `RetrievalBudget` — a retrieval budget.
- `apply_budget` — apply a retrieval budget.
- `BudgetResult` — the result of applying a budget.

### `loopplane.toolkit` (unit 008)

The advanced tool ecosystem: discovery, registry, packages, manifests, versioning,
and diagnostics.

- `discover` — discover tools from a source.
- `DiscoveredTool` — a discovered tool.
- `ToolCatalog` — a catalog of tools.
- `ToolPackage` — a tool package's metadata.
- `ToolPlugin` — a tool plugin bundle.
- `register_plugin` — register a tool plugin.
- `AdapterRegistrar` — registers adapters with the gateway.
- `CapabilityManifest` — a tool capability manifest.
- `build_manifest` — build a capability manifest.
- `select_by_policy` — select tools by policy.
- `Version` — a parsed tool version.
- `parse_version` — parse a version string.
- `diagnose` — produce a tool diagnostics report.
- `DiagnosticsReport` — a diagnostics report.
- `Diagnostic` — a single diagnostic.
- `DiagnosticKind` — the kind of a diagnostic.
- `ToolkitError` — raised on a toolkit error.

### `loopplane.governance` (unit 009)

Sandbox, policy, and cost governance.

- `sandbox_profile` — a sandbox execution profile.
- `path_policy` — a filesystem path policy.
- `permission_policy` — a permission policy.
- `capability_policy` — a capability policy.
- `budget_policy` — a budget policy.
- `quota_policy` — a quota policy.
- `CostModel` — a cost model.
- `safe_failure` — a safe-failure decision.
- `default_deny` — a default-deny decision.
- `allow` — an allow decision.
- `deny` — a deny decision.
- `SimpleDecision` — a simple allow/deny decision.
- `as_decider` — adapt a policy to a decider.
- `all_of` — combine policies (all must allow).
- `network_policy` — gate tools that require network egress (opt-in).
- `plan_mode_policy` — gate non-read-only tools during plan-mode investigation.
- `per_run_permission_mode_policy` — apply one validated named permission mode to one run while preserving explicit deny and existing safety-policy precedence (unit 077).
- `rule_dsl_policy` — enforce a host-suppliable declarative permission rule set (allow/deny/ask).
- `PermissionRuleSet` — a host-suppliable permission rule set with a default decision.
- `PermissionRuleSpec` — one declarative permission rule (tool matcher, optional input match, decision).
- `permission_mode_ruleset` — build the preset rule set for a named permission mode (unit 066).
- `PERMISSION_MODES` — the known named permission modes: acceptEdits / bypassPermissions / dontAsk / plan (unit 066).

### `loopplane.inspect` (unit 010)

Read-only observability and debug data contracts.

- `build_trace` — build a trace from recorded events.
- `Trace` — a normalized trace.
- `TraceSpan` — a span in a trace.
- `SpanKind` — the kind of a trace span.
- `build_timeline` — build a debug timeline.
- `Timeline` — a sequence-ordered timeline.
- `TimelineEntry` — one timeline entry.
- `SequencedEvent` — an event paired with its sequence.
- `replay` — deterministically replay recorded events.
- `ReplaySummary` — a replay's summary.
- `run_diagnostics` — summarize a runtime event stream.
- `RunDiagnostics` — run diagnostics (metadata only).
- `loop_diagnostics` — summarize a loop event stream.
- `LoopDiagnostics` — loop diagnostics (metadata only).

### `loopplane.webapi` (unit 011)

The web/API host transport over the Host Application Interface.

- `create_app` — build the web/API application.
- `Authenticator` — the pluggable default-deny auth boundary.
- `Principal` — an authenticated caller's identity (session ownership, 022).
- `token_authenticator` — a reference token→principal verifier (dev/tests).
- `jwt_authenticator` — a host-supplied OAuth/JWT/OIDC verifier (JWKS, iss/aud/exp/nbf; 056).
- `TenantHostPool` — a per-principal host pool for concurrent multi-tenant serving (061; ADR 0009).
- `EventReplayRecord` — a replayable session SSE frame record.
- `EventReplayStore` — the durable event replay store protocol.
- `FileEventReplayStore` — a filesystem event replay store.
- `SqliteEventReplayStore` — a local SQLite event replay store.
- `PostgresEventReplayStore` — a PostgreSQL event replay store (`loopplane[postgres]`).
- `RunRequest` — a run request body; unit 077 adds an optional validated one-run `permission_mode` and structured opaque upload references. The Web host also exposes an owner-scoped agent-controls projection alongside the existing session/monthly cost reads; rejected modes and unavailable non-image handoffs fail before model work without echoing private values.
- `UploadRef` — a reference to an uploaded file a run carries (036).
- `RunResult` — a run result (metadata only).
- `OpenedSession` — an opened session handle.
- `SessionAnswer` — an answer submitted to a session.
- `SessionSummaryView` — a session summary view.
- `HistoryEntryView` — a history entry view.
- `ArtifactContent` — a public-safe artifact content view.
- `QuestionAnswer` — an answer to a question.
- `Resolved` — a resolved interaction marker.
- `ErrorResponse` — a normalized error response.

### `loopplane.studio` (unit 012)

The local desktop/studio host presentation.

- `StudioHost` — the local developer-console host.
- `SidecarHost` — the in-process sidecar host.
- `InProcessSidecar` — the in-process sidecar contract.
- `RunResultView` — a run result view.
- `OutcomeView` — an outcome view.
- `SessionSummaryView` — a session summary view.
- `HistoryEntryView` — a history entry view.
- `ErrorView` — an error view.

### `loopplane.orchestration` (unit 013)

Multi-agent orchestration: run several loops as subagents and combine results.

- `AgentRegistry` — a registry of named subagents.
- `Subagent` — a named subagent (a loop definition).
- `DuplicateSubagentError` — raised on a duplicate subagent name.
- `Coordinator` — runs selected subagents and returns results.
- `DelegationPolicy` — selects which subagents to run.
- `ChildRunReference` — a public-safe child run reference.
- `SubagentResult` — a subagent's coordinated result.
- `aggregate_events` — aggregate subagents' loop events.
- `AggregatedEvent` — one aggregated, metadata-only event.
- `aggregate_artifacts` — aggregate subagents' artifact references.
- `AggregatedArtifact` — one aggregated, metadata-only artifact reference.

### `loopplane.hooks` (unit 015)

Lifecycle hooks: observe — and, at the gating points, gate or modify — the agent
at well-defined lifecycle moments. Additive and inert by default.

- `LifecyclePoint` — the eleven lifecycle points.
- `is_gating` — whether a point accepts a gating decision.
- `HookRegistry` — register, unregister, and clear callbacks per point.
- `HookCallback` — the type of a hook callback (sync or async).
- `HookDispatcher` — fires points and resolves gating decisions.
- `BeforeToolUsePayload` — the before-tool-use payload.
- `AfterToolUsePayload` — the after-tool-use payload.
- `AfterToolFailurePayload` — the after-tool-failure payload.
- `FileChangedPayload` — the file-changed payload.
- `UserPromptSubmitPayload` — the user-prompt-submit payload.
- `SessionStartPayload` — the session-start payload.
- `SessionEndPayload` — the session-end payload.
- `ProcessSetupPayload` — the process-setup payload.
- `SubagentStartPayload` — the subagent-start payload.
- `SubagentStopPayload` — the subagent-stop payload.
- `ModelStopPayload` — the model-stop payload.
- `ToolGateAllow` — allow a tool call unchanged.
- `ToolGateDeny` — deny a tool call with a public-safe reason.
- `ToolGateModify` — replace a tool call's inputs.
- `ToolGateDecision` — the before-tool-use decision type.
- `PromptAllow` — allow a prompt unchanged.
- `PromptBlock` — block a prompt with a public-safe reason.
- `PromptAnnotate` — augment a prompt with extra context.
- `PromptDecision` — the user-prompt-submit decision type.

### `loopplane.plugins` (unit 016)

Manifest-bundle plugins: discover, gate by an enable-list, and collect skills, MCP
servers, and hooks for the existing seams. Inert by default.

- `discover` — discover plugins under host-supplied roots.
- `DiscoveredPlugin` — one discovered candidate (manifest or a public-safe problem).
- `PluginManifest` — the parsed, validated `plugin.json`.
- `HookEntry` — a manifest hook declaration (`point` + importable `target`).
- `load_plugins` — gate by an enable-list and collect contributions.
- `PluginLoadResult` — the collected contribution set plus diagnostics.
- `PluginInfo` — a read-only, metadata-only plugin listing entry.
- `list_plugins` — a public-safe listing of discovered plugins.

### `loopplane.cli` (units 017, 079)

A thin terminal host over `loopplane.host`: the `loopplane` console command and its
testable, credential-free core. Unit 079 makes the interactive path hold ONE
conversation (approvals, questions, and a mid-turn interrupt included) and adds a
remote bridge that is a client of the existing web/API host — no outward contract
changes, and `httpx` stays lazily imported from the existing `net` extra.

- `main` — the `loopplane` console entry point.
- `dispatch` — parse argv and run a command; returns an exit code.
- `make_parser` — the argument parser for the CLI commands.
- `build_host` — build a host over the selected model (optionally with a store).
- `run_once` — run one prompt and render it to a stream (the one-shot path).
- `chat_loop` — hold one conversation, running input lines as turns in it (079).
- `resume_loop` — pick a stored conversation up and continue it interactively (079).
- `remote_loop` — drive a conversation on a remote host; returns an exit code (079).
- `RemoteEndpoint` — where to connect and as whom; holds the credential in memory only, and carries an `api_prefix` for a server not published under `/v1` (079).
- `EventRenderer` — an event sink that renders a run, metadata-safe; renders approval
  requests and questions as of 079.
- `LineSource` — the single input source turns and answers are read from (079).
- `parse_approval_answer` — map a typed line to a permission decision (079).
- `question_answer` — the answer text for a pending question (079).
- `select_model` — choose the demo model or an env-configured provider.
- `DemoModel` — the built-in, credential-free demo model.

### `loopplane.commands` (units 065, 079)

Backend-semantic slash commands (gap G14): a small host command surface that maps a
leading-`/` command to an EXISTING host seam — `/cost` (064), `/model`, `/memory`,
`/compact` (the loop's `compact_history`), and, added by 079, `/help`, `/sessions`
(`list_sessions`), `/permission` (`agent_controls`), and `/history`
(`history_snapshot`). Commands are a host UX, NOT tools: they never reach the Tool
Gateway or the Event Bus. Shared by the CLI REPL, the web/API `POST /commands`
endpoint, and the Desktop sidecar's `command.execute` (ADR 0017); dispatch never raises
and is public-safe.

Unit 079 adds a **remote-safety classification**: each command declares whether it may
run over a remote connection, and a context can declare that its caller is remote. A
non-remote-safe command is refused before its handler runs, so it touches no host seam.
`/compact` is the one built-in that is not remote-safe — the only mutator, irreversible,
and unverifiable from a remote view. Both knobs default to the pre-079 behavior
(`remote_safe=True`, `CommandContext.remote=False`), so existing consumers are
byte-identical.

- `CommandResult` — a normalized, public-safe command result (`kind` + `text`).
- `CommandContext` — what a handler needs (the host + principal + optional session +
  models + whether the caller is remote).
- `CommandDescriptor` — one command's name, one-line summary, remote-safety, and whether it is session-scoped (079).
- `CommandRegistry` — parses a leading-`/` line and dispatches to a handler (never
  raises). `register` takes keyword-only `summary`, `remote_safe`, and
  `session_scoped`; `describe` enumerates every command; `session_scoped_names`
  tells a host with principals which commands need an ownership check before
  dispatch.
- `format_command_listing` — the operator-facing command listing, shared so a host
  that answers `/help` itself produces exactly the registry's text (079).
- `default_registry` — a registry with the eight built-in commands.
