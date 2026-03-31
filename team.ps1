[CmdletBinding()]
param(
	[Parameter(Position = 0)]
	[ValidateSet("help", "env", "up", "down", "ps", "logs", "restart", "infra-up", "infra-down", "infra-ps", "infra-logs", "local-up", "local-down", "local-ps", "local-logs")]
	[string]$Action = "help",

	[ValidateSet("dev", "prod")]
	[string]$Mode = "dev",

	[int]$Tail = 100,

	[switch]$IncludeWorker,

	[ValidateSet("all", "backend", "bot-api", "frontend", "worker")]
	[string]$Service = "all"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Info([string]$Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Ok([string]$Message) { Write-Host "[OK]   $Message" -ForegroundColor Green }
function Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Err([string]$Message) { Write-Host "[ERR]  $Message" -ForegroundColor Red }

function Require-Command([string]$Name, [string]$Hint) {
	if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
		throw "Missing required command '$Name'. $Hint"
	}
}

function Show-Help {
	@(
		"dYdX team runner (Windows PowerShell)",
		"",
		"Usage:",
		"  .\team.ps1 <action> [-Mode dev|prod] [-Service all|backend|bot-api|frontend|worker]",
		"",
		"Actions:",
		"  env         Create .env.stack from .env.stack.example (if missing)",
		"  local-up    Start services locally (backend + bot-api + frontend; add -IncludeWorker for worker)",
		"  local-down  Stop locally started services",
		"  local-ps    Show locally started services and health",
		"  local-logs  Tail local log file(s) from ./.local-logs",
		"  up          Start full stack (frontend + api + worker + postgres + redis)",
		"  down        Stop full stack",
		"  ps          Show stack status",
		"  logs        Follow stack logs",
		"  restart     Restart full stack",
		"  infra-up    Start infra only (postgres + redis)",
		"  infra-down  Stop infra only",
		"  infra-ps    Show infra status",
		"  infra-logs  Follow infra logs",
		"",
		"Examples:",
		"  .\team.ps1 local-up",
		"  .\team.ps1 local-up -IncludeWorker",
		"  .\team.ps1 local-ps",
		"  .\team.ps1 local-logs -Service backend",
		"  .\team.ps1 up -Mode dev",
		"  .\team.ps1 logs",
		"  .\team.ps1 down",
		"",
		"Tip: Local mode is for native dev (no full docker stack). Stack mode is for integration."
	) | ForEach-Object { Write-Host $_ }
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$stackEnv = Join-Path $repoRoot ".env.stack"
$stackEnvExample = Join-Path $repoRoot ".env.stack.example"
$stackCompose = Join-Path $repoRoot "docker-compose.stack.yml"
$infraCompose = Join-Path $repoRoot "docker-compose.infra.yml"
$stackValidator = Join-Path $repoRoot "scripts/validate_stack_env.py"
$localStatePath = Join-Path $repoRoot ".local-services.json"
$localLogDir = Join-Path $repoRoot ".local-logs"

$localServiceConfig = @(
	@{
		Name            = "backend"
		WorkDir         = "backend"
		Command         = ".\\make.ps1 run"
		Log             = "backend.log"
		HealthUrl       = "http://127.0.0.1:8888/health"
		RequiredCommand = "go"
		RequiredHint    = "Install Go 1.23+ and ensure it is in PATH."
	},
	@{
		Name            = "bot-api"
		WorkDir         = "bot"
		Command         = "python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8889 --reload"
		Log             = "bot-api.log"
		HealthUrl       = "http://127.0.0.1:8889/health"
		RequiredCommand = "python"
		RequiredHint    = "Install Python and ensure it is in PATH (or use your venv/devcontainer)."
	},
	@{
		Name            = "frontend"
		WorkDir         = "frontend"
		Command         = "npm run dev -- --host 0.0.0.0 --port 5173"
		Log             = "frontend.log"
		HealthUrl       = "http://127.0.0.1:5173"
		RequiredCommand = "npm"
		RequiredHint    = "Install Node.js + npm and ensure it is in PATH."
	},
	@{
		Name            = "worker"
		WorkDir         = "bot"
		Command         = "python src/main_instance.py --instance-id bot-1"
		Log             = "worker.log"
		HealthUrl       = ""
		RequiredCommand = "python"
		RequiredHint    = "Install Python and ensure it is in PATH (or use your venv/devcontainer)."
	}
)

function Get-LocalState {
	if (-not (Test-Path $localStatePath)) {
		return @{}
	}

	try {
		$state = Get-Content -Path $localStatePath -Raw | ConvertFrom-Json -AsHashtable
		if ($null -eq $state) { return @{} }
		return $state
	}
	catch {
		Warn "Failed to parse local state file; starting with empty state"
		return @{}
	}
}

function Save-LocalState([hashtable]$State) {
	$json = $State | ConvertTo-Json -Depth 6
	Set-Content -Path $localStatePath -Value $json
}

function Ensure-LocalLogDir {
	if (-not (Test-Path $localLogDir)) {
		New-Item -Path $localLogDir -ItemType Directory | Out-Null
	}
}

function Resolve-ServiceSelection {
	$selected = @()
	if ($Service -eq "all") {
		$selected = $localServiceConfig | Where-Object { $_.Name -ne "worker" }
		if ($IncludeWorker.IsPresent) {
			$selected += ($localServiceConfig | Where-Object { $_.Name -eq "worker" })
		}
	}
	else {
		$selected = $localServiceConfig | Where-Object { $_.Name -eq $Service }
	}

	return $selected
}

function Start-LocalServices {
	$selection = Resolve-ServiceSelection
	if ($selection.Count -eq 0) {
		throw "No services selected"
	}

	Ensure-LocalLogDir
	$state = Get-LocalState

	foreach ($svc in $selection) {
		Require-Command $svc.RequiredCommand $svc.RequiredHint

		if ($state.ContainsKey($svc.Name)) {
			$existingPid = [int]$state[$svc.Name].pid
			if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
				Warn "$($svc.Name) already running (pid=$existingPid); skipping"
				continue
			}
		}

		$workDir = Join-Path $repoRoot $svc.WorkDir
		$logPath = Join-Path $localLogDir $svc.Log

		Info "Starting $($svc.Name) locally..."
		$proc = Start-Process -FilePath "powershell" `
			-ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $svc.Command) `
			-WorkingDirectory $workDir `
			-RedirectStandardOutput $logPath `
			-RedirectStandardError $logPath `
			-PassThru

		$state[$svc.Name] = @{
			pid       = $proc.Id
			startedAt = (Get-Date).ToUniversalTime().ToString("o")
			workDir   = $svc.WorkDir
			log       = $svc.Log
			healthUrl = $svc.HealthUrl
		}
		Ok "$($svc.Name) started (pid=$($proc.Id))"
	}

	Save-LocalState -State $state
	Write-Host "Local logs directory: $localLogDir" -ForegroundColor Cyan
}

function Stop-LocalServices {
	$selection = Resolve-ServiceSelection
	$state = Get-LocalState

	if ($state.Count -eq 0) {
		Warn "No local service state found"
		return
	}

	foreach ($svc in $selection) {
		if (-not $state.ContainsKey($svc.Name)) {
			Warn "$($svc.Name) not found in local state"
			continue
		}

		$pid = [int]$state[$svc.Name].pid
		$proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
		if ($proc) {
			Info "Stopping $($svc.Name) (pid=$pid)..."
			Stop-Process -Id $pid -Force
			Ok "$($svc.Name) stopped"
		}
		else {
			Warn "$($svc.Name) pid=$pid not running"
		}

		$state.Remove($svc.Name) | Out-Null
	}

	Save-LocalState -State $state
}

function Show-LocalStatus {
	$selection = Resolve-ServiceSelection
	$state = Get-LocalState

	if ($selection.Count -eq 0) {
		Warn "No services selected"
		return
	}

	foreach ($svc in $selection) {
		if (-not $state.ContainsKey($svc.Name)) {
			Write-Host ("{0,-10} : not tracked" -f $svc.Name) -ForegroundColor Yellow
			continue
		}

		$entry = $state[$svc.Name]
		$pid = [int]$entry.pid
		$proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
		$procStatus = if ($proc) { "running" } else { "stopped" }

		$healthStatus = "n/a"
		if (-not [string]::IsNullOrWhiteSpace($entry.healthUrl)) {
			try {
				$response = Invoke-WebRequest -Uri $entry.healthUrl -Method GET -TimeoutSec 3 -UseBasicParsing
				$healthStatus = "http $($response.StatusCode)"
			}
			catch {
				$healthStatus = "unreachable"
			}
		}

		Write-Host ("{0,-10} : {1,-8} pid={2} health={3}" -f $svc.Name, $procStatus, $pid, $healthStatus)
	}
}

function Show-LocalLogs {
	$selection = Resolve-ServiceSelection
	$targets = @()

	foreach ($svc in $selection) {
		$targets += (Join-Path $localLogDir $svc.Log)
	}

	$existing = $targets | Where-Object { Test-Path $_ }
	if ($existing.Count -eq 0) {
		Warn "No log files found yet in $localLogDir"
		return
	}

	Get-Content -Path $existing -Tail $Tail -Wait
}

function Ensure-StackEnv {
	if (Test-Path $stackEnv) {
		Info ".env.stack already exists"
		return
	}

	if (-not (Test-Path $stackEnvExample)) {
		throw "Missing .env.stack.example at repo root"
	}

	Copy-Item -Path $stackEnvExample -Destination $stackEnv
	Ok "Created .env.stack from template"
}

function Invoke-StackValidation {
	if (-not (Test-Path $stackValidator)) {
		Warn "Stack validator script not found; skipping env validation"
		return
	}

	if (Get-Command python -ErrorAction SilentlyContinue) {
		& python $stackValidator
		return
	}

	if (Get-Command python3 -ErrorAction SilentlyContinue) {
		& python3 $stackValidator
		return
	}

	Warn "python/python3 not found; skipping stack env validation"
}

function Compose-CommonArgs {
	$args = @("compose")
	if (Test-Path $stackEnv) {
		$args += @("--env-file", ".env.stack")
	}
	return $args
}

Push-Location $repoRoot
try {
	switch ($Action) {
		"help" {
			Show-Help
		}

		"local-up" {
			Start-LocalServices
		}

		"local-down" {
			Stop-LocalServices
		}

		"local-ps" {
			Show-LocalStatus
		}

		"local-logs" {
			Show-LocalLogs
		}

		"env" {
			Ensure-StackEnv
		}

		"up" {
			Require-Command "docker" "Install Docker Desktop and ensure 'docker compose' works."
			Ensure-StackEnv
			Invoke-StackValidation

			$args = Compose-CommonArgs
			$profile = if ($Mode -eq "prod") { "prod" } else { "dev" }

			Info "Starting full stack profile '$profile'..."
			& docker @args -f "docker-compose.stack.yml" --profile $profile up -d --remove-orphans
			Ok "Stack started"

			if ($Mode -eq "dev") {
				Write-Host "Frontend: http://localhost:5173" -ForegroundColor Cyan
				Write-Host "Bot API:   http://localhost:8889" -ForegroundColor Cyan
			}
			else {
				Write-Host "Proxy:     http://localhost:8080" -ForegroundColor Cyan
			}
		}

		"down" {
			Require-Command "docker" "Install Docker Desktop and ensure 'docker compose' works."
			$args = Compose-CommonArgs
			Info "Stopping full stack..."
			& docker @args -f "docker-compose.stack.yml" --profile dev --profile prod down --remove-orphans
			Ok "Stack stopped"
		}

		"ps" {
			Require-Command "docker" "Install Docker Desktop and ensure 'docker compose' works."
			$args = Compose-CommonArgs
			& docker @args -f "docker-compose.stack.yml" ps
		}

		"logs" {
			Require-Command "docker" "Install Docker Desktop and ensure 'docker compose' works."
			$args = Compose-CommonArgs
			& docker @args -f "docker-compose.stack.yml" logs -f --tail=$Tail
		}

		"restart" {
			Require-Command "docker" "Install Docker Desktop and ensure 'docker compose' works."
			Info "Restarting full stack..."
			& $PSCommandPath down
			& $PSCommandPath up -Mode $Mode
			Ok "Stack restarted"
		}

		"infra-up" {
			Require-Command "docker" "Install Docker Desktop and ensure 'docker compose' works."
			Ensure-StackEnv
			$args = @("compose")
			if (Test-Path $stackEnv) {
				$args += @("--env-file", ".env.stack")
			}
			Info "Starting infra (postgres + redis)..."
			& docker @args -f "docker-compose.infra.yml" up -d --remove-orphans
			Ok "Infra started"
		}

		"infra-down" {
			Require-Command "docker" "Install Docker Desktop and ensure 'docker compose' works."
			$args = @("compose")
			if (Test-Path $stackEnv) {
				$args += @("--env-file", ".env.stack")
			}
			Info "Stopping infra..."
			& docker @args -f "docker-compose.infra.yml" down --remove-orphans
			Ok "Infra stopped"
		}

		"infra-ps" {
			Require-Command "docker" "Install Docker Desktop and ensure 'docker compose' works."
			$args = @("compose")
			if (Test-Path $stackEnv) {
				$args += @("--env-file", ".env.stack")
			}
			& docker @args -f "docker-compose.infra.yml" ps
		}

		"infra-logs" {
			Require-Command "docker" "Install Docker Desktop and ensure 'docker compose' works."
			$args = @("compose")
			if (Test-Path $stackEnv) {
				$args += @("--env-file", ".env.stack")
			}
			& docker @args -f "docker-compose.infra.yml" logs -f --tail=$Tail
		}
	}
}
finally {
	Pop-Location
}
