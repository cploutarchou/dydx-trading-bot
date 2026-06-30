package repository

import (
	"database/sql"
	"fmt"
	"log"
	"os"
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

func recordBacktestRunUpsertOutcome(runID string, inserted bool) {
	outcome := "update"
	rowsAffected := int64(0)
	if inserted {
		outcome = "insert"
		rowsAffected = 1
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
	RunID                 string     `json:"run_id"`
	Status                string     `json:"status"`
	CreatedAt             *time.Time `json:"created_at,omitempty"`
	Trades                int        `json:"trades"`                  // Delegated artifact-backed trade availability (primary)
	BackendMirroredTrades int        `json:"backend_mirrored_trades"` // Legacy backend DB mirror count (debug only)
	Positions             int        `json:"positions"`
	Candles               int        `json:"candles"`
	RunAgeSec             int64      `json:"run_age_seconds"`
	SyncLagSec            int64      `json:"sync_lag_seconds"`
	QualityIssues         int        `json:"quality_issues"`
}

type BacktestSyncRepository struct {
	db       *sql.DB
	dbDriver string
	runLocks sync.Map
}

func NewBacktestSyncRepository(db *sql.DB) *BacktestSyncRepository {
	driver := os.Getenv("DB_TYPE")
	if driver == "" {
		driver = os.Getenv("DB_DRIVER")
	}
	if driver == "" {
		driver = "postgres"
	}

	return &BacktestSyncRepository{db: db, dbDriver: driver}
}

func NewBacktestSyncRepositoryWithDriver(db *sql.DB, driver string) *BacktestSyncRepository {
	if strings.TrimSpace(driver) == "" {
		driver = "postgres"
	}
	return &BacktestSyncRepository{db: db, dbDriver: driver}
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

func (r *BacktestSyncRepository) bindQuery(query string) string {
	if r == nil {
		return query
	}
	if !strings.Contains(strings.ToLower(r.dbDriver), "postgres") {
		return query
	}
	var builder strings.Builder
	builder.Grow(len(query) + 16)
	argIndex := 1
	for i := 0; i < len(query); i++ {
		if query[i] == '?' {
			builder.WriteString(fmt.Sprintf("$%d", argIndex))
			argIndex++
			continue
		}
		builder.WriteByte(query[i])
	}
	return builder.String()
}

func (r *BacktestSyncRepository) runExists(runID string) (bool, error) {
	if strings.TrimSpace(runID) == "" {
		return false, fmt.Errorf("run_id is required")
	}
	var id int
	err := r.db.QueryRow(r.bindQuery(`SELECT id FROM backtest_runs WHERE run_id = ? LIMIT 1`), runID).Scan(&id)
	if err != nil {
		if err == sql.ErrNoRows {
			return false, nil
		}
		return false, fmt.Errorf("failed to check existing backtest run: %w", err)
	}
	return true, nil
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

		existing, err := r.runExists(payload.RunID)
		if err != nil {
			return err
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
		ON CONFLICT (run_id) DO UPDATE SET
			status = EXCLUDED.status,
			user_id = EXCLUDED.user_id,
			start_date = EXCLUDED.start_date,
			end_date = EXCLUDED.end_date,
			num_pairs = EXCLUDED.num_pairs,
			total_markets = EXCLUDED.total_markets,
			resolution = EXCLUDED.resolution,
			config = EXCLUDED.config,
			started_at = COALESCE(EXCLUDED.started_at, backtest_runs.started_at),
			completed_at = COALESCE(EXCLUDED.completed_at, backtest_runs.completed_at),
			duration_seconds = COALESCE(EXCLUDED.duration_seconds, backtest_runs.duration_seconds),
			error_message = COALESCE(EXCLUDED.error_message, backtest_runs.error_message),
			total_trades = COALESCE(EXCLUDED.total_trades, backtest_runs.total_trades),
			profitable_trades = COALESCE(EXCLUDED.profitable_trades, backtest_runs.profitable_trades),
			losing_trades = COALESCE(EXCLUDED.losing_trades, backtest_runs.losing_trades),
			win_rate = COALESCE(EXCLUDED.win_rate, backtest_runs.win_rate),
			total_pnl = COALESCE(EXCLUDED.total_pnl, backtest_runs.total_pnl),
			total_pnl_usd = COALESCE(EXCLUDED.total_pnl_usd, backtest_runs.total_pnl_usd),
			sharpe_ratio = COALESCE(EXCLUDED.sharpe_ratio, backtest_runs.sharpe_ratio),
			max_drawdown = COALESCE(EXCLUDED.max_drawdown, backtest_runs.max_drawdown),
			strategy_id = COALESCE(EXCLUDED.strategy_id, backtest_runs.strategy_id)
	`

		upsertArgs := []interface{}{
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
		}

		if _, err := r.db.Exec(r.bindQuery(upsertQuery), upsertArgs...); err != nil {
			return fmt.Errorf("failed to upsert backtest run: %w", err)
		}

		recordBacktestRunUpsertOutcome(payload.RunID, !existing)

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
			ON CONFLICT (trade_id) DO UPDATE SET
				%s = EXCLUDED.%s,
				market_1 = EXCLUDED.market_1,
				market_2 = EXCLUDED.market_2,
				entry_timestamp = EXCLUDED.entry_timestamp,
				entry_price_1 = EXCLUDED.entry_price_1,
				entry_price_2 = EXCLUDED.entry_price_2,
				entry_z_score = EXCLUDED.entry_z_score,
				side_1 = EXCLUDED.side_1,
				side_2 = EXCLUDED.side_2,
				size_1 = EXCLUDED.size_1,
				size_2 = EXCLUDED.size_2,
				exit_timestamp = EXCLUDED.exit_timestamp,
				exit_price_1 = EXCLUDED.exit_price_1,
				exit_price_2 = EXCLUDED.exit_price_2,
				exit_z_score = EXCLUDED.exit_z_score,
				pnl = EXCLUDED.pnl,
				pnl_pct = EXCLUDED.pnl_pct,
				duration_hours = EXCLUDED.duration_hours,
				hedge_ratio = EXCLUDED.hedge_ratio,
				transaction_fee = EXCLUDED.transaction_fee,
				slippage = EXCLUDED.slippage
		`, fkColumn, fkColumn, fkColumn)

			if _, err := r.db.Exec(
				r.bindQuery(upsertQuery),
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
			ON CONFLICT (position_id) DO UPDATE SET
				%s = EXCLUDED.%s,
				market_1 = EXCLUDED.market_1,
				market_2 = EXCLUDED.market_2,
				status = EXCLUDED.status,
				entry_timestamp = EXCLUDED.entry_timestamp,
				close_timestamp = EXCLUDED.close_timestamp,
				entry_price_1 = EXCLUDED.entry_price_1,
				entry_price_2 = EXCLUDED.entry_price_2,
				entry_z_score = EXCLUDED.entry_z_score,
				current_price_1 = EXCLUDED.current_price_1,
				current_price_2 = EXCLUDED.current_price_2,
				current_z_score = EXCLUDED.current_z_score,
				size_1 = EXCLUDED.size_1,
				size_2 = EXCLUDED.size_2,
				side_1 = EXCLUDED.side_1,
				side_2 = EXCLUDED.side_2,
				hedge_ratio = EXCLUDED.hedge_ratio,
				unrealized_pnl = EXCLUDED.unrealized_pnl,
				realized_pnl = EXCLUDED.realized_pnl
		`, fkColumn, fkColumn, fkColumn)

			if _, err := r.db.Exec(
				r.bindQuery(upsertQuery),
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
			ON CONFLICT (%s, market, timestamp, resolution) DO UPDATE SET
				open_price = EXCLUDED.open_price,
				high_price = EXCLUDED.high_price,
				low_price = EXCLUDED.low_price,
				close_price = EXCLUDED.close_price,
				volume = EXCLUDED.volume,
				trades_count = EXCLUDED.trades_count
		`, fkColumn, fkColumn)
			if _, err := r.db.Exec(
				r.bindQuery(upsertQuery),
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
	err := r.db.QueryRow(r.bindQuery(`SELECT id FROM backtest_runs WHERE run_id = ? LIMIT 1`), runID).Scan(&id)
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

	rows, err := r.db.Query(r.bindQuery(query), args...)
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
		backendMirroredTrades, err := r.countRowsForRunByRunID("backtest_trades", runIDVal, userID)
		if err != nil {
			backendMirroredTrades = 0
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

		// Get delegated trades count from backtest_runs table which contains the total_trades from bot
		// This represents artifact-backed trade availability
		delegatedTrades, err := r.getDelegatedTradesCountByRunID(runIDVal, userID)
		if err != nil {
			delegatedTrades = 0
		}

		item := BacktestSyncHealth{
			RunID:                 runIDVal,
			Status:                status,
			Trades:                delegatedTrades,       // Primary: delegated artifact-backed
			BackendMirroredTrades: backendMirroredTrades, // Debug: legacy backend DB mirror
			Positions:             positions,
			Candles:               candles,
			QualityIssues:         qualityIssues,
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
		err := r.db.QueryRow(r.bindQuery(query), runID, userID).Scan(&count)
		if err == nil {
			return count, nil
		}
		lower := strings.ToLower(err.Error())
		if strings.Contains(lower, "no such column") || strings.Contains(lower, "undefined column") || strings.Contains(lower, "does not exist") {
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
		err := r.db.QueryRow(r.bindQuery(query), runID, userID).Scan(&count)
		if err != nil {
			lower := strings.ToLower(err.Error())
			if strings.Contains(lower, "no such column") || strings.Contains(lower, "undefined column") || strings.Contains(lower, "does not exist") {
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
		err := r.db.QueryRow(r.bindQuery(query), runID, userID).Scan(&ts)
		if err != nil {
			lower := strings.ToLower(err.Error())
			if strings.Contains(lower, "no such column") || strings.Contains(lower, "undefined column") || strings.Contains(lower, "does not exist") {
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

func (r *BacktestSyncRepository) getDelegatedTradesCountByRunID(runID string, userID int) (int, error) {
	// Get total_trades from backtest_runs table which stores the delegated bot API response
	query := `SELECT COALESCE(total_trades, 0) FROM backtest_runs WHERE run_id = ? AND user_id = ? LIMIT 1`
	var count int
	err := r.db.QueryRow(r.bindQuery(query), runID, userID).Scan(&count)
	if err != nil {
		if err == sql.ErrNoRows {
			return 0, nil
		}
		return 0, fmt.Errorf("failed to get delegated trades count: %w", err)
	}
	return count, nil
}
