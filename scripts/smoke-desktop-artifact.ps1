#Requires -Version 5.1
<#
.SYNOPSIS
  對已複製到 checkout 外的 Windows Desktop artifact 執行 UI Automation smoke。

.DESCRIPTION
  只使用 Windows 內建 UIAutomationClient/UIAutomationTypes，並以固定的
  Name/ControlType 配對操作一般可見控制項。T090 前不得對真實 artifact 執行。
#>
[CmdletBinding()]
param(
    [string] $AppExecutable,
    [string] $ScratchRoot,
    [string] $EvidencePath,

    [ValidateSet(
        'happy',
        'missing-sidecar',
        'corrupt-sidecar',
        'incompatible-sidecar',
        'all'
    )]
    [string] $Scenario = 'happy',

    [string] $SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:CheckoutRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot '..')
).TrimEnd([char[]]@('\', '/'))
$script:ForbiddenEnvironment = @(
    'PYTHONPATH',
    'NODE_PATH',
    'LOOPPLANE_STAGE_B_GITHUB_TOKEN',
    'GH_TOKEN',
    'GITHUB_TOKEN'
)
$script:SupportedScenarios = @(
    'happy',
    'missing-sidecar',
    'corrupt-sidecar',
    'incompatible-sidecar'
)

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class LoopPlaneSmokeWindow
{
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr window);
}

// Observation runs inside the fixed acceptance deadline, so it must cost
// microseconds: Win32_Process/Get-NetTCPConnection each cost ~1-3s per sample
// on a loaded desktop and would measure the harness instead of the artifact.
public static class LoopPlaneSmokeProcessTable
{
    private const uint TH32CS_SNAPPROCESS = 0x00000002;

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
    private struct PROCESSENTRY32
    {
        public uint dwSize;
        public uint cntUsage;
        public uint th32ProcessID;
        public IntPtr th32DefaultHeapID;
        public uint th32ModuleID;
        public uint cntThreads;
        public uint th32ParentProcessID;
        public int pcPriClassBase;
        public uint dwFlags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)]
        public string szExeFile;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr CreateToolhelp32Snapshot(uint flags, uint processId);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Ansi)]
    private static extern bool Process32First(IntPtr snapshot, ref PROCESSENTRY32 entry);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Ansi)]
    private static extern bool Process32Next(IntPtr snapshot, ref PROCESSENTRY32 entry);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);

    /// <summary>Flat [childPid, parentPid, ...] pairs for every visible process.</summary>
    public static int[] ParentPairs()
    {
        List<int> pairs = new List<int>();
        IntPtr snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        if (snapshot == IntPtr.Zero || snapshot == new IntPtr(-1))
        {
            throw new InvalidOperationException("process_snapshot_failed");
        }
        try
        {
            PROCESSENTRY32 entry = new PROCESSENTRY32();
            entry.dwSize = (uint)Marshal.SizeOf(typeof(PROCESSENTRY32));
            if (Process32First(snapshot, ref entry))
            {
                do
                {
                    pairs.Add((int)entry.th32ProcessID);
                    pairs.Add((int)entry.th32ParentProcessID);
                }
                while (Process32Next(snapshot, ref entry));
            }
        }
        finally
        {
            CloseHandle(snapshot);
        }
        return pairs.ToArray();
    }
}

public static class LoopPlaneSmokeTcpTable
{
    private const int AF_INET = 2;
    private const int AF_INET6 = 23;
    private const int TCP_TABLE_OWNER_PID_LISTENER = 3;
    private const uint NO_ERROR = 0;
    private const uint ERROR_NOT_SUPPORTED = 50;
    private const uint ERROR_INSUFFICIENT_BUFFER = 122;
    private const int IPV4_ROW_BYTES = 24;
    private const int IPV4_PID_OFFSET = 20;
    private const int IPV6_ROW_BYTES = 56;
    private const int IPV6_PID_OFFSET = 52;

    [DllImport("iphlpapi.dll", SetLastError = true)]
    private static extern uint GetExtendedTcpTable(
        IntPtr table,
        ref int size,
        bool order,
        int addressFamily,
        int tableClass,
        int reserved);

    /// <summary>Owning process IDs of every local TCP listener (IPv4 and IPv6).</summary>
    public static int[] ListenerProcessIds()
    {
        List<int> owners = new List<int>();
        Collect(AF_INET, IPV4_ROW_BYTES, IPV4_PID_OFFSET, owners);
        Collect(AF_INET6, IPV6_ROW_BYTES, IPV6_PID_OFFSET, owners);
        return owners.ToArray();
    }

    private static void Collect(int family, int rowBytes, int pidOffset, List<int> owners)
    {
        // The listener table can grow between sizing and reading; bound the retries.
        for (int attempt = 0; attempt < 4; attempt += 1)
        {
            int size = 0;
            uint status = GetExtendedTcpTable(
                IntPtr.Zero, ref size, false, family, TCP_TABLE_OWNER_PID_LISTENER, 0);
            if (status == ERROR_NOT_SUPPORTED)
            {
                return;
            }
            if (status != NO_ERROR && status != ERROR_INSUFFICIENT_BUFFER)
            {
                throw new InvalidOperationException("tcp_listener_table_failed");
            }
            if (size <= 0)
            {
                return;
            }
            IntPtr buffer = Marshal.AllocHGlobal(size);
            try
            {
                status = GetExtendedTcpTable(
                    buffer, ref size, false, family, TCP_TABLE_OWNER_PID_LISTENER, 0);
                if (status == ERROR_NOT_SUPPORTED)
                {
                    return;
                }
                if (status == ERROR_INSUFFICIENT_BUFFER)
                {
                    continue;
                }
                if (status != NO_ERROR)
                {
                    throw new InvalidOperationException("tcp_listener_table_failed");
                }
                int count = Marshal.ReadInt32(buffer);
                for (int index = 0; index < count; index += 1)
                {
                    IntPtr row = new IntPtr(buffer.ToInt64() + 4 + ((long)index * rowBytes));
                    owners.Add(Marshal.ReadInt32(row, pidOffset));
                }
                return;
            }
            finally
            {
                Marshal.FreeHGlobal(buffer);
            }
        }
        throw new InvalidOperationException("tcp_listener_table_failed");
    }
}
'@

