package repository

import (
	"database/sql"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// StrategyRepository handles strategy database operations
type StrategyRepository struct {
	db                      *sql.DB
	strategySchemaMu        sync.Mutex
	strategySchemaSet       bool
	executionStateSchemaMu  sync.Mutex
	executionStateSchemaSet bool
}

// NewStrategyRepository creates a new strategy repository
func NewStrategyRepository(db *sql.DB) *StrategyRepository {
	return &StrategyRepository{db: db}
}

func (r *StrategyRepository) ensureStrategySchema() error {
	r.strategySchemaMu.Lock()
	defer r.strategySchemaMu.Unlock()

	if r.strategySchemaSet {
		return nil
	}

	rows, err := r.db.Query(`SELECT * FROM backtest_strategies LIMIT 0`)
	if err != nil {
		return fmt.Errorf("failed to inspect backtest strategy schema: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close strategy schema rows: %v", closeErr)
		}
	}()

	columnNames, err := rows.Columns()
	if err != nil {
		return fmt.Errorf("failed to read backtest strategy columns: %w", err)
	}
	if err := rows.Err(); err != nil {
		return fmt.Errorf("failed to inspect backtest strategy schema rows: %w", err)
	}

	columns := make(map[string]struct{}, len(columnNames))
	for _, name := range columnNames {
		columns[strings.ToLower(strings.TrimSpace(name))] = struct{}{}
	}

	if _, exists := columns["runtime_strategy"]; !exists {
		if _, err := r.db.Exec(`ALTER TABLE backtest_strategies ADD COLUMN runtime_strategy TEXT NOT NULL DEFAULT 'cointegration'`); err != nil {
			return fmt.Errorf("failed to add backtest strategy runtime_strategy column: %w", err)
		}
	}

	r.strategySchemaSet = true
	return nil
}

func (r *StrategyRepository) ensureExecutionStateSchema() error {
	r.executionStateSchemaMu.Lock()
	defer r.executionStateSchemaMu.Unlock()

	if r.executionStateSchemaSet {
		return nil
	}

	rows, err := r.db.Query(`SELECT * FROM strategy_execution_states LIMIT 0`)
	if err != nil {
		return fmt.Errorf("failed to inspect strategy execution state schema: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close execution state schema rows: %v", closeErr)
		}
	}()

	columnNames, err := rows.Columns()
	if err != nil {
		return fmt.Errorf("failed to read strategy execution state columns: %w", err)
	}
	if err := rows.Err(); err != nil {
		return fmt.Errorf("failed to inspect strategy execution state schema rows: %w", err)
	}

	columns := make(map[string]struct{}, len(columnNames))
	for _, name := range columnNames {
		columns[strings.ToLower(strings.TrimSpace(name))] = struct{}{}
	}

	type columnRepair struct {
		name        string
		addSQL      string
		backfillSQL string
	}

	repairs := []columnRepair{
		{
			name:   "is_running",
			addSQL: `ALTER TABLE strategy_execution_states ADD COLUMN is_running BOOLEAN DEFAULT 0`,
			backfillSQL: `UPDATE strategy_execution_states
				SET is_running = CASE
					WHEN is_running IS NOT NULL THEN is_running
					WHEN enabled IS NOT NULL THEN enabled
					WHEN LOWER(COALESCE(status, '')) IN ('running', 'starting') THEN 1
					ELSE 0
				END`,
		},
		{
			name:   "last_run_at",
			addSQL: `ALTER TABLE strategy_execution_states ADD COLUMN last_run_at TIMESTAMP NULL`,
			backfillSQL: `UPDATE strategy_execution_states
				SET last_run_at = COALESCE(last_run_at, last_started, last_trade_at)`,
		},
		{
			name:        "next_run_at",
			addSQL:      `ALTER TABLE strategy_execution_states ADD COLUMN next_run_at TIMESTAMP NULL`,
			backfillSQL: ``,
		},
		{
			name:   "state",
			addSQL: `ALTER TABLE strategy_execution_states ADD COLUMN state TEXT`,
			backfillSQL: `UPDATE strategy_execution_states
				SET state = COALESCE(
					NULLIF(state, ''),
					NULLIF(status, ''),
					CASE
						WHEN COALESCE(is_running, enabled, 0) = 1 THEN 'running'
						ELSE 'stopped'
					END
				)`,
		},
	}

	for _, repair := range repairs {
		if _, exists := columns[repair.name]; exists {
			continue
		}
		if _, err := r.db.Exec(repair.addSQL); err != nil {
			return fmt.Errorf("failed to add strategy execution state column %s: %w", repair.name, err)
		}
		if strings.TrimSpace(repair.backfillSQL) != "" {
			if _, err := r.db.Exec(repair.backfillSQL); err != nil {
				return fmt.Errorf("failed to backfill strategy execution state column %s: %w", repair.name, err)
			}
		}
	}

	if _, err := r.db.Exec(`UPDATE strategy_execution_states SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)`); err != nil {
		return fmt.Errorf("failed to backfill strategy execution state created_at: %w", err)
	}

	if _, err := r.db.Exec(`UPDATE strategy_execution_states SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)`); err != nil {
		return fmt.Errorf("failed to backfill strategy execution state updated_at: %w", err)
	}

	r.executionStateSchemaSet = true
	return nil
}

