package repository

import (
	"database/sql"
	"fmt"
	"log"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

type KeyRepository struct {
	db *sql.DB
}

func NewKeyRepository(db *sql.DB) *KeyRepository {
	return &KeyRepository{db: db}
}

func (r *KeyRepository) CreateKey(key *models.DYDXKey) error {
	query := `
		INSERT INTO dydx_keys (user_id, network, chain_address, encrypted_secret, secret_hash, secret_masked, is_active, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		RETURNING id, created_at, updated_at
	`

	now := time.Now()
	err := r.db.QueryRow(
		query,
		key.UserID,
		key.Network,
		key.ChainAddress,
		key.EncryptedSecret,
		key.SecretHash,
		key.SecretMasked,
		true,
		now,
		now,
	).Scan(&key.ID, &key.CreatedAt, &key.UpdatedAt)

	if err != nil {
		return fmt.Errorf("failed to create key: %w", err)
	}

	return nil
}

func (r *KeyRepository) GetKeyByUserAndNetwork(userID int, network string) (*models.DYDXKey, error) {
	query := `
		SELECT id, user_id, network, chain_address, encrypted_secret, COALESCE(secret_hash, ''), COALESCE(secret_masked, ''), is_active, created_at, updated_at
		FROM dydx_keys
		WHERE user_id = $1 AND network = $2 AND is_active = true
		LIMIT 1
	`

	key := &models.DYDXKey{}
	err := r.db.QueryRow(query, userID, network).Scan(
		&key.ID,
		&key.UserID,
		&key.Network,
		&key.ChainAddress,
		&key.EncryptedSecret,
		&key.SecretHash,
		&key.SecretMasked,
		&key.IsActive,
		&key.CreatedAt,
		&key.UpdatedAt,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get key: %w", err)
	}

	return key, nil
}

func (r *KeyRepository) GetActiveKeysByUser(userID int) ([]models.DYDXKey, error) {
	query := `
		SELECT id, user_id, network, chain_address, encrypted_secret, COALESCE(secret_hash, ''), COALESCE(secret_masked, ''), is_active, created_at, updated_at
		FROM dydx_keys
		WHERE user_id = $1 AND is_active = true
		ORDER BY created_at DESC
	`

	rows, err := r.db.Query(query, userID)
	if err != nil {
		return nil, fmt.Errorf("failed to query keys: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close key rows: %v", closeErr)
		}
	}()

	var keys []models.DYDXKey
	for rows.Next() {
		key := models.DYDXKey{}
		err := rows.Scan(
			&key.ID,
			&key.UserID,
			&key.Network,
			&key.ChainAddress,
			&key.EncryptedSecret,
			&key.SecretHash,
			&key.SecretMasked,
			&key.IsActive,
			&key.CreatedAt,
			&key.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan key: %w", err)
		}
		keys = append(keys, key)
	}

	if err = rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating keys: %w", err)
	}

	return keys, nil
}

func (r *KeyRepository) UpdateKey(key *models.DYDXKey) error {
	query := `
		UPDATE dydx_keys
		SET chain_address = $1, encrypted_secret = $2, secret_hash = $3, secret_masked = $4, updated_at = $5
		WHERE id = $6 AND user_id = $7
		RETURNING updated_at
	`

	now := time.Now()
	err := r.db.QueryRow(
		query,
		key.ChainAddress,
		key.EncryptedSecret,
		key.SecretHash,
		key.SecretMasked,
		now,
		key.ID,
		key.UserID,
	).Scan(&key.UpdatedAt)

	if err != nil {
		if err == sql.ErrNoRows {
			return fmt.Errorf("key not found or unauthorized")
		}
		return fmt.Errorf("failed to update key: %w", err)
	}

	return nil
}

func (r *KeyRepository) DeleteKey(userID int, network string) error {
	query := `
		UPDATE dydx_keys
		SET is_active = false, updated_at = $1
		WHERE user_id = $2 AND network = $3
	`

	result, err := r.db.Exec(query, time.Now(), userID, network)
	if err != nil {
		return fmt.Errorf("failed to delete key: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("no key found to delete")
	}

	return nil
}
