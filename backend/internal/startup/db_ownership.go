package startup

import (
	"fmt"
	"net/url"
	"os"
	"strings"

	"github.com/dydx-trading-bot/backend-go/config"
)

const (
	_dedicated                  = "dedicated"
	dedicatedwithsharedfallback = "dedicated_with_shared_fallback"
)

type DatabaseTarget struct {
	Host   string `json:"host"`
	Port   string `json:"port"`
	Name   string `json:"name"`
	Source string `json:"source"`
}

type DatabaseOwnershipDiagnostics struct {
	Mode              string          `json:"mode"`
	BackendTarget     DatabaseTarget  `json:"backend_target"`
	BotTarget         *DatabaseTarget `json:"bot_target,omitempty"`
	Separated         bool            `json:"separated"`
	BlockingViolation bool            `json:"blocking_violation"`
	Notes             []string        `json:"notes"`
}

func normalizeCutoverMode(raw string) string {
	normalized := strings.ToLower(strings.TrimSpace(raw))
	normalized = strings.ReplaceAll(normalized, "-", "_")
	switch normalized {
	case _dedicated, dedicatedwithsharedfallback, "shared":
		return normalized
	default:
		return "shared"
	}
}

func normalizeDBTarget(target DatabaseTarget) DatabaseTarget {
	target.Host = strings.ToLower(strings.TrimSpace(target.Host))
	target.Port = strings.TrimSpace(target.Port)
	target.Name = strings.ToLower(strings.TrimSpace(target.Name))
	target.Source = strings.TrimSpace(target.Source)
	return target
}

func parseDatabaseTarget(rawURL string, source string) (*DatabaseTarget, bool) {
	candidate := strings.TrimSpace(rawURL)
	if candidate == "" {
		return nil, false
	}

	parsed, err := url.Parse(candidate)
	if err != nil {
		return nil, false
	}

	scheme := strings.ToLower(parsed.Scheme)
	if scheme != "postgres" && scheme != "postgresql" {
		return nil, false
	}

	target := normalizeDBTarget(DatabaseTarget{
		Host:   parsed.Hostname(),
		Port:   parsed.Port(),
		Name:   strings.TrimPrefix(parsed.Path, "/"),
		Source: source,
	})
	if target.Port == "" {
		target.Port = "5432"
	}
	return &target, true
}

func parseAnyDatabaseTarget(rawURL string, source string) (*DatabaseTarget, bool) {
	if target, ok := parseDatabaseTarget(rawURL, source); ok {
		return target, true
	}
	return nil, false
}

func resolveSharedDBTargetFromEnv() (*DatabaseTarget, bool) {
	if target, ok := parseAnyDatabaseTarget(os.Getenv("DATABASE_URL"), "shared_database_url"); ok {
		return target, true
	}

	host := strings.TrimSpace(firstNonEmpty(os.Getenv("DB_HOST"), os.Getenv("POSTGRES_HOST"), "localhost"))
	port := strings.TrimSpace(firstNonEmpty(os.Getenv("DB_PORT"), os.Getenv("POSTGRES_PORT"), "5432"))
	name := strings.TrimSpace(firstNonEmpty(os.Getenv("DB_NAME"), os.Getenv("POSTGRES_DB"), "dydx_bot"))

	target := normalizeDBTarget(DatabaseTarget{
		Host:   host,
		Port:   port,
		Name:   name,
		Source: "shared_db_fields",
	})
	if target.Host == "" || target.Port == "" || target.Name == "" {
		return nil, false
	}
	return &target, true
}

func hasBotDBFieldTarget() bool {
	required := []string{
		strings.TrimSpace(os.Getenv("BOT_DB_HOST")),
		strings.TrimSpace(os.Getenv("BOT_DB_PORT")),
		strings.TrimSpace(os.Getenv("BOT_DB_NAME")),
	}
	for _, value := range required {
		if value == "" {
			return false
		}
	}
	return true
}

func resolveBotDBTargetFromEnv(mode string) (*DatabaseTarget, bool) {
	if target, ok := parseAnyDatabaseTarget(os.Getenv("BOT_DATABASE_URL"), "bot_database_url"); ok {
		return target, true
	}

	if hasBotDBFieldTarget() {
		target := normalizeDBTarget(DatabaseTarget{
			Host:   os.Getenv("BOT_DB_HOST"),
			Port:   os.Getenv("BOT_DB_PORT"),
			Name:   os.Getenv("BOT_DB_NAME"),
			Source: "bot_db_fields",
		})
		return &target, true
	}

	if mode == "shared" || mode == dedicatedwithsharedfallback {
		if sharedTarget, ok := resolveSharedDBTargetFromEnv(); ok {
			return sharedTarget, true
		}
	}

	return nil, false
}

func targetsEqual(left DatabaseTarget, right DatabaseTarget) bool {
	nLeft := normalizeDBTarget(left)
	nRight := normalizeDBTarget(right)
	return nLeft.Host == nRight.Host && nLeft.Port == nRight.Port && nLeft.Name == nRight.Name
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}

func BuildDatabaseOwnershipDiagnostics(cfg *config.Config) DatabaseOwnershipDiagnostics {
	mode := normalizeCutoverMode(os.Getenv("BOT_DB_CUTOVER_MODE"))
	backendTarget := normalizeDBTarget(DatabaseTarget{
		Host:   cfg.Database.Host,
		Port:   fmt.Sprintf("%d", cfg.Database.Port),
		Name:   cfg.Database.Dbname,
		Source: "backend_database_config",
	})

	diagnostics := DatabaseOwnershipDiagnostics{
		Mode:          mode,
		BackendTarget: backendTarget,
		Separated:     true,
		Notes:         []string{},
	}

	botTarget, hasBotTarget := resolveBotDBTargetFromEnv(mode)
	if !hasBotTarget || botTarget == nil {
		diagnostics.Notes = append(diagnostics.Notes, "bot runtime DB target unavailable from env")
		if mode == _dedicated {
			diagnostics.Notes = append(diagnostics.Notes, "dedicated mode requires BOT_DATABASE_URL or BOT_DB_* in bot runtime")
		}
		return diagnostics
	}
	diagnostics.BotTarget = botTarget

	sharedDetected := targetsEqual(backendTarget, *botTarget)
	diagnostics.Separated = !sharedDetected
	if sharedDetected {
		diagnostics.Notes = append(diagnostics.Notes, "backend and bot DB targets resolve to the same host/port/name")
		if mode == _dedicated {
			diagnostics.BlockingViolation = true
		}
	} else {
		diagnostics.Notes = append(diagnostics.Notes, "backend and bot DB targets are separated")
	}

	if mode == "shared" {
		diagnostics.Notes = append(diagnostics.Notes, "cutover mode shared allows shared DB targets")
	}
	if mode == dedicatedwithsharedfallback {
		diagnostics.Notes = append(diagnostics.Notes, "cutover mode dedicated_with_shared_fallback may use shared target if bot overrides are absent")
	}

	return diagnostics
}

func ValidateDatabaseOwnership(cfg *config.Config) error {
	diagnostics := BuildDatabaseOwnershipDiagnostics(cfg)
	if diagnostics.BlockingViolation {
		return fmt.Errorf(
			"database ownership validation failed: dedicated mode points bot and backend to the same target (%s:%s/%s)",
			diagnostics.BackendTarget.Host,
			diagnostics.BackendTarget.Port,
			diagnostics.BackendTarget.Name,
		)
	}
	return nil
}
