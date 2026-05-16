package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/gin-gonic/gin"
	_ "modernc.org/sqlite"
)

func setupBotInstanceHandlerTestDB(t *testing.T) *sql.DB {
	t.Helper()
	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
	}

	stmts := []string{
		`CREATE TABLE bot_instances (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			instance_id TEXT NOT NULL UNIQUE,
			instance_name TEXT,
			user_id INTEGER NOT NULL,
			status TEXT,
			network TEXT,
			strategy TEXT,
			config TEXT,
			trading_params TEXT,
			total_trades INTEGER,
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
			created_at DATETIME,
			updated_at DATETIME
		);`,
		`CREATE TABLE bot_positions (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			bot_instance_id INTEGER NOT NULL,
			position_id TEXT NOT NULL,
			market_1 TEXT,
			market_2 TEXT,
			status TEXT,
			is_active BOOLEAN,
			entry_timestamp DATETIME,
			entry_price_1 REAL,
			entry_price_2 REAL,
			entry_zscore REAL,
			side_1 TEXT,
			side_2 TEXT,
			size_1 REAL,
			size_2 REAL,
			hedge_ratio REAL,
			current_price_1 REAL,
			current_price_2 REAL,
			current_zscore REAL,
			unrealized_pnl REAL,
			unrealized_pnl_pct REAL,
			exit_timestamp DATETIME,
			exit_price_1 REAL,
			exit_price_2 REAL,
			exit_zscore REAL,
			realized_pnl REAL,
			realized_pnl_pct REAL,
			duration_hours REAL,
			created_at DATETIME,
			updated_at DATETIME
		);`,
		`CREATE TABLE bot_trades (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			bot_instance_id INTEGER NOT NULL,
			trade_id TEXT NOT NULL UNIQUE,
			market_1 TEXT,
			market_2 TEXT,
			entry_timestamp DATETIME,
			entry_price_1 REAL,
			entry_price_2 REAL,
			entry_zscore REAL,
			side_1 TEXT,
			side_2 TEXT,
			size_1 REAL,
			size_2 REAL,
			hedge_ratio REAL,
			exit_timestamp DATETIME,
			exit_price_1 REAL,
			exit_price_2 REAL,
			exit_zscore REAL,
			pnl REAL,
			pnl_pct REAL,
			duration_hours REAL,
			strategy_zscore_threshold REAL,
			created_at DATETIME,
			updated_at DATETIME
		);`,
	}

	for _, stmt := range stmts {
		if _, err := dbConn.Exec(stmt); err != nil {
			t.Fatalf("schema setup failed: %v", err)
		}
	}

	return dbConn
}

func TestGetBotPositions_HandlerReturnsScopedPositions(t *testing.T) {
	gin.SetMode(gin.TestMode)
	dbConn := setupBotInstanceHandlerTestDB(t)
	t.Cleanup(func() { _ = dbConn.Close() })

	now := time.Now().UTC()
	_, _ = dbConn.Exec(`INSERT INTO bot_instances (instance_id, instance_name, user_id, status, network, strategy, config, trading_params, total_trades, total_pnl, current_balance, starting_balance, process_id, pid, host, port, error_message, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"bot-1", "Bot One", 1, "running", "testnet", "pairs", "{}", "{}", 0, 0.0, 0.0, 0.0, 0, "", "", 0, "", now, now)

	_, _ = dbConn.Exec(`INSERT INTO bot_positions (bot_instance_id, position_id, market_1, market_2, status, is_active, entry_timestamp, entry_price_1, entry_price_2, entry_zscore, side_1, side_2, size_1, size_2, hedge_ratio, current_price_1, current_price_2, current_zscore, unrealized_pnl, unrealized_pnl_pct, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		1, "pos-1", "BTC-USD", "ETH-USD", "open", true, now, 100.0, 200.0, 1.1, "LONG", "SHORT", 1.0, 2.0, 0.5, 101.0, 199.0, 0.9, 1.2, 0.5, now, now)

	h := &BotInstanceHandler{
		repo:         repository.NewBotInstanceRepository(dbConn),
		positionRepo: repository.NewBotPositionRepository(dbConn),
		botTradeRepo: repository.NewBotTradeRepository(dbConn),
	}

	router := gin.New()
	router.GET("/api/v1/bots/:instance_id/positions", func(c *gin.Context) {
		c.Set("user_id", 1)
		c.Set("is_admin", false)
		h.GetBotPositions(c)
	})

	req := httptest.NewRequest(http.MethodGet, "/api/v1/bots/bot-1/positions?status=open&page=1&page_size=20", nil)
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", res.Code, res.Body.String())
	}

	var body struct {
		Success bool                     `json:"success"`
		Data    []map[string]interface{} `json:"data"`
	}
	if err := json.Unmarshal(res.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if !body.Success {
		t.Fatalf("expected success=true")
	}
	if len(body.Data) != 1 {
		t.Fatalf("expected exactly one position, got %d", len(body.Data))
	}
}

func TestGetBotTrade_HandlerReturnsSingleTrade(t *testing.T) {
	gin.SetMode(gin.TestMode)
	dbConn := setupBotInstanceHandlerTestDB(t)
	t.Cleanup(func() { _ = dbConn.Close() })

	now := time.Now().UTC()
	_, _ = dbConn.Exec(`INSERT INTO bot_instances (instance_id, instance_name, user_id, status, network, strategy, config, trading_params, total_trades, total_pnl, current_balance, starting_balance, process_id, pid, host, port, error_message, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"bot-2", "Bot Two", 2, "running", "testnet", "pairs", "{}", "{}", 0, 0.0, 0.0, 0.0, 0, "", "", 0, "", now, now)

	_, _ = dbConn.Exec(`INSERT INTO bot_trades (bot_instance_id, trade_id, market_1, market_2, entry_timestamp, entry_price_1, entry_price_2, entry_zscore, side_1, side_2, size_1, size_2, hedge_ratio, pnl, pnl_pct, duration_hours, strategy_zscore_threshold, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		1, "trade-1", "BTC-USD", "ETH-USD", now, 100.0, 200.0, 1.2, "LONG", "SHORT", 1.0, 2.0, 0.5, 3.2, 0.8, 4.0, 1.5, now, now)

	h := &BotInstanceHandler{
		repo:         repository.NewBotInstanceRepository(dbConn),
		positionRepo: repository.NewBotPositionRepository(dbConn),
		botTradeRepo: repository.NewBotTradeRepository(dbConn),
	}

	router := gin.New()
	router.GET("/api/v1/bots/:instance_id/trades/:trade_id", func(c *gin.Context) {
		c.Set("user_id", 2)
		c.Set("is_admin", false)
		h.GetBotTrade(c)
	})

	req := httptest.NewRequest(http.MethodGet, "/api/v1/bots/bot-2/trades/trade-1", nil)
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", res.Code, res.Body.String())
	}

	var body struct {
		Success bool                   `json:"success"`
		Data    map[string]interface{} `json:"data"`
	}
	if err := json.Unmarshal(res.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if !body.Success {
		t.Fatalf("expected success=true")
	}
	if body.Data["trade_id"] != "trade-1" {
		t.Fatalf("expected trade_id trade-1, got %v", body.Data["trade_id"])
	}
}
