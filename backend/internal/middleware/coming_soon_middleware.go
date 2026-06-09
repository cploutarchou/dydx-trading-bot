package middleware

import (
	"database/sql"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/gin-gonic/gin"
)

func parseComingSoonBool(value string) bool {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "true", "1", "yes", "on":
		return true
	default:
		return false
	}
}

func comingSoonExemptPath(path string) bool {
	normalized := strings.TrimSpace(path)
	if normalized == "" {
		return true
	}

	exact := map[string]struct{}{
		"/health":                    {},
		"/ready":                     {},
		"/metrics":                   {},
		"/api/v1/health":             {},
		"/api/v1/ready":              {},
		"/api/v1/public/app-config":  {},
		"/api/v1/auth/login":         {},
		"/api/v1/auth/register":      {},
		"/api/v1/auth/refresh":       {},
		"/api/v1/auth/token":         {},
		"/api/v1/auth/logout":        {},
		"/api/v1/auth/me":            {},
		"/api/v1/auth/2fa/setup":     {},
		"/api/v1/auth/2fa/verify":    {},
		"/api/v1/auth/password":      {},
		"/api/v1/auth/force-password": {},
		"/api/v1/auth/registration-status": {},
	}
	if _, ok := exact[normalized]; ok {
		return true
	}

	prefixes := []string{
		"/assets/",
		"/static/",
		"/ws",
		"/api/v1/auth/",
		"/api/v1/public/",
		"/api/v1/settings",
		"/api/v1/admin",
		"/api/v1/backoffice",
		"/api/v1/debug",
	}
	for _, prefix := range prefixes {
		if strings.HasPrefix(normalized, prefix) {
			return true
		}
	}

	return false
}

func comingSoonAdminBypass(c *gin.Context) bool {
	if c.GetBool("is_admin") {
		return true
	}

	switch models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin")) {
	case "admin", "super_admin", "backoffice", "operations_admin", "compliance_admin",
		"support_agent", "finance_admin", "read_only_auditor", "security_analyst",
		"accounting", "marketing", "agent":
		return true
	default:
		return false
	}
}

func comingSoonEnabled(database *sql.DB) bool {
	if database == nil {
		return false
	}
	setting, err := repository.NewSettingsRepository(database).GetBotSettingBySectionAndKey("platform", "coming_soon_enabled")
	if err != nil {
		log.Printf("ComingSoonMiddleware: failed to load setting, allowing request: %v", err)
		return false
	}
	if setting == nil || !setting.IsActive {
		return false
	}
	return parseComingSoonBool(setting.Value)
}

// ComingSoonMiddleware blocks authenticated non-admin application API calls while
// platform.coming_soon_enabled is active. Exempt routes keep auth, admin,
// readiness, public bootstrap config, static assets, and websocket operations
// available so administrators cannot lock themselves out.
func ComingSoonMiddleware(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		if comingSoonExemptPath(c.Request.URL.Path) || !comingSoonEnabled(database) {
			c.Next()
			return
		}

		if !TrySetAuthContext(c) {
			c.Next()
			return
		}

		if comingSoonAdminBypass(c) {
			c.Next()
			return
		}

		c.JSON(http.StatusServiceUnavailable, gin.H{
			"success":   false,
			"message":   "Public access is temporarily paused while Coming Soon mode is enabled.",
			"code":      "coming_soon_enabled",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
		c.Abort()
	}
}
