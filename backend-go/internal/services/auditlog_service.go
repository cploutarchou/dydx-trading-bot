package services

import (
	"fmt"
	"log"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

// AuditLogService manages audit log operations
type AuditLogService struct {
	repo *repository.AuditLogRepository
}

// NewAuditLogService creates a new audit log service
func NewAuditLogService(repo *repository.AuditLogRepository) *AuditLogService {
	return &AuditLogService{repo: repo}
}

// CreateAuditLog creates a new audit log entry
func (s *AuditLogService) CreateAuditLog(userID *int, action, resourceType string, resourceID *string, details interface{}, ipAddress *string) (*models.AuditLog, error) {
	if action == "" {
		return nil, fmt.Errorf("action is required")
	}
	if resourceType == "" {
		return nil, fmt.Errorf("resource_type is required")
	}

	status := "success"
	now := time.Now()

	auditLog := &models.AuditLog{
		UserID:       userID,
		Action:       action,
		ResourceType: resourceType,
		ResourceID:   resourceID,
		Details:      details,
		Status:       &status,
		IPAddress:    ipAddress,
		CreatedAt:    &now,
	}

	if err := s.repo.CreateAuditLog(auditLog); err != nil {
		return nil, fmt.Errorf("failed to create audit log: %w", err)
	}

	log.Printf("✅ Created audit log: action=%s resource_type=%s", action, resourceType)
	return auditLog, nil
}

// GetAuditLog retrieves an audit log by ID
func (s *AuditLogService) GetAuditLog(id int) (*models.AuditLog, error) {
	if id <= 0 {
		return nil, fmt.Errorf("invalid audit log id")
	}

	auditLog, err := s.repo.GetAuditLogByID(id)
	if err != nil {
		return nil, fmt.Errorf("failed to get audit log: %w", err)
	}

	return auditLog, nil
}

// ListAuditLogsByUser retrieves all audit logs for a user
func (s *AuditLogService) ListAuditLogsByUser(userID int) ([]models.AuditLog, error) {
	if userID <= 0 {
		return nil, fmt.Errorf("invalid user id")
	}

	auditLogs, err := s.repo.GetAuditLogsByUser(userID)
	if err != nil {
		return nil, fmt.Errorf("failed to list audit logs: %w", err)
	}

	return auditLogs, nil
}

// ListAuditLogsByAction retrieves audit logs by action
func (s *AuditLogService) ListAuditLogsByAction(action string, limit int) ([]models.AuditLog, error) {
	if action == "" {
		return nil, fmt.Errorf("action is required")
	}
	if limit <= 0 {
		limit = 100
	}

	auditLogs, err := s.repo.GetAuditLogsByAction(action, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to list audit logs: %w", err)
	}

	return auditLogs, nil
}

// ListAllAuditLogs retrieves all audit logs with pagination
func (s *AuditLogService) ListAllAuditLogs(limit, offset int) ([]models.AuditLog, error) {
	if limit <= 0 {
		limit = 100
	}
	if offset < 0 {
		offset = 0
	}

	auditLogs, err := s.repo.ListAllAuditLogs(limit, offset)
	if err != nil {
		return nil, fmt.Errorf("failed to list audit logs: %w", err)
	}

	return auditLogs, nil
}
