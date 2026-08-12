#Requires -Version 5.1
<#
.SYNOPSIS
  從 delivery verifier 的唯讀 descriptor snapshot 建立完整 Desktop artifact。

.DESCRIPTION
  這是唯一完整 package route。它不做網路 authority lookup，不讀取 mutable
  checkout source/lock，並在讀取 descriptor 前拒絕任何 GitHub authority token。
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
$script:SidecarWrapperPath = Join-Path $PSScriptRoot 'build-desktop-sidecar.ps1'
$script:ForbiddenTokens = @(
    'LOOPPLANE_STAGE_B_GITHUB_TOKEN',
    'GH_TOKEN',
    'GITHUB_TOKEN'
)
$script:DependencyProperties = [ordered]@{
    rootPackageJsonPath = 'package.json'
    rootPackageLockPath = 'package-lock.json'
    webPackageJsonPath = 'apps/web/package.json'
    desktopPackageJsonPath = 'apps/desktop/package.json'
    sharedPackageJsonPath = 'packages/cowork-presentation/package.json'
}

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

function Clear-ForbiddenChildEnvironment {
    foreach ($name in $script:ForbiddenTokens) {
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

    if ($null -eq $Descriptor) {
        throw 'descriptor_required'
    }
    if ([int]$Descriptor.schema_version -ne 1 -or
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
    $sourceRoot = Get-CanonicalPath $Descriptor.reviewedSourceRoot
    if (-not (Test-PathInside $sourceRoot $materializationRoot)) {
        throw 'descriptor_source_outside_materialization'
    }
    foreach ($property in $script:DependencyProperties.Keys) {
        $path = Get-CanonicalPath $Descriptor.$property
        if (-not (Test-PathInside $path $materializationRoot)) {
            throw 'descriptor_dependency_outside_materialization'
        }
        if ($RequireFiles -and -not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw 'descriptor_dependency_missing'
        }
    }
    if ($RequireFiles -and
        -not (Test-Path -LiteralPath $sourceRoot -PathType Container)) {
        throw 'descriptor_source_missing'
    }
}

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string] $Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
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

function Test-SkippedSourceRelativePath {
    param([string] $RelativePath)
    $normalized = $RelativePath.Replace('\', '/')
    if ($normalized -in @(
        'package.json',
        'package-lock.json',
        'apps/web/package.json',
        'apps/web/package-lock.json',
        'apps/desktop/package.json',
        'apps/desktop/package-lock.json',
        'packages/cowork-presentation/package.json'
    )) {
        return $true
    }
    $segments = $normalized.Split('/')
    foreach ($segment in $segments) {
        if ($segment -in @(
            '.git',
            '.superpowers',
            'node_modules',
            '.build',
            'release',
            'dist',
            'dist-electron',
            'profiles',
            'backups'
        )) {
            return $true
        }
    }
    return $false
}

function Copy-ReviewedTree {
    param(
        [Parameter(Mandatory = $true)][string] $SourceRoot,
        [Parameter(Mandatory = $true)][string] $DestinationRoot
    )
    $sourceCanonical = Get-CanonicalPath $SourceRoot
    foreach ($relativeRoot in @(
        'apps/desktop',
        'apps/web',
        'packages/cowork-presentation'
    )) {
        $start = Join-Path $sourceCanonical $relativeRoot
        if (-not (Test-Path -LiteralPath $start -PathType Container)) {
            throw 'reviewed_source_subtree_missing'
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
                if (Test-SkippedSourceRelativePath $relative) {
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

function Copy-GeneratedTree {
    param(
        [Parameter(Mandatory = $true)][string] $SourceRoot,
        [Parameter(Mandatory = $true)][string] $DestinationRoot
    )
    $sourceCanonical = Get-CanonicalPath $SourceRoot
    $queue = New-Object System.Collections.Generic.Queue[string]
    $queue.Enqueue($sourceCanonical)
    while ($queue.Count -gt 0) {
        $directory = $queue.Dequeue()
        foreach ($entry in Get-ChildItem -LiteralPath $directory -Force) {
            Assert-RegularNoLink $entry
            $relative = $entry.FullName.Substring(
                $sourceCanonical.Length
            ).TrimStart([char[]]@('\', '/'))
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

function Copy-AcceptedDependencies {
    param(
        $Descriptor,
        [Parameter(Mandatory = $true)][string] $DestinationRoot
    )
    foreach ($property in $script:DependencyProperties.Keys) {
        $relative = $script:DependencyProperties[$property]
        $source = [string]$Descriptor.$property
        $digestProperty = $property.Replace('Path', 'Sha256')
        Assert-ExpectedDigest $source ([string]$Descriptor.$digestProperty)
        Copy-FileCreateNew $source (Join-Path $DestinationRoot $relative)
    }
    foreach ($appLock in @(
        'apps/web/package-lock.json',
        'apps/desktop/package-lock.json'
    )) {
        if (Test-Path -LiteralPath (Join-Path $DestinationRoot $appLock)) {
            throw 'app_local_lock_forbidden'
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
        rootPackageJsonPath = Join-Path $acceptedRoot 'dependencies/package.json'
        rootPackageLockPath = Join-Path $acceptedRoot 'dependencies/package-lock.json'
        webPackageJsonPath = Join-Path $acceptedRoot 'dependencies/apps/web/package.json'
        desktopPackageJsonPath = Join-Path $acceptedRoot 'dependencies/apps/desktop/package.json'
        sharedPackageJsonPath = Join-Path $acceptedRoot 'dependencies/packages/cowork-presentation/package.json'
    }

    switch ($Case) {
        'reject-missing-descriptor' {
            try { Assert-DescriptorShape $null; $ok = $false }
            catch { $ok = ($_.Exception.Message -ceq 'descriptor_required') }
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
            $ok = (Test-PathInside $descriptor.reviewedSourceRoot $acceptedRoot)
            foreach ($property in $script:DependencyProperties.Keys) {
                $ok = $ok -and (Test-PathInside $descriptor.$property $acceptedRoot)
            }
        }
        'checkout-source-lock-sentinels-uncalled' {
            $mutableCheckoutInputs = @(
                (Join-Path $script:RepositoryRoot 'package-lock.json'),
                (Join-Path $script:RepositoryRoot 'apps/desktop/src')
            )
            $consumers = @(
                $descriptor.rootPackageLockPath,
                $descriptor.reviewedSourceRoot
            )
            $ok = -not @(
                $consumers | Where-Object { $_ -in $mutableCheckoutInputs }
            ).Count
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
        'delegates-only-sidecar-wrapper' {
            $plan = @(
                'npm ci',
                'npm run build -w @loopplane/web',
                'npm run build -w @loopplane/desktop',
                $script:SidecarWrapperPath,
                'npm run dist -w @loopplane/desktop'
            )
            $ok = (@($plan | Where-Object {
                $_ -eq $script:SidecarWrapperPath
            }).Count -eq 1)
            $ok = $ok -and (-not @($plan | Where-Object {
                $_ -match '(?i)pyinstaller'
            }).Count)
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
    Clear-ForbiddenChildEnvironment
    & $script:VerifierPath -AssertMaterializedInputs $descriptorFile
    if ($LASTEXITCODE -ne 0) {
        throw 'descriptor_offline_assertion_failed'
    }
    $descriptor = Get-Content -LiteralPath $descriptorFile -Raw |
        ConvertFrom-Json
    Assert-DescriptorShape $descriptor -RequireFiles

    $buildParent = Join-Path `
        $script:RepositoryRoot `
        'apps/desktop/.build/package-roots'
    if (-not (Test-Path -LiteralPath $buildParent -PathType Container)) {
        New-Item -ItemType Directory -Path $buildParent -Force | Out-Null
    }
    $buildRoot = Join-Path $buildParent ([guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $buildRoot | Out-Null
    Copy-ReviewedTree $descriptor.reviewedSourceRoot $buildRoot
    Copy-AcceptedDependencies $descriptor $buildRoot
    & $script:VerifierPath -AssertMaterializedInputs $descriptorFile
    if ($LASTEXITCODE -ne 0) {
        throw 'descriptor_post_copy_assertion_failed'
    }

    $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
    Invoke-TokenFreeCommand $npm @('ci') $buildRoot
    Invoke-TokenFreeCommand $npm @(
        'run', 'typecheck', '-w', '@loopplane/cowork-presentation'
    ) $buildRoot
    Invoke-TokenFreeCommand $npm @(
        'run', 'build', '-w', '@loopplane/web'
    ) $buildRoot
    Invoke-TokenFreeCommand $npm @(
        'run', 'build', '-w', '@loopplane/desktop'
    ) $buildRoot

    $sidecarResult = Join-Path $buildRoot 'sidecar-result.json'
    Invoke-TokenFreeCommand `
        (Join-Path $PSHOME 'powershell.exe') `
        @(
            '-NoProfile',
            '-NonInteractive',
            '-File',
            $script:SidecarWrapperPath,
            '-DescriptorPath',
            $descriptorFile,
            '-ResultPath',
            $sidecarResult
        ) `
        $buildRoot
    $sidecar = Get-Content -LiteralPath $sidecarResult -Raw | ConvertFrom-Json
    $sidecarDestination = Join-Path $buildRoot 'apps/desktop/sidecar/dist'
    New-Item -ItemType Directory -Path $sidecarDestination | Out-Null
    Copy-GeneratedTree $sidecar.output_root $sidecarDestination
    & $script:VerifierPath -AssertMaterializedInputs $descriptorFile
    if ($LASTEXITCODE -ne 0) {
        throw 'descriptor_pre_package_assertion_failed'
    }

    # electron-builder 只能由 accepted Desktop dist script 間接執行。
    Invoke-TokenFreeCommand $npm @(
        'run', 'dist', '-w', '@loopplane/desktop'
    ) $buildRoot
    $releaseRoot = Join-Path $buildRoot 'apps/desktop/release'
    if (-not (Test-Path -LiteralPath $releaseRoot -PathType Container)) {
        throw 'electron_builder_output_missing'
    }
    $result = [ordered]@{
        mode = 'delivery-package'
        build_root = $buildRoot
        release_output_path = $releaseRoot
        descriptor_sha256 = Get-Sha256 $descriptorFile
    }
    if (-not [string]::IsNullOrWhiteSpace($ResultPath)) {
        Write-BoundedResult (Get-CanonicalPath $ResultPath) $result
    } else {
        $result | ConvertTo-Json -Compress | Write-Output
    }
    exit 0
} catch {
    Write-PublicFail 'package_build_failed'
    exit 2
}
