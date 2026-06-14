package repository

import (
	"database/sql"
	"fmt"
	"log"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

var backtestRunSyncFreshInsertTotal atomic.Uint64
var backtestRunSyncRerunUpdateTotal atomic.Uint64

func BacktestRunSyncOutcomeCounters() map[string]uint64 {
	return map[string]uint64{
		"fresh_inserts_total": backtestRunSyncFreshInsertTotal.Load(),
		"rerun_updates_total": backtestRunSyncRerunUpdateTotal.Load(),
	}
}

func classifyBacktestRunUpsertOutcome(rowsAffected int64) string {
	if rowsAffected == 1 {
		return "insert"
	}
	// MySQL upsert rowsAffected semantics:
	// 2 => existing row changed, 0 => existing row unchanged.
	// Both are rerun updates for run_id visibility.
	return "update"
}

func recordBacktestRunUpsertOutcome(runID string, rowsAffected int64) {
	outcome := classifyBacktestRunUpsertOutcome(rowsAffected)
	if outcome == "insert" {
		backtestRunSyncFreshInsertTotal.Add(1)
	} else {
		backtestRunSyncRerunUpdateTotal.Add(1)
	}
	log.Printf(
		"backtest_sync_upsert outcome=%s run_id=%s rows_affected=%d fresh_inserts_total=%d rerun_updates_total=%d",
		outcome,
		runID,
		rowsAffected,
		backtestRunSyncFreshInsertTotal.Load(),
		backtestRunSyncRerunUpdateTotal.Load(),
	)
}

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
	StrategyID      sql.NullInt64
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
	SharpeRatio     sql.NullFloat64
	MaxDrawdown     sql.NullFloat64
}

type BacktestTradeSyncPayload struct {
	TradeID        string
	Market1        string
	Market2        string
	EntryTimestamp *time.Time
	EntryPrice1    float64
	EntryPrice2    float64
	EntryZScore    float64
	Side1          string
	Side2          string
	Size1          float64
	Size2          float64
	ExitTimestamp  *time.Time
	ExitPrice1     *float64
	ExitPrice2     *float64
	ExitZScore     *float64
	PnL            *float64
	PnLPct         *float64
	DurationHours  *float64
	HedgeRatio     float64
	TransactionFee float64
	Slippage       float64
}

type BacktestPositionSyncPayload struct {
	PositionID     string
	Market1        string
	Market2        string
	Status         string
	EntryTimestamp *time.Time
	CloseTimestamp *time.Time
	EntryPrice1    float64
	EntryPrice2    float64
	EntryZScore    float64
	CurrentPrice1  *float64
	CurrentPrice2  *float64
	CurrentZScore  *float64
	Size1          float64
	Size2          float64
	Side1          string
	Side2          string
	HedgeRatio     float64
	UnrealizedPnL  *float64
	RealizedPnL    *float64
}

type BacktestCandleSyncPayload struct {
	Market      string
	Timestamp   *time.Time
	Resolution  string
	OpenPrice   float64
	HighPrice   float64
	LowPrice    float64
	ClosePrice  float64
	Volume      float64
	TradesCount *int
}

type BacktestSyncHealth struct {
	RunID         string     `json:"run_id"`
	Status        string     `json:"status"`
	CreatedAt     *time.Time `json:"created_at,omitempty"`
	Trades        int        `json:"trades"`
	Positions     int        `json:"positions"`
	Candles       int        `json:"candles"`
	RunAgeSec     int64      `json:"run_age_seconds"`
	SyncLagSec    int64      `json:"sync_lag_seconds"`
	QualityIssues int        `json:"quality_issues"`
}

type BacktestSyncRepository struct {
	db       *sql.DB
	runLocks sync.Map
}

func NewBacktestSyncRepository(db *sql.DB) *BacktestSyncRepository {
	return &BacktestSyncRepository{db: db}
}

func (r *BacktestSyncRepository) withRunLock(runID string, fn func() error) error {
	if strings.TrimSpace(runID) == "" {
		return fn()
	}

	lockValue, _ := r.runLocks.LoadOrStore(runID, &sync.Mutex{})
	lock := lockValue.(*sync.Mutex)
	lock.Lock()
	defer lock.Unlock()

	return fn()
}

