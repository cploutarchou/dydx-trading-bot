package repository

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

type BacktestRepository struct {
	db             *sql.DB
	dbDriver       string // Store driver name to determine parameter syntax
	admissionLocks sync.Map
}

// NewBacktestRepository creates a BacktestRepository with automatic driver detection
func NewBacktestRepository(db *sql.DB) *BacktestRepository {
	// Detect database driver from environment.
	driver := os.Getenv("DB_TYPE")
	if driver == "" {
		driver = os.Getenv("DB_DRIVER")
	}
	if driver == "" {
		driver = "postgres"
	}

	return &BacktestRepository{
		db:       db,
		dbDriver: driver,
	}
}

// NewBacktestRepositoryWithDriver creates a BacktestRepository with explicit driver information
func NewBacktestRepositoryWithDriver(db *sql.DB, driver string) *BacktestRepository {
	return &BacktestRepository{
		db:       db,
		dbDriver: driver,
	}
}

var errAdvisoryLockUnsupported = errors.New("named locks unsupported")

func backtestAdmissionLockKey(userID int) string {
	return fmt.Sprintf("backtest-admission:%d", userID)
}

func isAdvisoryLockUnsupportedError(err error) bool {
	if err == nil {
		return false
	}
	lower := strings.ToLower(err.Error())
	if strings.Contains(lower, "pg_try_advisory_lock") || strings.Contains(lower, "pg_advisory_unlock") {
		if strings.Contains(lower, "does not exist") || strings.Contains(lower, "unknown function") {
			return true
		}
	}
	return false
}

func (r *BacktestRepository) bindQuery(query string) string {
	return bindPlaceholders(r.dbDriver, query)
}

func (r *BacktestRepository) withInProcessAdmissionLock(userID int, fn func() error) error {
	lockValue, _ := r.admissionLocks.LoadOrStore(userID, &sync.Mutex{})
	lock := lockValue.(*sync.Mutex)
	lock.Lock()
	defer lock.Unlock()
	return fn()
}

func (r *BacktestRepository) withNamedAdmissionLock(ctx context.Context, userID int, fn func() error) error {
	if r == nil || r.db == nil {
		return errAdvisoryLockUnsupported
	}

	conn, err := r.db.Conn(ctx)
	if err != nil {
		return fmt.Errorf("failed to acquire database connection for admission lock: %w", err)
	}
	defer func() { _ = conn.Close() }()

	lockKey := backtestAdmissionLockKey(userID)

	// Try to acquire non-blocking advisory lock.
	var acquired bool
	if err := conn.QueryRowContext(ctx, `SELECT pg_try_advisory_lock(hashtext($1))`, lockKey).Scan(&acquired); err != nil {
		if isAdvisoryLockUnsupportedError(err) {
			return errAdvisoryLockUnsupported
		}
		return fmt.Errorf("failed to acquire lock for user %d: %w", userID, err)
	}

	if !acquired {
		return fmt.Errorf("failed to acquire admission lock for user %d: lock is already held", userID)
	}

	defer func() {
		if _, unlockErr := conn.ExecContext(context.Background(), `SELECT pg_advisory_unlock(hashtext($1))`, lockKey); unlockErr != nil {
			log.Printf("failed to release admission lock for user %d: %v", userID, unlockErr)
		}
	}()

	return fn()
}

// WithUserAdmissionLock serializes admission checks per user.
//
// Behavior:
// - PostgreSQL runtime: uses advisory locks via pg_try_advisory_lock/pg_advisory_unlock.
// - Unsupported engines/test setups: falls back to in-process mutex lock.
func (r *BacktestRepository) WithUserAdmissionLock(ctx context.Context, userID int, fn func() error) error {
	if userID <= 0 {
		return fmt.Errorf("invalid user id")
	}
	if fn == nil {
		return fmt.Errorf("admission callback is required")
	}
	if ctx == nil {
		ctx = context.Background()
	}

	if err := r.withNamedAdmissionLock(ctx, userID, fn); err != nil {
		if errors.Is(err, errAdvisoryLockUnsupported) {
			return r.withInProcessAdmissionLock(userID, fn)
		}
		return err
	}

	return nil
}

type CandleFilter struct {
	RunID     int
	Market    string
	StartDate *time.Time
	EndDate   *time.Time
	Skip      int
	Limit     int
}

