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
		group.DELETE("/market-filters/key/:provider", handler.DeleteKey)
		group.POST("/market-filters/select", func(c *gin.Context) {
			payload, err := apiClient.GetPerpetualMarkets(0)
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
