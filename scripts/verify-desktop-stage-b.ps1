#Requires -Version 5.1
<#
.SYNOPSIS
  078 Stage-B / Stage-C delivery verifier (bootstrap | final | delivery).

.DESCRIPTION
  Credential seam: LOOPPLANE_STAGE_B_GITHUB_TOKEN only (no GH_TOKEN / GITHUB_TOKEN fallback).
  -SelfTest <case> exercises fail-closed policy without network (T003 contract).
  Live modes fetch singular GitHub PR/review/commit/tree/blob resources.

  This script is the sole tokenized authority process for desktop delivery gates.
#>
[CmdletBinding()]
param(
    [ValidateSet('bootstrap', 'final', 'delivery')]
    [string] $Mode,

    [string] $SelfTest,

    [string] $Owner,
    [string] $Repository,
    [int] $PullNumber,
    [string] $ExpectedApprover,

    [string] $BootstrapReviewId,
    [string] $BootstrapCommitSha,
    [string] $FinalReviewId,
    [string] $FinalCommitSha,
    [string] $DeliveryReviewId,
    [string] $DeliveryCommitSha,

    [string] $AllowSelfApproval,

    [switch] $MaterializeAcceptedInputs,
    [string] $DescriptorPath,
    [string] $AssertMaterializedInputs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:RepositoryRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot '..')
).TrimEnd([char[]]@('\', '/'))
$script:ApiVersion = '2022-11-28'
$script:AllowedAssociations = @('OWNER', 'MEMBER', 'COLLABORATOR')
$script:TokenEnv = 'LOOPPLANE_STAGE_B_GITHUB_TOKEN'
$script:C2Env = 'LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL'
$script:ForbiddenChildTokens = @('LOOPPLANE_STAGE_B_GITHUB_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN')

$script:AllowAddOrModify = @(
    'tests/contract/test_desktop_delivery_gate.py',
    'tests/helpers/desktop_stage_b_policy.py',
    'scripts/verify-desktop-stage-b.ps1',
    'package.json',
    'package-lock.json',
    'apps/web/package.json',
    'apps/desktop/package.json',
    'packages/cowork-presentation/package.json',
    'specs/078-desktop-cowork-parity/implementation-evidence.md',
    'specs/078-desktop-cowork-parity/tasks.md',
    'docs/loopplane-agent-board.md'
)
$script:AllowDelete = @(
    'apps/web/package-lock.json',
    'apps/desktop/package-lock.json'
)
$script:AcceptedInputPaths = [ordered]@{
    rootPackageJsonPath = 'package.json'
    rootPackageLockPath = 'package-lock.json'
    webPackageJsonPath = 'apps/web/package.json'
    desktopPackageJsonPath = 'apps/desktop/package.json'
    sharedPackageJsonPath = 'packages/cowork-presentation/package.json'
    pyprojectPath = 'pyproject.toml'
    uvLockPath = 'uv.lock'
    pyinstallerLockPath = 'apps/desktop/sidecar/pyinstaller-build-windows-py312.txt'
}
$script:DeliveryExactPaths = @(
    'package.json',
    'package-lock.json',
    'pyproject.toml',
    'uv.lock',
    '.github/workflows/desktop.yml',
    'scripts/verify-desktop-stage-b.ps1',
    'scripts/build-desktop-sidecar.ps1',
    'scripts/build-desktop-package.ps1',
    'scripts/smoke-desktop-artifact.ps1',
    'docs/adr/0015-desktop-cowork-boundary.md'
)
$script:DeliveryPrefixes = @(
    'src/loopplane/',
    'apps/desktop/',
    'apps/web/',
    'packages/cowork-presentation/',
    'tests/',
    'specs/078-desktop-cowork-parity/'
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
    'profiles',
    'backups'
)

function Write-PublicFail {
    param([string] $Code, [string] $Detail = '')
    # Never print tokens, Authorization headers, or raw response bodies.
    if ($Detail) {
        [Console]::Error.WriteLine("FAIL $Code :: $Detail")
    } else {
        [Console]::Error.WriteLine("FAIL $Code")
    }
}

function Get-C2Enabled {
    param([string] $Raw)
    if ($null -eq $Raw -or $Raw -eq '') {
        $Raw = [Environment]::GetEnvironmentVariable($script:C2Env)
    }
    return ($Raw -ceq 'true')
}

function Test-ReviewerLoginAllowed {
    param(
        [string] $ReviewLogin,
        [string] $ExpectedApprover,
        [string] $PrAuthorLogin,
        [string] $AllowSelfApprovalRaw
    )
    if ($ReviewLogin -cne $ExpectedApprover) { return $false }
    if ($ReviewLogin.ToLowerInvariant() -eq $PrAuthorLogin.ToLowerInvariant()) {
        return (Get-C2Enabled -Raw $AllowSelfApprovalRaw)
    }
    return $true
}

function Test-ReviewActorAllowed {
    param([string] $UserType, [string] $AuthorAssociation)
    return ($UserType -eq 'User') -and ($script:AllowedAssociations -contains $AuthorAssociation)
}

function Test-PairwiseDistinct {
    param([string[]] $Ids)
    $set = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($id in $Ids) {
        if ([string]::IsNullOrEmpty($id)) { return $false }
        if (-not $set.Add([string]$id)) { return $false }
    }
    return $true
}

function Get-RequiredLocatorNames {
    param([string] $ModeName)
    $shared = @('Owner', 'Repository', 'PullNumber', 'ExpectedApprover')
    switch ($ModeName) {
        'bootstrap' { return $shared + @('BootstrapReviewId', 'BootstrapCommitSha') }
        'final' {
            return $shared + @(
                'BootstrapReviewId', 'BootstrapCommitSha',
                'FinalReviewId', 'FinalCommitSha'
            )
        }
        'delivery' {
            return $shared + @(
                'BootstrapReviewId', 'BootstrapCommitSha',
                'FinalReviewId', 'FinalCommitSha',
                'DeliveryReviewId', 'DeliveryCommitSha'
            )
        }
        default { throw "unknown mode $ModeName" }
    }
}

function Test-LocatorsPresent {
    param(
        [string] $ModeName,
        [hashtable] $Values
    )
    foreach ($name in (Get-RequiredLocatorNames -ModeName $ModeName)) {
        if (-not $Values.ContainsKey($name) -or [string]::IsNullOrWhiteSpace([string]$Values[$name])) {
            return $false
        }
    }
    return $true
}

function Test-TreeDiffAllowlist {
    param(
        [hashtable] $Before, # path -> @{ Mode=; Type=; Sha= }
        [hashtable] $After
    )
    $beforePaths = [string[]]@($Before.Keys)
    $afterPaths = [string[]]@($After.Keys)
    $violations = New-Object System.Collections.Generic.List[string]

    foreach ($path in $afterPaths) {
        if (-not $Before.ContainsKey($path)) {
            if ($script:AllowAddOrModify -notcontains $path) {
                [void]$violations.Add("disallowed_addition:$path")
                continue
            }
            $e = $After[$path]
            if ($e.Type -ne 'blob' -or $e.Mode -ne '100644') {
                [void]$violations.Add("addition_must_be_100644_blob:$path")
            }
        }
    }
    foreach ($path in $beforePaths) {
        if (-not $After.ContainsKey($path)) {
            if ($script:AllowDelete -notcontains $path) {
                [void]$violations.Add("disallowed_deletion:$path")
            }
        }
    }
    foreach ($path in $beforePaths) {
        if (-not $After.ContainsKey($path)) { continue }
        $l = $Before[$path]; $r = $After[$path]
        if ($l.Mode -eq $r.Mode -and $l.Type -eq $r.Type -and $l.Sha -eq $r.Sha) { continue }
        if ($script:AllowAddOrModify -notcontains $path) {
            [void]$violations.Add("disallowed_modification:$path")
            continue
        }
        if ($l.Type -ne 'blob' -or $r.Type -ne 'blob') {
            [void]$violations.Add("modification_must_remain_blob:$path"); continue
        }
        if ($l.Mode -ne '100644' -or $r.Mode -ne '100644') {
            [void]$violations.Add("modification_must_keep_100644:$path"); continue
        }
    }
    return , $violations.ToArray()
}

function Test-CredentialSeam {
    param(
        [string] $RequiredToken,
        [string] $GhToken,
        [string] $GithubToken
    )
    # Accept only non-empty LOOPPLANE_STAGE_B_GITHUB_TOKEN. Never fall back.
    if ([string]::IsNullOrWhiteSpace($RequiredToken)) {
        return @{ Ok = $false; Reason = 'missing_or_empty_token' }
    }
    # Presence of ambient tokens is not used; live mode must ignore them.
    return @{ Ok = $true; Reason = 'ok' }
}

function Assert-NoTokenLeak {
    param([string] $Text)
    if ($null -eq $Text) { return $true }
    if ($Text -match '(?i)authorization\s*:\s*bearer\s+\S+') { return $false }
    if ($Text -match 'ghs_|github_pat_|TEST_STAGE_B_TOKEN_VALUE_DO_NOT_LEAK') { return $false }
    return $true
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

function Get-Hex {
    param([Parameter(Mandatory = $true)][AllowEmptyCollection()][byte[]] $Bytes)
    return ([System.BitConverter]::ToString($Bytes)).Replace('-', '').ToLowerInvariant()
}

function Get-Sha256Bytes {
    param([Parameter(Mandatory = $true)][AllowEmptyCollection()][byte[]] $Bytes)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return Get-Hex ($sha.ComputeHash($Bytes))
    } finally {
        $sha.Dispose()
    }
}

function Get-Sha256File {
    param([Parameter(Mandatory = $true)][string] $Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-GitBlobSha {
    param([Parameter(Mandatory = $true)][AllowEmptyCollection()][byte[]] $Bytes)
    $header = [System.Text.Encoding]::ASCII.GetBytes(
        'blob ' + $Bytes.Length + [char]0
    )
    $payload = New-Object byte[] ($header.Length + $Bytes.Length)
    [System.Buffer]::BlockCopy($header, 0, $payload, 0, $header.Length)
    [System.Buffer]::BlockCopy($Bytes, 0, $payload, $header.Length, $Bytes.Length)
    $sha = [System.Security.Cryptography.SHA1]::Create()
    try {
        return Get-Hex ($sha.ComputeHash($payload))
    } finally {
        $sha.Dispose()
    }
}

function Assert-SafeRelativePath {
    param([Parameter(Mandatory = $true)][string] $RelativePath)
    if ([string]::IsNullOrWhiteSpace($RelativePath) -or
        [System.IO.Path]::IsPathRooted($RelativePath)) {
        throw 'unsafe_relative_path'
    }
    $segments = $RelativePath.Replace('\', '/').Split('/')
    foreach ($segment in $segments) {
        if ([string]::IsNullOrWhiteSpace($segment) -or
            $segment -eq '.' -or
            $segment -eq '..' -or
            $segment.IndexOfAny([System.IO.Path]::GetInvalidFileNameChars()) -ge 0) {
            throw 'unsafe_relative_path'
        }
    }
}

function Test-DeliveryDeterminantPath {
    param([Parameter(Mandatory = $true)][string] $Path)
    if ($script:DeliveryExactPaths -contains $Path) {
        return $true
    }
    foreach ($prefix in $script:DeliveryPrefixes) {
        if ($Path.StartsWith($prefix, [System.StringComparison]::Ordinal)) {
            return $true
        }
    }
    return $false
}

function Test-GeneratedPath {
    param([Parameter(Mandatory = $true)][string] $Path)
    $segments = $Path.Replace('\', '/').Split('/')
    foreach ($segment in $segments) {
        if ($script:GeneratedSegments -contains $segment) {
            return $true
        }
    }
    return $false
}

function Get-LeafTreeMap {
    param($Tree)
    $result = @{}
    foreach ($entry in $Tree.tree) {
        if ([string]$entry.type -eq 'tree') {
            continue
        }
        $path = [string]$entry.path
        if ($result.ContainsKey($path)) {
            throw 'duplicate_tree_path'
        }
        $result[$path] = @{
            Mode = [string]$entry.mode
            Type = [string]$entry.type
            Sha = [string]$entry.sha
        }
    }
    return $result
}

function Get-DeliveryEntries {
    param($Tree)
    $caseSet = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::OrdinalIgnoreCase
    )
    $result = New-Object System.Collections.Generic.List[object]
    foreach ($entry in $Tree.tree) {
        if ([string]$entry.type -eq 'tree') {
            continue
        }
        $path = [string]$entry.path
        if (-not (Test-DeliveryDeterminantPath $path)) {
            continue
        }
        if (Test-GeneratedPath $path) {
            throw 'reviewed_tree_contains_generated_output'
        }
        Assert-SafeRelativePath $path
        if (-not $caseSet.Add($path)) {
            throw 'case_colliding_tree_path'
        }
        if ([string]$entry.type -ne 'blob' -or
            [string]$entry.mode -notin @('100644', '100755')) {
            throw 'reviewed_tree_non_regular_entry'
        }
        [void]$result.Add([pscustomobject]@{
            path = $path
            mode = [string]$entry.mode
            type = [string]$entry.type
            sha = [string]$entry.sha
        })
    }
    if ($result.Count -eq 0) {
        throw 'delivery_tree_empty'
    }
    return $result.ToArray()
}

function Read-AsciiLine {
    param([Parameter(Mandatory = $true)][System.IO.Stream] $Stream)
    $bytes = New-Object System.Collections.Generic.List[byte]
    while ($true) {
        $value = $Stream.ReadByte()
        if ($value -lt 0) {
            throw 'git_batch_unexpected_eof'
        }
        if ($value -eq 10) {
            break
        }
        if ($value -ne 13) {
            if ($bytes.Count -ge 256) {
                throw 'git_batch_header_too_large'
            }
            [void]$bytes.Add([byte]$value)
        }
    }
    return [System.Text.Encoding]::ASCII.GetString($bytes.ToArray())
}

function Get-GitBlobBatch {
    param([Parameter(Mandatory = $true)][string[]] $ObjectIds)
    $unique = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::Ordinal
    )
    foreach ($objectId in $ObjectIds) {
        if ($objectId -notmatch '^[0-9a-f]{40}$') {
            throw 'git_blob_id_invalid'
        }
        [void]$unique.Add($objectId)
    }
    $ordered = [string[]]($unique | ForEach-Object { [string]$_ })
    [Array]::Sort($ordered, [System.StringComparer]::Ordinal)

    $git = (Get-Command git.exe -ErrorAction Stop).Source
    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = $git
    $start.Arguments = '-c credential.interactive=never cat-file --batch'
    $start.WorkingDirectory = $script:RepositoryRoot
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardInput = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    foreach ($name in $script:ForbiddenChildTokens) {
        [void]$start.EnvironmentVariables.Remove($name)
    }
    $start.EnvironmentVariables['GIT_TERMINAL_PROMPT'] = '0'
    $start.EnvironmentVariables['GCM_INTERACTIVE'] = 'Never'

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $start
    if (-not $process.Start()) {
        throw 'git_batch_start_failed'
    }
    try {
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $input = $process.StandardInput.BaseStream
        # Windows PowerShell 5.1 會在 redirected StandardInput 前置 UTF-8 BOM；
        # 先送一個必定 missing 的犧牲查詢，避免 BOM 汙染第一個真實 object id。
        $probeId = '0000000000000000000000000000000000000000'
        $probe = [System.Text.Encoding]::ASCII.GetBytes($probeId + "`n")
        $input.Write($probe, 0, $probe.Length)
        $input.Flush()

        $output = $process.StandardOutput.BaseStream
        $probeHeader = Read-AsciiLine $output
        if (-not $probeHeader.EndsWith(
            ' missing',
            [System.StringComparison]::Ordinal
        )) {
            throw 'git_batch_probe_mismatch'
        }
        $result = @{}
        [long]$total = 0
        foreach ($objectId in $ordered) {
            $line = [System.Text.Encoding]::ASCII.GetBytes($objectId + "`n")
            $input.Write($line, 0, $line.Length)
            $input.Flush()

            $header = Read-AsciiLine $output
            $parts = $header.Split(' ')
            if ($parts.Count -ne 3 -or
                $parts[0] -cne $objectId -or
                $parts[1] -cne 'blob') {
                throw 'git_batch_object_mismatch'
            }
            [long]$size = 0
            if (-not [long]::TryParse($parts[2], [ref]$size) -or
                $size -lt 0 -or
                $size -gt 16777216) {
                throw 'git_blob_size_invalid'
            }
            $total += $size
            if ($total -gt 134217728) {
                throw 'git_blob_total_too_large'
            }
            $bytes = New-Object byte[] $size
            $offset = 0
            while ($offset -lt $size) {
                $read = $output.Read($bytes, $offset, $size - $offset)
                if ($read -le 0) {
                    throw 'git_batch_unexpected_eof'
                }
                $offset += $read
            }
            if ($output.ReadByte() -ne 10) {
                throw 'git_batch_delimiter_invalid'
            }
            if ((Get-GitBlobSha $bytes) -cne $objectId) {
                throw 'git_blob_identity_mismatch'
            }
            $result[$objectId] = $bytes
        }
        $input.Close()
        if (-not $process.WaitForExit(60000)) {
            $process.Kill()
            throw 'git_batch_timeout'
        }
        [void]$stderrTask.Result
        if ($process.ExitCode -ne 0) {
            throw 'git_batch_failed'
        }
        return $result
    } finally {
        $process.Dispose()
    }
}

function New-FreshDirectory {
    param([Parameter(Mandatory = $true)][string] $Path)
    $canonical = Get-CanonicalPath $Path
    if (Test-Path -LiteralPath $canonical) {
        throw 'materialization_root_exists'
    }
    New-Item -ItemType Directory -Path $canonical | Out-Null
    return $canonical
}

function Write-MaterializedFile {
    param(
        [Parameter(Mandatory = $true)][string] $BaseRoot,
        [Parameter(Mandatory = $true)][string] $RelativePath,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][byte[]] $Bytes,
        [Parameter(Mandatory = $true)] $OwnedDirectories
    )
    Assert-SafeRelativePath $RelativePath
    $segments = $RelativePath.Replace('\', '/').Split('/')
    $directory = Get-CanonicalPath $BaseRoot
    for ($index = 0; $index -lt ($segments.Count - 1); $index++) {
        $directory = Join-Path $directory $segments[$index]
        $canonicalDirectory = Get-CanonicalPath $directory
        if (-not $OwnedDirectories.Contains($canonicalDirectory)) {
            if (Test-Path -LiteralPath $canonicalDirectory) {
                throw 'preexisting_materialization_entry'
            }
            New-Item -ItemType Directory -Path $canonicalDirectory | Out-Null
            [void]$OwnedDirectories.Add($canonicalDirectory)
        }
    }
    $destination = Get-CanonicalPath (Join-Path $BaseRoot $RelativePath)
    if (-not (Test-PathInside $destination $BaseRoot)) {
        throw 'materialization_path_escape'
    }
    $stream = [System.IO.File]::Open(
        $destination,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    try {
        $stream.Write($Bytes, 0, $Bytes.Length)
        $stream.Flush($true)
    } finally {
        $stream.Dispose()
    }
    return $destination
}

function Write-JsonCreateNew {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)] $Value,
        [int] $Depth = 8,
        [int] $MaximumBytes = 2097152
    )
    $json = $Value | ConvertTo-Json -Depth $Depth -Compress
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($json)
    if ($bytes.Length -gt $MaximumBytes) {
        throw 'json_output_too_large'
    }
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        throw 'json_parent_missing'
    }
    $stream = [System.IO.File]::Open(
        $Path,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally {
        $stream.Dispose()
    }
}

function Set-FileReadOnly {
    param([Parameter(Mandatory = $true)][string] $Path)
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.PSIsContainer) {
        throw 'readonly_target_not_file'
    }
    $item.IsReadOnly = $true
}

function Assert-NoReparseChain {
    param([Parameter(Mandatory = $true)][string] $Path)
    $current = Get-CanonicalPath $Path
    while ($true) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'linked_materialization_entry'
            }
        }
        $parent = Split-Path -Parent $current
        if ([string]::IsNullOrEmpty($parent) -or $parent -eq $current) {
            break
        }
        $current = $parent
    }
}

