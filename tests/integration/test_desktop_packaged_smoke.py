"""Packaged Windows UI Automation driver contract (078 T083 RED)."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "smoke-desktop-artifact.ps1"
MAIN_SOURCE = REPO_ROOT / "apps" / "desktop" / "electron" / "main.ts"
SIDECAR_MAIN = REPO_ROOT / "apps" / "desktop" / "sidecar" / "__main__.py"
SIDECAR_BRIDGE = REPO_ROOT / "apps" / "desktop" / "sidecar" / "bridge.py"
SHELL_SOURCE = (
    REPO_ROOT
    / "packages"
    / "cowork-presentation"
    / "src"
    / "components"
    / "CoworkShell.tsx"
)
UNAVAILABLE_SOURCE = (
    REPO_ROOT
    / "packages"
    / "cowork-presentation"
    / "src"
    / "components"
    / "RuntimeUnavailable.tsx"
)

UIA_LOCATORS: tuple[tuple[str, str], ...] = (
    ("LoopPlane smoke runtime status", "Group"),
    ("LoopPlane smoke new session", "Button"),
    ("LoopPlane smoke prompt", "Edit"),
    ("LoopPlane smoke submit", "Button"),
    ("LoopPlane smoke latest outcome", "Group"),
    ("LoopPlane smoke session list", "List"),
    ("LoopPlane smoke runtime diagnostic", "Group"),
)

PATH_SELFTEST_CASES: tuple[str, ...] = (
    "external-cwd-accepted",
    "reject-checkout-executable",
    "reject-checkout-scratch",
    "reject-checkout-evidence",
    "reject-checkout-profile",
    "reject-checkout-cwd",
    "reject-reparse-layout",
    "python-node-path-cleared",
)

FAILURE_SELFTEST_CASES: tuple[str, ...] = (
    "scenario-set-declared",
    "missing-sidecar-restored",
    "corrupt-sidecar-restored",
    "incompatible-sidecar-restored",
    "all-scenarios-use-fresh-profiles",
    "diagnostic-evidence-bounded",
    "runtime-diagnostic-placeholder-rejected",
    "runtime-diagnostic-failure-accepted",
    "restart-history-placeholder-rejected",
    "restart-history-session-accepted",
    "profile-inventory-detects-mutation",
    "orphan-observation-detects-process",
    "listener-observation-detects-listener",
    "continuous-observation-detects-transient-listener",
    "continuous-observation-detects-late-descendant",
    "continuous-observation-detects-post-close-orphan",
    "continuous-observation-survives-root-dispose",
)


# The driver is a Windows UI-Automation tool, and most of its self-tests are portable
# enough to run under pwsh on Linux. These three are not: they exercise NTFS
# junctions, the .NET Framework compiler behind `Add-Type -OutputAssembly`, and the
# `iphlpapi.dll` TCP listener table, none of which exist on Linux.
WINDOWS_ONLY_SELFTEST_CASES: frozenset[str] = frozenset(
    {
        "reject-reparse-layout",
        "incompatible-sidecar-restored",
        "listener-observation-detects-listener",
    }
)


def _powershell() -> str:
    return "pwsh" if sys.platform != "win32" else "powershell"


def _run_selftest(case: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    assert SMOKE_SCRIPT.is_file(), f"missing packaged smoke driver: {SMOKE_SCRIPT}"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "sentinel-pythonpath")
    env["NODE_PATH"] = str(REPO_ROOT / "sentinel-node-path")
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(SMOKE_SCRIPT),
            "-SelfTest",
            case,
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )


def test_packaged_smoke_driver_exists_at_canonical_path() -> None:
    assert SMOKE_SCRIPT.is_file()


def test_driver_uses_only_builtin_uia_and_normal_window_patterns() -> None:
    source = SMOKE_SCRIPT.read_text(encoding="utf-8")

    assert "UIAutomationClient" in source
    assert "UIAutomationTypes" in source
    assert "ValuePattern" in source
    assert "InvokePattern" in source
    assert "WindowPattern" in source
    assert "SetForegroundWindow" in source
    assert "SendKeys]::SendWait('{TAB}')" in source
    assert "$terminalDeadline = [datetime]::UtcNow.AddSeconds(10)" in source
    assert "$outcomeElement = Find-UniqueElement" in source
    assert "$sessionList = Find-UniqueElement" in source
    assert "loopplane packaged smoke" in source
    assert "loopplane-packaged-smoke-ok" in source
    assert "--loopplane-packaged-smoke=" in source
    for name, control_type in UIA_LOCATORS:
        assert name in source
        assert f"::{control_type}" in source

    forbidden = (
        "playwright",
        "appium",
        "winappdriver",
        "automationidproperty",
        "remote-debugging",
        "devtools",
        "chrome devtools protocol",
    )
    folded = source.casefold()
    assert not [marker for marker in forbidden if marker in folded]
    assert not re.search(r"(?i)\b(?:ipc|rpc)\b", source)


@pytest.mark.parametrize("case", PATH_SELFTEST_CASES + FAILURE_SELFTEST_CASES)
def test_driver_path_environment_and_failure_selftest(case: str) -> None:
    if case in WINDOWS_ONLY_SELFTEST_CASES and sys.platform != "win32":
        pytest.skip(f"{case} exercises a Windows-only mechanism")
    result = _run_selftest(case, Path(tempfile.gettempdir()))
    assert result.returncode == 0, (
        f"SelfTest {case!r} failed with {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert str(REPO_ROOT) not in result.stdout
    assert str(REPO_ROOT) not in result.stderr


def test_driver_declares_bounded_failure_scenario_matrix() -> None:
    source = SMOKE_SCRIPT.read_text(encoding="utf-8")

    assert 'Regex.Match(request, @"""id""\\s*:\\s*""' in source
    assert 'Console.WriteLine("{\\"jsonrpc\\"' in source
    assert 'Console.WriteLine("{\\\\\\"jsonrpc' not in source
    for scenario in (
        "happy",
        "missing-sidecar",
        "corrupt-sidecar",
        "incompatible-sidecar",
        "all",
    ):
        assert scenario in source
    assert "Invoke-SmokeScenario" in source
    assert "Restore-CopiedSidecar" in source
    assert "profile-" in source
    assert "runtime diagnostic" in source
    assert "AddSeconds(10)" in source
    assert "FileMode]::CreateNew" in source
    assert "Get-FileHash" in source
    assert "Get-ProfileInventory" in source
    assert "Test-LoopPlaneOrphanProcess" in source
    assert "Test-LocalTcpListener" in source
    assert "Start-ProcessNetworkObservation" in source
    assert "Stop-ProcessNetworkObservation" in source
    assert "foreach ($observation in $observations.ToArray())" in source
    assert "@($observations)" not in source
    assert "observation_samples" in source
    assert "failure_profile_unchanged" in source
    assert not re.search(r"orphan\s*=\s*\$false", source)
    assert not re.search(r"listener\s*=\s*\$false", source)
    assert "raw_error" not in source
    assert "exception_message" not in source


