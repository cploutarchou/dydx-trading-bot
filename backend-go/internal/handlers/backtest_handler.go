package handlers

import (
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/gin-gonic/gin"
)

type BacktestHandler struct {
	repo *repository.BacktestRepository
}

func NewBacktestHandler(repo *repository.BacktestRepository) *BacktestHandler {
	return &BacktestHandler{
		repo: repo,
	}
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
	RunID   int              `json:"run_id"`
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

	runIDInt, err := strconv.Atoi(runID)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Invalid run_id format",
		})
		return
	}

	// Verify run exists using repository
	run, err := h.repo.GetRunByID(runID)
	if err != nil || run == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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
				Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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
				Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
				Error:     "end_date must be ISO format (YYYY-MM-DD)",
			})
			return
		}
		endDt = &t
	}

	// Get candles using repository
	filter := repository.CandleFilter{
		RunID:     runIDInt,
		Market:    market,
		StartDate: startDt,
		EndDate:   endDt,
	}

	dbCandles, err := h.repo.GetCandles(filter)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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
		RunID:   runIDInt,
		Candles: candles,
		Count:   len(candles),
		Markets: marketsList,
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      data,
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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
	RunID       int                `json:"run_id"`
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

	runIDInt, err := strconv.Atoi(runID)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Invalid run_id format",
		})
		return
	}

	// Verify run exists using repository
	run, err := h.repo.GetRunByID(runID)
	if err != nil || run == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Backtest run %s not found", runID),
		})
		return
	}

	// Get positions using repository
	filter := repository.PositionFilter{
		RunID:   runIDInt,
		Status:  strings.ToUpper(status),
		Market1: market1,
		Market2: market2,
	}

	dbPositions, err := h.repo.GetPositions(filter)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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

		positions = append(positions, PositionResponse{
			PositionID:     fmt.Sprintf("%d", pos.ID),
			Market1:        pos.Market1,
			Market2:        pos.Market2,
			EntryTimestamp: entryTimestamp,
			ExitTimestamp:  exitTimestamp,
			EntryPrice1:    pos.EntryPrice1,
			ExitPrice1:     pos.ExitPrice1,
			EntryPrice2:    pos.EntryPrice2,
			ExitPrice2:     pos.ExitPrice2,
			PnLM1USD:       pnlM1,
			PnLM2USD:       pnlM2,
			TotalPnLUSD:    pnlM1 + pnlM2,
			Status:         pos.Status,
		})
	}

	// Get counts using repository
	openCount, closedCount, err := h.repo.GetPositionCountsByStatus(runIDInt)
	if err != nil {
		openCount = 0
		closedCount = 0
	}

	data := PositionsData{
		RunID:       runIDInt,
		Positions:   positions,
		Count:       len(positions),
		OpenCount:   openCount,
		ClosedCount: closedCount,
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      data,
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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
	RunID  int             `json:"run_id"`
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

	runIDInt, err := strconv.Atoi(runID)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Invalid run_id format",
		})
		return
	}

	// Verify run exists using repository
	run, err := h.repo.GetRunByID(runID)
	if err != nil || run == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Backtest run %s not found", runID),
		})
		return
	}

	// Get total count using repository
	total, err := h.repo.GetTradesCount(runIDInt, market1, market2)
	if err != nil {
		total = 0
	}

	// Get trades using repository
	filter := repository.TradeFilter{
		RunID:   runIDInt,
		Market1: market1,
		Market2: market2,
		Skip:    skip,
		Limit:   limit,
	}

	dbTrades, err := h.repo.GetTrades(filter)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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
		RunID:  runIDInt,
		Trades: trades,
		Count:  len(trades),
		Total:  total,
		Skip:   skip,
		Limit:  limit,
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      data,
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}
