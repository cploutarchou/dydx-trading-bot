package handlers

import (
	"fmt"
	"net/http"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

type MailgunHandler struct {
	service *services.MailgunService
}

func NewMailgunHandler(service *services.MailgunService) *MailgunHandler {
	return &MailgunHandler{service: service}
}

func (h *MailgunHandler) GetStatus(c *gin.Context) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Admin access required",
		})
		return
	}

	status, err := h.service.GetStatus()
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to load Mailgun status: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      status,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *MailgunHandler) SaveConfig(c *gin.Context) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Admin access required",
		})
		return
	}

	var req services.MailgunConfigPayload
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	status, err := h.service.SaveSharedConfig(req)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to save Mailgun config: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      status,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *MailgunHandler) DeleteConfig(c *gin.Context) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Admin access required",
		})
		return
	}

	if err := h.service.DeleteSharedConfig(); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to delete Mailgun config: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      gin.H{"deleted": true},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}
