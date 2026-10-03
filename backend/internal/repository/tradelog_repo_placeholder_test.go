package repository

import (
	"database/sql"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	_ "modernc.org/sqlite"
)

func setupTradeLogTestDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
	}
	t.Cleanup(func() { _ = db.Close() })

	schema := `
		CREATE TABLE trade_logs (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			result_id_fk INTEGER NOT NULL,
			trade_number INTEGER NOT NULL,
			entry_timestamp TIMESTAMP NOT NULL,
			exit_timestamp TIMESTAMP DEFAULT NULL,
			entry_price_1 REAL NOT NULL,
			entry_price_2 REAL NOT NULL,
			exit_price_1 REAL DEFAULT NULL,
			exit_price_2 REAL DEFAULT NULL,
			quantity_1 REAL NOT NULL,
			quantity_2 REAL NOT NULL,
			side_1 TEXT NOT NULL,
			side_2 TEXT NOT NULL,
			pnl REAL DEFAULT NULL,
			pnl_usd REAL DEFAULT NULL,
			entry_zscore REAL DEFAULT NULL,
			exit_zscore REAL DEFAULT NULL,
			created_at TIMESTAMP DEFAULT NULL
		);
		CREATE TABLE backtest_runs (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id INTEGER NOT NULL,
			run_id TEXT,
			status TEXT,
			created_at TIMESTAMP NOT NULL
		);
		CREATE TABLE backtest_results (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			run_id_fk INTEGER NOT NULL,
			market_1 TEXT NOT NULL,
			market_2 TEXT NOT NULL,
			created_at TIMESTAMP
		);
	`
	if _, err := db.Exec(schema); err != nil {
		t.Fatalf("create trade_logs schema: %v", err)
	}

	// Seed the ownership chain: run (owner 7) -> result (id 101).
	now := time.Now().UTC()
	if _, err := db.Exec(`INSERT INTO backtest_runs (id, user_id, created_at) VALUES (11, 7, ?)`, now); err != nil {
		t.Fatalf("seed backtest run: %v", err)
	}
	if _, err := db.Exec(`INSERT INTO backtest_results (id, run_id_fk, market_1, market_2) VALUES (101, 11, 'BTC-USD', 'ETH-USD')`); err != nil {
		t.Fatalf("seed backtest result: %v", err)
	}
	return db
}

// TestTradeLogOwnershipScoping verifies the tenant-isolation joins: a trade
// log is only visible to the run's owner (or unscoped admin access).
func TestTradeLogOwnershipScoping(t *testing.T) {
	db := setupTradeLogTestDB(t)
	t.Setenv("DB_TYPE", "sqlite")
	repo := NewTradeLogRepository(db)

	now := time.Now().UTC()
	tradeNumber := 1
	entryPrice := 100.5
	side1 := "long"
	created := &models.TradeLog{
		ResultIDFK:     101,
		TradeNumber:    &tradeNumber,
		EntryPrice1:    &entryPrice,
		EntryPrice2:    &entryPrice,
		Quantity1:      &entryPrice,
		Quantity2:      &entryPrice,
		Side1:          &side1,
		Side2:          &side1,
		EntryTimestamp: &now,
	}
	if err := repo.CreateTradeLog(created); err != nil {
		t.Fatalf("CreateTradeLog: %v", err)
	}

	if got, err := repo.GetTradeLogByID(created.ID, 7); err != nil || got == nil {
		t.Fatalf("owner scope expected the log, got %v err %v", got, err)
	}
	if got, err := repo.GetTradeLogByID(created.ID, 8); err != nil || got != nil {
		t.Fatalf("foreign user must not see the log, got %v err %v", got, err)
	}
	if got, err := repo.GetTradeLogByID(created.ID, 0); err != nil || got == nil {
		t.Fatalf("admin scope (0) expected the log, got %v err %v", got, err)
	}

	logs, err := repo.GetTradeLogsByResult(101, 7)
	if err != nil || len(logs) != 1 {
		t.Fatalf("owner result listing expected 1 log, got %d err %v", len(logs), err)
	}
	logs, err = repo.GetTradeLogsByResult(101, 8)
	if err != nil || len(logs) != 0 {
		t.Fatalf("foreign result listing expected 0 logs, got %d err %v", len(logs), err)
	}

	owner, err := repo.GetResultOwnerID(101)
	if err != nil || owner == nil || *owner != 7 {
		t.Fatalf("GetResultOwnerID expected 7, got %v err %v", owner, err)
	}
	if owner, err = repo.GetResultOwnerID(999); err != nil || owner != nil {
		t.Fatalf("missing result should return nil owner, got %v err %v", owner, err)
	}
}

// Regression test: UpdateTradeLog previously used `?0..?5` placeholder
// suffixes that bindQuery rewrote into non-existent `$100/$111/...`
// parameters, so PUT /api/v1/trade-logs/:id failed on every call.
func TestUpdateTradeLog_PersistsAllFields(t *testing.T) {
	db := setupTradeLogTestDB(t)
	t.Setenv("DB_TYPE", "sqlite")
	repo := NewTradeLogRepository(db)

	now := time.Now().UTC().Truncate(time.Second)
	tradeNumber := 1
	entryPrice := 100.5
	side1 := "long"
	side2 := "short"
	created := &models.TradeLog{
		ResultIDFK:     101,
		TradeNumber:    &tradeNumber,
		EntryPrice1:    &entryPrice,
		EntryPrice2:    &entryPrice,
		Quantity1:      &entryPrice,
		Quantity2:      &entryPrice,
		Side1:          &side1,
		Side2:          &side2,
		EntryTimestamp: &now,
	}
	if err := repo.CreateTradeLog(created); err != nil {
		t.Fatalf("CreateTradeLog: %v", err)
	}

	exitPrice := 110.25
	pnl := 9.75
	pnlUSD := 9.75
	entryZ := 1.5
	exitZ := 2.5
	exitTS := now.Add(2 * time.Hour)
	created.ExitPrice1 = &exitPrice
	created.ExitPrice2 = &exitPrice
	created.Pnl = &pnl
	created.PnlUSD = &pnlUSD
	created.EntryZScore = &entryZ
	created.ExitZScore = &exitZ
	created.ExitTimestamp = &exitTS

	if err := repo.UpdateTradeLog(created); err != nil {
		t.Fatalf("UpdateTradeLog: %v", err)
	}

	updated, err := repo.GetTradeLogByID(created.ID, 0)
	if err != nil {
		t.Fatalf("GetTradeLogByID: %v", err)
	}
	if updated == nil {
		t.Fatal("expected trade log to exist after update")
	}
	if updated.Pnl == nil || *updated.Pnl != pnl {
		t.Fatalf("expected pnl=%v persisted, got %+v", pnl, updated.Pnl)
	}
	if updated.PnlUSD == nil || *updated.PnlUSD != pnlUSD {
		t.Fatalf("expected pnl_usd=%v persisted, got %+v", pnlUSD, updated.PnlUSD)
	}
	if updated.ExitPrice1 == nil || *updated.ExitPrice1 != exitPrice {
		t.Fatalf("expected exit_price_1=%v persisted, got %+v", exitPrice, updated.ExitPrice1)
	}
	if updated.ExitTimestamp == nil || !updated.ExitTimestamp.Equal(exitTS) {
		t.Fatalf("expected exit_timestamp=%v persisted, got %+v", exitTS, updated.ExitTimestamp)
	}
}
