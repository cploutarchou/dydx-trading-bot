package routes

import (
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

// RegisterAuditLogRoutes registers audit log API routes
func RegisterAuditLogRoutes(router *gin.Engine, database *db.Database) {
	auditLogRepo := repository.NewAuditLogRepository(database.DB)
	auditLogService := services.NewAuditLogService(auditLogRepo)
	auditLogHandler := handlers.NewAuditLogHandler(auditLogService)

	v1 := router.Group("/api/v1")
	{
		auditLogs := v1.Group("/audit-logs")
		{
			// CRUD operations
			auditLogs.POST("", auditLogHandler.CreateAuditLog)
			auditLogs.GET("/:id", auditLogHandler.GetAuditLog)

			// Query operations
			auditLogs.GET("/user/:user_id", auditLogHandler.ListAuditLogsByUser)
			auditLogs.GET("/list/all", auditLogHandler.ListAllAuditLogs)

			// Action-based queries
			auditLogs.GET("/list/by-action", auditLogHandler.ListAuditLogsByAction)
		}
	}
}
