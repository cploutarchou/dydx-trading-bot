[CmdletBinding()]
param(
	[Parameter(Position = 0)]
	[string]$Target = "help",

	[ValidateSet("development", "production")]
	[string]$Mode = "development",

	[string]$Name,

	[switch]$Yes
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
	Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Success([string]$Message) {
	Write-Host "[OK]   $Message" -ForegroundColor Green
}

function Write-WarnMsg([string]$Message) {
	Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-ErrMsg([string]$Message) {
	Write-Host "[ERR]  $Message" -ForegroundColor Red
}

function Require-Command([string]$CommandName, [string]$Hint) {
	if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
		throw "Required command '$CommandName' was not found. $Hint"
	}
}

function Test-CommandAvailable([string]$CommandName) {
	return $null -ne (Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Update-EnvFileValue {
	param(
		[Parameter(Mandatory = $true)]
		[string]$Path,
		[Parameter(Mandatory = $true)]
		[string]$Key,
		[Parameter(Mandatory = $true)]
		[string]$Value
	)

	$lines = @()
	if (Test-Path $Path) {
		$lines = Get-Content -Path $Path
	}

	$updated = $false
	$pattern = "^\s*" + [Regex]::Escape($Key) + "\s*="

	for ($i = 0; $i -lt $lines.Count; $i++) {
		if ($lines[$i] -match $pattern) {
			$lines[$i] = "$Key=$Value"
			$updated = $true
		}
	}

	if (-not $updated) {
		$lines += "$Key=$Value"
	}

	Set-Content -Path $Path -Value $lines
}

function Show-Help {
	@(
		"dYdX backend PowerShell task runner",
		"",
		"Usage:",
		"  .\make.ps1 <target> [options]",
		"  .\make.ps1 first-run -Mode development",
		"",
		"Targets:",
		"  help            Show this help",
		"  doctor          Check local toolchain and env file health",
		"  first-run       Bootstrap fresh clone (env + dependency fetch + guidance)",
		"  build           go build -v -o bin/dydx-bot ./cmd/server",
		"  run             go run ./cmd/server/main.go",
		"  dev             run with air (hot reload)",
		"  dev-env         create/update .env (use -Mode development|production)",
		"  test            go test -v [-race] -coverprofile=coverage.out ./...  (race enabled when CGO available)",
		"  test-coverage   test + coverage HTML report",
		"  bench           go test -bench=. -benchmem ./...",
		"  lint            golangci-lint run --config .golangci.yml ./...",
		"  lint-fix        golangci-lint run --config .golangci.yml --fix ./...",
		"  fmt             go fmt ./...",
		"  vet             go vet ./...",
		"  tidy            go mod tidy",
		"  clean           remove build/test artifacts",
		"  migrate-up      migrate database up (requires migrate CLI)",
		"  migrate-down    rollback one migration (requires migrate CLI)",
		"  migrate-create  create migration (requires -Name)",
		"  tasks-summary   recompute Completed/Pending status in backend/bot/frontend tasks.md",
		"  tasks-validate  validate cross-service task governance consistency",
		"  tasks-governance update summaries + validate governance checks",
		"",
		"Examples:",
		"  .\make.ps1 doctor",
		"  .\make.ps1 first-run -Mode development",
		"  .\make.ps1 dev-env -Mode development",
		"  .\make.ps1 run",
		"  .\make.ps1 test"
	) | ForEach-Object { Write-Host $_ }
}

function Invoke-DevEnv([string]$SelectedMode, [bool]$OverwriteExisting) {
	$envFile = Join-Path $backendRoot ".env"
	$exampleFile = Join-Path $backendRoot ".env.example"

	if (-not (Test-Path $exampleFile)) {
		throw "Missing .env.example at $exampleFile"
	}

	if ((Test-Path $envFile) -and (-not $OverwriteExisting)) {
		$answer = Read-Host ".env already exists. Overwrite for '$SelectedMode'? [y/N]"
		if ($answer -notin @("y", "Y", "yes", "YES")) {
			Write-WarnMsg "Cancelled"
			return
		}
	}

	Copy-Item -Path $exampleFile -Destination $envFile -Force

	Update-EnvFileValue -Path $envFile -Key "BOT_API_URL" -Value "http://127.0.0.1:8889"

	if ($SelectedMode -eq "development") {
		Update-EnvFileValue -Path $envFile -Key "BOT_API_USE_SERVICE_TOKEN" -Value "true"
		Update-EnvFileValue -Path $envFile -Key "BOT_API_TOKEN" -Value "dev-local-service-token"
		Update-EnvFileValue -Path $envFile -Key "APP_ENV" -Value "development"
		Update-EnvFileValue -Path $envFile -Key "IS_TESTNET" -Value "true"
	}
	else {
		Update-EnvFileValue -Path $envFile -Key "BOT_API_USE_SERVICE_TOKEN" -Value "true"
		Update-EnvFileValue -Path $envFile -Key "BOT_API_TOKEN" -Value "change-me-service-token"
		Update-EnvFileValue -Path $envFile -Key "APP_ENV" -Value "production"
		Update-EnvFileValue -Path $envFile -Key "IS_TESTNET" -Value "false"
	}

	Write-Success ".env generated for $SelectedMode"
}

function Invoke-Doctor {
	Write-Info "Checking backend development prerequisites..."

	$checks = @(
		@{ Name = "go"; Required = $true; Hint = "Install Go 1.23+ and add to PATH." },
		@{ Name = "air"; Required = $false; Hint = "Optional for hot reload: go install github.com/air-verse/air@v1.61.7" },
		@{ Name = "golangci-lint"; Required = $false; Hint = "Optional for lint target." },
		@{ Name = "migrate"; Required = $false; Hint = "Optional for migration CLI commands." }
	)

	$missingRequired = @()

	foreach ($check in $checks) {
		if (Test-CommandAvailable $check.Name) {
			Write-Success ("{0} found" -f $check.Name)
		}
		else {
			if ($check.Required) {
				Write-ErrMsg ("{0} missing. {1}" -f $check.Name, $check.Hint)
				$missingRequired += $check.Name
			}
			else {
				Write-WarnMsg ("{0} missing. {1}" -f $check.Name, $check.Hint)
			}
		}
	}

	$envFile = Join-Path $backendRoot ".env"
	if (Test-Path $envFile) {
		Write-Success ".env file present"
	}
	else {
		Write-WarnMsg ".env file missing (run: .\make.ps1 dev-env -Mode development)"
	}

	if ($missingRequired.Count -gt 0) {
		throw "Missing required tools: $($missingRequired -join ', ')"
	}
}

$backendRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $backendRoot

try {
	switch ($Target.ToLowerInvariant()) {
		"help" {
			Show-Help
		}

		"doctor" {
			Invoke-Doctor
		}

		"first-run" {
			Write-Info "Running first-run bootstrap for backend..."

			$envFile = Join-Path $backendRoot ".env"
			if (-not (Test-Path $envFile)) {
				Invoke-DevEnv -SelectedMode $Mode -OverwriteExisting $true
			}
			else {
				Write-Info ".env already exists; keeping current file"
			}

			try {
				Invoke-Doctor
			}
			catch {
				Write-ErrMsg $_.Exception.Message
				Write-WarnMsg "Bootstrap stopped at prerequisite checks. Install missing required tools and rerun first-run."
				break
			}

			if (Test-CommandAvailable "go") {
				Write-Info "Downloading Go dependencies..."
				& go mod download
				Write-Success "Dependencies downloaded"
			}

			Write-Success "First-run bootstrap complete"
			Write-Host "Next steps:" -ForegroundColor Cyan
			Write-Host "  1) Start bot API on port 8889" -ForegroundColor Cyan
			Write-Host "  2) Run backend: .\make.ps1 run" -ForegroundColor Cyan
		}

		"build" {
			Require-Command "go" "Install Go and ensure it is in PATH."
			Write-Info "Building backend binary..."
			if (-not (Test-Path "bin")) { New-Item -Path "bin" -ItemType Directory | Out-Null }
			& go build -v -o "bin/dydx-bot" "./cmd/server"
			Write-Success "Build complete: bin/dydx-bot"
		}

		"run" {
			Require-Command "go" "Install Go and ensure it is in PATH."
			Write-Info "Running backend..."
			& go run "./cmd/server/main.go"
		}

		"dev" {
			Require-Command "air" "Install air: go install github.com/air-verse/air@v1.61.7"
			Write-Info "Running with hot reload (air)..."
			& air
		}

		"dev-env" {
			Invoke-DevEnv -SelectedMode $Mode -OverwriteExisting $Yes.IsPresent
		}

		"test" {
			Require-Command "go" "Install Go and ensure it is in PATH."
			Write-Info "Running tests..."
			$cgoEnabled = $env:CGO_ENABLED
			$hasCCompiler = Test-CommandAvailable "gcc"
			$useRace = ($cgoEnabled -eq "1") -or ($hasCCompiler -and ($cgoEnabled -ne "0"))
			if ($useRace) {
				& go test -v -race -coverprofile=coverage.out ./...
			} else {
				Write-WarnMsg "CGO not available (no gcc found or CGO_ENABLED=0); running tests without -race. Install GCC/MinGW and set CGO_ENABLED=1 to enable the race detector."
				& go test -v -coverprofile=coverage.out ./...
			}
			Write-Success "Tests complete"
		}

		"test-coverage" {
			Require-Command "go" "Install Go and ensure it is in PATH."
			Write-Info "Running tests with coverage..."
			$cgoEnabled = $env:CGO_ENABLED
			$hasCCompiler = Test-CommandAvailable "gcc"
			$useRace = ($cgoEnabled -eq "1") -or ($hasCCompiler -and ($cgoEnabled -ne "0"))
			if ($useRace) {
				& go test -v -race -coverprofile=coverage.out ./...
			} else {
				Write-WarnMsg "CGO not available (no gcc found or CGO_ENABLED=0); running tests without -race. Install GCC/MinGW and set CGO_ENABLED=1 to enable the race detector."
				& go test -v -coverprofile=coverage.out ./...
			}
			& go tool cover -html=coverage.out -o coverage.html
			Write-Success "Coverage report generated: coverage.html"
		}

		"bench" {
			Require-Command "go" "Install Go and ensure it is in PATH."
			Write-Info "Running benchmarks..."
			& go test -bench=. -benchmem ./...
			Write-Success "Benchmarks complete"
		}

		"lint" {
			Require-Command "golangci-lint" "Install golangci-lint and ensure it is in PATH."
			Write-Info "Running linter..."
			& golangci-lint run --config .golangci.yml ./...
			Write-Success "Linting complete"
		}

		"lint-fix" {
			Require-Command "golangci-lint" "Install golangci-lint and ensure it is in PATH."
			Write-Info "Running linter with fixes..."
			& golangci-lint run --config .golangci.yml --fix ./...
			Write-Success "Lint fix complete"
		}

		"fmt" {
			Require-Command "go" "Install Go and ensure it is in PATH."
			Write-Info "Formatting code..."
			& go fmt ./...
			Write-Success "Formatting complete"
		}

		"vet" {
			Require-Command "go" "Install Go and ensure it is in PATH."
			Write-Info "Running go vet..."
			& go vet ./...
			Write-Success "Vet complete"
		}

		"tidy" {
			Require-Command "go" "Install Go and ensure it is in PATH."
			Write-Info "Tidying modules..."
			& go mod tidy
			Write-Success "Dependencies tidied"
		}

		"clean" {
			Require-Command "go" "Install Go and ensure it is in PATH."
			Write-Info "Cleaning build/test artifacts..."
			if (Test-Path "bin") { Remove-Item -Path "bin" -Recurse -Force }
			if (Test-Path "coverage.out") { Remove-Item -Path "coverage.out" -Force }
			if (Test-Path "coverage.html") { Remove-Item -Path "coverage.html" -Force }
			& go clean -cache -testcache -modcache
			Write-Success "Clean complete"
		}

		"migrate-up" {
			Require-Command "migrate" "Install golang-migrate CLI and ensure it is in PATH."
			$dbType = $env:DB_TYPE
			if ([string]::IsNullOrWhiteSpace($dbType)) { $dbType = "sqlite3" }

			Write-Info "Running migrations up for DB_TYPE=$dbType..."
			if ($dbType -eq "sqlite3") {
				& migrate -path migrations -database "sqlite3://trading_bot.db" up
			}
			else {
				if ([string]::IsNullOrWhiteSpace($env:DATABASE_URL)) {
					throw "DATABASE_URL is required when DB_TYPE is not sqlite3"
				}
				& migrate -path migrations -database "$env:DATABASE_URL" up
			}
			Write-Success "Migrations complete"
		}

		"migrate-down" {
			Require-Command "migrate" "Install golang-migrate CLI and ensure it is in PATH."
			$dbType = $env:DB_TYPE
			if ([string]::IsNullOrWhiteSpace($dbType)) { $dbType = "sqlite3" }

			Write-Info "Rolling back one migration for DB_TYPE=$dbType..."
			if ($dbType -eq "sqlite3") {
				& migrate -path migrations -database "sqlite3://trading_bot.db" down 1
			}
			else {
				if ([string]::IsNullOrWhiteSpace($env:DATABASE_URL)) {
					throw "DATABASE_URL is required when DB_TYPE is not sqlite3"
				}
				& migrate -path migrations -database "$env:DATABASE_URL" down 1
			}
			Write-Success "Rollback complete"
		}

		"migrate-create" {
			Require-Command "migrate" "Install golang-migrate CLI and ensure it is in PATH."
			if ([string]::IsNullOrWhiteSpace($Name)) {
				throw "Please pass migration name with -Name, e.g. .\make.ps1 migrate-create -Name add_index"
			}
			Write-Info "Creating migration: $Name"
			& migrate create -ext sql -dir migrations -seq "$Name"
			Write-Success "Migration files created"
		}

		"tasks-summary" {
			Write-Info "Updating task status summaries..."
			& powershell -ExecutionPolicy Bypass -File (Join-Path $backendRoot "scripts\update_task_summary.ps1")
			Write-Success "Task status summaries updated"
		}

		"tasks-validate" {
			Write-Info "Validating task governance..."
			& powershell -ExecutionPolicy Bypass -File (Join-Path $backendRoot "scripts\validate_task_governance.ps1")
			Write-Success "Task governance validation passed"
		}

		"tasks-governance" {
			Write-Info "Updating and validating task governance..."
			& powershell -ExecutionPolicy Bypass -File (Join-Path $backendRoot "scripts\update_task_summary.ps1")
			& powershell -ExecutionPolicy Bypass -File (Join-Path $backendRoot "scripts\validate_task_governance.ps1")
			Write-Success "Task governance update + validation complete"
		}

		default {
			throw "Unknown target '$Target'. Run '.\make.ps1 help'"
		}
	}
}
finally {
	Pop-Location
}
