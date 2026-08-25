package repository

import (
	"database/sql"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

func setupInvitationTokenTestDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
	}
	t.Cleanup(func() { _ = db.Close() })

	schema := `
		CREATE TABLE invitation_tokens (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			token_code TEXT NOT NULL UNIQUE,
			label TEXT NOT NULL DEFAULT '',
			ib_name TEXT NOT NULL DEFAULT '',
			campaign_name TEXT NOT NULL DEFAULT '',
			max_uses INTEGER NOT NULL DEFAULT 1,
			used_count INTEGER NOT NULL DEFAULT 0,
			created_by_user_id INTEGER,
			last_used_by_user_id INTEGER,
			expires_at TIMESTAMP,
			last_used_at TIMESTAMP,
			revoked_at TIMESTAMP,
			created_at TIMESTAMP NOT NULL,
			updated_at TIMESTAMP NOT NULL
		);
	`
	if _, err := db.Exec(schema); err != nil {
		t.Fatalf("create invitation_tokens schema: %v", err)
	}
	return db
}

func newSqliteInvitationTokenRepo(t *testing.T, db *sql.DB) *InvitationTokenRepository {
	t.Helper()
	t.Setenv("DB_TYPE", "sqlite")
	return NewInvitationTokenRepository(db)
}

func seedInvitationToken(t *testing.T, db *sql.DB, tokenCode string, maxUses, usedCount int, expiresAt *time.Time, revokedAt *time.Time) {
	t.Helper()
	now := time.Now().UTC()
	var expires, revoked interface{}
	if expiresAt != nil {
		expires = *expiresAt
	}
	if revokedAt != nil {
		revoked = *revokedAt
	}
	_, err := db.Exec(
		`INSERT INTO invitation_tokens (token_code, max_uses, used_count, expires_at, revoked_at, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?)`,
		tokenCode, maxUses, usedCount, expires, revoked, now, now,
	)
	if err != nil {
		t.Fatalf("seed invitation token %q: %v", tokenCode, err)
	}
}

// Regression test: Redeem previously passed 3 args to a 5-placeholder query,
// which fails on every driver ("expected 5 arguments, got 3") and broke
// invitation-only registration end to end.
func TestInvitationTokenRedeem_IncrementsUsage(t *testing.T) {
	db := setupInvitationTokenTestDB(t)
	repo := newSqliteInvitationTokenRepo(t, db)

	expires := time.Now().UTC().Add(24 * time.Hour)
	seedInvitationToken(t, db, "VALIDCODE", 2, 0, &expires, nil)

	ok, err := repo.Redeem("VALIDCODE", 42)
	if err != nil {
		t.Fatalf("Redeem returned error: %v", err)
	}
	if !ok {
		t.Fatalf("expected successful redemption of valid token")
	}

	var usedCount int
	var lastUsedBy int
	if err := db.QueryRow(`SELECT used_count, last_used_by_user_id FROM invitation_tokens WHERE token_code = ?`, "VALIDCODE").
		Scan(&usedCount, &lastUsedBy); err != nil {
		t.Fatalf("read back token state: %v", err)
	}
	if usedCount != 1 {
		t.Fatalf("expected used_count=1 after redeem, got %d", usedCount)
	}
	if lastUsedBy != 42 {
		t.Fatalf("expected last_used_by_user_id=42, got %d", lastUsedBy)
	}
}

func TestInvitationTokenRedeem_RejectsExhaustedToken(t *testing.T) {
	db := setupInvitationTokenTestDB(t)
	repo := newSqliteInvitationTokenRepo(t, db)

	expires := time.Now().UTC().Add(24 * time.Hour)
	seedInvitationToken(t, db, "EXHAUSTED", 1, 1, &expires, nil)

	ok, err := repo.Redeem("EXHAUSTED", 42)
	if err != nil {
		t.Fatalf("Redeem returned error: %v", err)
	}
	if ok {
		t.Fatalf("expected redemption to be rejected for exhausted token")
	}
}

func TestInvitationTokenRedeem_RejectsExpiredToken(t *testing.T) {
	db := setupInvitationTokenTestDB(t)
	repo := newSqliteInvitationTokenRepo(t, db)

	expired := time.Now().UTC().Add(-1 * time.Hour)
	seedInvitationToken(t, db, "EXPIRED", 5, 0, &expired, nil)

	ok, err := repo.Redeem("EXPIRED", 42)
	if err != nil {
		t.Fatalf("Redeem returned error: %v", err)
	}
	if ok {
		t.Fatalf("expected redemption to be rejected for expired token")
	}
}

// Regression test: RevokeByTokenCode previously passed 2 args to a
// 3-placeholder query, so revocation always failed at runtime.
func TestInvitationTokenRevokeByTokenCode(t *testing.T) {
	db := setupInvitationTokenTestDB(t)
	repo := newSqliteInvitationTokenRepo(t, db)

	expires := time.Now().UTC().Add(24 * time.Hour)
	seedInvitationToken(t, db, "REVOKEME", 5, 0, &expires, nil)

	if err := repo.RevokeByTokenCode("REVOKEME"); err != nil {
		t.Fatalf("RevokeByTokenCode returned error: %v", err)
	}

	var revokedCount int
	if err := db.QueryRow(`SELECT COUNT(*) FROM invitation_tokens WHERE token_code = ? AND revoked_at IS NOT NULL`, "REVOKEME").
		Scan(&revokedCount); err != nil {
		t.Fatalf("read back revoked state: %v", err)
	}
	if revokedCount != 1 {
		t.Fatalf("expected token to be revoked")
	}

	// Revoking an already-revoked token must report not found/already revoked.
	if err := repo.RevokeByTokenCode("REVOKEME"); err == nil {
		t.Fatalf("expected error when revoking an already-revoked token")
	}
}
