package handlers

import (
	"fmt"
	"net/http"
	"strconv"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

// PairStorageHandler handles pair storage endpoints
type PairStorageHandler struct {
	storage *services.PairStorageManager
}

// NewPairStorageHandler creates a new pair storage handler
func NewPairStorageHandler() *PairStorageHandler {
	return &PairStorageHandler{
		storage: services.GetPairStorage(),
	}
}

// SavePairs saves cointegration analysis results
func (h *PairStorageHandler) SavePairs(c *gin.Context) {
	var pairs []services.CointegrationResult

	if err := c.ShouldBindJSON(&pairs); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request body: %v", err),
		})
		return
	}

	if len(pairs) == 0 {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "No pairs provided",
		})
		return
	}

	result, err := h.storage.SavePairs(pairs)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to save pairs: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"result":          result,
			"pairs_saved":     len(pairs),
			"high_confidence": 0,
			"message":         "Pairs saved successfully",
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// LoadPairs loads stored cointegration results
func (h *PairStorageHandler) LoadPairs(c *gin.Context) {
	pairs, err := h.storage.LoadPairs()
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to load pairs: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"pairs": pairs,
			"count": len(pairs),
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetBestPairs returns top pairs by confidence score
func (h *PairStorageHandler) GetBestPairs(c *gin.Context) {
	limitStr := c.DefaultQuery("limit", "10")
	limit, _ := strconv.Atoi(limitStr)
	if limit > 100 {
		limit = 100
	}
	if limit < 1 {
		limit = 10
	}

	pairs, err := h.storage.GetBestPairs(limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get best pairs: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"pairs": pairs,
			"count": len(pairs),
			"limit": limit,
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetHighConfidencePairs returns only high-confidence pairs (score >= 0.7)
func (h *PairStorageHandler) GetHighConfidencePairs(c *gin.Context) {
	pairs, err := h.storage.GetHighConfidencePairs()
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get high confidence pairs: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"pairs": pairs,
			"count": len(pairs),
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetPairByMarkets gets a specific pair by market symbols
func (h *PairStorageHandler) GetPairByMarkets(c *gin.Context) {
	baseMarket := c.Query("base_market")
	quoteMarket := c.Query("quote_market")

	if baseMarket == "" || quoteMarket == "" {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "base_market and quote_market are required",
		})
		return
	}

	pair, err := h.storage.GetPairByMarkets(baseMarket, quoteMarket)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get pair: %v", err),
		})
		return
	}

	if pair == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Pair %s/%s not found", baseMarket, quoteMarket),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      pair,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetStorageInfo returns storage statistics
func (h *PairStorageHandler) GetStorageInfo(c *gin.Context) {
	info := h.storage.GetStorageInfo()

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      info,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// CalculateConfidence calculates confidence score for a pair
func (h *PairStorageHandler) CalculateConfidence(c *gin.Context) {
	var req struct {
		PValue        float64 `json:"p_value"`
		HalfLife      float64 `json:"half_life"`
		ZeroCrossings int     `json:"zero_crossings"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request body: %v", err),
		})
		return
	}

	confidence := services.CalculateConfidenceScore(req.PValue, req.HalfLife, req.ZeroCrossings)

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"confidence_score":   confidence,
			"is_high_confidence": confidence >= 0.7,
			"p_value":            req.PValue,
			"half_life":          req.HalfLife,
			"zero_crossings":     req.ZeroCrossings,
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}
