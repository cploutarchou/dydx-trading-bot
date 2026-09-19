// Package handlers provides HTTP request handlers for outbound email settings.
package handlers

import (
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

type EmailHandler struct {
	service *services.EmailService
}

func NewEmailHandler(service *services.EmailService) *EmailHandler {
	return &EmailHandler{service: service}
}

type emailTestRequest struct {
	To string `json:"to"`
}

func (h *EmailHandler) requireAdmin(c *gin.Context) bool {
	if c.GetBool("is_admin") {
		return true
	}
	c.JSON(http.StatusForbidden, APIResponse{
		Success:   false,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Error:     "Admin access required",
	})
	return false
}

func (h *EmailHandler) GetStatus(c *gin.Context) {
	if !h.requireAdmin(c) {
		return
	}

	status, err := h.service.GetStatus()
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to load email status: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      status,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *EmailHandler) SaveConfig(c *gin.Context) {
	if !h.requireAdmin(c) {
		return
	}

	var req services.EmailConfigPayload
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request body: %v", err),
		})
		return
	}

	status, err := h.service.SaveSharedConfig(req)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      status,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *EmailHandler) DeleteConfig(c *gin.Context) {
	if !h.requireAdmin(c) {
		return
	}

	if err := h.service.DeleteSharedConfig(); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      gin.H{"removed": true},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// SendTest sends a fixed test message. With no recipient it goes to the
// signed-in admin's own address.
func (h *EmailHandler) SendTest(c *gin.Context) {
	if !h.requireAdmin(c) {
		return
	}

	var req emailTestRequest
	if err := c.ShouldBindJSON(&req); err != nil && c.Request.ContentLength > 0 {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request body: %v", err),
		})
		return
	}
	recipient := strings.TrimSpace(req.To)
	if recipient == "" {
		recipient = strings.TrimSpace(c.GetString("email"))
	}

	result, err := h.service.SendTest(c.Request.Context(), recipient)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     err.Error(),
		})
		return
	}
	if !result.Delivered {
		c.JSON(http.StatusBadGateway, APIResponse{
			Success:   false,
			Data:      result,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     result.Message,
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      result,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}
