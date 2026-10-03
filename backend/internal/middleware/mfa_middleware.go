package middleware

import (
	"database/sql"
	"net/http"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/auth"
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
		user, err := userRepo.GetByIDContext(c.Request.Context(), userID)
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

// RequireRecentMFA demands that the current SESSION has completed a TOTP
// verification within maxAge. This is a true step-up: unlike RequireMFA
// (which only checks enrollment), a stolen base session cookie cannot pass
// without the authenticator. Bearer-JWT requests have no session record of
// recent verification and always fail — callers must use the session flow.
func RequireRecentMFA(maxAge time.Duration) gin.HandlerFunc {
	return func(c *gin.Context) {
		store := AuthSessionStore()
		if store == nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"success": false,
				"message": "session store unavailable; cannot verify recent MFA",
				"code":    "mfa_step_up_unavailable",
			})
			c.Abort()
			return
		}

		token := sessionTokenFromRequest(c)
		if token == "" {
			c.JSON(http.StatusForbidden, gin.H{
				"success": false,
				"message": "recent multi-factor verification required",
				"code":    "mfa_step_up_required",
			})
			c.Abort()
			return
		}

		sessionData, err := store.Get(c.Request.Context(), token)
		if err != nil || sessionData == nil {
			c.JSON(http.StatusForbidden, gin.H{
				"success": false,
				"message": "recent multi-factor verification required",
				"code":    "mfa_step_up_required",
			})
			c.Abort()
			return
		}

		if sessionData.MFAVerifiedAt == nil ||
			time.Since(sessionData.MFAVerifiedAt.UTC()) > maxAge {
			c.JSON(http.StatusForbidden, gin.H{
				"success": false,
				"message": "recent multi-factor verification required",
				"code":    "mfa_step_up_required",
			})
			c.Abort()
			return
		}

		c.Next()
	}
}

// sessionTokenFromRequest resolves the opaque session token the auth
// middleware would have accepted (cookie first, bearer fallback).
func sessionTokenFromRequest(c *gin.Context) string {
	if v, err := c.Cookie(auth.SessionCookieName); err == nil && strings.TrimSpace(v) != "" {
		return strings.TrimSpace(v)
	}
	header := strings.TrimSpace(c.GetHeader("Authorization"))
	parts := strings.SplitN(header, " ", 2)
	if len(parts) == 2 && strings.EqualFold(strings.TrimSpace(parts[0]), "Bearer") {
		return strings.TrimSpace(parts[1])
	}
	return ""
}
