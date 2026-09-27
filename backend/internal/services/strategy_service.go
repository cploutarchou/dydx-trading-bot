package services

import (
	"database/sql"
	"fmt"
	"log"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

// StrategyService manages backtest strategy operations
type StrategyService struct {
	repo *repository.StrategyRepository
	// inTx is set on a copy bound to a transaction by WithTx.
	inTx bool
}

// NewStrategyService creates a new strategy service
func NewStrategyService(repo *repository.StrategyRepository) *StrategyService {
	return &StrategyService{repo: repo}
}

// WithTx returns a copy of the service whose repository executes within tx.
func (s *StrategyService) WithTx(tx *sql.Tx) *StrategyService {
	return &StrategyService{repo: s.repo.WithTx(tx), inTx: true}
}

// ============ BacktestStrategy Operations ============

// CreateStrategy creates a new backtest strategy
func (s *StrategyService) CreateStrategy(userID int, name, description, category string, isPublic, isDefault bool) (*models.BacktestStrategy, error) {
	if name == "" {
		return nil, fmt.Errorf("strategy name is required")
	}

	strategy := newStrategyWithDefaults(userID, name, description, category, isPublic, isDefault)
	if err := s.repo.CreateStrategy(strategy); err != nil {
		return nil, fmt.Errorf("failed to create strategy: %w", err)
	}

	log.Printf("✅ Created strategy: %s (ID: %d)", name, strategy.ID)
	return strategy, nil
}

// newStrategyWithDefaults is a new strategy before the operator changes it.
func newStrategyWithDefaults(userID int, name, description, category string, isPublic, isDefault bool) *models.BacktestStrategy {
	return &models.BacktestStrategy{
		UserID:                userID,
		Name:                  name,
		Description:           description,
		Category:              category,
		IsPublic:              isPublic,
		IsDefault:             isDefault,
		RuntimeStrategy:       "cointegration",
		RuntimeNetwork:        "testnet",
		RuntimeSubaccount:     0,
		PairSelectionMode:     "liquidity",
		ZscoreThreshold:       1.5,
		StatsWindow:           21,
		MaxHalfLife:           24.0,
		UsdPerTrade:           10.0,
		UsdMinCollateral:      100.0,
		CloseAtZscoreCross:    true,
		FindCointegratedPairs: true,
		ManageExits:           true,
		PlaceTrades:           true,
		AbortAllPositions:     false,
		MaxPositions:          5,
		// The live runtime enforces both (a drawdown limit that halts new
		// entries, a per-pair trailing stop), so they start off and are
		// turned on by the operator, not by a default.
		MaxDrawdownPct:         0,
		StopLossPct:            2.0,
		TakeProfitPct:          5.0,
		TrailingStopPct:        0,
		RebalanceIntervalHours: 24,
		PositionTimeoutHours:   72,
		TransactionFee:         0.0005,
		Slippage:               0.001,
		StartingBalance:        1000.0,
		CandleResolution:       "1HOUR",
		MaxHistoryDays:         90,
		BenchmarkSymbol:        "BTC-USD",
		RiskFreeRate:           0.02,
		InitialAmount:          1000.0,
		UsageCount:             0,
		CreatedAt:              time.Now().UTC(),
		UpdatedAt:              time.Now().UTC(),
	}
}

// GetStrategy retrieves a strategy by ID
func (s *StrategyService) GetStrategy(id int) (*models.BacktestStrategy, error) {
	if id <= 0 {
		return nil, fmt.Errorf("invalid strategy id")
	}

	strategy, err := s.repo.GetStrategyByID(id)
	if err != nil {
		return nil, fmt.Errorf("failed to get strategy: %w", err)
	}

	return strategy, nil
}

// GetStrategyForUpdate reads a strategy and, on a transaction-bound service on
// PostgreSQL, locks its row until the transaction ends.
func (s *StrategyService) GetStrategyForUpdate(id int) (*models.BacktestStrategy, error) {
	if id <= 0 {
		return nil, fmt.Errorf("invalid strategy id")
	}

	strategy, err := s.repo.GetStrategyByIDForUpdate(id)
	if err != nil {
		return nil, fmt.Errorf("failed to get strategy: %w", err)
	}

	return strategy, nil
}

// CountStrategies counts a user's strategies that are not deleted.
func (s *StrategyService) CountStrategies(userID int) (int, error) {
	if userID <= 0 {
		return 0, fmt.Errorf("invalid user id")
	}

	count, err := s.repo.CountStrategiesByUser(userID)
	if err != nil {
		return 0, fmt.Errorf("failed to count strategies: %w", err)
	}

	return count, nil
}

// ListStrategies retrieves all strategies for a user
func (s *StrategyService) ListStrategies(userID int) ([]models.BacktestStrategy, error) {
	if userID <= 0 {
		return nil, fmt.Errorf("invalid user id")
	}

	strategies, err := s.repo.GetStrategiesByUser(userID)
	if err != nil {
		return nil, fmt.Errorf("failed to list strategies: %w", err)
	}

	return strategies, nil
}

// UpdateStrategy updates an existing strategy
func (s *StrategyService) UpdateStrategy(strategy *models.BacktestStrategy) error {
	if strategy.ID <= 0 {
		return fmt.Errorf("invalid strategy id")
	}

	strategy.UpdatedAt = time.Now().UTC()
	strategy.UsageCount++

	if err := s.repo.UpdateStrategy(strategy); err != nil {
		return fmt.Errorf("failed to update strategy: %w", err)
	}

	log.Printf("✅ Updated strategy: %s (ID: %d)", strategy.Name, strategy.ID)
	return nil
}

// UpdateStrategyFields writes only the given columns of a strategy, never the
// whole row, so nothing another writer changed in the meantime is reverted.
func (s *StrategyService) UpdateStrategyFields(id int, fields map[string]any) error {
	if id <= 0 {
		return fmt.Errorf("invalid strategy id")
	}

	if err := s.repo.UpdateStrategyFields(id, fields); err != nil {
		return fmt.Errorf("failed to update strategy fields: %w", err)
	}

	log.Printf("✅ Updated strategy fields: ID %d (%d fields)", id, len(fields))
	return nil
}

// DeleteStrategy deletes a strategy
func (s *StrategyService) DeleteStrategy(id int) error {
	if id <= 0 {
		return fmt.Errorf("invalid strategy id")
	}

	if err := s.repo.DeleteStrategy(id); err != nil {
		return fmt.Errorf("failed to delete strategy: %w", err)
	}

	log.Printf("✅ Deleted strategy: ID %d", id)
	return nil
}

// ============ StrategyExecutionState Operations ============

// GetExecutionState retrieves execution state for a strategy
func (s *StrategyService) GetExecutionState(strategyID int) (*models.StrategyExecutionState, error) {
	if strategyID <= 0 {
		return nil, fmt.Errorf("invalid strategy id")
	}

	state, err := s.repo.GetExecutionState(strategyID)
	if err != nil {
		return nil, fmt.Errorf("failed to get execution state: %w", err)
	}

	return state, nil
}

// CreateExecutionState creates a new execution state
func (s *StrategyService) CreateExecutionState(strategyID int) (*models.StrategyExecutionState, error) {
	if strategyID <= 0 {
		return nil, fmt.Errorf("invalid strategy id")
	}

	state := &models.StrategyExecutionState{
		StrategyID: strategyID,
		IsRunning:  false,
		CreatedAt:  time.Now().UTC(),
		UpdatedAt:  time.Now().UTC(),
	}

	if err := s.repo.CreateExecutionState(state); err != nil {
		return nil, fmt.Errorf("failed to create execution state: %w", err)
	}

	return state, nil
}

// UpdateExecutionState updates execution state
func (s *StrategyService) UpdateExecutionState(state *models.StrategyExecutionState) error {
	if state.ID <= 0 || state.StrategyID <= 0 {
		return fmt.Errorf("invalid state or strategy id")
	}

	state.UpdatedAt = time.Now().UTC()

	if err := s.repo.UpdateExecutionState(state); err != nil {
		return fmt.Errorf("failed to update execution state: %w", err)
	}

	return nil
}

// ============ StrategyVersionHistory Operations ============

// CreateVersionHistory creates a new version history record
func (s *StrategyService) CreateVersionHistory(strategyID int, createdByUserID int, versionNumber int, changeLog string) (*models.StrategyVersionHistory, error) {
	if strategyID <= 0 {
		return nil, fmt.Errorf("invalid strategy id")
	}

	history := &models.StrategyVersionHistory{
		StrategyID:      strategyID,
		CreatedByUserID: createdByUserID,
		Version:         versionNumber,
		ChangeLog:       changeLog,
		CreatedAt:       time.Now().UTC(),
		UpdatedAt:       time.Now().UTC(),
	}

	if err := s.repo.CreateVersionHistory(history); err != nil {
		return nil, fmt.Errorf("failed to create version history: %w", err)
	}

	log.Printf("✅ Created version history for strategy %d (v%d)", strategyID, versionNumber)
	return history, nil
}

// SaveVersionSnapshot stores the strategy as it is now under the next
// version number, in the shape RevertVersion restores (ToJSON of the strategy).
func (s *StrategyService) SaveVersionSnapshot(strategy *models.BacktestStrategy, createdByUserID int, changeLog string) (*models.StrategyVersionHistory, error) {
	if strategy == nil || strategy.ID <= 0 {
		return nil, fmt.Errorf("invalid strategy id")
	}
	snapshot, err := strategy.ToJSON()
	if err != nil {
		return nil, fmt.Errorf("failed to encode strategy snapshot: %w", err)
	}
	if runes := []rune(changeLog); len(runes) > 500 {
		changeLog = string(runes[:500])
	}

	// version_number is UNIQUE per strategy; a concurrent snapshot can take the
	// number first, so read the latest again and retry a few times. Inside a
	// transaction there is one attempt: the caller holds the strategy row lock,
	// and PostgreSQL aborts the transaction on the first UNIQUE failure anyway.
	attempts := 3
	if s.inTx {
		attempts = 1
	}
	var lastErr error
	for attempt := 0; attempt < attempts; attempt++ {
		history, err := s.repo.GetVersionHistoryByStrategy(strategy.ID)
		if err != nil {
			return nil, fmt.Errorf("failed to read version history: %w", err)
		}
		next := 1
		for _, version := range history {
			if version.Version >= next {
				next = version.Version + 1
			}
		}
		record := &models.StrategyVersionHistory{
			StrategyID:      strategy.ID,
			CreatedByUserID: createdByUserID,
			Version:         next,
			StrategyData:    sql.NullString{String: string(snapshot), Valid: true},
			ChangeLog:       changeLog,
		}
		if lastErr = s.repo.CreateVersionHistory(record); lastErr == nil {
			return record, nil
		}
	}
	return nil, fmt.Errorf("failed to create version snapshot: %w", lastErr)
}

// GetVersionHistory retrieves version history for a strategy
func (s *StrategyService) GetVersionHistory(strategyID int) ([]models.StrategyVersionHistory, error) {
	if strategyID <= 0 {
		return nil, fmt.Errorf("invalid strategy id")
	}

	history, err := s.repo.GetVersionHistoryByStrategy(strategyID)
	if err != nil {
		return nil, fmt.Errorf("failed to get version history: %w", err)
	}

	return history, nil
}