// ============ BacktestStrategy Operations ============

// CreateStrategy creates a new backtest strategy
func (r *StrategyRepository) CreateStrategy(strategy *models.BacktestStrategy) error {
	if err := r.ensureStrategySchema(); err != nil {
		return err
	}
	if strings.TrimSpace(strategy.RuntimeStrategy) == "" {
		strategy.RuntimeStrategy = "cointegration"
	}

	query := `
		INSERT INTO backtest_strategies (
			user_id, name, description, category, is_public, is_default, runtime_strategy,
			zscore_threshold, stats_window, max_half_life, usd_per_trade,
			usd_min_collateral, close_at_zscore_cross, find_cointegrated_pairs,
			manage_exits, place_trades, abort_all_positions, max_positions,
			max_drawdown_pct, stop_loss_pct, take_profit_pct, trailing_stop_pct,
			rebalance_interval_hours, position_timeout_hours, transaction_fee,
			slippage, starting_balance, candle_resolution, max_history_days,
			benchmark_symbol, risk_free_rate, initial_amount, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32, $33, $34)
		RETURNING id, created_at, updated_at
	`

	now := time.Now()
	err := r.db.QueryRow(
		query,
		strategy.UserID, strategy.Name, strategy.Description, strategy.Category,
		strategy.IsPublic, strategy.IsDefault, strategy.RuntimeStrategy, strategy.ZscoreThreshold,
		strategy.StatsWindow, strategy.MaxHalfLife, strategy.UsdPerTrade,
		strategy.UsdMinCollateral, strategy.CloseAtZscoreCross, strategy.FindCointegratedPairs,
		strategy.ManageExits, strategy.PlaceTrades, strategy.AbortAllPositions,
		strategy.MaxPositions, strategy.MaxDrawdownPct, strategy.StopLossPct,
		strategy.TakeProfitPct, strategy.TrailingStopPct, strategy.RebalanceIntervalHours,
		strategy.PositionTimeoutHours, strategy.TransactionFee, strategy.Slippage,
		strategy.StartingBalance, strategy.CandleResolution, strategy.MaxHistoryDays,
		strategy.BenchmarkSymbol, strategy.RiskFreeRate, strategy.InitialAmount,
		now, now,
	).Scan(&strategy.ID, &strategy.CreatedAt, &strategy.UpdatedAt)

	if err != nil {
		return fmt.Errorf("failed to create strategy: %w", err)
	}

	return nil
}

