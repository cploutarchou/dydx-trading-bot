package services

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	_ "modernc.org/sqlite"
)

// sharedBotInstancesTable is bot_instances as the backend's migrations create it:
// user_id is NOT NULL and instance_id is UNIQUE. With BOT_DB_CUTOVER_MODE=shared
// the bot API reads and writes this very table.
func sharedBotInstancesTable(t *testing.T) *sql.DB {
	t.Helper()
	conn, err := sql.Open("sqlite", "file:"+strings.ReplaceAll(t.Name(), "/", "_")+"?mode=memory&cache=shared")
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	conn.SetMaxOpenConns(1)
	if _, err := conn.Exec(`CREATE TABLE bot_instances (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		instance_id TEXT NOT NULL UNIQUE,
		instance_name TEXT,
		user_id INTEGER NOT NULL,
		status TEXT NOT NULL DEFAULT 'STOPPED',
		network TEXT,
		strategy TEXT,
		config TEXT,
		trading_params TEXT,
		total_trades INTEGER NOT NULL DEFAULT 0,
		total_pnl REAL,
		current_balance REAL,
		starting_balance REAL,
		process_id INTEGER,
		pid TEXT,
		host TEXT,
		port INTEGER,
		error_message TEXT,
		last_error_at DATETIME,
		started_at DATETIME,
		stopped_at DATETIME,
		created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
		updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
	)`); err != nil {
		t.Fatalf("create bot_instances: %v", err)
	}
	return conn
}

// botAPISharingTheTable behaves like the bot API on a shared database
// (bot/src/api/v1/bot_lifecycle.py): create updates the row when it exists and
// otherwise inserts one without user_id; delete removes the row.
func botAPISharingTheTable(t *testing.T, conn *sql.DB, failCreate bool) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	mux.HandleFunc("/api/v1/bots", func(w http.ResponseWriter, r *http.Request) {
		defer func() { _ = r.Body.Close() }()
		var payload map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode create payload: %v", err)
		}
		instanceID, _ := payload["instance_id"].(string)
		w.Header().Set("Content-Type", "application/json")
		if failCreate {
			w.WriteHeader(http.StatusInternalServerError)
			_, _ = w.Write([]byte(`{"success":false,"message":"Internal server error"}`))
			return
		}

		var existing int
		_ = conn.QueryRow(`SELECT COUNT(*) FROM bot_instances WHERE instance_id = ?`, instanceID).Scan(&existing)
		var err error
		if existing > 0 {
			_, err = conn.Exec(`UPDATE bot_instances SET config = ? WHERE instance_id = ?`, `{"sealed":true}`, instanceID)
		} else {
			_, err = conn.Exec(
				`INSERT INTO bot_instances (instance_id, network, strategy, config, status) VALUES (?, 'testnet', 'cointegration', '{"sealed":true}', 'CREATED')`,
				instanceID,
			)
		}
		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			_, _ = w.Write([]byte(`{"success":false,"message":"Internal server error"}`))
			return
		}
		_, _ = w.Write([]byte(`{"success":true,"data":{"instance_id":"` + instanceID + `"}}`))
	})
	mux.HandleFunc("/api/v1/bots/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if r.Method == http.MethodDelete {
			instanceID := strings.TrimPrefix(r.URL.Path, "/api/v1/bots/")
			_, _ = conn.Exec(`DELETE FROM bot_instances WHERE instance_id = ?`, instanceID)
		}
		_, _ = w.Write([]byte(`{"success":true,"data":{}}`))
	})
	server := httptest.NewServer(mux)
	t.Cleanup(server.Close)
	return server
}

func sharedTableInstance() (*models.BotInstance, map[string]interface{}) {
	instance := &models.BotInstance{
		InstanceID:   "strategy-85-1",
		InstanceName: "test current market",
		UserID:       85,
		Status:       "stopped",
		Network:      "testnet",
		Strategy:     "cointegration",
		Config:       sql.NullString{String: `{"instance_name":"test current market"}`, Valid: true},
	}
	return instance, map[string]interface{}{"instance_id": instance.InstanceID, "instance_name": instance.InstanceName}
}