func (r *BacktestRepository) GetRunByID(runID string) (*models.BacktestRun, error) {
	ctx, cancel := context.WithTimeout(context.Background(), defaultQueryTimeout)
	defer cancel()
	return r.GetRunByIDContext(ctx, runID)
}

// GetRunByIDContext loads a run stub by its public run id, honouring cancellation.
func (r *BacktestRepository) GetRunByIDContext(ctx context.Context, runID string) (*models.BacktestRun, error) {
	query := "SELECT id FROM backtest_runs WHERE run_id = ? LIMIT 1"

	run := &models.BacktestRun{}
	err := r.db.QueryRowContext(ctx, r.bindQuery(query), runID).Scan(&run.ID)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get backtest run: %w", err)
	}

	return run, nil
}

func (r *BacktestRepository) GetRunOwnerID(runID string) (*int, error) {
	ctx, cancel := context.WithTimeout(context.Background(), defaultQueryTimeout)
	defer cancel()
	return r.GetRunOwnerIDContext(ctx, runID)
}

// GetRunOwnerIDContext resolves a run's owner, honouring cancellation.
func (r *BacktestRepository) GetRunOwnerIDContext(ctx context.Context, runID string) (*int, error) {
	query := "SELECT user_id FROM backtest_runs WHERE run_id = ? LIMIT 1"

	var owner sql.NullInt64
	err := r.db.QueryRowContext(ctx, r.bindQuery(query), runID).Scan(&owner)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get backtest run owner: %w", err)
	}
	if !owner.Valid {
		return nil, nil
	}
	ownerID := int(owner.Int64)
	return &ownerID, nil
}

func (r *BacktestRepository) GetCandles(filter CandleFilter) ([]models.BacktestCandle, error) {
	fkColumn, err := r.detectRunFKColumn("backtest_candles")
	if err != nil {
		return nil, err
	}

	query := fmt.Sprintf(`
		SELECT id, %s AS run_id, market, timestamp, resolution, open_price, high_price, low_price, close_price, volume, trades_count
		FROM backtest_candles
		WHERE %s = ?
	`, fkColumn, fkColumn)
	args := []interface{}{filter.RunID}

	if filter.Market != "" {
		query += " AND market = ?"
		args = append(args, filter.Market)
	}

	if filter.StartDate != nil {
		query += " AND timestamp >= ?"
		args = append(args, filter.StartDate)
	}

	if filter.EndDate != nil {
		query += " AND timestamp <= ?"
		args = append(args, filter.EndDate)
	}

	query += " ORDER BY timestamp"
	if filter.Limit > 0 {
		query += " LIMIT ? OFFSET ?"
		args = append(args, filter.Limit, filter.Skip)
	}

	rows, err := r.db.Query(r.bindQuery(query), args...)
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
		WHERE %s = ?
	`, fkColumn, exitPrice1Expr, exitPrice2Expr, exitTimestampExpr, fkColumn)
	args := []interface{}{filter.RunID}

	if filter.Status != "" && filter.Status != "ALL" {
		query += " AND status = ?"
		args = append(args, filter.Status)
	}

	if filter.Market1 != "" {
		query += " AND market_1 = ?"
		args = append(args, filter.Market1)
	}

	if filter.Market2 != "" {
		query += " AND market_2 = ?"
		args = append(args, filter.Market2)
	}

	query += " ORDER BY entry_timestamp"

	rows, err := r.db.Query(r.bindQuery(query), args...)
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

	openQuery := fmt.Sprintf("SELECT COUNT(*) FROM backtest_positions WHERE %s = ? AND status = 'OPEN'", fkColumn)
	closedQuery := fmt.Sprintf("SELECT COUNT(*) FROM backtest_positions WHERE %s = ? AND status = 'CLOSED'", fkColumn)

	err = r.db.QueryRow(r.bindQuery(openQuery), runID).Scan(&open)
	if err != nil {
		return 0, 0, fmt.Errorf("failed to get open positions count: %w", err)
	}

	err = r.db.QueryRow(r.bindQuery(closedQuery), runID).Scan(&closed)
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
		WHERE %s = ?
	`, fkColumn, fkColumn)
	args := []interface{}{filter.RunID}

	if filter.Market1 != "" {
		query += " AND market_1 = ?"
		args = append(args, filter.Market1)
	}

	if filter.Market2 != "" {
		query += " AND market_2 = ?"
		args = append(args, filter.Market2)
	}

	query += " ORDER BY entry_timestamp"
	query += " LIMIT ? OFFSET ?"
	args = append(args, filter.Limit, filter.Skip)

	rows, err := r.db.Query(r.bindQuery(query), args...)
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

	query := fmt.Sprintf("SELECT COUNT(*) FROM backtest_trades WHERE %s = ?", fkColumn)
	args := []interface{}{runID}

	if market1 != "" {
		query += " AND market_1 = ?"
		args = append(args, market1)
	}

	if market2 != "" {
		query += " AND market_2 = ?"
		args = append(args, market2)
	}

	var count int
	err = r.db.QueryRow(r.bindQuery(query), args...).Scan(&count)
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

	query := fmt.Sprintf("SELECT DISTINCT market FROM backtest_candles WHERE %s = ? ORDER BY market", fkColumn)

	rows, err := r.db.Query(r.bindQuery(query), runID)
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

