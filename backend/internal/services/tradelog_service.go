package services

import (
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

// TradeLogService manages trade log operations.
//
// Every method takes ownerUserID to enforce tenant isolation:
// trade_logs -> backtest_results -> backtest_runs.user_id. ownerUserID <= 0
// means unscoped access (admins / internal callers); regular users only see
// and mutate logs belonging to their own backtest runs.
type TradeLogService struct {
	repo *repository.TradeLogRepository
}

var (
	// ErrTradeLogNotFound maps to 404 at the handler.
	ErrTradeLogNotFound = errors.New("trade log not found")
	// ErrResultNotFound rejects creates against results the caller does not own.
	ErrResultNotFound = errors.New("backtest result not found")
)

// NewTradeLogService creates a new trade log service
func NewTradeLogService(repo *repository.TradeLogRepository) *TradeLogService {
	return &TradeLogService{repo: repo}
}

// CreateTradeLog creates a new trade log entry for a result the caller owns,
// persisting the full field set supplied in the request.
func (s *TradeLogService) CreateTradeLog(ownerUserID int, tradeLog *models.TradeLog) (*models.TradeLog, error) {
	if tradeLog.ResultIDFK <= 0 {
		return nil, fmt.Errorf("invalid result_id_fk")
	}
	if tradeLog.EntryTimestamp == nil {
		now := time.Now().UTC().UTC()
		tradeLog.EntryTimestamp = &now
	}

	resultOwner, err := s.repo.GetResultOwnerID(tradeLog.ResultIDFK)
	if err != nil {
		return nil, fmt.Errorf("failed to verify result ownership: %w", err)
	}
	if resultOwner == nil {
		return nil, ErrResultNotFound
	}
	if ownerUserID > 0 && *resultOwner != ownerUserID {
		return nil, ErrResultNotFound
	}

	if err := s.repo.CreateTradeLog(tradeLog); err != nil {
		return nil, fmt.Errorf("failed to create trade log: %w", err)
	}

	log.Printf("✅ Created trade log: ID %d for result %d", tradeLog.ID, tradeLog.ResultIDFK)
	return tradeLog, nil
}

// GetTradeLog retrieves a trade log by ID if it is within the caller's scope.
// Returns ErrTradeLogNotFound for foreign or missing logs.
func (s *TradeLogService) GetTradeLog(ownerUserID int, id int) (*models.TradeLog, error) {
	if id <= 0 {
		return nil, fmt.Errorf("invalid trade log id")
	}

	tradeLog, err := s.repo.GetTradeLogByID(id, ownerUserID)
	if err != nil {
		return nil, fmt.Errorf("failed to get trade log: %w", err)
	}
	if tradeLog == nil {
		return nil, ErrTradeLogNotFound
	}

	return tradeLog, nil
}

// ListTradeLogsByResult retrieves trade logs for a result in the caller's scope.
func (s *TradeLogService) ListTradeLogsByResult(ownerUserID int, resultIDFK int) ([]models.TradeLog, error) {
	if resultIDFK <= 0 {
		return nil, fmt.Errorf("invalid result_id_fk")
	}

	tradeLogs, err := s.repo.GetTradeLogsByResult(resultIDFK, ownerUserID)
	if err != nil {
		return nil, fmt.Errorf("failed to list trade logs: %w", err)
	}

	return tradeLogs, nil
}

// ListTradeLogsByBacktestRun retrieves trade logs for a backtest run in the
// caller's scope.
func (s *TradeLogService) ListTradeLogsByBacktestRun(ownerUserID int, runID int) ([]models.TradeLog, error) {
	if runID <= 0 {
		return nil, fmt.Errorf("invalid run id")
	}

	tradeLogs, err := s.repo.GetTradeLogsByBacktestRun(runID, ownerUserID)
	if err != nil {
		return nil, fmt.Errorf("failed to list trade logs: %w", err)
	}

	return tradeLogs, nil
}

// UpdateTradeLog updates an existing trade log after re-verifying ownership.
func (s *TradeLogService) UpdateTradeLog(ownerUserID int, tradeLog *models.TradeLog) error {
	if tradeLog.ID <= 0 {
		return fmt.Errorf("invalid trade log id")
	}

	// Ownership gate: the update may only proceed when the log is in scope.
	existing, err := s.repo.GetTradeLogByID(tradeLog.ID, ownerUserID)
	if err != nil {
		return fmt.Errorf("failed to get trade log: %w", err)
	}
	if existing == nil {
		return ErrTradeLogNotFound
	}

	if err := s.repo.UpdateTradeLog(tradeLog); err != nil {
		return fmt.Errorf("failed to update trade log: %w", err)
	}

	log.Printf("✅ Updated trade log: ID %d", tradeLog.ID)
	return nil
}

// DeleteTradeLog deletes a trade log after verifying it is in scope.
func (s *TradeLogService) DeleteTradeLog(ownerUserID int, id int) error {
	if id <= 0 {
		return fmt.Errorf("invalid trade log id")
	}

	existing, err := s.repo.GetTradeLogByID(id, ownerUserID)
	if err != nil {
		return fmt.Errorf("failed to get trade log: %w", err)
	}
	if existing == nil {
		return ErrTradeLogNotFound
	}

	if err := s.repo.DeleteTradeLog(id); err != nil {
		return fmt.Errorf("failed to delete trade log: %w", err)
	}

	log.Printf("✅ Deleted trade log: ID %d", id)
	return nil
}
