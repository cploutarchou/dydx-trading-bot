package routes

import (
	"database/sql"
	"testing"

	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	_ "modernc.org/sqlite"
)

func newArbitrageSettingsTestService(t *testing.T) *services.SettingsService {
	t.Helper()
	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	t.Cleanup(func() { _ = dbConn.Close() })
	if _, err := dbConn.Exec(`
		CREATE TABLE bot_settings (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			section TEXT NOT NULL,
			key TEXT NOT NULL,
			value TEXT NOT NULL,
			value_type TEXT NOT NULL,
			description TEXT DEFAULT NULL,
			default_value TEXT DEFAULT NULL,
			is_active BOOLEAN DEFAULT 1,
			version INTEGER DEFAULT 1,
			created_at TIMESTAMP DEFAULT NULL,
			updated_at TIMESTAMP DEFAULT NULL,
			UNIQUE(section, key)
		);
	`); err != nil {
		t.Fatalf("create bot_settings: %v", err)
	}
	return services.NewSettingsService(repository.NewSettingsRepository(dbConn))
}

func TestArbitrageRuntimeSettingsPersistAndMapToBotPayload(t *testing.T) {
	service := newArbitrageSettingsTestService(t)

	defaults, err := loadArbitrageRuntimeSettings(service)
	if err != nil {
		t.Fatalf("load defaults: %v", err)
	}
	if defaults["arbitrage_improvements_enabled"] != false {
		t.Fatalf("expected improvements disabled by default, got %v", defaults["arbitrage_improvements_enabled"])
	}

	err = saveArbitrageRuntimeSettings(service, map[string]interface{}{
		"arbitrage_improvements_enabled": true,
		"pair_priority_engine_enabled":   true,
		"pair_priority_max_pairs":        12,
		"pair_priority_stale_seconds":    60,
	})
	if err != nil {
		t.Fatalf("save settings: %v", err)
	}

	loaded, err := loadArbitrageRuntimeSettings(service)
	if err != nil {
		t.Fatalf("reload settings: %v", err)
	}
	if loaded["pair_priority_engine_enabled"] != true {
		t.Fatalf("expected pair priority enabled, got %v", loaded["pair_priority_engine_enabled"])
	}
	if loaded["pair_priority_max_pairs"] != 12 {
		t.Fatalf("expected pair cap 12, got %v", loaded["pair_priority_max_pairs"])
	}

	botPayload := arbitrageSettingsForBot(loaded)
	if botPayload["PAIR_PRIORITY_ENGINE_ENABLED"] != true {
		t.Fatalf("expected uppercase bot payload flag, got %v", botPayload["PAIR_PRIORITY_ENGINE_ENABLED"])
	}
	if botPayload["PAIR_PRIORITY_MAX_PAIRS"] != 12 {
		t.Fatalf("expected uppercase bot payload cap, got %v", botPayload["PAIR_PRIORITY_MAX_PAIRS"])
	}
}

func TestArbitrageRuntimeSettingsRejectUnsupportedKeys(t *testing.T) {
	service := newArbitrageSettingsTestService(t)

	err := saveArbitrageRuntimeSettings(service, map[string]interface{}{
		"unknown_setting": true,
	})
	if err == nil {
		t.Fatal("expected unsupported setting error")
	}
}
