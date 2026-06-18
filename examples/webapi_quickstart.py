"""Quickstart: drive the LoopPlane web/API host in-process (feature 011).

Public-safe and credential-free: build a host over a scripted fake model, mount it
with ``create_app`` behind a simple injected authenticator, and drive an auth
check + a run + a session listing through Starlette's in-process ``TestClient`` —
no real socket and no network.

Run: ``python examples/webapi_quickstart.py``
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from loopplane.host import LoopPlaneHost, RuntimeConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement
from loopplane.webapi import Principal, create_app

CREDENTIAL = "let-me-in"


async def authenticator(credential: str | None) -> Principal | None:
    """A minimal injected verifier — map the one demo credential to a principal,
    deny all else (the host ships no credential store; the embedder injects this).

    The web/API auth boundary identifies the caller (a ``Principal``) rather than
    returning a bool (022); a real deployment injects its own OAuth/JWT verifier."""

    return Principal(id="demo-user") if credential == CREDENTIAL else None


def build_demo_host(scope: Path) -> LoopPlaneHost:
    model = ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text="hello from the loop")])],
        context_capacity=100_000,
    )
    return LoopPlaneHost(RuntimeConfig(model=model), working_scope=scope)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        host = build_demo_host(Path(tmp))
        app = create_app(host, authenticator=authenticator)
        client = TestClient(app)

        # 1) No credential -> denied by the default-deny boundary.
        denied = client.post("/v1/runs", json={"prompt": "please run"})
        print("no credential ->", denied.status_code)  # 401

        # 2) Authenticated run -> a metadata-only outcome (no conversation text).
        auth = {"Authorization": CREDENTIAL}
        run = client.post("/v1/runs", json={"prompt": "please run"}, headers=auth)
        outcome = run.json()
        print(
            "run ->",
            run.status_code,
            "| reason:",
            outcome["termination_reason"],
            "| turns:",
            outcome["turns_taken"],
        )
        print("history (metadata-only):", outcome["history"])

        # 3) Inspect sessions (read-only).
        listing = client.get("/v1/sessions", headers=auth)
        print("sessions ->", listing.status_code, "| count:", len(listing.json()))


if __name__ == "__main__":
    main()
