// Package routes provides HTTP route registration and handlers for the dYdX backend API outbound email settings.
package routes

import (
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func RegisterEmailRoutes(router *gin.Engine, database *db.Database) {
	credentialRepo := repository.NewExternalAPICredentialRepository(database.DB)
	settingsRepo := repository.NewSettingsRepository(database.DB)
	userRepo := repository.NewUserRepository(database.DB)
	credentialService := services.NewExternalAPICredentialService(credentialRepo)
	emailService := services.NewEmailService(credentialService, settingsRepo, userRepo)
	handler := handlers.NewEmailHandler(emailService)

	v1 := router.Group("/api/v1")
	{
		email := v1.Group("/email")
		email.Use(middleware.RequireAuth())
		{
			email.GET("/status", handler.GetStatus)
			email.PUT("/config", handler.SaveConfig)
			email.DELETE("/config", handler.DeleteConfig)
			email.POST("/test", handler.SendTest)
		}
	}
}
