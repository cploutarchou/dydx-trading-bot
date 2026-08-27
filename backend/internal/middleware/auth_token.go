package middleware

import (
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
)

// ResolveRequestAuthHeader returns the auth header value accepted by RequireAuth
// along with the source used to resolve it.
func ResolveRequestAuthHeader(c *gin.Context) (string, string) {
	authHeader := strings.TrimSpace(c.GetHeader("Authorization"))
	if authHeader != "" {
		return authHeader, "authorization"
	}

	cookieNames := []string{"dydx_session", "access_token", "token", "jwt"}
	for _, name := range cookieNames {
		if cookieVal, err := c.Cookie(name); err == nil && strings.TrimSpace(cookieVal) != "" {
			return "Bearer " + strings.TrimSpace(cookieVal), "cookie:" + name
		}
	}

	// The query-string fallback is restricted to WebSocket upgrades: browsers
	// cannot set headers on WS handshakes, so the frontend appends the token
	// there. Everywhere else query strings would leak tokens into server logs,
	// browser history, and Referer headers, so they are rejected.
	if isBrowserWebSocketUpgrade(c.Request) {
		if queryToken := strings.TrimSpace(c.Query("access_token")); queryToken != "" {
			return "Bearer " + queryToken, "query:access_token"
		}
	}

	return "", ""
}

// isBrowserWebSocketUpgrade reports whether the request is a WebSocket
// handshake (the only context where a query-string token is accepted).
func isBrowserWebSocketUpgrade(request *http.Request) bool {
	return strings.EqualFold(strings.TrimSpace(request.Header.Get("Upgrade")), "websocket") &&
	 strings.Contains(strings.ToLower(strings.TrimSpace(request.Header.Get("Connection"))), "upgrade")
}

// ExtractRequestAccessToken returns the bearer token accepted for the request.
func ExtractRequestAccessToken(c *gin.Context) string {
	authHeader, _ := ResolveRequestAuthHeader(c)
	parts := strings.SplitN(strings.TrimSpace(authHeader), " ", 2)
	if len(parts) == 2 && strings.EqualFold(strings.TrimSpace(parts[0]), "Bearer") {
		return strings.TrimSpace(parts[1])
	}
	return strings.TrimSpace(authHeader)
}
