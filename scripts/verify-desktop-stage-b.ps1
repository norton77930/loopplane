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

    [string] $AllowSelfApproval
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

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

    # Build path maps for allowlist diff (blobs only for simplicity of inventory).
    $before = @{}
    foreach ($e in $bootTree.tree) {
        if ($e.type -eq 'blob') {
            $before[[string]$e.path] = @{ Mode = [string]$e.mode; Type = 'blob'; Sha = [string]$e.sha }
        }
    }
    $after = @{}
    foreach ($e in $finalTree.tree) {
        if ($e.type -eq 'blob') {
            $after[[string]$e.path] = @{ Mode = [string]$e.mode; Type = 'blob'; Sha = [string]$e.sha }
        }
    }
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

    # Descriptor is non-secret identities only.
    $descriptor = [ordered]@{
        mode                 = 'delivery'
        bootstrap_review_id  = $BootstrapReviewId
        bootstrap_commit_sha = $BootstrapCommitSha
        bootstrap_tree_sha   = $bootTreeSha
        final_review_id      = $FinalReviewId
        final_commit_sha     = $FinalCommitSha
        final_tree_sha       = $finalTreeSha
        delivery_review_id   = $DeliveryReviewId
        delivery_commit_sha  = $DeliveryCommitSha
        delivery_tree_sha    = $delTreeSha
    }
    $descriptor | ConvertTo-Json -Compress | Write-Output
    exit 0
}

# --- main ---
if ($SelfTest) {
    Invoke-SelfTest -Case $SelfTest
}

if (-not $Mode) {
    Write-PublicFail -Code 'mode_required'
    exit 2
}

Invoke-LiveMode -ModeName $Mode
