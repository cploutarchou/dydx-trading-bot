// Package routes provides helper functions for HTTP response formatting in the dYdX backend API.
package routes

import (
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/gin-gonic/gin"
)

func respondEnvelope(c *gin.Context, statusCode int, success bool, message string, data interface{}) {
	c.JSON(statusCode, gin.H{
		"success":   success,
		"message":   message,
		"data":      data,
		"timestamp": time.Now().UTC().Format(time.RFC3339),
		"trace_id":  middleware.GetTraceID(c),
	})
}
