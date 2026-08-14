#Requires -Version 5.1
<#
.SYNOPSIS
  從 delivery verifier 的唯讀 descriptor snapshot 建立 Desktop sidecar。

.DESCRIPTION
  這是唯一 sidecar freeze route。它不讀取 mutable checkout Python source，
  不接受 PATH/global/bare PyInstaller，並在讀取 descriptor 前拒絕 GitHub token。
#>
[CmdletBinding()]
param(
    [string] $DescriptorPath,
    [string] $ResultPath,
    [string] $SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:RepositoryRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot '..')
).TrimEnd([char[]]@('\', '/'))
$script:VerifierPath = Join-Path $PSScriptRoot 'verify-desktop-stage-b.ps1'
$script:ForbiddenTokens = @(
    'LOOPPLANE_STAGE_B_GITHUB_TOKEN',
    'GH_TOKEN',
    'GITHUB_TOKEN'
)
$script:PackagedExtras = @(
    'anthropic',
    'gemini',
    'mcp',
    'net',
    'oauth',
    'openai'
)
$script:GeneratedSegments = @(
    '.git',
    '.superpowers',
    'node_modules',
    '.build',
    'release',
    'dist',
    'dist-electron',
    '__pycache__',
    '.venv',
    'profiles',
    'backups'
)

# Static contract for the exact accepted runtime export:
# uv export --extra anthropic --extra gemini --extra mcp --extra net --extra oauth --extra openai

function Write-PublicFail {
    param([string] $Code)
    [Console]::Error.WriteLine('FAIL ' + $Code)
}

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
    return $candidatePath.StartsWith(
        $rootPath + [System.IO.Path]::DirectorySeparatorChar,
        $comparison
    )
}

function Test-ForbiddenCredential {
    param([hashtable] $Environment)
    foreach ($name in $script:ForbiddenTokens) {
        if ($Environment.ContainsKey($name) -and
            -not [string]::IsNullOrEmpty([string]$Environment[$name])) {
            return $true
        }
    }
    return $false
}

function Assert-NoAuthorityCredential {
    $environment = @{}
    foreach ($name in $script:ForbiddenTokens) {
        $environment[$name] = [Environment]::GetEnvironmentVariable($name)
    }
    if (Test-ForbiddenCredential $environment) {
        throw 'credential_environment_forbidden'
    }
}

function Clear-BuildEnvironment {
    foreach ($name in @(
        'LOOPPLANE_STAGE_B_GITHUB_TOKEN',
        'GH_TOKEN',
        'GITHUB_TOKEN',
        'PYTHONPATH',
        'PYTHONHOME',
        'VIRTUAL_ENV'
    )) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
        Remove-Item -LiteralPath ('Env:' + $name) -ErrorAction SilentlyContinue
    }
}

function Test-ReviewIdsDistinct {
    param($Authority)
    if ($null -eq $Authority) {
        return $false
    }
    $ids = @(
        [string]$Authority.bootstrap_review_id,
        [string]$Authority.final_review_id,
        [string]$Authority.delivery_review_id
    )
    if ($ids -contains '') {
        return $false
    }
    return (($ids | Select-Object -Unique).Count -eq 3)
}

