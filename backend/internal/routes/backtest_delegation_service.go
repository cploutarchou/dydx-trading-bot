// Package routes provides services for delegated backtest operations in the dYdX backend API.
package routes

import (
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

type BacktestDelegationService struct {
	backtestSync *services.BacktestSyncService
}

type (
	syncRunFunc      func(c *gin.Context, payload map[string]interface{})
	syncChildrenFunc func(c *gin.Context, runID string, payload map[string]interface{})
)

func NewBacktestDelegationService(backtestSync *services.BacktestSyncService) *BacktestDelegationService {
	return &BacktestDelegationService{backtestSync: backtestSync}
}

func (s *BacktestDelegationService) ResyncBacktestRun(
	c *gin.Context,
	requestClient *services.BotAPIClient,
	runID string,
	syncRun syncRunFunc,
	syncChildren syncChildrenFunc,
) (gin.H, error) {
	result := gin.H{
		"run_synced":       false,
		"trades_synced":    false,
		"positions_synced": false,
		"candles_synced":   false,
		"run_id":           runID,
		"status":           "unknown",
		"progress_percent": 0.0,
		"progress_pct":     0.0,
		"progress":         0.0,
		"current_task":     nil,
		"current_pair":     nil,
		"sync_state":       "partial",
	}

	details, err := requestClient.GetBacktestDetails(runID)
	if err != nil {
		return result, err
	}
	details = normalizeBacktestDetailsPayload(details)
	state := normalizeBacktestStatusFields(unwrapEnvelopePayload(details))
	if v, ok := state["run_id"]; ok {
		result["run_id"] = v
	}
	if v, ok := state["status"]; ok {
		result["status"] = v
	}
	for _, key := range []string{"progress_percent", "progress_pct", "progress", "current_task", "current_pair"} {
		if v, ok := state[key]; ok {
			result[key] = v
		}
	}
	syncRun(c, details)
	syncChildren(c, runID, details)
	result["run_synced"] = true

	tradesPayload, err := requestClient.GetBacktestTradesWithFilters(runID, 500, 0, false)
	if err == nil {
		syncChildren(c, runID, tradesPayload)
		result["trades_synced"] = true
	}

	positionsPayload, err := requestClient.GetPositionSnapshots(runID, 500, 0, nil)
	if err == nil {
		syncChildren(c, runID, positionsPayload)
		result["positions_synced"] = true
	}

	metricsPayload, err := requestClient.GetAdvancedPerformanceMetrics(runID, "BTC-USD")
	if err == nil {
		syncChildren(c, runID, metricsPayload)
		result["candles_synced"] = true
	}

	if result["run_synced"] == true &&
		result["trades_synced"] == true &&
		result["positions_synced"] == true &&
		result["candles_synced"] == true {
		result["sync_state"] = "completed"
	}

	return result, nil
}
