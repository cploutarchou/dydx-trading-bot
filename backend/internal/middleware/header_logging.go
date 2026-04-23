package middleware

import (
	"log"

	"github.com/gin-gonic/gin"
)

// HeaderLoggingMiddleware logs incoming request headers for debugging.
// It masks sensitive headers such as Authorization and Cookie.
func HeaderLoggingMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		headers := SanitizeHeaders(c.Request.Header)
		clientIP := c.ClientIP()
		method := c.Request.Method
		path := c.Request.URL.Path
		log.Printf("headers trace_id=%s method=%s path=%s client_ip=%s headers=%v", GetTraceID(c), method, path, clientIP, headers)
		c.Next()
	}
}
