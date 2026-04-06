package middleware

import (
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

	cookieNames := []string{"access_token", "token", "jwt"}
	for _, name := range cookieNames {
		if cookieVal, err := c.Cookie(name); err == nil && strings.TrimSpace(cookieVal) != "" {
			return "Bearer " + strings.TrimSpace(cookieVal), "cookie:" + name
		}
	}

	if queryToken := strings.TrimSpace(c.Query("access_token")); queryToken != "" {
		return "Bearer " + queryToken, "query:access_token"
	}

	return "", ""
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
