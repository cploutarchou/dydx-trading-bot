package routes

import (
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

// RegisterSettingsRoutes registers settings API routes
func RegisterSettingsRoutes(router *gin.Engine, database *db.Database) {
	settingsRepo := repository.NewSettingsRepository(database.DB)
	settingsService := services.NewSettingsService(settingsRepo)
	settingsHandler := handlers.NewSettingsHandler(settingsService)

	v1 := router.Group("/api/v1")
	{
		settings := v1.Group("/settings")
		{
			// Require authentication for all settings routes
			settings.Use(middleware.RequireAuth())

			// BotSetting routes
			settings.POST("/bot", settingsHandler.CreateBotSetting)
			settings.GET("/bot", settingsHandler.GetBotSetting)
			settings.GET("/bot/section", settingsHandler.GetBotSettingsBySection)
			settings.GET("/bot/all", settingsHandler.ListAllBotSettings)
			settings.PUT("/bot/:id", settingsHandler.UpdateBotSetting)
			settings.DELETE("/bot/:id", settingsHandler.DeleteBotSetting)

			// RedisSetting routes
			settings.GET("/redis", settingsHandler.GetRedisSetting)
			settings.PUT("/redis", settingsHandler.UpdateRedisSetting)

			// Cache management
			settings.POST("/cache/clear", settingsHandler.ClearSettingsCache)
			settings.GET("/cache/stats", settingsHandler.GetCacheStats)
		}
	}
}
