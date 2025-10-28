package repository

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

type BacktestRepository struct {
	db *sql.DB
}

func NewBacktestRepository(db *sql.DB) *BacktestRepository {
	return &BacktestRepository{db: db}
}

type CandleFilter struct {
	RunID     int
	Market    string
	StartDate *time.Time
	EndDate   *time.Time
}

func (r *BacktestRepository) GetRunByID(runID string) (*models.BacktestRun, error) {
	query := "SELECT id FROM backtest_runs WHERE run_id = $1 LIMIT 1"

	run := &models.BacktestRun{}
	err := r.db.QueryRow(query, runID).Scan(&run.ID)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get backtest run: %w", err)
	}

	return run, nil
}

func (r *BacktestRepository) GetCandles(filter CandleFilter) ([]models.BacktestCandle, error) {
	query := `
		SELECT id, run_id, market, timestamp, resolution, open_price, high_price, low_price, close_price, volume, trades_count
		FROM backtest_candles
		WHERE run_id = $1
	`
	args := []interface{}{filter.RunID}
	argNum := 2

	if filter.Market != "" {
		query += fmt.Sprintf(" AND market = $%d", argNum)
		args = append(args, filter.Market)
		argNum++
	}

	if filter.StartDate != nil {
		query += fmt.Sprintf(" AND timestamp >= $%d", argNum)
		args = append(args, filter.StartDate)
		argNum++
	}

	if filter.EndDate != nil {
		query += fmt.Sprintf(" AND timestamp <= $%d", argNum)
		args = append(args, filter.EndDate)
		argNum++
	}

	query += " ORDER BY timestamp"

	rows, err := r.db.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query candles: %w", err)
	}
	defer rows.Close()

	var candles []models.BacktestCandle
	for rows.Next() {
		candle := models.BacktestCandle{}
		err := rows.Scan(
			&candle.ID,
			&candle.RunID,
			&candle.Market,
			&candle.Timestamp,
			&candle.Resolution,
			&candle.OpenPrice,
			&candle.HighPrice,
			&candle.LowPrice,
			&candle.ClosePrice,
			&candle.Volume,
			&candle.TradesCount,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan candle: %w", err)
		}
		candles = append(candles, candle)
	}

	if err = rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating candles: %w", err)
	}

	return candles, nil
}

type PositionFilter struct {
	RunID   int
	Status  string
	Market1 string
	Market2 string
}

func (r *BacktestRepository) GetPositions(filter PositionFilter) ([]models.BacktestPosition, error) {
	query := `
		SELECT id, run_id, market_1, market_2, entry_price_1, exit_price_1, entry_price_2, exit_price_2,
		       entry_timestamp, exit_timestamp, status
		FROM backtest_positions
		WHERE run_id = $1
	`
	args := []interface{}{filter.RunID}
	argNum := 2

	if filter.Status != "" && filter.Status != "ALL" {
		query += fmt.Sprintf(" AND status = $%d", argNum)
		args = append(args, filter.Status)
		argNum++
	}

	if filter.Market1 != "" {
		query += fmt.Sprintf(" AND market_1 = $%d", argNum)
		args = append(args, filter.Market1)
		argNum++
	}

	if filter.Market2 != "" {
		query += fmt.Sprintf(" AND market_2 = $%d", argNum)
		args = append(args, filter.Market2)
		argNum++
	}

	query += " ORDER BY entry_timestamp"

	rows, err := r.db.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query positions: %w", err)
	}
	defer rows.Close()

	var positions []models.BacktestPosition
	for rows.Next() {
		pos := models.BacktestPosition{}
		err := rows.Scan(
			&pos.ID,
			&pos.RunID,
			&pos.Market1,
			&pos.Market2,
			&pos.EntryPrice1,
			&pos.ExitPrice1,
			&pos.EntryPrice2,
			&pos.ExitPrice2,
			&pos.EntryTimestamp,
			&pos.ExitTimestamp,
			&pos.Status,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan position: %w", err)
		}
		positions = append(positions, pos)
	}

	if err = rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating positions: %w", err)
	}

	return positions, nil
}

