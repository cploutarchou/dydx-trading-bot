package repository

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// TradeLogRepository handles trade log database operations
type TradeLogRepository struct {
	db       *sql.DB
	dbDriver string
}

// NewTradeLogRepository creates a new trade log repository
func NewTradeLogRepository(db *sql.DB) *TradeLogRepository {
	driver := os.Getenv("DB_TYPE")
	if driver == "" {
		driver = os.Getenv("DB_DRIVER")
	}
	if driver == "" {
		driver = "postgres"
	}
	return &TradeLogRepository{db: db, dbDriver: driver}
}

func (r *TradeLogRepository) bindQuery(query string) string {
	return bindPlaceholders(r.dbDriver, query)
}

// CreateTradeLog creates a new trade log entry
func (r *TradeLogRepository) CreateTradeLog(tradeLog *models.TradeLog) error {
	query := `
		INSERT INTO trade_logs (
			result_id_fk, trade_number, entry_price_1, entry_price_2,
			exit_price_1, exit_price_2, quantity_1, quantity_2,
			side_1, side_2, pnl, pnl_usd, entry_zscore, exit_zscore,
			entry_timestamp, exit_timestamp, created_at
			) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
			RETURNING id
		`

	now := time.Now()
	if err := r.db.QueryRow(
		r.bindQuery(query),
		tradeLog.ResultIDFK, tradeLog.TradeNumber, tradeLog.EntryPrice1, tradeLog.EntryPrice2,
		tradeLog.ExitPrice1, tradeLog.ExitPrice2, tradeLog.Quantity1, tradeLog.Quantity2,
		tradeLog.Side1, tradeLog.Side2, tradeLog.Pnl, tradeLog.PnlUSD, tradeLog.EntryZScore,
		tradeLog.ExitZScore, tradeLog.EntryTimestamp, tradeLog.ExitTimestamp, now,
	).Scan(&tradeLog.ID); err != nil {
		return fmt.Errorf("failed to create trade log: %w", err)
	}
	tradeLog.CreatedAt = now

	return nil
}

// GetResultOwnerID resolves the user that owns the backtest run a result
// belongs to (trade_logs -> backtest_results -> backtest_runs). Returns nil
// when the result does not exist.
func (r *TradeLogRepository) GetResultOwnerID(resultIDFK int) (*int, error) {
	query := `
		SELECT run.user_id
		FROM backtest_results br
		JOIN backtest_runs run ON br.run_id_fk = run.id
		WHERE br.id = ?
		LIMIT 1
	`
	var ownerID int
	err := r.db.QueryRow(r.bindQuery(query), resultIDFK).Scan(&ownerID)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to resolve result owner: %w", err)
	}
	return &ownerID, nil
}

// GetTradeLogByID retrieves a trade log by ID. ownerUserID > 0 restricts the
// lookup to logs belonging to that user's runs (0 = unscoped, for admins).
// Returns nil when the log does not exist or is out of scope.
func (r *TradeLogRepository) GetTradeLogByID(id int, ownerUserID int) (*models.TradeLog, error) {
	query := `
		SELECT tl.id, tl.result_id_fk, tl.trade_number, tl.entry_price_1, tl.entry_price_2,
		       tl.exit_price_1, tl.exit_price_2, tl.quantity_1, tl.quantity_2, tl.side_1, tl.side_2,
		       tl.pnl, tl.pnl_usd, tl.entry_zscore, tl.exit_zscore, tl.entry_timestamp,
		       tl.exit_timestamp, tl.created_at
		FROM trade_logs tl
		JOIN backtest_results br ON tl.result_id_fk = br.id
		JOIN backtest_runs run ON br.run_id_fk = run.id
		WHERE tl.id = ?
		  AND (? <= 0 OR run.user_id = ?)
		LIMIT 1
	`

	tradeLog := &models.TradeLog{}
	err := r.db.QueryRow(r.bindQuery(query), id, ownerUserID, ownerUserID).Scan(
		&tradeLog.ID, &tradeLog.ResultIDFK, &tradeLog.TradeNumber, &tradeLog.EntryPrice1,
		&tradeLog.EntryPrice2, &tradeLog.ExitPrice1, &tradeLog.ExitPrice2, &tradeLog.Quantity1,
		&tradeLog.Quantity2, &tradeLog.Side1, &tradeLog.Side2, &tradeLog.Pnl, &tradeLog.PnlUSD,
		&tradeLog.EntryZScore, &tradeLog.ExitZScore, &tradeLog.EntryTimestamp,
		&tradeLog.ExitTimestamp, &tradeLog.CreatedAt,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get trade log: %w", err)
	}

	return tradeLog, nil
}

