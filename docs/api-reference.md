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
- `OutputBlock` — an assistant output content block.
- `TextIncrement` — a streamed assistant text increment.
- `ReasoningIncrement` — a streamed assistant reasoning increment.
- `ToolCallBlock` — a tool-call content block.
- `ToolCallRequest` — a requested tool call.
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

The internal tool adapter.

- `InternalToolAdapter` — the adapter for built-in internal tools.

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

- `MemoryStore` — the memory store interface.
- `MemoryEntry` — a stored memory entry.
- `MemoryAugmentation` — a memory-derived prompt augmentation.
- `select_entries` — select memory entries for a prompt.

### `loopplane.checkpoint`

Durable session recording, checkpoint records, and session rebuild.

- `SessionRecorder` — records a session to durable records.
- `RecordingSink` — an event sink that records to the store.
- `CheckpointStore` — the checkpoint record store.
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

- `LoopPlaneHost` — the host-facing runtime entry point.
- `RuntimeConfig` — programmatic runtime configuration.
- `Session` — a host-driven run session.
- `RunOutcome` — the terminal outcome of a run.
- `AssembledRuntime` — the assembled runtime components.
- `assemble` — assemble a runtime from configuration.
- `build_host` — build a host from configuration.
- `validate_config` — validate a runtime configuration.
- `ConfigError` — raised on invalid configuration.
- `MemoryConfig` — memory configuration.
- `StorageConfig` — storage configuration.
- `SkillsConfig` — skills configuration.
- `ToolSpec` — a tool specification for the host.
- `ApprovalPolicy` — the host approval policy.
- `ApprovalDecision` — a host approval decision.

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
- `RunRequest` — a run request body.
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

### `loopplane.cli` (unit 017)

A thin terminal host over `loopplane.host`: the `loopplane` console command and its
testable, credential-free core.

- `main` — the `loopplane` console entry point.
- `dispatch` — parse argv and run a command; returns an exit code.
- `make_parser` — the argument parser for the CLI commands.
- `build_host` — build a host over the selected model (optionally with a store).
- `run_once` — run one prompt and render it to a stream.
- `chat_loop` — run input lines as turns until EOF/quit.
- `EventRenderer` — an event sink that renders a run, metadata-safe.
- `select_model` — choose the demo model or an env-configured provider.
- `DemoModel` — the built-in, credential-free demo model.
