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
			// This returns the decrypted wallet secret over HTTP. RequireMFA
			// enforces *enrollment* for privileged roles (platform setting
			// platform.require_privileged_mfa, production-default on) — it is
			// NOT a per-request step-up: a stolen session cookie of an
			// MFA-enrolled user can still read this. A true step-up (recent
			// session MFAVerifiedAt + re-challenge flow for promoted sessions)
			// is tracked as a remaining risk in BACKEND_AUDIT.md.
			keys.GET("/:network/secret", middleware.RequireMFA(database.DB), keyHandler.GetKeyWithSecret)

			// DELETE /api/v1/keys/{network} - Delete (deactivate) a key
			keys.DELETE("/:network", keyHandler.DeleteKey)
		}
	}
}