// GetStrategyByID retrieves a strategy by ID
func (r *StrategyRepository) GetStrategyByID(id int) (*models.BacktestStrategy, error) {
	if err := r.ensureStrategySchema(); err != nil {
		return nil, err
	}

	query := `
		SELECT id, user_id, name, description, category, is_public, is_default, runtime_strategy,
		       zscore_threshold, stats_window, max_half_life, usd_per_trade,
		       usd_min_collateral, close_at_zscore_cross, find_cointegrated_pairs,
		       manage_exits, place_trades, abort_all_positions, max_positions,
		       max_drawdown_pct, stop_loss_pct, take_profit_pct, trailing_stop_pct,
		       rebalance_interval_hours, position_timeout_hours, transaction_fee,
		       slippage, starting_balance, candle_resolution, max_history_days,
		       benchmark_symbol, risk_free_rate, initial_amount, usage_count,
		       last_used_at, deleted_at, created_at, updated_at
		FROM backtest_strategies
		WHERE id = $1
		LIMIT 1
	`

	strategy := &models.BacktestStrategy{}
	err := r.db.QueryRow(query, id).Scan(
		&strategy.ID, &strategy.UserID, &strategy.Name, &strategy.Description,
		&strategy.Category, &strategy.IsPublic, &strategy.IsDefault, &strategy.RuntimeStrategy,
		&strategy.ZscoreThreshold, &strategy.StatsWindow, &strategy.MaxHalfLife,
		&strategy.UsdPerTrade, &strategy.UsdMinCollateral, &strategy.CloseAtZscoreCross,
		&strategy.FindCointegratedPairs, &strategy.ManageExits, &strategy.PlaceTrades,
		&strategy.AbortAllPositions, &strategy.MaxPositions, &strategy.MaxDrawdownPct,
		&strategy.StopLossPct, &strategy.TakeProfitPct, &strategy.TrailingStopPct,
		&strategy.RebalanceIntervalHours, &strategy.PositionTimeoutHours,
		&strategy.TransactionFee, &strategy.Slippage, &strategy.StartingBalance,
		&strategy.CandleResolution, &strategy.MaxHistoryDays, &strategy.BenchmarkSymbol,
		&strategy.RiskFreeRate, &strategy.InitialAmount, &strategy.UsageCount,
		&strategy.LastUsedAt, &strategy.DeletedAt, &strategy.CreatedAt, &strategy.UpdatedAt,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get strategy: %w", err)
	}

	return strategy, nil
}

// GetStrategiesByUser retrieves all strategies for a user
func (r *StrategyRepository) GetStrategiesByUser(userID int) ([]models.BacktestStrategy, error) {
	if err := r.ensureStrategySchema(); err != nil {
		return nil, err
	}

	query := `
		SELECT id, user_id, name, description, category, is_public, is_default, runtime_strategy,
		       zscore_threshold, stats_window, max_half_life, usd_per_trade,
		       usd_min_collateral, close_at_zscore_cross, find_cointegrated_pairs,
		       manage_exits, place_trades, abort_all_positions, max_positions,
		       max_drawdown_pct, stop_loss_pct, take_profit_pct, trailing_stop_pct,
		       rebalance_interval_hours, position_timeout_hours, transaction_fee,
		       slippage, starting_balance, candle_resolution, max_history_days,
		       benchmark_symbol, risk_free_rate, initial_amount, usage_count,
		       last_used_at, deleted_at, created_at, updated_at
		FROM backtest_strategies
		WHERE user_id = $1 AND deleted_at IS NULL
		ORDER BY created_at DESC
	`

	rows, err := r.db.Query(query, userID)
	if err != nil {
		return nil, fmt.Errorf("failed to query strategies: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close strategy rows: %v", closeErr)
		}
	}()

	var strategies []models.BacktestStrategy
	for rows.Next() {
		strategy := models.BacktestStrategy{}
		err := rows.Scan(
			&strategy.ID, &strategy.UserID, &strategy.Name, &strategy.Description,
			&strategy.Category, &strategy.IsPublic, &strategy.IsDefault, &strategy.RuntimeStrategy,
			&strategy.ZscoreThreshold, &strategy.StatsWindow, &strategy.MaxHalfLife,
			&strategy.UsdPerTrade, &strategy.UsdMinCollateral, &strategy.CloseAtZscoreCross,
			&strategy.FindCointegratedPairs, &strategy.ManageExits, &strategy.PlaceTrades,
			&strategy.AbortAllPositions, &strategy.MaxPositions, &strategy.MaxDrawdownPct,
			&strategy.StopLossPct, &strategy.TakeProfitPct, &strategy.TrailingStopPct,
			&strategy.RebalanceIntervalHours, &strategy.PositionTimeoutHours,
			&strategy.TransactionFee, &strategy.Slippage, &strategy.StartingBalance,
			&strategy.CandleResolution, &strategy.MaxHistoryDays, &strategy.BenchmarkSymbol,
			&strategy.RiskFreeRate, &strategy.InitialAmount, &strategy.UsageCount,
			&strategy.LastUsedAt, &strategy.DeletedAt, &strategy.CreatedAt, &strategy.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan strategy: %w", err)
		}
		strategies = append(strategies, strategy)
	}

	return strategies, rows.Err()
}

