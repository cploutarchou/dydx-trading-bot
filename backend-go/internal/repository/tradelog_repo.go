package repository

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// TradeLogRepository handles trade log database operations
type TradeLogRepository struct {
	db *sql.DB
}

// NewTradeLogRepository creates a new trade log repository
func NewTradeLogRepository(db *sql.DB) *TradeLogRepository {
	return &TradeLogRepository{db: db}
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
		RETURNING id, created_at
	`

	now := time.Now()
	err := r.db.QueryRow(
		query,
		tradeLog.ResultIDFK, tradeLog.TradeNumber, tradeLog.EntryPrice1, tradeLog.EntryPrice2,
		tradeLog.ExitPrice1, tradeLog.ExitPrice2, tradeLog.Quantity1, tradeLog.Quantity2,
		tradeLog.Side1, tradeLog.Side2, tradeLog.Pnl, tradeLog.PnlUSD, tradeLog.EntryZScore,
		tradeLog.ExitZScore, tradeLog.EntryTimestamp, tradeLog.ExitTimestamp, now,
	).Scan(&tradeLog.ID, &tradeLog.CreatedAt)

	if err != nil {
		return fmt.Errorf("failed to create trade log: %w", err)
	}

	return nil
}

// GetTradeLogByID retrieves a trade log by ID
func (r *TradeLogRepository) GetTradeLogByID(id int) (*models.TradeLog, error) {
	query := `
		SELECT id, result_id_fk, trade_number, entry_price_1, entry_price_2,
		       exit_price_1, exit_price_2, quantity_1, quantity_2, side_1, side_2,
		       pnl, pnl_usd, entry_zscore, exit_zscore, entry_timestamp,
		       exit_timestamp, created_at
		FROM trade_logs
		WHERE id = ?
		LIMIT 1
	`

	tradeLog := &models.TradeLog{}
	err := r.db.QueryRow(query, id).Scan(
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

// GetTradeLogsByResult retrieves all trade logs for a specific result
func (r *TradeLogRepository) GetTradeLogsByResult(resultIDFK int) ([]models.TradeLog, error) {
	query := `
		SELECT id, result_id_fk, trade_number, entry_price_1, entry_price_2,
		       exit_price_1, exit_price_2, quantity_1, quantity_2, side_1, side_2,
		       pnl, pnl_usd, entry_zscore, exit_zscore, entry_timestamp,
		       exit_timestamp, created_at
		FROM trade_logs
		WHERE result_id_fk = ?
		ORDER BY trade_number ASC
	`

	rows, err := r.db.Query(query, resultIDFK)
	if err != nil {
		return nil, fmt.Errorf("failed to query trade logs: %w", err)
	}
	defer rows.Close()

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
		query,
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

	result, err := r.db.Exec(query, id)
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

// GetTradeLogsByBacktestRun retrieves all trade logs for a specific backtest run
func (r *TradeLogRepository) GetTradeLogsByBacktestRun(runID int) ([]models.TradeLog, error) {
	query := `
		SELECT tl.id, tl.result_id_fk, tl.trade_number, tl.entry_price_1, tl.entry_price_2,
		       tl.exit_price_1, tl.exit_price_2, tl.quantity_1, tl.quantity_2, tl.side_1,
		       tl.side_2, tl.pnl, tl.pnl_usd, tl.entry_zscore, tl.exit_zscore,
		       tl.entry_timestamp, tl.exit_timestamp, tl.created_at
		FROM trade_logs tl
		JOIN backtest_results br ON tl.result_id_fk = br.id
		WHERE br.run_id = ?
		ORDER BY tl.entry_timestamp ASC
	`

	rows, err := r.db.Query(query, runID)
	if err != nil {
		return nil, fmt.Errorf("failed to query trade logs: %w", err)
	}
	defer rows.Close()

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