def test_sidecar_entrypoint_defers_model_import_until_after_initialize() -> None:
    code = (
        "import importlib.util, pathlib, sys; "
        "path = pathlib.Path(sys.argv[1]); "
        "sys.path.insert(0, str(path.parent)); "
        "spec = importlib.util.spec_from_file_location('desktop_sidecar_entry', path); "
        "module = importlib.util.module_from_spec(spec); "
        "spec.loader.exec_module(module); "
        "print('loopplane.model' in sys.modules)"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code, str(SIDECAR_MAIN)],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "False"


def test_packaged_application_exposes_bounded_smoke_composition() -> None:
    main = MAIN_SOURCE.read_text(encoding="utf-8")
    sidecar_main = (
        SIDECAR_MAIN.read_text(encoding="utf-8") if SIDECAR_MAIN.is_file() else ""
    )
    sidecar_bridge = (
        SIDECAR_BRIDGE.read_text(encoding="utf-8") if SIDECAR_BRIDGE.is_file() else ""
    )
    presentation = SHELL_SOURCE.read_text(encoding="utf-8")
    unavailable = (
        UNAVAILABLE_SOURCE.read_text(encoding="utf-8")
        if UNAVAILABLE_SOURCE.is_file()
        else ""
    )
    desktop_app = (REPO_ROOT / "apps" / "desktop" / "src" / "App.tsx").read_text(
        encoding="utf-8"
    )
    session_sidebar_path = (
        REPO_ROOT / "apps" / "desktop" / "src" / "components" / "SessionSidebar.tsx"
    )
    session_sidebar = session_sidebar_path.read_text(encoding="utf-8")

    assert "--loopplane-packaged-smoke=" in main
    assert "app.isPackaged" in main
    assert "setAccessibilitySupportEnabled(true)" in main
    assert 'app.commandLine.appendSwitch("enable-features", "UiaProvider")' in main
    assert "LOOPPLANE_PACKAGED_SMOKE_PROFILE" in main
    assert "LOOPPLANE_PACKAGED_SMOKE_SCENARIO" in main
    assert "LOOPPLANE_PACKAGED_SMOKE_SCENARIO: smoke?.scenario" in main
    assert 'join(app.getPath("userData"), "profile")' in main
    assert "(app.isPackaged" in main
    assert (
        "smoke?.profileRoot ??\n        process.env.LOOPPLANE_PROFILE_ROOT" not in main
    )
    assert 'new URL("../.desktop-profile", import.meta.url)' not in main
    assert "ScriptedModel" in sidecar_main
    for scenario in (
        "happy",
        "missing-sidecar",
        "corrupt-sidecar",
        "incompatible-sidecar",
    ):
        assert scenario in main
        assert scenario in sidecar_bridge
    assert "loopplane-packaged-smoke-ok" in presentation
    combined = presentation + unavailable + desktop_app + session_sidebar
    for name, _control_type in UIA_LOCATORS:
        assert name in combined

    folded_main = main.casefold()
    folded_presentation = combined.casefold()
    for forbidden in (
        "remote-debugging",
        "devtools",
        "automationid",
        "http.createserver",
        "net.createserver",
    ):
        assert forbidden not in folded_main
        assert forbidden not in folded_presentation
    assert "LOOPPLANE_PACKAGED_SMOKE_PROFILE" not in combined
    assert "LOOPPLANE_PACKAGED_SMOKE_SCENARIO" not in combined
