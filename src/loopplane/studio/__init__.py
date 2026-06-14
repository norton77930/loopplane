"""LoopPlane Desktop / Studio Host (feature 012-loopplane-desktop-or-studio-host).

A local, in-process developer experience over the public Host Application
Interface (:mod:`loopplane.host`): a developer-console core (command →
metadata-only view model), a local session manager, and a sidecar host contract.
It embeds a ``LoopPlaneHost``; it drives no runtime internals, executes no tool,
and re-emits no live event bus (Constitution V & VI). No GUI / network / OS
process spawning — those are reserved extension points.
"""

from __future__ import annotations

__all__: list[str] = []
