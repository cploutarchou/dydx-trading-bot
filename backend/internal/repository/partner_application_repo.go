package repository

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

type PartnerApplicationRepository struct {
	db       SQLRunner
	dbDriver string
}

// WithTx returns a copy of the repository that executes within tx.
func (r *PartnerApplicationRepository) WithTx(tx *sql.Tx) *PartnerApplicationRepository {
	return &PartnerApplicationRepository{db: tx, dbDriver: r.dbDriver}
}

func NewPartnerApplicationRepository(db *sql.DB) *PartnerApplicationRepository {
	driver := os.Getenv("DB_TYPE")
	if driver == "" {
		driver = os.Getenv("DB_DRIVER")
	}
	if driver == "" {
		driver = "postgres"
	}
	return &PartnerApplicationRepository{db: db, dbDriver: driver}
}

func (r *PartnerApplicationRepository) bindQuery(query string) string {
	return bindPlaceholders(r.dbDriver, query)
}

func (r *PartnerApplicationRepository) Create(application *models.PartnerApplication) error {
	query := `
		INSERT INTO partner_applications (
			applicant_user_id, sponsor_user_id, requested_role, status,
			business_name, notes, review_notes, reviewed_by_user_id, reviewed_at,
			created_at, updated_at
		)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		RETURNING id
	`

	now := time.Now().UTC()
	if err := r.db.QueryRow(
		r.bindQuery(query),
		application.ApplicantUserID,
		application.SponsorUserID,
		application.RequestedRole,
		application.Status,
		application.BusinessName,
		application.Notes,
		application.ReviewNotes,
		application.ReviewedByUserID,
		application.ReviewedAt,
		now,
		now,
	).Scan(&application.ID); err != nil {
		return fmt.Errorf("failed to create partner application: %w", err)
	}
	application.CreatedAt = now
	application.UpdatedAt = now

	return nil
}

func (r *PartnerApplicationRepository) GetByID(id int) (*models.PartnerApplication, error) {
	query := `
		SELECT id, applicant_user_id, sponsor_user_id, requested_role, status,
		       business_name, notes, review_notes, reviewed_by_user_id, reviewed_at,
		       created_at, updated_at
		FROM partner_applications
		WHERE id = ?
		LIMIT 1
	`

	application := &models.PartnerApplication{}
	if err := r.db.QueryRow(r.bindQuery(query), id).Scan(
		&application.ID,
		&application.ApplicantUserID,
		&application.SponsorUserID,
		&application.RequestedRole,
		&application.Status,
		&application.BusinessName,
		&application.Notes,
		&application.ReviewNotes,
		&application.ReviewedByUserID,
		&application.ReviewedAt,
		&application.CreatedAt,
		&application.UpdatedAt,
	); err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get partner application: %w", err)
	}

	return application, nil
}

func (r *PartnerApplicationRepository) List(limit int, offset int) ([]*models.PartnerApplication, error) {
	query := `
		SELECT id, applicant_user_id, sponsor_user_id, requested_role, status,
		       business_name, notes, review_notes, reviewed_by_user_id, reviewed_at,
		       created_at, updated_at
		FROM partner_applications
		ORDER BY created_at DESC
		LIMIT ? OFFSET ?
	`
	return r.queryMany(query, limit, offset)
}

func (r *PartnerApplicationRepository) ListByApplicant(applicantUserID int, limit int, offset int) ([]*models.PartnerApplication, error) {
	query := `
		SELECT id, applicant_user_id, sponsor_user_id, requested_role, status,
		       business_name, notes, review_notes, reviewed_by_user_id, reviewed_at,
		       created_at, updated_at
		FROM partner_applications
		WHERE applicant_user_id = ?
		ORDER BY created_at DESC
		LIMIT ? OFFSET ?
	`
	return r.queryMany(query, applicantUserID, limit, offset)
}

func (r *PartnerApplicationRepository) ListBySponsor(sponsorUserID int, limit int, offset int) ([]*models.PartnerApplication, error) {
	query := `
		SELECT id, applicant_user_id, sponsor_user_id, requested_role, status,
		       business_name, notes, review_notes, reviewed_by_user_id, reviewed_at,
		       created_at, updated_at
		FROM partner_applications
		WHERE sponsor_user_id = ?
		ORDER BY created_at DESC
		LIMIT ? OFFSET ?
	`
	return r.queryMany(query, sponsorUserID, limit, offset)
}

func (r *PartnerApplicationRepository) CountPending() (int, error) {
	var count int
	if err := r.db.QueryRow(r.bindQuery(`SELECT COUNT(*) FROM partner_applications WHERE status = 'pending'`)).Scan(&count); err != nil {
		return 0, fmt.Errorf("failed to count pending partner applications: %w", err)
	}
	return count, nil
}

func (r *PartnerApplicationRepository) UpdateReview(application *models.PartnerApplication) error {
	query := `
		UPDATE partner_applications
		SET status = ?,
		    review_notes = ?,
		    reviewed_by_user_id = ?,
		    reviewed_at = ?,
		    updated_at = ?
		WHERE id = ?
	`

	now := time.Now().UTC()
	result, err := r.db.Exec(
		r.bindQuery(query),
		application.Status,
		application.ReviewNotes,
		application.ReviewedByUserID,
		application.ReviewedAt,
		now,
		application.ID,
	)
	if err != nil {
		return fmt.Errorf("failed to update partner application review: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get partner application rows affected: %w", err)
	}
	if rowsAffected == 0 {
		return fmt.Errorf("partner application not found")
	}

	application.UpdatedAt = now
	return nil
}

func (r *PartnerApplicationRepository) queryMany(query string, args ...interface{}) ([]*models.PartnerApplication, error) {
	rows, err := r.db.Query(r.bindQuery(query), args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query partner applications: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close partner application rows: %v", closeErr)
		}
	}()

	applications := make([]*models.PartnerApplication, 0)
	for rows.Next() {
		application := &models.PartnerApplication{}
		if err := rows.Scan(
			&application.ID,
			&application.ApplicantUserID,
			&application.SponsorUserID,
			&application.RequestedRole,
			&application.Status,
			&application.BusinessName,
			&application.Notes,
			&application.ReviewNotes,
			&application.ReviewedByUserID,
			&application.ReviewedAt,
			&application.CreatedAt,
			&application.UpdatedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan partner application: %w", err)
		}
		applications = append(applications, application)
	}

	return applications, rows.Err()
}
