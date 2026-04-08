package repository

import (
	"database/sql"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

func TestUpsertBacktestRunAllowsNullableSyncFields(t *testing.T) {
	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	defer func() { _ = dbConn.Close() }()

	_, err = dbConn.Exec(`
		CREATE TABLE backtest_runs (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			run_id TEXT NOT NULL UNIQUE,
			status TEXT,
			created_at DATETIME,
			started_at DATETIME,
			completed_at DATETIME,
			duration_seconds REAL,
			start_date TEXT NOT NULL,
			end_date TEXT NOT NULL,
			num_pairs INTEGER NOT NULL,
			total_markets INTEGER NOT NULL,
			resolution TEXT,
			config TEXT,
			total_trades INTEGER,
			profitable_trades INTEGER,
			losing_trades INTEGER,
			win_rate REAL,
			total_pnl REAL,
			total_pnl_usd REAL,
			error_message TEXT,
			user_id INTEGER
		);
	`)
	if err != nil {
		t.Fatalf("create backtest_runs: %v", err)
	}

	now := time.Now().UTC()
	_, err = dbConn.Exec(
		`INSERT INTO backtest_runs (run_id, status, created_at, start_date, end_date, num_pairs, total_markets, error_message, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"run-sync-1",
		"queued",
		now,
		"2026-04-01",
		"2026-04-02",
		2,
		10,
		"existing-error",
		7,
	)
	if err != nil {
		t.Fatalf("seed backtest_run: %v", err)
	}

	repo := NewBacktestSyncRepository(dbConn)
	durationSeconds := 123.45
	if err := repo.UpsertBacktestRun(BacktestRunSyncPayload{
		RunID:           "run-sync-1",
		UserID:          7,
		Status:          "completed",
		StartDate:       "2026-04-01",
		EndDate:         "2026-04-02",
		NumPairs:        2,
		TotalMarkets:    10,
		DurationSeconds: &durationSeconds,
		Resolution:      sql.NullString{},
		Config:          sql.NullString{},
		ErrorMessage:    sql.NullString{},
		TotalTrades:     sql.NullInt64{},
		WinningTrades:   sql.NullInt64{},
		LosingTrades:    sql.NullInt64{},
		WinRate:         sql.NullFloat64{},
		TotalPnL:        sql.NullFloat64{},
		TotalPnLUSD:     sql.NullFloat64{},
	}); err != nil {
		t.Fatalf("upsert backtest run: %v", err)
	}

	var (
		status       string
		errorMessage sql.NullString
		duration     sql.NullFloat64
	)
	err = dbConn.QueryRow(
		`SELECT status, error_message, duration_seconds FROM backtest_runs WHERE run_id = ?`,
		"run-sync-1",
	).Scan(&status, &errorMessage, &duration)
	if err != nil {
		t.Fatalf("query updated run: %v", err)
	}

	if status != "completed" {
		t.Fatalf("expected status completed, got %q", status)
	}
	if !errorMessage.Valid || errorMessage.String != "existing-error" {
		t.Fatalf("expected existing error message to be preserved, got %#v", errorMessage)
	}
	if !duration.Valid || duration.Float64 != durationSeconds {
		t.Fatalf("expected duration %.2f, got %#v", durationSeconds, duration)
	}
}
