package middleware

import (
	"crypto/rand"
	"encoding/hex"
	"strings"

	"github.com/gin-gonic/gin"
)

const (
	TraceIDHeader     = "X-Trace-Id"
	traceIDContextKey = "trace_id"
)

func generateTraceID() string {
	buffer := make([]byte, 6)
	if _, err := rand.Read(buffer); err != nil {
		return "req-fallback"
	}
	return "req-" + hex.EncodeToString(buffer)
}

// RequestTraceMiddleware attaches a request-scoped trace ID to every request.
// It reuses an inbound X-Trace-Id when present so the full stack can correlate
// a single action across frontend, backend, and bot runtime services.
func RequestTraceMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		traceID := strings.TrimSpace(c.GetHeader(TraceIDHeader))
		if traceID == "" {
			traceID = generateTraceID()
		}

		c.Set(traceIDContextKey, traceID)
		c.Writer.Header().Set(TraceIDHeader, traceID)
		c.Next()
		c.Writer.Header().Set(TraceIDHeader, traceID)
	}
}

// GetTraceID returns the trace ID attached to the current request context.
func GetTraceID(c *gin.Context) string {
	if c == nil {
		return ""
	}
	traceID, _ := c.Get(traceIDContextKey)
	if value, ok := traceID.(string); ok {
		return strings.TrimSpace(value)
	}
	return ""
}
