package repository

import (
	"database/sql"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// StrategyRepository handles strategy database operations.
// Schema is fully managed by MariaDB migrations — no runtime ALTER TABLE patching.
type StrategyRepository struct {
	db *sql.DB
}

// NewStrategyRepository creates a new strategy repository
func NewStrategyRepository(db *sql.DB) *StrategyRepository {
	return &StrategyRepository{db: db}
}

// ============ BacktestStrategy Operations ============

// CreateStrategy creates a new backtest strategy
func (r *StrategyRepository) CreateStrategy(strategy *models.BacktestStrategy) error {
	if strings.TrimSpace(strategy.RuntimeStrategy) == "" {
		strategy.RuntimeStrategy = "cointegration"
	}
	if strings.TrimSpace(strategy.RuntimeNetwork) == "" {
		strategy.RuntimeNetwork = "testnet"
	}
	if strategy.RuntimeSubaccount < 0 {
		strategy.RuntimeSubaccount = 0
	}
	if strings.TrimSpace(strategy.PairSelectionMode) == "" {
		strategy.PairSelectionMode = "liquidity"
	}
	if strings.TrimSpace(strategy.SelectedMarkets) == "" {
		strategy.SelectedMarkets = "[]"
	}

	query := `
		INSERT INTO backtest_strategies (
			user_id, name, description, category, is_public, is_default, runtime_strategy, runtime_network, runtime_subaccount, pair_selection_mode,
			selected_markets, zscore_threshold, stats_window, max_half_life, usd_per_trade,
			usd_min_collateral, close_at_zscore_cross, find_cointegrated_pairs,
			manage_exits, place_trades, abort_all_positions, max_positions,
			max_drawdown_pct, stop_loss_pct, take_profit_pct, trailing_stop_pct,
			rebalance_interval_hours, position_timeout_hours, transaction_fee,
			slippage, starting_balance, candle_resolution, max_history_days,
			benchmark_symbol, risk_free_rate, initial_amount, created_at, updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	now := time.Now()
	result, err := r.db.Exec(
		query,
		strategy.UserID, strategy.Name, strategy.Description, strategy.Category,
		strategy.IsPublic, strategy.IsDefault, strategy.RuntimeStrategy, strategy.RuntimeNetwork, strategy.RuntimeSubaccount, strategy.PairSelectionMode, strategy.SelectedMarkets, strategy.ZscoreThreshold,
		strategy.StatsWindow, strategy.MaxHalfLife, strategy.UsdPerTrade,
		strategy.UsdMinCollateral, strategy.CloseAtZscoreCross, strategy.FindCointegratedPairs,
		strategy.ManageExits, strategy.PlaceTrades, strategy.AbortAllPositions,
		strategy.MaxPositions, strategy.MaxDrawdownPct, strategy.StopLossPct,
		strategy.TakeProfitPct, strategy.TrailingStopPct, strategy.RebalanceIntervalHours,
		strategy.PositionTimeoutHours, strategy.TransactionFee, strategy.Slippage,
		strategy.StartingBalance, strategy.CandleResolution, strategy.MaxHistoryDays,
		strategy.BenchmarkSymbol, strategy.RiskFreeRate, strategy.InitialAmount,
		now, now,
	)

	if err != nil {
		return fmt.Errorf("failed to create strategy: %w", err)
	}

	lastID, err := result.LastInsertId()
	if err != nil {
		return fmt.Errorf("failed to get last insert ID: %w", err)
	}

	strategy.ID = int(lastID)
	strategy.CreatedAt = now
	strategy.UpdatedAt = now

	return nil
}

// GetStrategyByID retrieves a strategy by ID
func (r *StrategyRepository) GetStrategyByID(id int) (*models.BacktestStrategy, error) {

	query := `
		SELECT id, user_id, name, description, category, is_public, is_default, runtime_strategy, pair_selection_mode,
		       runtime_network, runtime_subaccount, selected_markets,
		       zscore_threshold, stats_window, max_half_life, usd_per_trade,
		       usd_min_collateral, close_at_zscore_cross, find_cointegrated_pairs,
		       manage_exits, place_trades, abort_all_positions, max_positions,
		       max_drawdown_pct, stop_loss_pct, take_profit_pct, trailing_stop_pct,
		       rebalance_interval_hours, position_timeout_hours, transaction_fee,
		       slippage, starting_balance, candle_resolution, max_history_days,
		       benchmark_symbol, risk_free_rate, initial_amount, usage_count,
		       last_used_at, deleted_at, created_at, updated_at
		FROM backtest_strategies
		WHERE id = ?
		LIMIT 1
	`

	strategy := &models.BacktestStrategy{}
	err := r.db.QueryRow(query, id).Scan(
		&strategy.ID, &strategy.UserID, &strategy.Name, &strategy.Description,
		&strategy.Category, &strategy.IsPublic, &strategy.IsDefault, &strategy.RuntimeStrategy, &strategy.PairSelectionMode,
		&strategy.RuntimeNetwork, &strategy.RuntimeSubaccount, &strategy.SelectedMarkets,
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

	query := `
		SELECT id, user_id, name, description, category, is_public, is_default, runtime_strategy, pair_selection_mode,
		       runtime_network, runtime_subaccount, selected_markets,
		       zscore_threshold, stats_window, max_half_life, usd_per_trade,
		       usd_min_collateral, close_at_zscore_cross, find_cointegrated_pairs,
		       manage_exits, place_trades, abort_all_positions, max_positions,
		       max_drawdown_pct, stop_loss_pct, take_profit_pct, trailing_stop_pct,
		       rebalance_interval_hours, position_timeout_hours, transaction_fee,
		       slippage, starting_balance, candle_resolution, max_history_days,
		       benchmark_symbol, risk_free_rate, initial_amount, usage_count,
		       last_used_at, deleted_at, created_at, updated_at
		FROM backtest_strategies
		WHERE user_id = ? AND deleted_at IS NULL
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
			&strategy.Category, &strategy.IsPublic, &strategy.IsDefault, &strategy.RuntimeStrategy, &strategy.PairSelectionMode,
			&strategy.RuntimeNetwork, &strategy.RuntimeSubaccount, &strategy.SelectedMarkets,
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

func (r *StrategyRepository) CountStrategiesByUser(userID int) (int, error) {
	var count int
	err := r.db.QueryRow(
		`SELECT COUNT(*) FROM backtest_strategies WHERE user_id = ? AND deleted_at IS NULL`,
		userID,
	).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to count strategies: %w", err)
	}
	return count, nil
}

// UpdateStrategy updates an existing strategy
func (r *StrategyRepository) UpdateStrategy(strategy *models.BacktestStrategy) error {
	if strings.TrimSpace(strategy.RuntimeStrategy) == "" {
		strategy.RuntimeStrategy = "cointegration"
	}
	if strings.TrimSpace(strategy.RuntimeNetwork) == "" {
		strategy.RuntimeNetwork = "testnet"
	}
	if strategy.RuntimeSubaccount < 0 {
		strategy.RuntimeSubaccount = 0
	}
	if strings.TrimSpace(strategy.PairSelectionMode) == "" {
		strategy.PairSelectionMode = "liquidity"
	}
	if strings.TrimSpace(strategy.SelectedMarkets) == "" {
		strategy.SelectedMarkets = "[]"
	}

	query := `
		UPDATE backtest_strategies
		SET name = ?, description = ?, category = ?, is_public = ?,
		    runtime_strategy = ?, runtime_network = ?, runtime_subaccount = ?, pair_selection_mode = ?, selected_markets = ?, zscore_threshold = ?, stats_window = ?, max_half_life = ?,
		    usd_per_trade = ?, usd_min_collateral = ?, close_at_zscore_cross = ?,
		    find_cointegrated_pairs = ?, manage_exits = ?, place_trades = ?,
		    abort_all_positions = ?, max_positions = ?, max_drawdown_pct = ?,
		    stop_loss_pct = ?, take_profit_pct = ?, trailing_stop_pct = ?,
		    rebalance_interval_hours = ?, position_timeout_hours = ?,
		    transaction_fee = ?, slippage = ?, starting_balance = ?,
		    candle_resolution = ?, max_history_days = ?, benchmark_symbol = ?,
		    risk_free_rate = ?, initial_amount = ?, usage_count = ?, last_used_at = ?,
		    updated_at = ?
		WHERE id = ?
	`

	result, err := r.db.Exec(
		query,
		strategy.Name, strategy.Description, strategy.Category, strategy.IsPublic,
		strategy.RuntimeStrategy, strategy.RuntimeNetwork, strategy.RuntimeSubaccount, strategy.PairSelectionMode, strategy.SelectedMarkets, strategy.ZscoreThreshold, strategy.StatsWindow, strategy.MaxHalfLife,
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
	query := `UPDATE backtest_strategies SET deleted_at = ? WHERE id = ?`

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

	query := `
		SELECT id, strategy_id, is_running, last_run_at, next_run_at, state, created_at, updated_at
		FROM strategy_execution_states
		WHERE strategy_id = ?
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

	query := `
		INSERT INTO strategy_execution_states (strategy_id, is_running, created_at, updated_at)
		VALUES (?, ?, ?, ?)
	`

	now := time.Now()
	var err error
	var result sql.Result
	for attempt := 0; attempt < 5; attempt++ {
		result, err = r.db.Exec(query, state.StrategyID, state.IsRunning, now, now)
		if err == nil {
			lastID, _ := result.LastInsertId()
			state.ID = int(lastID)
			state.CreatedAt = now
			state.UpdatedAt = now
			if err == nil {
				return nil
			}
			if !isRetryableSchemaChangeError(err) {
				return fmt.Errorf("failed to create execution state: %w", err)
			}
			time.Sleep(time.Duration(attempt+1) * 50 * time.Millisecond)
		}
	}

	return fmt.Errorf("failed to create execution state: %w", err)
}

// UpdateExecutionState updates execution state
func (r *StrategyRepository) UpdateExecutionState(state *models.StrategyExecutionState) error {

	query := `
		UPDATE strategy_execution_states
		SET is_running = ?, last_run_at = ?, next_run_at = ?, state = ?, updated_at = ?
		WHERE id = ?
	`

	var (
		result sql.Result
		err    error
	)
	for attempt := 0; attempt < 5; attempt++ {
		result, err = r.db.Exec(
			query,
			state.IsRunning, state.LastRunAt, state.NextRunAt, state.State, time.Now(), state.ID,
		)
		if err == nil {
			break
		}
		if !isRetryableSchemaChangeError(err) {
			return fmt.Errorf("failed to update execution state: %w", err)
		}
		time.Sleep(time.Duration(attempt+1) * 50 * time.Millisecond)
	}

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

func isRetryableSchemaChangeError(err error) bool {
	if err == nil {
		return false
	}
	message := strings.ToLower(err.Error())
	return strings.Contains(message, "could not obtain lock on relation") ||
		strings.Contains(message, "deadlock detected")
}

// ============ StrategyVersionHistory Operations ============

// CreateVersionHistory creates a new version history record
func (r *StrategyRepository) CreateVersionHistory(history *models.StrategyVersionHistory) error {
	configSnapshot := history.StrategyData
	if !configSnapshot.Valid || strings.TrimSpace(configSnapshot.String) == "" {
		configSnapshot = sql.NullString{
			String: "{}",
			Valid:  true,
		}
	}

	query := `
		INSERT INTO strategy_version_history (
			strategy_id, created_by_user_id, version_number, change_description, config_snapshot, created_at
		)
		VALUES (?, ?, ?, ?, ?, ?)
	`

	now := time.Now()
	result, err := r.db.Exec(
		query,
		history.StrategyID, history.CreatedByUserID, history.Version,
		history.ChangeLog, configSnapshot, now,
	)

	if err != nil {
		return fmt.Errorf("failed to create version history: %w", err)
	}

	lastID, err := result.LastInsertId()
	if err != nil {
		return fmt.Errorf("failed to get last insert ID: %w", err)
	}

	history.ID = int(lastID)
	history.CreatedAt = now

	if err != nil {
		return fmt.Errorf("failed to create version history: %w", err)
	}

	history.StrategyData = configSnapshot
	history.UpdatedAt = history.CreatedAt

	return nil
}

// GetVersionHistoryByStrategy retrieves version history for a strategy
func (r *StrategyRepository) GetVersionHistoryByStrategy(strategyID int) ([]models.StrategyVersionHistory, error) {
	query := `
		SELECT id, strategy_id, COALESCE(created_by_user_id, 0), version_number,
		       config_snapshot, COALESCE(change_description, ''), created_at, created_at AS updated_at
		FROM strategy_version_history
		WHERE strategy_id = ?
		ORDER BY version_number DESC
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
			&h.StrategyData, &h.ChangeLog, &h.CreatedAt, &h.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan version history: %w", err)
		}
		history = append(history, h)
	}

	return history, rows.Err()
}
