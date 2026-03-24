package handlers

import (
	"fmt"
	"net/http"
	"strconv"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

// StrategyHandler handles strategy API endpoints
type StrategyHandler struct {
	service *services.StrategyService
}

type strategyPayload struct {
	Name                   string  `json:"name" binding:"required"`
	Description            string  `json:"description"`
	Category               string  `json:"category"`
	IsPublic               bool    `json:"is_public"`
	IsDefault              bool    `json:"is_default"`
	Resolution             string  `json:"resolution"`
	CandleResolution       string  `json:"candle_resolution"`
	ZscoreThreshold        float64 `json:"zscore_threshold"`
	StatsWindow            int     `json:"stats_window"`
	MaxHalfLife            float64 `json:"max_half_life"`
	UsdPerTrade            float64 `json:"usd_per_trade"`
	UsdMinCollateral       float64 `json:"usd_min_collateral"`
	CloseAtZscoreCross     *bool   `json:"close_at_zscore_cross"`
	FindCointegratedPairs  *bool   `json:"find_cointegrated_pairs"`
	ManageExits            *bool   `json:"manage_exits"`
	PlaceTrades            *bool   `json:"place_trades"`
	AbortAllPositions      *bool   `json:"abort_all_positions"`
	MaxDrawdownPct         float64 `json:"max_drawdown_pct"`
	StopLossPct            float64 `json:"stop_loss_pct"`
	TakeProfitPct          float64 `json:"take_profit_pct"`
	TrailingStopPct        float64 `json:"trailing_stop_pct"`
	MaxPositions           int     `json:"max_positions"`
	RebalanceIntervalHours int     `json:"rebalance_interval_hours"`
	PositionTimeoutHours   int     `json:"position_timeout_hours"`
	InitialAmount          float64 `json:"initial_amount"`
	TransactionFee         float64 `json:"transaction_fee"`
	Slippage               float64 `json:"slippage"`
	MaxHistoryDays         int     `json:"max_history_days"`
	BenchmarkSymbol        string  `json:"benchmark_symbol"`
	RiskFreeRate           float64 `json:"risk_free_rate"`
}

func applyStrategyPayload(strategy *models.BacktestStrategy, req strategyPayload) {
	if req.Name != "" {
		strategy.Name = req.Name
	}
	if req.Description != "" {
		strategy.Description = req.Description
	}
	if req.Category != "" {
		strategy.Category = req.Category
	}
	strategy.IsPublic = req.IsPublic
	strategy.IsDefault = req.IsDefault

	if req.CandleResolution != "" {
		strategy.CandleResolution = req.CandleResolution
	} else if req.Resolution != "" {
		strategy.CandleResolution = req.Resolution
	}
	if req.ZscoreThreshold > 0 {
		strategy.ZscoreThreshold = req.ZscoreThreshold
	}
	if req.StatsWindow > 0 {
		strategy.StatsWindow = req.StatsWindow
	}
	if req.MaxHalfLife > 0 {
		strategy.MaxHalfLife = req.MaxHalfLife
	}
	if req.UsdPerTrade > 0 {
		strategy.UsdPerTrade = req.UsdPerTrade
	}
	if req.UsdMinCollateral > 0 {
		strategy.UsdMinCollateral = req.UsdMinCollateral
	}
	if req.CloseAtZscoreCross != nil {
		strategy.CloseAtZscoreCross = *req.CloseAtZscoreCross
	}
	if req.FindCointegratedPairs != nil {
		strategy.FindCointegratedPairs = *req.FindCointegratedPairs
	}
	if req.ManageExits != nil {
		strategy.ManageExits = *req.ManageExits
	}
	if req.PlaceTrades != nil {
		strategy.PlaceTrades = *req.PlaceTrades
	}
	if req.AbortAllPositions != nil {
		strategy.AbortAllPositions = *req.AbortAllPositions
	}
	if req.MaxDrawdownPct > 0 {
		strategy.MaxDrawdownPct = req.MaxDrawdownPct
	}
	if req.StopLossPct > 0 {
		strategy.StopLossPct = req.StopLossPct
	}
	if req.TakeProfitPct > 0 {
		strategy.TakeProfitPct = req.TakeProfitPct
	}
	if req.TrailingStopPct > 0 {
		strategy.TrailingStopPct = req.TrailingStopPct
	}
	if req.MaxPositions > 0 {
		strategy.MaxPositions = req.MaxPositions
	}
	if req.RebalanceIntervalHours > 0 {
		strategy.RebalanceIntervalHours = req.RebalanceIntervalHours
	}
	if req.PositionTimeoutHours > 0 {
		strategy.PositionTimeoutHours = req.PositionTimeoutHours
	}
	if req.InitialAmount > 0 {
		strategy.InitialAmount = req.InitialAmount
		// Keep create/edit UI budget aligned with runtime collateral defaults.
		if strategy.UsdMinCollateral <= 0 {
			strategy.UsdMinCollateral = req.InitialAmount
		}
	}
	if req.TransactionFee > 0 {
		strategy.TransactionFee = req.TransactionFee
	}
	if req.Slippage > 0 {
		strategy.Slippage = req.Slippage
	}
	if req.MaxHistoryDays > 0 {
		strategy.MaxHistoryDays = req.MaxHistoryDays
	}
	if req.BenchmarkSymbol != "" {
		strategy.BenchmarkSymbol = req.BenchmarkSymbol
	}
	if req.RiskFreeRate > 0 {
		strategy.RiskFreeRate = req.RiskFreeRate
	}
}

// NewStrategyHandler creates a new strategy handler
func NewStrategyHandler(service *services.StrategyService) *StrategyHandler {
	return &StrategyHandler{
		service: service,
	}
}

// CreateStrategy creates a new strategy
func (h *StrategyHandler) CreateStrategy(c *gin.Context) {
	var req strategyPayload

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Unauthorized",
		})
		return
	}

	strategy, err := h.service.CreateStrategy(
		userID.(int),
		req.Name,
		req.Description,
		req.Category,
		req.IsPublic,
		req.IsDefault,
	)
	if err == nil {
		applyStrategyPayload(strategy, req)
		err = h.service.UpdateStrategy(strategy)
	}

	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to create strategy: %v", err),
		})
		return
	}

	c.JSON(http.StatusCreated, APIResponse{
		Success:   true,
		Data:      strategy.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// GetStrategy retrieves a strategy by ID
func (h *StrategyHandler) GetStrategy(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Invalid strategy ID",
		})
		return
	}

	strategy, err := h.service.GetStrategy(id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to get strategy: %v", err),
		})
		return
	}

	if strategy == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Strategy not found",
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      strategy.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// ListStrategies lists all strategies for the user
func (h *StrategyHandler) ListStrategies(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Unauthorized",
		})
		return
	}

	strategies, err := h.service.ListStrategies(userID.(int))
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to list strategies: %v", err),
		})
		return
	}

	var result []map[string]interface{}
	for _, s := range strategies {
		result = append(result, s.ToDict())
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"strategies": result,
			"total":      len(result),
			"count":      len(result),
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// UpdateStrategy updates a strategy
func (h *StrategyHandler) UpdateStrategy(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Invalid strategy ID",
		})
		return
	}

	var req strategyPayload

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	strategy, err := h.service.GetStrategy(id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to get strategy: %v", err),
		})
		return
	}

	if strategy == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Strategy not found",
		})
		return
	}

	applyStrategyPayload(strategy, req)

	if err := h.service.UpdateStrategy(strategy); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to update strategy: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      strategy.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// DeleteStrategy deletes a strategy
func (h *StrategyHandler) DeleteStrategy(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Invalid strategy ID",
		})
		return
	}

	if err := h.service.DeleteStrategy(id); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to delete strategy: %v", err),
		})
		return
	}

	c.Status(http.StatusNoContent)
}
