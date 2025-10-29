package services

import (
	"fmt"
	"log"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

// TradeLogService manages trade log operations
type TradeLogService struct {
	repo *repository.TradeLogRepository
}

// NewTradeLogService creates a new trade log service
func NewTradeLogService(repo *repository.TradeLogRepository) *TradeLogService {
	return &TradeLogService{repo: repo}
}

// CreateTradeLog creates a new trade log entry
func (s *TradeLogService) CreateTradeLog(resultIDFK int, tradeNumber *int, entry_price_1, entry_price_2 *float64) (*models.TradeLog, error) {
	if resultIDFK <= 0 {
		return nil, fmt.Errorf("invalid result_id_fk")
	}

	tradeLog := &models.TradeLog{
		ResultIDFK:     resultIDFK,
		TradeNumber:    tradeNumber,
		EntryPrice1:    entry_price_1,
		EntryPrice2:    entry_price_2,
		EntryTimestamp: &[]time.Time{time.Now()}[0],
		CreatedAt:      time.Now(),
	}

	if err := s.repo.CreateTradeLog(tradeLog); err != nil {
		return nil, fmt.Errorf("failed to create trade log: %w", err)
	}

	log.Printf("✅ Created trade log: ID %d for result %d", tradeLog.ID, resultIDFK)
	return tradeLog, nil
}

// GetTradeLog retrieves a trade log by ID
func (s *TradeLogService) GetTradeLog(id int) (*models.TradeLog, error) {
	if id <= 0 {
		return nil, fmt.Errorf("invalid trade log id")
	}

	tradeLog, err := s.repo.GetTradeLogByID(id)
	if err != nil {
		return nil, fmt.Errorf("failed to get trade log: %w", err)
	}

	return tradeLog, nil
}

// ListTradeLogsByResult retrieves all trade logs for a result
func (s *TradeLogService) ListTradeLogsByResult(resultIDFK int) ([]models.TradeLog, error) {
	if resultIDFK <= 0 {
		return nil, fmt.Errorf("invalid result_id_fk")
	}

	tradeLogs, err := s.repo.GetTradeLogsByResult(resultIDFK)
	if err != nil {
		return nil, fmt.Errorf("failed to list trade logs: %w", err)
	}

	return tradeLogs, nil
}

// ListTradeLogsByBacktestRun retrieves all trade logs for a backtest run
func (s *TradeLogService) ListTradeLogsByBacktestRun(runID int) ([]models.TradeLog, error) {
	if runID <= 0 {
		return nil, fmt.Errorf("invalid run id")
	}

	tradeLogs, err := s.repo.GetTradeLogsByBacktestRun(runID)
	if err != nil {
		return nil, fmt.Errorf("failed to list trade logs: %w", err)
	}

	return tradeLogs, nil
}

// UpdateTradeLog updates an existing trade log
func (s *TradeLogService) UpdateTradeLog(tradeLog *models.TradeLog) error {
	if tradeLog.ID <= 0 {
		return fmt.Errorf("invalid trade log id")
	}

	if err := s.repo.UpdateTradeLog(tradeLog); err != nil {
		return fmt.Errorf("failed to update trade log: %w", err)
	}

	log.Printf("✅ Updated trade log: ID %d", tradeLog.ID)
	return nil
}

// DeleteTradeLog deletes a trade log
func (s *TradeLogService) DeleteTradeLog(id int) error {
	if id <= 0 {
		return fmt.Errorf("invalid trade log id")
	}

	if err := s.repo.DeleteTradeLog(id); err != nil {
		return fmt.Errorf("failed to delete trade log: %w", err)
	}

	log.Printf("✅ Deleted trade log: ID %d", id)
	return nil
}
