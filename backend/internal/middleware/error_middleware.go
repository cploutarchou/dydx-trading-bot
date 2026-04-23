package middleware

import (
	"log"
	"net/http"
	"runtime/debug"

	"github.com/gin-gonic/gin"
)

// ErrorHandlingMiddleware handles panics and recovers gracefully
func ErrorHandlingMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		defer func() {
			if err := recover(); err != nil {
				traceID := GetTraceID(c)
				log.Printf("panic recovered trace_id=%s err=%v\n%s", traceID, err, debug.Stack())
				if !c.Writer.Written() {
					c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{
						"error":    "Internal server error",
						"trace_id": traceID,
					})
					return
				}
				c.Abort()
			}
		}()
		c.Next()
	}
}
