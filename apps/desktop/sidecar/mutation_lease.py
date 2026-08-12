"""In-process Profile Mutation Lease (078 US2/US5).

Single writer gate for durable profile/workspace/session mutations.
Backup/restore ownership blocks competing writers with public-safe busy.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


class MutationLeaseBusy(RuntimeError):
    public_code = "busy"

    def __init__(self, owner: str = "unknown") -> None:
        super().__init__("profile mutation lease busy")
        self.owner = owner


@dataclass
class ProfileMutationLease:
    """Process-local exclusive writer lease (not the OS profile lock).

    ``owner`` is only a diagnostic category.  Exclusivity is instead keyed by
    the main-owned mutation identity, so nested calls from one operation may
    proceed while a second request in the same category is rejected.
    """

    _owner: str | None = field(default=None, init=False, repr=False)
    _identity: str | None = field(default=None, init=False, repr=False)
    _depth: int = field(default=0, init=False, repr=False)
    _expiry_reaper: Callable[[], None] | None = field(
        default=None, init=False, repr=False
    )
    _reaping: bool = field(default=False, init=False, repr=False)

    @property
    def owner(self) -> str | None:
        return self._owner

    def held(self) -> bool:
        return self._owner is not None

    def held_by(self, owner: str, identity: str) -> bool:
        return self._owner == owner and self._identity == identity

    def set_expiry_reaper(self, reaper: Callable[[], None]) -> None:
        """Run one owner-provided expiry cleanup before writer admission."""

        self._expiry_reaper = reaper

    def _reap_expired(self) -> None:
        if self._expiry_reaper is None or self._reaping:
            return
        self._reaping = True
        try:
            self._expiry_reaper()
        finally:
            self._reaping = False

    def acquire(self, owner: str, identity: str | None = None) -> None:
        self._reap_expired()
        identity = identity or owner
        if self._owner is not None and (
            self._owner != owner or self._identity != identity
        ):
            raise MutationLeaseBusy(self._owner)
        self._owner = owner
        self._identity = identity
        self._depth += 1

    def release(self, owner: str | None = None, identity: str | None = None) -> None:
        if self._owner is None:
            return
        owner = owner or self._owner
        identity = identity or owner
        if self._owner != owner or self._identity != identity:
            raise MutationLeaseBusy(self._owner)
        self._depth -= 1
        if self._depth == 0:
            self._owner = None
            self._identity = None

    def require_free_or_owner(self, owner: str, identity: str | None = None) -> None:
        self._reap_expired()
        identity = identity or owner
        if self._owner is not None and (
            self._owner != owner or self._identity != identity
        ):
            raise MutationLeaseBusy(self._owner)

    def __enter__(self) -> ProfileMutationLease:
        return self

    def __exit__(self, *args: object) -> None:
        # Callers that acquire must release explicitly with owner/identity.
        return None
