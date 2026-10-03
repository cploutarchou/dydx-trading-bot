package handlers

import (
	"fmt"
	"net/http"
	"strconv"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

// AuditLogHandler handles audit log API endpoints
type AuditLogHandler struct {
	service *services.AuditLogService
}

// NewAuditLogHandler creates a new audit log handler
func NewAuditLogHandler(service *services.AuditLogService) *AuditLogHandler {
	return &AuditLogHandler{
		service: service,
	}
}

// CreateAuditLog creates a new audit log entry
func (h *AuditLogHandler) CreateAuditLog(c *gin.Context) {
	var req struct {
		UserID       *int        `json:"user_id"`
		Action       string      `json:"action" binding:"required"`
		ResourceType string      `json:"resource_type" binding:"required"`
		ResourceID   *string     `json:"resource_id"`
		Details      interface{} `json:"details"`
		IPAddress    *string     `json:"ip_address"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	// Get IP address from request if not provided
	if req.IPAddress == nil {
		ip := c.ClientIP()
		req.IPAddress = &ip
	}

	auditLog, err := h.service.CreateAuditLog(req.UserID, req.Action, req.ResourceType, req.ResourceID, req.Details, req.IPAddress)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to create audit log: %v", err),
		})
		return
	}

	c.JSON(http.StatusCreated, APIResponse{
		Success:   true,
		Data:      auditLog.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetAuditLog retrieves an audit log by ID
func (h *AuditLogHandler) GetAuditLog(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Invalid audit log ID",
		})
		return
	}

	auditLog, err := h.service.GetAuditLog(id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get audit log: %v", err),
		})
		return
	}

	if auditLog == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Audit log not found",
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      auditLog.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// ListAuditLogsByUser lists audit logs for a user
func (h *AuditLogHandler) ListAuditLogsByUser(c *gin.Context) {
	userIDStr := c.Param("user_id")
	userID, err := strconv.Atoi(userIDStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Invalid user ID",
		})
		return
	}

	// Bound the page size: audit_logs is append-only and grows with every
	// authenticated action, so an unbounded listing would degrade without limit.
	limit := 200
	if parsed, err := strconv.Atoi(c.DefaultQuery("limit", "200")); err == nil && parsed > 0 {
		limit = parsed
	}
	if limit > 1000 {
		limit = 1000
	}

	auditLogs, err := h.service.ListAuditLogsByUser(userID, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to list audit logs: %v", err),
		})
		return
	}

	result := make([]map[string]interface{}, 0)
	for _, al := range auditLogs {
		result = append(result, al.ToDict())
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"audit_logs": result,
			"count":      len(result),
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// ListAuditLogsByAction lists audit logs by action
func (h *AuditLogHandler) ListAuditLogsByAction(c *gin.Context) {
	action := c.Query("action")
	if action == "" {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "action query parameter is required",
		})
		return
	}

	limitStr := c.DefaultQuery("limit", "100")
	limit, err := strconv.Atoi(limitStr)
	if err != nil || limit <= 0 {
		limit = 100
	}

	auditLogs, err := h.service.ListAuditLogsByAction(action, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to list audit logs: %v", err),
		})
		return
	}

	result := make([]map[string]interface{}, 0)
	for _, al := range auditLogs {
		result = append(result, al.ToDict())
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"audit_logs": result,
			"count":      len(result),
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// ListAllAuditLogs lists all audit logs with pagination
func (h *AuditLogHandler) ListAllAuditLogs(c *gin.Context) {
	limitStr := c.DefaultQuery("limit", "100")
	offsetStr := c.DefaultQuery("offset", "0")

	limit, err := strconv.Atoi(limitStr)
	if err != nil || limit <= 0 {
		limit = 100
	}

	offset, err := strconv.Atoi(offsetStr)
	if err != nil || offset < 0 {
		offset = 0
	}

	auditLogs, err := h.service.ListAllAuditLogs(limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to list audit logs: %v", err),
		})
		return
	}

	result := make([]map[string]interface{}, 0)
	for _, al := range auditLogs {
		result = append(result, al.ToDict())
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"audit_logs": result,
			"count":      len(result),
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}
