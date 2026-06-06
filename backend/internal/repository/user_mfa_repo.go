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
	query := `SELECT id, user_id, encrypted_secret, encrypted_backup_codes, enabled, verified_at, last_used_at, created_at, updated_at FROM user_mfa_credentials WHERE user_id = ? LIMIT 1`
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
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)
		ON DUPLICATE KEY UPDATE
			encrypted_secret = VALUES(encrypted_secret),
			encrypted_backup_codes = VALUES(encrypted_backup_codes),
			enabled = VALUES(enabled),
			verified_at = VALUES(verified_at),
			last_used_at = VALUES(last_used_at),
			updated_at = VALUES(updated_at)
	`
	result, err := r.db.Exec(
		query,
		credential.UserID,
		credential.EncryptedSecret,
		credential.EncryptedBackupCodes,
		credential.Enabled,
		credential.VerifiedAt,
		credential.LastUsedAt,
		now,
		now,
	)

	if err != nil {
		return fmt.Errorf("failed to upsert MFA credential: %w", err)
	}

	lastID, err := result.LastInsertId()
	if err != nil {
		return fmt.Errorf("failed to get last insert ID: %w", err)
	}

	credential.ID = int(lastID)
	credential.CreatedAt = now
	credential.UpdatedAt = now

	return nil
}

func (r *UserMFARepository) MarkVerified(userID int, verifiedAt time.Time) error {
	_, err := r.db.Exec(`UPDATE user_mfa_credentials SET enabled = TRUE, verified_at = ?, last_used_at = ?, updated_at = ? WHERE user_id = ?`, userID, verifiedAt)
	if err != nil {
		return fmt.Errorf("failed to mark mfa verified: %w", err)
	}
	return nil
}

func (r *UserMFARepository) DeleteByUserID(userID int) (bool, error) {
	result, err := r.db.Exec(`DELETE FROM user_mfa_credentials WHERE user_id = ?`, userID)
	if err != nil {
		return false, fmt.Errorf("failed to delete user mfa credential: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return false, fmt.Errorf("failed to read deleted mfa credential rows: %w", err)
	}

	return rowsAffected > 0, nil
}
