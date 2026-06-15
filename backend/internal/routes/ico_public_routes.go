package routes

import (
	"database/sql"

	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func RegisterICOPublicRoutes(router *gin.Engine, database *sql.DB) {
	repo := repository.NewICOWhitelistRepository(database)
	service := services.NewICOWhitelistService(repo)
	handler := handlers.NewICOWhitelistHandler(service)
	webhookHandler := handlers.NewICOMailgunWebhookHandler(repo)

	registerICOWhitelistGroup(router.Group("/api/v1/public/ico"), handler)
	registerICOWhitelistGroup(router.Group("/api/public/ico"), handler)
	router.POST("/api/v1/public/ico/mailgun/webhook", webhookHandler.Handle)
}

func registerICOWhitelistGroup(group *gin.RouterGroup, handler *handlers.ICOWhitelistHandler) {
	group.POST("/whitelist", handler.Submit)
	group.GET("/whitelist/confirm", handler.Confirm)
	group.POST("/whitelist/confirm", handler.Confirm)
	group.GET("/whitelist/unsubscribe", handler.Unsubscribe)
	group.POST("/whitelist/unsubscribe", handler.Unsubscribe)
	group.GET("/whitelist/withdraw", handler.Withdraw)
	group.POST("/whitelist/withdraw", handler.Withdraw)
}