func (r *BacktestRepository) getTableColumns(tableName string) (map[string]struct{}, error) {
	return cachedTableColumns(r.db, tableName)
}

func (r *BacktestRepository) GetRunsByUserID(userID int, skip int, limit int) ([]models.BacktestRun, error) {
	ctx, cancel := context.WithTimeout(context.Background(), defaultQueryTimeout)
	defer cancel()
	return r.GetRunsByUserIDContext(ctx, userID, skip, limit)
}

// GetRunsByUserIDContext lists a user's runs, honouring cancellation.
func (r *BacktestRepository) GetRunsByUserIDContext(ctx context.Context, userID int, skip int, limit int) ([]models.BacktestRun, error) {
	// Excludes heavy JSON blobs (config, strategy_snapshot) — these are only needed on the detail
	// view and can easily double/triple per-row payload size for large backtests.
	query := `
		SELECT id, user_id, strategy_id, strategy_version_id, run_id, COALESCE(status, ''), start_date, end_date,
		       num_pairs, total_markets, COALESCE(resolution, ''), COALESCE(total_trades, 0), COALESCE(profitable_trades, 0), COALESCE(losing_trades, 0),
		       win_rate, COALESCE(total_pnl, 0), COALESCE(total_pnl_usd, 0), sharpe_ratio, sortino_ratio, calmar_ratio,
		       max_drawdown, profit_factor, COALESCE(starting_balance, 0), ending_balance, max_balance, min_balance,
		       COALESCE(error_message, ''), started_at, completed_at, duration_seconds,
		       created_at
		FROM backtest_runs
		WHERE user_id = ?
		ORDER BY created_at DESC
		LIMIT ? OFFSET ?
	`

	rows, err := r.db.QueryContext(ctx, r.bindQuery(query), userID, limit, skip)
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

func (r *BacktestRepository) CountRunsByUserID(userID int) (int, error) {
	ctx, cancel := context.WithTimeout(context.Background(), defaultQueryTimeout)
	defer cancel()
	return r.CountRunsByUserIDContext(ctx, userID)
}

// CountRunsByUserIDContext counts a user's runs, honouring cancellation.
func (r *BacktestRepository) CountRunsByUserIDContext(ctx context.Context, userID int) (int, error) {
	var count int
	if err := r.db.QueryRowContext(ctx, r.bindQuery(`SELECT COUNT(*) FROM backtest_runs WHERE user_id = ?`), userID).Scan(&count); err != nil {
		return 0, fmt.Errorf("failed to count backtest runs: %w", err)
	}
	return count, nil
}

// backtestRunListColumns is the column list of the run list queries: the
// heavy JSON blobs (config, strategy_snapshot) are excluded, they are only
// needed on the detail view.
const backtestRunListColumns = `id, user_id, strategy_id, strategy_version_id, run_id, COALESCE(status, ''), start_date, end_date,
		       num_pairs, total_markets, COALESCE(resolution, ''), COALESCE(total_trades, 0), COALESCE(profitable_trades, 0), COALESCE(losing_trades, 0),
		       win_rate, COALESCE(total_pnl, 0), COALESCE(total_pnl_usd, 0), sharpe_ratio, sortino_ratio, calmar_ratio,
		       max_drawdown, profit_factor, COALESCE(starting_balance, 0), ending_balance, max_balance, min_balance,
		       COALESCE(error_message, ''), started_at, completed_at, duration_seconds,
		       created_at`

func scanBacktestRunListRow(rows *sql.Rows) (models.BacktestRun, error) {
	run := models.BacktestRun{}
	err := rows.Scan(
		&run.ID, &run.UserID, &run.StrategyID, &run.StrategyVersionID,
		&run.RunID, &run.Status, &run.StartDate, &run.EndDate,
		&run.NumPairs, &run.TotalMarkets, &run.Resolution,
		&run.TotalTrades, &run.ProfitableTrades, &run.LosingTrades,
		&run.WinRate, &run.TotalPnL, &run.TotalPnLUSD,
		&run.SharpeRatio, &run.SortinoRatio, &run.CalmarRatio,
		&run.MaxDrawdown, &run.ProfitFactor,
		&run.StartingBalance, &run.EndingBalance, &run.MaxBalance, &run.MinBalance,
		&run.ErrorMessage, &run.StartedAt, &run.CompletedAt, &run.DurationSeconds,
		&run.CreatedAt,
	)
	return run, err
}

// backtestStatusFilter renders an optional status filter as a parameterized
// IN clause; an empty list means no filter.
func backtestStatusFilter(statuses []string) (string, []interface{}) {
	cleaned := make([]interface{}, 0, len(statuses))
	for _, status := range statuses {
		if trimmed := strings.ToLower(strings.TrimSpace(status)); trimmed != "" {
			cleaned = append(cleaned, trimmed)
		}
	}
	if len(cleaned) == 0 {
		return "", nil
	}
	placeholders := strings.Repeat("?, ", len(cleaned))
	return " AND LOWER(COALESCE(status, '')) IN (" + strings.TrimSuffix(placeholders, ", ") + ")", cleaned
}

// backtestRunListFilter renders the WHERE clause of a filtered run list: the
// user, optionally one strategy (strategyID > 0) and optionally a status list.
func backtestRunListFilter(userID int, strategyID int, statuses []string) (string, []interface{}) {
	where := ` WHERE user_id = ?`
	args := []interface{}{userID}
	if strategyID > 0 {
		where += ` AND strategy_id = ?`
		args = append(args, strategyID)
	}
	filter, filterArgs := backtestStatusFilter(statuses)
	return where + filter, append(args, filterArgs...)
}

// GetRunsByUserAndStrategyContext lists a user's runs, newest first, limited
// to one strategy when strategyID is positive and to the given statuses
// (case-insensitive) when any are given.
func (r *BacktestRepository) GetRunsByUserAndStrategyContext(ctx context.Context, userID int, strategyID int, skip int, limit int, statuses []string) ([]models.BacktestRun, error) {
	where, args := backtestRunListFilter(userID, strategyID, statuses)
	query := `SELECT ` + backtestRunListColumns + `
		FROM backtest_runs` + where + `
		ORDER BY created_at DESC
		LIMIT ? OFFSET ?`
	args = append(args, limit, skip)

	rows, err := r.db.QueryContext(ctx, r.bindQuery(query), args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query strategy backtest runs: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close strategy backtest run rows: %v", closeErr)
		}
	}()

	var runs []models.BacktestRun
	for rows.Next() {
		run, err := scanBacktestRunListRow(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan strategy backtest run: %w", err)
		}
		runs = append(runs, run)
	}
	if err = rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating strategy backtest runs: %w", err)
	}
	return runs, nil
}

