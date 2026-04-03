package repository

import (
	"database/sql"
	"fmt"
	"time"
)

// BacktestRunSyncPayload contains the subset of backtest run fields we can
// safely synchronize from delegated bot API responses.
type BacktestRunSyncPayload struct {
	RunID           string
	UserID          int
	Status          string
	StartDate       string
	EndDate         string
	NumPairs        int
	TotalMarkets    int
	Resolution      sql.NullString
	Config          sql.NullString
	StartedAt       *time.Time
	CompletedAt     *time.Time
	DurationSeconds *float64
	ErrorMessage    sql.NullString
	TotalTrades     sql.NullInt64
	WinningTrades   sql.NullInt64
	LosingTrades    sql.NullInt64
	WinRate         sql.NullFloat64
	TotalPnL        sql.NullFloat64
	TotalPnLUSD     sql.NullFloat64
}

type BacktestSyncRepository struct {
	db *sql.DB
}

func NewBacktestSyncRepository(db *sql.DB) *BacktestSyncRepository {
	return &BacktestSyncRepository{db: db}
}

func (r *BacktestSyncRepository) UpsertBacktestRun(payload BacktestRunSyncPayload) error {
	if payload.RunID == "" {
		return fmt.Errorf("run_id is required")
	}
	if payload.StartDate == "" {
		payload.StartDate = time.Now().UTC().Format("2006-01-02")
	}
	if payload.EndDate == "" {
		payload.EndDate = payload.StartDate
	}

	updateQuery := `
		UPDATE backtest_runs
		SET status = $1,
			user_id = $2,
			start_date = $3,
			end_date = $4,
			num_pairs = $5,
			total_markets = $6,
			resolution = $7,
			config = $8,
			started_at = COALESCE($9, started_at),
			completed_at = COALESCE($10, completed_at),
			duration_seconds = COALESCE($11, duration_seconds),
			error_message = CASE WHEN $12 IS NULL THEN error_message ELSE $12 END,
			total_trades = COALESCE($13, total_trades),
			profitable_trades = COALESCE($14, profitable_trades),
			losing_trades = COALESCE($15, losing_trades),
			win_rate = COALESCE($16, win_rate),
			total_pnl = COALESCE($17, total_pnl),
			total_pnl_usd = COALESCE($18, total_pnl_usd)
		WHERE run_id = $19
	`

	result, err := r.db.Exec(
		updateQuery,
		payload.Status,
		payload.UserID,
		payload.StartDate,
		payload.EndDate,
		payload.NumPairs,
		payload.TotalMarkets,
		payload.Resolution,
		payload.Config,
		payload.StartedAt,
		payload.CompletedAt,
		payload.DurationSeconds,
		payload.ErrorMessage,
		payload.TotalTrades,
		payload.WinningTrades,
		payload.LosingTrades,
		payload.WinRate,
		payload.TotalPnL,
		payload.TotalPnLUSD,
		payload.RunID,
	)
	if err != nil {
		return fmt.Errorf("failed to update backtest run: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to check updated rows: %w", err)
	}
	if rows > 0 {
		return nil
	}

	insertQuery := `
		INSERT INTO backtest_runs (
			run_id, status, created_at, started_at, completed_at, duration_seconds,
			start_date, end_date, num_pairs, total_markets, resolution, config,
			total_trades, profitable_trades, losing_trades, win_rate,
			total_pnl, total_pnl_usd, error_message, user_id
		) VALUES (
			$1, $2, $3, $4, $5, $6,
			$7, $8, $9, $10, $11, $12,
			$13, $14, $15, $16,
			$17, $18, $19, $20
		)
	`

	_, err = r.db.Exec(
		insertQuery,
		payload.RunID,
		payload.Status,
		time.Now().UTC(),
		payload.StartedAt,
		payload.CompletedAt,
		payload.DurationSeconds,
		payload.StartDate,
		payload.EndDate,
		payload.NumPairs,
		payload.TotalMarkets,
		payload.Resolution,
		payload.Config,
		payload.TotalTrades,
		payload.WinningTrades,
		payload.LosingTrades,
		payload.WinRate,
		payload.TotalPnL,
		payload.TotalPnLUSD,
		payload.ErrorMessage,
		payload.UserID,
	)
	if err != nil {
		return fmt.Errorf("failed to insert backtest run: %w", err)
	}

	return nil
}