func (r *BacktestSyncRepository) DB() *sql.DB {
	if r == nil {
		return nil
	}
	return r.db
}

func nullableStringValue(value sql.NullString) interface{} {
	if value.Valid {
		return value.String
	}
	return nil
}

func nullableInt64Value(value sql.NullInt64) interface{} {
	if value.Valid {
		return value.Int64
	}
	return nil
}

func nullableFloat64Value(value sql.NullFloat64) interface{} {
	if value.Valid {
		return value.Float64
	}
	return nil
}

func (r *BacktestSyncRepository) UpsertBacktestRun(payload BacktestRunSyncPayload) error {
	return r.withRunLock(payload.RunID, func() error {
		if payload.RunID == "" {
			return fmt.Errorf("run_id is required")
		}
		if payload.StartDate == "" {
			return fmt.Errorf("start_date is required")
		}
		if payload.EndDate == "" {
			return fmt.Errorf("end_date is required")
		}

		upsertQuery := `
		INSERT INTO backtest_runs (
			run_id, status, created_at, started_at, completed_at, duration_seconds,
			start_date, end_date, num_pairs, total_markets, resolution, config,
			total_trades, profitable_trades, losing_trades, win_rate,
			total_pnl, total_pnl_usd, sharpe_ratio, max_drawdown,
			error_message, user_id, strategy_id
		) VALUES (
			?, ?, ?, ?, ?, ?,
			?, ?, ?, ?, ?, ?,
			?, ?, ?, ?,
			?, ?, ?, ?,
			?, ?, ?
		)
		ON DUPLICATE KEY UPDATE
			status = VALUES(status),
			user_id = VALUES(user_id),
			start_date = VALUES(start_date),
			end_date = VALUES(end_date),
			num_pairs = VALUES(num_pairs),
			total_markets = VALUES(total_markets),
			resolution = VALUES(resolution),
			config = VALUES(config),
			started_at = COALESCE(VALUES(started_at), started_at),
			completed_at = COALESCE(VALUES(completed_at), completed_at),
			duration_seconds = COALESCE(VALUES(duration_seconds), duration_seconds),
			error_message = COALESCE(VALUES(error_message), error_message),
			total_trades = COALESCE(VALUES(total_trades), total_trades),
			profitable_trades = COALESCE(VALUES(profitable_trades), profitable_trades),
			losing_trades = COALESCE(VALUES(losing_trades), losing_trades),
			win_rate = COALESCE(VALUES(win_rate), win_rate),
			total_pnl = COALESCE(VALUES(total_pnl), total_pnl),
			total_pnl_usd = COALESCE(VALUES(total_pnl_usd), total_pnl_usd),
			sharpe_ratio = COALESCE(VALUES(sharpe_ratio), sharpe_ratio),
			max_drawdown = COALESCE(VALUES(max_drawdown), max_drawdown),
			strategy_id = COALESCE(VALUES(strategy_id), strategy_id)
	`

		execResult, err := r.db.Exec(
			upsertQuery,
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
			nullableStringValue(payload.Resolution),
			nullableStringValue(payload.Config),
			nullableInt64Value(payload.TotalTrades),
			nullableInt64Value(payload.WinningTrades),
			nullableInt64Value(payload.LosingTrades),
			nullableFloat64Value(payload.WinRate),
			nullableFloat64Value(payload.TotalPnL),
			nullableFloat64Value(payload.TotalPnLUSD),
			nullableFloat64Value(payload.SharpeRatio),
			nullableFloat64Value(payload.MaxDrawdown),
			nullableStringValue(payload.ErrorMessage),
			payload.UserID,
			nullableInt64Value(payload.StrategyID),
		)
		if err != nil {
			return fmt.Errorf("failed to upsert backtest run: %w", err)
		}

		if rowsAffected, rowsErr := execResult.RowsAffected(); rowsErr == nil {
			recordBacktestRunUpsertOutcome(payload.RunID, rowsAffected)
		} else {
			log.Printf("backtest_sync_upsert outcome=unknown run_id=%s rows_affected_error=%v", payload.RunID, rowsErr)
		}

		return nil
	})
}

