param(
    [string]$BaseUrl = 'http://localhost:5173',
    [string]$ManifestPath = 'scripts/responsive-screenshot-routes.json',
    [string]$OutputDir = 'docs/screenshots/responsive',
    [string]$BrowserPath,
    [string]$UserDataDir,
    [string]$ProfileDirectory,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

function Resolve-BrowserPath {
    param([string]$Candidate)

    if ($Candidate -and (Test-Path $Candidate)) {
        return (Resolve-Path $Candidate).Path
    }

    $edgePaths = @(
        'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
    )

    foreach ($path in $edgePaths) {
        if (Test-Path $path) {
            return $path
        }
    }

    return $null
}

function Ensure-Directory {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function New-TemporaryProfileClone {
    param(
        [string]$OriginalUserDataDir,
        [string]$OriginalProfileDirectory
    )

    if (-not $OriginalUserDataDir -or -not (Test-Path $OriginalUserDataDir)) {
        return $null
    }

    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('dydx-responsive-capture-' + [System.Guid]::NewGuid().ToString('N'))
    Ensure-Directory -Path $tempRoot

    $localStateSource = Join-Path $OriginalUserDataDir 'Local State'
    if (Test-Path $localStateSource) {
        Copy-Item -Path $localStateSource -Destination (Join-Path $tempRoot 'Local State') -Force
    }

    if ($OriginalProfileDirectory) {
        $profileSource = Join-Path $OriginalUserDataDir $OriginalProfileDirectory
        if (Test-Path $profileSource) {
            Copy-Item -Path $profileSource -Destination (Join-Path $tempRoot $OriginalProfileDirectory) -Recurse -Force
        }
    }

    return $tempRoot
}

function Invoke-ScreenshotCapture {
    param(
        [string]$Executable,
        [string]$TargetUrl,
        [int]$Width,
        [int]$Height,
        [string]$OutputPath,
        [string]$ProfilePath,
        [string]$ProfileName,
        [switch]$IsDryRun
    )

    $args = @(
        '--headless=new',
        '--disable-gpu',
        '--disable-extensions',
        '--disable-component-extensions-with-background-pages',
        '--no-first-run',
        '--no-default-browser-check',
        '--hide-scrollbars',
        '--run-all-compositor-stages-before-draw',
        '--virtual-time-budget=10000',
        '--window-size={0},{1}' -f $Width, $Height,
        '--screenshot={0}' -f $OutputPath,
        $TargetUrl
    )

    if ($ProfilePath) {
        $args = @('--user-data-dir={0}' -f $ProfilePath) + $args
    }

    if ($ProfileName) {
        $args = @('--profile-directory={0}' -f $ProfileName) + $args
    }

    if ($IsDryRun) {
        Write-Host ('DRY RUN  -> {0} [{1}x{2}]' -f $TargetUrl, $Width, $Height) -ForegroundColor Yellow
        Write-Host ('           output: {0}' -f $OutputPath) -ForegroundColor DarkYellow
        return
    }

    Write-Host ('CAPTURE  -> {0} [{1}x{2}]' -f $TargetUrl, $Width, $Height) -ForegroundColor Cyan
    $process = Start-Process -FilePath $Executable -ArgumentList $args -PassThru -Wait -NoNewWindow
    if ($process.ExitCode -ne 0) {
        throw "Screenshot capture failed for $TargetUrl ($Width px). Exit code: $($process.ExitCode)"
    }
}

$resolvedBrowser = Resolve-BrowserPath -Candidate $BrowserPath
if (-not $resolvedBrowser) {
    throw 'Could not find Microsoft Edge. Pass -BrowserPath explicitly or install Edge.'
}

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$manifestFullPath = Join-Path $projectRoot $ManifestPath
$outputFullPath = Join-Path $projectRoot $OutputDir
$captureUserDataDir = $UserDataDir
$temporaryProfileClone = $null

if (-not (Test-Path $manifestFullPath)) {
    throw "Manifest file not found: $manifestFullPath"
}

Ensure-Directory -Path $outputFullPath

if ($UserDataDir) {
    $temporaryProfileClone = New-TemporaryProfileClone -OriginalUserDataDir $UserDataDir -OriginalProfileDirectory $ProfileDirectory
    if ($temporaryProfileClone) {
        $captureUserDataDir = $temporaryProfileClone
        Write-Host "Profile clone: $temporaryProfileClone" -ForegroundColor Green
    }
}

$viewports = @(
    @{ Width = 375; Height = 812 },
    @{ Width = 768; Height = 1024 },
    @{ Width = 1024; Height = 900 },
    @{ Width = 1440; Height = 1080 }
)

$routes = Get-Content -Path $manifestFullPath -Raw | ConvertFrom-Json

Write-Host "Using browser: $resolvedBrowser" -ForegroundColor Green
Write-Host "Manifest: $manifestFullPath" -ForegroundColor Green
Write-Host "Output:   $outputFullPath" -ForegroundColor Green

foreach ($route in $routes) {
    foreach ($viewport in $viewports) {
        $fileName = '{0}-{1}.png' -f $route.routeKey, $viewport.Width
        $targetUrl = '{0}{1}' -f $BaseUrl.TrimEnd('/'), $route.path
        $targetOutput = Join-Path $outputFullPath $fileName

        Invoke-ScreenshotCapture `
            -Executable $resolvedBrowser `
            -TargetUrl $targetUrl `
            -Width $viewport.Width `
            -Height $viewport.Height `
            -OutputPath $targetOutput `
            -ProfilePath $captureUserDataDir `
            -ProfileName $ProfileDirectory `
            -IsDryRun:$DryRun
    }
}

Write-Host 'Responsive screenshot capture plan complete.' -ForegroundColor Green

if ($temporaryProfileClone -and (Test-Path $temporaryProfileClone)) {
    Remove-Item -Path $temporaryProfileClone -Recurse -Force -ErrorAction SilentlyContinue
}


