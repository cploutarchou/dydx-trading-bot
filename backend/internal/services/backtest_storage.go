package services

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// BacktestStorageManager handles JSON-based backtest result storage following singleton pattern
type BacktestStorageManager struct {
	mu          sync.RWMutex
	storagePath string
	backtestDir string
}

var (
	storageInstance *BacktestStorageManager
	storageOnce     sync.Once
)

// GetBacktestStorage returns singleton instance of BacktestStorageManager
func GetBacktestStorage() *BacktestStorageManager {
	storageOnce.Do(func() {
		storageInstance = &BacktestStorageManager{
			storagePath: "app",
			backtestDir: filepath.Join("app", "backtest_results"),
		}

		// Create backtest results directory if it doesn't exist
		if err := os.MkdirAll(storageInstance.backtestDir, 0755); err != nil {
			log.Printf("❌ Failed to create backtest directory: %v", err)
		} else {
			log.Printf("✅ BacktestStorageManager initialized with directory: %s", storageInstance.backtestDir)
		}
	})
	return storageInstance
}

// BacktestResultData represents the JSON structure for storing backtest results
type BacktestResultData struct {
	StartDate         string                 `json:"start_date"`
	EndDate           string                 `json:"end_date"`
	TotalDays         int                    `json:"total_days"`
	StartingBalance   float64                `json:"starting_balance"`
	EndingBalance     float64                `json:"ending_balance"`
	Metrics           BacktestMetricsData    `json:"metrics"`
	Trades            []BacktestTradeData    `json:"trades"`
	ConfigSnapshot    map[string]interface{} `json:"config_snapshot"`
	AnalysisTimestamp string                 `json:"analysis_timestamp"`
	Version           string                 `json:"version"`
}

// BacktestMetricsData represents metrics for JSON storage
type BacktestMetricsData struct {
	TotalPnl              float64 `json:"total_pnl"`
	TotalReturnPct        float64 `json:"total_return_pct"`
	TotalTrades           int     `json:"total_trades"`
	WinningTrades         int     `json:"winning_trades"`
	LosingTrades          int     `json:"losing_trades"`
	WinRate               float64 `json:"win_rate"`
	AvgWin                float64 `json:"avg_win"`
	AvgLoss               float64 `json:"avg_loss"`
	ProfitFactor          float64 `json:"profit_factor"`
	MaxDrawdown           float64 `json:"max_drawdown"`
	MaxDrawdownPct        float64 `json:"max_drawdown_pct"`
	SharpeRatio           float64 `json:"sharpe_ratio"`
	CalmarRatio           float64 `json:"calmar_ratio"`
	MaxConsecutiveLosses  int     `json:"max_consecutive_losses"`
	AvgTradeDurationHours float64 `json:"avg_trade_duration_hours"`
}

// BacktestTradeData represents trade data for JSON storage
type BacktestTradeData struct {
	TradeID                 string   `json:"trade_id"`
	Timestamp               string   `json:"timestamp"`
	Market1                 string   `json:"market_1"`
	Market2                 string   `json:"market_2"`
	Side1                   string   `json:"side_1"`
	Side2                   string   `json:"side_2"`
	Size1                   float64  `json:"size_1"`
	Size2                   float64  `json:"size_2"`
	EntryPrice1             float64  `json:"entry_price_1"`
	EntryPrice2             float64  `json:"entry_price_2"`
	ExitPrice1              *float64 `json:"exit_price_1"`
	ExitPrice2              *float64 `json:"exit_price_2"`
	ZScoreEntry             float64  `json:"z_score_entry"`
	ZScoreExit              *float64 `json:"z_score_exit"`
	Pnl                     *float64 `json:"pnl"`
	DurationHours           *float64 `json:"duration_hours"`
	HedgeRatio              float64  `json:"hedge_ratio"`
	StrategyID              *int     `json:"strategy_id"`
	StrategyName            *string  `json:"strategy_name"`
	StrategyZscoreThreshold *float64 `json:"strategy_zscore_threshold"`
}