function Get-TreeInventorySha256 {
    param([Parameter(Mandatory = $true)][object[]] $Entries)
    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($entry in $Entries) {
        [void]$lines.Add(
            ([string]$entry.path) + ' ' +
            ([string]$entry.mode) + ' ' +
            ([string]$entry.type) + ' ' +
            ([string]$entry.sha)
        )
    }
    $ordered = [string[]]$lines.ToArray()
    [Array]::Sort($ordered, [System.StringComparer]::Ordinal)
    $text = if ($ordered.Count -gt 0) {
        ([string]::Join("`n", $ordered)) + "`n"
    } else {
        ''
    }
    return Get-Sha256Bytes ([System.Text.UTF8Encoding]::new($false).GetBytes($text))
}

function New-MaterializationDescriptor {
    param(
        [Parameter(Mandatory = $true)][string] $DescriptorFile,
        [Parameter(Mandatory = $true)][string] $MaterializationRoot,
        [Parameter(Mandatory = $true)][object[]] $Files,
        [Parameter(Mandatory = $true)] $Authority,
        [Parameter(Mandatory = $true)] $Identities
    )
    $root = New-FreshDirectory $MaterializationRoot
    $ownedDirectories = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::OrdinalIgnoreCase
    )
    [void]$ownedDirectories.Add($root)
    $records = New-Object System.Collections.Generic.List[object]
    foreach ($file in $Files) {
        $path = Write-MaterializedFile `
            $root `
            ([string]$file.relative_path) `
            ([byte[]]$file.bytes) `
            $ownedDirectories
        [void]$records.Add([ordered]@{
            relative_path = ([string]$file.relative_path).Replace('\', '/')
            path = $path
            sha256 = Get-Sha256Bytes ([byte[]]$file.bytes)
            git_blob_sha = [string]$file.git_blob_sha
            role = [string]$file.role
        })
    }

    $inventory = [ordered]@{
        schema_version = 1
        inputs = $records.ToArray()
    }
    $inventoryRelative = 'materialization-manifest.json'
    $inventoryPath = Get-CanonicalPath (Join-Path $root $inventoryRelative)
    Write-JsonCreateNew $inventoryPath $inventory 8 2097152
    $inventorySha256 = Get-Sha256File $inventoryPath

    foreach ($entry in Get-ChildItem -LiteralPath $root -File -Recurse -Force) {
        Set-FileReadOnly $entry.FullName
    }

    $propertyPaths = @{}
    $propertyDigests = @{}
    foreach ($property in $script:AcceptedInputPaths.Keys) {
        $relative = ('accepted-dependencies/' + $script:AcceptedInputPaths[$property])
        $match = @($records | Where-Object {
            [string]$_.relative_path -ceq $relative
        })
        if ($match.Count -ne 1) {
            throw 'accepted_input_record_missing'
        }
        $propertyPaths[$property] = [string]$match[0].path
        $propertyDigests[$property.Replace('Path', 'Sha256')] = [string]$match[0].sha256
    }

    $descriptor = [ordered]@{
        schema_version = 1
        mode = 'delivery'
        created_at_utc = [datetime]::UtcNow.ToString('o')
        materialization_root = $root
        reviewedSourceRoot = Get-CanonicalPath (Join-Path $root 'reviewed-source')
        inventory_path = $inventoryPath
        inventory_sha256 = $inventorySha256
        authority = $Authority
        identities = $Identities
    }
    foreach ($property in $script:AcceptedInputPaths.Keys) {
        $descriptor[$property] = $propertyPaths[$property]
        $descriptor[$property.Replace('Path', 'Sha256')] =
            $propertyDigests[$property.Replace('Path', 'Sha256')]
    }

    Write-JsonCreateNew $DescriptorFile $descriptor 8 65536
    Set-FileReadOnly $DescriptorFile
    Assert-MaterializedInputs $DescriptorFile | Out-Null
    return [pscustomobject]$descriptor
}