func (r *BacktestSyncRepository) UpsertBacktestTrades(runID string, items []BacktestTradeSyncPayload) error {
	return r.withRunLock(runID, func() error {
		if len(items) == 0 {
			return nil
		}
		runPK, fkColumn, err := r.resolveRunAndFKColumn("backtest_trades", runID)
		if err != nil {
			return err
		}

		for _, item := range items {
			if strings.TrimSpace(item.TradeID) == "" {
				continue
			}
			if item.EntryTimestamp == nil {
				now := time.Now().UTC()
				item.EntryTimestamp = &now
			}
			if item.Market1 == "" {
				item.Market1 = "UNKNOWN"
			}
			if item.Market2 == "" {
				item.Market2 = "UNKNOWN"
			}
			if item.Side1 == "" {
				item.Side1 = "BUY"
			}
			if item.Side2 == "" {
				item.Side2 = "SELL"
			}

			upsertQuery := fmt.Sprintf(`
			INSERT INTO backtest_trades (
				%s, trade_id, market_1, market_2, entry_timestamp,
				entry_price_1, entry_price_2, entry_z_score,
				side_1, side_2, size_1, size_2,
				exit_timestamp, exit_price_1, exit_price_2, exit_z_score,
				pnl, pnl_pct, duration_hours, hedge_ratio, transaction_fee, slippage
			) VALUES (
				?, ?, ?, ?, ?,
				?, ?, ?,
				?, ?, ?, ?,
				?, ?, ?, ?,
				?, ?, ?, ?, ?, ?
			)
			ON DUPLICATE KEY UPDATE
				%s = VALUES(%s),
				market_1 = VALUES(market_1),
				market_2 = VALUES(market_2),
				entry_timestamp = VALUES(entry_timestamp),
				entry_price_1 = VALUES(entry_price_1),
				entry_price_2 = VALUES(entry_price_2),
				entry_z_score = VALUES(entry_z_score),
				side_1 = VALUES(side_1),
				side_2 = VALUES(side_2),
				size_1 = VALUES(size_1),
				size_2 = VALUES(size_2),
				exit_timestamp = VALUES(exit_timestamp),
				exit_price_1 = VALUES(exit_price_1),
				exit_price_2 = VALUES(exit_price_2),
				exit_z_score = VALUES(exit_z_score),
				pnl = VALUES(pnl),
				pnl_pct = VALUES(pnl_pct),
				duration_hours = VALUES(duration_hours),
				hedge_ratio = VALUES(hedge_ratio),
				transaction_fee = VALUES(transaction_fee),
				slippage = VALUES(slippage)
		`, fkColumn, fkColumn, fkColumn)

			if _, err := r.db.Exec(
				upsertQuery,
				runPK,
				item.TradeID,
				item.Market1,
				item.Market2,
				item.EntryTimestamp,
				item.EntryPrice1,
				item.EntryPrice2,
				item.EntryZScore,
				item.Side1,
				item.Side2,
				item.Size1,
				item.Size2,
				item.ExitTimestamp,
				item.ExitPrice1,
				item.ExitPrice2,
				item.ExitZScore,
				item.PnL,
				item.PnLPct,
				item.DurationHours,
				item.HedgeRatio,
				item.TransactionFee,
				item.Slippage,
			); err != nil {
				return fmt.Errorf("failed to insert backtest trade: %w", err)
			}
		}

		return nil
	})
}

