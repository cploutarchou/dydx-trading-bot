package routes

import (
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func RegisterCodexRoutes(router *gin.Engine, database *db.Database) {
	credentialRepo := repository.NewExternalAPICredentialRepository(database.DB)
	credentialService := services.NewExternalAPICredentialService(credentialRepo)
	codexService := services.NewCodexServiceFromEnv(credentialService)
	handler := handlers.NewCodexHandler(codexService)

	v1 := router.Group("/api/v1")
	{
		codex := v1.Group("/codex")
		codex.Use(middleware.RequireAuth())
		{
			codex.GET("/status", handler.GetStatus)
			codex.PUT("/key", handler.SaveKey)
			codex.DELETE("/key", handler.DeleteKey)
			codex.GET("/market/overview", handler.GetMarketOverview)
			codex.GET("/tokens/search", handler.SearchTokens)
			codex.GET("/tokens/:network/:address", handler.GetTokenDetail)
			codex.GET("/tokens/:network/:address/chart", handler.GetTokenChart)
			codex.POST("/assets/context", handler.ResolveAssetsContext)
		}
	}
}
