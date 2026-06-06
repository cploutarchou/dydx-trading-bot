package repository

import (
	"database/sql"
	"fmt"
	"log"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

type PartnerRelationshipRepository struct {
	db *sql.DB
}

func NewPartnerRelationshipRepository(db *sql.DB) *PartnerRelationshipRepository {
	return &PartnerRelationshipRepository{db: db}
}

func (r *PartnerRelationshipRepository) Upsert(relationship *models.PartnerRelationship) error {
	query := `
		INSERT INTO partner_relationships (
			sponsor_user_id,
			partner_user_id,
			relationship_type,
			source_application_id,
			is_active,
			created_at,
			updated_at
		)
		VALUES (?, ?, ?, ?, ?, ?, ?)
		ON DUPLICATE KEY UPDATE
			sponsor_user_id = VALUES(sponsor_user_id),
			relationship_type = VALUES(relationship_type),
			source_application_id = VALUES(source_application_id),
			is_active = VALUES(is_active),
			updated_at = VALUES(updated_at)
	`

	now := time.Now().UTC()
	result, err := r.db.Exec(
		query,
		relationship.SponsorUserID,
		relationship.PartnerUserID,
		relationship.RelationshipType,
		relationship.SourceApplicationID,
		relationship.IsActive,
		now,
		now,
	)

	if err != nil {
		return fmt.Errorf("failed to upsert partner relationship: %w", err)
	}

	lastID, err := result.LastInsertId()
	if err != nil {
		return fmt.Errorf("failed to get last insert ID: %w", err)
	}

	relationship.ID = int(lastID)
	relationship.CreatedAt = now
	relationship.UpdatedAt = now

	return nil
}

func (r *PartnerRelationshipRepository) List(limit int, offset int) ([]*models.PartnerRelationship, error) {
	query := `
		SELECT id, sponsor_user_id, partner_user_id, relationship_type, source_application_id, is_active, created_at, updated_at
		FROM partner_relationships
		ORDER BY updated_at DESC
		LIMIT ? OFFSET ?
	`
	return r.queryMany(query, limit, offset)
}

func (r *PartnerRelationshipRepository) ListBySponsor(sponsorUserID int, limit int, offset int) ([]*models.PartnerRelationship, error) {
	query := `
		SELECT id, sponsor_user_id, partner_user_id, relationship_type, source_application_id, is_active, created_at, updated_at
		FROM partner_relationships
		WHERE sponsor_user_id = ?
		ORDER BY updated_at DESC
		LIMIT ? OFFSET ?
	`
	return r.queryMany(query, sponsorUserID, limit, offset)
}

func (r *PartnerRelationshipRepository) GetByPartner(partnerUserID int) (*models.PartnerRelationship, error) {
	query := `
		SELECT id, sponsor_user_id, partner_user_id, relationship_type, source_application_id, is_active, created_at, updated_at
		FROM partner_relationships
		WHERE partner_user_id = ?
		LIMIT 1
	`

	relationship := &models.PartnerRelationship{}
	if err := r.db.QueryRow(query, partnerUserID).Scan(
		&relationship.ID,
		&relationship.SponsorUserID,
		&relationship.PartnerUserID,
		&relationship.RelationshipType,
		&relationship.SourceApplicationID,
		&relationship.IsActive,
		&relationship.CreatedAt,
		&relationship.UpdatedAt,
	); err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to load partner relationship: %w", err)
	}

	return relationship, nil
}

func (r *PartnerRelationshipRepository) CountDirectPartners(sponsorUserID int) (int, error) {
	var count int
	query := `SELECT COUNT(*) FROM partner_relationships WHERE sponsor_user_id = ? AND is_active = TRUE`
	if err := r.db.QueryRow(query, sponsorUserID).Scan(&count); err != nil {
		return 0, fmt.Errorf("failed to count direct partners: %w", err)
	}
	return count, nil
}

func (r *PartnerRelationshipRepository) DeactivateByPartner(partnerUserID int) error {
	result, err := r.db.Exec(
		`UPDATE partner_relationships SET is_active = FALSE, updated_at = ? WHERE partner_user_id = ? AND is_active = TRUE`,
		time.Now().UTC(),
		partnerUserID,
	)
	if err != nil {
		return fmt.Errorf("failed to deactivate partner relationship: %w", err)
	}
	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to read relationship rows affected: %w", err)
	}
	if rows == 0 {
		return fmt.Errorf("active partner relationship not found")
	}
	return nil
}

func (r *PartnerRelationshipRepository) queryMany(query string, args ...interface{}) ([]*models.PartnerRelationship, error) {
	rows, err := r.db.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query partner relationships: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close partner relationship rows: %v", closeErr)
		}
	}()

	relationships := make([]*models.PartnerRelationship, 0)
	for rows.Next() {
		relationship := &models.PartnerRelationship{}
		if err := rows.Scan(
			&relationship.ID,
			&relationship.SponsorUserID,
			&relationship.PartnerUserID,
			&relationship.RelationshipType,
			&relationship.SourceApplicationID,
			&relationship.IsActive,
			&relationship.CreatedAt,
			&relationship.UpdatedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan partner relationship: %w", err)
		}
		relationships = append(relationships, relationship)
	}

	return relationships, rows.Err()
}
