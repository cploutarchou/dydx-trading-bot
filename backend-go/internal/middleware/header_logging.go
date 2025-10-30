package middleware

import (
	"log"
	"strings"

	"github.com/gin-gonic/gin"
)

// HeaderLoggingMiddleware logs incoming request headers for debugging.
// It masks sensitive headers such as Authorization and Cookie.
func HeaderLoggingMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Build a sanitized headers map
		headers := make(map[string]string)
		for k, vals := range c.Request.Header {
			v := strings.Join(vals, ",")
			switch strings.ToLower(k) {
			case "authorization":
				if v != "" {
					// mask token value but keep prefix
					if strings.HasPrefix(strings.ToLower(v), "bearer ") {
						headers[k] = "Bearer <masked>"
					} else {
						headers[k] = "<masked>"
					}
				} else {
					headers[k] = v
				}
			case "cookie":
				if v != "" {
					headers[k] = "<masked>"
				} else {
					headers[k] = v
				}
			default:
				headers[k] = v
			}
		}

		// Log method, path, client IP and sanitized headers
		clientIP := c.ClientIP()
		method := c.Request.Method
		path := c.Request.URL.Path
		log.Printf("Headers: %s %s from %s - %v", method, path, clientIP, headers)

		// Continue to next handler
		c.Next()
	}
}
