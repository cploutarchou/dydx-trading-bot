package middleware

import (
	"fmt"
	"net/url"
	"os"
	"strings"

	"github.com/gin-gonic/gin"
)

// CORSMiddleware adds CORS headers
func CORSMiddleware() gin.HandlerFunc {
	allowedOrigins := allowedCORSOriginsFromEnv()

	return func(c *gin.Context) {
		origin := c.GetHeader("Origin")
		if origin != "" {
			appendVaryHeader(c, "Origin")
			appendVaryHeader(c, "Access-Control-Request-Method")
			appendVaryHeader(c, "Access-Control-Request-Headers")
			if isAllowedCORSOrigin(origin, allowedOrigins) {
				// Echo the origin to support credentials in browsers
				c.Writer.Header().Set("Access-Control-Allow-Origin", origin)
			}
		} else if len(allowedOrigins) == 0 {
			c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		}
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization, accept, origin, Cache-Control, X-Requested-With, X-Trace-Id")
		c.Writer.Header().Set("Access-Control-Expose-Headers", "X-Trace-Id")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS, GET, PUT, DELETE, PATCH")
		c.Writer.Header().Set("Access-Control-Max-Age", "600")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	}
}

func allowedCORSOriginsFromEnv() map[string]struct{} {
	allowed := map[string]struct{}{}
	for _, raw := range []string{os.Getenv("CORS_ALLOWED_ORIGINS"), os.Getenv("FRONTEND_URL")} {
		for _, part := range strings.Split(raw, ",") {
			normalized := normalizeOrigin(part)
			if normalized == "" {
				continue
			}
			allowed[normalized] = struct{}{}
		}
	}
	return allowed
}

func isAllowedCORSOrigin(origin string, allowed map[string]struct{}) bool {
	if len(allowed) == 0 {
		return true
	}
	_, ok := allowed[normalizeOrigin(origin)]
	return ok
}

func normalizeOrigin(origin string) string {
	trimmed := strings.TrimSpace(origin)
	if trimmed == "" {
		return ""
	}
	parsed, err := url.Parse(trimmed)
	if err != nil || parsed.Scheme == "" || parsed.Host == "" {
		return strings.TrimRight(trimmed, "/")
	}
	return strings.TrimRight(parsed.Scheme+"://"+parsed.Host, "/")
}

func appendVaryHeader(c *gin.Context, value string) {
	existing := c.Writer.Header().Values("Vary")
	for _, headerValue := range existing {
		for _, part := range strings.Split(headerValue, ",") {
			if strings.EqualFold(strings.TrimSpace(part), value) {
				return
			}
		}
	}
	c.Writer.Header().Add("Vary", value)
}

// LoggingMiddleware logs requests
func LoggingMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Next()
		fmt.Printf("[%s] %s %s - Status: %d - Trace: %s\n", c.Request.Method, c.Request.RequestURI, c.Request.RemoteAddr, c.Writer.Status(), GetTraceID(c))
	}
}

// AuthMiddleware is kept for backward compatibility.
// Deprecated: use RequireAuth() from auth_middleware.go.
func AuthMiddleware() gin.HandlerFunc {
	return RequireAuth()
}
