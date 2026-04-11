package repository

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

type UserMFARepository struct {
	db *sql.DB
}

func NewUserMFARepository(db *sql.DB) *UserMFARepository {
	return &UserMFARepository{db: db}
}

func (r *UserMFARepository) GetByUserID(userID int) (*models.UserMFA, error) {
	query := `SELECT id, user_id, encrypted_secret, encrypted_backup_codes, enabled, verified_at, last_used_at, created_at, updated_at FROM user_mfa_credentials WHERE user_id = $1 LIMIT 1`
	credential := &models.UserMFA{}
	err := r.db.QueryRow(query, userID).Scan(
		&credential.ID,
		&credential.UserID,
		&credential.EncryptedSecret,
		&credential.EncryptedBackupCodes,
		&credential.Enabled,
		&credential.VerifiedAt,
		&credential.LastUsedAt,
		&credential.CreatedAt,
		&credential.UpdatedAt,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get user mfa credential: %w", err)
	}
	return credential, nil
}

func (r *UserMFARepository) Upsert(credential *models.UserMFA) error {
	now := time.Now().UTC()
	query := `
		INSERT INTO user_mfa_credentials (user_id, encrypted_secret, encrypted_backup_codes, enabled, verified_at, last_used_at, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		ON CONFLICT (user_id)
		DO UPDATE SET encrypted_secret = EXCLUDED.encrypted_secret,
		             encrypted_backup_codes = EXCLUDED.encrypted_backup_codes,
		             enabled = EXCLUDED.enabled,
		             verified_at = EXCLUDED.verified_at,
		             last_used_at = EXCLUDED.last_used_at,
		             updated_at = EXCLUDED.updated_at
		RETURNING id, created_at, updated_at`
	return r.db.QueryRow(
		query,
		credential.UserID,
		credential.EncryptedSecret,
		credential.EncryptedBackupCodes,
		credential.Enabled,
		credential.VerifiedAt,
		credential.LastUsedAt,
		now,
		now,
	).Scan(&credential.ID, &credential.CreatedAt, &credential.UpdatedAt)
}

func (r *UserMFARepository) MarkVerified(userID int, verifiedAt time.Time) error {
	_, err := r.db.Exec(`UPDATE user_mfa_credentials SET enabled = TRUE, verified_at = $2, last_used_at = $2, updated_at = $2 WHERE user_id = $1`, userID, verifiedAt)
	if err != nil {
		return fmt.Errorf("failed to mark mfa verified: %w", err)
	}
	return nil
}

func (r *UserMFARepository) DeleteByUserID(userID int) (bool, error) {
	result, err := r.db.Exec(`DELETE FROM user_mfa_credentials WHERE user_id = $1`, userID)
	if err != nil {
		return false, fmt.Errorf("failed to delete user mfa credential: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return false, fmt.Errorf("failed to read deleted mfa credential rows: %w", err)
	}

	return rowsAffected > 0, nil
}
