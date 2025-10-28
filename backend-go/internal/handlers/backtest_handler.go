package handlers

import (
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/gin-gonic/gin"
)

type BacktestHandler struct {
	db *db.Database
}

func NewBacktestHandler(database *db.Database) *BacktestHandler {
	return &BacktestHandler{
		db: database,
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

	// Convert run_id to int for validation
	runIDInt, err := strconv.Atoi(runID)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Invalid run_id format",
		})
		return
	}

	// Verify run exists
	var run models.BacktestRun
	if err := h.db.DB.QueryRow("SELECT id FROM backtest_runs WHERE run_id = $1", runID).Scan(&run.ID); err != nil {
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

	// Build query
	query := "SELECT id, run_id, market, timestamp, resolution, open_price, high_price, low_price, close_price, volume, trades_count FROM backtest_candles WHERE run_id = $1"
	args := []interface{}{runIDInt}
	argNum := 2

	if market != "" {
		query += fmt.Sprintf(" AND market = $%d", argNum)
		args = append(args, market)
		argNum++
	}

	if startDt != nil {
		query += fmt.Sprintf(" AND timestamp >= $%d", argNum)
		args = append(args, startDt)
		argNum++
	}

	if endDt != nil {
		query += fmt.Sprintf(" AND timestamp <= $%d", argNum)
		args = append(args, endDt)
		argNum++
	}

	query += " ORDER BY timestamp"

	rows, err := h.db.DB.Query(query, args...)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Failed to retrieve candles",
		})
		return
	}
	defer rows.Close()

	var candles []CandleResponse
	var uniqueMarkets map[string]bool = make(map[string]bool)

	for rows.Next() {
		var candle models.BacktestCandle
		if err := rows.Scan(&candle.ID, &candle.RunID, &candle.Market, &candle.Timestamp, &candle.Resolution, &candle.OpenPrice, &candle.HighPrice, &candle.LowPrice, &candle.ClosePrice, &candle.Volume, &candle.TradesCount); err != nil {
			continue
		}

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

	// Verify run exists
	var run models.BacktestRun
	if err := h.db.DB.QueryRow("SELECT id FROM backtest_runs WHERE run_id = $1", runID).Scan(&run.ID); err != nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Backtest run %s not found", runID),
		})
		return
	}

	// Build query
	query := "SELECT id, run_id, market_1, market_2, entry_price_1, exit_price_1, entry_price_2, exit_price_2, entry_timestamp, exit_timestamp FROM backtest_positions WHERE run_id = $1"
	args := []interface{}{runIDInt}
	argNum := 2

	if status != "" && strings.ToUpper(status) != "ALL" {
		query += fmt.Sprintf(" AND status = $%d", argNum)
		args = append(args, strings.ToUpper(status))
		argNum++
	}

	if market1 != "" {
		query += fmt.Sprintf(" AND market_1 = $%d", argNum)
		args = append(args, market1)
		argNum++
	}

	if market2 != "" {
		query += fmt.Sprintf(" AND market_2 = $%d", argNum)
		args = append(args, market2)
		argNum++
	}

	query += " ORDER BY entry_timestamp"

	rows, err := h.db.DB.Query(query, args...)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Failed to retrieve positions",
		})
		return
	}
	defer rows.Close()

	var positions []PositionResponse

	for rows.Next() {
		var pos models.BacktestPosition
		if err := rows.Scan(&pos.ID, &pos.RunID, &pos.Market1, &pos.Market2, &pos.EntryPrice1, &pos.ExitPrice1, &pos.EntryPrice2, &pos.ExitPrice2, &pos.EntryTimestamp, &pos.ExitTimestamp); err != nil {
			continue
		}

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
			Status:         "CLOSED",
		})
	}

	// Get counts
	openCount := 0
	closedCount := 0

	h.db.DB.QueryRow("SELECT COUNT(*) FROM backtest_positions WHERE run_id = $1 AND status = 'OPEN'", runIDInt).Scan(&openCount)
	h.db.DB.QueryRow("SELECT COUNT(*) FROM backtest_positions WHERE run_id = $1 AND status = 'CLOSED'", runIDInt).Scan(&closedCount)

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

	// Verify run exists
	var run models.BacktestRun
	if err := h.db.DB.QueryRow("SELECT id FROM backtest_runs WHERE run_id = $1", runID).Scan(&run.ID); err != nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Backtest run %s not found", runID),
		})
		return
	}

	// Build count query
	countQuery := "SELECT COUNT(*) FROM backtest_trades WHERE run_id = $1"
	countArgs := []interface{}{runIDInt}
	countArgNum := 2

	// Build data query
	query := "SELECT id, run_id, trade_id, market_1, market_2, entry_price_1, exit_price_1, entry_price_2, exit_price_2, hedge_ratio, entry_z_score, exit_z_score, entry_timestamp, exit_timestamp, pnl, pnl_pct, duration_hours FROM backtest_trades WHERE run_id = $1"
	args := []interface{}{runIDInt}
	argNum := 2

	if market1 != "" {
		countQuery += fmt.Sprintf(" AND market_1 = $%d", countArgNum)
		countArgs = append(countArgs, market1)
		countArgNum++

		query += fmt.Sprintf(" AND market_1 = $%d", argNum)
		args = append(args, market1)
		argNum++
	}

	if market2 != "" {
		countQuery += fmt.Sprintf(" AND market_2 = $%d", countArgNum)
		countArgs = append(countArgs, market2)
		countArgNum++

		query += fmt.Sprintf(" AND market_2 = $%d", argNum)
		args = append(args, market2)
		argNum++
	}

	// Get total count
	total := 0
	if err := h.db.DB.QueryRow(countQuery, countArgs...).Scan(&total); err != nil {
		total = 0
	}

	query += " ORDER BY entry_timestamp"
	query += fmt.Sprintf(" OFFSET %d LIMIT %d", skip, limit)

	rows, err := h.db.DB.Query(query, args...)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Failed to retrieve trades",
		})
		return
	}
	defer rows.Close()

	var trades []TradeResponse

	for rows.Next() {
		var trade models.BacktestTrade
		if err := rows.Scan(&trade.ID, &trade.RunID, &trade.TradeID, &trade.Market1, &trade.Market2, &trade.EntryPrice1, &trade.ExitPrice1, &trade.EntryPrice2, &trade.ExitPrice2, &trade.HedgeRatio, &trade.EntryZScore, &trade.ExitZScore, &trade.EntryTimestamp, &trade.ExitTimestamp, &trade.Pnl, &trade.PnlPct, &trade.DurationHours); err != nil {
			continue
		}

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

		trades = append(trades, TradeResponse{
			TradeID:        trade.TradeID,
			Market1:        trade.Market1,
			Market2:        trade.Market2,
			EntryTimestamp: entryTimestamp,
			ExitTimestamp:  exitTimestamp,
			EntryZScore:    &trade.EntryZScore,
			ExitZScore:     trade.ExitZScore,
			EntryPrice1:    trade.EntryPrice1,
			ExitPrice1:     trade.ExitPrice1,
			EntryPrice2:    trade.EntryPrice2,
			ExitPrice2:     trade.ExitPrice2,
			HedgeRatio:     &trade.HedgeRatio,
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
