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
	`
	if _, err := db.Exec(schema); err != nil {
		t.Fatalf("create trade_logs schema: %v", err)
	}
	return db
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
		ResultIDFK:     7,
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

	updated, err := repo.GetTradeLogByID(created.ID)
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