func (r *BacktestSyncRepository) UpsertBacktestPositions(runID string, items []BacktestPositionSyncPayload) error {
	return r.withRunLock(runID, func() error {
		if len(items) == 0 {
			return nil
		}
		runPK, fkColumn, err := r.resolveRunAndFKColumn("backtest_positions", runID)
		if err != nil {
			return err
		}

		for _, item := range items {
			if strings.TrimSpace(item.PositionID) == "" {
				continue
			}
			if item.EntryTimestamp == nil {
				now := time.Now().UTC()
				item.EntryTimestamp = &now
			}
			if item.Market1 == "" {
				item.Market1 = "UNKNOWN"
			}
			if item.Market2 == "" {
				item.Market2 = "UNKNOWN"
			}
			if item.Status == "" {
				item.Status = "OPEN"
			}
			if item.Side1 == "" {
				item.Side1 = "BUY"
			}
			if item.Side2 == "" {
				item.Side2 = "SELL"
			}

			upsertQuery := fmt.Sprintf(`
			INSERT INTO backtest_positions (
				%s, position_id, market_1, market_2, status,
				entry_timestamp, close_timestamp,
				entry_price_1, entry_price_2, entry_z_score,
				current_price_1, current_price_2, current_z_score,
				size_1, size_2, side_1, side_2, hedge_ratio,
				unrealized_pnl, realized_pnl
			) VALUES (
				?, ?, ?, ?, ?,
				?, ?,
				?, ?, ?,
				?, ?, ?,
				?, ?, ?, ?, ?,
				?, ?
			)
			ON DUPLICATE KEY UPDATE
				%s = VALUES(%s),
				market_1 = VALUES(market_1),
				market_2 = VALUES(market_2),
				status = VALUES(status),
				entry_timestamp = VALUES(entry_timestamp),
				close_timestamp = VALUES(close_timestamp),
				entry_price_1 = VALUES(entry_price_1),
				entry_price_2 = VALUES(entry_price_2),
				entry_z_score = VALUES(entry_z_score),
				current_price_1 = VALUES(current_price_1),
				current_price_2 = VALUES(current_price_2),
				current_z_score = VALUES(current_z_score),
				size_1 = VALUES(size_1),
				size_2 = VALUES(size_2),
				side_1 = VALUES(side_1),
				side_2 = VALUES(side_2),
				hedge_ratio = VALUES(hedge_ratio),
				unrealized_pnl = VALUES(unrealized_pnl),
				realized_pnl = VALUES(realized_pnl)
		`, fkColumn, fkColumn, fkColumn)

			if _, err := r.db.Exec(
				upsertQuery,
				runPK,
				item.PositionID,
				item.Market1,
				item.Market2,
				item.Status,
				item.EntryTimestamp,
				item.CloseTimestamp,
				item.EntryPrice1,
				item.EntryPrice2,
				item.EntryZScore,
				item.CurrentPrice1,
				item.CurrentPrice2,
				item.CurrentZScore,
				item.Size1,
				item.Size2,
				item.Side1,
				item.Side2,
				item.HedgeRatio,
				item.UnrealizedPnL,
				item.RealizedPnL,
			); err != nil {
				return fmt.Errorf("failed to insert backtest position: %w", err)
			}
		}

		return nil
	})
}

func (r *BacktestSyncRepository) UpsertBacktestCandles(runID string, items []BacktestCandleSyncPayload) error {
	return r.withRunLock(runID, func() error {
		if len(items) == 0 {
			return nil
		}
		runPK, fkColumn, err := r.resolveRunAndFKColumn("backtest_candles", runID)
		if err != nil {
			return err
		}

		for _, item := range items {
			if item.Timestamp == nil || strings.TrimSpace(item.Market) == "" {
				continue
			}
			if item.Resolution == "" {
				item.Resolution = "1HOUR"
			}

			upsertQuery := fmt.Sprintf(`
			INSERT INTO backtest_candles (
				%s, market, timestamp, resolution, open_price,
				high_price, low_price, close_price, volume, trades_count, created_at
			) VALUES (
				?, ?, ?, ?, ?,
				?, ?, ?, ?, ?, ?
			)
			ON DUPLICATE KEY UPDATE
				open_price = VALUES(open_price),
				high_price = VALUES(high_price),
				low_price = VALUES(low_price),
				close_price = VALUES(close_price),
				volume = VALUES(volume),
				trades_count = VALUES(trades_count)
		`, fkColumn)
			if _, err := r.db.Exec(
				upsertQuery,
				runPK,
				item.Market,
				item.Timestamp,
				item.Resolution,
				item.OpenPrice,
				item.HighPrice,
				item.LowPrice,
				item.ClosePrice,
				item.Volume,
				item.TradesCount,
				time.Now().UTC(),
			); err != nil {
				return fmt.Errorf("failed to insert backtest candle: %w", err)
			}
		}

		return nil
	})
}

func (r *BacktestSyncRepository) resolveRunAndFKColumn(tableName, runID string) (int, string, error) {
	runPK, err := r.getRunPrimaryKey(runID)
	if err != nil {
		return 0, "", err
	}
	fkColumn, err := r.detectFKColumn(tableName)
	if err != nil {
		return 0, "", err
	}
	return runPK, fkColumn, nil
}

