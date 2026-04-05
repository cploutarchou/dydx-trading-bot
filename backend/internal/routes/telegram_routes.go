package routes

import (
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func RegisterTelegramRoutes(router *gin.Engine, database *db.Database) {
	credentialRepo := repository.NewExternalAPICredentialRepository(database.DB)
	settingsRepo := repository.NewSettingsRepository(database.DB)
	credentialService := services.NewExternalAPICredentialService(credentialRepo)
	telegramService := services.NewTelegramService(credentialService, settingsRepo)
	handler := handlers.NewTelegramHandler(telegramService)

	v1 := router.Group("/api/v1")
	{
		telegram := v1.Group("/telegram")
		telegram.Use(middleware.RequireAuth())
		{
			telegram.GET("/status", handler.GetStatus)
			telegram.PUT("/config", handler.SaveConfig)
			telegram.DELETE("/config", handler.DeleteConfig)
		}
	}
}
