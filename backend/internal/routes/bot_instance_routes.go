// Package routes provides HTTP route registration and handlers for the dYdX backend API bot instance features.
package routes

import (
	"os"

	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func RegisterBotInstanceRoutes(router *gin.Engine, database *db.Database, cache *services.CacheService) {
	botInstanceRepo := repository.NewBotInstanceRepository(database.DB)
	userRepo := repository.NewUserRepository(database.DB)
	botTradeRepo := repository.NewBotTradeRepository(database.DB)
	botPositionRepo := repository.NewBotPositionRepository(database.DB)

	// Initialize bot API client
	botAPIURL := os.Getenv("BOT_API_URL")
	if botAPIURL == "" {
		botAPIURL = "http://127.0.0.1:8889"
	}
	botAPIToken := os.Getenv("BOT_API_TOKEN")
	botAPIClient := services.NewBotAPIClient(botAPIURL, botAPIToken)

	botInstanceService := services.NewBotInstanceService(botInstanceRepo, botAPIClient)
	botInstanceHandler := handlers.NewBotInstanceHandlerWithCache(botInstanceService, botInstanceRepo, userRepo, botPositionRepo, botTradeRepo, cache)

	v1 := router.Group("/api/v1")
	{
		bots := v1.Group("/bots")
		{
			// Require authentication for all bot routes
			bots.Use(middleware.RequireAuth())

			// List all bot instances for current user
			bots.GET("", botInstanceHandler.ListBotInstances)

			// Create a new bot instance
			bots.POST("", botInstanceHandler.CreateBotInstance)

			// Get specific bot instance
			bots.GET("/:instance_id", botInstanceHandler.GetBotInstance)

			// Update bot instance status
			bots.DELETE("/:instance_id", botInstanceHandler.DeleteBotInstance)

			// Bot instance controls
			bots.POST("/:instance_id/start", botInstanceHandler.StartBotInstance)
			bots.POST("/:instance_id/stop", botInstanceHandler.StopBotInstance)
			bots.POST("/:instance_id/restart", botInstanceHandler.RestartBotInstance)

			// Bot instance statistics and history
			bots.GET("/:instance_id/stats", botInstanceHandler.GetBotInstanceStats)
			bots.GET("/:instance_id/trades", botInstanceHandler.GetBotInstanceTrades)

			// Position management endpoints
			bots.GET("/:instance_id/positions", botInstanceHandler.GetBotPositions)

			// Trade management endpoints
			bots.GET("/:instance_id/trades/:trade_id", botInstanceHandler.GetBotTrade)

			// Aggregate summary endpoint (stats + positions + trades in one call)
			bots.GET("/:instance_id/summary", botInstanceHandler.GetBotSummary)
		}
	}
}
