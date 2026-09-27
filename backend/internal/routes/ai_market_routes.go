// Package routes provides HTTP route registration and handlers for the dYdX backend API AI market features.
package routes

import (
	"net/http"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func RegisterAIMarketRoutes(router *gin.Engine, database *db.Database, apiClient *services.BotAPIClient) {
	credentialRepo := repository.NewExternalAPICredentialRepository(database.DB)
	credentialService := services.NewExternalAPICredentialService(credentialRepo)
	aiService := services.NewAIMarketService(credentialService)
	// Strategy evidence for the analysis endpoints: completed runs and their
	// ledgers from the mirror and the bot, the live runtime and the stored
	// pair scan through the bot client (nil client: noted as unavailable).
	backtestRepo := repository.NewBacktestRepository(database.DB)
	strategyService := services.NewStrategyService(repository.NewStrategyRepository(database.DB))
	aiService.SetStrategyEvidence(services.NewStrategyEvidenceBuilder(backtestRepo, services.NewBotEvidenceClient(apiClient)), strategyService, backtestRepo)
	// Market selection reads a strategy's pair statistics through the same
	// service (it satisfies StrategyEvidenceSource).
	aiService.SetStrategyEvidenceSource(aiService)
	handler := handlers.NewAIMarketHandler(aiService)

	group := router.Group("/api/v1/ai")
	group.Use(middleware.RequireAuth())
	{
		group.GET("/market-filters/status", handler.GetStatus)
		group.PUT("/market-filters/key", handler.SaveKey)
		group.PUT("/market-filters/shared-key", handler.SaveSharedKey)
		group.DELETE("/market-filters/key/:provider", handler.DeleteKey)
		group.DELETE("/market-filters/shared-key/:provider", handler.DeleteSharedKey)
		// The AI selector ranks mainnet statistics (the list backtests replay)
		// and keeps the markets the runtime can trade; the loader caches both
		// lists and serves them stale for a while when the bot is down.
		marketUniverse := services.NewMarketUniverseLoader(apiClient)
		group.POST("/market-filters/select", func(c *gin.Context) {
			if apiClient == nil {
				c.JSON(http.StatusServiceUnavailable, gin.H{
					"success":   false,
					"error":     "bot market client is not configured",
					"timestamp": time.Now().UTC().Format(time.RFC3339),
				})
				return
			}

			universe, err := marketUniverse.Load(c.Request.Context())
			if err != nil {
				respondBotAPIError(c, err)
				return
			}

			handler.SelectMarkets(c, universe)
		})
		group.POST("/backtests/explain", handler.ExplainBacktest)
		group.POST("/strategies/suggest-params", handler.SuggestStrategyParams)
		group.POST("/runtime/digest", handler.RuntimeDigest)
	}
}