// CountRunsByUserAndStrategyContext counts the runs
// GetRunsByUserAndStrategyContext lists for the same filters.
func (r *BacktestRepository) CountRunsByUserAndStrategyContext(ctx context.Context, userID int, strategyID int, statuses []string) (int, error) {
	where, args := backtestRunListFilter(userID, strategyID, statuses)
	query := `SELECT COUNT(*) FROM backtest_runs` + where

	var count int
	if err := r.db.QueryRowContext(ctx, r.bindQuery(query), args...).Scan(&count); err != nil {
		return 0, fmt.Errorf("failed to count strategy backtest runs: %w", err)
	}
	return count, nil
}

// GetRunByRunIDContext loads the full mirror row of a run by its public run
// id (metrics and the config snapshot), or nil when there is none.
func (r *BacktestRepository) GetRunByRunIDContext(ctx context.Context, runID string) (*models.BacktestRun, error) {
	query := `SELECT ` + backtestRunListColumns + `, config
		FROM backtest_runs
		WHERE run_id = ?
		LIMIT 1`
	rows, err := r.db.QueryContext(ctx, r.bindQuery(query), runID)
	if err != nil {
		return nil, fmt.Errorf("failed to query backtest run: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close backtest run rows: %v", closeErr)
		}
	}()
	if !rows.Next() {
		if err := rows.Err(); err != nil {
			return nil, fmt.Errorf("failed to read backtest run: %w", err)
		}
		return nil, nil
	}
	run := models.BacktestRun{}
	if err := rows.Scan(
		&run.ID, &run.UserID, &run.StrategyID, &run.StrategyVersionID,
		&run.RunID, &run.Status, &run.StartDate, &run.EndDate,
		&run.NumPairs, &run.TotalMarkets, &run.Resolution,
		&run.TotalTrades, &run.ProfitableTrades, &run.LosingTrades,
		&run.WinRate, &run.TotalPnL, &run.TotalPnLUSD,
		&run.SharpeRatio, &run.SortinoRatio, &run.CalmarRatio,
		&run.MaxDrawdown, &run.ProfitFactor,
		&run.StartingBalance, &run.EndingBalance, &run.MaxBalance, &run.MinBalance,
		&run.ErrorMessage, &run.StartedAt, &run.CompletedAt, &run.DurationSeconds,
		&run.CreatedAt, &run.Config,
	); err != nil {
		return nil, fmt.Errorf("failed to scan backtest run: %w", err)
	}
	return &run, nil
}

