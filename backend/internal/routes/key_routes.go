// Package routes provides HTTP route registration and handlers for the dYdX backend API key management features.
package routes

import (
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func RegisterKeyRoutes(router *gin.Engine, database *db.Database) {
	keyRepo := repository.NewKeyRepository(database.DB)
	keyService := services.NewKeyManagementService(keyRepo)
	keyHandler := handlers.NewKeyHandler(keyService)

	v1 := router.Group("/api/v1")
	{
		keys := v1.Group("/keys")
		keys.Use(middleware.RequireAuth())
		{
			// POST /api/v1/keys/create - Create or update a dYdX key
			keys.POST("/create", keyHandler.CreateKey)

			// GET /api/v1/keys/list - Get all active keys for current user
			keys.GET("/list", keyHandler.ListKeys)

			// GET /api/v1/keys/{network} - Get key info for a specific network
			keys.GET("/:network", keyHandler.GetKeyInfo)

			// GET /api/v1/keys/{network}/secret - Get full key with decrypted secret
			keys.GET("/:network/secret", keyHandler.GetKeyWithSecret)

			// DELETE /api/v1/keys/{network} - Delete (deactivate) a key
			keys.DELETE("/:network", keyHandler.DeleteKey)
		}
	}
}
