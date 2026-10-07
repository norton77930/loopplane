"""The path policy — confining a tool's path argument to an allowed root
(contracts/policies.md; FR-020-FR-021).

Containment is a deterministic **lexical** check (POSIX-style ``.``/``..``
resolution, no filesystem access): a path that escapes the root via traversal or
an absolute path, or a missing/non-string argument, is denied.
"""

from __future__ import annotations

import posixpath
from typing import TYPE_CHECKING

from loopplane.governance.base import allow, as_decider, deny

if TYPE_CHECKING:
    from loopplane.approval import PolicyDecider, PolicyVerdict
    from loopplane.model import ToolCallRequest, ToolDescriptor


def path_policy(allowed_root: str, *, key: str = "path") -> PolicyDecider:
    """Deny a call whose ``input[key]`` path escapes ``allowed_root`` (traversal or
    absolute), or is missing/non-string; allow a contained path (FR-020, FR-021)."""

    root = posixpath.normpath(allowed_root)

    def decide(call: ToolCallRequest, descriptor: ToolDescriptor) -> PolicyVerdict:
        value = call.input.get(key)
        if not isinstance(value, str) or not value:
            return deny(f"path policy: missing or invalid {key!r} argument")
        candidate = (
            posixpath.normpath(value)
            if posixpath.isabs(value)
            else posixpath.normpath(posixpath.join(root, value))
        )
        # normpath("/") is "/"; prefixing another slash yields "//", which
        # rejects every normal child and matches only the two-slash form.
        if root == "/":
            contained = candidate == "/" or (
                candidate.startswith("/") and not candidate.startswith("//")
            )
        else:
            contained = candidate == root or candidate.startswith(root + "/")
        if contained:
            return allow()
        return deny(f"path policy: {key!r} escapes the allowed root")

    return as_decider(decide)
