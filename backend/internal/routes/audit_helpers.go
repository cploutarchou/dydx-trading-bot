// Package routes provides helper functions for audit logging in the dYdX backend API.
package routes

import (
	"database/sql"
	"log"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/gin-gonic/gin"
)

func writeAuditLog(database *sql.DB, c *gin.Context, action, resourceType string, resourceID *string, details interface{}, status string) {
	actorID := c.GetInt("user_id")
	ipAddress := c.ClientIP()
	now := time.Now().UTC()
	audit := &models.AuditLog{
		UserID:       &actorID,
		Action:       action,
		ResourceType: resourceType,
		ResourceID:   resourceID,
		Details:      details,
		Status:       &status,
		IPAddress:    &ipAddress,
		CreatedAt:    &now,
	}
	if err := repository.NewAuditLogRepository(database).CreateAuditLog(audit); err != nil {
		log.Printf("failed to write audit log action=%s resource=%s: %v", action, resourceType, err)
	}
}
