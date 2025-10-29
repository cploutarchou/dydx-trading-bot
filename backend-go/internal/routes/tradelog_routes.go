package routes

import (
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

// RegisterTradeLogRoutes registers trade log API routes
func RegisterTradeLogRoutes(router *gin.Engine, database *db.Database) {
	tradeLogRepo := repository.NewTradeLogRepository(database.DB)
	tradeLogService := services.NewTradeLogService(tradeLogRepo)
	tradeLogHandler := handlers.NewTradeLogHandler(tradeLogService)

	v1 := router.Group("/api/v1")
	{
		tradeLogs := v1.Group("/trade-logs")
		{
			// CRUD operations
			tradeLogs.POST("", tradeLogHandler.CreateTradeLog)
			tradeLogs.GET("/:id", tradeLogHandler.GetTradeLog)
			tradeLogs.PUT("/:id", tradeLogHandler.UpdateTradeLog)
			tradeLogs.DELETE("/:id", tradeLogHandler.DeleteTradeLog)

			// Query operations
			tradeLogs.GET("/result/:result_id", tradeLogHandler.ListTradeLogsByResult)
			tradeLogs.GET("/backtest-run/:run_id", tradeLogHandler.ListTradeLogsByBacktestRun)
		}
	}
}
