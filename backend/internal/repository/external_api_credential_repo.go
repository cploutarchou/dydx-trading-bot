package repository

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

type ExternalAPICredentialRepository struct {
	db *sql.DB
}

func NewExternalAPICredentialRepository(db *sql.DB) *ExternalAPICredentialRepository {
	return &ExternalAPICredentialRepository{db: db}
}

func (r *ExternalAPICredentialRepository) GetByUserAndProvider(userID int, provider string) (*models.ExternalAPICredential, error) {
	query := `
		SELECT id, user_id, provider, label, encrypted_api_key, COALESCE(api_key_hash, ''), COALESCE(api_key_salt, ''), COALESCE(api_key_masked, ''), is_active, created_at, updated_at
		FROM external_api_credentials
		WHERE user_id = $1 AND provider = $2
		LIMIT 1
	`

	credential := &models.ExternalAPICredential{}
	err := r.db.QueryRow(query, userID, provider).Scan(
		&credential.ID,
		&credential.UserID,
		&credential.Provider,
		&credential.Label,
		&credential.EncryptedAPIKey,
		&credential.APIKeyHash,
		&credential.APIKeySalt,
		&credential.APIKeyMasked,
		&credential.IsActive,
		&credential.CreatedAt,
		&credential.UpdatedAt,
	)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get external api credential: %w", err)
	}

	return credential, nil
}

func (r *ExternalAPICredentialRepository) Upsert(credential *models.ExternalAPICredential) error {
	now := time.Now().UTC()
	if r.usesSQLite() {
		return r.upsertSQLite(credential, now)
	}

	query := `
		INSERT INTO external_api_credentials (user_id, provider, label, encrypted_api_key, api_key_hash, api_key_salt, api_key_masked, is_active, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		ON CONFLICT (user_id, provider) DO UPDATE SET
			label = EXCLUDED.label,
			encrypted_api_key = EXCLUDED.encrypted_api_key,
			api_key_hash = EXCLUDED.api_key_hash,
			api_key_salt = EXCLUDED.api_key_salt,
			api_key_masked = EXCLUDED.api_key_masked,
			is_active = EXCLUDED.is_active,
			updated_at = EXCLUDED.updated_at
		RETURNING id, created_at, updated_at
	`

	if err := r.db.QueryRow(
		query,
		credential.UserID,
		credential.Provider,
		credential.Label,
		credential.EncryptedAPIKey,
		credential.APIKeyHash,
		credential.APIKeySalt,
		credential.APIKeyMasked,
		credential.IsActive,
		now,
		now,
	).Scan(&credential.ID, &credential.CreatedAt, &credential.UpdatedAt); err != nil {
		return fmt.Errorf("failed to upsert external api credential: %w", err)
	}
	return nil
}

func (r *ExternalAPICredentialRepository) usesSQLite() bool {
	if r == nil || r.db == nil {
		return false
	}
	var version string
	return r.db.QueryRow(`SELECT sqlite_version()`).Scan(&version) == nil
}

func (r *ExternalAPICredentialRepository) upsertSQLite(credential *models.ExternalAPICredential, now time.Time) error {
	existing, err := r.GetByUserAndProvider(credential.UserID, credential.Provider)
	if err != nil {
		return fmt.Errorf("failed to check external api credential before sqlite upsert: %w", err)
	}

	if existing == nil {
		if _, err := r.db.Exec(
			`INSERT INTO external_api_credentials (user_id, provider, label, encrypted_api_key, api_key_hash, api_key_salt, api_key_masked, is_active, created_at, updated_at)
			VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
			credential.UserID,
			credential.Provider,
			credential.Label,
			credential.EncryptedAPIKey,
			credential.APIKeyHash,
			credential.APIKeySalt,
			credential.APIKeyMasked,
			credential.IsActive,
			now,
			now,
		); err != nil {
			return fmt.Errorf("failed to insert external api credential in sqlite test db: %w", err)
		}
	} else if _, err := r.db.Exec(
		`UPDATE external_api_credentials
		SET label = $1, encrypted_api_key = $2, api_key_hash = $3, api_key_salt = $4, api_key_masked = $5, is_active = $6, updated_at = $7
		WHERE user_id = $8 AND provider = $9`,
		credential.Label,
		credential.EncryptedAPIKey,
		credential.APIKeyHash,
		credential.APIKeySalt,
		credential.APIKeyMasked,
		credential.IsActive,
		now,
		credential.UserID,
		credential.Provider,
	); err != nil {
		return fmt.Errorf("failed to update external api credential in sqlite test db: %w", err)
	}

	stored, err := r.GetByUserAndProvider(credential.UserID, credential.Provider)
	if err != nil {
		return fmt.Errorf("failed to reload external api credential after sqlite upsert: %w", err)
	}
	if stored == nil {
		return fmt.Errorf("external api credential was not found after sqlite upsert")
	}
	credential.ID = stored.ID
	credential.CreatedAt = stored.CreatedAt
	credential.UpdatedAt = stored.UpdatedAt
	return nil
}

func (r *ExternalAPICredentialRepository) Deactivate(userID int, provider string) error {
	result, err := r.db.Exec(
		`UPDATE external_api_credentials SET is_active = false, updated_at = $1 WHERE user_id = $2 AND provider = $3`,
		time.Now().UTC(),
		userID,
		provider,
	)
	if err != nil {
		return fmt.Errorf("failed to deactivate external api credential: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to check deactivated rows: %w", err)
	}
	if rowsAffected == 0 {
		return fmt.Errorf("credential not found")
	}

	return nil
}
