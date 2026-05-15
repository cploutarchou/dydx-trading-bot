// Package routes provides HTTP route registration and handlers for the dYdX backend API backtest features.
package routes

import (
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func RegisterBacktestRoutes(router *gin.Engine, database *db.Database) {
	RegisterBacktestRoutesWithCache(router, database, nil)
}

func RegisterBacktestRoutesWithCache(router *gin.Engine, database *db.Database, cacheService *services.CacheService) {
	backtestRepo := repository.NewBacktestRepository(database.DB)
	storageManager := services.GetBacktestStorage()
	backtestHandler := handlers.NewBacktestHandler(backtestRepo, storageManager)
	if cacheService != nil {
		candleCache := services.NewCandleCacheServiceWithRepo(cacheService, backtestRepo)
		backtestHandler = backtestHandler.WithCandleCache(candleCache)
	}

	v1 := router.Group("/api/v1")
	{
		backtests := v1.Group("/backtests")
		{
			// Require authentication for all backtest routes
			backtests.Use(middleware.RequireAuth())

			// List all backtests with pagination
			backtests.GET("", backtestHandler.ListBacktests)

			// Existing endpoints - query from database
			backtests.GET("/:run_id/candles", backtestHandler.GetBacktestCandles)
			backtests.GET("/:run_id/positions", backtestHandler.GetBacktestPositions)
			backtests.GET("/:run_id/trades", backtestHandler.GetBacktestTrades)

			// NEW: Storage endpoints - JSON file-based
			backtests.POST("/:run_id/save-json", backtestHandler.SaveBacktestResultJSON)
			backtests.GET("/export/results", backtestHandler.ExportBacktestResults)
			backtests.GET("/export/best", backtestHandler.GetBestResults)
			backtests.GET("/export/stats", backtestHandler.GetStorageStats)
			backtests.POST("/export/cleanup", backtestHandler.CleanupOldResults)
		}
	}
}
