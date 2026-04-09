package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

// StrategyHandler handles strategy API endpoints
type StrategyHandler struct {
	service        *services.StrategyService
	runtimeService *services.StrategyRuntimeService
}

type strategyPayload struct {
	Name                   string  `json:"name" binding:"required"`
	Description            string  `json:"description"`
	Category               string  `json:"category"`
	IsPublic               bool    `json:"is_public"`
	IsDefault              bool    `json:"is_default"`
	RuntimeStrategy        string  `json:"runtime_strategy"`
	RuntimeNetwork         string  `json:"runtime_network"`
	RuntimeSubaccount      *int    `json:"runtime_subaccount"`
	PairSelectionMode      string  `json:"pair_selection_mode"`
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
	StartingBalance        float64 `json:"starting_balance"`
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
	if strings.TrimSpace(req.RuntimeStrategy) != "" {
		strategy.RuntimeStrategy = strings.TrimSpace(req.RuntimeStrategy)
	}
	if strings.TrimSpace(req.RuntimeNetwork) != "" {
		strategy.RuntimeNetwork = normalizeRuntimeNetwork(req.RuntimeNetwork)
	}
	if req.RuntimeSubaccount != nil && *req.RuntimeSubaccount >= 0 {
		strategy.RuntimeSubaccount = *req.RuntimeSubaccount
	}
	if strings.TrimSpace(req.PairSelectionMode) != "" {
		strategy.PairSelectionMode = normalizePairSelectionMode(req.PairSelectionMode)
	}

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
	if req.StartingBalance > 0 {
		strategy.StartingBalance = req.StartingBalance
		if strategy.InitialAmount <= 0 {
			strategy.InitialAmount = req.StartingBalance
		}
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
	if strategy.RuntimeStrategy == "" {
		strategy.RuntimeStrategy = "cointegration"
	}
	if strategy.RuntimeNetwork == "" {
		strategy.RuntimeNetwork = "testnet"
	}
	if strategy.PairSelectionMode == "" {
		strategy.PairSelectionMode = "liquidity"
	}
	if strategy.RuntimeSubaccount < 0 {
		strategy.RuntimeSubaccount = 0
	}
}

func normalizePairSelectionMode(value string) string {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "liquidity", "volume":
		return "liquidity"
	case "volatility":
		return "volatility"
	case "cointegration":
		return "cointegration"
	case "input", "none", "order":
		return "input"
	default:
		return "liquidity"
	}
}

func normalizeRuntimeNetwork(value string) string {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "mainnet":
		return "mainnet"
	default:
		return "testnet"
	}
}

// NewStrategyHandler creates a new strategy handler
func NewStrategyHandler(service *services.StrategyService, runtimeService *services.StrategyRuntimeService) *StrategyHandler {
	return &StrategyHandler{
		service:        service,
		runtimeService: runtimeService,
	}
}

// CreateStrategy creates a new strategy
func (h *StrategyHandler) CreateStrategy(c *gin.Context) {
	var req strategyPayload

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
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
		if updateErr := h.service.UpdateStrategy(strategy); updateErr != nil {
			// Rollback: delete the orphaned strategy record.
			_ = h.service.DeleteStrategy(strategy.ID)
			err = updateErr
		}
	}

	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to create strategy: %v", err),
		})
		return
	}

	c.JSON(http.StatusCreated, APIResponse{
		Success:   true,
		Data:      strategy.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetStrategy retrieves a strategy by ID
func (h *StrategyHandler) GetStrategy(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Invalid strategy ID",
		})
		return
	}

	strategy, err := h.service.GetStrategy(id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get strategy: %v", err),
		})
		return
	}

	if strategy == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Strategy not found",
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      strategy.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// ListStrategies lists all strategies for the user
func (h *StrategyHandler) ListStrategies(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Unauthorized",
		})
		return
	}

	strategies, err := h.service.ListStrategies(userID.(int))
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to list strategies: %v", err),
		})
		return
	}

	result := make([]map[string]interface{}, 0)
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
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// UpdateStrategy updates a strategy
func (h *StrategyHandler) UpdateStrategy(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Invalid strategy ID",
		})
		return
	}

	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Unauthorized",
		})
		return
	}

	var req strategyPayload

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	strategy, err := h.service.GetStrategy(id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get strategy: %v", err),
		})
		return
	}

	if strategy == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Strategy not found",
		})
		return
	}

	// Ownership guard: only the owner or an admin may update.
	isAdmin, _ := c.Get("is_admin")
	if strategy.UserID != userID.(int) && isAdmin != true {
		c.JSON(http.StatusForbidden, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Forbidden: you do not own this strategy",
		})
		return
	}

	applyStrategyPayload(strategy, req)

	if err := h.service.UpdateStrategy(strategy); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to update strategy: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      strategy.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// DeleteStrategy deletes a strategy
