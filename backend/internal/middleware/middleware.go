package middleware

import (
	"fmt"
	"github.com/gin-gonic/gin"
)

// CORSMiddleware adds CORS headers
func CORSMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		origin := c.GetHeader("Origin")
		if origin == "" {
			c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		} else {
			// Echo the origin to support credentials in browsers
			c.Writer.Header().Set("Access-Control-Allow-Origin", origin)
			c.Writer.Header().Set("Vary", "Origin")
		}
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization, accept, origin, Cache-Control, X-Requested-With, X-Trace-Id")
		c.Writer.Header().Set("Access-Control-Expose-Headers", "X-Trace-Id")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS, GET, PUT, DELETE, PATCH")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	}
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
