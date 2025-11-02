package routes

import (
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/gin-gonic/gin"
)

// RegisterPairStorageRoutes registers pair storage API routes
func RegisterPairStorageRoutes(router *gin.Engine) {
	pairHandler := handlers.NewPairStorageHandler()

	v1 := router.Group("/api/v1")
	{
		pairs := v1.Group("/pairs")
		{
			// Require authentication for all pair storage routes
			pairs.Use(middleware.RequireAuth())

			// Save and load operations
			pairs.POST("/save", pairHandler.SavePairs)
			pairs.GET("/load", pairHandler.LoadPairs)

			// Query operations
			pairs.GET("/best", pairHandler.GetBestPairs)
			pairs.GET("/high-confidence", pairHandler.GetHighConfidencePairs)
			pairs.GET("/find", pairHandler.GetPairByMarkets)

			// Statistics
			pairs.GET("/storage-info", pairHandler.GetStorageInfo)

			// Analysis
			pairs.POST("/calculate-confidence", pairHandler.CalculateConfidence)
		}
	}
}
