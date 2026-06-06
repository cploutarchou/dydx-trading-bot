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
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	now := time.Now()
	result, err := r.db.Exec(
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
	)

	if err != nil {
		return fmt.Errorf("failed to create key: %w", err)
	}

	lastID, err := result.LastInsertId()
	if err != nil {
		return fmt.Errorf("failed to get last insert ID: %w", err)
	}

	key.ID = int(lastID)
	key.CreatedAt = now
	key.UpdatedAt = now

	return nil
}

func (r *KeyRepository) GetKeyByUserAndNetwork(userID int, network string) (*models.DYDXKey, error) {
	query := `
		SELECT id, user_id, network, chain_address, encrypted_secret, COALESCE(secret_hash, ''), COALESCE(secret_masked, ''), is_active, created_at, updated_at
		FROM dydx_keys
		WHERE user_id = ? AND network = ? AND is_active = true
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
		WHERE user_id = ? AND is_active = true
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
		SET chain_address = ?, encrypted_secret = ?, secret_hash = ?, secret_masked = ?, updated_at = ?
		WHERE id = ? AND user_id = ?
	`

	now := time.Now()
	result, err := r.db.Exec(
		query,
		key.ChainAddress,
		key.EncryptedSecret,
		key.SecretHash,
		key.SecretMasked,
		now,
		key.ID,
		key.UserID,
	)

	if err != nil {
		return fmt.Errorf("failed to update key: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("key not found or unauthorized")
	}

	key.UpdatedAt = now

	return nil
}

func (r *KeyRepository) DeleteKey(userID int, network string) error {
	query := `
		UPDATE dydx_keys
		SET is_active = false, updated_at = ?
		WHERE user_id = ? AND network = ?
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
