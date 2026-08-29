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
		ON CONFLICT (user_id) DO UPDATE SET
			encrypted_secret = EXCLUDED.encrypted_secret,
			encrypted_backup_codes = EXCLUDED.encrypted_backup_codes,
			enabled = EXCLUDED.enabled,
			verified_at = EXCLUDED.verified_at,
			last_used_at = EXCLUDED.last_used_at,
			updated_at = EXCLUDED.updated_at
		RETURNING id, created_at, updated_at
	`
	err := r.db.QueryRow(
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

	if err != nil {
		return fmt.Errorf("failed to upsert MFA credential: %w", err)
	}
	if credential.CreatedAt.IsZero() {
		credential.CreatedAt = now
	}
	if credential.UpdatedAt.IsZero() {
		credential.UpdatedAt = now
	}

	return nil
}

func (r *UserMFARepository) MarkVerified(userID int, verifiedAt time.Time) error {
	now := time.Now().UTC()
	_, err := r.db.Exec(
		`UPDATE user_mfa_credentials SET enabled = TRUE, verified_at = $1, last_used_at = $2, updated_at = $3 WHERE user_id = $4`,
		verifiedAt,
		now,
		now,
		userID,
	)
	if err != nil {
		return fmt.Errorf("failed to mark mfa verified: %w", err)
	}
	return nil
}

// MarkUsed records a successful verification at a specific TOTP window.
// last_used_at stores the window's canonical timestamp (window*30) so the
// replay guard can reject any window <= the last used one, while keeping the
// enabled/verified semantics of MarkVerified.
func (r *UserMFARepository) MarkUsed(userID int, window int64) error {
	now := time.Now().UTC()
	_, err := r.db.Exec(
		`UPDATE user_mfa_credentials SET enabled = TRUE, verified_at = COALESCE(verified_at, $1), last_used_at = $2, updated_at = $3 WHERE user_id = $4`,
		now,
		time.Unix(window*30, 0).UTC(),
		now,
		userID,
	)
	if err != nil {
		return fmt.Errorf("failed to mark mfa used: %w", err)
	}
	return nil
}

// UpdateBackupCodes replaces the stored (encrypted) backup-code payload —
// used to consume a redeemed code.
func (r *UserMFARepository) UpdateBackupCodes(userID int, encryptedBackupCodes string) error {
	now := time.Now().UTC()
	_, err := r.db.Exec(
		`UPDATE user_mfa_credentials SET encrypted_backup_codes = $1, updated_at = $2 WHERE user_id = $3`,
		encryptedBackupCodes,
		now,
		userID,
	)
	if err != nil {
		return fmt.Errorf("failed to update mfa backup codes: %w", err)
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
