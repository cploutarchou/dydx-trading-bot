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
				requestCtx := buildRequestLogContext(c)

				log.Printf(
					"panic recovered trace_id=%s method=%s path=%s route=%s handler=%s client_ip=%s err=%v\n%s",
					requestCtx.TraceID,
					requestCtx.Method,
					requestCtx.Path,
					requestCtx.Route,
					requestCtx.Handler,
					requestCtx.ClientIP,
					err,
					debug.Stack(),
				)
				if !c.Writer.Written() {
					c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{
						"error":    "Internal server error",
						"trace_id": requestCtx.TraceID,
					})
					return
				}
				c.Abort()
			}
		}()
		c.Next()
	}
}
