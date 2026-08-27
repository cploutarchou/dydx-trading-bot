package handlers

import (
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
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

// tradeLogScopeUserID returns the owner scope for the request: 0 for admins
// (unscoped), otherwise the authenticated user's id.
func tradeLogScopeUserID(c *gin.Context) (int, bool) {
	if c.GetBool("is_admin") {
		return 0, true
	}
	userIDValue, exists := c.Get("user_id")
	if !exists {
		return 0, false
	}
	userID, ok := userIDValue.(int)
	if !ok || userID <= 0 {
		return 0, false
	}
	return userID, true
}

func (h *TradeLogHandler) respondTradeLogError(c *gin.Context, err error, action string) {
	if errors.Is(err, services.ErrTradeLogNotFound) || errors.Is(err, services.ErrResultNotFound) {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Trade log not found",
		})
		return
	}
	c.JSON(http.StatusInternalServerError, APIResponse{
		Success:   false,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Error:     fmt.Sprintf("Failed to %s: %v", action, err),
	})
}

// CreateTradeLog creates a new trade log entry for a result the caller owns.
// All supplied fields are persisted; the response reflects stored values.
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
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	scopeUserID, ok := tradeLogScopeUserID(c)
	if !ok {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Unauthorized",
		})
		return
	}

	tradeLog, err := h.service.CreateTradeLog(scopeUserID, &models.TradeLog{
		ResultIDFK:  req.ResultIDFK,
		TradeNumber: req.TradeNumber,
		EntryPrice1: req.EntryPrice1,
		EntryPrice2: req.EntryPrice2,
		ExitPrice1:  req.ExitPrice1,
		ExitPrice2:  req.ExitPrice2,
		Quantity1:   req.Quantity1,
		Quantity2:   req.Quantity2,
		Side1:       req.Side1,
		Side2:       req.Side2,
		Pnl:         req.Pnl,
		PnlUSD:      req.PnlUSD,
		EntryZScore: req.EntryZScore,
		ExitZScore:  req.ExitZScore,
	})
	if err != nil {
		h.respondTradeLogError(c, err, "create trade log")
		return
	}

	c.JSON(http.StatusCreated, APIResponse{
		Success:   true,
		Data:      tradeLog.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetTradeLog retrieves a trade log by ID
func (h *TradeLogHandler) GetTradeLog(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Invalid trade log ID",
		})
		return
	}

	scopeUserID, ok := tradeLogScopeUserID(c)
	if !ok {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Unauthorized",
		})
		return
	}

	tradeLog, err := h.service.GetTradeLog(scopeUserID, id)
	if err != nil {
		h.respondTradeLogError(c, err, "get trade log")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      tradeLog.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// ListTradeLogsByResult lists trade logs for a result
func (h *TradeLogHandler) ListTradeLogsByResult(c *gin.Context) {
	resultIDStr := c.Param("result_id")
	resultID, err := strconv.Atoi(resultIDStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Invalid result ID",
		})
		return
	}

	scopeUserID, ok := tradeLogScopeUserID(c)
	if !ok {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Unauthorized",
		})
		return
	}

	tradeLogs, err := h.service.ListTradeLogsByResult(scopeUserID, resultID)
	if err != nil {
		h.respondTradeLogError(c, err, "list trade logs")
		return
	}

	result := make([]map[string]interface{}, 0)
	for _, tl := range tradeLogs {
		result = append(result, tl.ToDict())
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"trade_logs": result,
			"count":      len(result),
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// ListTradeLogsByBacktestRun lists trade logs for a backtest run
func (h *TradeLogHandler) ListTradeLogsByBacktestRun(c *gin.Context) {
	runIDStr := c.Param("run_id")
	runID, err := strconv.Atoi(runIDStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Invalid run ID",
		})
		return
	}

	scopeUserID, ok := tradeLogScopeUserID(c)
	if !ok {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Unauthorized",
		})
		return
	}

	tradeLogs, err := h.service.ListTradeLogsByBacktestRun(scopeUserID, runID)
	if err != nil {
		h.respondTradeLogError(c, err, "list trade logs")
		return
	}

	result := make([]map[string]interface{}, 0)
	for _, tl := range tradeLogs {
		result = append(result, tl.ToDict())
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"trade_logs": result,
			"count":      len(result),
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// UpdateTradeLog updates a trade log
func (h *TradeLogHandler) UpdateTradeLog(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Invalid trade log ID",
		})
		return
	}

	scopeUserID, ok := tradeLogScopeUserID(c)
	if !ok {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Unauthorized",
		})
		return
	}

	tradeLog, err := h.service.GetTradeLog(scopeUserID, id)
	if err != nil {
		h.respondTradeLogError(c, err, "get trade log")
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
			Timestamp: time.Now().UTC().Format(time.RFC3339),
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

	if err := h.service.UpdateTradeLog(scopeUserID, tradeLog); err != nil {
		h.respondTradeLogError(c, err, "update trade log")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      tradeLog.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// DeleteTradeLog deletes a trade log
func (h *TradeLogHandler) DeleteTradeLog(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Invalid trade log ID",
		})
		return
	}

	scopeUserID, ok := tradeLogScopeUserID(c)
	if !ok {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Unauthorized",
		})
		return
	}

	if err := h.service.DeleteTradeLog(scopeUserID, id); err != nil {
		h.respondTradeLogError(c, err, "delete trade log")
		return
	}

	c.Status(http.StatusNoContent)
}