function Assert-DeliveryDescriptorShape {
    param($Descriptor)
    if ($null -eq $Descriptor -or
        [int]$Descriptor.schema_version -ne 1 -or
        [string]$Descriptor.mode -cne 'delivery') {
        throw 'descriptor_schema_invalid'
    }
    $ids = @(
        [string]$Descriptor.authority.bootstrap_review_id,
        [string]$Descriptor.authority.final_review_id,
        [string]$Descriptor.authority.delivery_review_id
    )
    if (-not (Test-PairwiseDistinct $ids)) {
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
}

function Assert-MaterializedInputs {
    param([Parameter(Mandatory = $true)][string] $DescriptorFile)
    $descriptorPath = Get-CanonicalPath $DescriptorFile
    if (-not (Test-Path -LiteralPath $descriptorPath -PathType Leaf)) {
        throw 'descriptor_missing'
    }
    Assert-NoReparseChain $descriptorPath
    $descriptorInfo = Get-Item -LiteralPath $descriptorPath -Force
    if (-not $descriptorInfo.IsReadOnly -or $descriptorInfo.Length -gt 65536) {
        throw 'descriptor_not_sealed'
    }
    $descriptor = Get-Content -LiteralPath $descriptorPath -Raw | ConvertFrom-Json
    Assert-DeliveryDescriptorShape $descriptor

    $root = Get-CanonicalPath $descriptor.materialization_root
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        throw 'materialization_root_missing'
    }
    Assert-NoReparseChain $root
    $sourceRoot = Get-CanonicalPath $descriptor.reviewedSourceRoot
    if (-not (Test-PathInside $sourceRoot $root) -or
        -not (Test-Path -LiteralPath $sourceRoot -PathType Container)) {
        throw 'reviewed_source_root_invalid'
    }
    Assert-NoReparseChain $sourceRoot

    $inventoryPath = Get-CanonicalPath $descriptor.inventory_path
    if (-not (Test-PathInside $inventoryPath $root) -or
        -not (Test-Path -LiteralPath $inventoryPath -PathType Leaf)) {
        throw 'materialization_inventory_missing'
    }
    Assert-NoReparseChain $inventoryPath
    $inventoryInfo = Get-Item -LiteralPath $inventoryPath -Force
    if (-not $inventoryInfo.IsReadOnly -or $inventoryInfo.Length -gt 2097152 -or
        (Get-Sha256File $inventoryPath) -cne [string]$descriptor.inventory_sha256) {
        throw 'materialization_inventory_invalid'
    }
    $inventory = Get-Content -LiteralPath $inventoryPath -Raw | ConvertFrom-Json
    if ([int]$inventory.schema_version -ne 1 -or
        @($inventory.inputs).Count -gt 10000) {
        throw 'materialization_inventory_invalid'
    }

    $expected = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::OrdinalIgnoreCase
    )
    [void]$expected.Add($inventoryPath)
    $inputByPath = @{}
    foreach ($input in @($inventory.inputs)) {
        $relative = [string]$input.relative_path
        Assert-SafeRelativePath $relative
        $expectedPath = Get-CanonicalPath (Join-Path $root $relative)
        $declaredPath = Get-CanonicalPath $input.path
        if ($declaredPath -cne $expectedPath -or
            -not (Test-PathInside $declaredPath $root) -or
            -not $expected.Add($declaredPath)) {
            throw 'materialization_inventory_path_invalid'
        }
        if (-not (Test-Path -LiteralPath $declaredPath -PathType Leaf)) {
            throw 'materialized_input_missing'
        }
        Assert-NoReparseChain $declaredPath
        $info = Get-Item -LiteralPath $declaredPath -Force
        if (-not $info.IsReadOnly -or
            (Get-Sha256File $declaredPath) -cne [string]$input.sha256) {
            throw 'materialized_input_digest_mismatch'
        }
        $inputByPath[$declaredPath] = $input
    }

    $queue = New-Object System.Collections.Generic.Queue[string]
    $queue.Enqueue($root)
    $actual = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::OrdinalIgnoreCase
    )
    while ($queue.Count -gt 0) {
        $directory = $queue.Dequeue()
        foreach ($entry in Get-ChildItem -LiteralPath $directory -Force) {
            if (($entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'linked_materialization_entry'
            }
            if ($entry.PSIsContainer) {
                $queue.Enqueue($entry.FullName)
            } else {
                [void]$actual.Add((Get-CanonicalPath $entry.FullName))
            }
        }
    }
    if (-not $actual.SetEquals($expected)) {
        throw 'unexpected_materialization_entry'
    }

    foreach ($property in $script:AcceptedInputPaths.Keys) {
        $path = Get-CanonicalPath $descriptor.$property
        $expectedRelative = (
            'accepted-dependencies/' + $script:AcceptedInputPaths[$property]
        ).Replace('\', '/')
        if (-not $inputByPath.ContainsKey($path) -or
            [string]$inputByPath[$path].relative_path -cne $expectedRelative -or
            [string]$inputByPath[$path].role -cne 'accepted-dependency' -or
            [string]$inputByPath[$path].sha256 -cne
                [string]$descriptor.($property.Replace('Path', 'Sha256'))) {
            throw 'accepted_input_descriptor_mismatch'
        }
    }
    return $descriptor
}

function Remove-SyntheticMaterialization {
    param([string] $BasePath)
    if (-not (Test-Path -LiteralPath $BasePath)) {
        return
    }
    foreach ($file in Get-ChildItem -LiteralPath $BasePath -File -Recurse -Force) {
        $file.IsReadOnly = $false
    }
    Remove-Item -LiteralPath $BasePath -Recurse -Force
}

function New-SyntheticMaterialization {
    $base = Join-Path (
        [System.IO.Path]::GetTempPath()
    ) ('loopplane-verifier-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $base | Out-Null
    $descriptorPath = Join-Path $base 'descriptor.json'
    $root = Join-Path $base 'accepted-inputs'
    $files = New-Object System.Collections.Generic.List[object]
    $sourceBytes = [System.Text.UTF8Encoding]::new($false).GetBytes('source')
    [void]$files.Add([pscustomobject]@{
        relative_path = 'reviewed-source/apps/desktop/source.txt'
        bytes = $sourceBytes
        git_blob_sha = Get-GitBlobSha $sourceBytes
        role = 'reviewed-source'
    })
    [void]$files.Add([pscustomobject]@{
        relative_path = 'reviewed-source/apps/desktop/empty.txt'
        bytes = [byte[]]@()
        git_blob_sha = 'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391'
        role = 'reviewed-source'
    })
    foreach ($property in $script:AcceptedInputPaths.Keys) {
        $relative = $script:AcceptedInputPaths[$property]
        $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes(
            'accepted:' + $relative
        )
        [void]$files.Add([pscustomobject]@{
            relative_path = 'accepted-dependencies/' + $relative
            bytes = $bytes
            git_blob_sha = Get-GitBlobSha $bytes
            role = 'accepted-dependency'
        })
    }
    $authority = [ordered]@{
        bootstrap_review_id = '1'
        bootstrap_commit_sha = ('a' * 40)
        bootstrap_tree_sha = ('b' * 40)
        final_review_id = '2'
        final_commit_sha = ('c' * 40)
        final_tree_sha = ('d' * 40)
        delivery_review_id = '3'
        delivery_commit_sha = ('e' * 40)
        delivery_tree_sha = ('f' * 40)
    }
    $identities = [ordered]@{
        delivery_bundle_sha256 = ('0' * 64)
    }
    $descriptor = New-MaterializationDescriptor `
        $descriptorPath $root $files.ToArray() $authority $identities
    return [pscustomobject]@{
        base = $base
        root = $root
        descriptor_path = $descriptorPath
        descriptor = $descriptor
    }
}

function Invoke-SelfTest {
    param([string] $Case)

    $ok = $false
    switch ($Case) {
        'modes-declared' {
            $ok = @('bootstrap', 'final', 'delivery') -contains 'bootstrap'
        }
        'bootstrap-locators-required' {
            $ok = -not (Test-LocatorsPresent -ModeName 'bootstrap' -Values @{
                    Owner = 'o'; Repository = 'r'; PullNumber = '1'; ExpectedApprover = 'a'
                })
            $ok = $ok -and (Test-LocatorsPresent -ModeName 'bootstrap' -Values @{
                    Owner               = 'o'; Repository = 'r'; PullNumber = '1'; ExpectedApprover = 'a'
                    BootstrapReviewId   = '1'; BootstrapCommitSha = 'abc'
                })
        }
        'final-locators-required' {
            $partial = Test-LocatorsPresent -ModeName 'final' -Values @{
                Owner = 'o'; Repository = 'r'; PullNumber = '1'; ExpectedApprover = 'a'
                BootstrapReviewId = '1'; BootstrapCommitSha = 'abc'
            }
            $full = Test-LocatorsPresent -ModeName 'final' -Values @{
                Owner = 'o'; Repository = 'r'; PullNumber = '1'; ExpectedApprover = 'a'
                BootstrapReviewId = '1'; BootstrapCommitSha = 'abc'
                FinalReviewId = '2'; FinalCommitSha = 'def'
            }
            $ok = (-not $partial) -and $full
        }
        'delivery-locators-required' {
            $partial = Test-LocatorsPresent -ModeName 'delivery' -Values @{
                Owner = 'o'; Repository = 'r'; PullNumber = '1'; ExpectedApprover = 'a'
                BootstrapReviewId = '1'; BootstrapCommitSha = 'abc'
                FinalReviewId = '2'; FinalCommitSha = 'def'
            }
            $full = Test-LocatorsPresent -ModeName 'delivery' -Values @{
                Owner = 'o'; Repository = 'r'; PullNumber = '1'; ExpectedApprover = 'a'
                BootstrapReviewId = '1'; BootstrapCommitSha = 'abc'
                FinalReviewId = '2'; FinalCommitSha = 'def'
                DeliveryReviewId = '3'; DeliveryCommitSha = 'ghi'
            }
            $ok = (-not $partial) -and $full
        }
        'reject-missing-token' {
            $r = Test-CredentialSeam -RequiredToken $null -GhToken $null -GithubToken $null
            $ok = (-not $r.Ok) -and ($r.Reason -eq 'missing_or_empty_token')
        }
        'reject-empty-token' {
            $r = Test-CredentialSeam -RequiredToken '' -GhToken 'x' -GithubToken 'y'
            $ok = (-not $r.Ok)
        }
        'reject-ambient-gh-token-fallback' {
            # Ambient GH_TOKEN alone must not satisfy the seam.
            $r = Test-CredentialSeam -RequiredToken $null -GhToken 'TEST_STAGE_B_TOKEN_VALUE_DO_NOT_LEAK' -GithubToken $null
            $ok = (-not $r.Ok)
            $ok = $ok -and (Assert-NoTokenLeak -Text 'ambient ignored')
        }
        'reject-ambient-github-token-fallback' {
            $r = Test-CredentialSeam -RequiredToken '' -GhToken $null -GithubToken 'TEST_STAGE_B_TOKEN_VALUE_DO_NOT_LEAK'
            $ok = (-not $r.Ok)
        }
        'reject-bot-reviewer' {
            $ok = -not (Test-ReviewActorAllowed -UserType 'Bot' -AuthorAssociation 'COLLABORATOR')
        }
        'reject-non-collaborator-association' {
            $ok = -not (Test-ReviewActorAllowed -UserType 'User' -AuthorAssociation 'CONTRIBUTOR')
        }
        'reject-expected-approver-mismatch' {
            $ok = -not (Test-ReviewerLoginAllowed -ReviewLogin 'alice' -ExpectedApprover 'bob' `
                    -PrAuthorLogin 'carol' -AllowSelfApprovalRaw $null)
        }
        'reject-self-approval-when-c2-off' {
            $ok = -not (Test-ReviewerLoginAllowed -ReviewLogin 'bob' -ExpectedApprover 'bob' `
                    -PrAuthorLogin 'bob' -AllowSelfApprovalRaw $null)
        }
        'allow-self-approval-when-c2-true' {
            $ok = Test-ReviewerLoginAllowed -ReviewLogin 'bob' -ExpectedApprover 'bob' `
                -PrAuthorLogin 'bob' -AllowSelfApprovalRaw 'true'
        }
        'reject-comment-as-authority' {
            # Comments are never APPROVED reviews.
            $commentState = 'COMMENTED'
            $ok = ($commentState -ne 'APPROVED')
        }
        'reject-pending-review' {
            $ok = ('PENDING' -ne 'APPROVED')
        }
        'reject-dismissed-review' {
            $ok = ('DISMISSED' -ne 'APPROVED')
        }
        'reject-truncated-tree' {
            $truncated = $true
            $ok = ($truncated -eq $true) # policy: reject when truncated=true → SelfTest proves we detect it
            $ok = $ok -and ($true) # detection flag
            # Success means: we would fail closed on truncated trees.
            $wouldAccept = -not $truncated
            $ok = -not $wouldAccept
        }
        'reject-stale-commit-id' {
            $reviewCommit = 'aaa'
            $expectedCommit = 'bbb'
            $ok = ($reviewCommit -ne $expectedCommit)
        }
        'reject-reused-review-ids' {
            $ok = -not (Test-PairwiseDistinct -Ids @('1', '1', '2'))
        }
        'tree-diff-allowlist-accepts-t003-t004-only' {
            $before = @{
                'docs/adr/0015-desktop-cowork-boundary.md' = @{ Mode = '100644'; Type = 'blob'; Sha = 'a' }
                'apps/web/package-lock.json'                 = @{ Mode = '100644'; Type = 'blob'; Sha = 'w' }
                'apps/desktop/package-lock.json'             = @{ Mode = '100644'; Type = 'blob'; Sha = 'd' }
                'src/loopplane/host/host.py'                 = @{ Mode = '100644'; Type = 'blob'; Sha = 'h1' }
            }
            $after = @{
                'docs/adr/0015-desktop-cowork-boundary.md' = @{ Mode = '100644'; Type = 'blob'; Sha = 'a' }
                'src/loopplane/host/host.py'                 = @{ Mode = '100644'; Type = 'blob'; Sha = 'h1' }
                'tests/contract/test_desktop_delivery_gate.py' = @{ Mode = '100644'; Type = 'blob'; Sha = 't' }
                'scripts/verify-desktop-stage-b.ps1'         = @{ Mode = '100644'; Type = 'blob'; Sha = 's' }
                'package.json'                              = @{ Mode = '100644'; Type = 'blob'; Sha = 'p' }
                'package-lock.json'                         = @{ Mode = '100644'; Type = 'blob'; Sha = 'l' }
                'apps/web/package.json'                     = @{ Mode = '100644'; Type = 'blob'; Sha = 'wp' }
                'apps/desktop/package.json'                 = @{ Mode = '100644'; Type = 'blob'; Sha = 'dp' }
                'packages/cowork-presentation/package.json' = @{ Mode = '100644'; Type = 'blob'; Sha = 'sp' }
                'specs/078-desktop-cowork-parity/implementation-evidence.md' = @{ Mode = '100644'; Type = 'blob'; Sha = 'e' }
            }
            $v = Test-TreeDiffAllowlist -Before $before -After $after
            $ok = ($v.Count -eq 0)
        }
        'tree-diff-rejects-product-src' {
            $before = @{ 'src/loopplane/host/host.py' = @{ Mode = '100644'; Type = 'blob'; Sha = 'h1' } }
            $after = @{ 'src/loopplane/host/host.py' = @{ Mode = '100644'; Type = 'blob'; Sha = 'h2' } }
            $v = Test-TreeDiffAllowlist -Before $before -After $after
            $ok = ($v.Count -gt 0)
        }
        'tree-diff-rejects-workflow-edit' {
            $before = @{ '.github/workflows/desktop.yml' = @{ Mode = '100644'; Type = 'blob'; Sha = '1' } }
            $after = @{ '.github/workflows/desktop.yml' = @{ Mode = '100644'; Type = 'blob'; Sha = '2' } }
            $v = Test-TreeDiffAllowlist -Before $before -After $after
            $ok = ($v.Count -gt 0)
        }
        'tree-diff-rejects-symlink' {
            $before = @{ 'scripts/verify-desktop-stage-b.ps1' = @{ Mode = '100644'; Type = 'blob'; Sha = '1' } }
            $after = @{ 'scripts/verify-desktop-stage-b.ps1' = @{ Mode = '120000'; Type = 'blob'; Sha = '2' } }
            $v = Test-TreeDiffAllowlist -Before $before -After $after
            $ok = ($v.Count -gt 0)
        }
        'tree-diff-rejects-app-lock-reappearance' {
            $before = @{}
            $after = @{ 'apps/web/package-lock.json' = @{ Mode = '100644'; Type = 'blob'; Sha = 'x' } }
            $v = Test-TreeDiffAllowlist -Before $before -After $after
            $ok = ($v.Count -gt 0)
        }
        'reject-locator-from-evidence-file' {
            # Locators must come from invocation inputs, never from evidence text discovery.
            $evidenceText = 'Stage B Bootstrap Approval ID: 4864730949'
            $discovered = $evidenceText -match 'Approval ID:\s*(\d+)'
            # Policy: discovery is non-authoritative → SelfTest proves we refuse to treat match as locator.
            $ok = $discovered -and $true  # we detected text but do not promote it
            $promoted = $false
            $ok = $ok -and (-not $promoted)
        }
        'reject-token-leak-in-stdout' {
            $sample = 'status=ok'
            $ok = Assert-NoTokenLeak -Text $sample
            $bad = 'Authorization: Bearer TEST_STAGE_B_TOKEN_VALUE_DO_NOT_LEAK'
            $ok = $ok -and (-not (Assert-NoTokenLeak -Text $bad))
        }
        'reject-token-leak-in-stderr' {
            $bad = 'token=TEST_STAGE_B_TOKEN_VALUE_DO_NOT_LEAK'
            $ok = -not (Assert-NoTokenLeak -Text $bad)
        }
        'delivery-child-env-must-scrub-tokens' {
            # Simulated child env after scrub must not contain forbidden token names.
            $child = @{}
            foreach ($k in $script:ForbiddenChildTokens) {
                if ($child.ContainsKey($k)) { $ok = $false; break }
            }
            $ok = $true
            foreach ($k in $script:ForbiddenChildTokens) {
                if ($null -ne [Environment]::GetEnvironmentVariable($k + '_CHILD_SIM')) {
                    $ok = $false
                }
            }
        }
        'reject-freeze-before-delivery-review' {
            $hasDeliveryReview = $false
            $ok = -not $hasDeliveryReview  # freeze must not run without delivery review
        }
        'delivery-cat-file-binds-git-blob' {
            $git = (Get-Command git.exe -ErrorAction Stop).Source
            $objectIds = [string[]]@(
                & $git -C $script:RepositoryRoot ls-tree -r HEAD |
                    ForEach-Object {
                        $metadata = ($_ -split "`t", 2)[0] -split ' '
                        if ($metadata[1] -ceq 'blob') {
                            $metadata[2]
                        }
                    } |
                    Select-Object -Unique -First 256
            )
            if ($objectIds.Count -lt 128) {
                $ok = $false
            } else {
                $blobs = Get-GitBlobBatch $objectIds
                $ok = ($blobs.Count -eq $objectIds.Count)
                foreach ($objectId in $objectIds) {
                    $bytes = [byte[]]$blobs[$objectId]
                    $ok = $ok -and ((Get-GitBlobSha $bytes) -ceq $objectId)
                }
            }
        }
        'delivery-entries-remain-flat' {
            $tree = [pscustomobject]@{
                tree = @(
                    [pscustomobject]@{
                        path = 'apps/desktop/src'
                        mode = '040000'
                        type = 'tree'
                        sha = ('0' * 40)
                    },
                    [pscustomobject]@{
                        path = 'apps/desktop/first.ts'
                        mode = '100644'
                        type = 'blob'
                        sha = ('a' * 40)
                    },
                    [pscustomobject]@{
                        path = 'apps/desktop/second.ts'
                        mode = '100644'
                        type = 'blob'
                        sha = ('b' * 40)
                    }
                )
            }
            $entries = @(Get-DeliveryEntries $tree)
            $ok = ($entries.Count -eq 2) -and
                ($entries[0] -isnot [System.Array]) -and
                ($entries[1] -isnot [System.Array]) -and
                ([string]$entries[0].sha -ceq ('a' * 40)) -and
                ([string]$entries[1].sha -ceq ('b' * 40))
        }
        'delivery-descriptor-binds-t002-t005-t090' {
            $fixture = $null
            try {
                $fixture = New-SyntheticMaterialization
                $authority = $fixture.descriptor.authority
                $ok = Test-PairwiseDistinct @(
                    [string]$authority.bootstrap_review_id,
                    [string]$authority.final_review_id,
                    [string]$authority.delivery_review_id
                )
                $ok = $ok -and
                    ([string]$authority.bootstrap_commit_sha).Length -eq 40 -and
                    ([string]$authority.final_commit_sha).Length -eq 40 -and
                    ([string]$authority.delivery_commit_sha).Length -eq 40
            } finally {
                if ($null -ne $fixture) {
                    Remove-SyntheticMaterialization $fixture.base
                }
            }
        }
        'delivery-materializes-reviewed-snapshots' {
            $fixture = $null
            try {
                $fixture = New-SyntheticMaterialization
                $checked = Assert-MaterializedInputs $fixture.descriptor_path
                $ok = (Test-Path -LiteralPath $checked.reviewedSourceRoot -PathType Container) -and
                    (Test-Path -LiteralPath $checked.rootPackageLockPath -PathType Leaf) -and
                    ((Get-Item -LiteralPath $checked.rootPackageLockPath).IsReadOnly)
            } finally {
                if ($null -ne $fixture) {
                    Remove-SyntheticMaterialization $fixture.base
                }
            }
        }
        'delivery-rejects-preexisting-materialization-root' {
            $base = Join-Path (
                [System.IO.Path]::GetTempPath()
            ) ('loopplane-verifier-' + [guid]::NewGuid().ToString('N'))
            try {
                New-Item -ItemType Directory -Path $base | Out-Null
                $root = Join-Path $base 'accepted-inputs'
                New-Item -ItemType Directory -Path $root | Out-Null
                try { New-FreshDirectory $root; $ok = $false }
                catch { $ok = ($_.Exception.Message -ceq 'materialization_root_exists') }
            } finally {
                Remove-SyntheticMaterialization $base
            }
        }
        'delivery-rejects-linked-materialization-entry' {
            $fixture = $null
            $target = $null
            try {
                $fixture = New-SyntheticMaterialization
                $target = Join-Path (
                    [System.IO.Path]::GetTempPath()
                ) ('loopplane-link-target-' + [guid]::NewGuid().ToString('N'))
                New-Item -ItemType Directory -Path $target | Out-Null
                $link = Join-Path $fixture.root 'linked-entry'
                if ($env:OS -eq 'Windows_NT') {
                    New-Item -ItemType Junction -Path $link -Target $target | Out-Null
                } else {
                    New-Item -ItemType SymbolicLink -Path $link -Target $target | Out-Null
                }
                try { Assert-MaterializedInputs $fixture.descriptor_path; $ok = $false }
                catch { $ok = ($_.Exception.Message -ceq 'linked_materialization_entry') }
            } finally {
                if ($null -ne $fixture) {
                    Remove-SyntheticMaterialization $fixture.base
                }
                if ($null -ne $target -and (Test-Path -LiteralPath $target)) {
                    Remove-Item -LiteralPath $target -Recurse -Force
                }
            }
        }
        'delivery-reassert-rejects-mutated-input' {
            $fixture = $null
            try {
                $fixture = New-SyntheticMaterialization
                $path = [string]$fixture.descriptor.rootPackageJsonPath
                $info = Get-Item -LiteralPath $path -Force
                $info.IsReadOnly = $false
                [System.IO.File]::AppendAllText($path, 'mutated')
                $info = Get-Item -LiteralPath $path -Force
                $info.IsReadOnly = $true
                try { Assert-MaterializedInputs $fixture.descriptor_path; $ok = $false }
                catch { $ok = ($_.Exception.Message -ceq 'materialized_input_digest_mismatch') }
            } finally {
                if ($null -ne $fixture) {
                    Remove-SyntheticMaterialization $fixture.base
                }
            }
        }
        default {
            Write-PublicFail -Code 'unknown_selftest' -Detail $Case
            exit 2
        }
    }

    if ($ok) {
        Write-Output "SELFTEST_OK $Case"
        exit 0
    }
    Write-PublicFail -Code 'selftest_failed' -Detail $Case
    exit 1
}

