package handlers

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

type AIMarketHandler struct {
	service *services.AIMarketService
}

func NewAIMarketHandler(service *services.AIMarketService) *AIMarketHandler {
	return &AIMarketHandler{service: service}
}

func (h *AIMarketHandler) GetStatus(c *gin.Context) {
	status, err := h.service.Status(getUserID(c))
	if err != nil {
		h.respondError(c, http.StatusBadGateway, err, "Failed to load AI provider status")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      status,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *AIMarketHandler) SaveKey(c *gin.Context) {
	var req services.AICredentialPayload
	if err := c.ShouldBindJSON(&req); err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Invalid AI key request")
		return
	}

	credential, err := h.service.SaveUserKey(getUserID(c), req)
	if err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Failed to save AI key")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      credential,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *AIMarketHandler) SaveSharedKey(c *gin.Context) {
	if !c.GetBool("is_admin") {
		h.respondError(c, http.StatusForbidden, errors.New("admin access required"), "Admin access required")
		return
	}

	var req services.AICredentialPayload
	if err := c.ShouldBindJSON(&req); err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Invalid AI key request")
		return
	}

	credential, err := h.service.SaveSharedKey(req)
	if err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Failed to save shared AI key")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      credential,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *AIMarketHandler) DeleteKey(c *gin.Context) {
	provider := c.Param("provider")
	if err := h.service.DeleteUserKey(getUserID(c), provider); err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Failed to delete AI key")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      gin.H{"deleted": true, "provider": provider},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *AIMarketHandler) DeleteSharedKey(c *gin.Context) {
	if !c.GetBool("is_admin") {
		h.respondError(c, http.StatusForbidden, errors.New("admin access required"), "Admin access required")
		return
	}

	provider := strings.TrimSpace(c.Param("provider"))
	if provider == "" {
		h.respondError(c, http.StatusBadRequest, errors.New("provider is required"), "Provider is required")
		return
	}

	if err := h.service.DeleteSharedKey(provider); err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Failed to delete shared AI key")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      gin.H{"deleted": true, "provider": provider},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *AIMarketHandler) SelectMarkets(c *gin.Context, markets []string) {
	var req services.AIMarketSelectionRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Invalid AI market selection request")
		return
	}
	if len(req.Markets) == 0 {
		req.Markets = markets
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 60*time.Second)
	defer cancel()

	result, err := h.service.SelectMarkets(ctx, getUserID(c), req)
	if err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Failed to select dYdX markets with AI")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      result,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *AIMarketHandler) ExplainBacktest(c *gin.Context) {
	var req services.AIBacktestExplainRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Invalid backtest explain request")
		return
	}
	ctx, cancel := context.WithTimeout(c.Request.Context(), 60*time.Second)
	defer cancel()
	result, err := h.service.ExplainBacktest(ctx, getUserID(c), req)
	if err != nil {
		h.respondError(c, http.StatusBadGateway, err, "Failed to explain backtest with AI")
		return
	}
	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      result,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *AIMarketHandler) SuggestStrategyParams(c *gin.Context) {
	var req services.AISuggestParamsRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Invalid parameter suggestion request")
		return
	}
	ctx, cancel := context.WithTimeout(c.Request.Context(), 75*time.Second)
	defer cancel()
	result, err := h.service.SuggestStrategyParams(ctx, getUserID(c), req)
	if err != nil {
		h.respondError(c, http.StatusBadGateway, err, "Failed to suggest strategy parameters with AI")
		return
	}
	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      result,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *AIMarketHandler) RuntimeDigest(c *gin.Context) {
	var req services.AIRuntimeDigestRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Invalid runtime digest request")
		return
	}
	ctx, cancel := context.WithTimeout(c.Request.Context(), 45*time.Second)
	defer cancel()
	result, err := h.service.RuntimeDigest(ctx, getUserID(c), req)
	if err != nil {
		h.respondError(c, http.StatusBadGateway, err, "Failed to generate runtime digest with AI")
		return
	}
	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      result,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *AIMarketHandler) respondError(c *gin.Context, status int, err error, fallback string) {
	message := fallback
	if err != nil {
		message = err.Error()
	}
	var providerErr *services.AIProviderAccessError
	if errors.As(err, &providerErr) {
		status = providerErr.Code
		message = providerErr.Message
	}
	if errors.Is(err, context.DeadlineExceeded) {
		status = http.StatusGatewayTimeout
		message = "AI market selection timed out"
	}
	c.JSON(status, APIResponse{
		Success:   false,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Error:     fmt.Sprintf("%s", message),
	})
}
