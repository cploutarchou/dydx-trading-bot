package routes

import (
	"database/sql"

	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func RegisterICOAdminRoutes(router *gin.Engine, database *sql.DB) {
	whitelistRepo := repository.NewICOWhitelistRepository(database)
	credentialRepo := repository.NewExternalAPICredentialRepository(database)
	settingsRepo := repository.NewSettingsRepository(database)
	userRepo := repository.NewUserRepository(database)
	credentialService := services.NewExternalAPICredentialService(credentialRepo)
	mailgunService := services.NewMailgunService(credentialService, settingsRepo, userRepo)
	outboxService := services.NewICOEmailOutboxService(whitelistRepo, mailgunService)
	handler := handlers.NewICOAdminHandler(whitelistRepo, outboxService)

	admin := router.Group("/api/v1/admin/ico")
	admin.Use(middleware.RequireAuth())
	admin.GET("/whitelist", handler.ListWhitelistApplications)
	admin.POST("/email-outbox/process", handler.ProcessEmailOutbox)
}
