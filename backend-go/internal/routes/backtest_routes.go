package routes

import (
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/gin-gonic/gin"
)

func RegisterBacktestRoutes(router *gin.Engine, database *db.Database) {
	backtestRepo := repository.NewBacktestRepository(database.DB)
	backtestHandler := handlers.NewBacktestHandler(backtestRepo)

	v1 := router.Group("/api/v1")
	{
		backtests := v1.Group("/backtests")
		{
			backtests.GET("/:run_id/candles", backtestHandler.GetBacktestCandles)
			backtests.GET("/:run_id/positions", backtestHandler.GetBacktestPositions)
			backtests.GET("/:run_id/trades", backtestHandler.GetBacktestTrades)
		}
	}
}
