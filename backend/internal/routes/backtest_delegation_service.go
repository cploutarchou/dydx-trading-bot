// Package routes provides services for delegated backtest operations in the dYdX backend API.
package routes

import (
	"sync"

	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

const backtestMetricSyncWorkers = 8

type benchmarkMetricsResult struct {
	payload map[string]interface{}
	err     error
}

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
		"run_synced":              false,
		"trades_fetched_from_bot": false,
		"backend_trades_synced":   false,
		"positions_synced":        false,
		"candles_synced":          false,
		"run_id":                  runID,
		"status":                  "unknown",
		"progress_percent":        0.0,
		"progress_pct":            0.0,
		"progress":                0.0,
		"current_task":            nil,
		"current_pair":            nil,
		"sync_state":              "partial",
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
		result["trades_fetched_from_bot"] = true
		// Note: trades are fetched from bot but NOT synced to backend DB for delegated runs
		// backend_trades_synced remains false to reflect actual behavior
	}

	positionsPayload, err := requestClient.GetPositionSnapshots(runID, 500, 0, nil)
	if err == nil {
		syncChildren(c, runID, positionsPayload)
		result["positions_synced"] = true
	}

	benchmarks := resolveBacktestBenchmarks(details)
	result["benchmarks_requested"] = len(benchmarks)
	result["benchmarks_synced"] = 0

	jobs := make(chan string, len(benchmarks))
	metricsResults := make(chan benchmarkMetricsResult, len(benchmarks))
	for _, benchmark := range benchmarks {
		jobs <- benchmark
	}
	close(jobs)

	workerCount := min(backtestMetricSyncWorkers, len(benchmarks))
	var workers sync.WaitGroup
	workers.Add(workerCount)
	for range workerCount {
		go func() {
			defer workers.Done()
			for benchmark := range jobs {
				payload, metricsErr := requestClient.GetAdvancedPerformanceMetrics(runID, benchmark)
				metricsResults <- benchmarkMetricsResult{payload: payload, err: metricsErr}
			}
		}()
	}
	workers.Wait()
	close(metricsResults)

	benchmarksSynced := 0
	for metricsResult := range metricsResults {
		if metricsResult.err != nil {
			continue
		}
		syncChildren(c, runID, metricsResult.payload)
		benchmarksSynced++
	}
	result["benchmarks_synced"] = benchmarksSynced
	result["candles_synced"] = benchmarksSynced == len(benchmarks)

	if result["run_synced"] == true &&
		result["trades_fetched_from_bot"] == true &&
		result["positions_synced"] == true &&
		result["candles_synced"] == true {
		result["sync_state"] = "completed"
	}

	return result, nil
}