// GetRunConfigsContext returns the stored config snapshot of each given run
// id (runs without a snapshot are absent from the result).
func (r *BacktestRepository) GetRunConfigsContext(ctx context.Context, runIDs []string) (map[string]string, error) {
	configs := make(map[string]string, len(runIDs))
	if len(runIDs) == 0 {
		return configs, nil
	}
	args := make([]interface{}, 0, len(runIDs))
	for _, runID := range runIDs {
		args = append(args, runID)
	}
	placeholders := strings.TrimSuffix(strings.Repeat("?, ", len(args)), ", ")
	query := `SELECT run_id, config FROM backtest_runs WHERE run_id IN (` + placeholders + `)`

	rows, err := r.db.QueryContext(ctx, r.bindQuery(query), args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query backtest run configs: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close backtest run config rows: %v", closeErr)
		}
	}()
	for rows.Next() {
		var runID string
		var config sql.NullString
		if err := rows.Scan(&runID, &config); err != nil {
			return nil, fmt.Errorf("failed to scan backtest run config: %w", err)
		}
		if config.Valid && strings.TrimSpace(config.String) != "" {
			configs[runID] = config.String
		}
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating backtest run configs: %w", err)
	}
	return configs, nil
}

func (r *BacktestRepository) GetExperimentGroupsByUserID(userID int, runScanLimit int, groupLimit int) ([]models.BacktestExperimentGroup, error) {
	if runScanLimit <= 0 {
		runScanLimit = 500
	}
	if runScanLimit > 5000 {
		runScanLimit = 5000
	}

	query := `
		SELECT run_id, COALESCE(status, ''), created_at, completed_at,
		       COALESCE(total_trades, 0), COALESCE(total_pnl_usd, 0), win_rate,
		       config, strategy_snapshot
		FROM backtest_runs
		WHERE user_id = ?
		ORDER BY created_at DESC
		LIMIT ?
	`

	rows, err := r.db.Query(r.bindQuery(query), userID, runScanLimit)
	if err != nil {
		return nil, fmt.Errorf("failed to query experiment runs: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close experiment run rows: %v", closeErr)
		}
	}()

	groupsByID := make(map[string]*models.BacktestExperimentGroup)
	variantCountsByGroup := make(map[string]map[string]int)

	for rows.Next() {
		var runID string
		var status string
		var createdAt time.Time
		var completedAt *time.Time
		var totalTrades int
		var totalPnLUSD float64
		var winRate *float64
		var config sql.NullString
		var strategySnapshot sql.NullString

		if err := rows.Scan(
			&runID,
			&status,
			&createdAt,
			&completedAt,
			&totalTrades,
			&totalPnLUSD,
			&winRate,
			&config,
			&strategySnapshot,
		); err != nil {
			return nil, fmt.Errorf("failed to scan experiment run: %w", err)
		}

		experimentID, variant, compareWinner := extractABExperimentFields(config, strategySnapshot)
		if experimentID == "" {
			continue
		}

		group := groupsByID[experimentID]
		if group == nil {
			group = &models.BacktestExperimentGroup{
				ExperimentID:    experimentID,
				RunCount:        0,
				VariantCount:    0,
				CreatedAt:       createdAt,
				LatestCreatedAt: createdAt,
				LatestStatus:    status,
				Variants:        []models.BacktestExperimentVariantSummary{},
				Runs:            []models.BacktestExperimentRunSummary{},
			}
			groupsByID[experimentID] = group
			variantCountsByGroup[experimentID] = map[string]int{}
		}

		group.RunCount++
		if createdAt.Before(group.CreatedAt) {
			group.CreatedAt = createdAt
		}
		if createdAt.After(group.LatestCreatedAt) {
			group.LatestCreatedAt = createdAt
			group.LatestStatus = status
		}

		if variant != "" {
			variantCountsByGroup[experimentID][variant]++
		}

		runSummary := models.BacktestExperimentRunSummary{
			RunID:       runID,
			Status:      status,
			CreatedAt:   createdAt,
			CompletedAt: completedAt,
			TotalTrades: totalTrades,
			TotalPnLUSD: totalPnLUSD,
			WinRate:     winRate,
			Variant:     variant,
		}
		if compareWinner != nil {
			runSummary.CompareWinner = compareWinner
		}
		group.Runs = append(group.Runs, runSummary)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating experiment runs: %w", err)
	}

	groups := make([]models.BacktestExperimentGroup, 0, len(groupsByID))
	for experimentID, group := range groupsByID {
		counts := variantCountsByGroup[experimentID]
		variants := make([]models.BacktestExperimentVariantSummary, 0, len(counts))
		for variant, count := range counts {
			variants = append(variants, models.BacktestExperimentVariantSummary{
				Variant:  variant,
				RunCount: count,
			})
		}
		sort.SliceStable(variants, func(i, j int) bool {
			if variants[i].RunCount == variants[j].RunCount {
				return variants[i].Variant < variants[j].Variant
			}
			return variants[i].RunCount > variants[j].RunCount
		})
		group.Variants = variants
		group.VariantCount = len(variants)

		sort.SliceStable(group.Runs, func(i, j int) bool {
			return group.Runs[i].CreatedAt.After(group.Runs[j].CreatedAt)
		})

		groups = append(groups, *group)
	}

	sort.SliceStable(groups, func(i, j int) bool {
		return groups[i].LatestCreatedAt.After(groups[j].LatestCreatedAt)
	})

	if groupLimit > 0 && len(groups) > groupLimit {
		groups = groups[:groupLimit]
	}

	return groups, nil
}

