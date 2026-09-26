// Package routes provides HTTP route registration and handlers for the dYdX backend API AI market features.
package routes

import (
	"net/http"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func RegisterAIMarketRoutes(router *gin.Engine, database *db.Database, apiClient *services.BotAPIClient) {
	credentialRepo := repository.NewExternalAPICredentialRepository(database.DB)
	credentialService := services.NewExternalAPICredentialService(credentialRepo)
	aiService := services.NewAIMarketService(credentialService)
	handler := handlers.NewAIMarketHandler(aiService)

	group := router.Group("/api/v1/ai")
	group.Use(middleware.RequireAuth())
	{
		group.GET("/market-filters/status", handler.GetStatus)
		group.PUT("/market-filters/key", handler.SaveKey)
		group.PUT("/market-filters/shared-key", handler.SaveSharedKey)
		group.DELETE("/market-filters/key/:provider", handler.DeleteKey)
		group.DELETE("/market-filters/shared-key/:provider", handler.DeleteSharedKey)
		group.POST("/market-filters/select", func(c *gin.Context) {
			if apiClient == nil {
				c.JSON(http.StatusServiceUnavailable, gin.H{
					"success":   false,
					"error":     "bot market client is not configured",
					"timestamp": time.Now().UTC().Format(time.RFC3339),
				})
				return
			}

			// The AI selector ranks the tradable universe: active markets only.
			payload, err := apiClient.GetPerpetualMarkets(0, false)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}

			markets := extractPerpetualMarkets(payload)
			if len(markets) < 2 {
				c.JSON(http.StatusBadGateway, gin.H{
					"success":   false,
					"error":     "dYdX market universe did not return at least two markets",
					"timestamp": time.Now().UTC().Format(time.RFC3339),
				})
				return
			}

			handler.SelectMarkets(c, markets)
		})
		group.POST("/backtests/explain", handler.ExplainBacktest)
		group.POST("/strategies/suggest-params", handler.SuggestStrategyParams)
		group.POST("/runtime/digest", handler.RuntimeDigest)
	}
}

func extractPerpetualMarkets(payload map[string]interface{}) []string {
	if payload == nil {
		return []string{}
	}

	if markets := stringSliceFromAny(payload["markets"]); len(markets) > 0 {
		return markets
	}

	if data, ok := payload["data"].(map[string]interface{}); ok {
		return stringSliceFromAny(data["markets"])
	}

	return []string{}
}

func stringSliceFromAny(value interface{}) []string {
	items, ok := value.([]interface{})
	if !ok {
		if strings, ok := value.([]string); ok {
			return strings
		}
		return []string{}
	}

	result := make([]string, 0, len(items))
	for _, item := range items {
		if market, ok := item.(string); ok && market != "" {
			result = append(result, market)
		}
	}
	return result
}
