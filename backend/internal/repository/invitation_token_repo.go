package repository

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// InvitationTokenRepository manages one-time / limited-use registration invitation tokens.
type InvitationTokenRepository struct {
	db       SQLRunner
	dbDriver string
}

// WithTx returns a copy of the repository that executes within tx.
func (r *InvitationTokenRepository) WithTx(tx *sql.Tx) *InvitationTokenRepository {
	return &InvitationTokenRepository{db: tx, dbDriver: r.dbDriver}
}

func NewInvitationTokenRepository(db *sql.DB) *InvitationTokenRepository {
	driver := os.Getenv("DB_TYPE")
	if driver == "" {
		driver = os.Getenv("DB_DRIVER")
	}
	if driver == "" {
		driver = "postgres"
	}
	return &InvitationTokenRepository{db: db, dbDriver: driver}
}

func (r *InvitationTokenRepository) bindQuery(query string) string {
	if r == nil || !strings.Contains(strings.ToLower(r.dbDriver), "postgres") {
		return query
	}
	var b strings.Builder
	b.Grow(len(query) + 16)
	idx := 1
	for i := 0; i < len(query); i++ {
		if query[i] == '?' {
			b.WriteString(fmt.Sprintf("$%d", idx))
			idx++
			continue
		}
		b.WriteByte(query[i])
	}
	return b.String()
}

func (r *InvitationTokenRepository) Create(token *models.InvitationToken) error {
	query := `
		INSERT INTO invitation_tokens (
			token_code, label, ib_name, campaign_name, max_uses, used_count,
			created_by_user_id, last_used_by_user_id, expires_at, last_used_at, revoked_at,
			created_at, updated_at
		)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		RETURNING id
	`

	now := time.Now().UTC()
	if err := r.db.QueryRow(
		r.bindQuery(query),
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
	).Scan(&token.ID); err != nil {
		return fmt.Errorf("failed to create invitation token: %w", err)
	}
	token.CreatedAt = now
	token.UpdatedAt = now

	return nil
}

func (r *InvitationTokenRepository) List(limit int, offset int) ([]*models.InvitationToken, error) {
	query := `
		SELECT id, token_code, label, ib_name, campaign_name, max_uses, used_count,
		       created_by_user_id, last_used_by_user_id, expires_at, last_used_at, revoked_at,
		       created_at, updated_at
		FROM invitation_tokens
		ORDER BY created_at DESC
		LIMIT ? OFFSET ?
	`

	rows, err := r.db.Query(r.bindQuery(query), limit, offset)
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
	if err := r.db.QueryRow(r.bindQuery(`SELECT COUNT(*) FROM invitation_tokens`)).Scan(&count); err != nil {
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
		WHERE id = ?
		LIMIT 1
	`

	token := &models.InvitationToken{}
	if err := r.db.QueryRow(r.bindQuery(query), id).Scan(
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
		WHERE token_code = ?
		LIMIT 1
	`

	token := &models.InvitationToken{}
	if err := r.db.QueryRow(r.bindQuery(query), tokenCode).Scan(
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
		SET revoked_at = ?, updated_at = ?
		WHERE token_code = ? AND revoked_at IS NULL
	`

	now := time.Now().UTC()
	result, err := r.db.Exec(r.bindQuery(query), now, now, tokenCode)
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
		    last_used_at = ?,
		    last_used_by_user_id = ?,
		    updated_at = ?
		WHERE token_code = ?
		  AND revoked_at IS NULL
		  AND (expires_at IS NULL OR expires_at > ?)
		  AND used_count < max_uses
	`

	now := time.Now().UTC()
	result, err := r.db.Exec(r.bindQuery(query), now, usedByUserID, now, tokenCode, now)
	if err != nil {
		return false, fmt.Errorf("failed to redeem invitation token: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return false, fmt.Errorf("failed to read redeem rows affected: %w", err)
	}

	return rowsAffected > 0, nil
}
