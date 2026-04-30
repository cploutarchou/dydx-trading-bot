package repository

import (
	"database/sql"
	"fmt"
	"log"
	"strings"
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
	fkColumn, err := r.detectRunFKColumn("backtest_candles")
	if err != nil {
		return nil, err
	}

	query := fmt.Sprintf(`
		SELECT id, %s AS run_id, market, timestamp, resolution, open_price, high_price, low_price, close_price, volume, trades_count
		FROM backtest_candles
		WHERE %s = $1
	`, fkColumn, fkColumn)
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
	}

	query += " ORDER BY timestamp"

	rows, err := r.db.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query candles: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close candle rows: %v", closeErr)
		}
	}()

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
	columns, err := r.getTableColumns("backtest_positions")
	if err != nil {
		return nil, err
	}

	fkColumn, err := r.detectRunFKColumn("backtest_positions")
	if err != nil {
		return nil, err
	}

	exitTimestampExpr := "close_timestamp"
	if _, exists := columns["exit_timestamp"]; exists {
		exitTimestampExpr = "exit_timestamp"
	}

	exitPrice1Expr := "NULL AS exit_price_1"
	if _, exists := columns["exit_price_1"]; exists {
		exitPrice1Expr = "exit_price_1"
	}

	exitPrice2Expr := "NULL AS exit_price_2"
	if _, exists := columns["exit_price_2"]; exists {
		exitPrice2Expr = "exit_price_2"
	}

	query := fmt.Sprintf(`
		SELECT id, %s AS run_id, position_id, market_1, market_2, status,
		       entry_price_1, entry_price_2, entry_z_score, %s, %s,
		       current_price_1, current_price_2, current_z_score,
		       side_1, side_2, size_1, size_2, hedge_ratio,
		       unrealized_pnl, realized_pnl, entry_timestamp, %s AS exit_timestamp
		FROM backtest_positions
		WHERE %s = $1
	`, fkColumn, exitPrice1Expr, exitPrice2Expr, exitTimestampExpr, fkColumn)
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
	}

	query += " ORDER BY entry_timestamp"

	rows, err := r.db.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query positions: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close position rows: %v", closeErr)
		}
	}()

	var positions []models.BacktestPosition
	for rows.Next() {
		pos := models.BacktestPosition{}
		err := rows.Scan(
			&pos.ID,
			&pos.RunID,
			&pos.PositionID,
			&pos.Market1,
			&pos.Market2,
			&pos.Status,
			&pos.EntryPrice1,
			&pos.EntryPrice2,
			&pos.EntryZScore,
			&pos.ExitPrice1,
			&pos.ExitPrice2,
			&pos.CurrentPrice1,
			&pos.CurrentPrice2,
			&pos.CurrentZScore,
			&pos.Side1,
			&pos.Side2,
			&pos.Size1,
			&pos.Size2,
			&pos.HedgeRatio,
			&pos.UnrealizedPnl,
			&pos.RealizedPnl,
			&pos.EntryTimestamp,
			&pos.ExitTimestamp,
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
	fkColumn, err := r.detectRunFKColumn("backtest_positions")
	if err != nil {
		return 0, 0, err
	}

	openQuery := fmt.Sprintf("SELECT COUNT(*) FROM backtest_positions WHERE %s = $1 AND status = 'OPEN'", fkColumn)
	closedQuery := fmt.Sprintf("SELECT COUNT(*) FROM backtest_positions WHERE %s = $1 AND status = 'CLOSED'", fkColumn)

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
	fkColumn, err := r.detectRunFKColumn("backtest_trades")
	if err != nil {
		return nil, err
	}

	query := fmt.Sprintf(`
		SELECT id, %s AS run_id, trade_id, market_1, market_2,
		       entry_price_1, entry_price_2, entry_z_score,
		       exit_price_1, exit_price_2, exit_z_score,
		       side_1, side_2, size_1, size_2,
		       hedge_ratio, transaction_fee, slippage,
		       pnl, pnl_pct, duration_hours,
		       entry_timestamp, exit_timestamp,
		       strategy_id, strategy_name, strategy_zscore_threshold
		FROM backtest_trades
		WHERE %s = $1
	`, fkColumn, fkColumn)
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
	query += fmt.Sprintf(" LIMIT $%d OFFSET $%d", argNum, argNum+1)
	args = append(args, filter.Limit, filter.Skip)

	rows, err := r.db.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query trades: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close trade rows: %v", closeErr)
		}
	}()

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
			&trade.EntryPrice2,
			&trade.EntryZScore,
			&trade.ExitPrice1,
			&trade.ExitPrice2,
			&trade.ExitZScore,
			&trade.Side1,
			&trade.Side2,
			&trade.Size1,
			&trade.Size2,
			&trade.HedgeRatio,
			&trade.TransactionFee,
			&trade.Slippage,
			&trade.Pnl,
			&trade.PnlPct,
			&trade.DurationHours,
			&trade.EntryTimestamp,
			&trade.ExitTimestamp,
			&trade.StrategyID,
			&trade.StrategyName,
			&trade.StrategyZscoreThreshold,
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
	fkColumn, err := r.detectRunFKColumn("backtest_trades")
	if err != nil {
		return 0, err
	}

	query := fmt.Sprintf("SELECT COUNT(*) FROM backtest_trades WHERE %s = $1", fkColumn)
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
	}

	var count int
	err = r.db.QueryRow(query, args...).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to count trades: %w", err)
	}

	return count, nil
}

