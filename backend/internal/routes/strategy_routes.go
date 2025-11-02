package routes

import (
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

// RegisterStrategyRoutes registers strategy API routes
func RegisterStrategyRoutes(router *gin.Engine, database *db.Database) {
	strategyRepo := repository.NewStrategyRepository(database.DB)
	strategyService := services.NewStrategyService(strategyRepo)
	strategyHandler := handlers.NewStrategyHandler(strategyService)

	v1 := router.Group("/api/v1")
	{
		strategies := v1.Group("/strategies")
		{
			// Require authentication for all strategy routes
			strategies.Use(middleware.RequireAuth())

			// CRUD operations
			strategies.POST("", strategyHandler.CreateStrategy)
			strategies.GET("", strategyHandler.ListStrategies)
			strategies.GET("/:id", strategyHandler.GetStrategy)
			strategies.PUT("/:id", strategyHandler.UpdateStrategy)
			strategies.DELETE("/:id", strategyHandler.DeleteStrategy)
		}
	}
}
