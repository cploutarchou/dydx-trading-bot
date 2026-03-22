package handlers

import (
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func extractAuthToken(c *gin.Context) string {
	authHeader := strings.TrimSpace(c.GetHeader("Authorization"))
	if authHeader != "" {
		if strings.HasPrefix(strings.ToLower(authHeader), "bearer ") {
			return strings.TrimSpace(authHeader[7:])
		}
		return authHeader
	}

	if cookieToken, err := c.Cookie("access_token"); err == nil {
		return strings.TrimSpace(cookieToken)
	}

	return ""
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

// ListBotInstances retrieves all bot instances for the current user
func (h *BotInstanceHandler) ListBotInstances(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// GetBotInstance retrieves a specific bot instance
func (h *BotInstanceHandler) GetBotInstance(c *gin.Context) {
	instanceID := c.Param("instance_id")

	instance, err := h.repo.GetBotInstanceByInstanceID(instanceID)
	if err != nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Bot instance not found: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      instance,
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// CreateBotInstance creates a new bot instance
func (h *BotInstanceHandler) CreateBotInstance(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "User ID not found in context",
		})
		return
	}

	var req struct {
		InstanceID    string                 `json:"instance_id" binding:"required"`
		InstanceName  string                 `json:"instance_name" binding:"required"`
		Network       string                 `json:"network"` // testnet or mainnet
		Strategy      string                 `json:"strategy"`
		Config        map[string]interface{} `json:"config"`
		TradingParams map[string]interface{} `json:"trading_params"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	if req.Network == "" {
		req.Network = "testnet"
	}
	if req.Strategy == "" {
		req.Strategy = "default"
	}

	instance := &models.BotInstance{
		InstanceID:   req.InstanceID,
		InstanceName: req.InstanceName,
		UserID:       userID.(int),
		Status:       "stopped",
		Network:      req.Network,
		Strategy:     req.Strategy,
	}

	if err := h.service.CreateBotInstance(instance); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to create bot instance: %v", err),
		})
		return
	}

	c.JSON(http.StatusCreated, APIResponse{
		Success:   true,
		Data:      instance,
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// StartBotInstance starts a bot instance
func (h *BotInstanceHandler) StartBotInstance(c *gin.Context) {
	instanceID := c.Param("instance_id")
	service := h.service.WithAuthToken(extractAuthToken(c))

	if err := service.StartBotInstance(instanceID); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to start bot instance: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      map[string]string{"status": "started"},
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// StopBotInstance stops a bot instance
func (h *BotInstanceHandler) StopBotInstance(c *gin.Context) {
	instanceID := c.Param("instance_id")
	service := h.service.WithAuthToken(extractAuthToken(c))

	if err := service.StopBotInstance(instanceID); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to stop bot instance: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      map[string]string{"status": "stopped"},
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// RestartBotInstance restarts a bot instance
func (h *BotInstanceHandler) RestartBotInstance(c *gin.Context) {
	instanceID := c.Param("instance_id")
	service := h.service.WithAuthToken(extractAuthToken(c))

	if err := service.RestartBotInstance(instanceID); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to restart bot instance: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      map[string]string{"status": "restarted"},
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// DeleteBotInstance deletes a bot instance
func (h *BotInstanceHandler) DeleteBotInstance(c *gin.Context) {
	instanceID := c.Param("instance_id")

	if err := h.service.DeleteBotInstance(instanceID); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to delete bot instance: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      map[string]string{"status": "deleted"},
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// GetBotInstanceStats retrieves statistics for a bot instance
func (h *BotInstanceHandler) GetBotInstanceStats(c *gin.Context) {
	instanceID := c.Param("instance_id")
	service := h.service.WithAuthToken(extractAuthToken(c))

	stats, err := service.GetBotInstanceStats(instanceID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to get bot instance stats: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      stats,
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// GetBotInstanceTrades retrieves trades for a bot instance
func (h *BotInstanceHandler) GetBotInstanceTrades(c *gin.Context) {
	instanceID := c.Param("instance_id")
	service := h.service.WithAuthToken(extractAuthToken(c))

	limit := 100
	offset := 0
	winningOnly := false

	if limitStr := c.Query("limit"); limitStr != "" {
		if l, err := strconv.Atoi(limitStr); err == nil && l > 0 {
			limit = l
		}
	}

	if offsetStr := c.Query("offset"); offsetStr != "" {
		if o, err := strconv.Atoi(offsetStr); err == nil && o >= 0 {
			offset = o
		}
	}

	if winningStr := c.Query("winning_only"); winningStr == "true" {
		winningOnly = true
	}

	trades, err := service.GetBotInstanceTrades(instanceID, limit, offset, winningOnly)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to get bot instance trades: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      trades,
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}