func extractABExperimentFields(config sql.NullString, strategySnapshot sql.NullString) (experimentID string, variant string, compareWinner *bool) {
	for _, source := range []sql.NullString{config, strategySnapshot} {
		if !source.Valid {
			continue
		}

		var decoded map[string]interface{}
		if err := json.Unmarshal([]byte(source.String), &decoded); err != nil {
			continue
		}

		if experimentID != "" {
			continue
		}

		metadata := extractMetadataMap(decoded)
		abExperiment := asMap(metadata["ab_experiment"])
		if abExperiment == nil {
			continue
		}

		experimentID = strings.TrimSpace(asString(abExperiment["experiment_id"]))
		variant = strings.TrimSpace(asString(abExperiment["variant"]))

		if compare := asMap(metadata["ab_compare_summary"]); compare != nil {
			if winner, ok := asBool(compare["winner"]); ok {
				compareWinner = &winner
			}
		}
	}

	return experimentID, variant, compareWinner
}

func extractMetadataMap(source map[string]interface{}) map[string]interface{} {
	if source == nil {
		return nil
	}

	if metadata := asMap(source["metadata"]); metadata != nil {
		return metadata
	}

	if request := asMap(source["request"]); request != nil {
		if metadata := asMap(request["metadata"]); metadata != nil {
			return metadata
		}
	}

	return nil
}

func asMap(value interface{}) map[string]interface{} {
	if mapped, ok := value.(map[string]interface{}); ok {
		return mapped
	}
	return nil
}

