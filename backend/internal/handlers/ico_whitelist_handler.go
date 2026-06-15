package handlers

import (
	"context"
	"net/http"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

type ICOWhitelistHandler struct {
	service *services.ICOWhitelistService
}

func NewICOWhitelistHandler(service *services.ICOWhitelistService) *ICOWhitelistHandler {
	return &ICOWhitelistHandler{service: service}
}

func (h *ICOWhitelistHandler) Submit(c *gin.Context) {
	var req services.ICOWhitelistSubmitRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Invalid whitelist request.",
		})
		return
	}

	result, err := h.service.Submit(c.Request.Context(), req)
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
		Data:      result,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *ICOWhitelistHandler) Confirm(c *gin.Context) {
	token := c.Query("token")
	if token == "" {
		var req struct {
			Token string `json:"token"`
		}
		_ = c.ShouldBindJSON(&req)
		token = req.Token
	}

	result, err := h.service.Confirm(c.Request.Context(), token)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Confirmation could not be processed.",
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   result.Confirmed,
		Data:      result,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *ICOWhitelistHandler) Unsubscribe(c *gin.Context) {
	h.handleTokenAction(c, h.service.Unsubscribe, "Unsubscribe could not be processed.")
}

func (h *ICOWhitelistHandler) Withdraw(c *gin.Context) {
	h.handleTokenAction(c, h.service.Withdraw, "Withdrawal could not be processed.")
}

func (h *ICOWhitelistHandler) handleTokenAction(
	c *gin.Context,
	action func(ctx context.Context, token string) (*services.ICOTokenActionResponse, error),
	failureMessage string,
) {
	token := c.Query("token")
	if token == "" {
		var req struct {
			Token string `json:"token"`
		}
		_ = c.ShouldBindJSON(&req)
		token = req.Token
	}

	result, err := action(c.Request.Context(), token)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     failureMessage,
		})
		return
	}
	c.JSON(http.StatusOK, APIResponse{
		Success:   result.Completed,
		Data:      result,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}
