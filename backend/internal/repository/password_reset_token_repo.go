package repository

import (
	"context"
	"database/sql"
	"errors"
	"time"
)

var ErrPasswordResetTokenNotFound = errors.New("password reset token not found")

// PasswordResetToken is a single-use reset credential. TokenHash holds the
// SHA-256 hex of the raw token that was emailed to the user.
type PasswordResetToken struct {
	ID        int64
	UserID    int
	TokenHash string
	ExpiresAt time.Time
	UsedAt    sql.NullTime
	CreatedAt time.Time
}

type PasswordResetTokenRepository struct {
	db SQLRunner
}

func NewPasswordResetTokenRepository(db *sql.DB) *PasswordResetTokenRepository {
	return &PasswordResetTokenRepository{db: db}
}

// Create stores a new hashed token, invalidating any previous unused tokens
// for the user (only the newest emailed link works).
func (r *PasswordResetTokenRepository) Create(ctx context.Context, userID int, tokenHash string, expiresAt time.Time, createdIP string) error {
	now := time.Now().UTC()
	if _, err := r.db.ExecContext(ctx,
		`UPDATE password_reset_tokens SET used_at = $1 WHERE user_id = $2 AND used_at IS NULL`, now, userID); err != nil {
		return err
	}
	_, err := r.db.ExecContext(ctx,
		`INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, created_ip, created_at)
		 VALUES ($1, $2, $3, $4, $5)`,
		userID, tokenHash, expiresAt, createdIP, now)
	return err
}

// Consume marks the token used and returns it, but only when it is unused and
// unexpired — the atomic guard against replay.
func (r *PasswordResetTokenRepository) Consume(ctx context.Context, tokenHash string) (*PasswordResetToken, error) {
	row := r.db.QueryRowContext(ctx, `
		UPDATE password_reset_tokens SET used_at = $2
		WHERE token_hash = $1 AND used_at IS NULL AND expires_at > $2
		RETURNING id, user_id, token_hash, expires_at, used_at, created_at`,
		tokenHash, time.Now().UTC())
	var t PasswordResetToken
	if err := row.Scan(&t.ID, &t.UserID, &t.TokenHash, &t.ExpiresAt, &t.UsedAt, &t.CreatedAt); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrPasswordResetTokenNotFound
		}
		return nil, err
	}
	return &t, nil
}

// RecentCreatedWithin reports whether the user received an unused token in the
// window — used as a send-cooldown so the endpoint cannot be used to flood a
// mailbox.
func (r *PasswordResetTokenRepository) RecentCreatedWithin(ctx context.Context, userID int, window time.Duration) (bool, error) {
	var count int
	err := r.db.QueryRowContext(ctx,
		`SELECT COUNT(*) FROM password_reset_tokens
		 WHERE user_id = $1 AND used_at IS NULL AND created_at > $2`,
		userID, time.Now().UTC().Add(-window)).Scan(&count)
	return count > 0, err
}

// DeleteExpired prunes consumed/expired rows (call opportunistically).
func (r *PasswordResetTokenRepository) DeleteExpired(ctx context.Context) error {
	_, err := r.db.ExecContext(ctx,
		`DELETE FROM password_reset_tokens WHERE expires_at < $1`, time.Now().UTC().AddDate(0, 0, -7))
	return err
}
