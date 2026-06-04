package routes

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	backenddb "github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/gin-gonic/gin"
	_ "modernc.org/sqlite"
)

func setupPublicAppConfigRouter(t *testing.T) (*gin.Engine, *sql.DB) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
	}

	if _, err := dbConn.Exec(`
	CREATE TABLE bot_settings (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		section TEXT NOT NULL,
		key TEXT NOT NULL,
		value TEXT NOT NULL,
		value_type TEXT NOT NULL,
		description TEXT NOT NULL DEFAULT '',
		default_value TEXT NOT NULL DEFAULT '',
		is_active BOOLEAN NOT NULL DEFAULT 1,
		version INTEGER NOT NULL DEFAULT 1,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL,
		UNIQUE(section, key)
	);`); err != nil {
		t.Fatalf("create bot_settings table: %v", err)
	}

	router := gin.New()
	RegisterSettingsRoutes(router, &backenddb.Database{DB: dbConn})
	return router, dbConn
}

func TestPublicAppConfigDefaultsComingSoonDisabled(t *testing.T) {
	router, dbConn := setupPublicAppConfigRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	req := httptest.NewRequest(http.MethodGet, "/api/v1/public/app-config", nil)
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", res.Code, res.Body.String())
	}

	var body struct {
		Data struct {
			AppName           string `json:"app_name"`
			ComingSoonEnabled bool   `json:"coming_soon_enabled"`
		} `json:"data"`
	}
	if err := json.Unmarshal(res.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response: %v", err)
	}

	if body.Data.AppName != "ExecutionLab" {
		t.Fatalf("expected app_name ExecutionLab, got %q", body.Data.AppName)
	}
	if body.Data.ComingSoonEnabled {
		t.Fatalf("expected coming_soon_enabled false by default")
	}
}

func TestPublicAppConfigReadsComingSoonSetting(t *testing.T) {
	router, dbConn := setupPublicAppConfigRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	_, err := dbConn.Exec(
		`INSERT INTO bot_settings (section, key, value, value_type, description, default_value, is_active, version, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"platform",
		"coming_soon_enabled",
		"true",
		"boolean",
		"Coming soon",
		"false",
		true,
		1,
		time.Now().UTC(),
		time.Now().UTC(),
	)
	if err != nil {
		t.Fatalf("insert coming soon setting: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/api/v1/public/app-config", nil)
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", res.Code, res.Body.String())
	}

	var body struct {
		Data struct {
			ComingSoonEnabled bool `json:"coming_soon_enabled"`
		} `json:"data"`
	}
	if err := json.Unmarshal(res.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if !body.Data.ComingSoonEnabled {
		t.Fatalf("expected coming_soon_enabled true")
	}
}