func (r *BacktestSyncRepository) getRunPrimaryKey(runID string) (int, error) {
	if strings.TrimSpace(runID) == "" {
		return 0, fmt.Errorf("run_id is required")
	}
	var id int
	err := r.db.QueryRow(`SELECT id FROM backtest_runs WHERE run_id = ? LIMIT 1`, runID).Scan(&id)
	if err != nil {
		if err == sql.ErrNoRows {
			return 0, fmt.Errorf("backtest run not found for run_id=%s", runID)
		}
		return 0, fmt.Errorf("failed to resolve run id: %w", err)
	}
	return id, nil
}

func (r *BacktestSyncRepository) detectFKColumn(tableName string) (_ string, err error) {
	rows, err := r.db.Query(fmt.Sprintf(`SELECT * FROM %s LIMIT 0`, tableName))
	if err != nil {
		return "", fmt.Errorf("failed to inspect table %s: %w", tableName, err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil && err == nil {
			err = fmt.Errorf("failed to close inspection rows for %s: %w", tableName, closeErr)
		}
	}()

	columns, err := rows.Columns()
	if err != nil {
		return "", fmt.Errorf("failed to inspect columns for %s: %w", tableName, err)
	}
	if err := rows.Err(); err != nil {
		return "", fmt.Errorf("failed to inspect rows for %s: %w", tableName, err)
	}
	for _, column := range columns {
		if strings.EqualFold(column, "run_id_fk") {
			return "run_id_fk", nil
		}
	}
	for _, column := range columns {
		if strings.EqualFold(column, "run_id") {
			return "run_id", nil
		}
	}
	return "", fmt.Errorf("table %s has no run foreign-key column (run_id_fk/run_id)", tableName)
}

func (r *BacktestSyncRepository) GetSyncHealthByRun(userID int, runID string, limit int) ([]BacktestSyncHealth, error) {
	if userID <= 0 {
		return nil, fmt.Errorf("invalid user id")
	}
	if limit <= 0 {
		limit = 20
	}

	query := `
		SELECT id, run_id, COALESCE(status, ''), created_at
		FROM backtest_runs
		WHERE user_id = ?
	`
	args := []interface{}{userID}
	if strings.TrimSpace(runID) != "" {
		query += " AND run_id = ?"
		args = append(args, runID)
	}
	query += " ORDER BY created_at DESC LIMIT ?"
	args = append(args, limit)

	rows, err := r.db.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query backtest runs for sync health: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close sync health rows: %v", closeErr)
		}
	}()

	health := make([]BacktestSyncHealth, 0)
	for rows.Next() {
		var (
			runPK     int
			runIDVal  string
			status    string
			createdAt sql.NullTime
		)
		if err := rows.Scan(&runPK, &runIDVal, &status, &createdAt); err != nil {
			return nil, fmt.Errorf("failed to scan sync health run row: %w", err)
		}

		_ = runPK
		trades, err := r.countRowsForRunByRunID("backtest_trades", runIDVal, userID)
		if err != nil {
			trades = 0
		}
		positions, err := r.countRowsForRunByRunID("backtest_positions", runIDVal, userID)
		if err != nil {
			positions = 0
		}
		candles, err := r.countRowsForRunByRunID("backtest_candles", runIDVal, userID)
		if err != nil {
			candles = 0
		}
		qualityIssues, err := r.countDataQualityIssuesByRunID(runIDVal, userID)
		if err != nil {
			qualityIssues = 0
		}
		lastSyncedAt, err := r.getLastSyncedAtByRunID(runIDVal, userID)
		if err != nil {
			lastSyncedAt = nil
		}

		item := BacktestSyncHealth{
			RunID:         runIDVal,
			Status:        status,
			Trades:        trades,
			Positions:     positions,
			Candles:       candles,
			QualityIssues: qualityIssues,
		}
		if createdAt.Valid {
			created := createdAt.Time.UTC()
			item.CreatedAt = &created
			item.RunAgeSec = int64(time.Since(created).Seconds())
			if item.RunAgeSec < 0 {
				item.RunAgeSec = 0
			}
		}
		if lastSyncedAt != nil {
			lag := int64(time.Since(lastSyncedAt.UTC()).Seconds())
			if lag < 0 {
				lag = 0
			}
			item.SyncLagSec = lag
		} else if item.CreatedAt != nil {
			item.SyncLagSec = item.RunAgeSec
		}
		health = append(health, item)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("failed iterating sync health runs: %w", err)
	}

	return health, nil
}