function Assert-DescriptorShape {
    param(
        $Descriptor,
        [switch] $RequireFiles
    )
    if ($null -eq $Descriptor -or
        [int]$Descriptor.schema_version -ne 1 -or
        [string]$Descriptor.mode -cne 'delivery') {
        throw 'descriptor_schema_invalid'
    }
    if (-not (Test-ReviewIdsDistinct $Descriptor.authority)) {
        throw 'delivery_review_chain_invalid'
    }
    $created = [datetime]::MinValue
    if (-not [datetime]::TryParse(
        [string]$Descriptor.created_at_utc,
        [ref]$created
    )) {
        throw 'descriptor_timestamp_invalid'
    }
    $createdUtc = $created.ToUniversalTime()
    $now = [datetime]::UtcNow
    if ($createdUtc -gt $now) {
        throw 'descriptor_timestamp_future'
    }
    if ($now - $createdUtc -gt [timespan]::FromMinutes(15)) {
        throw 'descriptor_stale'
    }

    $materializationRoot = Get-CanonicalPath $Descriptor.materialization_root
    $reviewedSourceRoot = Get-CanonicalPath $Descriptor.reviewedSourceRoot
    if (-not (Test-PathInside $reviewedSourceRoot $materializationRoot)) {
        throw 'descriptor_source_outside_materialization'
    }
    foreach ($property in @(
        'pyprojectPath',
        'uvLockPath',
        'pyinstallerLockPath'
    )) {
        $path = Get-CanonicalPath $Descriptor.$property
        if (-not (Test-PathInside $path $materializationRoot)) {
            throw 'descriptor_dependency_outside_materialization'
        }
        if ($RequireFiles -and -not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw 'descriptor_dependency_missing'
        }
    }
    if ($RequireFiles -and
        -not (Test-Path -LiteralPath $reviewedSourceRoot -PathType Container)) {
        throw 'descriptor_source_missing'
    }
}

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string] $Path)
    # Hash with .NET rather than Get-FileHash, which has to be resolved from
    # Microsoft.PowerShell.Utility at call time and is not available on every runner.
    $full = (Resolve-Path -LiteralPath $Path).Path
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $stream = [System.IO.File]::OpenRead($full)
        try {
            return [System.BitConverter]::ToString(
                $sha.ComputeHash($stream)
            ).Replace('-', '').ToLowerInvariant()
        } finally {
            $stream.Dispose()
        }
    } finally {
        $sha.Dispose()
    }
}

function Assert-ExpectedDigest {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $Expected
    )
    if ([string]::IsNullOrWhiteSpace($Expected) -or
        (Get-Sha256 $Path) -cne $Expected.ToLowerInvariant()) {
        throw 'accepted_input_digest_mismatch'
    }
}