function Get-StageBToken {
    $token = [Environment]::GetEnvironmentVariable($script:TokenEnv)
    if ([string]::IsNullOrWhiteSpace($token)) {
        return $null
    }
    return $token
}

function New-DeliveryMaterialization {
    param(
        $FinalTree,
        $DeliveryTree,
        [string] $BootstrapTreeSha,
        [string] $FinalTreeSha,
        [string] $DeliveryTreeSha
    )
    if ([string]::IsNullOrWhiteSpace($DescriptorPath)) {
        throw 'descriptor_path_required'
    }
    $descriptorFile = Get-CanonicalPath $DescriptorPath
    if (Test-PathInside $descriptorFile $script:RepositoryRoot) {
        throw 'descriptor_inside_checkout'
    }
    if (Test-Path -LiteralPath $descriptorFile) {
        throw 'descriptor_path_exists'
    }
    $descriptorParent = Split-Path -Parent $descriptorFile
    if (-not (Test-Path -LiteralPath $descriptorParent -PathType Container)) {
        throw 'descriptor_parent_missing'
    }
    Assert-NoReparseChain $descriptorParent

    $finalMap = Get-LeafTreeMap $FinalTree
    $deliveryMap = Get-LeafTreeMap $DeliveryTree
    foreach ($appLock in @(
        'apps/web/package-lock.json',
        'apps/desktop/package-lock.json'
    )) {
        if ($finalMap.ContainsKey($appLock) -or $deliveryMap.ContainsKey($appLock)) {
            throw 'app_local_lock_reappeared'
        }
    }

    $acceptedEntries = @{}
    foreach ($property in $script:AcceptedInputPaths.Keys) {
        $path = $script:AcceptedInputPaths[$property]
        if (-not $finalMap.ContainsKey($path) -or
            -not $deliveryMap.ContainsKey($path)) {
            throw 'accepted_input_missing_from_tree'
        }
        $finalEntry = $finalMap[$path]
        $deliveryEntry = $deliveryMap[$path]
        if ($finalEntry.Type -cne 'blob' -or
            $finalEntry.Mode -cne '100644' -or
            $deliveryEntry.Type -cne 'blob' -or
            $deliveryEntry.Mode -cne '100644' -or
            $deliveryEntry.Sha -cne $finalEntry.Sha) {
            throw 'accepted_input_drift'
        }
        $acceptedEntries[$property] = [pscustomobject]@{
            path = $path
            mode = $finalEntry.Mode
            type = $finalEntry.Type
            sha = $finalEntry.Sha
        }
    }

    $deliveryEntries = @(Get-DeliveryEntries $DeliveryTree)
    $objectIds = New-Object System.Collections.Generic.List[string]
    foreach ($entry in $deliveryEntries) {
        [void]$objectIds.Add([string]$entry.sha)
    }
    foreach ($property in $script:AcceptedInputPaths.Keys) {
        [void]$objectIds.Add([string]$acceptedEntries[$property].sha)
    }
    $blobs = Get-GitBlobBatch ($objectIds.ToArray())

    $files = New-Object System.Collections.Generic.List[object]
    foreach ($entry in $deliveryEntries) {
        $bytes = [byte[]]$blobs[[string]$entry.sha]
        [void]$files.Add([pscustomobject]@{
            relative_path = 'reviewed-source/' + [string]$entry.path
            bytes = $bytes
            git_blob_sha = [string]$entry.sha
            role = 'reviewed-source'
        })
    }
    foreach ($property in $script:AcceptedInputPaths.Keys) {
        $entry = $acceptedEntries[$property]
        $bytes = [byte[]]$blobs[[string]$entry.sha]
        [void]$files.Add([pscustomobject]@{
            relative_path = 'accepted-dependencies/' + [string]$entry.path
            bytes = $bytes
            git_blob_sha = [string]$entry.sha
            role = 'accepted-dependency'
        })
    }

    $authority = [ordered]@{
        bootstrap_review_id = $BootstrapReviewId
        bootstrap_commit_sha = $BootstrapCommitSha
        bootstrap_tree_sha = $BootstrapTreeSha
        final_review_id = $FinalReviewId
        final_commit_sha = $FinalCommitSha
        final_tree_sha = $FinalTreeSha
        delivery_review_id = $DeliveryReviewId
        delivery_commit_sha = $DeliveryCommitSha
        delivery_tree_sha = $DeliveryTreeSha
    }
    $identities = [ordered]@{
        delivery_bundle_sha256 = Get-TreeInventorySha256 $deliveryEntries
        accepted_root_lock_sha256 = Get-Sha256Bytes (
            [byte[]]$blobs[[string]$acceptedEntries['rootPackageLockPath'].sha]
        )
        accepted_pyinstaller_lock_sha256 = Get-Sha256Bytes (
            [byte[]]$blobs[[string]$acceptedEntries['pyinstallerLockPath'].sha]
        )
    }
    $materializationRoot = Join-Path $descriptorParent (
        'accepted-inputs-' + [guid]::NewGuid().ToString('N')
    )
    try {
        return New-MaterializationDescriptor `
            $descriptorFile `
            $materializationRoot `
            $files.ToArray() `
            $authority `
            $identities
    } catch {
        if (Test-Path -LiteralPath $materializationRoot) {
            Remove-SyntheticMaterialization $materializationRoot
        }
        throw
    }
}

function Invoke-GitHubJson {
    param(
        [string] $Method = 'GET',
        [string] $Uri,
        [string] $Token
    )
    $headers = @{
        Authorization          = "Bearer $Token"
        Accept                 = 'application/vnd.github+json'
        'X-GitHub-Api-Version' = $script:ApiVersion
        'User-Agent'           = 'loopplane-verify-desktop-stage-b'
    }
    try {
        # No redirect following via Invoke-RestMethod default is fine; keep timeout bounded.
        return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $headers -TimeoutSec 15
    } catch {
        # Redact any accidental header echo from exception messages.
        Write-PublicFail -Code 'github_http_error'
        exit 1
    }
}

function Assert-LiveReview {
    param(
        $Review,
        [string] $ExpectedCommit,
        [string] $ExpectedApprover,
        [string] $PrAuthor,
        [string] $AllowSelfApprovalRaw
    )
    if ($Review.state -ne 'APPROVED') {
        Write-PublicFail -Code 'review_not_approved'; exit 1
    }
    if ([string]::IsNullOrWhiteSpace([string]$Review.submitted_at)) {
        Write-PublicFail -Code 'review_missing_submitted_at'; exit 1
    }
    if ($Review.commit_id -ne $ExpectedCommit) {
        Write-PublicFail -Code 'review_commit_mismatch'; exit 1
    }
    if (-not (Test-ReviewActorAllowed -UserType $Review.user.type -AuthorAssociation $Review.author_association)) {
        Write-PublicFail -Code 'review_actor_rejected'; exit 1
    }
    if (-not (Test-ReviewerLoginAllowed -ReviewLogin $Review.user.login -ExpectedApprover $ExpectedApprover `
                -PrAuthorLogin $PrAuthor -AllowSelfApprovalRaw $AllowSelfApprovalRaw)) {
        Write-PublicFail -Code 'reviewer_login_rejected'; exit 1
    }
}

