package repository

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"hash/fnv"
	"log"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

type BacktestRepository struct {
	db             *sql.DB
	admissionLocks sync.Map
}

func NewBacktestRepository(db *sql.DB) *BacktestRepository {
	return &BacktestRepository{db: db}
}

var errAdvisoryLockUnsupported = errors.New("postgres advisory locks unsupported")

func backtestAdmissionLockKey(userID int) int64 {
	hasher := fnv.New64a()
	_, _ = fmt.Fprintf(hasher, "backtest-admission:%d", userID)
	return int64(hasher.Sum64())
}

func isAdvisoryLockUnsupportedError(err error) bool {
	if err == nil {
		return false
	}
	lower := strings.ToLower(err.Error())
	if strings.Contains(lower, "function pg_try_advisory_lock") && strings.Contains(lower, "does not exist") {
		return true
	}
	return strings.Contains(lower, "no such function") && strings.Contains(lower, "pg_try_advisory_lock")
}

func (r *BacktestRepository) withInProcessAdmissionLock(userID int, fn func() error) error {
	lockValue, _ := r.admissionLocks.LoadOrStore(userID, &sync.Mutex{})
	lock := lockValue.(*sync.Mutex)
	lock.Lock()
	defer lock.Unlock()
	return fn()
}

func (r *BacktestRepository) withPostgresAdvisoryAdmissionLock(ctx context.Context, userID int, fn func() error) error {
	if r == nil || r.db == nil {
		return errAdvisoryLockUnsupported
	}

	conn, err := r.db.Conn(ctx)
	if err != nil {
		return fmt.Errorf("failed to acquire database connection for admission lock: %w", err)
	}
	defer func() { _ = conn.Close() }()

	lockKey := backtestAdmissionLockKey(userID)
	for {
		var acquired bool
		if err := conn.QueryRowContext(ctx, `SELECT pg_try_advisory_lock($1)`, lockKey).Scan(&acquired); err != nil {
			if isAdvisoryLockUnsupportedError(err) {
				return errAdvisoryLockUnsupported
			}
			return fmt.Errorf("failed to acquire postgres advisory lock for user %d: %w", userID, err)
		}
		if acquired {
			break
		}

		select {
		case <-ctx.Done():
			return fmt.Errorf("timed out waiting for admission lock for user %d: %w", userID, ctx.Err())
		case <-time.After(50 * time.Millisecond):
		}
	}

	defer func() {
		if _, unlockErr := conn.ExecContext(context.Background(), `SELECT pg_advisory_unlock($1)`, lockKey); unlockErr != nil {
			log.Printf("failed to release postgres advisory lock for user %d: %v", userID, unlockErr)
		}
	}()

	return fn()
}

// WithUserAdmissionLock serializes admission checks per user.
//
// Behavior:
// - PostgreSQL: uses pg advisory locks (cross-replica safe).
// - Other engines/test setups: falls back to in-process mutex lock.
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

	if err := r.withPostgresAdvisoryAdmissionLock(ctx, userID, fn); err != nil {
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

func (r *BacktestRepository) GetRunOwnerID(runID string) (*int, error) {
	query := "SELECT user_id FROM backtest_runs WHERE run_id = $1 LIMIT 1"

	var owner sql.NullInt64
	err := r.db.QueryRow(query, runID).Scan(&owner)
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
		argNum++
	}

	query += " ORDER BY timestamp"
	if filter.Limit > 0 {
		query += fmt.Sprintf(" LIMIT $%d OFFSET $%d", argNum, argNum+1)
		args = append(args, filter.Limit, filter.Skip)
	}

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
		SELECT id, user_id, strategy_id, strategy_version_id, run_id, COALESCE(status, ''), start_date, end_date,
		       num_pairs, total_markets, COALESCE(resolution, ''), COALESCE(total_trades, 0), COALESCE(profitable_trades, 0), COALESCE(losing_trades, 0),
		       win_rate, COALESCE(total_pnl, 0), COALESCE(total_pnl_usd, 0), sharpe_ratio, sortino_ratio, calmar_ratio,
		       max_drawdown, profit_factor, COALESCE(starting_balance, 0), ending_balance, max_balance, min_balance,
		       COALESCE(error_message, ''), started_at, completed_at, duration_seconds,
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

func (r *BacktestRepository) CountRunsByUserID(userID int) (int, error) {
	var count int
	if err := r.db.QueryRow(`SELECT COUNT(*) FROM backtest_runs WHERE user_id = $1`, userID).Scan(&count); err != nil {
		return 0, fmt.Errorf("failed to count backtest runs: %w", err)
	}
	return count, nil
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
		WHERE user_id = $1
		ORDER BY created_at DESC
		LIMIT $2
	`

	rows, err := r.db.Query(query, userID, runScanLimit)
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
		WHERE user_id = $1
		  AND strategy_id = $2
		  AND LOWER(COALESCE(status, '')) IN ('completed', 'finished', 'done', 'success', 'succeeded')
		ORDER BY created_at DESC
		LIMIT $3
	`
	rows, err := r.db.Query(query, userID, strategyID, limit)
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
	query := `
		SELECT COUNT(*)
		FROM backtest_runs
		WHERE user_id = $1
		  AND LOWER(COALESCE(status, '')) IN (
			'pending', 'queued', 'created', 'scheduled',
			'running', 'in_progress', 'processing', 'active',
			'paused', 'retry', 'retrying'
		  )
	`

	var count int
	if err := r.db.QueryRow(query, userID).Scan(&count); err != nil {
		return 0, fmt.Errorf("failed to count active backtest runs: %w", err)
	}
	return count, nil
}