func TestCreateBotInstanceWithConfigOnASharedTable(t *testing.T) {
	conn := sharedBotInstancesTable(t)
	defer func() { _ = conn.Close() }()
	server := botAPISharingTheTable(t, conn, false)
	service := NewBotInstanceService(repository.NewBotInstanceRepository(conn), NewBotAPIClient(server.URL, "test-token"))

	instance, payload := sharedTableInstance()
	if err := service.CreateBotInstanceWithConfig(instance, payload); err != nil {
		t.Fatalf("creating a runtime instance on a shared bot_instances table failed: %v", err)
	}

	var rows, userID int
	var config string
	if err := conn.QueryRow(`SELECT COUNT(*), MAX(user_id), MAX(config) FROM bot_instances WHERE instance_id = ?`, instance.InstanceID).Scan(&rows, &userID, &config); err != nil {
		t.Fatalf("read bot_instances: %v", err)
	}
	if rows != 1 {
		t.Fatalf("expected exactly one row for the instance, got %d", rows)
	}
	if userID != 85 {
		t.Fatalf("the row must belong to the strategy's user, got user_id=%d", userID)
	}
	if config != `{"sealed":true}` {
		t.Fatalf("the bot's sealed config must be the one that is stored, got %s", config)
	}
}

func TestCreateBotInstanceWithConfigRemovesItsRowWhenTheBotAPIFails(t *testing.T) {
	conn := sharedBotInstancesTable(t)
	defer func() { _ = conn.Close() }()
	server := botAPISharingTheTable(t, conn, true)
	service := NewBotInstanceService(repository.NewBotInstanceRepository(conn), NewBotAPIClient(server.URL, "test-token"))

	instance, payload := sharedTableInstance()
	err := service.CreateBotInstanceWithConfig(instance, payload)
	if err == nil || !strings.Contains(err.Error(), "failed to create bot instance in bot API") {
		t.Fatalf("expected the bot API failure to be reported, got %v", err)
	}

	var rows int
	if err := conn.QueryRow(`SELECT COUNT(*) FROM bot_instances`).Scan(&rows); err != nil {
		t.Fatalf("count rows: %v", err)
	}
	if rows != 0 {
		t.Fatalf("a failed create must not leave a row behind, found %d", rows)
	}
}

func TestRecreateAndDeleteTolerateTheBotHavingRemovedTheSharedRow(t *testing.T) {
	conn := sharedBotInstancesTable(t)
	defer func() { _ = conn.Close() }()
	server := botAPISharingTheTable(t, conn, false)
	service := NewBotInstanceService(repository.NewBotInstanceRepository(conn), NewBotAPIClient(server.URL, "test-token"))

	instance, payload := sharedTableInstance()
	if err := service.CreateBotInstanceWithConfig(instance, payload); err != nil {
		t.Fatalf("create: %v", err)
	}

	// The bot API's delete removes the shared row before the backend gets to it.
	if err := service.RecreateBotInstanceWithConfig(instance, payload); err != nil {
		t.Fatalf("recreate on a shared table failed: %v", err)
	}
	var rows int
	if err := conn.QueryRow(`SELECT COUNT(*) FROM bot_instances WHERE user_id = 85`).Scan(&rows); err != nil || rows != 1 {
		t.Fatalf("expected one owned row after recreate, got rows=%d err=%v", rows, err)
	}

	if err := service.DeleteBotInstance(instance.InstanceID); err != nil {
		t.Fatalf("delete on a shared table failed: %v", err)
	}
	if err := conn.QueryRow(`SELECT COUNT(*) FROM bot_instances`).Scan(&rows); err != nil || rows != 0 {
		t.Fatalf("expected no rows after delete, got rows=%d err=%v", rows, err)
	}
}