// GetTradeLogsByResult retrieves trade logs for a specific result. ownerUserID
// > 0 restricts results to that user's runs (0 = unscoped, for admins).
func (r *TradeLogRepository) GetTradeLogsByResult(resultIDFK int, ownerUserID int) ([]models.TradeLog, error) {
	query := `
		SELECT tl.id, tl.result_id_fk, tl.trade_number, tl.entry_price_1, tl.entry_price_2,
		       tl.exit_price_1, tl.exit_price_2, tl.quantity_1, tl.quantity_2, tl.side_1, tl.side_2,
		       tl.pnl, tl.pnl_usd, tl.entry_zscore, tl.exit_zscore, tl.entry_timestamp,
		       tl.exit_timestamp, tl.created_at
		FROM trade_logs tl
		JOIN backtest_results br ON tl.result_id_fk = br.id
		JOIN backtest_runs run ON br.run_id_fk = run.id
		WHERE tl.result_id_fk = ?
		  AND (? <= 0 OR run.user_id = ?)
		ORDER BY tl.trade_number ASC
	`

	rows, err := r.db.Query(r.bindQuery(query), resultIDFK, ownerUserID, ownerUserID)
	if err != nil {
		return nil, fmt.Errorf("failed to query trade logs: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close trade log rows: %v", closeErr)
		}
	}()

	var tradeLogs []models.TradeLog
	for rows.Next() {
		tradeLog := models.TradeLog{}
		err := rows.Scan(
			&tradeLog.ID, &tradeLog.ResultIDFK, &tradeLog.TradeNumber, &tradeLog.EntryPrice1,
			&tradeLog.EntryPrice2, &tradeLog.ExitPrice1, &tradeLog.ExitPrice2, &tradeLog.Quantity1,
			&tradeLog.Quantity2, &tradeLog.Side1, &tradeLog.Side2, &tradeLog.Pnl, &tradeLog.PnlUSD,
			&tradeLog.EntryZScore, &tradeLog.ExitZScore, &tradeLog.EntryTimestamp,
			&tradeLog.ExitTimestamp, &tradeLog.CreatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan trade log: %w", err)
		}
		tradeLogs = append(tradeLogs, tradeLog)
	}

	return tradeLogs, rows.Err()
}

// UpdateTradeLog updates an existing trade log
func (r *TradeLogRepository) UpdateTradeLog(tradeLog *models.TradeLog) error {
	query := `
		UPDATE trade_logs
		SET trade_number = ?, entry_price_1 = ?, entry_price_2 = ?,
		    exit_price_1 = ?, exit_price_2 = ?, quantity_1 = ?, quantity_2 = ?,
		    side_1 = ?, side_2 = ?, pnl = ?, pnl_usd = ?, entry_zscore = ?,
		    exit_zscore = ?, exit_timestamp = ?
		WHERE id = ?
	`

	result, err := r.db.Exec(
		r.bindQuery(query),
		tradeLog.TradeNumber, tradeLog.EntryPrice1, tradeLog.EntryPrice2,
		tradeLog.ExitPrice1, tradeLog.ExitPrice2, tradeLog.Quantity1, tradeLog.Quantity2,
		tradeLog.Side1, tradeLog.Side2, tradeLog.Pnl, tradeLog.PnlUSD, tradeLog.EntryZScore,
		tradeLog.ExitZScore, tradeLog.ExitTimestamp, tradeLog.ID,
	)

	if err != nil {
		return fmt.Errorf("failed to update trade log: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("trade log not found")
	}

	return nil
}

// DeleteTradeLog deletes a trade log
func (r *TradeLogRepository) DeleteTradeLog(id int) error {
	query := `DELETE FROM trade_logs WHERE id = ?`

	result, err := r.db.Exec(r.bindQuery(query), id)
	if err != nil {
		return fmt.Errorf("failed to delete trade log: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("trade log not found")
	}

	return nil
}

// GetTradeLogsByBacktestRun retrieves trade logs for a specific backtest run.
// ownerUserID > 0 restricts results to that user's runs (0 = unscoped).
func (r *TradeLogRepository) GetTradeLogsByBacktestRun(runID int, ownerUserID int) ([]models.TradeLog, error) {
	query := `
		SELECT tl.id, tl.result_id_fk, tl.trade_number, tl.entry_price_1, tl.entry_price_2,
		       tl.exit_price_1, tl.exit_price_2, tl.quantity_1, tl.quantity_2, tl.side_1,
		       tl.side_2, tl.pnl, tl.pnl_usd, tl.entry_zscore, tl.exit_zscore,
		       tl.entry_timestamp, tl.exit_timestamp, tl.created_at
		FROM trade_logs tl
		JOIN backtest_results br ON tl.result_id_fk = br.id
		JOIN backtest_runs run ON br.run_id_fk = run.id
		WHERE br.run_id_fk = ?
		  AND (? <= 0 OR run.user_id = ?)
		ORDER BY tl.entry_timestamp ASC
	`

	rows, err := r.db.Query(r.bindQuery(query), runID, ownerUserID, ownerUserID)
	if err != nil {
		return nil, fmt.Errorf("failed to query trade logs: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close run trade log rows: %v", closeErr)
		}
	}()

	var tradeLogs []models.TradeLog
	for rows.Next() {
		tradeLog := models.TradeLog{}
		err := rows.Scan(
			&tradeLog.ID, &tradeLog.ResultIDFK, &tradeLog.TradeNumber, &tradeLog.EntryPrice1,
			&tradeLog.EntryPrice2, &tradeLog.ExitPrice1, &tradeLog.ExitPrice2, &tradeLog.Quantity1,
			&tradeLog.Quantity2, &tradeLog.Side1, &tradeLog.Side2, &tradeLog.Pnl, &tradeLog.PnlUSD,
			&tradeLog.EntryZScore, &tradeLog.ExitZScore, &tradeLog.EntryTimestamp,
			&tradeLog.ExitTimestamp, &tradeLog.CreatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan trade log: %w", err)
		}
		tradeLogs = append(tradeLogs, tradeLog)
	}

	return tradeLogs, rows.Err()
}
