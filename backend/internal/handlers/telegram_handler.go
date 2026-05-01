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
	h.GetUserStatus(c)
}

func (h *TelegramHandler) SaveConfig(c *gin.Context) {
	h.SaveUserConfig(c)
}

func (h *TelegramHandler) DeleteConfig(c *gin.Context) {
	h.DeleteUserConfig(c)
}

func (h *TelegramHandler) PreflightValidateTelegramDelivery(c *gin.Context) {
	h.PreflightValidateUserDelivery(c)
}

func (h *TelegramHandler) GetUserStatus(c *gin.Context) {
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

func (h *TelegramHandler) SaveUserConfig(c *gin.Context) {
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

	status, err := h.service.SaveUserConfigForUser(targetUserID, req)
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

func (h *TelegramHandler) DeleteUserConfig(c *gin.Context) {
	targetUserID, ok := resolveTelegramScopeUserID(c)
	if !ok {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Unauthorized",
		})
		return
	}

	if err := h.service.DeleteUserConfigForUser(targetUserID); err != nil {
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

func (h *TelegramHandler) GetGlobalStatus(c *gin.Context) {
	if !requireTelegramAdminRole(c) {
		return
	}

	status, err := h.service.GetGlobalStatus()
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to load global Telegram status: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      status,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *TelegramHandler) SaveGlobalConfig(c *gin.Context) {
	if !requireTelegramAdminRole(c) {
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

	status, err := h.service.SaveGlobalConfig(req)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to save global Telegram config: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      status,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *TelegramHandler) DeleteGlobalConfig(c *gin.Context) {
	if !requireTelegramAdminRole(c) {
		return
	}

	if err := h.service.DeleteGlobalConfig(); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to delete global Telegram config: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      gin.H{"deleted": true},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *TelegramHandler) PreflightValidateUserDelivery(c *gin.Context) {
	targetUserID, ok := resolveTelegramScopeUserID(c)
	if !ok {
		c.JSON(http.StatusUnauthorized, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Unauthorized",
		})
		return
	}

	h.preflightValidateDelivery(c, targetUserID, services.TelegramConfigSourceUser)
}

func (h *TelegramHandler) PreflightValidateGlobalDelivery(c *gin.Context) {
	if !requireTelegramAdminRole(c) {
		return
	}

	h.preflightValidateDelivery(c, services.SharedCredentialUserID, services.TelegramConfigSourceGlobal)
}

func (h *TelegramHandler) preflightValidateDelivery(c *gin.Context, targetUserID int, scope services.TelegramConfigSource) {
	var overrideReq *services.TelegramConfigPayload
	isOverride := false

	// Try to bind JSON body (may be empty or missing)
	if c.ShouldBindJSON(&overrideReq) == nil && overrideReq != nil {
		// Use override if provided in request body
		isOverride = true
	} else {
		// Use saved config
		var config *services.TelegramSharedConfig
		var configured bool
		var err error
		if scope == services.TelegramConfigSourceGlobal {
			config, configured, err = h.service.ResolveGlobalConfig()
		} else {
			resolved, resolveErr := h.service.ResolveEffectiveConfig(targetUserID)
			err = resolveErr
			if resolved != nil && resolved.Config != nil {
				config = resolved.Config
				configured = resolved.Source != services.TelegramConfigSourceNone
			}
		}
		if err != nil {
			c.JSON(http.StatusInternalServerError, APIResponse{
				Success:   false,
				Timestamp: time.Now().UTC().Format(time.RFC3339),
				Error:     fmt.Sprintf("Failed to resolve Telegram config: %v", err),
			})
			return
		}
		if !configured {
			c.JSON(http.StatusBadRequest, APIResponse{
				Success:   false,
				Timestamp: time.Now().UTC().Format(time.RFC3339),
				Error:     "Telegram not configured for this scope",
			})
			return
		}
		overrideReq = &services.TelegramConfigPayload{
			BotToken: config.BotToken,
			ChatID:   config.ChatID,
		}
	}

	// Validate credentials
	result, err := h.service.PreflightValidateTelegramDelivery(overrideReq.BotToken, overrideReq.ChatID)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Telegram validation failed: %v", err),
		})
		return
	}

	// If validation passed and override was provided, save the credentials securely
	if result.Valid && isOverride {
		var saveErr error
		if scope == services.TelegramConfigSourceGlobal {
			_, saveErr = h.service.SaveGlobalConfig(*overrideReq)
		} else {
			_, saveErr = h.service.SaveUserConfigForUser(targetUserID, *overrideReq)
		}
		if saveErr != nil {
			c.JSON(http.StatusInternalServerError, APIResponse{
				Success:   false,
				Timestamp: time.Now().UTC().Format(time.RFC3339),
				Error:     fmt.Sprintf("Telegram validation passed but failed to save: %v", saveErr),
			})
			return
		}
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      result,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func requireTelegramAdminRole(c *gin.Context) bool {
	role := c.GetString("role")
	if !c.GetBool("is_admin") && role != "admin" && role != "backoffice_admin" && role != "super_admin" {
		c.JSON(http.StatusForbidden, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Admin role required for global Telegram settings",
		})
		c.Abort()
		return false
	}
	return true
}

func resolveTelegramScopeUserID(c *gin.Context) (int, bool) {
	userID := getUserID(c)
	if userID <= 0 {
		return 0, false
	}

	return userID, true
}
