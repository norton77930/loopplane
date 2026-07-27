"""``create_app``: the web/API host application factory (011; per-principal
ownership added in 022).

Builds an ASGI app that exposes the embedded :class:`~loopplane.host.LoopPlaneHost`
behind the authentication boundary: run, event stream, interactive session, and
read-only inspection. The boundary now identifies the caller (a ``Principal``) and
every session is scoped to the principal that opened it — the listing returns only
the caller's sessions, and a per-session route returns ``404`` (never another
principal's data or its existence) for a session the caller does not own. Malformed
requests return the one public-safe ``ErrorResponse`` envelope (FR-016). Interactive
sessions live in a lifespan-held task group (see :mod:`loopplane.webapi.sessions`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager, nullcontext, suppress
from dataclasses import dataclass
from datetime import UTC, datetime

import anyio
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    WebSocket,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.websockets import WebSocketDisconnect

from loopplane.commands import CommandContext, default_registry
from loopplane.events import RuntimeEvent
from loopplane.host import (
    ContentBlock,
    LoopPlaneHost,
    PlatformFairnessRejected,
    TextBlock,
)
from loopplane.webapi.auth import (
    DENY_ALL,
    Authenticator,
    Principal,
    make_auth_dependency,
)
from loopplane.webapi.live import (
    LiveTicketStore,
    latest_sequence,
    replay_event_messages,
)
from loopplane.webapi.models import (
    AgentControlProjectionView,
    ArtifactContent,
    BulkDeleteRequest,
    BulkDeleteResult,
    CapabilityOperationResultView,
    CapabilitySettingsStatusView,
    CommandRequest,
    CommandResultView,
    ErrorResponse,
    ForkSessionRequest,
    HistoryEntryView,
    LiveClientMessage,
    LiveTicketView,
    ManagedMcpConfigurationView,
    ManagedMemoryDetailView,
    ManagedMemoryView,
    ManagedScheduleView,
    ManagedSkillDetailView,
    ManagedSkillView,
    McpConfigurationWriteRequest,
    McpMutationResponse,
    McpServerView,
    MemoryEntryView,
    MemoryMutationResponse,
    MemoryWriteRequest,
    ModelDefaultMutationResponse,
    ModelDefaultView,
    ModelDefaultWriteRequest,
    ModelInfo,
    MonthlyCostView,
    OpenedSession,
    QuestionAnswer,
    RenameRequest,
    Resolved,
    RunRequest,
    RunResult,
    ScheduleMutationResponse,
    ScheduleWriteRequest,
    SessionAnswer,
    SessionContextBindRequest,
    SessionContextView,
    SessionCostView,
    SessionSummaryView,
    SkillImportRequest,
    SkillMutationResponse,
    SkillsResponse,
    SkillView,
    SkillWriteRequest,
    ToolView,
    UploadResult,
    WorkspaceContextMutationResponse,
    WorkspaceContextView,
    WorkspaceContextWriteRequest,
)
from loopplane.webapi.multimodal import (
    MediaNotAccepted,
    MediaTooLarge,
    UnknownUpload,
    UploadHandoffRejected,
    assemble_blocks,
)
from loopplane.webapi.pool import TenantHostPool
from loopplane.webapi.replay import EventReplayRecord, EventReplayStore
from loopplane.webapi.sessions import (
    SessionEntry,
    reconnect_stream,
    replay_store_stream,
    run_session,
)
from loopplane.webapi.streaming import run_event_stream
from loopplane.webapi.uploads import UploadStore, UploadTooLarge


async def _discard(event: RuntimeEvent) -> None:
    """A run sink that drops events — used when only the outcome is returned."""

    return None


@dataclass(frozen=True)
class ModelHost:
    """A model-catalog entry (028): a label + a single-model host. Catalog hosts share
    one checkpoint root (021) so a routed run resumes the shared session.

    ``accepts_media`` (036) declares whether the host's model accepts image input;
    the catalog advertises it on ``/v1/models`` and the run endpoints reject an
    image sent to a text-only model with a clear normalized error (ADR 0001 D5)."""

    label: str
    host: LoopPlaneHost
    accepts_media: bool = False
    # 045 — whether the host's model supports native structured output; the catalog
    # advertises it and the run endpoints reject a schema for a non-supporting model.
    supports_structured_output: bool = False


def create_app(
    host: LoopPlaneHost,
    *,
    authenticator: Authenticator | None = None,
    api_prefix: str = "/v1",
    models: Mapping[str, ModelHost] | None = None,
    uploads: UploadStore | None = None,
    default_accepts_media: bool = False,
    default_supports_structured_output: bool = False,
    max_image_bytes: int = 5 * 1024 * 1024,
    sse_replay_buffer: int = 0,
    event_replay_store: EventReplayStore | None = None,
    event_replay_limit: int = 1000,
    event_replay_poll_interval_seconds: float = 0.25,
    event_replay_idle_polls: int | None = None,
    host_pool: TenantHostPool | None = None,
) -> FastAPI:
    """Build the web/API host app embedding ``host`` behind the auth boundary.

    ``authenticator`` is the embedder's verifier; absent one, every request is
    denied (default-deny, FR-014). Each route resolves the caller's ``Principal``
    and scopes sessions to it (022). ``models`` is an optional catalog of single-model
    hosts a run can route to (028, one model per run); ``uploads`` is an optional
    per-principal blob store for the upload endpoint + the ``read_upload`` tool.
    ``default_accepts_media`` declares whether the bare default ``host`` accepts
    image input (036); ``max_image_bytes`` caps an embedded image (ADR 0001 D6).
    ``sse_replay_buffer`` (058; default 0 = off, byte-identical) sizes the bounded
    per-session SSE replay buffer for ``Last-Event-ID`` reconnect (ADR 0006).
    ``event_replay_store`` (071; default None = off) persists the same session SSE
    frames for durable reconnect replay after ownership checks.
    ``host_pool`` (061; default None = off, byte-identical) routes each principal to
    its OWN host so principals run concurrently, while each principal's host keeps
    its sequential ``_active`` invariant (ADR 0009, pool-above-host).
    """

    auth = authenticator or DENY_ALL
    require = make_auth_dependency(auth)
    sessions: dict[str, SessionEntry] = {}
    session_hosts: dict[str, tuple[str, LoopPlaneHost]] = {}
    live_tickets = LiveTicketStore()
    catalog = dict(models or {})
    command_registry = default_registry()  # 065: backend slash commands

    def _select(model: str | None) -> tuple[LoopPlaneHost, bool, bool]:
        # Route to the chosen single-model host (028); one model per run. Returns
        # the host, whether it accepts image input (036), and whether it supports
        # native structured output (045).
        if not model:
            return host, default_accepts_media, default_supports_structured_output
        entry = catalog.get(model)
        if entry is None:
            raise HTTPException(status_code=400, detail="unknown model")
        return entry.host, entry.accepts_media, entry.supports_structured_output

    def _resolve(
        model: str | None, principal: Principal
    ) -> tuple[LoopPlaneHost, bool, bool]:
        # 061: with a host pool, route the caller to its OWN host (concurrent across
        # principals; each host stays sequential). The model is still validated by
        # _select (unknown -> 400) + supplies the media/structured-output flags.
        # Default (no pool) returns _select(model) verbatim — byte-identical.
        effective_model = model
        resolve_default = getattr(host, "model_default", None)
        if effective_model is None and callable(resolve_default):
            available = {model_id: entry.label for model_id, entry in catalog.items()}
            default = resolve_default(
                principal.id,
                available_models=available,
            )
            if default.status == "available":
                effective_model = default.model_id
        chosen, accepts_media, supports_so = _select(effective_model)
        if host_pool is not None:
            try:
                chosen = host_pool.host_for(principal.id, effective_model)
            except RuntimeError as exc:
                raise HTTPException(
                    status_code=429, detail="capacity exceeded"
                ) from exc
        return chosen, accepts_media, supports_so

    def _read_upload_available(selected: LoopPlaneHost) -> bool:
        if not hasattr(selected, "inspect_tools"):
            return False
        return any(tool.name == "read_upload" for tool in selected.inspect_tools())

    def _build_blocks(
        body: RunRequest,
        owner: str,
        accepts_media: bool,
        read_upload_available: bool,
    ) -> list[ContentBlock]:
        # Assemble the user message: image uploads (036) become leading ImageBlocks
        # ahead of the prompt; failures degrade to a public-safe normalized error
        # before any run starts (ADR 0001 D5/D6). No uploads -> a single TextBlock.
        if not body.uploads:
            return [TextBlock(text=body.prompt)]
        if uploads is None:
            raise HTTPException(status_code=400, detail="uploads not configured")
        try:
            return assemble_blocks(
                body.prompt,
                [ref.reference for ref in body.uploads],
                uploads,
                owner,
                accepts_media=accepts_media,
                accepts_read_upload=read_upload_available,
                max_image_bytes=max_image_bytes,
            )
        except MediaTooLarge as exc:
            raise HTTPException(status_code=413, detail="image too large") from exc
        except UploadHandoffRejected as exc:
            raise HTTPException(
                status_code=400, detail="upload handoff unavailable"
            ) from exc
        except (UnknownUpload, MediaNotAccepted) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def _check_output_schema(
        output_schema: dict[str, object] | None, supports: bool
    ) -> None:
        # 045: validate a supplied structured-output schema before any run starts.
        # A malformed (empty) schema or a non-supporting model is a clear 400, so a
        # caller is never silently handed unconstrained output presented as structured.
        if output_schema is None:
            return
        if not output_schema:
            raise HTTPException(status_code=400, detail="malformed output_schema")
        if not supports:
            raise HTTPException(
                status_code=400,
                detail="model does not support structured output",
            )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # A task group that outlives individual requests holds open interactive
        # sessions until they are closed (US3).
        async with anyio.create_task_group() as task_group:
            app.state.session_tg = task_group
            try:
                yield
            finally:
                task_group.cancel_scope.cancel()

    app = FastAPI(lifespan=lifespan)

    async def on_validation_error(request: Request, exc: Exception) -> JSONResponse:
        # A malformed request → a fixed public-safe envelope, never the
        # field-level internals (FR-016).
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(detail="invalid request").model_dump(),
        )

    app.add_exception_handler(RequestValidationError, on_validation_error)

    # Auth is enforced per route by resolving the caller's principal; this also
    # hands each route the identity it scopes ownership against.
    router = APIRouter(prefix=api_prefix)

    def _require(session_id: str, principal: Principal) -> SessionEntry:
        # A live interactive session the caller owns — otherwise 404 (never reveal
        # another principal's session or its existence).
        entry = sessions.get(session_id)
        if entry is None or entry.owner != principal.id:
            raise HTTPException(status_code=404, detail="not found")
        return entry

    def _owned_or_404(session_id: str, principal: Principal) -> None:
        # Ownership for the durable/inspection routes: a live session by its
        # registry owner, else the durable owner from the checkpoint metadata.
        entry = sessions.get(session_id)
        if entry is not None:
            if entry.owner != principal.id:
                raise HTTPException(status_code=404, detail="not found")
            return
        for summary in host.list_sessions():
            if summary.session_id == session_id:
                if summary.principal_id != principal.id:
                    raise HTTPException(status_code=404, detail="not found")
                return
        raise HTTPException(status_code=404, detail="not found")

    def _agent_control_host_or_404(
        session_id: str, principal: Principal
    ) -> LoopPlaneHost:
        entry = sessions.get(session_id)
        if entry is not None:
            if entry.owner != principal.id:
                raise HTTPException(status_code=404, detail="not found")
            return entry.host or host
        routed = session_hosts.get(session_id)
        if routed is not None:
            owner, owning_host = routed
            if owner != principal.id:
                raise HTTPException(status_code=404, detail="not found")
            return owning_host
        _owned_or_404(session_id, principal)
        return host

    # --- US1: run -----------------------------------------------------------

    @router.post("/runs")
    async def post_run(
        body: RunRequest, principal: Principal = Depends(require)
    ) -> RunResult:
        chosen, accepts_media, supports_so = _resolve(body.model, principal)
        _check_output_schema(body.output_schema, supports_so)
        blocks = _build_blocks(
            body,
            principal.id,
            accepts_media,
            _read_upload_available(chosen),
        )
        # 061: bound a principal's concurrent in-flight runs (no-op when no pool —
        # nullcontext keeps the default path byte-identical).
        in_flight = (
            host_pool.in_flight(principal.id)
            if host_pool is not None
            else nullcontext()
        )
        try:
            async with in_flight:
                outcome = await chosen.run(
                    blocks,
                    _discard,
                    principal_id=principal.id,
                    output_schema=body.output_schema,
                    model=body.model,
                    permission_mode=body.permission_mode,
                )
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="permission mode unavailable"
            ) from exc
        except PlatformFairnessRejected as exc:
            raise HTTPException(status_code=429, detail="capacity exceeded") from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=409, detail="a run is already active"
            ) from exc
        session_hosts[outcome.session_id] = (principal.id, chosen)
        return RunResult.from_outcome(outcome)

    # --- US2: event stream --------------------------------------------------

    @router.post("/runs/events")
    async def post_run_events(
        body: RunRequest, principal: Principal = Depends(require)
    ) -> StreamingResponse:
        chosen, accepts_media, supports_so = _resolve(body.model, principal)
        _check_output_schema(body.output_schema, supports_so)
        blocks = _build_blocks(
            body,
            principal.id,
            accepts_media,
            _read_upload_available(chosen),
        )
        return StreamingResponse(
            run_event_stream(
                chosen,
                blocks,
                principal.id,
                body.output_schema,
                model=body.model,
                permission_mode=body.permission_mode,
                on_session=lambda session_id: session_hosts.__setitem__(
                    session_id, (principal.id, chosen)
                ),
            ),
            media_type="text/event-stream",
        )

    # --- 077: owner-scoped agent-control projection ------------------------

    @router.get("/sessions/{session_id}/agent-controls")
    async def agent_controls(
        session_id: str, principal: Principal = Depends(require)
    ) -> AgentControlProjectionView:
        owning_host = _agent_control_host_or_404(session_id, principal)
        return AgentControlProjectionView.from_projection(
            owning_host.agent_controls(session_id)
        )

    # --- US3: interactive session -------------------------------------------

    @router.post("/sessions")
    async def open_session(
        model: str | None = None, principal: Principal = Depends(require)
    ) -> OpenedSession:
        chosen, accepts_media, supports_so = _resolve(model, principal)
        ready = anyio.Event()
        box: dict[str, str] = {}
        app.state.session_tg.start_soon(
            run_session,
            chosen,
            sessions,
            ready,
            box,
            principal.id,
            accepts_media,
            supports_so,
            sse_replay_buffer,
            event_replay_store,
            model,
        )
        await ready.wait()
        if box.get("error"):
            raise HTTPException(status_code=409, detail="a run is already active")
        return OpenedSession(session_id=box["sid"])

    @router.get("/sessions/{session_id}/events")
    async def session_events(
        session_id: str,
        principal: Principal = Depends(require),
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> StreamingResponse:
        # 058 + 071: replay the in-memory and optional durable frames after
        # Last-Event-ID, then continue live. If this worker has no live entry, the
        # durable store can still serve/tail replay after the existing ownership
        # check. With no durable store, unknown/non-live sessions keep 404 behavior.
        entry = sessions.get(session_id)
        if entry is None:
            _owned_or_404(session_id, principal)
            if event_replay_store is None:
                raise HTTPException(status_code=404, detail="not found")
            return StreamingResponse(
                replay_store_stream(
                    event_replay_store,
                    session_id,
                    principal.id,
                    last_event_id,
                    limit=event_replay_limit,
                    poll_interval_seconds=event_replay_poll_interval_seconds,
                    idle_polls=event_replay_idle_polls,
                ),
                media_type="text/event-stream",
            )
        if entry.owner != principal.id:
            raise HTTPException(status_code=404, detail="not found")
        durable_records: list[EventReplayRecord] = []
        if event_replay_store is not None and last_event_id is not None:
            with suppress(Exception):
                last_id = int(last_event_id)
                durable_records, _problems = event_replay_store.load_after(
                    session_id, principal.id, last_id, limit=event_replay_limit
                )
        return StreamingResponse(
            reconnect_stream(
                entry.replay_buffer,
                last_event_id,
                entry.events,
                durable_records=durable_records,
            ),
            media_type="text/event-stream",
        )

    @router.post("/sessions/{session_id}/live-ticket")
    async def live_ticket(
        session_id: str, principal: Principal = Depends(require)
    ) -> LiveTicketView:
        _require(session_id, principal)
        record = live_tickets.issue(principal.id, session_id)
        return LiveTicketView(
            ticket=record.ticket,
            session_id=record.session_id,
            issued_at=record.issued_at,
            expires_at=record.expires_at,
            capabilities=list(record.capabilities),
        )

    @router.websocket("/sessions/{session_id}/live")
    async def live_session_channel(
        websocket: WebSocket,
        session_id: str,
        ticket: str,
        last_sequence: int = 0,
    ) -> None:
        record = live_tickets.consume(ticket, session_id)
        entry = sessions.get(session_id)
        if record is None or entry is None or entry.owner != record.principal_id:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        await websocket.send_json(
            {
                "type": "ready",
                "session_id": session_id,
                "sequence": latest_sequence(entry.replay_buffer),
                "payload": {"latest_sequence": latest_sequence(entry.replay_buffer)},
            }
        )
        seen_sequence = last_sequence
        send_lock = anyio.Lock()

        async def send_live(message: dict[str, object]) -> None:
            async with send_lock:
                with suppress(WebSocketDisconnect, RuntimeError):
                    await websocket.send_json(message)

        async def drive_live(body: RunRequest) -> None:
            try:
                blocks = _build_blocks(
                    body,
                    record.principal_id,
                    entry.accepts_media,
                    _read_upload_available(entry.host or host),
                )
                await entry.session.submit(
                    blocks,
                    output_schema=body.output_schema,
                    permission_mode=body.permission_mode,
                )
            except HTTPException as exc:
                await send_live(
                    {"type": "error", "payload": {"detail": str(exc.detail)}}
                )
            except ValueError:
                await send_live(
                    {
                        "type": "error",
                        "payload": {"detail": "permission mode unavailable"},
                    }
                )
            except RuntimeError:
                await send_live(
                    {
                        "type": "error",
                        "payload": {"detail": "a run is already active"},
                    }
                )

        async def pump_events() -> None:
            nonlocal seen_sequence
            while True:
                sent = False
                for event_message in replay_event_messages(
                    entry.replay_buffer, seen_sequence
                ):
                    await send_live(event_message)
                    sequence = event_message.get("sequence")
                    if isinstance(sequence, int):
                        seen_sequence = max(seen_sequence, sequence)
                    sent = True
                await anyio.sleep(0 if sent else 0.01)

        async with anyio.create_task_group() as live_tasks:
            live_tasks.start_soon(pump_events)
            try:
                while True:
                    message = LiveClientMessage.model_validate(
                        await websocket.receive_json()
                    )
                    if message.sequence is not None:
                        seen_sequence = max(seen_sequence, message.sequence)
                    if message.type == "ack":
                        continue
                    if message.type == "abort":
                        entry.session.cancel()
                        entry.close.set()
                        await send_live(
                            {"type": "notice", "payload": {"aborted": True}}
                        )
                        continue
                    if message.type == "approval_decision":
                        request_id = str(message.payload.get("request_id", ""))
                        scope = message.payload.get("scope", "once")
                        resolved = entry.session.answer_approval(
                            request_id,
                            allow=bool(message.payload.get("allow", False)),
                            scope=(scope if scope in ("once", "session") else "once"),
                            reason=(
                                str(message.payload["reason"])
                                if "reason" in message.payload
                                else None
                            ),
                        )
                        await send_live(
                            {"type": "notice", "payload": {"resolved": resolved}}
                        )
                        continue
                    if message.type == "question_answer":
                        request_id = str(message.payload.get("request_id", ""))
                        raw_answers = message.payload.get("answers", [])
                        answers = (
                            [str(answer) for answer in raw_answers]
                            if isinstance(raw_answers, list)
                            else []
                        )
                        resolved = entry.session.answer_question(request_id, answers)
                        await send_live(
                            {"type": "notice", "payload": {"resolved": resolved}}
                        )
                        continue
                    body = RunRequest.model_validate(message.payload)
                    _check_output_schema(
                        body.output_schema, entry.supports_structured_output
                    )
                    app.state.session_tg.start_soon(drive_live, body)
            except WebSocketDisconnect:
                return
            finally:
                live_tasks.cancel_scope.cancel()

    @router.post("/sessions/{session_id}/submit")
    async def submit_to_session(
        session_id: str, body: RunRequest, principal: Principal = Depends(require)
    ) -> RunResult:
        # Drive the live session to its outcome. A pending approval/question is
        # answered out-of-band by a concurrent request; a client that prefers to
        # observe progress incrementally reads the session events stream (FR-007).
        entry = _require(session_id, principal)
        _check_output_schema(body.output_schema, entry.supports_structured_output)
        blocks = _build_blocks(
            body,
            principal.id,
            entry.accepts_media,
            _read_upload_available(entry.host or host),
        )
        try:
            outcome = await entry.session.submit(
                blocks,
                output_schema=body.output_schema,
                permission_mode=body.permission_mode,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="permission mode unavailable"
            ) from exc
        except PlatformFairnessRejected as exc:
            raise HTTPException(status_code=429, detail="capacity exceeded") from exc
        return RunResult.from_outcome(outcome)

    @router.post("/sessions/{session_id}/approvals/{request_id}")
    async def answer_approval(
        session_id: str,
        request_id: str,
        body: SessionAnswer,
        principal: Principal = Depends(require),
    ) -> Resolved:
        entry = _require(session_id, principal)
        resolved = entry.session.answer_approval(
            request_id, allow=body.allow, scope=body.scope, reason=body.reason
        )
        return Resolved(resolved=resolved)

    @router.post("/sessions/{session_id}/questions/{request_id}")
    async def answer_question(
        session_id: str,
        request_id: str,
        body: QuestionAnswer,
        principal: Principal = Depends(require),
    ) -> Resolved:
        entry = _require(session_id, principal)
        resolved = entry.session.answer_question(request_id, body.answers)
        return Resolved(resolved=resolved)

    @router.post("/sessions/{session_id}/cancel")
    async def cancel_session(
        session_id: str, principal: Principal = Depends(require)
    ) -> Resolved:
        entry = _require(session_id, principal)
        entry.session.cancel()
        entry.close.set()
        return Resolved(resolved=True)

    # --- US4: inspection (read-only, metadata-only) -------------------------

    @router.get("/sessions")
    async def list_sessions(
        principal: Principal = Depends(require),
    ) -> list[SessionSummaryView]:
        return [
            SessionSummaryView.from_summary(summary)
            for summary in host.list_sessions()
            if summary.principal_id == principal.id
        ]

    @router.get("/sessions/search")
    async def search_sessions(
        q: str, principal: Principal = Depends(require)
    ) -> list[SessionSummaryView]:
        return [
            SessionSummaryView.from_summary(summary)
            for summary in host.search_sessions(q, principal.id)
        ]

    @router.post("/sessions/bulk-delete")
    async def bulk_delete_sessions(
        body: BulkDeleteRequest, principal: Principal = Depends(require)
    ) -> BulkDeleteResult:
        deleted = host.bulk_delete_sessions(body.session_ids, principal_id=principal.id)
        for session_id in deleted:
            entry = sessions.get(session_id)
            if entry is not None:
                entry.session.cancel()
                entry.close.set()
            if event_replay_store is not None:
                with suppress(Exception):
                    event_replay_store.delete_session(session_id)
        return BulkDeleteResult(deleted=deleted)

    @router.post("/sessions/{session_id}/star")
    async def star_session(
        session_id: str, principal: Principal = Depends(require)
    ) -> Resolved:
        _owned_or_404(session_id, principal)
        await host.set_session_starred(session_id, True)
        return Resolved(resolved=True)

    @router.delete("/sessions/{session_id}/star")
    async def unstar_session(
        session_id: str, principal: Principal = Depends(require)
    ) -> Resolved:
        _owned_or_404(session_id, principal)
        await host.set_session_starred(session_id, False)
        return Resolved(resolved=True)

    @router.post("/sessions/{session_id}/context")
    async def bind_session_context(
        session_id: str,
        body: SessionContextBindRequest,
        principal: Principal = Depends(require),
    ) -> SessionContextView:
        _owned_or_404(session_id, principal)
        try:
            binding = await host.bind_session_context(
                session_id, body.context_id, principal_id=principal.id
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None
        return SessionContextView.from_binding(binding)

    @router.post("/sessions/{session_id}/fork")
    async def fork_session(
        session_id: str,
        body: ForkSessionRequest,
        principal: Principal = Depends(require),
    ) -> OpenedSession:
        _owned_or_404(session_id, principal)
        try:
            fork_id = await host.fork_session(
                session_id,
                principal_id=principal.id,
                source_sequence=body.sequence,
                title=body.title,
                model=body.model,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None
        return OpenedSession(session_id=fork_id)

    @router.patch("/sessions/{session_id}")
    async def rename_session(
        session_id: str,
        body: RenameRequest,
        principal: Principal = Depends(require),
    ) -> Resolved:
        # Rename a session the caller owns (030); non-owner / unknown -> 404.
        _owned_or_404(session_id, principal)
        try:
            await host.set_session_title(session_id, body.title)
        except (KeyError, RuntimeError):
            raise HTTPException(status_code=404, detail="not found") from None
        return Resolved(resolved=True)

    @router.delete("/sessions/{session_id}")
    async def delete_session(
        session_id: str, principal: Principal = Depends(require)
    ) -> Resolved:
        # Delete a session the caller owns (030): cancel a live entry first, then
        # remove the durable records. Non-owner / unknown -> 404.
        _owned_or_404(session_id, principal)
        entry = sessions.get(session_id)
        if entry is not None:
            entry.session.cancel()
            entry.close.set()
        host.delete_session(session_id)
        if event_replay_store is not None:
            with suppress(Exception):
                event_replay_store.delete_session(session_id)
        return Resolved(resolved=True)

    @router.get("/sessions/{session_id}/history")
    async def session_history(
        session_id: str, principal: Principal = Depends(require)
    ) -> list[HistoryEntryView]:
        _owned_or_404(session_id, principal)
        try:
            entries = host.history_snapshot(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None
        return [
            HistoryEntryView(role=entry.role, block_count=len(entry.blocks))
            for entry in entries
        ]

    @router.get("/sessions/{session_id}/cost")
    async def session_cost(
        session_id: str, principal: Principal = Depends(require)
    ) -> SessionCostView:
        # 064: a session's accumulated USD (owner-only; 404 otherwise). null when no
        # budget is configured ("not tracked"). Read-only; mirrors inspection routes.
        _owned_or_404(session_id, principal)
        try:
            spent = host.session_cost(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None
        return SessionCostView.of(session_id, spent)

    @router.get("/cost/monthly")
    async def monthly_cost(
        principal: Principal = Depends(require),
    ) -> MonthlyCostView:
        # 064: the CALLER's own current-month USD (never another principal's). null
        # when no durable ledger is configured. Read-only.
        month = datetime.now(UTC).strftime("%Y-%m")
        spent = host.monthly_spend(principal.id)
        return MonthlyCostView.of(principal.id, month, spent)

    @router.post("/commands")
    async def run_command(
        body: CommandRequest, principal: Principal = Depends(require)
    ) -> CommandResultView:
        # 065: dispatch a backend slash command against EXISTING host seams (never
        # the gateway/event bus). Session-scoped commands (/cost, /compact) require
        # ownership; the result is public-safe (the caller's own data only).
        line = body.command if body.command.startswith("/") else f"/{body.command}"
        name = line[1:].strip().split(" ", 1)[0].lower()
        if name in ("cost", "compact"):
            if body.session_id is None:
                raise HTTPException(status_code=400, detail="session_id required")
            _owned_or_404(body.session_id, principal)
        ctx = CommandContext(
            host=host,
            principal_id=principal.id,
            session_id=body.session_id,
            models=tuple(catalog),
        )
        result = command_registry.dispatch(line, ctx)
        return CommandResultView(kind=result.kind, text=result.text)

    @router.post("/sessions/{session_id}/resume")
    async def resume_session(
        session_id: str, principal: Principal = Depends(require)
    ) -> Resolved:
        _owned_or_404(session_id, principal)
        try:
            await host.resume(session_id)
        except (KeyError, RuntimeError):
            raise HTTPException(status_code=404, detail="not found") from None
        return Resolved(resolved=True)

    @router.get("/sessions/{session_id}/artifacts/{reference}")
    async def get_artifact(
        session_id: str, reference: str, principal: Principal = Depends(require)
    ) -> ArtifactContent:
        _owned_or_404(session_id, principal)
        content = host.retrieve_artifact(session_id, reference)
        if content is None:
            raise HTTPException(status_code=404, detail="not found")
        return ArtifactContent(reference=reference, content=content)

    # --- 027: read-only inspection (skills / tools / MCP / memory) ----------

    @router.get("/inspect/skills")
    async def get_skills(principal: Principal = Depends(require)) -> SkillsResponse:
        return SkillsResponse(
            skills=[SkillView.from_info(info) for info in host.inspect_skills()],
            problems=list(host.skill_problems),
        )

    @router.get("/inspect/tools")
    async def get_tools(principal: Principal = Depends(require)) -> list[ToolView]:
        return [ToolView.from_info(info) for info in host.inspect_tools()]

    @router.get("/inspect/mcp")
    async def get_mcp(principal: Principal = Depends(require)) -> list[McpServerView]:
        return [McpServerView.from_info(info) for info in host.inspect_mcp()]

    @router.get("/inspect/memory")
    async def get_memory(
        q: str | None = None, principal: Principal = Depends(require)
    ) -> list[MemoryEntryView]:
        return [MemoryEntryView.from_info(info) for info in host.inspect_memory(q)]

    # --- 075: capability management foundation ------------------------------

    @router.get("/capabilities/settings")
    async def get_capability_settings(
        principal: Principal = Depends(require),
    ) -> CapabilitySettingsStatusView:
        return CapabilitySettingsStatusView.from_status(
            host.capability_settings_status(principal_id=principal.id)
        )

    @router.get("/capabilities/memory")
    async def list_managed_memory(
        principal: Principal = Depends(require),
    ) -> list[ManagedMemoryView]:
        return [
            ManagedMemoryView.from_entry(entry)
            for entry in host.list_managed_memory(principal_id=principal.id)
        ]

    @router.post("/capabilities/memory")
    async def write_managed_memory(
        body: MemoryWriteRequest, principal: Principal = Depends(require)
    ) -> MemoryMutationResponse:
        result = host.write_managed_memory(
            name=body.name,
            kind=body.kind,
            description=body.description,
            content=body.content,
            principal_id=principal.id,
        )
        entry = None
        if result.ok and result.resource_id is not None:
            entry = ManagedMemoryView.from_entry(
                host.get_managed_memory(
                    result.resource_id,
                    principal_id=principal.id,
                )
            )
        return MemoryMutationResponse(
            result=CapabilityOperationResultView.from_result(result),
            entry=entry,
        )

    @router.get("/capabilities/memory/{memory_id}")
    async def get_managed_memory(
        memory_id: str, principal: Principal = Depends(require)
    ) -> ManagedMemoryDetailView:
        try:
            return ManagedMemoryDetailView.from_detail(
                host.get_managed_memory(memory_id, principal_id=principal.id)
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None

    @router.delete("/capabilities/memory/{memory_id}")
    async def delete_managed_memory(
        memory_id: str,
        confirm: bool = False,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        result = host.delete_managed_memory(
            memory_id,
            confirm=confirm,
            principal_id=principal.id,
        )
        return CapabilityOperationResultView.from_result(result)

    @router.get("/capabilities/skills")
    async def list_managed_skills(
        principal: Principal = Depends(require),
    ) -> list[ManagedSkillView]:
        return [
            ManagedSkillView.from_skill(skill)
            for skill in host.list_managed_skills(principal.id)
        ]

    @router.post("/capabilities/skills")
    async def write_managed_skill(
        body: SkillWriteRequest, principal: Principal = Depends(require)
    ) -> SkillMutationResponse:
        result = host.write_managed_skill(
            name=body.name,
            description=body.description,
            instructions=body.instructions,
            principal_id=principal.id,
        )
        skill = None
        if result.ok and result.resource_id is not None:
            skill = ManagedSkillView.from_skill(
                host.get_managed_skill(
                    result.resource_id,
                    principal_id=principal.id,
                )
            )
        return SkillMutationResponse(
            result=CapabilityOperationResultView.from_result(result),
            skill=skill,
        )

    @router.post("/capabilities/skills/import")
    async def import_managed_skill(
        body: SkillImportRequest, principal: Principal = Depends(require)
    ) -> SkillMutationResponse:
        result = host.import_managed_skill(
            body.definition,
            principal_id=principal.id,
        )
        skill = None
        if result.ok and result.resource_id is not None:
            skill = ManagedSkillView.from_skill(
                host.get_managed_skill(
                    result.resource_id,
                    principal_id=principal.id,
                )
            )
        return SkillMutationResponse(
            result=CapabilityOperationResultView.from_result(result),
            skill=skill,
        )

    @router.get("/capabilities/skills/{skill_id}")
    async def get_managed_skill(
        skill_id: str, principal: Principal = Depends(require)
    ) -> ManagedSkillDetailView:
        try:
            return ManagedSkillDetailView.from_detail(
                host.get_managed_skill(skill_id, principal_id=principal.id)
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None

    @router.delete("/capabilities/skills/{skill_id}")
    async def delete_managed_skill(
        skill_id: str,
        confirm: bool = False,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        result = host.delete_managed_skill(
            skill_id,
            confirm=confirm,
            principal_id=principal.id,
        )
        return CapabilityOperationResultView.from_result(result)

    @router.get("/capabilities/mcp")
    async def list_managed_mcp(
        principal: Principal = Depends(require),
    ) -> list[ManagedMcpConfigurationView]:
        return [
            ManagedMcpConfigurationView.from_config(config)
            for config in host.list_managed_mcp(principal.id)
        ]

    @router.post("/capabilities/mcp")
    async def upsert_managed_mcp(
        body: McpConfigurationWriteRequest,
        principal: Principal = Depends(require),
    ) -> McpMutationResponse:
        result = await host.upsert_managed_mcp(
            name=body.name,
            transport=body.transport,
            url=body.url,
            command=body.command,
            args=body.args,
            principal_id=principal.id,
        )
        config = next(
            (
                ManagedMcpConfigurationView.from_config(config)
                for config in host.list_managed_mcp(principal.id)
                if config.id == result.resource_id
            ),
            None,
        )
        return McpMutationResponse(
            result=CapabilityOperationResultView.from_result(result),
            config=config,
        )

    @router.get("/capabilities/mcp/{mcp_id}")
    async def get_managed_mcp(
        mcp_id: str,
        principal: Principal = Depends(require),
    ) -> ManagedMcpConfigurationView:
        try:
            return ManagedMcpConfigurationView.from_config(
                host.get_managed_mcp(mcp_id, principal_id=principal.id)
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None

    @router.post("/capabilities/mcp/{mcp_id}/reconnect")
    async def reconnect_managed_mcp(
        mcp_id: str,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        result = await host.reconnect_managed_mcp(mcp_id, principal_id=principal.id)
        return CapabilityOperationResultView.from_result(result)

    @router.delete("/capabilities/mcp/{mcp_id}")
    async def delete_managed_mcp(
        mcp_id: str,
        confirm: bool = False,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        result = await host.delete_managed_mcp(
            mcp_id, confirm=confirm, principal_id=principal.id
        )
        return CapabilityOperationResultView.from_result(result)

    @router.get("/capabilities/contexts")
    async def list_workspace_contexts(
        principal: Principal = Depends(require),
    ) -> list[WorkspaceContextView]:
        return [
            WorkspaceContextView.from_context(context)
            for context in host.list_workspace_contexts(principal.id)
        ]

    @router.post("/capabilities/contexts")
    async def upsert_workspace_context(
        body: WorkspaceContextWriteRequest,
        principal: Principal = Depends(require),
    ) -> WorkspaceContextMutationResponse:
        result = host.upsert_workspace_context(
            name=body.name,
            description=body.description,
            workspace_label=body.workspace_label,
            principal_id=principal.id,
        )
        context = None
        if result.ok and result.resource_id is not None:
            context = WorkspaceContextView.from_context(
                host.get_workspace_context(
                    result.resource_id, principal_id=principal.id
                )
            )
        return WorkspaceContextMutationResponse(
            result=CapabilityOperationResultView.from_result(result),
            context=context,
        )

    @router.get("/capabilities/contexts/{context_id}")
    async def get_workspace_context(
        context_id: str,
        principal: Principal = Depends(require),
    ) -> WorkspaceContextView:
        try:
            return WorkspaceContextView.from_context(
                host.get_workspace_context(context_id, principal_id=principal.id)
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None

    @router.delete("/capabilities/contexts/{context_id}")
    async def delete_workspace_context(
        context_id: str,
        confirm: bool = False,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        result = host.delete_workspace_context(
            context_id, confirm=confirm, principal_id=principal.id
        )
        return CapabilityOperationResultView.from_result(result)

    @router.get("/capabilities/schedules")
    async def list_managed_schedules(
        principal: Principal = Depends(require),
    ) -> list[ManagedScheduleView]:
        return [
            ManagedScheduleView.from_schedule(schedule)
            for schedule in host.list_managed_schedules(principal.id)
        ]

    @router.post("/capabilities/schedules")
    async def upsert_managed_schedule(
        body: ScheduleWriteRequest,
        principal: Principal = Depends(require),
    ) -> ScheduleMutationResponse:
        result = host.upsert_managed_schedule(
            name=body.name,
            description=body.description,
            trigger=body.trigger,
            instruction=body.instruction,
            enabled=body.enabled,
            principal_id=principal.id,
        )
        schedule = None
        if result.ok and result.resource_id is not None:
            schedule = ManagedScheduleView.from_schedule(
                host.get_managed_schedule(result.resource_id, principal_id=principal.id)
            )
        return ScheduleMutationResponse(
            result=CapabilityOperationResultView.from_result(result),
            schedule=schedule,
        )

    @router.get("/capabilities/schedules/{schedule_id}")
    async def get_managed_schedule(
        schedule_id: str,
        principal: Principal = Depends(require),
    ) -> ManagedScheduleView:
        try:
            return ManagedScheduleView.from_schedule(
                host.get_managed_schedule(schedule_id, principal_id=principal.id)
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None

    @router.post("/capabilities/schedules/{schedule_id}/run-now")
    async def run_managed_schedule_now(
        schedule_id: str,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        try:
            result = host.run_managed_schedule_now(
                schedule_id, principal_id=principal.id
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None
        return CapabilityOperationResultView.from_result(result)

    @router.post("/capabilities/schedules/{schedule_id}/enable")
    async def enable_managed_schedule(
        schedule_id: str,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        result = host.enable_managed_schedule(schedule_id, principal_id=principal.id)
        return CapabilityOperationResultView.from_result(result)

    @router.post("/capabilities/schedules/{schedule_id}/disable")
    async def disable_managed_schedule(
        schedule_id: str,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        result = host.disable_managed_schedule(schedule_id, principal_id=principal.id)
        return CapabilityOperationResultView.from_result(result)

    @router.delete("/capabilities/schedules/{schedule_id}")
    async def delete_managed_schedule(
        schedule_id: str,
        confirm: bool = False,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        result = host.delete_managed_schedule(
            schedule_id, confirm=confirm, principal_id=principal.id
        )
        return CapabilityOperationResultView.from_result(result)

    @router.get("/capabilities/model-default")
    async def get_model_default(
        principal: Principal = Depends(require),
    ) -> ModelDefaultView:
        available = {model_id: entry.label for model_id, entry in catalog.items()}
        return ModelDefaultView.from_default(
            host.model_default(
                principal.id,
                available_models=available,
            )
        )

    @router.post("/capabilities/model-default")
    async def set_model_default(
        body: ModelDefaultWriteRequest,
        principal: Principal = Depends(require),
    ) -> ModelDefaultMutationResponse:
        available = {model_id: entry.label for model_id, entry in catalog.items()}
        result = host.set_model_default(
            body.model_id,
            available_models=available,
            principal_id=principal.id,
        )
        return ModelDefaultMutationResponse(
            result=CapabilityOperationResultView.from_result(result),
            default=ModelDefaultView.from_default(
                host.model_default(
                    principal.id,
                    available_models=available,
                )
            ),
        )

    @router.delete("/capabilities/model-default")
    async def clear_model_default(
        principal: Principal = Depends(require),
    ) -> ModelDefaultMutationResponse:
        available = {model_id: entry.label for model_id, entry in catalog.items()}
        result = host.clear_model_default(principal_id=principal.id)
        return ModelDefaultMutationResponse(
            result=CapabilityOperationResultView.from_result(result),
            default=ModelDefaultView.from_default(
                host.model_default(
                    principal.id,
                    available_models=available,
                )
            ),
        )

    # --- 028: model catalog + file uploads ----------------------------------

    @router.get("/models")
    async def list_models(
        principal: Principal = Depends(require),
    ) -> list[ModelInfo]:
        return [
            ModelInfo(
                id=mid,
                label=entry.label,
                accepts_media=entry.accepts_media,
                supports_structured_output=entry.supports_structured_output,
            )
            for mid, entry in catalog.items()
        ]

    @router.post("/uploads")
    async def upload_file(
        request: Request,
        name: str = "upload",
        principal: Principal = Depends(require),
    ) -> UploadResult:
        if uploads is None:
            raise HTTPException(status_code=404, detail="uploads not configured")
        data = await request.body()
        try:
            stored = uploads.save(principal.id, name, data)
        except UploadTooLarge as exc:
            raise HTTPException(status_code=413, detail="upload too large") from exc
        return UploadResult(reference=stored.reference, name=stored.name)

    app.include_router(router)
    return app
