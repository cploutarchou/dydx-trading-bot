package repository

import (
	"database/sql"
	"fmt"
	"log"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// InvitationTokenRepository manages one-time / limited-use registration invitation tokens.
type InvitationTokenRepository struct {
	db *sql.DB
}

func NewInvitationTokenRepository(db *sql.DB) *InvitationTokenRepository {
	return &InvitationTokenRepository{db: db}
}

func (r *InvitationTokenRepository) Create(token *models.InvitationToken) error {
	query := `
		INSERT INTO invitation_tokens (
			token_code, label, ib_name, campaign_name, max_uses, used_count,
			created_by_user_id, last_used_by_user_id, expires_at, last_used_at, revoked_at,
			created_at, updated_at
		)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
		RETURNING id, created_at, updated_at
	`

	now := time.Now().UTC()
	if err := r.db.QueryRow(
		query,
		token.TokenCode,
		token.Label,
		token.IBName,
		token.CampaignName,
		token.MaxUses,
		token.UsedCount,
		token.CreatedByUserID,
		token.LastUsedByUserID,
		token.ExpiresAt,
		token.LastUsedAt,
		token.RevokedAt,
		now,
		now,
	).Scan(&token.ID, &token.CreatedAt, &token.UpdatedAt); err != nil {
		return fmt.Errorf("failed to create invitation token: %w", err)
	}

	return nil
}

func (r *InvitationTokenRepository) List(limit int, offset int) ([]*models.InvitationToken, error) {
	query := `
		SELECT id, token_code, label, ib_name, campaign_name, max_uses, used_count,
		       created_by_user_id, last_used_by_user_id, expires_at, last_used_at, revoked_at,
		       created_at, updated_at
		FROM invitation_tokens
		ORDER BY created_at DESC
		LIMIT $1 OFFSET $2
	`

	rows, err := r.db.Query(query, limit, offset)
	if err != nil {
		return nil, fmt.Errorf("failed to list invitation tokens: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close invitation token rows: %v", closeErr)
		}
	}()

	result := make([]*models.InvitationToken, 0, limit)
	for rows.Next() {
		token := &models.InvitationToken{}
		if err := rows.Scan(
			&token.ID,
			&token.TokenCode,
			&token.Label,
			&token.IBName,
			&token.CampaignName,
			&token.MaxUses,
			&token.UsedCount,
			&token.CreatedByUserID,
			&token.LastUsedByUserID,
			&token.ExpiresAt,
			&token.LastUsedAt,
			&token.RevokedAt,
			&token.CreatedAt,
			&token.UpdatedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan invitation token: %w", err)
		}
		result = append(result, token)
	}

	return result, rows.Err()
}

func (r *InvitationTokenRepository) Count() (int, error) {
	var count int
	if err := r.db.QueryRow(`SELECT COUNT(*) FROM invitation_tokens`).Scan(&count); err != nil {
		return 0, fmt.Errorf("failed to count invitation tokens: %w", err)
	}
	return count, nil
}

func (r *InvitationTokenRepository) GetByID(id int) (*models.InvitationToken, error) {
	query := `
		SELECT id, token_code, label, ib_name, campaign_name, max_uses, used_count,
		       created_by_user_id, last_used_by_user_id, expires_at, last_used_at, revoked_at,
		       created_at, updated_at
		FROM invitation_tokens
		WHERE id = $1
		LIMIT 1
	`

	token := &models.InvitationToken{}
	if err := r.db.QueryRow(query, id).Scan(
		&token.ID,
		&token.TokenCode,
		&token.Label,
		&token.IBName,
		&token.CampaignName,
		&token.MaxUses,
		&token.UsedCount,
		&token.CreatedByUserID,
		&token.LastUsedByUserID,
		&token.ExpiresAt,
		&token.LastUsedAt,
		&token.RevokedAt,
		&token.CreatedAt,
		&token.UpdatedAt,
	); err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get invitation token: %w", err)
	}
	return token, nil
}

func (r *InvitationTokenRepository) GetByTokenCode(tokenCode string) (*models.InvitationToken, error) {
	query := `
		SELECT id, token_code, label, ib_name, campaign_name, max_uses, used_count,
		       created_by_user_id, last_used_by_user_id, expires_at, last_used_at, revoked_at,
		       created_at, updated_at
		FROM invitation_tokens
		WHERE token_code = $1
		LIMIT 1
	`

	token := &models.InvitationToken{}
	if err := r.db.QueryRow(query, tokenCode).Scan(
		&token.ID,
		&token.TokenCode,
		&token.Label,
		&token.IBName,
		&token.CampaignName,
		&token.MaxUses,
		&token.UsedCount,
		&token.CreatedByUserID,
		&token.LastUsedByUserID,
		&token.ExpiresAt,
		&token.LastUsedAt,
		&token.RevokedAt,
		&token.CreatedAt,
		&token.UpdatedAt,
	); err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get invitation token by code: %w", err)
	}
	return token, nil
}

func (r *InvitationTokenRepository) RevokeByTokenCode(tokenCode string) error {
	query := `
		UPDATE invitation_tokens
		SET revoked_at = $1, updated_at = $1
		WHERE token_code = $2 AND revoked_at IS NULL
	`

	now := time.Now().UTC()
	result, err := r.db.Exec(query, now, tokenCode)
	if err != nil {
		return fmt.Errorf("failed to revoke invitation token: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to read revoke rows affected: %w", err)
	}
	if rowsAffected == 0 {
		return fmt.Errorf("invitation token not found or already revoked")
	}

	return nil
}

// Redeem increments usage if the token is active, not expired, and still has remaining uses.
// Returns true when token redemption succeeds.
func (r *InvitationTokenRepository) Redeem(tokenCode string, usedByUserID int) (bool, error) {
	query := `
		UPDATE invitation_tokens
		SET used_count = used_count + 1,
		    last_used_at = $1,
		    last_used_by_user_id = $2,
		    updated_at = $1
		WHERE token_code = $3
		  AND revoked_at IS NULL
		  AND (expires_at IS NULL OR expires_at > $1)
		  AND used_count < max_uses
	`

	now := time.Now().UTC()
	result, err := r.db.Exec(query, now, usedByUserID, tokenCode)
	if err != nil {
		return false, fmt.Errorf("failed to redeem invitation token: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return false, fmt.Errorf("failed to read redeem rows affected: %w", err)
	}

	return rowsAffected > 0, nil
}
