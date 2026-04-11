package middleware

import (
	"database/sql"
	"net/http"
	"strings"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/gin-gonic/gin"
)

func IsPrivilegedMFARequired(database *sql.DB) bool {
	defaultRequired := strings.EqualFold(config.ResolveAppConfigEnvironment(), "production")
	if database == nil {
		return defaultRequired
	}

	setting, err := repository.NewSettingsRepository(database).GetBotSettingBySectionAndKey("platform", "require_privileged_mfa")
	if err != nil {
		lower := strings.ToLower(err.Error())
		if strings.Contains(lower, "no such table") || strings.Contains(lower, "does not exist") {
			return defaultRequired
		}
		return defaultRequired
	}
	if setting == nil {
		return defaultRequired
	}

	value := strings.TrimSpace(strings.ToLower(setting.Value))
	switch value {
	case "true", "1", "yes", "on":
		return true
	case "false", "0", "no", "off", "":
		return false
	default:
		return defaultRequired
	}
}

func RequireMFA(database *sql.DB) gin.HandlerFunc {
	userRepo := repository.NewUserRepository(database)
	return func(c *gin.Context) {
		if !IsPrivilegedMFARequired(database) {
			c.Next()
			return
		}

		if !userRepo.SupportsMFA() {
			c.Next()
			return
		}

		role := models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin"))
		if !models.IsMFAMandatoryRole(role) {
			c.Next()
			return
		}

		userID := c.GetInt("user_id")
		user, err := userRepo.GetByID(userID)
		if err != nil || user == nil {
			c.JSON(http.StatusUnauthorized, gin.H{"success": false, "message": "User not found"})
			c.Abort()
			return
		}
		if user.MFAEnabled {
			c.Next()
			return
		}

		c.JSON(http.StatusForbidden, gin.H{
			"success": false,
			"message": "MFA enrollment required for this operation",
			"code":    "mfa_required",
		})
		c.Abort()
	}
}
