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

func RegisterBotInstanceRoutes(router *gin.Engine, database *db.Database) {
	botInstanceRepo := repository.NewBotInstanceRepository(database.DB)
	botTradeRepo := repository.NewBotTradeRepository(database.DB)
	botPositionRepo := repository.NewBotPositionRepository(database.DB)

	// Initialize bot API client
	botAPIURL := os.Getenv("BOT_API_URL")
	if botAPIURL == "" {
		botAPIURL = "http://localhost:8889"
	}
	botAPIToken := os.Getenv("BOT_API_TOKEN")
	botAPIClient := services.NewBotAPIClient(botAPIURL, botAPIToken)

	botInstanceService := services.NewBotInstanceService(botInstanceRepo, botAPIClient)
	botInstanceHandler := handlers.NewBotInstanceHandler(botInstanceService, botInstanceRepo)

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
			bots.GET("/:instance_id/positions", func(c *gin.Context) {
				status := c.Query("status")
				limit := 100
				offset := 0

				positions, err := botPositionRepo.ListBotPositionsByInstanceID(0, status, limit, offset)
				if err != nil {
					c.JSON(400, gin.H{"error": err.Error()})
					return
				}

				c.JSON(200, gin.H{
					"success": true,
					"data":    positions,
				})
			})

			// Trade management endpoints
			bots.GET("/:instance_id/trades/:trade_id", func(c *gin.Context) {
				tradeID := c.Param("trade_id")

				trade, err := botTradeRepo.GetBotTradeByTradeID(tradeID)
				if err != nil {
					c.JSON(404, gin.H{"error": err.Error()})
					return
				}

				c.JSON(200, gin.H{
					"success": true,
					"data":    trade,
				})
			})
		}
	}
}
