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

// RegisterStrategyRoutes registers strategy API routes
func RegisterStrategyRoutes(router *gin.Engine, database *db.Database) {
	strategyRepo := repository.NewStrategyRepository(database.DB)
	keyRepo := repository.NewKeyRepository(database.DB)
	botInstanceRepo := repository.NewBotInstanceRepository(database.DB)
	settingsRepo := repository.NewSettingsRepository(database.DB)
	credentialRepo := repository.NewExternalAPICredentialRepository(database.DB)
	strategyService := services.NewStrategyService(strategyRepo)
	keyService := services.NewKeyManagementService(keyRepo)
	credentialService := services.NewExternalAPICredentialService(credentialRepo)
	telegramService := services.NewTelegramService(credentialService, settingsRepo)

	botAPIURL := os.Getenv("BOT_API_URL")
	if botAPIURL == "" {
		botAPIURL = "http://127.0.0.1:8889"
	}
	botAPIClient := services.NewBotAPIClient(botAPIURL, os.Getenv("BOT_API_TOKEN"))
	botInstanceService := services.NewBotInstanceService(botInstanceRepo, botAPIClient)
	runtimeService := services.NewStrategyRuntimeService(strategyService, keyService, telegramService, botInstanceService, botInstanceRepo)
	strategyHandler := handlers.NewStrategyHandler(strategyService, runtimeService)

	v1 := router.Group("/api/v1")
	{
		strategies := v1.Group("/strategies")
		{
			// Require authentication for all strategy routes
			strategies.Use(middleware.RequireAuth())

			// CRUD operations
			strategies.POST("", strategyHandler.CreateStrategy)
			strategies.GET("", strategyHandler.ListStrategies)
			strategies.GET("/:id", strategyHandler.GetStrategy)
			strategies.PUT("/:id", strategyHandler.UpdateStrategy)
			strategies.DELETE("/:id", strategyHandler.DeleteStrategy)
			strategies.GET("/:id/runtime", strategyHandler.GetStrategyRuntime)
			strategies.POST("/:id/start", strategyHandler.StartStrategyRuntime)
			strategies.POST("/:id/stop", strategyHandler.StopStrategyRuntime)
		}
	}
}
