package handlers

import (
	"fmt"
	"net/http"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

type TelegramHandler struct {
	service *services.TelegramService
}

func NewTelegramHandler(service *services.TelegramService) *TelegramHandler {
	return &TelegramHandler{service: service}
}

func (h *TelegramHandler) GetStatus(c *gin.Context) {
	targetUserID, ok := resolveTelegramScopeUserID(c)
	if !ok {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Unauthorized",
		})
		return
	}

	status, err := h.service.GetStatusForUser(targetUserID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to load Telegram status: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      status,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *TelegramHandler) SaveConfig(c *gin.Context) {
	targetUserID, ok := resolveTelegramScopeUserID(c)
	if !ok {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Unauthorized",
		})
		return
	}

	var req services.TelegramConfigPayload
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	status, err := h.service.SaveConfigForUser(targetUserID, req)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to save Telegram config: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      status,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *TelegramHandler) DeleteConfig(c *gin.Context) {
	targetUserID, ok := resolveTelegramScopeUserID(c)
	if !ok {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Unauthorized",
		})
		return
	}

	if err := h.service.DeleteConfigForUser(targetUserID); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to delete Telegram config: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      gin.H{"deleted": true},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func resolveTelegramScopeUserID(c *gin.Context) (int, bool) {
	userID := getUserID(c)
	if userID <= 0 {
		return 0, false
	}

	if c.GetBool("is_admin") {
		return services.SharedCredentialUserID, true
	}

	return userID, true
}
