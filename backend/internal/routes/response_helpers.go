// Package routes provides helper functions for HTTP response formatting in the dYdX backend API.
package routes

import (
	"net/http"
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

func respondErrorEnvelope(c *gin.Context, statusCode int, message string, code string) {
	payload := gin.H{"error": message}
	if code != "" {
		payload["code"] = code
	}
	respondEnvelope(c, statusCode, false, message, payload)
}

func respondOKEnvelope(c *gin.Context, message string, data interface{}) {
	respondEnvelope(c, http.StatusOK, true, message, data)
}
