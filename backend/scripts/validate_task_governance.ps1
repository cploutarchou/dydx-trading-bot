[CmdletBinding()]
param(
    [string[]]$Paths
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendRoot = Split-Path -Parent $scriptRoot
$repoRoot = Split-Path -Parent $backendRoot

if (-not $Paths -or $Paths.Count -eq 0) {
    $Paths = @(
        (Join-Path $backendRoot "tasks.md"),
        (Join-Path $repoRoot "bot\tasks.md"),
        (Join-Path $repoRoot "frontend\tasks.md")
    )
}

function Get-CheckboxCounts {
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

function Extract-StatusSummary {
    param([string[]]$Lines)

    $summaryIndex = -1
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -eq "## Status Summary") {
            $summaryIndex = $i
            break
        }
    }
    if ($summaryIndex -lt 0) {
        throw "Missing section: ## Status Summary"
    }

    $window = @()
    for ($j = $summaryIndex + 1; $j -lt [Math]::Min($summaryIndex + 8, $Lines.Count); $j++) {
        $window += $Lines[$j]
    }

    $completedLine = $window | Where-Object { $_ -match '^\s*-\s*Completed:\s*`\d+`\s*$' } | Select-Object -First 1
    $pendingLine = $window | Where-Object { $_ -match '^\s*-\s*Pending:\s*`\d+`\s*$' } | Select-Object -First 1
    $updatedLine = $window | Where-Object { $_ -match '^\s*-\s*Last updated:\s*`\d{4}-\d{2}-\d{2}`\s*$' } | Select-Object -First 1
    $noteLine = $window | Where-Object { $_ -match '^\s*-\s*Note:\s+update these totals whenever any \[x\] or \[ \] task changes\.?\s*$' } | Select-Object -First 1

    if (-not $completedLine) { throw "Missing or invalid Status Summary line: Completed" }
    if (-not $pendingLine) { throw "Missing or invalid Status Summary line: Pending" }
    if (-not $updatedLine) { throw "Missing or invalid Status Summary line: Last updated" }
    if (-not $noteLine) { throw "Missing Status Summary note line" }

    $completed = [int]([regex]::Match($completedLine, '\d+').Value)
    $pending = [int]([regex]::Match($pendingLine, '\d+').Value)

    return @{ Completed = $completed; Pending = $pending }
}

function Assert-Contains {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Content,
        [Parameter(Mandatory = $true)]
        [string]$Snippet,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if (-not $Content.Contains($Snippet)) {
        throw $Message
    }
}

$requiredSections = @(
    "## Status Summary",
    "## Ongoing Update Protocol",
    "## Change Log",
    "## Change Log Template"
)

foreach ($path in $Paths) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing tasks file: $path"
    }

    $lines = Get-Content -LiteralPath $path
    if ($lines.Count -eq 0) {
        throw "Empty tasks file: $path"
    }

    $content = [string]::Join("`n", $lines)

    foreach ($section in $requiredSections) {
        if (-not ($lines -contains $section)) {
            throw "Missing required section '$section' in $path"
        }
    }

    $summary = Extract-StatusSummary -Lines $lines
    $actual = Get-CheckboxCounts -Lines $lines

    if ($summary.Completed -ne $actual.Completed -or $summary.Pending -ne $actual.Pending) {
        throw "Status Summary mismatch in $path. Summary Completed/Pending=$($summary.Completed)/$($summary.Pending), actual=$($actual.Completed)/$($actual.Pending). Run tasks-summary to fix."
    }

    $filename = [System.IO.Path]::GetFileName((Resolve-Path -LiteralPath $path).Path)
    if ($filename -ieq "tasks.md") {
        if ($path -like "*\backend\tasks.md") {
            Assert-Contains -Content $content -Snippet "../bot/tasks.md" -Message "Missing ../bot/tasks.md link in backend tasks protocol"
            Assert-Contains -Content $content -Snippet "../frontend/tasks.md" -Message "Missing ../frontend/tasks.md link in backend tasks protocol"
        }
        elseif ($path -like "*\bot\tasks.md") {
            Assert-Contains -Content $content -Snippet "../backend/tasks.md" -Message "Missing ../backend/tasks.md link in bot tasks protocol"
            Assert-Contains -Content $content -Snippet "../frontend/tasks.md" -Message "Missing ../frontend/tasks.md link in bot tasks protocol"
            Assert-Contains -Content $content -Snippet "./tasks.md" -Message "Missing ./tasks.md link in bot tasks protocol"
        }
        elseif ($path -like "*\frontend\tasks.md") {
            Assert-Contains -Content $content -Snippet "../backend/tasks.md" -Message "Missing ../backend/tasks.md link in frontend tasks protocol"
            Assert-Contains -Content $content -Snippet "../bot/tasks.md" -Message "Missing ../bot/tasks.md link in frontend tasks protocol"
            Assert-Contains -Content $content -Snippet "./tasks.md" -Message "Missing ./tasks.md link in frontend tasks protocol"
        }
    }

    Write-Host ("[OK] {0} governance validated (Completed={1}, Pending={2})" -f $path, $actual.Completed, $actual.Pending) -ForegroundColor Green
}