func (r *BacktestSyncRepository) countRowsForRunByRunID(tableName string, runID string, userID int) (int, error) {
	columns := []string{"run_id_fk", "run_id"}
	var lastErr error
	for _, fkColumn := range columns {
		query := fmt.Sprintf(`
			SELECT COUNT(*)
			FROM %s c
			JOIN backtest_runs r ON c.%s = r.id
			WHERE r.run_id = ? AND r.user_id = ?
		`, tableName, fkColumn)
		var count int
		err := r.db.QueryRow(query, runID, userID).Scan(&count)
		if err == nil {
			return count, nil
		}
		lower := strings.ToLower(err.Error())
		if strings.Contains(lower, "no such column") || strings.Contains(lower, "undefined column") {
			lastErr = err
			continue
		}
		return 0, fmt.Errorf("failed counting rows for %s by run_id: %w", tableName, err)
	}
	if lastErr != nil {
		return 0, fmt.Errorf("failed counting rows for %s by run_id: %w", tableName, lastErr)
	}
	return 0, fmt.Errorf("failed counting rows for %s by run_id", tableName)
}

func (r *BacktestSyncRepository) countDataQualityIssuesByRunID(runID string, userID int) (int, error) {
	queries := []string{
		`SELECT COUNT(*) FROM backtest_trades c JOIN backtest_runs r ON c.run_id_fk = r.id WHERE r.run_id = ? AND r.user_id = ? AND (c.market_1 = 'UNKNOWN' OR c.market_2 = 'UNKNOWN')`,
		`SELECT COUNT(*) FROM backtest_positions c JOIN backtest_runs r ON c.run_id_fk = r.id WHERE r.run_id = ? AND r.user_id = ? AND (c.market_1 = 'UNKNOWN' OR c.market_2 = 'UNKNOWN')`,
		`SELECT COUNT(*) FROM backtest_candles c JOIN backtest_runs r ON c.run_id_fk = r.id WHERE r.run_id = ? AND r.user_id = ? AND c.market = 'UNKNOWN'`,
	}
	total := 0
	for _, query := range queries {
		var count int
		err := r.db.QueryRow(query, runID, userID).Scan(&count)
		if err != nil {
			lower := strings.ToLower(err.Error())
			if strings.Contains(lower, "no such column") || strings.Contains(lower, "undefined column") {
				continue
			}
			return 0, err
		}
		total += count
	}
	return total, nil
}

func (r *BacktestSyncRepository) getLastSyncedAtByRunID(runID string, userID int) (*time.Time, error) {
	candidates := []string{
		`SELECT MAX(c.entry_timestamp) FROM backtest_trades c JOIN backtest_runs r ON c.run_id_fk = r.id WHERE r.run_id = ? AND r.user_id = ?`,
		`SELECT MAX(c.entry_timestamp) FROM backtest_positions c JOIN backtest_runs r ON c.run_id_fk = r.id WHERE r.run_id = ? AND r.user_id = ?`,
		`SELECT MAX(c.timestamp) FROM backtest_candles c JOIN backtest_runs r ON c.run_id_fk = r.id WHERE r.run_id = ? AND r.user_id = ?`,
	}
	var latest time.Time
	found := false
	for _, query := range candidates {
		var ts sql.NullTime
		err := r.db.QueryRow(query, runID, userID).Scan(&ts)
		if err != nil {
			lower := strings.ToLower(err.Error())
			if strings.Contains(lower, "no such column") || strings.Contains(lower, "undefined column") {
				continue
			}
			return nil, err
		}
		if ts.Valid {
			current := ts.Time.UTC()
			if !found || current.After(latest) {
				latest = current
				found = true
			}
		}
	}
	if !found {
		return nil, nil
	}
	return &latest, nil
}
