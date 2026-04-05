package routes

import (
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func RegisterCodexRoutes(router *gin.Engine) {
	handler := handlers.NewCodexHandler(services.NewCodexServiceFromEnv())

	v1 := router.Group("/api/v1")
	{
		codex := v1.Group("/codex")
		codex.Use(middleware.RequireAuth())
		{
			codex.GET("/status", handler.GetStatus)
			codex.POST("/respond", handler.Respond)
		}
	}
}
