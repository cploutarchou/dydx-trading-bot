package middleware

import (
	"fmt"
	"log"

	"github.com/gin-gonic/gin"
)

// ErrorHandlingMiddleware handles panics and recovers gracefully
func ErrorHandlingMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		defer func() {
			if err := recover(); err != nil {
				traceID := GetTraceID(c)
				log.Printf("🚨 Panic recovered: trace_id=%s err=%v", traceID, err)
				fmt.Printf("🚨 PANIC STACK TRACE: trace_id=%s err=%v\n", traceID, err)
				c.JSON(500, gin.H{
					"error":    "Internal server error",
					"trace_id": traceID,
				})
				c.Abort()
			}
		}()
		c.Next()
	}
}
