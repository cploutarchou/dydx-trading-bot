package handlers

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

type CodexHandler struct {
	service *services.CodexService
}

func NewCodexHandler(service *services.CodexService) *CodexHandler {
	return &CodexHandler{service: service}
}

func (h *CodexHandler) GetStatus(c *gin.Context) {
	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      h.service.Status(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *CodexHandler) Respond(c *gin.Context) {
	var req services.CodexRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	if !h.service.Status().Configured {
		c.JSON(http.StatusServiceUnavailable, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Codex is not configured on the backend. Set OPENAI_API_KEY to enable it.",
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 50*time.Second)
	defer cancel()

	result, err := h.service.Generate(ctx, middleware.GetTraceID(c), req)
	if err != nil {
		c.JSON(http.StatusBadGateway, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get Codex response: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      result,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}
