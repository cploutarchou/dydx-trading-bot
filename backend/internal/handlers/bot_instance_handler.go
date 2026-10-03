package handlers

import (
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func extractAuthToken(c *gin.Context) string {
	if services.UseConfiguredBotAPIServiceToken() {
		return ""
	}

	return middleware.ExtractRequestAccessToken(c)
}

type BotInstanceHandler struct {
	service      *services.BotInstanceService
	repo         *repository.BotInstanceRepository
	userRepo     *repository.UserRepository
	positionRepo *repository.BotPositionRepository
	botTradeRepo *repository.BotTradeRepository
	cache        *services.CacheService
}

const defaultBotStatsCacheTTLSeconds = 30

func botStatsCacheKey(instanceID string) string {
	return fmt.Sprintf("bot:stats:%s", instanceID)
}

func readBotStatsCacheTTLSeconds() int {
	raw := strings.TrimSpace(os.Getenv("BOT_STATS_CACHE_TTL_SECONDS"))
	if raw == "" {
		return defaultBotStatsCacheTTLSeconds
	}
	parsed, err := strconv.Atoi(raw)
	if err != nil {
		return defaultBotStatsCacheTTLSeconds
	}
	if parsed < 0 {
		return 0
	}
	return parsed
}

func parseLimitOffsetQuery(c *gin.Context, defaultLimit int, maxLimit int) (int, int) {
	limit := defaultLimit

	if pageSizeRaw := strings.TrimSpace(c.Query("page_size")); pageSizeRaw != "" {
		if parsed, err := strconv.Atoi(pageSizeRaw); err == nil && parsed > 0 {
			if parsed > maxLimit {
				parsed = maxLimit
			}
			limit = parsed
		}
	} else if limitRaw := strings.TrimSpace(c.Query("limit")); limitRaw != "" {
		if parsed, err := strconv.Atoi(limitRaw); err == nil && parsed > 0 {
			if parsed > maxLimit {
				parsed = maxLimit
			}
			limit = parsed
		}
	}

	page := 1
	if pageRaw := strings.TrimSpace(c.Query("page")); pageRaw != "" {
		if parsed, err := strconv.Atoi(pageRaw); err == nil && parsed > 0 {
			page = parsed
		}
	}
	offset := (page - 1) * limit

	if offsetRaw := strings.TrimSpace(c.Query("offset")); offsetRaw != "" {
		if parsed, err := strconv.Atoi(offsetRaw); err == nil && parsed >= 0 {
			offset = parsed
		}
	}

	return limit, offset
}

func (h *BotInstanceHandler) invalidateBotStatsCache(instanceID string) {
	if h.cache == nil {
		return
	}

	_ = h.cache.DeleteCache(botStatsCacheKey(instanceID))
	_ = h.cache.DeleteCache(fmt.Sprintf("bot_summary_stats:%s", instanceID))
}

func unwrapBotAPIEnvelope(payload map[string]interface{}) map[string]interface{} {
	if payload == nil {
		return map[string]interface{}{}
	}
	if data, ok := payload["data"].(map[string]interface{}); ok {
		return data
	}
	return payload
}

func buildEmptyBotStatsPayload(instanceID string, warning string) map[string]interface{} {
	payload := map[string]interface{}{
		"instance_id": instanceID,
		"bot_statistics": map[string]interface{}{
			"total_trades":      0,
			"successful_trades": 0,
			"failed_trades":     0,
			"total_profit_loss": 0,
			"win_rate":          0,
			"uptime_seconds":    nil,
		},
		"trade_statistics": map[string]interface{}{
			"total_trades":             0,
			"winning_trades":           0,
			"losing_trades":            0,
			"total_profit":             0,
			"total_loss":               0,
			"net_profit":               0,
			"average_profit":           0,
			"win_rate":                 0,
			"average_duration_seconds": 0,
		},
		"degraded": true,
	}

	if warning != "" {
		payload["warning"] = warning
	}

	return payload
}

func isRecoverableBotStatsError(err error) bool {
	if err == nil {
		return false
	}

	var apiErr *services.BotAPIError
	if errors.As(err, &apiErr) {
		return apiErr.StatusCode == http.StatusNotFound
	}

	var transportErr *services.BotAPITransportError
	if errors.As(err, &transportErr) {
		return true
	}

	message := strings.ToLower(strings.TrimSpace(err.Error()))
	return strings.Contains(message, "not found") ||
		strings.Contains(message, "connection refused") ||
		strings.Contains(message, "timed out") ||
		strings.Contains(message, "not reachable")
}

func NewBotInstanceHandler(
	service *services.BotInstanceService,
	repo *repository.BotInstanceRepository,
	userRepo *repository.UserRepository,
) *BotInstanceHandler {
	return &BotInstanceHandler{
		service:  service,
		repo:     repo,
		userRepo: userRepo,
	}
}

// NewBotInstanceHandlerWithRepos is like NewBotInstanceHandler but also accepts
// the position and trade repositories needed for GetBotPositions and GetBotTrade.
func NewBotInstanceHandlerWithRepos(
	service *services.BotInstanceService,
	repo *repository.BotInstanceRepository,
	userRepo *repository.UserRepository,
	positionRepo *repository.BotPositionRepository,
	botTradeRepo *repository.BotTradeRepository,
) *BotInstanceHandler {
	return &BotInstanceHandler{
		service:      service,
		repo:         repo,
		userRepo:     userRepo,
		positionRepo: positionRepo,
		botTradeRepo: botTradeRepo,
	}
}

// NewBotInstanceHandlerWithCache is like NewBotInstanceHandlerWithRepos but also
// accepts a CacheService for Redis-backed summary caching.
func NewBotInstanceHandlerWithCache(
	service *services.BotInstanceService,
	repo *repository.BotInstanceRepository,
	userRepo *repository.UserRepository,
	positionRepo *repository.BotPositionRepository,
	botTradeRepo *repository.BotTradeRepository,
	cache *services.CacheService,
) *BotInstanceHandler {
	return &BotInstanceHandler{
		service:      service,
		repo:         repo,
		userRepo:     userRepo,
		positionRepo: positionRepo,
		botTradeRepo: botTradeRepo,
		cache:        cache,
	}
}

// authorizeInstanceAccess ensures the requesting user can access the target
// bot instance. Unattributed legacy rows (user_id=0) are admin-only: fail
// closed rather than letting any authenticated user control them.
func (h *BotInstanceHandler) authorizeInstanceAccess(c *gin.Context, instanceID string) (*models.BotInstance, bool) {
	userIDValue, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "User ID not found in context",
		})
		return nil, false
	}

	userID, ok := userIDValue.(int)
	if !ok {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Invalid user context",
		})
		return nil, false
	}

	instance, err := h.repo.GetBotInstanceByInstanceID(instanceID)
	if err != nil || instance == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Bot instance not found",
		})
		return nil, false
	}

	isAdmin := c.GetBool("is_admin")
	if (instance.UserID <= 0 || instance.UserID != userID) && !isAdmin {
		// 404 (matching the delegated tree's ownership middleware) so foreign
		// instance IDs do not disclose existence.
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Bot instance not found",
		})
		return nil, false
	}

	return instance, true
}

