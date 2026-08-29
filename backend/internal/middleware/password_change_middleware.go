package middleware

import (
	"log"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
)

// passwordChangeLookup resolves whether a user must rotate their password
// before using the platform (users.password_change_required). It is injected
// at server bootstrap (cmd/server/main.go) to avoid a package-level database
// dependency here; while nil (tests, tools) the check is inert.
var passwordChangeLookup func(userID int) (bool, error)

// SetPasswordChangeLookup installs the DB-backed lookup used by
// enforcePasswordChangeCleared.
func SetPasswordChangeLookup(f func(userID int) (bool, error)) {
	passwordChangeLookup = f
}

// passwordChangeAllowPathPrefixes are the endpoints a password-change-pending
// user must still reach: completing the rotation itself, ending the session,
// reading their own session/profile state, and the MFA flows that gate the
// change-password request (RequireMFA step-up).
var passwordChangeAllowPathPrefixes = []string{
	"/api/v1/auth/change-password",
	"/api/v1/auth/logout",
	"/api/v1/auth/me",
	"/api/v1/auth/session",
	"/api/v1/auth/2fa",
	"/api/v1/auth/mfa",
}

// enforcePasswordChangeCleared blocks authenticated requests from users whose
// password_change_required flag is still set, except for the allowlisted
// flows above. Server-side enforcement matters because the flag was
// previously only surfaced to the frontend: seeded/recovered accounts with
// repo-known passwords could otherwise keep using the API indefinitely.
// Fails CLOSED (503) when the flag cannot be read: the flag exists precisely
// to force credential rotation on potentially-compromised accounts.
func enforcePasswordChangeCleared(c *gin.Context) bool {
	if passwordChangeLookup == nil {
		return true
	}
	userIDValue, exists := c.Get("user_id")
	if !exists {
		return true
	}
	userID, ok := userIDValue.(int)
	if !ok || userID <= 0 {
		return true
	}

	required, err := passwordChangeLookup(userID)
	if err != nil {
		log.Printf("password-change gate: lookup failed for user=%d: %v", userID, err)
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"success":    false,
			"error":      "unable to verify account status",
			"error_code": "password_change_check_failed",
		})
		c.Abort()
		return false
	}
	if !required {
		return true
	}

	path := c.Request.URL.Path
	for _, prefix := range passwordChangeAllowPathPrefixes {
		if path == prefix || strings.HasPrefix(path, prefix+"/") {
			return true
		}
	}

	c.JSON(http.StatusForbidden, gin.H{
		"success":    false,
		"error":      "password change required before using this endpoint",
		"error_code": "password_change_required",
	})
	c.Abort()
	return false
}
