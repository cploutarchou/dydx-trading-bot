package services

import (
	"fmt"
	"log"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

// StrategyService manages backtest strategy operations
type StrategyService struct {
	repo *repository.StrategyRepository
}

// NewStrategyService creates a new strategy service
func NewStrategyService(repo *repository.StrategyRepository) *StrategyService {
	return &StrategyService{repo: repo}
}

// ============ BacktestStrategy Operations ============

// CreateStrategy creates a new backtest strategy
func (s *StrategyService) CreateStrategy(userID int, name, description, category string, isPublic, isDefault bool) (*models.BacktestStrategy, error) {
	if name == "" {
		return nil, fmt.Errorf("strategy name is required")
	}

	strategy := &models.BacktestStrategy{
		UserID:                 userID,
		Name:                   name,
		Description:            description,
		Category:               category,
		IsPublic:               isPublic,
		IsDefault:              isDefault,
		ZscoreThreshold:        1.5,
		StatsWindow:            21,
		MaxHalfLife:            24.0,
		UsdPerTrade:            10.0,
		UsdMinCollateral:       100.0,
		CloseAtZscoreCross:     true,
		FindCointegratedPairs:  true,
		ManageExits:            true,
		PlaceTrades:            true,
		AbortAllPositions:      false,
		MaxPositions:           5,
		MaxDrawdownPct:         15.0,
		StopLossPct:            2.0,
		TakeProfitPct:          5.0,
		TrailingStopPct:        1.0,
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
		CreatedAt:              time.Now(),
		UpdatedAt:              time.Now(),
	}

	if err := s.repo.CreateStrategy(strategy); err != nil {
		return nil, fmt.Errorf("failed to create strategy: %w", err)
	}

	log.Printf("✅ Created strategy: %s (ID: %d)", name, strategy.ID)
	return strategy, nil
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

	strategy.UpdatedAt = time.Now()
	strategy.UsageCount++

	if err := s.repo.UpdateStrategy(strategy); err != nil {
		return fmt.Errorf("failed to update strategy: %w", err)
	}

	log.Printf("✅ Updated strategy: %s (ID: %d)", strategy.Name, strategy.ID)
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
		CreatedAt:  time.Now(),
		UpdatedAt:  time.Now(),
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

	state.UpdatedAt = time.Now()

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
		CreatedAt:       time.Now(),
		UpdatedAt:       time.Now(),
	}

	if err := s.repo.CreateVersionHistory(history); err != nil {
		return nil, fmt.Errorf("failed to create version history: %w", err)
	}

	log.Printf("✅ Created version history for strategy %d (v%d)", strategyID, versionNumber)
	return history, nil
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
