package routes

import (
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/gin-gonic/gin"
)

// RegisterBacktestRoutes registers all backtest-related routes
func RegisterBacktestRoutes(router *gin.Engine, database *db.Database) {
	backtestHandler := handlers.NewBacktestHandler(database)

	v1 := router.Group("/api/v1")
	{
		backtests := v1.Group("/backtests")
		{
			// GET /api/v1/backtests/{run_id}/candles - Historical price data
			backtests.GET("/:run_id/candles", backtestHandler.GetBacktestCandles)

			// GET /api/v1/backtests/{run_id}/positions - Open/closed positions
			backtests.GET("/:run_id/positions", backtestHandler.GetBacktestPositions)

			// GET /api/v1/backtests/{run_id}/trades - Individual trade records
			backtests.GET("/:run_id/trades", backtestHandler.GetBacktestTrades)
		}
	}
}