// SaveBacktestResult saves backtest result to JSON file with timestamped filename
func (bsm *BacktestStorageManager) SaveBacktestResult(trades []models.BacktestTrade, metrics *models.BacktestMetrics, run *models.BacktestRun, testName string) (string, error) {
	bsm.mu.Lock()
	defer bsm.mu.Unlock()

	timestamp := time.Now().Format("20060102_150405")
	filename := fmt.Sprintf("backtest_%s_%s.json", testName, timestamp)
	filePath := filepath.Join(bsm.backtestDir, filename)

	// Convert metrics to JSON format
	metricsData := BacktestMetricsData{
		TotalPnl:              metrics.TotalPnl,
		TotalReturnPct:        metrics.TotalReturnPct,
		TotalTrades:           metrics.TotalTrades,
		WinningTrades:         metrics.WinningTrades,
		LosingTrades:          metrics.LosingTrades,
		WinRate:               metrics.WinRate,
		AvgWin:                metrics.AvgWin,
		AvgLoss:               metrics.AvgLoss,
		ProfitFactor:          metrics.ProfitFactor,
		MaxDrawdown:           metrics.MaxDrawdown,
		MaxDrawdownPct:        metrics.MaxDrawdownPct,
		SharpeRatio:           metrics.SharpeRatio,
		CalmarRatio:           metrics.CalmarRatio,
		MaxConsecutiveLosses:  metrics.MaxConsecutiveLosses,
		AvgTradeDurationHours: metrics.AvgTradeDurationHours,
	}

	// Convert trades to JSON format
	tradesData := make([]BacktestTradeData, len(trades))
	for i, trade := range trades {
		tradesData[i] = BacktestTradeData{
			TradeID:                 trade.TradeID,
			Timestamp:               trade.EntryTimestamp.UTC().Format(time.RFC3339),
			Market1:                 trade.Market1,
			Market2:                 trade.Market2,
			Side1:                   trade.Side1,
			Side2:                   trade.Side2,
			Size1:                   trade.Size1,
			Size2:                   trade.Size2,
			EntryPrice1:             trade.EntryPrice1,
			EntryPrice2:             trade.EntryPrice2,
			ExitPrice1:              trade.ExitPrice1,
			ExitPrice2:              trade.ExitPrice2,
			ZScoreEntry:             trade.EntryZScore,
			ZScoreExit:              trade.ExitZScore,
			Pnl:                     trade.Pnl,
			DurationHours:           trade.DurationHours,
			HedgeRatio:              trade.HedgeRatio,
			StrategyID:              trade.StrategyID,
			StrategyName:            trade.StrategyName,
			StrategyZscoreThreshold: trade.StrategyZscoreThreshold,
		}
	}

	startDate, endDate, totalDays := deriveStoredBacktestDateRange(run, trades)
	startingBalance := float64(0)
	if run != nil {
		startingBalance = run.StartingBalance
	}
	endingBalance := float64(0)
	if run != nil && run.EndingBalance != nil {
		endingBalance = *run.EndingBalance
	} else if startingBalance > 0 {
		endingBalance = startingBalance + metrics.TotalPnl
	}

	// Create result data
	resultData := BacktestResultData{
		StartDate:         startDate,
		EndDate:           endDate,
		TotalDays:         totalDays,
		StartingBalance:   startingBalance,
		EndingBalance:     endingBalance,
		Metrics:           metricsData,
		Trades:            tradesData,
		ConfigSnapshot:    make(map[string]interface{}),
		AnalysisTimestamp: time.Now().Format(time.RFC3339),
		Version:           "1.0",
	}

	// Marshal to JSON
	data, err := json.MarshalIndent(resultData, "", "  ")
	if err != nil {
		log.Printf("❌ Failed to marshal backtest result: %v", err)
		return "", err
	}

	// Write to file
	if err := os.WriteFile(filePath, data, 0644); err != nil {
		log.Printf("❌ Failed to save backtest result %s: %v", filename, err)
		return "", err
	}

	log.Printf("✅ Saved backtest result: %s (%d trades, $%.2f PnL)", filename, metrics.TotalTrades, metrics.TotalPnl)
	return filename, nil
}

func deriveStoredBacktestDateRange(run *models.BacktestRun, trades []models.BacktestTrade) (string, string, int) {
	startDate := ""
	endDate := ""
	if run != nil {
		startDate = strings.TrimSpace(run.StartDate)
		endDate = strings.TrimSpace(run.EndDate)
	}

	if startDate == "" || endDate == "" {
		for _, trade := range trades {
			tradeDate := trade.EntryTimestamp.UTC().Format("2006-01-02")
			if startDate == "" || tradeDate < startDate {
				startDate = tradeDate
			}
			if endDate == "" || tradeDate > endDate {
				endDate = tradeDate
			}
		}
	}

	if startDate == "" && endDate != "" {
		startDate = endDate
	}
	if endDate == "" && startDate != "" {
		endDate = startDate
	}

	totalDays := 0
	if startDate != "" && endDate != "" {
		start, startErr := time.Parse("2006-01-02", startDate)
		end, endErr := time.Parse("2006-01-02", endDate)
		if startErr == nil && endErr == nil && !end.Before(start) {
			totalDays = int(end.Sub(start).Hours()/24) + 1
		}
	}

	return startDate, endDate, totalDays
}