func (r *BacktestRepository) GetPositionCountsByStatus(runID int) (open, closed int, err error) {
	openQuery := "SELECT COUNT(*) FROM backtest_positions WHERE run_id = $1 AND status = 'OPEN'"
	closedQuery := "SELECT COUNT(*) FROM backtest_positions WHERE run_id = $1 AND status = 'CLOSED'"

	err = r.db.QueryRow(openQuery, runID).Scan(&open)
	if err != nil {
		return 0, 0, fmt.Errorf("failed to get open positions count: %w", err)
	}

	err = r.db.QueryRow(closedQuery, runID).Scan(&closed)
	if err != nil {
		return 0, 0, fmt.Errorf("failed to get closed positions count: %w", err)
	}

	return open, closed, nil
}

type TradeFilter struct {
	RunID   int
	Market1 string
	Market2 string
	Skip    int
	Limit   int
}

func (r *BacktestRepository) GetTrades(filter TradeFilter) ([]models.BacktestTrade, error) {
	query := `
		SELECT id, run_id, trade_id, market_1, market_2, entry_price_1, exit_price_1, entry_price_2, exit_price_2,
		       entry_z_score, exit_z_score, entry_timestamp, exit_timestamp, duration_hours, pnl, pnl_pct
		FROM backtest_trades
		WHERE run_id = $1
	`
	args := []interface{}{filter.RunID}
	argNum := 2

	if filter.Market1 != "" {
		query += fmt.Sprintf(" AND market_1 = $%d", argNum)
		args = append(args, filter.Market1)
		argNum++
	}

	if filter.Market2 != "" {
		query += fmt.Sprintf(" AND market_2 = $%d", argNum)
		args = append(args, filter.Market2)
		argNum++
	}

	query += " ORDER BY entry_timestamp"
	query += fmt.Sprintf(" OFFSET $%d LIMIT $%d", argNum, argNum+1)
	args = append(args, filter.Skip, filter.Limit)

	rows, err := r.db.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query trades: %w", err)
	}
	defer rows.Close()

	var trades []models.BacktestTrade
	for rows.Next() {
		trade := models.BacktestTrade{}
		err := rows.Scan(
			&trade.ID,
			&trade.RunID,
			&trade.TradeID,
			&trade.Market1,
			&trade.Market2,
			&trade.EntryPrice1,
			&trade.ExitPrice1,
			&trade.EntryPrice2,
			&trade.ExitPrice2,
			&trade.EntryZScore,
			&trade.ExitZScore,
			&trade.EntryTimestamp,
			&trade.ExitTimestamp,
			&trade.DurationHours,
			&trade.Pnl,
			&trade.PnlPct,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan trade: %w", err)
		}
		trades = append(trades, trade)
	}

	if err = rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating trades: %w", err)
	}

	return trades, nil
}

func (r *BacktestRepository) GetTradesCount(runID int, market1, market2 string) (int, error) {
	query := "SELECT COUNT(*) FROM backtest_trades WHERE run_id = $1"
	args := []interface{}{runID}
	argNum := 2

	if market1 != "" {
		query += fmt.Sprintf(" AND market_1 = $%d", argNum)
		args = append(args, market1)
		argNum++
	}

	if market2 != "" {
		query += fmt.Sprintf(" AND market_2 = $%d", argNum)
		args = append(args, market2)
		argNum++
	}

	var count int
	err := r.db.QueryRow(query, args...).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to count trades: %w", err)
	}

	return count, nil
}

func (r *BacktestRepository) GetUniqueMarkets(runID int) ([]string, error) {
	query := "SELECT DISTINCT market FROM backtest_candles WHERE run_id = $1 ORDER BY market"

	rows, err := r.db.Query(query, runID)
	if err != nil {
		return nil, fmt.Errorf("failed to query markets: %w", err)
	}
	defer rows.Close()

	var markets []string
	for rows.Next() {
		var market string
		err := rows.Scan(&market)
		if err != nil {
			return nil, fmt.Errorf("failed to scan market: %w", err)
		}
		markets = append(markets, market)
	}

	if err = rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating markets: %w", err)
	}

	return markets, nil
}
