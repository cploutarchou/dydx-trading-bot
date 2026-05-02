package routes

import (
	"os"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func RegisterBotInstanceRoutes(router *gin.Engine, database *db.Database) {
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
	botInstanceHandler := handlers.NewBotInstanceHandler(botInstanceService, botInstanceRepo, userRepo)

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
				instanceID := c.Param("instance_id")
				status := c.Query("status")
				limit := 100
				offset := 0

				userIDValue, exists := c.Get("user_id")
				if !exists {
					c.JSON(401, gin.H{"success": false, "error": "unauthorized", "timestamp": time.Now().UTC().Format(time.RFC3339)})
					return
				}
				userID, ok := userIDValue.(int)
				if !ok {
					c.JSON(401, gin.H{"success": false, "error": "invalid user context", "timestamp": time.Now().UTC().Format(time.RFC3339)})
					return
				}

				// Resolve the string instance_id to the DB integer id.
				inst, err := botInstanceRepo.GetBotInstanceByInstanceID(instanceID)
				if err != nil || inst == nil {
					c.JSON(404, gin.H{"success": false, "error": "bot instance not found", "timestamp": time.Now().UTC().Format(time.RFC3339)})
					return
				}
				if inst.UserID > 0 && inst.UserID != userID && !c.GetBool("is_admin") {
					c.JSON(403, gin.H{"success": false, "error": "forbidden", "timestamp": time.Now().UTC().Format(time.RFC3339)})
					return
				}

				positions, err := botPositionRepo.ListBotPositionsByInstanceID(inst.ID, status, limit, offset)
				if err != nil {
					c.JSON(400, gin.H{"success": false, "error": err.Error(), "timestamp": time.Now().UTC().Format(time.RFC3339)})
					return
				}
				data := interface{}(positions)
				if positions == nil {
					data = []interface{}{}
				}

				c.JSON(200, gin.H{
					"success":   true,
					"data":      data,
					"timestamp": time.Now().UTC().Format(time.RFC3339),
				})
			})

			// Trade management endpoints
			bots.GET("/:instance_id/trades/:trade_id", func(c *gin.Context) {
				instanceID := c.Param("instance_id")
				tradeID := c.Param("trade_id")

				userIDValue, exists := c.Get("user_id")
				if !exists {
					c.JSON(401, gin.H{"success": false, "error": "unauthorized", "timestamp": time.Now().UTC().Format(time.RFC3339)})
					return
				}
				userID, ok := userIDValue.(int)
				if !ok {
					c.JSON(401, gin.H{"success": false, "error": "invalid user context", "timestamp": time.Now().UTC().Format(time.RFC3339)})
					return
				}

				inst, err := botInstanceRepo.GetBotInstanceByInstanceID(instanceID)
				if err != nil || inst == nil {
					c.JSON(404, gin.H{"success": false, "error": "bot instance not found", "timestamp": time.Now().UTC().Format(time.RFC3339)})
					return
				}
				if inst.UserID > 0 && inst.UserID != userID && !c.GetBool("is_admin") {
					c.JSON(403, gin.H{"success": false, "error": "forbidden", "timestamp": time.Now().UTC().Format(time.RFC3339)})
					return
				}

				trade, err := botTradeRepo.GetBotTradeByTradeID(tradeID)
				if err != nil {
					c.JSON(404, gin.H{"success": false, "error": err.Error(), "timestamp": time.Now().UTC().Format(time.RFC3339)})
					return
				}
				if trade.BotInstanceID != inst.ID {
					c.JSON(404, gin.H{"success": false, "error": "trade not found", "timestamp": time.Now().UTC().Format(time.RFC3339)})
					return
				}

				c.JSON(200, gin.H{
					"success":   true,
					"data":      trade,
					"timestamp": time.Now().UTC().Format(time.RFC3339),
				})
			})
		}
	}
}
