package handlers

import (
	"database/sql"
	"encoding/json"
	"fmt"
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
	serviceTokenMode := strings.EqualFold(strings.TrimSpace(os.Getenv("BOT_API_USE_SERVICE_TOKEN")), "true")
	serviceTokenConfigured := strings.TrimSpace(os.Getenv("BOT_API_TOKEN")) != ""

	if serviceTokenMode && serviceTokenConfigured {
		return ""
	}

	return middleware.ExtractRequestAccessToken(c)
}

type BotInstanceHandler struct {
	service *services.BotInstanceService
	repo    *repository.BotInstanceRepository
}

func NewBotInstanceHandler(service *services.BotInstanceService, repo *repository.BotInstanceRepository) *BotInstanceHandler {
	return &BotInstanceHandler{
		service: service,
		repo:    repo,
	}
}

// authorizeInstanceAccess ensures the requesting user can access the target
// bot instance. Legacy compat rows with user_id=0 are allowed.
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
	if instance.UserID > 0 && instance.UserID != userID && !isAdmin {
		c.JSON(http.StatusForbidden, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Forbidden: you do not own this bot instance",
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
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to retrieve bot instances: %v", err),
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

	configJSON, _ := json.Marshal(req.Config)
	tradingParamsJSON, _ := json.Marshal(req.TradingParams)

	instance := &models.BotInstance{
		InstanceID:   req.InstanceID,
		InstanceName: req.InstanceName,
		UserID:       userID.(int),
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

	service := h.service.WithAuthToken(extractAuthToken(c))
	if err := service.CreateBotInstanceWithConfig(instance, createPayload); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to create bot instance: %v", err),
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
	service := h.service.WithAuthToken(extractAuthToken(c))

	if err := service.StartBotInstance(instanceID); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to start bot instance: %v", err),
		})
		return
	}

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
	service := h.service.WithAuthToken(extractAuthToken(c))
	force, _ := strconv.ParseBool(c.DefaultQuery("force", "false"))

	if err := service.StopBotInstanceWithForce(instanceID, force); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to stop bot instance: %v", err),
		})
		return
	}

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
	service := h.service.WithAuthToken(extractAuthToken(c))

	if err := service.RestartBotInstance(instanceID); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to restart bot instance: %v", err),
		})
		return
	}

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

	if err := h.service.DeleteBotInstance(instanceID); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to delete bot instance: %v", err),
		})
		return
	}

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
	service := h.service.WithAuthToken(extractAuthToken(c))

	stats, err := service.GetBotInstanceStats(instanceID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get bot instance stats: %v", err),
		})
		return
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
	service := h.service.WithAuthToken(extractAuthToken(c))
	statusRaw := strings.TrimSpace(c.Query("status"))
	var status *string
	if statusRaw != "" {
		status = &statusRaw
	}

	trades, err := service.GetBotInstanceTrades(instanceID, status)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get bot instance trades: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      trades,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}