// UpdateStrategy updates an existing strategy
func (r *StrategyRepository) UpdateStrategy(strategy *models.BacktestStrategy) error {
	if err := r.ensureStrategySchema(); err != nil {
		return err
	}
	if strings.TrimSpace(strategy.RuntimeStrategy) == "" {
		strategy.RuntimeStrategy = "cointegration"
	}

	query := `
		UPDATE backtest_strategies
		SET name = $1, description = $2, category = $3, is_public = $4,
		    runtime_strategy = $5, zscore_threshold = $6, stats_window = $7, max_half_life = $8,
		    usd_per_trade = $9, usd_min_collateral = $10, close_at_zscore_cross = $11,
		    find_cointegrated_pairs = $12, manage_exits = $13, place_trades = $14,
		    abort_all_positions = $15, max_positions = $16, max_drawdown_pct = $17,
		    stop_loss_pct = $18, take_profit_pct = $19, trailing_stop_pct = $20,
		    rebalance_interval_hours = $21, position_timeout_hours = $22,
		    transaction_fee = $23, slippage = $24, starting_balance = $25,
		    candle_resolution = $26, max_history_days = $27, benchmark_symbol = $28,
		    risk_free_rate = $29, initial_amount = $30, usage_count = $31, last_used_at = $32,
		    updated_at = $33
		WHERE id = $34
	`

	result, err := r.db.Exec(
		query,
		strategy.Name, strategy.Description, strategy.Category, strategy.IsPublic,
		strategy.RuntimeStrategy, strategy.ZscoreThreshold, strategy.StatsWindow, strategy.MaxHalfLife,
		strategy.UsdPerTrade, strategy.UsdMinCollateral, strategy.CloseAtZscoreCross,
		strategy.FindCointegratedPairs, strategy.ManageExits, strategy.PlaceTrades,
		strategy.AbortAllPositions, strategy.MaxPositions, strategy.MaxDrawdownPct,
		strategy.StopLossPct, strategy.TakeProfitPct, strategy.TrailingStopPct,
		strategy.RebalanceIntervalHours, strategy.PositionTimeoutHours,
		strategy.TransactionFee, strategy.Slippage, strategy.StartingBalance,
		strategy.CandleResolution, strategy.MaxHistoryDays, strategy.BenchmarkSymbol,
		strategy.RiskFreeRate, strategy.InitialAmount, strategy.UsageCount, strategy.LastUsedAt,
		time.Now(), strategy.ID,
	)

	if err != nil {
		return fmt.Errorf("failed to update strategy: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("strategy not found")
	}

	return nil
}

// DeleteStrategy marks a strategy as deleted
func (r *StrategyRepository) DeleteStrategy(id int) error {
	query := `UPDATE backtest_strategies SET deleted_at = $1 WHERE id = $2`

	result, err := r.db.Exec(query, time.Now(), id)
	if err != nil {
		return fmt.Errorf("failed to delete strategy: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("strategy not found")
	}

	return nil
}

// ============ StrategyExecutionState Operations ============

// GetExecutionState retrieves execution state for a strategy
func (r *StrategyRepository) GetExecutionState(strategyID int) (*models.StrategyExecutionState, error) {
	if err := r.ensureExecutionStateSchema(); err != nil {
		return nil, err
	}

	query := `
		SELECT id, strategy_id, is_running, last_run_at, next_run_at, state, created_at, updated_at
		FROM strategy_execution_states
		WHERE strategy_id = $1
		LIMIT 1
	`

	state := &models.StrategyExecutionState{}
	err := r.db.QueryRow(query, strategyID).Scan(
		&state.ID, &state.StrategyID, &state.IsRunning, &state.LastRunAt,
		&state.NextRunAt, &state.State, &state.CreatedAt, &state.UpdatedAt,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get execution state: %w", err)
	}

	return state, nil
}

// CreateExecutionState creates a new execution state
func (r *StrategyRepository) CreateExecutionState(state *models.StrategyExecutionState) error {
	if err := r.ensureExecutionStateSchema(); err != nil {
		return err
	}

	query := `
		INSERT INTO strategy_execution_states (strategy_id, is_running, created_at, updated_at)
		VALUES ($1, $2, $3, $4)
		RETURNING id, created_at, updated_at
	`

	now := time.Now()
	err := r.db.QueryRow(query, state.StrategyID, state.IsRunning, now, now).Scan(
		&state.ID, &state.CreatedAt, &state.UpdatedAt,
	)

	if err != nil {
		return fmt.Errorf("failed to create execution state: %w", err)
	}

	return nil
}

// UpdateExecutionState updates execution state
func (r *StrategyRepository) UpdateExecutionState(state *models.StrategyExecutionState) error {
	if err := r.ensureExecutionStateSchema(); err != nil {
		return err
	}

	query := `
		UPDATE strategy_execution_states
		SET is_running = $1, last_run_at = $2, next_run_at = $3, state = $4, updated_at = $5
		WHERE id = $6
	`

	result, err := r.db.Exec(
		query,
		state.IsRunning, state.LastRunAt, state.NextRunAt, state.State, time.Now(), state.ID,
	)

	if err != nil {
		return fmt.Errorf("failed to update execution state: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("execution state not found")
	}

	return nil
}

// ============ StrategyVersionHistory Operations ============

// CreateVersionHistory creates a new version history record
func (r *StrategyRepository) CreateVersionHistory(history *models.StrategyVersionHistory) error {
	query := `
		INSERT INTO strategy_version_history (strategy_id, created_by_user_id, version, change_log, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING id, created_at, updated_at
	`

	now := time.Now()
	err := r.db.QueryRow(
		query,
		history.StrategyID, history.CreatedByUserID, history.Version,
		history.ChangeLog, now, now,
	).Scan(&history.ID, &history.CreatedAt, &history.UpdatedAt)

	if err != nil {
		return fmt.Errorf("failed to create version history: %w", err)
	}

	return nil
}

// GetVersionHistoryByStrategy retrieves version history for a strategy
func (r *StrategyRepository) GetVersionHistoryByStrategy(strategyID int) ([]models.StrategyVersionHistory, error) {
	query := `
		SELECT id, strategy_id, created_by_user_id, version, change_log, created_at, updated_at
		FROM strategy_version_history
		WHERE strategy_id = $1
		ORDER BY version DESC
	`

	rows, err := r.db.Query(query, strategyID)
	if err != nil {
		return nil, fmt.Errorf("failed to query version history: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close strategy version history rows: %v", closeErr)
		}
	}()

	var history []models.StrategyVersionHistory
	for rows.Next() {
		h := models.StrategyVersionHistory{}
		err := rows.Scan(
			&h.ID, &h.StrategyID, &h.CreatedByUserID, &h.Version,
			&h.ChangeLog, &h.CreatedAt, &h.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan version history: %w", err)
		}
		history = append(history, h)
	}

	return history, rows.Err()
}
