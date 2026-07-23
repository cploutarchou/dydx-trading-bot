[CmdletBinding()]
param(
    [switch] $Install,
    [switch] $ShowInstructions
)

Set-StrictMode -Version Latest

function Find-Makefile {
    $directory = Get-Item -LiteralPath (Get-Location)
    while ($null -ne $directory) {
        foreach ($name in @('GNUmakefile', 'makefile', 'Makefile')) {
            $candidate = Join-Path $directory.FullName $name
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                return $candidate
            }
        }
        $directory = $directory.Parent
    }
    return $null
}

function Get-MakeTarget {
    param([Parameter(Mandatory = $true)][string] $Makefile)

    $seen = @{}
    foreach ($line in Get-Content -LiteralPath $Makefile -Encoding UTF8) {
        if ($line -match '^([A-Za-z0-9][A-Za-z0-9_.-]*):.*?(?:##\s+(.+))?$') {
            $name = $Matches[1]
            if (-not $seen.ContainsKey($name)) {
                $seen[$name] = $true
                [PSCustomObject]@{
                    Name = $name
                    Description = if ($Matches.Count -gt 2) { $Matches[2] } else { '' }
                }
            }
        }
    }
}

$completer = {
    param($wordToComplete, $commandAst, $cursorPosition)

    $makefile = Find-Makefile
    if ($null -eq $makefile) { return }

    Get-MakeTarget -Makefile $makefile |
        Where-Object { $_.Name -like "$wordToComplete*" } |
        Sort-Object Name |
        ForEach-Object {
            [System.Management.Automation.CompletionResult]::new(
                $_.Name,
                $_.Name,
                [System.Management.Automation.CompletionResultType]::ParameterValue,
                $_.Description
            )
        }
}

Register-ArgumentCompleter -Native -CommandName make, gmake -ScriptBlock $completer

if ($Install) {
    $profilePath = $PROFILE.CurrentUserCurrentHost
    $profileDirectory = Split-Path -Parent $profilePath
    if (-not (Test-Path -LiteralPath $profileDirectory)) {
        New-Item -ItemType Directory -Path $profileDirectory -Force | Out-Null
    }
    if (-not (Test-Path -LiteralPath $profilePath)) {
        New-Item -ItemType File -Path $profilePath -Force | Out-Null
    }

    $escapedScriptPath = $PSCommandPath.Replace("'", "''")
    $loadLine = ". '$escapedScriptPath'"
    $alreadyInstalled = Select-String -LiteralPath $profilePath -SimpleMatch $loadLine -Quiet
    if (-not $alreadyInstalled) {
        Add-Content -LiteralPath $profilePath -Encoding UTF8 -Value @(
            '',
            '# GNU Make target completion (dydx-trading-bot)',
            $loadLine
        )
        Write-Host "Installed Make completion in $profilePath"
    } else {
        Write-Host "Make completion is already installed in $profilePath"
    }
    Write-Host 'Restart PowerShell, then type: make <Tab>'
} elseif ($ShowInstructions) {
    Write-Host 'Enable completion for this PowerShell session:'
    Write-Host '  . .\scripts\powershell\MakeCompletion.ps1'
    Write-Host ''
    Write-Host 'Install completion for future PowerShell sessions:'
    Write-Host '  make install-completion-powershell'
}
