package handlers

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"strconv"
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
	status, err := h.service.Status(getUserID(c))
	if err != nil {
		h.respondError(c, err, "Failed to load Codex.io status")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      status,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *CodexHandler) SaveKey(c *gin.Context) {
	var req services.CodexKeyPayload
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	credential, err := h.service.SaveUserKey(getUserID(c), req)
	if err != nil {
		h.respondError(c, err, "Failed to save Codex.io key")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      credential,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *CodexHandler) DeleteKey(c *gin.Context) {
	if err := h.service.DeleteUserKey(getUserID(c)); err != nil {
		h.respondError(c, err, "Failed to delete Codex.io key")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      gin.H{"deleted": true},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *CodexHandler) GetMarketOverview(c *gin.Context) {
	networkID, err := parseOptionalInt(c.DefaultQuery("network", "1"))
	if err != nil || networkID <= 0 {
		h.respondBadRequest(c, "network must be a positive integer")
		return
	}
	limit, err := parseOptionalInt(c.DefaultQuery("limit", "6"))
	if err != nil || limit <= 0 {
		h.respondBadRequest(c, "limit must be a positive integer")
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 15*time.Second)
	defer cancel()

	overview, err := h.service.GetMarketOverview(ctx, getUserID(c), networkID, limit, middleware.GetTraceID(c))
	if err != nil {
		h.respondError(c, err, "Failed to load Codex.io market overview")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      overview,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *CodexHandler) SearchTokens(c *gin.Context) {
	query := c.Query("q")
	limit, err := parseOptionalInt(c.DefaultQuery("limit", "8"))
	if err != nil || limit <= 0 {
		h.respondBadRequest(c, "limit must be a positive integer")
		return
	}

	networkID, err := parseOptionalNullableInt(c.Query("network"))
	if err != nil {
		h.respondBadRequest(c, "network must be a positive integer")
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 15*time.Second)
	defer cancel()

	results, err := h.service.SearchTokens(ctx, getUserID(c), query, networkID, limit, middleware.GetTraceID(c))
	if err != nil {
		h.respondError(c, err, "Failed to search Codex.io tokens")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: gin.H{
			"results": results,
			"count":   len(results),
			"query":   query,
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *CodexHandler) GetTokenDetail(c *gin.Context) {
	networkID, err := parseOptionalInt(c.Param("network"))
	if err != nil || networkID <= 0 {
		h.respondBadRequest(c, "network must be a positive integer")
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 15*time.Second)
	defer cancel()

	detail, err := h.service.GetTokenDetail(ctx, getUserID(c), networkID, c.Param("address"), middleware.GetTraceID(c))
	if err != nil {
		h.respondError(c, err, "Failed to load Codex.io token detail")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      detail,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *CodexHandler) GetTokenChart(c *gin.Context) {
	networkID, err := parseOptionalInt(c.Param("network"))
	if err != nil || networkID <= 0 {
		h.respondBadRequest(c, "network must be a positive integer")
		return
	}
	points, err := parseOptionalInt(c.DefaultQuery("points", "60"))
	if err != nil || points <= 0 {
		h.respondBadRequest(c, "points must be a positive integer")
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 15*time.Second)
	defer cancel()

	chart, err := h.service.GetTokenChart(
		ctx,
		getUserID(c),
		networkID,
		c.Param("address"),
		c.DefaultQuery("interval", "1d"),
		points,
		middleware.GetTraceID(c),
	)
	if err != nil {
		h.respondError(c, err, "Failed to load Codex.io token chart")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      chart,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *CodexHandler) ResolveAssetsContext(c *gin.Context) {
	var req services.CodexAssetContextRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 20*time.Second)
	defer cancel()

	response, err := h.service.ResolveAssetsContext(ctx, getUserID(c), req, middleware.GetTraceID(c))
	if err != nil {
		h.respondError(c, err, "Failed to resolve Codex.io asset context")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      response,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *CodexHandler) respondBadRequest(c *gin.Context, message string) {
	c.JSON(http.StatusBadRequest, APIResponse{
		Success:   false,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Error:     message,
	})
}

func (h *CodexHandler) respondError(c *gin.Context, err error, fallback string) {
	statusCode := http.StatusBadGateway
	message := fallback
	if err != nil {
		message = err.Error()
	}

	var serviceErr *services.CodexServiceError
	if errors.As(err, &serviceErr) {
		statusCode = serviceErr.StatusCode()
		message = serviceErr.Message
	}

	c.JSON(statusCode, APIResponse{
		Success:   false,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Error:     message,
	})
}

func getUserID(c *gin.Context) int {
	value, exists := c.Get("user_id")
	if !exists {
		return 0
	}
	userID, ok := value.(int)
	if !ok {
		return 0
	}
	return userID
}

func parseOptionalInt(raw string) (int, error) {
	value, err := strconv.Atoi(raw)
	if err != nil {
		return 0, err
	}
	return value, nil
}

func parseOptionalNullableInt(raw string) (*int, error) {
	if raw == "" {
		return nil, nil
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return nil, err
	}
	return &value, nil
}