func asString(value interface{}) string {
	if value == nil {
		return ""
	}
	if typed, ok := value.(string); ok {
		return typed
	}
	return fmt.Sprintf("%v", value)
}

func asBool(value interface{}) (bool, bool) {
	if value == nil {
		return false, false
	}
	if typed, ok := value.(bool); ok {
		return typed, true
	}
	if typed, ok := value.(string); ok {
		trimmed := strings.TrimSpace(strings.ToLower(typed))
		if trimmed == "true" || trimmed == "1" || trimmed == "yes" {
			return true, true
		}
		if trimmed == "false" || trimmed == "0" || trimmed == "no" {
			return false, true
		}
	}
	return false, false
}

// GetRunsByStrategyID returns completed backtest runs for a given strategy,
// scoped to the owning user, newest first. Limit defaults to 10.
func (r *BacktestRepository) GetRunsByStrategyID(userID int, strategyID int, limit int) ([]models.BacktestRun, error) {
	if limit <= 0 {
		limit = 10
	}
	query := `
		SELECT id, user_id, strategy_id, strategy_version_id, run_id, COALESCE(status, ''), start_date, end_date,
		       num_pairs, total_markets, COALESCE(resolution, ''), COALESCE(total_trades, 0), COALESCE(profitable_trades, 0), COALESCE(losing_trades, 0),
		       win_rate, COALESCE(total_pnl, 0), COALESCE(total_pnl_usd, 0), sharpe_ratio, sortino_ratio, calmar_ratio,
		       max_drawdown, profit_factor, COALESCE(starting_balance, 0), ending_balance, max_balance, min_balance,
		       COALESCE(error_message, ''), started_at, completed_at, duration_seconds,
		       created_at
		FROM backtest_runs
		WHERE user_id = ?
		  AND strategy_id = ?
		  AND COALESCE(status, '') IN ('completed', 'finished', 'done', 'success', 'succeeded')
		ORDER BY created_at DESC
		LIMIT ?
	`
	rows, err := r.db.Query(r.bindQuery(query), userID, strategyID, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query strategy backtest runs: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close strategy backtest run rows: %v", closeErr)
		}
	}()

	var runs []models.BacktestRun
	for rows.Next() {
		run := models.BacktestRun{}
		if err := rows.Scan(
			&run.ID, &run.UserID, &run.StrategyID, &run.StrategyVersionID,
			&run.RunID, &run.Status, &run.StartDate, &run.EndDate,
			&run.NumPairs, &run.TotalMarkets, &run.Resolution,
			&run.TotalTrades, &run.ProfitableTrades, &run.LosingTrades,
			&run.WinRate, &run.TotalPnL, &run.TotalPnLUSD,
			&run.SharpeRatio, &run.SortinoRatio, &run.CalmarRatio,
			&run.MaxDrawdown, &run.ProfitFactor,
			&run.StartingBalance, &run.EndingBalance, &run.MaxBalance, &run.MinBalance,
			&run.ErrorMessage, &run.StartedAt, &run.CompletedAt, &run.DurationSeconds,
			&run.CreatedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan strategy backtest run: %w", err)
		}
		runs = append(runs, run)
	}
	if err = rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating strategy backtest runs: %w", err)
	}
	return runs, nil
}

func (r *BacktestRepository) CountActiveRunsByUserID(userID int) (int, error) {
	ctx, cancel := context.WithTimeout(context.Background(), defaultQueryTimeout)
	defer cancel()
	return r.CountActiveRunsByUserIDContext(ctx, userID)
}

// CountActiveRunsByUserIDContext counts a user's in-flight runs (admission
// check on every backtest submission), honouring cancellation.
func (r *BacktestRepository) CountActiveRunsByUserIDContext(ctx context.Context, userID int) (int, error) {
	query := `
			SELECT COUNT(*)
			FROM backtest_runs
			WHERE user_id = ?
			  AND COALESCE(status, '') IN (
				'pending', 'queued', 'created', 'scheduled',
				'running', 'in_progress', 'processing', 'active',
				'paused', 'retry', 'retrying'
			  )
		`

	var count int
	if err := r.db.QueryRowContext(ctx, r.bindQuery(query), userID).Scan(&count); err != nil {
		return 0, fmt.Errorf("failed to count active backtest runs: %w", err)
	}
	return count, nil
}
