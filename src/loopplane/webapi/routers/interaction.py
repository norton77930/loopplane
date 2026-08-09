"""Interaction routes for the WebAPI app factory."""

from __future__ import annotations

from contextlib import nullcontext, suppress

import anyio
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    WebSocket,
)
from fastapi.responses import StreamingResponse
from starlette.websockets import WebSocketDisconnect

from loopplane.events import RuntimeEvent
from loopplane.host import (
    PlatformFairnessRejected,
)
from loopplane.webapi.auth import (
    Principal,
)
from loopplane.webapi.live import (
    latest_sequence,
    replay_event_messages,
)
from loopplane.webapi.models import (
    AgentControlProjectionView,
    LiveClientMessage,
    LiveTicketView,
    OpenedSession,
    QuestionAnswer,
    Resolved,
    RunRequest,
    RunResult,
    SessionAnswer,
)
from loopplane.webapi.replay import EventReplayRecord
from loopplane.webapi.routers.context import RouterState
from loopplane.webapi.sessions import (
    reconnect_stream,
    replay_store_stream,
    run_session,
)
from loopplane.webapi.streaming import run_event_stream


async def _discard(event: RuntimeEvent) -> None:
    return None


def build_router(state: RouterState, app: FastAPI) -> APIRouter:
    router = APIRouter(prefix=state.api_prefix)
    host = state.host
    require = state.require
    sessions = state.sessions
    session_hosts = state.session_hosts
    live_tickets = state.live_tickets
    host_pool = state.host_pool
    sse_replay_buffer = state.sse_replay_buffer
    event_replay_store = state.event_replay_store
    event_replay_limit = state.event_replay_limit
    event_replay_poll_interval_seconds = state.event_replay_poll_interval_seconds
    event_replay_idle_polls = state.event_replay_idle_polls
    _resolve = state.resolve
    _read_upload_available = state.read_upload_available
    _build_blocks = state.build_blocks
    _check_output_schema = state.check_output_schema
    _require = state.require_session
    _owned_or_404 = state.owned_or_404
    _agent_control_host_or_404 = state.agent_control_host_or_404

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

    return router
