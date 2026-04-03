[CmdletBinding()]
param(
    [string[]]$Paths
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendRoot = Split-Path -Parent $scriptRoot
$today = Get-Date -Format "yyyy-MM-dd"

if (-not $Paths -or $Paths.Count -eq 0) {
    $Paths = @(
        (Join-Path $backendRoot "tasks.md"),
        (Join-Path (Split-Path -Parent $backendRoot) "bot\tasks.md"),
        (Join-Path (Split-Path -Parent $backendRoot) "frontend\tasks.md")
    )
}

function Get-TaskCounts {
    param([string[]]$Lines)

    $completed = 0
    $pending = 0

    foreach ($line in $Lines) {
        if ($line -match '^\s*-\s*\[(x|X)\]\s+') {
            $completed++
        }
        elseif ($line -match '^\s*-\s*\[ \]\s+') {
            $pending++
        }
    }

    return @{ Completed = $completed; Pending = $pending }
}

function Update-StatusSummary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing tasks file: $Path"
    }

    $lines = Get-Content -LiteralPath $Path
    if ($lines.Count -eq 0) {
        throw "Empty tasks file: $Path"
    }

    $counts = Get-TaskCounts -Lines $lines

    $summaryHeaderIndex = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -eq "## Status Summary") {
            $summaryHeaderIndex = $i
            break
        }
    }

    $summaryBlock = @(
        "## Status Summary",
        "- Completed: ``$($counts.Completed)``",
        "- Pending: ``$($counts.Pending)``",
        "- Last updated: ``$today``",
        "- Note: update these totals whenever any `[x]` or `[ ]` task changes.",
        ""
    )

    if ($summaryHeaderIndex -lt 0) {
        # Insert after title and first blank line when summary is missing.
        $insertAt = 1
        if ($lines.Count -gt 1 -and $lines[1] -eq "") {
            $insertAt = 2
        }
        $before = @()
        if ($insertAt -gt 0) {
            $before = $lines[0..($insertAt - 1)]
        }
        $after = @()
        if ($insertAt -lt $lines.Count) {
            $after = $lines[$insertAt..($lines.Count - 1)]
        }
        $updated = @($before + $summaryBlock + $after)
    }
    else {
        $nextHeaderIndex = $lines.Count
        for ($j = $summaryHeaderIndex + 1; $j -lt $lines.Count; $j++) {
            if ($lines[$j] -match '^##\s+') {
                $nextHeaderIndex = $j
                break
            }
        }

        $before = @()
        if ($summaryHeaderIndex -gt 0) {
            $before = $lines[0..($summaryHeaderIndex - 1)]
        }

        $after = @()
        if ($nextHeaderIndex -lt $lines.Count) {
            $after = $lines[$nextHeaderIndex..($lines.Count - 1)]
        }

        $updated = @($before + $summaryBlock + $after)
    }

    Set-Content -LiteralPath $Path -Value $updated -Encoding utf8

    return [PSCustomObject]@{
        Path      = $Path
        Completed = $counts.Completed
        Pending   = $counts.Pending
    }
}

$results = @()
foreach ($path in $Paths) {
    $result = Update-StatusSummary -Path $path
    $results += $result
}

foreach ($result in $results) {
    Write-Host ("[OK] {0} -> Completed: {1}, Pending: {2}" -f $result.Path, $result.Completed, $result.Pending) -ForegroundColor Green
}

