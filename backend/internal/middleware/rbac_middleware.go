package middleware

import (
	"database/sql"
	"net/http"
	"strings"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func RequirePermission(database *sql.DB, permissionKey string) gin.HandlerFunc {
	normalizedPermission := strings.TrimSpace(strings.ToLower(permissionKey))
	repo := repository.NewRBACRepository(database)
	rbac := services.NewRBACService(repo)

	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		role := models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin"))

		allowed, err := rbac.HasPermission(userID, role, normalizedPermission)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"message": "Failed to verify permission",
			})
			c.Abort()
			return
		}

		if !allowed {
			c.JSON(http.StatusForbidden, gin.H{
				"success": false,
				"message": "Insufficient permissions",
				"code":    "insufficient_permissions",
			})
			c.Abort()
			return
		}

		c.Next()
	}
}