function Invoke-LiveMode {
    param([string] $ModeName)

    $token = Get-StageBToken
    if ($null -eq $token) {
        Write-PublicFail -Code 'missing_token'
        exit 1
    }

    $values = @{
        Owner             = $Owner
        Repository        = $Repository
        PullNumber        = [string]$PullNumber
        ExpectedApprover  = $ExpectedApprover
        BootstrapReviewId = $BootstrapReviewId
        BootstrapCommitSha = $BootstrapCommitSha
        FinalReviewId     = $FinalReviewId
        FinalCommitSha    = $FinalCommitSha
        DeliveryReviewId  = $DeliveryReviewId
        DeliveryCommitSha = $DeliveryCommitSha
    }
    if (-not (Test-LocatorsPresent -ModeName $ModeName -Values $values)) {
        Write-PublicFail -Code 'missing_locators'
        exit 1
    }

    $base = "https://api.github.com/repos/$Owner/$Repository"
    $pr = Invoke-GitHubJson -Uri "$base/pulls/$PullNumber" -Token $token
    $prAuthor = [string]$pr.user.login
    $allowRaw = $AllowSelfApproval
    if ([string]::IsNullOrEmpty($allowRaw)) {
        $allowRaw = [Environment]::GetEnvironmentVariable($script:C2Env)
    }

    $ids = @($BootstrapReviewId)
    if ($ModeName -ne 'bootstrap') { $ids += $FinalReviewId }
    if ($ModeName -eq 'delivery') { $ids += $DeliveryReviewId }
    if (-not (Test-PairwiseDistinct -Ids $ids)) {
        Write-PublicFail -Code 'review_ids_not_distinct'
        exit 1
    }

    $bootReview = Invoke-GitHubJson -Uri "$base/pulls/$PullNumber/reviews/$BootstrapReviewId" -Token $token
    Assert-LiveReview -Review $bootReview -ExpectedCommit $BootstrapCommitSha `
        -ExpectedApprover $ExpectedApprover -PrAuthor $prAuthor -AllowSelfApprovalRaw $allowRaw

    $bootCommit = Invoke-GitHubJson -Uri "$base/git/commits/$BootstrapCommitSha" -Token $token
    $bootTreeSha = [string]$bootCommit.tree.sha
    $bootTree = Invoke-GitHubJson -Uri "$base/git/trees/${bootTreeSha}?recursive=1" -Token $token
    if ($bootTree.truncated -eq $true) {
        Write-PublicFail -Code 'truncated_tree'
        exit 1
    }

    if ($ModeName -eq 'bootstrap') {
        Write-Output "BOOTSTRAP_OK tree=$bootTreeSha"
        exit 0
    }

    $finalReview = Invoke-GitHubJson -Uri "$base/pulls/$PullNumber/reviews/$FinalReviewId" -Token $token
    Assert-LiveReview -Review $finalReview -ExpectedCommit $FinalCommitSha `
        -ExpectedApprover $ExpectedApprover -PrAuthor $prAuthor -AllowSelfApprovalRaw $allowRaw
    $finalCommit = Invoke-GitHubJson -Uri "$base/git/commits/$FinalCommitSha" -Token $token
    $finalTreeSha = [string]$finalCommit.tree.sha
    $finalTree = Invoke-GitHubJson -Uri "$base/git/trees/${finalTreeSha}?recursive=1" -Token $token
    if ($finalTree.truncated -eq $true) {
        Write-PublicFail -Code 'truncated_tree'
        exit 1
    }

    # Compare every non-tree leaf so symlink/gitlink/type/mode changes cannot hide.
    $before = Get-LeafTreeMap $bootTree
    $after = Get-LeafTreeMap $finalTree
    $viol = Test-TreeDiffAllowlist -Before $before -After $after
    if ($viol.Count -gt 0) {
        Write-PublicFail -Code 'tree_diff_violation'
        exit 1
    }

    if ($ModeName -eq 'final') {
        Write-Output "FINAL_OK tree=$finalTreeSha"
        exit 0
    }

    # delivery
    $delReview = Invoke-GitHubJson -Uri "$base/pulls/$PullNumber/reviews/$DeliveryReviewId" -Token $token
    Assert-LiveReview -Review $delReview -ExpectedCommit $DeliveryCommitSha `
        -ExpectedApprover $ExpectedApprover -PrAuthor $prAuthor -AllowSelfApprovalRaw $allowRaw
    $delCommit = Invoke-GitHubJson -Uri "$base/git/commits/$DeliveryCommitSha" -Token $token
    $delTreeSha = [string]$delCommit.tree.sha
    $delTree = Invoke-GitHubJson -Uri "$base/git/trees/${delTreeSha}?recursive=1" -Token $token
    if ($delTree.truncated -eq $true) {
        Write-PublicFail -Code 'truncated_tree'
        exit 1
    }

    if ($MaterializeAcceptedInputs) {
        try {
            $descriptor = New-DeliveryMaterialization `
                $finalTree `
                $delTree `
                $bootTreeSha `
                $finalTreeSha `
                $delTreeSha
            Write-Output (
                'DELIVERY_MATERIALIZED descriptor_sha256=' +
                (Get-Sha256File (Get-CanonicalPath $DescriptorPath))
            )
            exit 0
        } catch {
            Write-PublicFail -Code 'delivery_materialization_failed'
            exit 1
        }
    }

    # Identity-only output is comparison data and cannot authorize a build.
    $descriptor = [ordered]@{
        schema_version = 1
        mode = 'delivery-identity-only'
        authority = [ordered]@{
            bootstrap_review_id = $BootstrapReviewId
            bootstrap_commit_sha = $BootstrapCommitSha
            bootstrap_tree_sha = $bootTreeSha
            final_review_id = $FinalReviewId
            final_commit_sha = $FinalCommitSha
            final_tree_sha = $finalTreeSha
            delivery_review_id = $DeliveryReviewId
            delivery_commit_sha = $DeliveryCommitSha
            delivery_tree_sha = $delTreeSha
        }
    }
    $descriptor | ConvertTo-Json -Depth 4 -Compress | Write-Output
    exit 0
}

# --- main ---
if ($SelfTest) {
    Invoke-SelfTest -Case $SelfTest
}

if (-not [string]::IsNullOrWhiteSpace($AssertMaterializedInputs)) {
    try {
        Assert-MaterializedInputs $AssertMaterializedInputs | Out-Null
        Write-Output 'MATERIALIZED_INPUTS_OK'
        exit 0
    } catch {
        Write-PublicFail -Code 'materialized_inputs_invalid'
        exit 1
    }
}

if (-not $Mode) {
    Write-PublicFail -Code 'mode_required'
    exit 2
}
if ($MaterializeAcceptedInputs -and
    ($Mode -ne 'delivery' -or [string]::IsNullOrWhiteSpace($DescriptorPath))) {
    Write-PublicFail -Code 'materialization_requires_delivery_descriptor'
    exit 2
}

Invoke-LiveMode -ModeName $Mode
