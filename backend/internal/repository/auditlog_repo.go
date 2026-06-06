package repository

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// AuditLogRepository handles audit log database operations
type AuditLogRepository struct {
	db *sql.DB
}

// NewAuditLogRepository creates a new audit log repository
func NewAuditLogRepository(db *sql.DB) *AuditLogRepository {
	return &AuditLogRepository{db: db}
}

// CreateAuditLog creates a new audit log entry
func (r *AuditLogRepository) CreateAuditLog(auditLog *models.AuditLog) error {
	query := `
		INSERT INTO audit_logs (
			user_id, action, resource_type, resource_id, details, status, ip_address, created_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
	`

	detailsJSON := ""
	if auditLog.Details != nil {
		if b, err := json.Marshal(auditLog.Details); err == nil {
			detailsJSON = string(b)
		}
	}

	now := time.Now()
	result, err := r.db.Exec(
		query,
		auditLog.UserID, auditLog.Action, auditLog.ResourceType, auditLog.ResourceID,
		detailsJSON, auditLog.Status, auditLog.IPAddress, now,
	)

	if err != nil {
		return fmt.Errorf("failed to create audit log: %w", err)
	}

	lastID, err := result.LastInsertId()
	if err != nil {
		return fmt.Errorf("failed to get last insert ID: %w", err)
	}

	auditLog.ID = int(lastID)
	auditLog.CreatedAt = &now

	return nil
}

// GetAuditLogByID retrieves an audit log by ID
func (r *AuditLogRepository) GetAuditLogByID(id int) (*models.AuditLog, error) {
	query := `
		SELECT id, user_id, action, resource_type, resource_id, details, status, ip_address, created_at
		FROM audit_logs
		WHERE id = ?
		LIMIT 1
	`

	auditLog := &models.AuditLog{}
	var detailsJSON sql.NullString

	err := r.db.QueryRow(query, id).Scan(
		&auditLog.ID, &auditLog.UserID, &auditLog.Action, &auditLog.ResourceType,
		&auditLog.ResourceID, &detailsJSON, &auditLog.Status, &auditLog.IPAddress, &auditLog.CreatedAt,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get audit log: %w", err)
	}

	// Parse details JSON if present
	if detailsJSON.Valid && detailsJSON.String != "" {
		var details interface{}
		if err := json.Unmarshal([]byte(detailsJSON.String), &details); err == nil {
			auditLog.Details = details
		}
	}

	return auditLog, nil
}

// GetAuditLogsByUser retrieves all audit logs for a user
func (r *AuditLogRepository) GetAuditLogsByUser(userID int) ([]models.AuditLog, error) {
	query := `
		SELECT id, user_id, action, resource_type, resource_id, details, status, ip_address, created_at
		FROM audit_logs
		WHERE user_id = ?
		ORDER BY created_at DESC
	`

	rows, err := r.db.Query(query, userID)
	if err != nil {
		return nil, fmt.Errorf("failed to query audit logs: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close audit log rows: %v", closeErr)
		}
	}()

	var auditLogs []models.AuditLog
	for rows.Next() {
		auditLog := models.AuditLog{}
		var detailsJSON sql.NullString

		err := rows.Scan(
			&auditLog.ID, &auditLog.UserID, &auditLog.Action, &auditLog.ResourceType,
			&auditLog.ResourceID, &detailsJSON, &auditLog.Status, &auditLog.IPAddress, &auditLog.CreatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan audit log: %w", err)
		}

		// Parse details JSON if present
		if detailsJSON.Valid && detailsJSON.String != "" {
			var details interface{}
			if err := json.Unmarshal([]byte(detailsJSON.String), &details); err == nil {
				auditLog.Details = details
			}
		}

		auditLogs = append(auditLogs, auditLog)
	}

	return auditLogs, rows.Err()
}

// GetAuditLogsByAction retrieves audit logs by action type
func (r *AuditLogRepository) GetAuditLogsByAction(action string, limit int) ([]models.AuditLog, error) {
	query := `
		SELECT id, user_id, action, resource_type, resource_id, details, status, ip_address, created_at
		FROM audit_logs
		WHERE action = ?
		ORDER BY created_at DESC
		LIMIT ?
	`

	rows, err := r.db.Query(query, action, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query audit logs: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close audit log rows: %v", closeErr)
		}
	}()

	var auditLogs []models.AuditLog
	for rows.Next() {
		auditLog := models.AuditLog{}
		var detailsJSON sql.NullString

		err := rows.Scan(
			&auditLog.ID, &auditLog.UserID, &auditLog.Action, &auditLog.ResourceType,
			&auditLog.ResourceID, &detailsJSON, &auditLog.Status, &auditLog.IPAddress, &auditLog.CreatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan audit log: %w", err)
		}

		// Parse details JSON if present
		if detailsJSON.Valid && detailsJSON.String != "" {
			var details interface{}
			if err := json.Unmarshal([]byte(detailsJSON.String), &details); err == nil {
				auditLog.Details = details
			}
		}

		auditLogs = append(auditLogs, auditLog)
	}

	return auditLogs, rows.Err()
}

// ListAllAuditLogs retrieves all audit logs with pagination
func (r *AuditLogRepository) ListAllAuditLogs(limit int, offset int) ([]models.AuditLog, error) {
	query := `
		SELECT id, user_id, action, resource_type, resource_id, details, status, ip_address, created_at
		FROM audit_logs
		ORDER BY created_at DESC
		LIMIT ? OFFSET ?
	`

	rows, err := r.db.Query(query, limit, offset)
	if err != nil {
		return nil, fmt.Errorf("failed to query audit logs: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close audit log rows: %v", closeErr)
		}
	}()

	var auditLogs []models.AuditLog
	for rows.Next() {
		auditLog := models.AuditLog{}
		var detailsJSON sql.NullString

		err := rows.Scan(
			&auditLog.ID, &auditLog.UserID, &auditLog.Action, &auditLog.ResourceType,
			&auditLog.ResourceID, &detailsJSON, &auditLog.Status, &auditLog.IPAddress, &auditLog.CreatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan audit log: %w", err)
		}

		// Parse details JSON if present
		if detailsJSON.Valid && detailsJSON.String != "" {
			var details interface{}
			if err := json.Unmarshal([]byte(detailsJSON.String), &details); err == nil {
				auditLog.Details = details
			}
		}

		auditLogs = append(auditLogs, auditLog)
	}

	return auditLogs, rows.Err()
}