function Get-CanonicalPath {
    param([Parameter(Mandatory = $true)][string] $Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw 'path_required'
    }
    return [System.IO.Path]::GetFullPath($Path).TrimEnd([char[]]@('\', '/'))
}

function Test-PathInside {
    param(
        [Parameter(Mandatory = $true)][string] $Candidate,
        [Parameter(Mandatory = $true)][string] $Root
    )

    $candidatePath = Get-CanonicalPath $Candidate
    $rootPath = Get-CanonicalPath $Root
    $comparison = if ($env:OS -eq 'Windows_NT') {
        [System.StringComparison]::OrdinalIgnoreCase
    } else {
        [System.StringComparison]::Ordinal
    }
    if ($candidatePath.Equals($rootPath, $comparison)) {
        return $true
    }
    $rootPrefix = $rootPath + [System.IO.Path]::DirectorySeparatorChar
    return $candidatePath.StartsWith($rootPrefix, $comparison)
}

function Assert-NoReparseChain {
    param([Parameter(Mandatory = $true)][string] $Path)

    $current = Get-CanonicalPath $Path
    while ($true) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'linked_layout_entry'
            }
        }
        $parent = Split-Path -Parent $current
        if ([string]::IsNullOrEmpty($parent) -or $parent -eq $current) {
            break
        }
        $current = $parent
    }
}

function Assert-ExternalLayout {
    param(
        [Parameter(Mandatory = $true)][string] $Executable,
        [Parameter(Mandatory = $true)][string] $Scratch,
        [Parameter(Mandatory = $true)][string] $Evidence,
        [Parameter(Mandatory = $true)][string] $GeneratedProfile,
        [Parameter(Mandatory = $true)][string] $CurrentDirectory
    )

    foreach ($candidate in @(
        $Executable,
        $Scratch,
        $Evidence,
        $GeneratedProfile,
        $CurrentDirectory
    )) {
        Assert-NoReparseChain $candidate
    }
    foreach ($candidate in @($Executable, $Scratch, $Evidence, $GeneratedProfile)) {
        if (Test-PathInside -Candidate $candidate -Root $script:CheckoutRoot) {
            throw 'checkout_path_forbidden'
        }
    }
    if (Test-PathInside -Candidate $CurrentDirectory -Root $script:CheckoutRoot) {
        throw 'checkout_cwd_forbidden'
    }
}

function Clear-AmbientBuildEnvironment {
    foreach ($name in $script:ForbiddenEnvironment) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
        Remove-Item -LiteralPath ("Env:" + $name) -ErrorAction SilentlyContinue
    }
}

function Assert-FailsWith {
    param(
        [Parameter(Mandatory = $true)][scriptblock] $Action,
        [Parameter(Mandatory = $true)][string] $Code
    )

    try {
        & $Action
        throw 'selftest_expected_failure'
    } catch {
        if ($_.Exception.Message -cne $Code) {
            throw
        }
    }
}

function Get-ScenarioProfile {
    param(
        [Parameter(Mandatory = $true)][string] $Root,
        [Parameter(Mandatory = $true)][string] $SmokeScenario
    )

    if ($script:SupportedScenarios -cnotcontains $SmokeScenario) {
        throw 'scenario_invalid'
    }
    return Get-CanonicalPath (Join-Path $Root ('profile-' + $SmokeScenario))
}

function Restore-CopiedSidecar {
    param(
        [Parameter(Mandatory = $true)][string] $SidecarPath,
        [Parameter(Mandatory = $true)][string] $BackupPath
    )

    if (-not (Test-Path -LiteralPath $BackupPath -PathType Leaf)) {
        throw 'sidecar_backup_missing'
    }
    if (Test-Path -LiteralPath $SidecarPath) {
        Remove-Item -LiteralPath $SidecarPath -Force
    }
    Move-Item -LiteralPath $BackupPath -Destination $SidecarPath
    if (-not (Test-Path -LiteralPath $SidecarPath -PathType Leaf)) {
        throw 'sidecar_restore_failed'
    }
}

