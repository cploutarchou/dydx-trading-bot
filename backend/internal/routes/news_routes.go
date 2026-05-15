// Package routes provides HTTP route registration and handlers for the dYdX backend API news features.
package routes

import (
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func RegisterNewsRoutes(router *gin.Engine, database *db.Database) {
	credentialRepo := repository.NewExternalAPICredentialRepository(database.DB)
	credentialService := services.NewExternalAPICredentialService(credentialRepo)
	newsService := services.NewNewsServiceFromEnv(credentialService)
	handler := handlers.NewNewsHandler(newsService)

	v1 := router.Group("/api/v1")
	{
		news := v1.Group("/news")
		news.Use(middleware.RequireAuth())
		{
			news.GET("/coindesk", handler.GetCoinDeskNews)
			news.GET("/coindesk/config", handler.GetCoinDeskConfigStatus)
			news.PUT("/coindesk/config", handler.SaveCoinDeskConfig)
			news.DELETE("/coindesk/config", handler.DeleteCoinDeskConfig)
		}
	}
}
