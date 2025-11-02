package handlers

import (
	"fmt"
	"net/http"
	"strconv"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

// StrategyHandler handles strategy API endpoints
type StrategyHandler struct {
	service *services.StrategyService
}

// NewStrategyHandler creates a new strategy handler
func NewStrategyHandler(service *services.StrategyService) *StrategyHandler {
	return &StrategyHandler{
		service: service,
	}
}

// CreateStrategy creates a new strategy
func (h *StrategyHandler) CreateStrategy(c *gin.Context) {
	var req struct {
		Name        string `json:"name" binding:"required"`
		Description string `json:"description"`
		Category    string `json:"category"`
		IsPublic    bool   `json:"is_public"`
		IsDefault   bool   `json:"is_default"`
	}

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

	var req struct {
		Name            string  `json:"name"`
		Description     string  `json:"description"`
		Category        string  `json:"category"`
		IsPublic        bool    `json:"is_public"`
		ZscoreThreshold float64 `json:"zscore_threshold"`
		MaxDrawdownPct  float64 `json:"max_drawdown_pct"`
		StopLossPct     float64 `json:"stop_loss_pct"`
		TakeProfitPct   float64 `json:"take_profit_pct"`
		TrailingStopPct float64 `json:"trailing_stop_pct"`
		MaxPositions    int     `json:"max_positions"`
	}

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

	// Update fields
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
	if req.ZscoreThreshold > 0 {
		strategy.ZscoreThreshold = req.ZscoreThreshold
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