function Get-ProfileInventory {
    param([Parameter(Mandatory = $true)][string] $Root)

    $canonicalRoot = Get-CanonicalPath $Root
    if (-not (Test-Path -LiteralPath $canonicalRoot -PathType Container)) {
        throw 'profile_inventory_root_missing'
    }
    $entries = New-Object System.Collections.Generic.List[string]
    foreach ($item in Get-ChildItem -LiteralPath $canonicalRoot -Force -Recurse) {
        $relative = $item.FullName.Substring($canonicalRoot.Length).TrimStart('\', '/')
        $kind = if ($item.PSIsContainer) { 'd' } else { 'f' }
        $digest = if ($item.PSIsContainer) {
            '-'
        } else {
            (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
        $entries.Add($kind + ':' + $relative.Replace('\', '/') + ':' + $digest)
    }
    return [string[]]($entries | Sort-Object)
}

function Test-InventoryEqual {
    param(
        [AllowEmptyCollection()][string[]] $Before = @(),
        [AllowEmptyCollection()][string[]] $After = @()
    )

    $beforeValues = [System.Collections.Generic.List[string]]::new()
    foreach ($value in @($Before)) {
        $beforeValues.Add([string]$value)
    }
    $afterValues = [System.Collections.Generic.List[string]]::new()
    foreach ($value in @($After)) {
        $afterValues.Add([string]$value)
    }
    if ($beforeValues.Count -ne $afterValues.Count) {
        return $false
    }
    return [System.Linq.Enumerable]::SequenceEqual($beforeValues, $afterValues)
}

function Get-DescendantProcessIds {
    param([Parameter(Mandatory = $true)][int] $RootProcessId)

    $descendants = New-Object System.Collections.Generic.HashSet[int]
    $pending = New-Object System.Collections.Generic.Queue[int]
    [void]$pending.Enqueue($RootProcessId)
    $pairs = [LoopPlaneSmokeProcessTable]::ParentPairs()
    while ($pending.Count -gt 0) {
        $parentId = $pending.Dequeue()
        for ($index = 0; $index -lt $pairs.Length; $index += 2) {
            if (
                [int]$pairs[$index + 1] -eq $parentId -and
                $descendants.Add([int]$pairs[$index])
            ) {
                $pending.Enqueue([int]$pairs[$index])
            }
        }
    }
    return [int[]]$descendants
}

function Test-LoopPlaneOrphanProcess {
    param([AllowEmptyCollection()][int[]] $ObservedProcessIds = @())

    foreach ($processId in $ObservedProcessIds) {
        if ($null -ne (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
            return $true
        }
    }
    return $false
}

function Test-LocalTcpListener {
    param([AllowEmptyCollection()][int[]] $ObservedProcessIds = @())

    $ids = @($ObservedProcessIds | Select-Object -Unique)
    if ($ids.Count -eq 0) {
        return $false
    }
    foreach ($owner in [LoopPlaneSmokeTcpTable]::ListenerProcessIds()) {
        if ($ids -contains [int]$owner) {
            return $true
        }
    }
    return $false
}

function Start-ProcessNetworkObservation {
    param(
        [Parameter(Mandatory = $true)][System.Diagnostics.Process] $Process,
        [Parameter(Mandatory = $true)] $ObservedProcessIds,
        [scriptblock] $DiscoverDescendants,
        [scriptblock] $DetectListener,
        [scriptblock] $DetectOrphan
    )

    $observation = [pscustomobject]@{
        RootProcessId = [int]$Process.Id
        ObservedProcessIds = $ObservedProcessIds
        ListenerObserved = $false
        Samples = 0
        DiscoverDescendants = $DiscoverDescendants
        DetectListener = $DetectListener
        DetectOrphan = $DetectOrphan
    }
    Update-ProcessNetworkObservation -Observation $observation
    return $observation
}

function Update-ProcessNetworkObservation {
    param([Parameter(Mandatory = $true)] $Observation)

    $rootId = [int]$Observation.RootProcessId
    $currentIds = @($rootId)
    try {
        if ($null -ne $Observation.DiscoverDescendants) {
            $currentIds += @(& $Observation.DiscoverDescendants $rootId)
        } else {
            $currentIds += @(Get-DescendantProcessIds $rootId)
        }
    } catch {
        # Process exit races are resolved by the accumulated ID set below.
    }
    foreach ($processId in $currentIds) {
        [void]$Observation.ObservedProcessIds.Add([int]$processId)
    }
    $listenerDetected = if ($null -ne $Observation.DetectListener) {
        & $Observation.DetectListener ([int[]]$Observation.ObservedProcessIds)
    } else {
        Test-LocalTcpListener -ObservedProcessIds ([int[]]$Observation.ObservedProcessIds)
    }
    if ($listenerDetected) {
        $Observation.ListenerObserved = $true
    }
    $Observation.Samples = [int]$Observation.Samples + 1
}

function Stop-ProcessNetworkObservation {
    param(
        [Parameter(Mandatory = $true)] $Observation,
        [int] $PostCloseMilliseconds = 500
    )

    $deadline = [datetime]::UtcNow.AddMilliseconds($PostCloseMilliseconds)
    do {
        Update-ProcessNetworkObservation -Observation $Observation
        if ([datetime]::UtcNow -lt $deadline) {
            Start-Sleep -Milliseconds 50
        }
    } while ([datetime]::UtcNow -lt $deadline)

    $orphanDetected = if ($null -ne $Observation.DetectOrphan) {
        & $Observation.DetectOrphan ([int[]]$Observation.ObservedProcessIds)
    } else {
        Test-LoopPlaneOrphanProcess `
            -ObservedProcessIds ([int[]]$Observation.ObservedProcessIds)
    }
    return [ordered]@{
        samples = [int]$Observation.Samples
        listener = [bool]$Observation.ListenerObserved
        orphan = [bool]$orphanDetected
    }
}

function Wait-ObservedProcessExit {
    param(
        [Parameter(Mandatory = $true)][System.Diagnostics.Process] $Process,
        [Parameter(Mandatory = $true)] $Observation,
        [Parameter(Mandatory = $true)][datetime] $Deadline
    )

    while ([datetime]::UtcNow -lt $Deadline) {
        Update-ProcessNetworkObservation -Observation $Observation
        if ($Process.HasExited) {
            return $true
        }
        Start-Sleep -Milliseconds 50
    }
    Update-ProcessNetworkObservation -Observation $Observation
    return $Process.HasExited
}

function Test-SidecarRestoreSelfTest {
    param([Parameter(Mandatory = $true)][string] $Variant)

    $root = Join-Path `
        ([System.IO.Path]::GetTempPath()) `
        ('loopplane-078-sidecar-selftest-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $root | Out-Null
    $sidecar = Join-Path $root 'loopplane-sidecar.exe'
    $backup = Join-Path $root 'loopplane-sidecar.accepted.exe'
    $accepted = [byte[]](1, 2, 3, 4, 5)
    try {
        [System.IO.File]::WriteAllBytes($sidecar, $accepted)
        Move-Item -LiteralPath $sidecar -Destination $backup
        if ($Variant -eq 'corrupt-sidecar') {
            [System.IO.File]::WriteAllBytes($sidecar, [byte[]](9, 8, 7))
        } elseif ($Variant -eq 'incompatible-sidecar') {
            New-IncompatibleSidecar -Path $sidecar
        }
        Restore-CopiedSidecar -SidecarPath $sidecar -BackupPath $backup
        $restored = [System.IO.File]::ReadAllBytes($sidecar)
        if ([System.Convert]::ToBase64String($restored) -cne `
            [System.Convert]::ToBase64String($accepted)) {
            throw 'sidecar_restore_bytes_changed'
        }
    } finally {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Test-DiagnosticEvidenceBounded {
    $sample = [ordered]@{
        scenario = 'missing-sidecar'
        state = 'diagnosed'
        elapsed_ms = 9999
        orphan = (Test-LoopPlaneOrphanProcess -ObservedProcessIds @())
        listener = (Test-LocalTcpListener -ObservedProcessIds @())
    }
    $json = $sample | ConvertTo-Json -Compress
    if ([System.Text.Encoding]::UTF8.GetByteCount($json) -gt 65536) {
        throw 'diagnostic_evidence_too_large'
    }
    if ($json -match '(?i)(exception|path|message)') {
        throw 'diagnostic_evidence_disclosure'
    }
}

function Test-RuntimeDiagnosticText {
    param([string] $Text)

    return (
        -not [string]::IsNullOrWhiteSpace($Text) -and
        $Text -notmatch '(?i)^no runtime diagnostic\.?$'
    )
}

function Test-RestartHistoryText {
    param([string] $Text)

    return (
        -not [string]::IsNullOrWhiteSpace($Text) -and
        $Text -notmatch '(?i)no sessions yet'
    )
}

function Invoke-PathSelfTest {
    param([Parameter(Mandatory = $true)][string] $Case)

    $externalRoot = Get-CanonicalPath ([System.IO.Path]::GetTempPath())
    $externalExecutable = Join-Path $externalRoot 'LoopPlane-selftest.exe'
    $externalScratch = Join-Path $externalRoot 'loopplane-smoke-selftest-scratch'
    $externalEvidence = Join-Path $externalRoot 'loopplane-smoke-selftest.json'
    $externalProfile = Join-Path $externalScratch 'profile-happy'
    $externalCwd = [System.IO.Directory]::GetCurrentDirectory()

    switch ($Case) {
        'external-cwd-accepted' {
            Assert-ExternalLayout `
                -Executable $externalExecutable `
                -Scratch $externalScratch `
                -Evidence $externalEvidence `
                -GeneratedProfile $externalProfile `
                -CurrentDirectory $externalCwd
        }
        'reject-checkout-executable' {
            Assert-FailsWith -Code 'checkout_path_forbidden' -Action {
                Assert-ExternalLayout `
                    -Executable (Join-Path $script:CheckoutRoot 'LoopPlane.exe') `
                    -Scratch $externalScratch `
                    -Evidence $externalEvidence `
                    -GeneratedProfile $externalProfile `
                    -CurrentDirectory $externalCwd
            }
        }
        'reject-checkout-scratch' {
            Assert-FailsWith -Code 'checkout_path_forbidden' -Action {
                Assert-ExternalLayout `
                    -Executable $externalExecutable `
                    -Scratch (Join-Path $script:CheckoutRoot 'scratch') `
                    -Evidence $externalEvidence `
                    -GeneratedProfile $externalProfile `
                    -CurrentDirectory $externalCwd
            }
        }
        'reject-checkout-evidence' {
            Assert-FailsWith -Code 'checkout_path_forbidden' -Action {
                Assert-ExternalLayout `
                    -Executable $externalExecutable `
                    -Scratch $externalScratch `
                    -Evidence (Join-Path $script:CheckoutRoot 'evidence.json') `
                    -GeneratedProfile $externalProfile `
                    -CurrentDirectory $externalCwd
            }
        }
        'reject-checkout-profile' {
            Assert-FailsWith -Code 'checkout_path_forbidden' -Action {
                Assert-ExternalLayout `
                    -Executable $externalExecutable `
                    -Scratch $externalScratch `
                    -Evidence $externalEvidence `
                    -GeneratedProfile (Join-Path $script:CheckoutRoot 'profile') `
                    -CurrentDirectory $externalCwd
            }
        }
        'reject-checkout-cwd' {
            Assert-FailsWith -Code 'checkout_cwd_forbidden' -Action {
                Assert-ExternalLayout `
                    -Executable $externalExecutable `
                    -Scratch $externalScratch `
                    -Evidence $externalEvidence `
                    -GeneratedProfile $externalProfile `
                    -CurrentDirectory $script:CheckoutRoot
            }
        }
        'reject-reparse-layout' {
            $reparseRoot = Join-Path `
                $externalRoot `
                ('loopplane-078-reparse-' + [guid]::NewGuid().ToString('N'))
            New-Item -ItemType Directory -Path $reparseRoot | Out-Null
            try {
                $linkedScratch = Join-Path $reparseRoot 'linked-scratch'
                New-Item `
                    -ItemType Junction `
                    -Path $linkedScratch `
                    -Target $externalRoot | Out-Null
                Assert-FailsWith -Code 'linked_layout_entry' -Action {
                    Assert-ExternalLayout `
                        -Executable $externalExecutable `
                        -Scratch $linkedScratch `
                        -Evidence $externalEvidence `
                        -GeneratedProfile (Join-Path $linkedScratch 'profile-happy') `
                        -CurrentDirectory $externalCwd
                }
            } finally {
                Remove-Item `
                    -LiteralPath $reparseRoot `
                    -Recurse `
                    -Force `
                    -ErrorAction SilentlyContinue
            }
        }
        'python-node-path-cleared' {
            Clear-AmbientBuildEnvironment
            if ($null -ne [Environment]::GetEnvironmentVariable('PYTHONPATH')) {
                throw 'pythonpath_not_cleared'
            }
            if ($null -ne [Environment]::GetEnvironmentVariable('NODE_PATH')) {
                throw 'node_path_not_cleared'
            }
        }
        'scenario-set-declared' {
            if (($script:SupportedScenarios -join ',') -cne `
                'happy,missing-sidecar,corrupt-sidecar,incompatible-sidecar') {
                throw 'scenario_set_invalid'
            }
        }
        'missing-sidecar-restored' {
            Test-SidecarRestoreSelfTest 'missing-sidecar'
        }
        'corrupt-sidecar-restored' {
            Test-SidecarRestoreSelfTest 'corrupt-sidecar'
        }
        'incompatible-sidecar-restored' {
            Test-SidecarRestoreSelfTest 'incompatible-sidecar'
        }
        'all-scenarios-use-fresh-profiles' {
            $profiles = @(
                $script:SupportedScenarios |
                    ForEach-Object { Get-ScenarioProfile $externalScratch $_ }
            )
            if (($profiles | Select-Object -Unique).Count -ne 4) {
                throw 'scenario_profiles_not_unique'
            }
            foreach ($profile in $profiles) {
                if (-not (Test-PathInside -Candidate $profile -Root $externalScratch)) {
                    throw 'scenario_profile_outside_scratch'
                }
            }
        }
        'diagnostic-evidence-bounded' {
            Test-DiagnosticEvidenceBounded
        }
        'runtime-diagnostic-placeholder-rejected' {
            if (Test-RuntimeDiagnosticText 'No runtime diagnostic.') {
                throw 'runtime_diagnostic_placeholder_accepted'
            }
        }
        'runtime-diagnostic-failure-accepted' {
            if (-not (Test-RuntimeDiagnosticText 'The local runtime is unavailable.')) {
                throw 'runtime_diagnostic_failure_rejected'
            }
        }
        'restart-history-placeholder-rejected' {
            if (Test-RestartHistoryText 'No sessions yet') {
                throw 'restart_history_placeholder_accepted'
            }
        }
        'restart-history-session-accepted' {
            if (-not (Test-RestartHistoryText 'Untitled session')) {
                throw 'restart_history_session_rejected'
            }
        }
        'profile-inventory-detects-mutation' {
            $profile = Join-Path `
                $externalRoot `
                ('loopplane-078-profile-inventory-' + [guid]::NewGuid().ToString('N'))
            New-Item -ItemType Directory -Path $profile | Out-Null
            try {
                $before = Get-ProfileInventory $profile
                [System.IO.File]::WriteAllText((Join-Path $profile 'changed.txt'), 'changed')
                $after = Get-ProfileInventory $profile
                if (Test-InventoryEqual -Before $before -After $after) {
                    throw 'profile_inventory_mutation_missed'
                }
            } finally {
                Remove-Item -LiteralPath $profile -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
        'orphan-observation-detects-process' {
            $currentId = [int]$PID
            if (-not (Test-LoopPlaneOrphanProcess -ObservedProcessIds @($currentId))) {
                throw 'orphan_process_observation_missed'
            }
        }
        'listener-observation-detects-listener' {
            $listener = [System.Net.Sockets.TcpListener]::new(
                [System.Net.IPAddress]::Loopback,
                0
            )
            $listener.Start()
            try {
                if (-not (Test-LocalTcpListener -ObservedProcessIds @([int]$PID))) {
                    throw 'listener_observation_missed'
                }
            } finally {
                $listener.Stop()
            }
        }
        'continuous-observation-detects-transient-listener' {
            $script:sample = 0
            $observation = Start-ProcessNetworkObservation `
                -Process (Get-Process -Id $PID) `
                -ObservedProcessIds (
                    New-Object System.Collections.Generic.HashSet[int]
                ) `
                -DiscoverDescendants { @() } `
                -DetectListener {
                    param([int[]] $ids)
                    $null = $ids
                    $script:sample += 1
                    return $script:sample -eq 2
                } `
                -DetectOrphan { $false }
            Update-ProcessNetworkObservation -Observation $observation
            Update-ProcessNetworkObservation -Observation $observation
            if (-not $observation.ListenerObserved) {
                throw 'transient_listener_observation_missed'
            }
        }
        'continuous-observation-detects-late-descendant' {
            $script:sample = 0
            $lateId = 24680
            $observation = Start-ProcessNetworkObservation `
                -Process (Get-Process -Id $PID) `
                -ObservedProcessIds (
                    New-Object System.Collections.Generic.HashSet[int]
                ) `
                -DiscoverDescendants {
                    param([int] $rootId)
                    $null = $rootId
                    $script:sample += 1
                    if ($script:sample -ge 2) { return @($lateId) }
                    return @()
                } `
                -DetectListener { $false } `
                -DetectOrphan { $false }
            Update-ProcessNetworkObservation -Observation $observation
            if (-not $observation.ObservedProcessIds.Contains($lateId)) {
                throw 'late_descendant_observation_missed'
            }
        }
        'continuous-observation-detects-post-close-orphan' {
            $observation = Start-ProcessNetworkObservation `
                -Process (Get-Process -Id $PID) `
                -ObservedProcessIds (
                    New-Object System.Collections.Generic.HashSet[int]
                ) `
                -DiscoverDescendants { @() } `
                -DetectListener { $false } `
                -DetectOrphan { $true }
            $result = Stop-ProcessNetworkObservation `
                -Observation $observation `
                -PostCloseMilliseconds 0
            if (-not $result.orphan) {
                throw 'post_close_orphan_observation_missed'
            }
        }
        'continuous-observation-survives-root-dispose' {
            $root = Get-Process -Id $PID
            $observation = Start-ProcessNetworkObservation `
                -Process $root `
                -ObservedProcessIds (
                    New-Object System.Collections.Generic.HashSet[int]
                ) `
                -DiscoverDescendants { @() } `
                -DetectListener { $false } `
                -DetectOrphan { $false }
            $root.Dispose()
            $result = Stop-ProcessNetworkObservation `
                -Observation $observation `
                -PostCloseMilliseconds 0
            if ($result.samples -lt 2) {
                throw 'disposed_root_observation_stopped'
            }
        }
        default {
            throw 'unknown_selftest'
        }
    }

    [Console]::Out.WriteLine("PASS " + $Case)
}

function Get-RequiredLocators {
    return @(
        [ordered]@{
            Name = 'LoopPlane smoke runtime status'
            ControlType = [System.Windows.Automation.ControlType]::Group
        },
        [ordered]@{
            Name = 'LoopPlane smoke new session'
            ControlType = [System.Windows.Automation.ControlType]::Button
        },
        [ordered]@{
            Name = 'LoopPlane smoke prompt'
            ControlType = [System.Windows.Automation.ControlType]::Edit
        },
        [ordered]@{
            Name = 'LoopPlane smoke submit'
            ControlType = [System.Windows.Automation.ControlType]::Button
        },
        [ordered]@{
            Name = 'LoopPlane smoke latest outcome'
            ControlType = [System.Windows.Automation.ControlType]::Group
        },
        [ordered]@{
            Name = 'LoopPlane smoke session list'
            ControlType = [System.Windows.Automation.ControlType]::List
        },
        [ordered]@{
            Name = 'LoopPlane smoke runtime diagnostic'
            ControlType = [System.Windows.Automation.ControlType]::Group
        }
    )
}

function Find-UniqueElement {
    param(
        [Parameter(Mandatory = $true)] $Root,
        [Parameter(Mandatory = $true)][string] $Name,
        [Parameter(Mandatory = $true)] $ControlType
    )

    $nameCondition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::NameProperty,
        $Name
    )
    $typeCondition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        $ControlType
    )
    $condition = [System.Windows.Automation.AndCondition]::new(
        [System.Windows.Automation.Condition[]]@($nameCondition, $typeCondition)
    )
    $matches = $Root.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        $condition
    )
    if ($matches.Count -ne 1) {
        throw 'uia_locator_cardinality_invalid'
    }
    return $matches.Item(0)
}

function Wait-TopLevelWindow {
    param(
        [Parameter(Mandatory = $true)][System.Diagnostics.Process] $Process,
        [Parameter(Mandatory = $true)][datetime] $Deadline,
        $Observation
    )

    $condition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ProcessIdProperty,
        $Process.Id
    )
    while ([datetime]::UtcNow -lt $Deadline) {
        if ($null -ne $Observation) {
            Update-ProcessNetworkObservation -Observation $Observation
        }
        $window = [System.Windows.Automation.AutomationElement]::RootElement.FindFirst(
            [System.Windows.Automation.TreeScope]::Children,
            $condition
        )
        if ($null -ne $window) {
            return $window
        }
        if ($Process.HasExited) {
            throw 'packaged_process_exited_early'
        }
        Start-Sleep -Milliseconds 100
    }
    throw 'packaged_window_timeout'
}

function Activate-PackagedRendererAccessibility {
    param(
        [Parameter(Mandatory = $true)][System.Diagnostics.Process] $Process,
        [Parameter(Mandatory = $true)] $Window
    )

    [void][LoopPlaneSmokeWindow]::SetForegroundWindow($Process.MainWindowHandle)
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.SendKeys]::SendWait('{TAB}')
}

function Wait-RequiredElements {
    param(
        [Parameter(Mandatory = $true)][System.Diagnostics.Process] $Process,
        [Parameter(Mandatory = $true)] $Window,
        [Parameter(Mandatory = $true)][datetime] $Deadline,
        $Observation
    )

    Activate-PackagedRendererAccessibility -Process $Process -Window $Window
    while ([datetime]::UtcNow -lt $Deadline) {
        if ($null -ne $Observation) {
            Update-ProcessNetworkObservation -Observation $Observation
        }
        try {
            $found = [ordered]@{}
            foreach ($locator in Get-RequiredLocators) {
                $found[$locator.Name] = Find-UniqueElement `
                    -Root $Window `
                    -Name $locator.Name `
                    -ControlType $locator.ControlType
            }
            return $found
        } catch {
            if ($_.Exception.Message -cne 'uia_locator_cardinality_invalid') {
                throw
            }
        }
        Start-Sleep -Milliseconds 100
    }
    throw 'uia_locator_timeout'
}

function Read-ContainerText {
    param([Parameter(Mandatory = $true)] $Container)

    $descendants = $Container.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.Condition]::TrueCondition
    )
    $values = New-Object System.Collections.Generic.List[string]
    for ($index = 0; $index -lt $descendants.Count; $index += 1) {
        $name = $descendants.Item($index).Current.Name
        if (-not [string]::IsNullOrWhiteSpace($name)) {
            $values.Add($name)
        }
    }
    return ($values -join "`n")
}

function Wait-RuntimeUsable {
    param(
        [Parameter(Mandatory = $true)] $Container,
        [Parameter(Mandatory = $true)][datetime] $Deadline,
        $Observation
    )

    while ([datetime]::UtcNow -lt $Deadline) {
        if ($null -ne $Observation) {
            Update-ProcessNetworkObservation -Observation $Observation
        }
        $status = Read-ContainerText $Container
        if ($status -match '(?i)usable') {
            return $status
        }
        Start-Sleep -Milliseconds 100
    }
    throw 'runtime_not_usable'
}

function Start-PackagedProcess {
    param(
        [Parameter(Mandatory = $true)][string] $Executable,
        [Parameter(Mandatory = $true)][string] $Profile,
        [Parameter(Mandatory = $true)][string] $SmokeScenario,
        [Parameter(Mandatory = $true)][string] $WorkingDirectory
    )

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $Executable
    $startInfo.Arguments = "--loopplane-packaged-smoke=" + $SmokeScenario
    $startInfo.WorkingDirectory = $WorkingDirectory
    $startInfo.UseShellExecute = $false
    $startInfo.EnvironmentVariables['LOOPPLANE_PACKAGED_SMOKE_PROFILE'] = $Profile
    foreach ($name in $script:ForbiddenEnvironment) {
        $startInfo.EnvironmentVariables.Remove($name)
    }
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw 'packaged_process_start_failed'
    }
    return $process
}

function Close-NormalWindow {
    param([Parameter(Mandatory = $true)] $Window)

    $pattern = $Window.GetCurrentPattern(
        [System.Windows.Automation.WindowPattern]::Pattern
    )
    $pattern.Close()
}

function Stop-PackagedProcess {
    param($Process)

    if ($null -eq $Process) {
        return
    }
    try {
        if (-not $Process.HasExited) {
            $Process.Kill()
            $Process.WaitForExit(5000) | Out-Null
        }
    } catch {
        # 清理由固定公開結果承擔，不輸出私有路徑或例外內容。
    }
    $Process.Dispose()
}

function Get-CopiedSidecarPath {
    param([Parameter(Mandatory = $true)][string] $Executable)

    $artifactRoot = Split-Path -Parent $Executable
    return Join-Path $artifactRoot 'resources/sidecar/loopplane-sidecar.exe'
}

function New-IncompatibleSidecar {
    param([Parameter(Mandatory = $true)][string] $Path)

    $source = @'
using System;
using System.Text.RegularExpressions;
using System.Threading;

public static class LoopPlaneIncompatibleSidecar
{
    public static void Main()
    {
        var request = Console.ReadLine() ?? String.Empty;
        var match = Regex.Match(request, @"""id""\s*:\s*""(?<id>[^""]+)""");
        var id = match.Success ? match.Groups["id"].Value : "incompatible";
        Console.WriteLine("{\"jsonrpc\":\"2.0\",\"id\":\"" + id + "\",\"result\":{\"protocol\":\"loopplane.desktop.stdio\",\"version\":999,\"methods\":[],\"capabilities\":{}}}");
        Console.Out.Flush();
        Thread.Sleep(10000);
    }
}
'@
    Add-Type `
        -TypeDefinition $source `
        -Language CSharp `
        -OutputAssembly $Path `
        -OutputType ConsoleApplication
}

function Set-CopiedSidecarVariant {
    param(
        [Parameter(Mandatory = $true)][string] $SidecarPath,
        [Parameter(Mandatory = $true)][string] $Variant
    )

    if ($script:SupportedScenarios -cnotcontains $Variant -or $Variant -eq 'happy') {
        throw 'sidecar_variant_invalid'
    }
    if (-not (Test-Path -LiteralPath $SidecarPath -PathType Leaf)) {
        throw 'copied_sidecar_missing_before_variant'
    }
    if (Test-PathInside -Candidate $SidecarPath -Root $script:CheckoutRoot) {
        throw 'checkout_path_forbidden'
    }

    $backupPath = $SidecarPath + '.accepted-' + [guid]::NewGuid().ToString('N')
    Move-Item -LiteralPath $SidecarPath -Destination $backupPath
    try {
        switch ($Variant) {
            'missing-sidecar' {
                # 保留缺檔狀態直到可見診斷完成。
            }
            'corrupt-sidecar' {
                [System.IO.File]::WriteAllBytes(
                    $SidecarPath,
                    [byte[]](0, 1, 2, 3, 4, 5, 6, 7)
                )
            }
            'incompatible-sidecar' {
                New-IncompatibleSidecar -Path $SidecarPath
            }
        }
        return $backupPath
    } catch {
        Restore-CopiedSidecar `
            -SidecarPath $SidecarPath `
            -BackupPath $backupPath
        throw
    }
}

function Invoke-SmokeScenario {
    param(
        [Parameter(Mandatory = $true)][string] $Executable,
        [Parameter(Mandatory = $true)][string] $Scratch,
        [Parameter(Mandatory = $true)][string] $SmokeScenario,
        [Parameter(Mandatory = $true)][string] $WorkingDirectory
    )

    $profilePath = Get-ScenarioProfile $Scratch $SmokeScenario
    if (Test-Path -LiteralPath $profilePath) {
        throw 'scenario_profile_exists'
    }
    New-Item -ItemType Directory -Path $profilePath | Out-Null
    $profileBefore = Get-ProfileInventory $profilePath

    $sidecarPath = Get-CopiedSidecarPath $Executable
    $backupPath = $null
    $process = $null
    $relaunch = $null
    $observations = New-Object System.Collections.Generic.List[object]
    $observationSamples = 0
    $listenerObserved = $false
    $orphanObserved = $false
    $started = [datetime]::UtcNow
    try {
        if ($SmokeScenario -ne 'happy') {
            $backupPath = Set-CopiedSidecarVariant `
                -SidecarPath $sidecarPath `
                -Variant $SmokeScenario
        }

        $deadline = [datetime]::UtcNow.AddSeconds(10)
        $process = Start-PackagedProcess `
            -Executable $Executable `
            -Profile $profilePath `
            -SmokeScenario $SmokeScenario `
            -WorkingDirectory $WorkingDirectory
        $processObservation = Start-ProcessNetworkObservation `
            -Process $process `
            -ObservedProcessIds (
                New-Object System.Collections.Generic.HashSet[int]
            )
        $observations.Add($processObservation)
        $window = Wait-TopLevelWindow `
            -Process $process `
            -Deadline $deadline `
            -Observation $processObservation
        $elements = Wait-RequiredElements `
            -Process $process `
            -Window $window `
            -Deadline $deadline `
            -Observation $processObservation
        Update-ProcessNetworkObservation -Observation $processObservation

        if ($SmokeScenario -eq 'happy') {
            [void](Wait-RuntimeUsable `
                -Container $elements['LoopPlane smoke runtime status'] `
                -Deadline $deadline `
                -Observation $processObservation)
            $newSession = $elements['LoopPlane smoke new session'].GetCurrentPattern(
                [System.Windows.Automation.InvokePattern]::Pattern
            )
            $newSession.Invoke()
            $prompt = $elements['LoopPlane smoke prompt'].GetCurrentPattern(
                [System.Windows.Automation.ValuePattern]::Pattern
            )
            $prompt.SetValue('loopplane packaged smoke')
            $submit = $elements['LoopPlane smoke submit'].GetCurrentPattern(
                [System.Windows.Automation.InvokePattern]::Pattern
            )
            $submit.Invoke()

            $outcome = ''
            $terminalDeadline = [datetime]::UtcNow.AddSeconds(10)
            while ([datetime]::UtcNow -lt $terminalDeadline) {
                Update-ProcessNetworkObservation -Observation $processObservation
                $outcomeElement = Find-UniqueElement `
                    -Root $window `
                    -Name 'LoopPlane smoke latest outcome' `
                    -ControlType ([System.Windows.Automation.ControlType]::Group)
                $outcome = Read-ContainerText $outcomeElement
                if ($outcome -match 'loopplane-packaged-smoke-ok') {
                    break
                }
                Start-Sleep -Milliseconds 100
            }
            if ($outcome -notmatch 'loopplane-packaged-smoke-ok') {
                throw 'terminal_marker_timeout'
            }

            Close-NormalWindow $window
            if (-not (Wait-ObservedProcessExit `
                -Process $process `
                -Observation $processObservation `
                -Deadline ([datetime]::UtcNow.AddSeconds(5)))) {
                throw 'packaged_process_exit_timeout'
            }
            $processResult = Stop-ProcessNetworkObservation `
                -Observation $processObservation
            $observationSamples += [int]$processResult.samples
            $listenerObserved = $listenerObserved -or [bool]$processResult.listener
            $orphanObserved = $orphanObserved -or [bool]$processResult.orphan
            [void]$observations.Remove($processObservation)
            $process.Dispose()
            $process = $null

            $relaunchDeadline = [datetime]::UtcNow.AddSeconds(10)
            $relaunch = Start-PackagedProcess `
                -Executable $Executable `
                -Profile $profilePath `
                -SmokeScenario $SmokeScenario `
                -WorkingDirectory $WorkingDirectory
            $relaunchObservation = Start-ProcessNetworkObservation `
                -Process $relaunch `
                -ObservedProcessIds (
                    New-Object System.Collections.Generic.HashSet[int]
                )
            $observations.Add($relaunchObservation)
            $relaunchWindow = Wait-TopLevelWindow `
                -Process $relaunch `
                -Deadline $relaunchDeadline `
                -Observation $relaunchObservation
            $relaunchElements = Wait-RequiredElements `
                -Process $relaunch `
                -Window $relaunchWindow `
                -Deadline $relaunchDeadline `
                -Observation $relaunchObservation
            Update-ProcessNetworkObservation -Observation $relaunchObservation
            $sessions = ''
            while ([datetime]::UtcNow -lt $relaunchDeadline) {
                Update-ProcessNetworkObservation -Observation $relaunchObservation
                $sessionList = Find-UniqueElement `
                    -Root $relaunchWindow `
                    -Name 'LoopPlane smoke session list' `
                    -ControlType ([System.Windows.Automation.ControlType]::List)
                $sessions = Read-ContainerText $sessionList
                if (Test-RestartHistoryText $sessions) {
                    break
                }
                Start-Sleep -Milliseconds 100
            }
            if (-not (Test-RestartHistoryText $sessions)) {
                throw 'restart_history_missing'
            }
            Close-NormalWindow $relaunchWindow
            if (-not (Wait-ObservedProcessExit `
                -Process $relaunch `
                -Observation $relaunchObservation `
                -Deadline ([datetime]::UtcNow.AddSeconds(5)))) {
                throw 'packaged_relaunch_exit_timeout'
            }
            $relaunchResult = Stop-ProcessNetworkObservation `
                -Observation $relaunchObservation
            $observationSamples += [int]$relaunchResult.samples
            $listenerObserved = $listenerObserved -or [bool]$relaunchResult.listener
            $orphanObserved = $orphanObserved -or [bool]$relaunchResult.orphan
            [void]$observations.Remove($relaunchObservation)
            $relaunch.Dispose()
            $relaunch = $null
            $state = 'passed'
        } else {
            $diagnostic = ''
            while ([datetime]::UtcNow -lt $deadline) {
                Update-ProcessNetworkObservation -Observation $processObservation
                $diagnostic = Read-ContainerText `
                    $elements['LoopPlane smoke runtime diagnostic']
                if (Test-RuntimeDiagnosticText $diagnostic) {
                    break
                }
                Start-Sleep -Milliseconds 100
            }
            if (-not (Test-RuntimeDiagnosticText $diagnostic)) {
                throw 'runtime_diagnostic_timeout'
            }
            foreach ($privateValue in @($Executable, $Scratch, $profilePath)) {
                if ($diagnostic.IndexOf(
                    $privateValue,
                    [System.StringComparison]::OrdinalIgnoreCase
                ) -ge 0) {
                    throw 'runtime_diagnostic_disclosure'
                }
            }
            Close-NormalWindow $window
            if (-not (Wait-ObservedProcessExit `
                -Process $process `
                -Observation $processObservation `
                -Deadline ([datetime]::UtcNow.AddSeconds(5)))) {
                throw 'packaged_process_exit_timeout'
            }
            $processResult = Stop-ProcessNetworkObservation `
                -Observation $processObservation
            $observationSamples += [int]$processResult.samples
            $listenerObserved = $listenerObserved -or [bool]$processResult.listener
            $orphanObserved = $orphanObserved -or [bool]$processResult.orphan
            [void]$observations.Remove($processObservation)
            $process.Dispose()
            $process = $null
            $state = 'diagnosed'
        }

        if (-not (Test-Path -LiteralPath $profilePath -PathType Container)) {
            throw 'scenario_profile_not_preserved'
        }
        $profileAfter = Get-ProfileInventory $profilePath
        $failureProfileUnchanged = if ($SmokeScenario -eq 'happy') {
            $null
        } else {
            Test-InventoryEqual -Before $profileBefore -After $profileAfter
        }
        if ($SmokeScenario -ne 'happy' -and -not $failureProfileUnchanged) {
            throw 'failure_profile_mutated'
        }
        if ($orphanObserved) {
            throw 'orphan_process_detected'
        }
        if ($listenerObserved) {
            throw 'local_listener_detected'
        }
        $observed = @()
        foreach ($locator in Get-RequiredLocators) {
            $observed += [ordered]@{
                name = $locator.Name
                control_type = $locator.ControlType.ProgrammaticName
            }
        }
        return [ordered]@{
            scenario = $SmokeScenario
            state = $state
            observed_pairs = $observed
            elapsed_ms = [int]([datetime]::UtcNow - $started).TotalMilliseconds
            profile_preserved = $true
            failure_profile_unchanged = $failureProfileUnchanged
            orphan = $orphanObserved
            listener = $listenerObserved
            observation_samples = $observationSamples
            copied_sidecar_restored = ($SmokeScenario -eq 'happy')
        }
    } finally {
        foreach ($observation in $observations.ToArray()) {
            $observationResult = Stop-ProcessNetworkObservation `
                -Observation $observation
            $observationSamples += [int]$observationResult.samples
            $listenerObserved = $listenerObserved -or [bool]$observationResult.listener
            $orphanObserved = $orphanObserved -or [bool]$observationResult.orphan
        }
        Stop-PackagedProcess $process
        Stop-PackagedProcess $relaunch
        if ($null -ne $backupPath) {
            Restore-CopiedSidecar `
                -SidecarPath $sidecarPath `
                -BackupPath $backupPath
        }
    }
}

function Write-BoundedEvidence {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)] $Value
    )

    $json = $Value | ConvertTo-Json -Depth 5 -Compress
    if ([System.Text.Encoding]::UTF8.GetByteCount($json) -gt 65536) {
        throw 'evidence_too_large'
    }
    $stream = [System.IO.FileStream]::new(
        $Path,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    try {
        $writer = [System.IO.StreamWriter]::new(
            $stream,
            (New-Object System.Text.UTF8Encoding($false)),
            4096,
            $true
        )
        try {
            $writer.Write($json)
            $writer.Flush()
            $stream.Flush($true)
        } finally {
            $writer.Dispose()
        }
    } finally {
        $stream.Dispose()
    }
}

if (-not [string]::IsNullOrWhiteSpace($SelfTest)) {
    try {
        Invoke-PathSelfTest $SelfTest
        exit 0
    } catch {
        [Console]::Error.WriteLine('FAIL smoke_selftest_failed')
        exit 2
    }
}

if ($env:OS -ne 'Windows_NT') {
    [Console]::Error.WriteLine('FAIL windows_required')
    exit 2
}

try {
    if (-not (Test-Path -LiteralPath $AppExecutable -PathType Leaf)) {
        throw 'packaged_executable_missing'
    }
    $appPath = (Resolve-Path -LiteralPath $AppExecutable).Path
    $scratchPath = Get-CanonicalPath $ScratchRoot
    $evidenceFile = Get-CanonicalPath $EvidencePath
    $currentDirectory = [System.IO.Directory]::GetCurrentDirectory()
    $scenarios = if ($Scenario -eq 'all') {
        $script:SupportedScenarios
    } else {
        @($Scenario)
    }
    foreach ($smokeScenario in $scenarios) {
        $profilePath = Get-ScenarioProfile $scratchPath $smokeScenario
        Assert-ExternalLayout `
            -Executable $appPath `
            -Scratch $scratchPath `
            -Evidence $evidenceFile `
            -GeneratedProfile $profilePath `
            -CurrentDirectory $currentDirectory
    }
    if (Test-Path -LiteralPath $evidenceFile) {
        throw 'evidence_path_exists'
    }

    Clear-AmbientBuildEnvironment
    New-Item -ItemType Directory -Path $scratchPath -ErrorAction Stop | Out-Null
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes

    $started = [datetime]::UtcNow
    $results = @()
    foreach ($smokeScenario in $scenarios) {
        $results += Invoke-SmokeScenario `
            -Executable $appPath `
            -Scratch $scratchPath `
            -SmokeScenario $smokeScenario `
            -WorkingDirectory $currentDirectory
    }
    foreach ($result in $results) {
        $result.copied_sidecar_restored = $true
    }
    $evidence = [ordered]@{
        scenario = $Scenario
        artifact_sha256 = (
            Get-FileHash -LiteralPath $appPath -Algorithm SHA256
        ).Hash.ToLowerInvariant()
        results = $results
        state = 'passed'
        elapsed_ms = [int]([datetime]::UtcNow - $started).TotalMilliseconds
        orphan = [bool]($results | Where-Object { $_.orphan } | Select-Object -First 1)
        listener = [bool]($results | Where-Object { $_.listener } | Select-Object -First 1)
    }
    Write-BoundedEvidence -Path $evidenceFile -Value $evidence
    exit 0
} catch {
    [Console]::Error.WriteLine('FAIL packaged_smoke_failed')
    exit 2
}