// LoadBacktestResult loads specific backtest result by filename
func (bsm *BacktestStorageManager) LoadBacktestResult(filename string) (*BacktestResultData, error) {
	bsm.mu.RLock()
	defer bsm.mu.RUnlock()

	filePath := filepath.Join(bsm.backtestDir, filename)

	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		log.Printf("⚠️  Backtest result file not found: %s", filename)
		return nil, fmt.Errorf("file not found: %s", filename)
	}

	data, err := os.ReadFile(filePath)
	if err != nil {
		log.Printf("❌ Failed to load backtest result %s: %v", filename, err)
		return nil, err
	}

	var result BacktestResultData
	if err := json.Unmarshal(data, &result); err != nil {
		log.Printf("❌ Failed to unmarshal backtest result %s: %v", filename, err)
		return nil, err
	}

	log.Printf("✅ Loaded backtest result: %s", filename)
	return &result, nil
}

// BacktestResultSummary represents summary info for a backtest result
type BacktestResultSummary struct {
	Filename          string  `json:"filename"`
	StartDate         string  `json:"start_date"`
	EndDate           string  `json:"end_date"`
	TotalTrades       int     `json:"total_trades"`
	TotalPnL          float64 `json:"total_pnl"`
	WinRate           float64 `json:"win_rate"`
	SharpeRatio       float64 `json:"sharpe_ratio"`
	AnalysisTimestamp string  `json:"analysis_timestamp"`
	FileSizeKB        float64 `json:"file_size_kb"`
}

// ListBacktestResults lists all available backtest results with summary info
func (bsm *BacktestStorageManager) ListBacktestResults() ([]BacktestResultSummary, error) {
	bsm.mu.RLock()
	defer bsm.mu.RUnlock()

	var results []BacktestResultSummary

	entries, err := os.ReadDir(bsm.backtestDir)
	if err != nil {
		log.Printf("❌ Failed to read backtest directory: %v", err)
		return results, err
	}

	for _, entry := range entries {
		if entry.IsDir() || filepath.Ext(entry.Name()) != ".json" {
			continue
		}

		filePath := filepath.Join(bsm.backtestDir, entry.Name())
		data, err := os.ReadFile(filePath)
		if err != nil {
			log.Printf("⚠️  Failed to read backtest summary from %s: %v", entry.Name(), err)
			continue
		}

		var resultData BacktestResultData
		if err := json.Unmarshal(data, &resultData); err != nil {
			log.Printf("⚠️  Failed to parse backtest summary from %s: %v", entry.Name(), err)
			continue
		}

		// Get file size
		info, err := os.Stat(filePath)
		fileSizeKB := float64(0)
		if err == nil {
			fileSizeKB = float64(info.Size()) / 1024
		}

		summary := BacktestResultSummary{
			Filename:          entry.Name(),
			StartDate:         resultData.StartDate,
			EndDate:           resultData.EndDate,
			TotalTrades:       resultData.Metrics.TotalTrades,
			TotalPnL:          resultData.Metrics.TotalPnl,
			WinRate:           resultData.Metrics.WinRate,
			SharpeRatio:       resultData.Metrics.SharpeRatio,
			AnalysisTimestamp: resultData.AnalysisTimestamp,
			FileSizeKB:        fileSizeKB,
		}

		results = append(results, summary)
	}

	// Sort by analysis timestamp (newest first)
	sort.Slice(results, func(i, j int) bool {
		return results[i].AnalysisTimestamp > results[j].AnalysisTimestamp
	})

	log.Printf("✅ Found %d backtest results", len(results))
	return results, nil
}

