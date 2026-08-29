package services

import (
	"database/sql"
	"encoding/json"
	"strings"
	"testing"
	"time"

	"github.com/pquerna/otp"
	"github.com/pquerna/otp/totp"

	"github.com/dydx-trading-bot/backend-go/internal/repository"
	_ "modernc.org/sqlite"
)

func newMFAVerifyService(t *testing.T) (*MFAService, *sql.DB) {
	t.Helper()
	t.Setenv("SECRET_KEY", "mfa-verify-test-secret-32-chars-ok!")
	t.Setenv("ENCRYPTION_KEY", "mfa-verify-test-secret-32-chars-ok!")

	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	t.Cleanup(func() { _ = dbConn.Close() })
	if _, err := dbConn.Exec(`
	CREATE TABLE user_mfa_credentials (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER NOT NULL UNIQUE,
		encrypted_secret TEXT NOT NULL,
		encrypted_backup_codes TEXT NOT NULL DEFAULT '',
		enabled BOOLEAN NOT NULL DEFAULT 0,
		verified_at TIMESTAMP NULL,
		last_used_at TIMESTAMP NULL,
		created_at TIMESTAMP NOT NULL,
		updated_at TIMESTAMP NOT NULL
	);`); err != nil {
		t.Fatalf("create table: %v", err)
	}

	svc := NewMFAService(repository.NewUserMFARepository(dbConn))
	// The service captured ENCRYPTION_KEY at construction; assert it is
	// usable for the encrypt/decrypt round trip the test relies on.
	if svc.secret == "" {
		t.Fatal("expected non-empty encryption secret")
	}
	return svc, dbConn
}

func seedMFACredential(t *testing.T, svc *MFAService, db *sql.DB, secret string, backupCodes []string, lastUsedAt *time.Time) {
	t.Helper()
	payload, err := json.Marshal(backupCodes)
	if err != nil {
		t.Fatalf("marshal backup codes: %v", err)
	}
	encSecret, err := encryptString(svc.secret, secret)
	if err != nil {
		t.Fatalf("encrypt secret: %v", err)
	}
	encBackup, err := encryptString(svc.secret, string(payload))
	if err != nil {
		t.Fatalf("encrypt backup codes: %v", err)
	}
	now := time.Now().UTC()
	var lastUsed interface{}
	if lastUsedAt != nil {
		lastUsed = lastUsedAt.UTC()
	}
	if _, err := db.Exec(
		`INSERT INTO user_mfa_credentials (user_id, encrypted_secret, encrypted_backup_codes, enabled, verified_at, last_used_at, created_at, updated_at)
		 VALUES (42, ?, ?, 1, ?, ?, ?, ?)`,
		encSecret, encBackup, now, lastUsed, now, now,
	); err != nil {
		t.Fatalf("seed credential: %v", err)
	}
}

func codeForWindow(t *testing.T, secret string, window int64) string {
	t.Helper()
	code, err := totp.GenerateCodeCustom(secret, time.Unix(window*30, 0).UTC(), totp.ValidateOpts{
		Period:    30,
		Skew:      2,
		Digits:    otp.DigitsSix,
		Algorithm: otp.AlgorithmSHA1,
	})
	if err != nil {
		t.Fatalf("generate code: %v", err)
	}
	return code
}

func TestMFAVerify_AcceptsFreshTOTPCode(t *testing.T) {
	svc, db := newMFAVerifyService(t)
	secret := "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
	seedMFACredential(t, svc, db, secret, nil, nil)

	current := time.Now().UTC().Unix() / 30
	if err := svc.Verify(42, codeForWindow(t, secret, current)); err != nil {
		t.Fatalf("fresh code must verify: %v", err)
	}
}

func TestMFAVerify_RejectsReplayedTOTPCode(t *testing.T) {
	svc, db := newMFAVerifyService(t)
	secret := "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
	seedMFACredential(t, svc, db, secret, nil, nil)

	current := time.Now().UTC().Unix() / 30
	code := codeForWindow(t, secret, current)
	if err := svc.Verify(42, code); err != nil {
		t.Fatalf("first use must verify: %v", err)
	}
	if err := svc.Verify(42, code); err == nil {
		t.Fatal("replayed code must be rejected")
	}
}

func TestMFAVerify_RejectsOlderInSkewWindowAfterUse(t *testing.T) {
	svc, db := newMFAVerifyService(t)
	secret := "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
	seedMFACredential(t, svc, db, secret, nil, nil)

	current := time.Now().UTC().Unix() / 30
	if err := svc.Verify(42, codeForWindow(t, secret, current)); err != nil {
		t.Fatalf("current-window code must verify: %v", err)
	}
	// A code from one window back is still within the ±2 skew for a fresh
	// verification, but must be rejected after a newer window was consumed.
	if err := svc.Verify(42, codeForWindow(t, secret, current-1)); err == nil {
		t.Fatal("older in-skew code must be rejected after use")
	}
}

func TestMFAVerify_BackupCodeSingleUse(t *testing.T) {
	svc, db := newMFAVerifyService(t)
	secret := "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
	seedMFACredential(t, svc, db, secret, []string{"ABCDE-WXY23", "ZZZZZ-99999"}, nil)

	if err := svc.Verify(42, "ABCDE-WXY23"); err != nil {
		t.Fatalf("backup code must verify: %v", err)
	}
	if err := svc.Verify(42, "ABCDE-WXY23"); err == nil {
		t.Fatal("backup code must be single-use")
	}
	// The other code still works.
	if err := svc.Verify(42, "ZZZZZ-99999"); err != nil {
		t.Fatalf("remaining backup code must verify: %v", err)
	}
}

func TestMFAVerify_RejectsWrongCode(t *testing.T) {
	svc, db := newMFAVerifyService(t)
	secret := "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
	seedMFACredential(t, svc, db, secret, []string{"ABCDE-WXY23"}, nil)

	err := svc.Verify(42, "000000")
	if err == nil || !strings.Contains(err.Error(), "invalid authenticator code") {
		t.Fatalf("expected invalid-code error, got %v", err)
	}
}
