package handlers

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

// StrategyHandler handles strategy API endpoints
type StrategyHandler struct {
	service        *services.StrategyService
	runtimeService *services.StrategyRuntimeService
	userRepo       *repository.UserRepository
	auditLogger    StrategyAuditLogger
}

type strategyPayload struct {
	Name                  string    `json:"name" binding:"required"`
	Description           string    `json:"description"`
	Category              string    `json:"category"`
	IsPublic              *bool     `json:"is_public"`
	IsDefault             *bool     `json:"is_default"`
	RuntimeStrategy       string    `json:"runtime_strategy"`
	RuntimeNetwork        string    `json:"runtime_network"`
	RuntimeSubaccount     *int      `json:"runtime_subaccount"`
	PairSelectionMode     string    `json:"pair_selection_mode"`
	SelectedMarkets       *[]string `json:"selected_markets"`
	Resolution            string    `json:"resolution"`
	CandleResolution      string    `json:"candle_resolution"`
	ZscoreThreshold       float64   `json:"zscore_threshold"`
	StatsWindow           int       `json:"stats_window"`
	MaxHalfLife           float64   `json:"max_half_life"`
	UsdPerTrade           float64   `json:"usd_per_trade"`
	UsdMinCollateral      float64   `json:"usd_min_collateral"`
	CloseAtZscoreCross    *bool     `json:"close_at_zscore_cross"`
	FindCointegratedPairs *bool     `json:"find_cointegrated_pairs"`
	ManageExits           *bool     `json:"manage_exits"`
	PlaceTrades           *bool     `json:"place_trades"`
	AbortAllPositions     *bool     `json:"abort_all_positions"`
	// Pointers so an explicit 0 (off) is honoured instead of keeping the
	// stored value: both are enforced by the live runtime when > 0.
	MaxDrawdownPct         *float64 `json:"max_drawdown_pct"`
	StopLossPct            float64  `json:"stop_loss_pct"`
	TakeProfitPct          float64  `json:"take_profit_pct"`
	TrailingStopPct        *float64 `json:"trailing_stop_pct"`
	MaxPositions           int      `json:"max_positions"`
	RebalanceIntervalHours int      `json:"rebalance_interval_hours"`
	PositionTimeoutHours   int      `json:"position_timeout_hours"`
	StartingBalance        float64  `json:"starting_balance"`
	InitialAmount          float64  `json:"initial_amount"`
	TransactionFee         float64  `json:"transaction_fee"`
	Slippage               float64  `json:"slippage"`
	MaxHistoryDays         int      `json:"max_history_days"`
	BenchmarkSymbol        string   `json:"benchmark_symbol"`
	RiskFreeRate           float64  `json:"risk_free_rate"`
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
	if req.IsPublic != nil {
		strategy.IsPublic = *req.IsPublic
	}
	if req.IsDefault != nil {
		strategy.IsDefault = *req.IsDefault
	}
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
	if req.SelectedMarkets != nil {
		strategy.SetSelectedMarketList(*req.SelectedMarkets)
	}

	if strings.TrimSpace(req.CandleResolution) != "" {
		strategy.CandleResolution = normalizeCandleResolution(req.CandleResolution)
	} else if strings.TrimSpace(req.Resolution) != "" {
		strategy.CandleResolution = normalizeCandleResolution(req.Resolution)
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
	if req.MaxDrawdownPct != nil && *req.MaxDrawdownPct >= 0 {
		strategy.MaxDrawdownPct = *req.MaxDrawdownPct
	}
	if req.StopLossPct > 0 {
		strategy.StopLossPct = req.StopLossPct
	}
	if req.TakeProfitPct > 0 {
		strategy.TakeProfitPct = req.TakeProfitPct
	}
	if req.TrailingStopPct != nil && *req.TrailingStopPct >= 0 {
		strategy.TrailingStopPct = *req.TrailingStopPct
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
		if req.StartingBalance <= 0 {
			strategy.StartingBalance = req.InitialAmount
		}
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
	if strings.TrimSpace(strategy.CandleResolution) == "" {
		strategy.CandleResolution = "1HOUR"
	}
}

func normalizeCandleResolution(value string) string {
	switch strings.ToUpper(strings.TrimSpace(value)) {
	case "M1", "1M", "1MIN", "1MINUTE", "1MINUTES":
		return "1MIN"
	case "M5", "5M", "5MIN", "5MINS", "5MINUTE", "5MINUTES":
		return "5MINS"
	case "M15", "15M", "15MIN", "15MINS", "15MINUTE", "15MINUTES":
		return "15MINS"
	case "M30", "30M", "30MIN", "30MINS", "30MINUTE", "30MINUTES":
		return "30MINS"
	case "H1", "1H", "1HR", "1HOUR", "1HOURS":
		return "1HOUR"
	case "H4", "4H", "4HR", "4HOUR", "4HOURS":
		return "4HOURS"
	case "D1", "1D", "1DAY", "1DAYS":
		return "1DAY"
	default:
		return "1HOUR"
	}
}

func boolValue(value *bool) bool {
	return value != nil && *value
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

func parseExplicitRuntimeNetwork(value string) (string, error) {
	normalized := strings.ToLower(strings.TrimSpace(value))
	if normalized == "" {
		return "", fmt.Errorf("runtime network selection is required")
	}
	switch normalized {
	case "testnet", "mainnet":
		return normalized, nil
	default:
		return "", fmt.Errorf("invalid runtime network %q; use testnet or mainnet", value)
	}
}

// NewStrategyHandler creates a new strategy handler
func NewStrategyHandler(
	service *services.StrategyService,
	runtimeService *services.StrategyRuntimeService,
	userRepo *repository.UserRepository,
) *StrategyHandler {
	return &StrategyHandler{
		service:        service,
		runtimeService: runtimeService,
		userRepo:       userRepo,
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

	userIDInt := userID.(int)
	maxStrategies := 10
	if h.userRepo != nil {
		if user, userErr := h.userRepo.GetByID(userIDInt); userErr == nil && user != nil && user.MaxStrategies > 0 {
			maxStrategies = user.MaxStrategies
		}
	}
	currentStrategies, countErr := h.service.ListStrategies(userIDInt)
	if countErr != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to enforce strategy quota: %v", countErr),
		})
		return
	}
	if len(currentStrategies) >= maxStrategies {
		c.JSON(http.StatusTooManyRequests, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error: fmt.Sprintf(
				"Strategy limit reached for this account (%d/%d). Ask an admin to increase your strategy quota.",
				len(currentStrategies),
				maxStrategies,
			),
		})
		return
	}

	strategy, err := h.service.CreateStrategy(
		userIDInt,
		req.Name,
		req.Description,
		req.Category,
		boolValue(req.IsPublic),
		boolValue(req.IsDefault),
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

// maxStrategyRuntimeBatch caps ?ids= on the batch runtime route; each id costs
// the same bot calls as the single route.
const maxStrategyRuntimeBatch = 100

// GetStrategyRuntimes reconciles every strategy in ?ids= and returns their
// runtime states in one response. Ownership is checked per id the same way the
// single-strategy route does, and one foreign id fails the whole request.
func (h *StrategyHandler) GetStrategyRuntimes(c *gin.Context) {
	ids, err := parseStrategyIDList(c.Query("ids"))
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     err.Error(),
		})
		return
	}

	userIDValue, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Unauthorized",
		})
		return
	}
	userID := userIDValue.(int)
	isAdmin := c.GetBool("is_admin")

	strategies := make([]*models.BacktestStrategy, 0, len(ids))
	for _, id := range ids {
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
				Error:     fmt.Sprintf("Strategy %d not found", id),
			})
			return
		}
		if strategy.UserID != userID && !isAdmin {
			c.JSON(http.StatusForbidden, APIResponse{
				Success:   false,
				Timestamp: time.Now().UTC().Format(time.RFC3339),
				Error:     "Forbidden: you do not own this strategy",
			})
			return
		}
		strategies = append(strategies, strategy)
	}

	runtimes := h.runtimeService.WithTraceID(middleware.GetTraceID(c)).WithAuthToken(extractAuthToken(c)).GetRuntimeStatuses(strategies)

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"runtimes": runtimes,
			"count":    len(runtimes),
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// parseStrategyIDList reads a comma-separated list of positive strategy ids,
// deduplicated, and refuses an empty, malformed or oversized list.
func parseStrategyIDList(raw string) ([]int, error) {
	seen := make(map[int]bool)
	ids := make([]int, 0)
	for _, part := range strings.Split(raw, ",") {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		id, err := strconv.Atoi(part)
		if err != nil || id <= 0 {
			return nil, fmt.Errorf("invalid strategy id %q", part)
		}
		if seen[id] {
			continue
		}
		seen[id] = true
		ids = append(ids, id)
		if len(ids) > maxStrategyRuntimeBatch {
			return nil, fmt.Errorf("at most %d strategy ids per request", maxStrategyRuntimeBatch)
		}
	}
	if len(ids) == 0 {
		return nil, fmt.Errorf("ids is required")
	}
	return ids, nil
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

// StrategyAuditLogger records an operator action on a strategy.
type StrategyAuditLogger func(c *gin.Context, action string, strategyID int, details interface{})

// SetAuditLogger wires audit logging for operator actions that change what a
// live runtime will (not) enforce.
func (h *StrategyHandler) SetAuditLogger(logger StrategyAuditLogger) {
	h.auditLogger = logger
}

// disableableRiskControls are operator-set controls that older live runtimes
// rejected when > 0. The current runtime enforces both, so start-readiness no
// longer reports them and the UI no longer offers this action; turning one off
// through the API still happens only as an explicit, acknowledged and audited
// action.
var disableableRiskControls = map[string]func(*models.BacktestStrategy) *float64{
	"max_drawdown_pct":  func(s *models.BacktestStrategy) *float64 { return &s.MaxDrawdownPct },
	"trailing_stop_pct": func(s *models.BacktestStrategy) *float64 { return &s.TrailingStopPct },
}

// DisableUnenforcedRiskControls sets the named unenforced risk controls to 0 on a
// strategy after an explicit operator acknowledgement. It never makes the live
// runtime accept a control it cannot enforce: the strategy simply stops asking
// for it, and the stored strategy shows what will really run.
func (h *StrategyHandler) DisableUnenforcedRiskControls(c *gin.Context) {
	strategy, _, ok := h.getAuthorizedStrategy(c)
	if !ok {
		return
	}

	var req struct {
		Fields       []string `json:"fields"`
		Acknowledged bool     `json:"acknowledged"`
		Network      string   `json:"network"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}
	if !req.Acknowledged {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "acknowledged must be true: confirm that the live bot will run without these risk controls",
		})
		return
	}
	if len(req.Fields) == 0 {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "fields must name at least one risk control to turn off",
		})
		return
	}

	seen := make(map[string]struct{}, len(req.Fields))
	fields := make([]string, 0, len(req.Fields))
	for _, rawField := range req.Fields {
		field := strings.ToLower(strings.TrimSpace(rawField))
		if _, allowed := disableableRiskControls[field]; !allowed {
			c.JSON(http.StatusBadRequest, APIResponse{
				Success:   false,
				Timestamp: time.Now().UTC().Format(time.RFC3339),
				Error:     fmt.Sprintf("%q cannot be turned off here; allowed: max_drawdown_pct, trailing_stop_pct", rawField),
			})
			return
		}
		if _, duplicate := seen[field]; duplicate {
			continue
		}
		seen[field] = struct{}{}
		fields = append(fields, field)
	}

	disabled := make([]map[string]interface{}, 0, len(fields))
	for _, field := range fields {
		value := disableableRiskControls[field](strategy)
		disabled = append(disabled, map[string]interface{}{
			"field":          field,
			"previous_value": *value,
		})
		*value = 0
	}

	if err := h.service.UpdateStrategy(strategy); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to update strategy: %v", err),
		})
		return
	}

	if h.auditLogger != nil {
		h.auditLogger(c, "strategy.risk_controls.disable_unenforced", strategy.ID, gin.H{
			"strategy_name":          strategy.Name,
			"network":                strings.ToLower(strings.TrimSpace(req.Network)),
			"disabled_risk_controls": disabled,
			"acknowledged":           true,
		})
	}

	data := strategy.ToDict()
	data["disabled_risk_controls"] = disabled
	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      data,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// entryHaltNoteMaxLength matches the bot API's limit on the clear note.
const entryHaltNoteMaxLength = 500

// GetStrategyEntryHalt reports whether the bot has halted new entries on the
// subaccount this strategy trades on.
func (h *StrategyHandler) GetStrategyEntryHalt(c *gin.Context) {
	strategy, _, ok := h.getAuthorizedStrategy(c)
	if !ok {
		return
	}

	state, err := h.runtimeService.WithTraceID(middleware.GetTraceID(c)).WithAuthToken(extractAuthToken(c)).GetRuntimeEntryHalt(strategy)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get strategy entry halt: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      state,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// ClearStrategyEntryHalt lets the bot resume opening pairs. The halt means a leg
// may be open without its hedge, so it is cleared only through this explicit,
// acknowledged and audited action, never as a side effect of another request.
func (h *StrategyHandler) ClearStrategyEntryHalt(c *gin.Context) {
	strategy, _, ok := h.getAuthorizedStrategy(c)
	if !ok {
		return
	}

	var req struct {
		Acknowledged bool   `json:"acknowledged"`
		Note         string `json:"note"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}
	if !req.Acknowledged {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "acknowledged must be true: confirm the account was checked on the exchange and no position is left without its hedge",
		})
		return
	}
	note := strings.TrimSpace(req.Note)
	if len([]rune(note)) > entryHaltNoteMaxLength {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("note must be at most %d characters", entryHaltNoteMaxLength),
		})
		return
	}

	// The operator is taken from the session, never from the request body.
	clearedBy := strings.TrimSpace(c.GetString("username"))
	if clearedBy == "" {
		clearedBy = fmt.Sprintf("user:%d", c.GetInt("user_id"))
	}

	result, err := h.runtimeService.WithTraceID(middleware.GetTraceID(c)).WithAuthToken(extractAuthToken(c)).ClearRuntimeEntryHalt(strategy, clearedBy, note)
	if err != nil {
		statusCode := http.StatusInternalServerError
		if errors.Is(err, services.ErrStrategyRuntimeNotFound) {
			statusCode = http.StatusNotFound
		}
		c.JSON(statusCode, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to clear strategy entry halt: %v", err),
		})
		return
	}

	if h.auditLogger != nil {
		h.auditLogger(c, "strategy.entry_halt.clear", strategy.ID, gin.H{
			"strategy_name": strategy.Name,
			"cleared":       result["cleared"],
			"note":          note,
			"acknowledged":  true,
		})
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      result,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *StrategyHandler) StartStrategyRuntime(c *gin.Context) {
	strategy, userID, ok := h.getAuthorizedStrategy(c)
	if !ok {
		return
	}

	// P1.8: Basic subscription check for live feature access
	// Note: Full subscription validation would require querying DB for subscription status
	// For now, we gate based on userID presence (always allowed) with future DB lookup
	_ = userID // Used for future subscription lookup

	runtimeNetwork, parseErr := parseExplicitRuntimeNetwork(c.Query("network"))
	if parseErr != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid runtime network selection: %v", parseErr),
		})
		return
	}

	forceRecreate, _ := strconv.ParseBool(c.DefaultQuery("force_recreate", "false"))
	runtimeService := h.runtimeService.WithTraceID(middleware.GetTraceID(c)).WithAuthToken(extractAuthToken(c))
	var (
		runtimeState map[string]interface{}
		err          error
	)
	if forceRecreate {
		runtimeState, err = runtimeService.StartRuntimeWithForceRecreate(strategy, runtimeNetwork)
	} else {
		runtimeState, err = runtimeService.StartRuntime(strategy, runtimeNetwork)
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
