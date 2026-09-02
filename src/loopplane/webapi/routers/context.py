"""Shared state and helper contracts for WebAPI domain routers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from loopplane.commands import CommandRegistry
from loopplane.host import ContentBlock, LoopPlaneHost
from loopplane.webapi.admission import (
    AdmissionCoordinator,
    bound_run,
    outstanding_cap_for,
)
from loopplane.webapi.auth import Principal
from loopplane.webapi.live import LiveTicketStore
from loopplane.webapi.models import RunRequest
from loopplane.webapi.pool import TenantHostPool
from loopplane.webapi.replay import EventReplayStore
from loopplane.webapi.sessions import SessionEntry
from loopplane.webapi.uploads import UploadStore


@dataclass(frozen=True)
class ModelHost:
    """A model-catalog entry backed by one host."""

    label: str
    host: LoopPlaneHost
    accepts_media: bool = False
    supports_structured_output: bool = False


RequirePrincipal = Callable[[str | None], Awaitable[Principal]]
SelectHost = Callable[[str | None], tuple[LoopPlaneHost, bool, bool]]
ResolveHost = Callable[[str | None, Principal], tuple[LoopPlaneHost, bool, bool]]
ReadUploadAvailable = Callable[[LoopPlaneHost], bool]
BuildBlocks = Callable[[RunRequest, str, bool, bool], list[ContentBlock]]
CheckOutputSchema = Callable[[dict[str, object] | None, bool], None]
RequireSession = Callable[[str, Principal], SessionEntry]
OwnedOr404 = Callable[[str, Principal], None]
AgentControlHostOr404 = Callable[[str, Principal], LoopPlaneHost]


@dataclass(frozen=True)
class RouterState:
    """The single owner-backed state and helper set shared by route modules."""

    api_prefix: str
    host: LoopPlaneHost
    require: RequirePrincipal
    sessions: dict[str, SessionEntry]
    session_hosts: dict[str, tuple[str, LoopPlaneHost]]
    live_tickets: LiveTicketStore
    catalog: dict[str, ModelHost]
    command_registry: CommandRegistry
    uploads: UploadStore | None
    max_image_bytes: int
    sse_replay_buffer: int
    event_replay_store: EventReplayStore | None
    event_replay_limit: int
    event_replay_poll_interval_seconds: float
    event_replay_idle_polls: int | None
    host_pool: TenantHostPool | None
    admission: AdmissionCoordinator | None
    select: SelectHost
    resolve: ResolveHost
    read_upload_available: ReadUploadAvailable
    build_blocks: BuildBlocks
    check_output_schema: CheckOutputSchema
    require_session: RequireSession
    owned_or_404: OwnedOr404
    agent_control_host_or_404: AgentControlHostOr404

    def drive_bound(
        self,
        principal_id: str,
        host: LoopPlaneHost,
        *,
        hold_local: bool = True,
    ) -> AbstractAsyncContextManager[None]:
        """Cluster grant + 061-path local in-flight for this principal."""

        return bound_run(
            admission=self.admission,
            pool=self.host_pool,
            principal_id=principal_id,
            outstanding_cap=outstanding_cap_for(host),
            hold_local=hold_local,
        )
