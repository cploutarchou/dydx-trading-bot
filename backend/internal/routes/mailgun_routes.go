// Package routes provides HTTP route registration and handlers for the dYdX backend API Mailgun integration features.
package routes

import (
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func RegisterMailgunRoutes(router *gin.Engine, database *db.Database) {
	credentialRepo := repository.NewExternalAPICredentialRepository(database.DB)
	settingsRepo := repository.NewSettingsRepository(database.DB)
	userRepo := repository.NewUserRepository(database.DB)
	credentialService := services.NewExternalAPICredentialService(credentialRepo)
	mailgunService := services.NewMailgunService(credentialService, settingsRepo, userRepo)
	handler := handlers.NewMailgunHandler(mailgunService)

	v1 := router.Group("/api/v1")
	{
		mailgun := v1.Group("/mailgun")
		mailgun.Use(middleware.RequireAuth())
		{
			mailgun.GET("/status", handler.GetStatus)
			mailgun.PUT("/config", handler.SaveConfig)
			mailgun.DELETE("/config", handler.DeleteConfig)
		}
	}
}
