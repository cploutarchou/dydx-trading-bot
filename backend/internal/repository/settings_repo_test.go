package repository_test

import (
	"database/sql"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	_ "modernc.org/sqlite"
)

func setupSettingsRepoTestDB(t *testing.T) *sql.DB {
	t.Helper()

	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close sqlite: %v", err)
		}
	})

	if _, err := dbConn.Exec(`
		CREATE TABLE bot_settings (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			section TEXT NOT NULL,
			key TEXT NOT NULL,
			value TEXT DEFAULT NULL,
			value_type TEXT DEFAULT NULL,
			description TEXT DEFAULT NULL,
			default_value TEXT DEFAULT NULL,
			is_active BOOLEAN DEFAULT NULL,
			version INTEGER DEFAULT NULL,
			created_at DATETIME DEFAULT NULL,
			updated_at DATETIME DEFAULT NULL,
			UNIQUE(section, key)
		);
	`); err != nil {
		t.Fatalf("create bot_settings: %v", err)
	}

	return dbConn
}

func TestSettingsRepositoryScansNullableBotSettingRows(t *testing.T) {
	dbConn := setupSettingsRepoTestDB(t)
	repo := repository.NewSettingsRepository(dbConn)

	if _, err := dbConn.Exec(
		`INSERT INTO bot_settings (section, key, value, value_type, description, default_value, is_active, version, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"platform",
		"coming_soon_enabled",
		"false",
		"boolean",
		nil,
		nil,
		nil,
		nil,
		nil,
		nil,
	); err != nil {
		t.Fatalf("insert nullable setting: %v", err)
	}

	settings, err := repo.GetAllBotSettings()
	if err != nil {
		t.Fatalf("GetAllBotSettings returned error for nullable row: %v", err)
	}
	if len(settings) != 1 {
		t.Fatalf("expected 1 setting, got %d", len(settings))
	}
	if settings[0].Description != "" || settings[0].DefaultValue != "" {
		t.Fatalf("expected nullable text fields to normalize empty, got %+v", settings[0])
	}
	if !settings[0].IsActive {
		t.Fatalf("expected NULL is_active to default active for legacy rows")
	}
	if settings[0].Version != 1 {
		t.Fatalf("expected NULL version to normalize to 1, got %d", settings[0].Version)
	}
	if settings[0].CreatedAt.IsZero() || settings[0].UpdatedAt.IsZero() {
		t.Fatalf("expected NULL timestamps to normalize to non-zero values")
	}

	setting, err := repo.GetBotSettingBySectionAndKey("platform", "coming_soon_enabled")
	if err != nil {
		t.Fatalf("GetBotSettingBySectionAndKey returned error for nullable row: %v", err)
	}
	if setting == nil || setting.Value != "false" {
		t.Fatalf("expected coming soon setting false, got %+v", setting)
	}
}

func TestSettingsServiceCreateBotSettingIsIdempotentOnDuplicateKey(t *testing.T) {
	dbConn := setupSettingsRepoTestDB(t)
	service := services.NewSettingsService(repository.NewSettingsRepository(dbConn))

	first, err := service.CreateBotSetting("platform", "coming_soon_enabled", "true", "boolean", "Existing value", "false", true)
	if err != nil {
		t.Fatalf("create first setting: %v", err)
	}
	second, err := service.CreateBotSetting("platform", "coming_soon_enabled", "false", "boolean", "Default value", "false", true)
	if err != nil {
		t.Fatalf("duplicate create should return existing setting, got error: %v", err)
	}
	if second.ID != first.ID || second.Value != "true" {
		t.Fatalf("expected duplicate create to preserve existing setting, first=%+v second=%+v", first, second)
	}

	var count int
	if err := dbConn.QueryRow(`SELECT COUNT(*) FROM bot_settings WHERE section = ? AND key = ?`, "platform", "coming_soon_enabled").Scan(&count); err != nil {
		t.Fatalf("count settings: %v", err)
	}
	if count != 1 {
		t.Fatalf("expected exactly one setting row, got %d", count)
	}
}

func TestSettingsRepositoryReturnsDatabaseErrors(t *testing.T) {
	dbConn := setupSettingsRepoTestDB(t)
	repo := repository.NewSettingsRepository(dbConn)
	if _, err := dbConn.Exec(`DROP TABLE bot_settings`); err != nil {
		t.Fatalf("drop bot_settings: %v", err)
	}

	if _, err := repo.GetAllBotSettings(); err == nil {
		t.Fatal("expected GetAllBotSettings to return database error")
	}
}

func TestBotSettingToDictSerializesNormalizedValues(t *testing.T) {
	now := time.Now().UTC()
	setting := models.BotSetting{
		ID:           1,
		Section:      "platform",
		Key:          "coming_soon_enabled",
		Value:        "false",
		ValueType:    "boolean",
		Description:  "",
		DefaultValue: "false",
		IsActive:     true,
		Version:      1,
		CreatedAt:    now,
		UpdatedAt:    now,
	}

	dto := setting.ToDict()
	if dto["value"] != "false" || dto["value_type"] != "boolean" || dto["is_active"] != true {
		t.Fatalf("unexpected DTO payload: %+v", dto)
	}
}
