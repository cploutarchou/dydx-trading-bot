package handlers

import (
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

type BacktestHandler struct {
	repo    *repository.BacktestRepository
	storage *services.BacktestStorageManager
}

func NewBacktestHandler(repo *repository.BacktestRepository, storage *services.BacktestStorageManager) *BacktestHandler {
	return &BacktestHandler{
		repo:    repo,
		storage: storage,
	}
}

// ListBacktests retrieves all backtest runs for the current user with pagination
func (h *BacktestHandler) ListBacktests(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success: false, Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error: "User ID not found in context",
		})
		return
	}

	skip := 0
	limit := 100

	if skipStr := c.Query("skip"); skipStr != "" {
		if s, err := strconv.Atoi(skipStr); err == nil && s >= 0 {
			skip = s
		}
	}

	if limitStr := c.Query("limit"); limitStr != "" {
		if l, err := strconv.Atoi(limitStr); err == nil && l > 0 && l <= 500 {
			limit = l
		}
	}

	var runs []models.BacktestRun
	var err error
	if strategyIDStr := c.Query("strategy_id"); strategyIDStr != "" {
		strategyID, parseErr := strconv.Atoi(strategyIDStr)
		if parseErr != nil || strategyID <= 0 {
			c.JSON(http.StatusBadRequest, APIResponse{
				Success:   false,
				Timestamp: time.Now().UTC().Format(time.RFC3339),
				Error:     "Invalid strategy_id",
			})
			return
		}
		runs, err = h.repo.GetRunsByStrategyID(userID.(int), strategyID, limit)
	} else {
		runs, err = h.repo.GetRunsByUserID(userID.(int), skip, limit)
	}
	if err != nil {
		fmt.Printf("ERROR in ListBacktests: %v\n", err)
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to retrieve backtests: %v", err),
		})
		return
	}

	if runs == nil {
		runs = []models.BacktestRun{}
	}

	// Wrap backtests in the expected response format for frontend compatibility
	responseData := map[string]interface{}{
		"backtests": runs,
		"total":     len(runs), // Note: this should ideally come from repo if pagination is implemented
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      responseData,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

type CandleResponse struct {
	Market    string  `json:"market"`
	Timestamp string  `json:"timestamp"`
	Open      float64 `json:"open"`
	High      float64 `json:"high"`
	Low       float64 `json:"low"`
	Close     float64 `json:"close"`
	Volume    float64 `json:"volume"`
}

type CandlesData struct {
	RunID   string           `json:"run_id"`
	Candles []CandleResponse `json:"candles"`
	Count   int              `json:"count"`
	Markets []string         `json:"markets"`
}

type APIResponse struct {
	Success   bool        `json:"success"`
	Data      interface{} `json:"data"`
	Timestamp string      `json:"timestamp"`
	Error     string      `json:"error,omitempty"`
}

// GetBacktestCandles retrieves historical candle data for a backtest run
func (h *BacktestHandler) GetBacktestCandles(c *gin.Context) {
	runID := c.Param("run_id")
	market := c.Query("market")
	startDate := c.Query("start_date")
	endDate := c.Query("end_date")

	// Verify run exists using repository
	run, err := h.repo.GetRunByID(runID)
	if err != nil || run == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Backtest run %s not found", runID),
		})
		return
	}

	// Parse dates
	var startDt, endDt *time.Time
	if startDate != "" {
		t, err := time.Parse("2006-01-02", startDate)
		if err != nil {
			c.JSON(http.StatusBadRequest, APIResponse{
				Success:   false,
				Timestamp: time.Now().UTC().Format(time.RFC3339),
				Error:     "start_date must be ISO format (YYYY-MM-DD)",
			})
			return
		}
		startDt = &t
	}

	if endDate != "" {
		t, err := time.Parse("2006-01-02", endDate)
		if err != nil {
			c.JSON(http.StatusBadRequest, APIResponse{
				Success:   false,
				Timestamp: time.Now().UTC().Format(time.RFC3339),
				Error:     "end_date must be ISO format (YYYY-MM-DD)",
			})
			return
		}
		endDt = &t
	}

	// Get candles using repository
	filter := repository.CandleFilter{
		RunID:     run.ID,
		Market:    market,
		StartDate: startDt,
		EndDate:   endDt,
	}

	dbCandles, err := h.repo.GetCandles(filter)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Failed to retrieve candles",
		})
		return
	}

	var candles []CandleResponse
	var uniqueMarkets map[string]bool = make(map[string]bool)

	for _, candle := range dbCandles {
		uniqueMarkets[candle.Market] = true

		timestamp := candle.Timestamp.Format(time.RFC3339)
		if !strings.HasSuffix(timestamp, "Z") {
			timestamp += "Z"
		}

		candles = append(candles, CandleResponse{
			Market:    candle.Market,
			Timestamp: timestamp,
			Open:      candle.OpenPrice,
			High:      candle.HighPrice,
			Low:       candle.LowPrice,
			Close:     candle.ClosePrice,
			Volume:    candle.Volume,
		})
	}

	// Get unique markets list
	var marketsList []string
	for m := range uniqueMarkets {
		marketsList = append(marketsList, m)
	}

	data := CandlesData{
		RunID:   runID,
		Candles: candles,
		Count:   len(candles),
		Markets: marketsList,
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      data,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

type PositionResponse struct {
	PositionID     string   `json:"position_id"`
	Market1        string   `json:"market_1"`
	Market2        string   `json:"market_2"`
	EntryTimestamp string   `json:"entry_timestamp"`
	ExitTimestamp  string   `json:"exit_timestamp,omitempty"`
	EntryPrice1    float64  `json:"entry_price_m1"`
	ExitPrice1     *float64 `json:"exit_price_m1,omitempty"`
	EntryPrice2    float64  `json:"entry_price_m2"`
	ExitPrice2     *float64 `json:"exit_price_m2,omitempty"`
	HedgeRatio     *float64 `json:"hedge_ratio,omitempty"`
	PnLM1USD       float64  `json:"pnl_m1_usd"`
	PnLM2USD       float64  `json:"pnl_m2_usd"`
	TotalPnLUSD    float64  `json:"total_pnl_usd"`
	Status         string   `json:"status"`
}

type PositionsData struct {
	RunID       string             `json:"run_id"`
	Positions   []PositionResponse `json:"positions"`
	Count       int                `json:"count"`
	OpenCount   int                `json:"open_count"`
	ClosedCount int                `json:"closed_count"`
}

// GetBacktestPositions retrieves positions from a backtest run
func (h *BacktestHandler) GetBacktestPositions(c *gin.Context) {
	runID := c.Param("run_id")
	status := c.Query("status")
	market1 := c.Query("market_1")
	market2 := c.Query("market_2")

	// Verify run exists using repository
	run, err := h.repo.GetRunByID(runID)
	if err != nil || run == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Backtest run %s not found", runID),
		})
		return
	}

	// Get positions using repository
	filter := repository.PositionFilter{
		RunID:   run.ID,
		Status:  strings.ToUpper(status),
		Market1: market1,
		Market2: market2,
	}

	dbPositions, err := h.repo.GetPositions(filter)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Failed to retrieve positions",
		})
		return
	}

	var positions []PositionResponse

	for _, pos := range dbPositions {
		entryTimestamp := pos.EntryTimestamp.Format(time.RFC3339)
		if !strings.HasSuffix(entryTimestamp, "Z") {
			entryTimestamp += "Z"
		}

		exitTimestamp := ""
		if pos.ExitTimestamp != nil {
			exitTimestamp = pos.ExitTimestamp.Format(time.RFC3339)
			if !strings.HasSuffix(exitTimestamp, "Z") {
				exitTimestamp += "Z"
			}
		}

		pnlM1 := float64(0)
		pnlM2 := float64(0)
		totalPnL := float64(0)
		if pos.RealizedPnl != nil {
			totalPnL = *pos.RealizedPnl
		} else if pos.UnrealizedPnl != nil {
			totalPnL = *pos.UnrealizedPnl
		}

		positionID := pos.PositionID
		if positionID == "" {
			positionID = fmt.Sprintf("%d", pos.ID)
		}

		hedgeRatio := pos.HedgeRatio

		positions = append(positions, PositionResponse{
			PositionID:     positionID,
			Market1:        pos.Market1,
			Market2:        pos.Market2,
			EntryTimestamp: entryTimestamp,
			ExitTimestamp:  exitTimestamp,
			EntryPrice1:    pos.EntryPrice1,
			ExitPrice1:     pos.ExitPrice1,
			EntryPrice2:    pos.EntryPrice2,
			ExitPrice2:     pos.ExitPrice2,
			HedgeRatio:     &hedgeRatio,
			PnLM1USD:       pnlM1,
			PnLM2USD:       pnlM2,
			TotalPnLUSD:    totalPnL,
			Status:         pos.Status,
		})
	}

	// Get counts using repository
	openCount, closedCount, err := h.repo.GetPositionCountsByStatus(run.ID)
	if err != nil {
		openCount = 0
		closedCount = 0
	}

	data := PositionsData{
		RunID:       runID,
		Positions:   positions,
		Count:       len(positions),
		OpenCount:   openCount,
		ClosedCount: closedCount,
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      data,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

type TradeResponse struct {
	TradeID        string   `json:"trade_id"`
	Market1        string   `json:"market_1"`
	Market2        string   `json:"market_2"`
	EntryTimestamp string   `json:"entry_timestamp"`
	ExitTimestamp  string   `json:"exit_timestamp,omitempty"`
	EntryZScore    *float64 `json:"entry_zscore,omitempty"`
	ExitZScore     *float64 `json:"exit_zscore,omitempty"`
	EntryPrice1    float64  `json:"entry_price_m1"`
	ExitPrice1     *float64 `json:"exit_price_m1,omitempty"`
	EntryPrice2    float64  `json:"entry_price_m2"`
	ExitPrice2     *float64 `json:"exit_price_m2,omitempty"`
	HedgeRatio     *float64 `json:"hedge_ratio,omitempty"`
	PnLUSD         float64  `json:"pnl_usd"`
	PnLPct         float64  `json:"pnl_pct"`
	DurationHours  float64  `json:"duration_hours"`
	Win            bool     `json:"win"`
}

type TradesData struct {
	RunID  string          `json:"run_id"`
	Trades []TradeResponse `json:"trades"`
	Count  int             `json:"count"`
	Total  int             `json:"total"`
	Skip   int             `json:"skip"`
	Limit  int             `json:"limit"`
}

// GetBacktestTrades retrieves individual trades from a backtest run (paginated)
func (h *BacktestHandler) GetBacktestTrades(c *gin.Context) {
	runID := c.Param("run_id")
	market1 := c.Query("market_1")
	market2 := c.Query("market_2")

	skip := 0
	limit := 50

	if s := c.Query("skip"); s != "" {
		if val, err := strconv.Atoi(s); err == nil && val >= 0 {
			skip = val
		}
	}

	if l := c.Query("limit"); l != "" {
		if val, err := strconv.Atoi(l); err == nil && val >= 1 && val <= 500 {
			limit = val
		}
	}

	// Verify run exists using repository
	run, err := h.repo.GetRunByID(runID)
	if err != nil || run == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Backtest run %s not found", runID),
		})
		return
	}

	// Get total count using repository
	total, err := h.repo.GetTradesCount(run.ID, market1, market2)
	if err != nil {
		total = 0
	}

	// Get trades using repository
	filter := repository.TradeFilter{
		RunID:   run.ID,
		Market1: market1,
		Market2: market2,
		Skip:    skip,
		Limit:   limit,
	}

	dbTrades, err := h.repo.GetTrades(filter)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Failed to retrieve trades",
		})
		return
	}

	var trades []TradeResponse

	for _, trade := range dbTrades {
		entryTimestamp := trade.EntryTimestamp.Format(time.RFC3339)
		if !strings.HasSuffix(entryTimestamp, "Z") {
			entryTimestamp += "Z"
		}

		exitTimestamp := ""
		if trade.ExitTimestamp != nil {
			exitTimestamp = trade.ExitTimestamp.Format(time.RFC3339)
			if !strings.HasSuffix(exitTimestamp, "Z") {
				exitTimestamp += "Z"
			}
		}

		pnlUSD := float64(0)
		if trade.Pnl != nil {
			pnlUSD = *trade.Pnl
		}

		pnlPct := float64(0)
		if trade.PnlPct != nil {
			pnlPct = *trade.PnlPct
		}

		durationHours := float64(0)
		if trade.DurationHours != nil {
			durationHours = *trade.DurationHours
		}

		win := pnlUSD > 0

		// Convert to pointers for response
		entryZScore := trade.EntryZScore
		exitZScore := trade.ExitZScore
		hedgeRatio := trade.HedgeRatio

		trades = append(trades, TradeResponse{
			TradeID:        trade.TradeID,
			Market1:        trade.Market1,
			Market2:        trade.Market2,
			EntryTimestamp: entryTimestamp,
			ExitTimestamp:  exitTimestamp,
			EntryZScore:    &entryZScore,
			ExitZScore:     exitZScore,
			EntryPrice1:    trade.EntryPrice1,
			ExitPrice1:     trade.ExitPrice1,
			EntryPrice2:    trade.EntryPrice2,
			ExitPrice2:     trade.ExitPrice2,
			HedgeRatio:     &hedgeRatio,
			PnLUSD:         pnlUSD,
			PnLPct:         pnlPct,
			DurationHours:  durationHours,
			Win:            win,
		})
	}

	data := TradesData{
		RunID:  runID,
		Trades: trades,
		Count:  len(trades),
		Total:  total,
		Skip:   skip,
		Limit:  limit,
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      data,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// ==================== BACKTEST STORAGE ENDPOINTS ====================

// SaveBacktestResultJSON saves completed backtest results to JSON storage
func (h *BacktestHandler) SaveBacktestResultJSON(c *gin.Context) {
	runID := c.Param("run_id")
	testName := c.Query("test_name")
	if testName == "" {
		testName = runID
	}

	run, err := h.repo.GetRunByID(runID)
	if err != nil || run == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success: false,
			Error:   fmt.Sprintf("Backtest run %s not found", runID),
		})
		return
	}

	// Get all trades for this run
	filter := repository.TradeFilter{
		RunID: run.ID,
		Limit: 10000,
	}

	trades, err := h.repo.GetTrades(filter)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success: false,
			Error:   fmt.Sprintf("Failed to fetch trades: %v", err),
		})
		return
	}

	// Calculate metrics from trades
	wins := 0
	totalPnl := float64(0)
	for _, t := range trades {
		if t.Pnl != nil && *t.Pnl > 0 {
			wins++
			totalPnl += *t.Pnl
		}
	}

	// Convert to models.BacktestMetrics
	metricsModel := &models.BacktestMetrics{
		TotalTrades:           len(trades),
		WinningTrades:         wins,
		LosingTrades:          len(trades) - wins,
		WinRate:               float64(0),
		AvgWin:                float64(0),
		AvgLoss:               float64(0),
		ProfitFactor:          float64(1),
		MaxDrawdown:           float64(0),
		MaxDrawdownPct:        float64(0),
		SharpeRatio:           1.5,
		CalmarRatio:           float64(0),
		MaxConsecutiveLosses:  0,
		AvgTradeDurationHours: float64(0),
		TotalPnl:              totalPnl,
		TotalReturnPct:        (totalPnl / 100000) * 100,
	}

	if len(trades) > 0 {
		metricsModel.WinRate = (float64(wins) / float64(len(trades))) * 100
	}

	// Save to JSON
	filename, err := h.storage.SaveBacktestResult(trades, metricsModel, testName)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success: false,
			Error:   fmt.Sprintf("Failed to save: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"filename":     filename,
			"test_name":    testName,
			"trades_saved": len(trades),
			"total_pnl":    metricsModel.TotalPnl,
			"win_rate":     metricsModel.WinRate,
			"message":      "Backtest results saved to JSON storage",
			"storage_path": "app/backtest_results",
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// ExportBacktestResults exports list of all stored backtest results
func (h *BacktestHandler) ExportBacktestResults(c *gin.Context) {
	summaries, err := h.storage.ListBacktestResults()
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success: false,
			Error:   "Failed to list results",
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"results":   summaries,
			"count":     len(summaries),
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetBestResults returns top performing backtests from JSON storage
func (h *BacktestHandler) GetBestResults(c *gin.Context) {
	limitStr := c.DefaultQuery("limit", "10")
	sortBy := c.DefaultQuery("sort_by", "total_pnl")

	limit, _ := strconv.Atoi(limitStr)
	if limit > 100 {
		limit = 100
	}
	if limit < 1 {
		limit = 10
	}

	results, err := h.storage.GetBestResults(limit, sortBy)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success: false,
			Error:   fmt.Sprintf("Failed to get best results: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"results":   results,
			"count":     len(results),
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetStorageStats returns backtest storage statistics
func (h *BacktestHandler) GetStorageStats(c *gin.Context) {
	info, err := h.storage.GetStorageInfo()
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get stats: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      info,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// CleanupOldResults removes old backtest result files keeping only recent ones
func (h *BacktestHandler) CleanupOldResults(c *gin.Context) {
	keepStr := c.DefaultQuery("keep_count", "100")
	keep, _ := strconv.Atoi(keepStr)
	if keep < 5 {
		keep = 5
	}

	deleted, err := h.storage.CleanupOldResults(keep)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Cleanup failed: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"deleted":   deleted,
			"kept":      keep,
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}