// ListBotInstances retrieves all bot instances for the current user
func (h *BotInstanceHandler) ListBotInstances(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "User ID not found in context",
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

	instances, err := h.repo.ListBotInstancesByUserID(userID.(int), limit, skip)
	if err != nil {
		log.Printf("bot_instance_handler: failed to retrieve bot instances: %v", err)
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Failed to retrieve bot instances",
		})
		return
	}

	if instances == nil {
		instances = []models.BotInstance{}
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      instances,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetBotInstance retrieves a specific bot instance
func (h *BotInstanceHandler) GetBotInstance(c *gin.Context) {
	instanceID := c.Param("instance_id")
	instance, ok := h.authorizeInstanceAccess(c, instanceID)
	if !ok {
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      instance,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// CreateBotInstance creates a new bot instance
func (h *BotInstanceHandler) CreateBotInstance(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "User ID not found in context",
		})
		return
	}

	var req struct {
		InstanceID    string                 `json:"instance_id" binding:"required"`
		InstanceName  string                 `json:"instance_name"`
		Network       string                 `json:"network"` // testnet or mainnet
		Strategy      string                 `json:"strategy"`
		Credentials   map[string]interface{} `json:"credentials"`
		Config        map[string]interface{} `json:"config"`
		TradingParams map[string]interface{} `json:"trading_params"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	if req.InstanceName == "" {
		req.InstanceName = req.InstanceID
	}

	if req.Credentials == nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "credentials are required",
		})
		return
	}

	if req.TradingParams == nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "trading_params are required",
		})
		return
	}

	if req.Network == "" {
		if isTestnetRaw, ok := req.TradingParams["is_testnet"]; ok {
			if isTestnet, ok := isTestnetRaw.(bool); ok && !isTestnet {
				req.Network = "mainnet"
			} else {
				req.Network = "testnet"
			}
		} else {
			req.Network = "testnet"
		}
	}
	if req.Strategy == "" {
		req.Strategy = "default"
	}

	userIDInt := userID.(int)
	maxBotInstances := 10
	if h.userRepo != nil {
		if user, userErr := h.userRepo.GetByID(userIDInt); userErr == nil && user != nil && user.MaxBotInstances > 0 {
			maxBotInstances = user.MaxBotInstances
		}
	}
	currentBotInstances, countErr := h.repo.CountBotInstancesByUserID(userIDInt)
	if countErr != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to enforce bot instance quota: %v", countErr),
		})
		return
	}
	if currentBotInstances >= maxBotInstances {
		c.JSON(http.StatusTooManyRequests, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error: fmt.Sprintf(
				"Bot instance limit reached for this account (%d/%d). Ask an admin to increase your bot quota.",
				currentBotInstances,
				maxBotInstances,
			),
		})
		return
	}

	configJSON, _ := json.Marshal(req.Config)
	tradingParamsJSON, _ := json.Marshal(req.TradingParams)

	instance := &models.BotInstance{
		InstanceID:   req.InstanceID,
		InstanceName: req.InstanceName,
		UserID:       userIDInt,
		Status:       "stopped",
		Network:      req.Network,
		Strategy:     req.Strategy,
		Config: sql.NullString{
			String: string(configJSON),
			Valid:  len(configJSON) > 0 && string(configJSON) != "null",
		},
		TradingParams: sql.NullString{
			String: string(tradingParamsJSON),
			Valid:  len(tradingParamsJSON) > 0 && string(tradingParamsJSON) != "null",
		},
	}

	createPayload := map[string]interface{}{
		"instance_id":    req.InstanceID,
		"instance_name":  req.InstanceName,
		"credentials":    req.Credentials,
		"trading_params": req.TradingParams,
	}
	if req.Config != nil {
		createPayload["config"] = req.Config
	}

	service := h.service.WithTraceID(middleware.GetTraceID(c)).WithAuthToken(extractAuthToken(c))
	if err := service.CreateBotInstanceWithConfig(instance, createPayload); err != nil {
		log.Printf("bot_instance_handler: failed to create bot instance: %v", err)
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Failed to create bot instance",
		})
		return
	}

	c.JSON(http.StatusCreated, APIResponse{
		Success:   true,
		Data:      instance,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// StartBotInstance starts a bot instance
func (h *BotInstanceHandler) StartBotInstance(c *gin.Context) {
	instanceID := c.Param("instance_id")
	if _, ok := h.authorizeInstanceAccess(c, instanceID); !ok {
		return
	}
	service := h.service.WithTraceID(middleware.GetTraceID(c)).WithAuthToken(extractAuthToken(c))

	if err := service.StartBotInstance(instanceID); err != nil {
		log.Printf("bot_instance_handler: failed to start bot instance: %v", err)
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Failed to start bot instance",
		})
		return
	}

	h.invalidateBotStatsCache(instanceID)

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      map[string]string{"status": "started"},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// StopBotInstance stops a bot instance
func (h *BotInstanceHandler) StopBotInstance(c *gin.Context) {
	instanceID := c.Param("instance_id")
	if _, ok := h.authorizeInstanceAccess(c, instanceID); !ok {
		return
	}
	service := h.service.WithTraceID(middleware.GetTraceID(c)).WithAuthToken(extractAuthToken(c))
	force, _ := strconv.ParseBool(c.DefaultQuery("force", "false"))

	if err := service.StopBotInstanceWithForce(instanceID, force); err != nil {
		log.Printf("bot_instance_handler: failed to stop bot instance: %v", err)
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Failed to stop bot instance",
		})
		return
	}

	h.invalidateBotStatsCache(instanceID)

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      map[string]interface{}{"status": "stopped", "force": force},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// RestartBotInstance restarts a bot instance
func (h *BotInstanceHandler) RestartBotInstance(c *gin.Context) {
	instanceID := c.Param("instance_id")
	if _, ok := h.authorizeInstanceAccess(c, instanceID); !ok {
		return
	}
	service := h.service.WithTraceID(middleware.GetTraceID(c)).WithAuthToken(extractAuthToken(c))

	if err := service.RestartBotInstance(instanceID); err != nil {
		log.Printf("bot_instance_handler: failed to restart bot instance: %v", err)
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Failed to restart bot instance",
		})
		return
	}

	h.invalidateBotStatsCache(instanceID)

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      map[string]string{"status": "restarted"},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// DeleteBotInstance deletes a bot instance
func (h *BotInstanceHandler) DeleteBotInstance(c *gin.Context) {
	instanceID := c.Param("instance_id")
	if _, ok := h.authorizeInstanceAccess(c, instanceID); !ok {
		return
	}

	service := h.service.WithTraceID(middleware.GetTraceID(c)).WithAuthToken(extractAuthToken(c))
	if err := service.DeleteBotInstance(instanceID); err != nil {
		log.Printf("bot_instance_handler: failed to delete bot instance: %v", err)
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Failed to delete bot instance",
		})
		return
	}

	h.invalidateBotStatsCache(instanceID)

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      map[string]string{"status": "deleted"},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetBotInstanceStats retrieves statistics for a bot instance
func (h *BotInstanceHandler) GetBotInstanceStats(c *gin.Context) {
	instanceID := c.Param("instance_id")
	if _, ok := h.authorizeInstanceAccess(c, instanceID); !ok {
		return
	}

	statsTTLSeconds := readBotStatsCacheTTLSeconds()
	if h.cache != nil && statsTTLSeconds > 0 {
		if cached, cacheErr := h.cache.GetCache(botStatsCacheKey(instanceID)); cacheErr == nil && cached != nil {
			if cachedMap, ok := cached.(map[string]interface{}); ok {
				c.JSON(http.StatusOK, APIResponse{
					Success:   true,
					Data:      cachedMap,
					Timestamp: time.Now().UTC().Format(time.RFC3339),
				})
				return
			}
		}
	}

	service := h.service.WithTraceID(middleware.GetTraceID(c)).WithAuthToken(extractAuthToken(c))

	stats, err := service.GetBotInstanceStats(instanceID)
	if err != nil {
		if isRecoverableBotStatsError(err) {
			emptyPayload := buildEmptyBotStatsPayload(instanceID, fmt.Sprintf("Runtime stats unavailable: %v", err))
			if h.cache != nil && statsTTLSeconds > 0 {
				_ = h.cache.SetCache(botStatsCacheKey(instanceID), emptyPayload, statsTTLSeconds)
			}
			c.JSON(http.StatusOK, APIResponse{
				Success:   true,
				Data:      emptyPayload,
				Timestamp: time.Now().UTC().Format(time.RFC3339),
			})
			return
		}

		log.Printf("bot_instance_handler: failed to get bot instance stats: %v", err)
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Failed to get bot instance stats",
		})
		return
	}

	if h.cache != nil && statsTTLSeconds > 0 {
		_ = h.cache.SetCache(botStatsCacheKey(instanceID), stats, statsTTLSeconds)
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      stats,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetBotInstanceTrades retrieves trades for a bot instance
func (h *BotInstanceHandler) GetBotInstanceTrades(c *gin.Context) {
	instanceID := c.Param("instance_id")
	if _, ok := h.authorizeInstanceAccess(c, instanceID); !ok {
		return
	}
	limit, offset := parseLimitOffsetQuery(c, 100, 500)
	service := h.service.WithTraceID(middleware.GetTraceID(c)).WithAuthToken(extractAuthToken(c))
	statusRaw := strings.TrimSpace(c.Query("status"))
	var status *string
	if statusRaw != "" {
		status = &statusRaw
	}

	trades, err := service.GetBotInstanceTrades(instanceID, status, &limit, &offset)
	if err != nil {
		log.Printf("bot_instance_handler: failed to get bot instance trades: %v", err)
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Failed to get bot instance trades",
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      unwrapBotAPIEnvelope(trades),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetBotPositions returns positions for a bot instance, optionally filtered by status.
// GET /api/v1/bots/:instance_id/positions?status=open
func (h *BotInstanceHandler) GetBotPositions(c *gin.Context) {
	instanceID := c.Param("instance_id")
	status := c.Query("status")
	limit, offset := parseLimitOffsetQuery(c, 100, 500)

	inst, authorized := h.authorizeInstanceAccess(c, instanceID)
	if !authorized {
		return
	}

	positions, err := h.positionRepo.ListBotPositionsByInstanceID(inst.ID, status, limit, offset)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Error:     err.Error(),
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	data := interface{}(positions)
	if positions == nil {
		data = []interface{}{}
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      data,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetBotTrade returns a single trade by trade_id, scoped to the bot instance.
// GET /api/v1/bots/:instance_id/trades/:trade_id
func (h *BotInstanceHandler) GetBotTrade(c *gin.Context) {
	instanceID := c.Param("instance_id")
	tradeID := c.Param("trade_id")

	inst, authorized := h.authorizeInstanceAccess(c, instanceID)
	if !authorized {
		return
	}

	trade, err := h.botTradeRepo.GetBotTradeByTradeID(tradeID)
	if err != nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Error:     err.Error(),
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}
	if trade.BotInstanceID != inst.ID {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Error:     "trade not found",
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      trade,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetBotSummary returns an aggregate view of a bot instance, combining stats,
// open positions, and recent trades in a single response.
//
// Query params:
//   - include: comma-separated subset of "stats,positions,trades" (default: all)
//   - limit:   max trades/positions to return (default: 20)
func (h *BotInstanceHandler) GetBotSummary(c *gin.Context) {
	instanceID := c.Param("instance_id")
	inst, ok := h.authorizeInstanceAccess(c, instanceID)
	if !ok {
		return
	}

	// Determine which sections to include.
	includeParam := c.DefaultQuery("include", "stats,positions,trades")
	includeSet := map[string]bool{}
	for _, part := range strings.Split(includeParam, ",") {
		includeSet[strings.TrimSpace(part)] = true
	}

	limitStr := c.DefaultQuery("limit", "20")
	limit, err := strconv.Atoi(limitStr)
	if err != nil || limit < 1 || limit > 200 {
		limit = 20
	}

	summary := map[string]interface{}{}

	// ── Stats (from Python bot API, Redis-cached for 30 s) ───────────────────
	if includeSet["stats"] {
		var statsPayload interface{}
		cacheKey := fmt.Sprintf("bot_summary_stats:%s", instanceID)

		if h.cache != nil {
			if cached, cacheErr := h.cache.GetCacheString(cacheKey); cacheErr == nil && cached != "" {
				var parsed interface{}
				if json.Unmarshal([]byte(cached), &parsed) == nil {
					statsPayload = parsed
				}
			}
		}

		if statsPayload == nil {
			svc := h.service.WithTraceID(middleware.GetTraceID(c)).WithAuthToken(extractAuthToken(c))
			stats, statsErr := svc.GetBotInstanceStats(instanceID)
			if statsErr != nil {
				if isRecoverableBotStatsError(statsErr) {
					statsPayload = buildEmptyBotStatsPayload(instanceID, fmt.Sprintf("Runtime stats unavailable: %v", statsErr))
				} else {
					c.JSON(http.StatusInternalServerError, APIResponse{
						Success:   false,
						Timestamp: time.Now().UTC().Format(time.RFC3339),
						Error:     fmt.Sprintf("Failed to get bot instance stats: %v", statsErr),
					})
					return
				}
			} else {
				statsPayload = stats
			}

			if h.cache != nil {
				if raw, marshalErr := json.Marshal(statsPayload); marshalErr == nil {
					_ = h.cache.SetCache(cacheKey, string(raw), 30)
				}
			}
		}

		summary["stats"] = statsPayload
	}

	// ── Positions (from DB) ────────────────────────────────────────────────────
	if includeSet["positions"] && h.positionRepo != nil {
		positions, posErr := h.positionRepo.ListBotPositionsByInstanceID(inst.ID, "", limit, 0)
		if posErr != nil {
			c.JSON(http.StatusInternalServerError, APIResponse{
				Success:   false,
				Timestamp: time.Now().UTC().Format(time.RFC3339),
				Error:     fmt.Sprintf("Failed to get positions: %v", posErr),
			})
			return
		}
		summary["positions"] = positions
	}

	// ── Recent trades (from DB) ───────────────────────────────────────────────
	if includeSet["trades"] && h.botTradeRepo != nil {
		trades, tradesErr := h.botTradeRepo.ListBotTradesByInstanceID(inst.ID, limit, 0)
		if tradesErr != nil {
			c.JSON(http.StatusInternalServerError, APIResponse{
				Success:   false,
				Timestamp: time.Now().UTC().Format(time.RFC3339),
				Error:     fmt.Sprintf("Failed to get trades: %v", tradesErr),
			})
			return
		}
		summary["trades"] = trades
	}

	summary["instance_id"] = instanceID
	summary["generated_at"] = time.Now().UTC().Format(time.RFC3339)

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      summary,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}