func (r *BacktestRepository) GetUniqueMarkets(runID int) ([]string, error) {
	fkColumn, err := r.detectRunFKColumn("backtest_candles")
	if err != nil {
		return nil, err
	}

	query := fmt.Sprintf("SELECT DISTINCT market FROM backtest_candles WHERE %s = $1 ORDER BY market", fkColumn)

	rows, err := r.db.Query(query, runID)
	if err != nil {
		return nil, fmt.Errorf("failed to query markets: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close market rows: %v", closeErr)
		}
	}()

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

func (r *BacktestRepository) detectRunFKColumn(tableName string) (string, error) {
	columns, err := r.getTableColumns(tableName)
	if err != nil {
		return "", err
	}

	if _, exists := columns["run_id_fk"]; exists {
		return "run_id_fk", nil
	}
	if _, exists := columns["run_id"]; exists {
		return "run_id", nil
	}

	return "", fmt.Errorf("table %s has no run foreign-key column", tableName)
}

func (r *BacktestRepository) getTableColumns(tableName string) (_ map[string]struct{}, err error) {
	rows, err := r.db.Query(fmt.Sprintf("SELECT * FROM %s LIMIT 0", tableName))
	if err != nil {
		return nil, fmt.Errorf("failed to inspect table %s: %w", tableName, err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil && err == nil {
			err = fmt.Errorf("failed to close schema rows for %s: %w", tableName, closeErr)
		}
	}()

	columnNames, err := rows.Columns()
	if err != nil {
		return nil, fmt.Errorf("failed to inspect columns for %s: %w", tableName, err)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("failed to inspect schema rows for %s: %w", tableName, err)
	}

	columns := make(map[string]struct{}, len(columnNames))
	for _, name := range columnNames {
		columns[strings.ToLower(strings.TrimSpace(name))] = struct{}{}
	}

	return columns, nil
}

func (r *BacktestRepository) GetRunsByUserID(userID int, skip int, limit int) ([]models.BacktestRun, error) {
	// Excludes heavy JSON blobs (config, strategy_snapshot) — these are only needed on the detail
	// view and can easily double/triple per-row payload size for large backtests.
	query := `
		SELECT id, user_id, strategy_id, strategy_version_id, run_id, status, start_date, end_date,
		       num_pairs, total_markets, resolution, total_trades, profitable_trades, losing_trades,
		       win_rate, total_pnl, total_pnl_usd, sharpe_ratio, sortino_ratio, calmar_ratio,
		       max_drawdown, profit_factor, starting_balance, ending_balance, max_balance, min_balance,
		       error_message, started_at, completed_at, duration_seconds,
		       created_at
		FROM backtest_runs
		WHERE user_id = $1
		ORDER BY created_at DESC
		LIMIT $2 OFFSET $3
	`

	rows, err := r.db.Query(query, userID, limit, skip)
	if err != nil {
		return nil, fmt.Errorf("failed to query backtest runs: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close backtest run rows: %v", closeErr)
		}
	}()

	var runs []models.BacktestRun
	for rows.Next() {
		run := models.BacktestRun{}
		err := rows.Scan(
			&run.ID,
			&run.UserID,
			&run.StrategyID,
			&run.StrategyVersionID,
			&run.RunID,
			&run.Status,
			&run.StartDate,
			&run.EndDate,
			&run.NumPairs,
			&run.TotalMarkets,
			&run.Resolution,
			&run.TotalTrades,
			&run.ProfitableTrades,
			&run.LosingTrades,
			&run.WinRate,
			&run.TotalPnL,
			&run.TotalPnLUSD,
			&run.SharpeRatio,
			&run.SortinoRatio,
			&run.CalmarRatio,
			&run.MaxDrawdown,
			&run.ProfitFactor,
			&run.StartingBalance,
			&run.EndingBalance,
			&run.MaxBalance,
			&run.MinBalance,
			&run.ErrorMessage,
			&run.StartedAt,
			&run.CompletedAt,
			&run.DurationSeconds,
			&run.CreatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan backtest run: %w", err)
		}
		runs = append(runs, run)
	}

	if err = rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating backtest runs: %w", err)
	}

	return runs, nil
}
