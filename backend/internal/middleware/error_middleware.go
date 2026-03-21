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
				log.Printf("🚨 Panic recovered: %v", err)
				fmt.Printf("🚨 PANIC STACK TRACE: %v\n", err)
				c.JSON(500, gin.H{
					"error": "Internal server error",
				})
				c.Abort()
			}
		}()
		c.Next()
	}
}
