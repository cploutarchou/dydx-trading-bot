package handlers

import (
	"fmt"
	"net/http"
	"strconv"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

// TradeLogHandler handles trade log API endpoints
type TradeLogHandler struct {
	service *services.TradeLogService
}

// NewTradeLogHandler creates a new trade log handler
func NewTradeLogHandler(service *services.TradeLogService) *TradeLogHandler {
	return &TradeLogHandler{
		service: service,
	}
}

// CreateTradeLog creates a new trade log entry
func (h *TradeLogHandler) CreateTradeLog(c *gin.Context) {
	var req struct {
		ResultIDFK  int      `json:"result_id_fk" binding:"required"`
		TradeNumber *int     `json:"trade_number"`
		EntryPrice1 *float64 `json:"entry_price_1"`
		EntryPrice2 *float64 `json:"entry_price_2"`
		ExitPrice1  *float64 `json:"exit_price_1"`
		ExitPrice2  *float64 `json:"exit_price_2"`
		Quantity1   *float64 `json:"quantity_1"`
		Quantity2   *float64 `json:"quantity_2"`
		Side1       *string  `json:"side_1"`
		Side2       *string  `json:"side_2"`
		Pnl         *float64 `json:"pnl"`
		PnlUSD      *float64 `json:"pnl_usd"`
		EntryZScore *float64 `json:"entry_zscore"`
		ExitZScore  *float64 `json:"exit_zscore"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	tradeLog, err := h.service.CreateTradeLog(req.ResultIDFK, req.TradeNumber, req.EntryPrice1, req.EntryPrice2)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to create trade log: %v", err),
		})
		return
	}

	// Update with additional fields
	tradeLog.ExitPrice1 = req.ExitPrice1
	tradeLog.ExitPrice2 = req.ExitPrice2
	tradeLog.Quantity1 = req.Quantity1
	tradeLog.Quantity2 = req.Quantity2
	tradeLog.Side1 = req.Side1
	tradeLog.Side2 = req.Side2
	tradeLog.Pnl = req.Pnl
	tradeLog.PnlUSD = req.PnlUSD
	tradeLog.EntryZScore = req.EntryZScore
	tradeLog.ExitZScore = req.ExitZScore

	c.JSON(http.StatusCreated, APIResponse{
		Success:   true,
		Data:      tradeLog.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// GetTradeLog retrieves a trade log by ID
func (h *TradeLogHandler) GetTradeLog(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Invalid trade log ID",
		})
		return
	}

	tradeLog, err := h.service.GetTradeLog(id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to get trade log: %v", err),
		})
		return
	}

	if tradeLog == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Trade log not found",
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      tradeLog.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// ListTradeLogsByResult lists trade logs for a result
func (h *TradeLogHandler) ListTradeLogsByResult(c *gin.Context) {
	resultIDStr := c.Param("result_id")
	resultID, err := strconv.Atoi(resultIDStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Invalid result ID",
		})
		return
	}

	tradeLogs, err := h.service.ListTradeLogsByResult(resultID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to list trade logs: %v", err),
		})
		return
	}

	var result []map[string]interface{}
	for _, tl := range tradeLogs {
		result = append(result, tl.ToDict())
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"trade_logs": result,
			"count":      len(result),
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// ListTradeLogsByBacktestRun lists trade logs for a backtest run
func (h *TradeLogHandler) ListTradeLogsByBacktestRun(c *gin.Context) {
	runIDStr := c.Param("run_id")
	runID, err := strconv.Atoi(runIDStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Invalid run ID",
		})
		return
	}

	tradeLogs, err := h.service.ListTradeLogsByBacktestRun(runID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to list trade logs: %v", err),
		})
		return
	}

	var result []map[string]interface{}
	for _, tl := range tradeLogs {
		result = append(result, tl.ToDict())
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"trade_logs": result,
			"count":      len(result),
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// UpdateTradeLog updates a trade log
func (h *TradeLogHandler) UpdateTradeLog(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Invalid trade log ID",
		})
		return
	}

	tradeLog, err := h.service.GetTradeLog(id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to get trade log: %v", err),
		})
		return
	}

	if tradeLog == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Trade log not found",
		})
		return
	}

	var req struct {
		ExitPrice1 *float64 `json:"exit_price_1"`
		ExitPrice2 *float64 `json:"exit_price_2"`
		Pnl        *float64 `json:"pnl"`
		PnlUSD     *float64 `json:"pnl_usd"`
		ExitZScore *float64 `json:"exit_zscore"`
		ExitTime   *string  `json:"exit_timestamp"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	// Update fields
	if req.ExitPrice1 != nil {
		tradeLog.ExitPrice1 = req.ExitPrice1
	}
	if req.ExitPrice2 != nil {
		tradeLog.ExitPrice2 = req.ExitPrice2
	}
	if req.Pnl != nil {
		tradeLog.Pnl = req.Pnl
	}
	if req.PnlUSD != nil {
		tradeLog.PnlUSD = req.PnlUSD
	}
	if req.ExitZScore != nil {
		tradeLog.ExitZScore = req.ExitZScore
	}
	if req.ExitTime != nil {
		if et, err := time.Parse(time.RFC3339, *req.ExitTime); err == nil {
			tradeLog.ExitTimestamp = &et
		}
	}

	if err := h.service.UpdateTradeLog(tradeLog); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to update trade log: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      tradeLog.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// DeleteTradeLog deletes a trade log
func (h *TradeLogHandler) DeleteTradeLog(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Invalid trade log ID",
		})
		return
	}

	if err := h.service.DeleteTradeLog(id); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to delete trade log: %v", err),
		})
		return
	}

	c.Status(http.StatusNoContent)
}