func (h *StrategyHandler) DeleteStrategy(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Invalid strategy ID",
		})
		return
	}

	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Unauthorized",
		})
		return
	}

	// Fetch strategy to enforce ownership before deletion.
	strategy, err := h.service.GetStrategy(id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get strategy: %v", err),
		})
		return
	}
	if strategy == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Strategy not found",
		})
		return
	}

	// Ownership guard: only the owner or an admin may delete.
	isAdmin, _ := c.Get("is_admin")
	if strategy.UserID != userID.(int) && isAdmin != true {
		c.JSON(http.StatusForbidden, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Forbidden: you do not own this strategy",
		})
		return
	}

	if err := h.service.DeleteStrategy(id); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to delete strategy: %v", err),
		})
		return
	}

	c.Status(http.StatusNoContent)
}

func (h *StrategyHandler) GetStrategyRuntime(c *gin.Context) {
	strategy, _, ok := h.getAuthorizedStrategy(c)
	if !ok {
		return
	}

	runtimeState, err := h.runtimeService.WithTraceID(middleware.GetTraceID(c)).WithAuthToken(extractAuthToken(c)).GetRuntimeStatus(strategy)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get strategy runtime: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      runtimeState,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *StrategyHandler) GetStrategyStartReadiness(c *gin.Context) {
	strategy, _, ok := h.getAuthorizedStrategy(c)
	if !ok {
		return
	}

	readiness, err := h.runtimeService.WithTraceID(middleware.GetTraceID(c)).WithAuthToken(extractAuthToken(c)).GetRuntimeStartReadiness(strategy, c.Query("network"))
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to evaluate strategy runtime readiness: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      readiness,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *StrategyHandler) StartStrategyRuntime(c *gin.Context) {
	strategy, _, ok := h.getAuthorizedStrategy(c)
	if !ok {
		return
	}

	forceRecreate, _ := strconv.ParseBool(c.DefaultQuery("force_recreate", "false"))
	runtimeService := h.runtimeService.WithTraceID(middleware.GetTraceID(c)).WithAuthToken(extractAuthToken(c))
	var (
		runtimeState map[string]interface{}
		err          error
	)
	if forceRecreate {
		runtimeState, err = runtimeService.StartRuntimeWithForceRecreate(strategy, c.Query("network"))
	} else {
		runtimeState, err = runtimeService.StartRuntime(strategy, c.Query("network"))
	}
	if err != nil {
		normalizedErr := strings.ToLower(err.Error())
		statusCode := http.StatusInternalServerError
		errorMessage := fmt.Sprintf("Failed to start strategy runtime: %v", err)
		if strings.Contains(normalizedErr, "active dydx key") || strings.Contains(normalizedErr, "no active dydx key") {
			statusCode = http.StatusBadRequest
		} else if strings.Contains(normalizedErr, "runtime readiness failed") || strings.Contains(normalizedErr, "failed to validate runtime readiness") {
			statusCode = http.StatusBadRequest
		} else if strings.Contains(normalizedErr, "confirm recreate") || strings.Contains(normalizedErr, "instance_id already exists") {
			statusCode = http.StatusConflict
			if !strings.Contains(normalizedErr, "confirm recreate") {
				errorMessage = fmt.Sprintf(
					"Failed to start strategy runtime: stale runtime instance detected; confirm recreate to replace it (%v)",
					err,
				)
			}
		}
		c.JSON(statusCode, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     errorMessage,
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      runtimeState,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *StrategyHandler) StopStrategyRuntime(c *gin.Context) {
	strategy, _, ok := h.getAuthorizedStrategy(c)
	if !ok {
		return
	}

	force, _ := strconv.ParseBool(c.DefaultQuery("force", "false"))
	runtimeState, err := h.runtimeService.WithTraceID(middleware.GetTraceID(c)).WithAuthToken(extractAuthToken(c)).StopRuntime(strategy, force)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to stop strategy runtime: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      runtimeState,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *StrategyHandler) GetVersionHistory(c *gin.Context) {
	strategy, _, ok := h.getAuthorizedStrategy(c)
	if !ok {
		return
	}

	history, err := h.service.GetVersionHistory(strategy.ID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get strategy version history: %v", err),
		})
		return
	}

	versions := make([]map[string]interface{}, 0, len(history))
	for _, version := range history {
		config := map[string]interface{}{}
		if version.StrategyData.Valid && strings.TrimSpace(version.StrategyData.String) != "" {
			if err := json.Unmarshal([]byte(version.StrategyData.String), &config); err != nil {
				config = map[string]interface{}{}
			}
		}

		name := strategy.Name
		if value, ok := config["name"].(string); ok && strings.TrimSpace(value) != "" {
			name = strings.TrimSpace(value)
		}

		description := strategy.Description
		if value, ok := config["description"].(string); ok && strings.TrimSpace(value) != "" {
			description = strings.TrimSpace(value)
		}
		if description == "" {
			description = version.ChangeLog
		}

		versions = append(versions, map[string]interface{}{
			"id":                 version.ID,
			"version_number":     version.Version,
			"name":               name,
			"description":        description,
			"config":             config,
			"changed_fields":     []string{},
			"change_reason":      version.ChangeLog,
			"created_at":         version.CreatedAt,
			"created_by_user_id": version.CreatedByUserID,
		})
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"versions": versions,
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *StrategyHandler) RevertVersion(c *gin.Context) {
	strategy, _, ok := h.getAuthorizedStrategy(c)
	if !ok {
		return
	}

	versionID, err := strconv.Atoi(c.Param("version_id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Invalid version ID",
		})
		return
	}

	history, err := h.service.GetVersionHistory(strategy.ID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get strategy version history: %v", err),
		})
		return
	}

	var target *models.StrategyVersionHistory
	for i := range history {
		if history[i].ID == versionID {
			target = &history[i]
			break
		}
	}
	if target == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Strategy version not found",
		})
		return
	}
	if !target.StrategyData.Valid || strings.TrimSpace(target.StrategyData.String) == "" {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Selected strategy version has no saved configuration snapshot",
		})
		return
	}

	reverted := *strategy
	if err := reverted.FromJSON([]byte(target.StrategyData.String)); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid strategy snapshot: %v", err),
		})
		return
	}

	reverted.ID = strategy.ID
	reverted.UserID = strategy.UserID
	reverted.CreatedAt = strategy.CreatedAt
	reverted.LastUsedAt = strategy.LastUsedAt
	reverted.DeletedAt = strategy.DeletedAt
	reverted.UsageCount = strategy.UsageCount
	if strings.TrimSpace(reverted.RuntimeStrategy) == "" {
		reverted.RuntimeStrategy = "cointegration"
	}
	reverted.PairSelectionMode = normalizePairSelectionMode(reverted.PairSelectionMode)

	if err := h.service.UpdateStrategy(&reverted); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to revert strategy version: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      reverted.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *StrategyHandler) getAuthorizedStrategy(c *gin.Context) (*models.BacktestStrategy, int, bool) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Invalid strategy ID",
		})
		return nil, 0, false
	}

	userIDValue, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Unauthorized",
		})
		return nil, 0, false
	}
	userID := userIDValue.(int)

	strategy, err := h.service.GetStrategy(id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get strategy: %v", err),
		})
		return nil, 0, false
	}
	if strategy == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Strategy not found",
		})
		return nil, 0, false
	}

	if strategy.UserID != userID && !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Forbidden: you do not own this strategy",
		})
		return nil, 0, false
	}

	return strategy, userID, true
}