function Assert-RegularNoLink {
    param([Parameter(Mandatory = $true)][System.IO.FileSystemInfo] $Entry)
    if (($Entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'linked_input_forbidden'
    }
}

function Test-SkippedRelativePath {
    param([string] $RelativePath)
    $normalized = $RelativePath.Replace('\', '/')
    if ($normalized -ceq 'apps/desktop/sidecar/pyinstaller-build-windows-py312.txt') {
        return $true
    }
    foreach ($segment in $normalized.Split('/')) {
        if ($script:GeneratedSegments -contains $segment) {
            return $true
        }
    }
    return $false
}

function Copy-FileCreateNew {
    param(
        [Parameter(Mandatory = $true)][string] $Source,
        [Parameter(Mandatory = $true)][string] $Destination
    )
    $parent = Split-Path -Parent $Destination
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent | Out-Null
    }
    $sourceStream = [System.IO.File]::Open(
        $Source,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read
    )
    try {
        $destinationStream = [System.IO.File]::Open(
            $Destination,
            [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None
        )
        try {
            $sourceStream.CopyTo($destinationStream)
            $destinationStream.Flush($true)
        } finally {
            $destinationStream.Dispose()
        }
    } finally {
        $sourceStream.Dispose()
    }
}

function Copy-ReviewedPythonSource {
    param(
        [Parameter(Mandatory = $true)][string] $reviewedSourceRoot,
        [Parameter(Mandatory = $true)][string] $DestinationRoot
    )
    $sourceCanonical = Get-CanonicalPath $reviewedSourceRoot
    foreach ($relativeRoot in @('src/loopplane', 'apps/desktop/sidecar')) {
        $start = Join-Path $sourceCanonical $relativeRoot
        if (-not (Test-Path -LiteralPath $start -PathType Container)) {
            throw 'reviewed_python_subtree_missing'
        }
        $queue = New-Object System.Collections.Generic.Queue[string]
        $queue.Enqueue($start)
        while ($queue.Count -gt 0) {
            $directory = $queue.Dequeue()
            foreach ($entry in Get-ChildItem -LiteralPath $directory -Force) {
                Assert-RegularNoLink $entry
                $relative = $entry.FullName.Substring(
                    $sourceCanonical.Length
                ).TrimStart([char[]]@('\', '/'))
                if (Test-SkippedRelativePath $relative) {
                    continue
                }
                $destination = Join-Path $DestinationRoot $relative
                if ($entry.PSIsContainer) {
                    if (-not (Test-Path -LiteralPath $destination)) {
                        New-Item -ItemType Directory -Path $destination | Out-Null
                    }
                    $queue.Enqueue($entry.FullName)
                } else {
                    Copy-FileCreateNew $entry.FullName $destination
                }
            }
        }
    }
}

function Invoke-TokenFreeCommand {
    param(
        [Parameter(Mandatory = $true)][string] $FilePath,
        [Parameter(Mandatory = $true)][string[]] $Arguments,
        [Parameter(Mandatory = $true)][string] $WorkingDirectory
    )
    Assert-NoAuthorityCredential
    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw 'build_child_failed'
        }
    } finally {
        Pop-Location
    }
}

function Invoke-TokenFreeCapture {
    param(
        [Parameter(Mandatory = $true)][string] $FilePath,
        [Parameter(Mandatory = $true)][string[]] $Arguments,
        [Parameter(Mandatory = $true)][string] $WorkingDirectory
    )
    Assert-NoAuthorityCredential
    Push-Location $WorkingDirectory
    try {
        $output = & $FilePath @Arguments | Out-String
        if ($LASTEXITCODE -ne 0) {
            throw 'build_child_failed'
        }
        return $output.Trim()
    } finally {
        Pop-Location
    }
}

function Write-BoundedResult {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)] $Value
    )
    $json = $Value | ConvertTo-Json -Depth 4 -Compress
    if ([System.Text.Encoding]::UTF8.GetByteCount($json) -gt 32768) {
        throw 'result_too_large'
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

function Invoke-SelfTest {
    param([Parameter(Mandatory = $true)][string] $Case)

    $ok = $false
    $acceptedRoot = Get-CanonicalPath (
        Join-Path ([System.IO.Path]::GetTempPath()) 'accepted-selftest'
    )
    $sourceRoot = Join-Path $acceptedRoot 'reviewed-source'
    $descriptor = [pscustomobject]@{
        schema_version = 1
        mode = 'delivery'
        created_at_utc = [datetime]::UtcNow.ToString('o')
        materialization_root = $acceptedRoot
        reviewedSourceRoot = $sourceRoot
        authority = [pscustomobject]@{
            bootstrap_review_id = '1'
            final_review_id = '2'
            delivery_review_id = '3'
        }
        pyprojectPath = Join-Path $acceptedRoot 'dependencies/pyproject.toml'
        uvLockPath = Join-Path $acceptedRoot 'dependencies/uv.lock'
        pyinstallerLockPath = Join-Path $acceptedRoot 'dependencies/pyinstaller.txt'
    }

    switch ($Case) {
        'reject-missing-descriptor' {
            try { Assert-DescriptorShape $null; $ok = $false }
            catch { $ok = ($_.Exception.Message -ceq 'descriptor_schema_invalid') }
        }
        'reject-before-distinct-delivery-review' {
            $descriptor.authority.delivery_review_id = '2'
            try { Assert-DescriptorShape $descriptor; $ok = $false }
            catch { $ok = ($_.Exception.Message -ceq 'delivery_review_chain_invalid') }
        }
        'reject-future-descriptor' {
            $descriptor.created_at_utc = [datetime]::UtcNow.AddMinutes(1).ToString('o')
            try { Assert-DescriptorShape $descriptor; $ok = $false }
            catch { $ok = ($_.Exception.Message -ceq 'descriptor_timestamp_future') }
        }
        'reject-stage-b-token' {
            $ok = Test-ForbiddenCredential @{
                LOOPPLANE_STAGE_B_GITHUB_TOKEN = 'sentinel'
            }
        }
        'reject-gh-token' {
            $ok = Test-ForbiddenCredential @{ GH_TOKEN = 'sentinel' }
        }
        'reject-github-token' {
            $ok = Test-ForbiddenCredential @{ GITHUB_TOKEN = 'sentinel' }
        }
        'descriptor-snapshots-only' {
            Assert-DescriptorShape $descriptor
            $ok = Test-PathInside $descriptor.reviewedSourceRoot $acceptedRoot
            foreach ($property in @(
                'pyprojectPath',
                'uvLockPath',
                'pyinstallerLockPath'
            )) {
                $ok = $ok -and (Test-PathInside $descriptor.$property $acceptedRoot)
            }
        }
        'checkout-source-sentinel-uncalled' {
            $mutableCheckoutSource = @(
                (Join-Path $script:RepositoryRoot 'src/loopplane'),
                (Join-Path $script:RepositoryRoot 'apps/desktop/sidecar')
            )
            $consumers = @(
                (Join-Path $descriptor.reviewedSourceRoot 'src/loopplane'),
                (Join-Path $descriptor.reviewedSourceRoot 'apps/desktop/sidecar')
            )
            $ok = -not @(
                $consumers | Where-Object { $_ -in $mutableCheckoutSource }
            ).Count
        }
        'path-global-bare-pyinstaller-sentinels-uncalled' {
            $isolated = Join-Path $acceptedRoot '.venv/Scripts/pyinstaller.exe'
            $sentinels = @(
                'pyinstaller',
                'pyinstaller.exe',
                (Join-Path $script:RepositoryRoot 'pyinstaller.exe')
            )
            $ok = $isolated.Replace('\', '/').EndsWith(
                'Scripts/pyinstaller.exe',
                [System.StringComparison]::OrdinalIgnoreCase
            )
            $ok = $ok -and ($sentinels -notcontains $isolated)
        }
        'child-env-must-scrub-tokens' {
            $child = @{
                LOOPPLANE_STAGE_B_GITHUB_TOKEN = 'x'
                GH_TOKEN = 'y'
                GITHUB_TOKEN = 'z'
                PATH = 'kept'
            }
            foreach ($name in $script:ForbiddenTokens) {
                [void]$child.Remove($name)
            }
            $ok = (-not (Test-ForbiddenCredential $child)) -and
                ($child.PATH -ceq 'kept')
        }
        default {
            Write-PublicFail 'unknown_selftest'
            exit 2
        }
    }
    if (-not $ok) {
        Write-PublicFail 'selftest_failed'
        exit 1
    }
    [Console]::Out.WriteLine('SELFTEST_OK ' + $Case)
    exit 0
}

if (-not [string]::IsNullOrWhiteSpace($SelfTest)) {
    Invoke-SelfTest $SelfTest
}

try {
    Assert-NoAuthorityCredential
} catch {
    Write-PublicFail 'credential_environment_forbidden'
    exit 2
}

if ($env:OS -ne 'Windows_NT') {
    Write-PublicFail 'windows_required'
    exit 2
}

try {
    if ([string]::IsNullOrWhiteSpace($DescriptorPath)) {
        throw 'descriptor_required'
    }
    if (-not (Test-Path -LiteralPath $DescriptorPath -PathType Leaf)) {
        throw 'descriptor_missing'
    }
    $descriptorFile = (Resolve-Path -LiteralPath $DescriptorPath).Path
    Clear-BuildEnvironment
    & $script:VerifierPath -AssertMaterializedInputs $descriptorFile
    if ($LASTEXITCODE -ne 0) {
        throw 'descriptor_offline_assertion_failed'
    }
    $descriptor = Get-Content -LiteralPath $descriptorFile -Raw | ConvertFrom-Json
    Assert-DescriptorShape $descriptor -RequireFiles

    Assert-ExpectedDigest $descriptor.pyprojectPath $descriptor.pyprojectSha256
    Assert-ExpectedDigest $descriptor.uvLockPath $descriptor.uvLockSha256
    Assert-ExpectedDigest `
        $descriptor.pyinstallerLockPath `
        $descriptor.pyinstallerLockSha256

    $reviewedSourceRoot = Get-CanonicalPath $descriptor.reviewedSourceRoot
    $resultFile = if ([string]::IsNullOrWhiteSpace($ResultPath)) {
        $null
    } else {
        Get-CanonicalPath $ResultPath
    }
    $buildParent = if ($null -ne $resultFile) {
        Split-Path -Parent $resultFile
    } else {
        [System.IO.Path]::GetTempPath()
    }
    if (-not (Test-Path -LiteralPath $buildParent -PathType Container)) {
        throw 'build_parent_missing'
    }
    if ($null -ne $resultFile -and (Test-Path -LiteralPath $resultFile)) {
        throw 'result_path_exists'
    }

    $buildRoot = Join-Path $buildParent (
        'sidecar-build-' + [guid]::NewGuid().ToString('N')
    )
    New-Item -ItemType Directory -Path $buildRoot | Out-Null
    Copy-ReviewedPythonSource $reviewedSourceRoot $buildRoot

    $pythonProjectRoot = $buildRoot
    Copy-FileCreateNew `
        $descriptor.pyprojectPath `
        (Join-Path $pythonProjectRoot 'pyproject.toml')
    Copy-FileCreateNew `
        $descriptor.uvLockPath `
        (Join-Path $pythonProjectRoot 'uv.lock')
    $acceptedPyinstallerLock = Join-Path `
        $pythonProjectRoot `
        'apps/desktop/sidecar/pyinstaller-build-windows-py312.txt'
    Copy-FileCreateNew $descriptor.pyinstallerLockPath $acceptedPyinstallerLock

    $uv = (Get-Command uv.exe -ErrorAction Stop).Source
    $runtimeRequirementsPath = Join-Path $buildRoot 'runtime-requirements.txt'
    $exportArguments = @(
        'export',
        '--frozen',
        '--no-dev',
        '--no-emit-project',
        '--format',
        'requirements-txt',
        '--output-file',
        $runtimeRequirementsPath
    )
    foreach ($extra in $script:PackagedExtras) {
        $exportArguments += @('--extra', $extra)
    }
    Invoke-TokenFreeCommand $uv $exportArguments $pythonProjectRoot
    if (-not (Test-Path -LiteralPath $runtimeRequirementsPath -PathType Leaf)) {
        throw 'runtime_requirements_missing'
    }

    $venvPath = Join-Path $buildRoot '.venv'
    Invoke-TokenFreeCommand $uv @(
        'venv', '--python', '3.12', $venvPath
    ) $pythonProjectRoot
    $python = Join-Path $venvPath 'Scripts/python.exe'
    Invoke-TokenFreeCommand $uv @(
        'pip', 'sync',
        '--python', $python,
        '--require-hashes',
        '--only-binary', ':all:',
        '--strict',
        $runtimeRequirementsPath,
        $acceptedPyinstallerLock
    ) $pythonProjectRoot
    Invoke-TokenFreeCommand $uv @(
        'pip', 'check', '--python', $python
    ) $pythonProjectRoot

    $pyinstaller = Join-Path $venvPath 'Scripts/pyinstaller.exe'
    if (-not (Test-Path -LiteralPath $pyinstaller -PathType Leaf)) {
        throw 'isolated_pyinstaller_missing'
    }
    $version = Invoke-TokenFreeCapture $pyinstaller @('--version') $buildRoot
    if ($version -cne '6.21.0') {
        throw 'isolated_pyinstaller_version_mismatch'
    }

    # Reassert the sealed descriptor immediately before the freeze boundary.
    & $script:VerifierPath -AssertMaterializedInputs $descriptorFile
    if ($LASTEXITCODE -ne 0) {
        throw 'descriptor_pre_freeze_assertion_failed'
    }

    $sidecarRoot = Join-Path $buildRoot 'apps/desktop/sidecar'
    $specPath = Join-Path $sidecarRoot 'loopplane-sidecar.spec'
    if (-not (Test-Path -LiteralPath $specPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath (Join-Path $sidecarRoot '__main__.py') -PathType Leaf)) {
        throw 'sidecar_entrypoint_missing'
    }
    $outputRoot = Join-Path $buildRoot 'output'
    $workRoot = Join-Path $buildRoot 'pyinstaller-work'
    Invoke-TokenFreeCommand $pyinstaller @(
        '--noconfirm',
        '--clean',
        '--distpath', $outputRoot,
        '--workpath', $workRoot,
        $specPath
    ) $sidecarRoot

    $bundleRoot = Join-Path $outputRoot 'loopplane-sidecar'
    $executable = Join-Path $bundleRoot 'loopplane-sidecar.exe'
    if (-not (Test-Path -LiteralPath $bundleRoot -PathType Container) -or
        -not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        throw 'frozen_sidecar_missing'
    }
    $result = [ordered]@{
        mode = 'delivery-sidecar'
        build_root = $buildRoot
        output_root = $bundleRoot
        executable_path = $executable
        descriptor_sha256 = Get-Sha256 $descriptorFile
    }
    if ($null -ne $resultFile) {
        Write-BoundedResult $resultFile $result
    } else {
        $result | ConvertTo-Json -Compress | Write-Output
    }
    exit 0
} catch {
    Write-PublicFail 'sidecar_build_failed'
    exit 2
}