// GetBestResults returns top backtest results sorted by specified metric
func (bsm *BacktestStorageManager) GetBestResults(limit int, sortBy string) ([]BacktestResultData, error) {
	summaries, err := bsm.ListBacktestResults()
	if err != nil {
		return nil, err
	}

	var results []BacktestResultData

	for _, summary := range summaries {
		result, err := bsm.LoadBacktestResult(summary.Filename)
		if err != nil {
			log.Printf("⚠️  Failed to load result %s: %v", summary.Filename, err)
			continue
		}
		results = append(results, *result)
	}

	// Sort by specified metric
	switch sortBy {
	case "total_pnl":
		sort.Slice(results, func(i, j int) bool {
			return results[i].Metrics.TotalPnl > results[j].Metrics.TotalPnl
		})
	case "sharpe_ratio":
		sort.Slice(results, func(i, j int) bool {
			return results[i].Metrics.SharpeRatio > results[j].Metrics.SharpeRatio
		})
	case "win_rate":
		sort.Slice(results, func(i, j int) bool {
			return results[i].Metrics.WinRate > results[j].Metrics.WinRate
		})
	case "total_return_pct":
		sort.Slice(results, func(i, j int) bool {
			return results[i].Metrics.TotalReturnPct > results[j].Metrics.TotalReturnPct
		})
	default:
		log.Printf("⚠️  Unknown sort metric: %s, using total_pnl", sortBy)
		sort.Slice(results, func(i, j int) bool {
			return results[i].Metrics.TotalPnl > results[j].Metrics.TotalPnl
		})
	}

	// Limit results
	if limit > 0 && len(results) > limit {
		results = results[:limit]
	}

	return results, nil
}

// DeleteBacktestResult deletes specific backtest result file
func (bsm *BacktestStorageManager) DeleteBacktestResult(filename string) error {
	bsm.mu.Lock()
	defer bsm.mu.Unlock()

	filePath := filepath.Join(bsm.backtestDir, filename)

	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		log.Printf("⚠️  Cannot delete - backtest result file not found: %s", filename)
		return fmt.Errorf("file not found: %s", filename)
	}

	if err := os.Remove(filePath); err != nil {
		log.Printf("❌ Failed to delete backtest result %s: %v", filename, err)
		return err
	}

	log.Printf("✅ Deleted backtest result: %s", filename)
	return nil
}

// CleanupOldResults cleans up old backtest results, keeping only the most recent
func (bsm *BacktestStorageManager) CleanupOldResults(keepCount int) (int, error) {
	summaries, err := bsm.ListBacktestResults()
	if err != nil {
		return 0, err
	}

	if len(summaries) <= keepCount {
		log.Printf("ℹ️  No cleanup needed - %d results (limit: %d)", len(summaries), keepCount)
		return 0, nil
	}

	// Delete oldest results
	deletedCount := 0
	for i := keepCount; i < len(summaries); i++ {
		if err := bsm.DeleteBacktestResult(summaries[i].Filename); err == nil {
			deletedCount++
		}
	}

	log.Printf("✅ Cleaned up %d old backtest results (kept %d)", deletedCount, keepCount)
	return deletedCount, nil
}

// StorageInfo represents information about backtest storage state
type StorageInfo struct {
	TotalResults     int     `json:"total_results"`
	StorageDirectory string  `json:"storage_directory"`
	TotalSizeKB      float64 `json:"total_size_kb"`
	AvgPnLPerTest    float64 `json:"avg_pnl_per_test"`
	BestPnL          float64 `json:"best_pnl"`
	WorstPnL         float64 `json:"worst_pnl"`
	MostRecent       string  `json:"most_recent"`
}

// GetStorageInfo gets information about current backtest storage state
func (bsm *BacktestStorageManager) GetStorageInfo() (StorageInfo, error) {
	summaries, err := bsm.ListBacktestResults()
	if err != nil {
		return StorageInfo{}, err
	}

	info := StorageInfo{
		TotalResults:     len(summaries),
		StorageDirectory: bsm.backtestDir,
	}

	if len(summaries) > 0 {
		totalPnL := float64(0)
		bestPnL := summaries[0].TotalPnL
		worstPnL := summaries[0].TotalPnL

		for _, summary := range summaries {
			totalPnL += summary.TotalPnL
			info.TotalSizeKB += summary.FileSizeKB

			if summary.TotalPnL > bestPnL {
				bestPnL = summary.TotalPnL
			}
			if summary.TotalPnL < worstPnL {
				worstPnL = summary.TotalPnL
			}
		}

		info.AvgPnLPerTest = totalPnL / float64(len(summaries))
		info.BestPnL = bestPnL
		info.WorstPnL = worstPnL
		info.MostRecent = summaries[0].AnalysisTimestamp
	}

	return info, nil
}
