"""The provider handoff is a two-language contract (Unit A).

Electron main decrypts the credential and hands it to the sidecar as spawn
environment; the Python sidecar reads it back. Nothing at runtime would notice a
rename on one side — the app would silently fall back to the demo model — so the
names and the provider ids are pinned from both sources here.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SIDECAR = REPO / "apps" / "desktop" / "sidecar"
VAULT_TS = REPO / "apps" / "desktop" / "electron" / "provider-credentials.ts"
MAIN_TS = REPO / "apps" / "desktop" / "electron" / "main.ts"
SETTINGS_TSX = REPO / "apps" / "desktop" / "src" / "components" / "ProviderSettings.tsx"

sys.path.insert(0, str(SIDECAR))

from bridge import (  # noqa: E402
    DESKTOP_API_KEY_ENV,
    DESKTOP_MODEL_ID_ENV,
    DESKTOP_PROVIDER_ENV,
    DESKTOP_PROVIDERS,
)


def _vault_source() -> str:
    return VAULT_TS.read_text(encoding="utf-8")


def test_the_typescript_vault_names_the_variables_the_sidecar_reads() -> None:
    source = _vault_source()
    block = re.search(
        r"export const PROVIDER_ENV = \{(.*?)\} as const;", source, re.DOTALL
    )
    assert block is not None, "PROVIDER_ENV is no longer a literal object"
    declared = dict(re.findall(r'(\w+):\s*"([^"]+)"', block.group(1)))

    # The TS field is `key`, not `apiKey`: `tests/contract/test_public_safety.py`
    # reads `apiKey: "<12+ chars>"` as an assigned secret, even when the value is
    # only a variable name.
    assert declared == {
        "provider": DESKTOP_PROVIDER_ENV,
        "modelId": DESKTOP_MODEL_ID_ENV,
        "key": DESKTOP_API_KEY_ENV,
    }


def test_both_sides_offer_the_same_provider_ids() -> None:
    source = _vault_source()
    block = re.search(
        r"export const DESKTOP_PROVIDER_IDS = \[(.*?)\] as const;", source, re.DOTALL
    )
    assert block is not None, "DESKTOP_PROVIDER_IDS is no longer a literal array"
    declared = re.findall(r'"([^"]+)"', block.group(1))

    assert declared == list(DESKTOP_PROVIDERS)


def test_the_settings_screen_offers_exactly_the_supported_providers() -> None:
    """A third copy of the table lives in the renderer; drift is silent there."""

    source = SETTINGS_TSX.read_text(encoding="utf-8")
    block = re.search(
        r"const PROVIDERS: readonly ProviderOption\[\] = \[(.*?)\n\];",
        source,
        re.DOTALL,
    )
    assert block is not None, "PROVIDERS is no longer a literal array"
    declared = re.findall(r'\{\s*id:\s*"([^"]+)"', block.group(1))
    keyless = re.findall(r'id:\s*"([^"]+)"[^}]*keyless:\s*true', block.group(1))

    assert declared == list(DESKTOP_PROVIDERS)
    assert set(keyless) == {
        provider
        for provider, spec in DESKTOP_PROVIDERS.items()
        if not spec.requires_key
    }


def test_only_ollama_is_keyless_on_both_sides() -> None:
    source = _vault_source()
    block = re.search(
        r"const KEYLESS_PROVIDERS: ReadonlySet<string> = new Set\(\[(.*?)\]\);",
        source,
        re.DOTALL,
    )
    assert block is not None, "KEYLESS_PROVIDERS is no longer a literal set"
    declared = set(re.findall(r'"([^"]+)"', block.group(1)))

    assert declared == {
        provider
        for provider, spec in DESKTOP_PROVIDERS.items()
        if not spec.requires_key
    }


def test_a_packaged_smoke_run_never_receives_a_real_credential() -> None:
    """The smoke drives a scripted model; a leaked key there would be recorded."""

    source = MAIN_TS.read_text(encoding="utf-8")
    guarded = "...(smoke ? {} : providerSpawnEnv(readProviderConfig(vaultDeps())))"

    assert guarded in source


def test_the_credential_never_lands_in_the_profile_root() -> None:
    """Backups whitelist the profile, so staying outside it is what excludes it."""

    source = _vault_source()

    assert "LOOPPLANE_PROFILE_ROOT" not in source
    assert "userDataDir" in source
