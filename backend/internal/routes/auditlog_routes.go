package routes

import (
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
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
			// Require authentication for all audit log routes
			auditLogs.Use(middleware.RequireAuth())
			auditLogs.Use(middleware.RequireMFA(database.DB))

			// CRUD operations
			auditLogs.POST("", middleware.RequirePermission(database.DB, "audit.read"), auditLogHandler.CreateAuditLog)
			auditLogs.GET("/:id", middleware.RequirePermission(database.DB, "audit.read"), auditLogHandler.GetAuditLog)

			// Query operations
			auditLogs.GET("/user/:user_id", middleware.RequirePermission(database.DB, "audit.read"), auditLogHandler.ListAuditLogsByUser)
			auditLogs.GET("/list/all", middleware.RequirePermission(database.DB, "audit.read"), auditLogHandler.ListAllAuditLogs)

			// Action-based queries
			auditLogs.GET("/list/by-action", middleware.RequirePermission(database.DB, "audit.read"), auditLogHandler.ListAuditLogsByAction)
		}
	}
}
