package repository

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

const sharedCredentialMigration = "000074_allow_shared_external_api_credentials.up.sql"

// credentialSchemaConn returns one connection pinned to a throwaway schema
// holding users + external_api_credentials exactly as migrations 000027,
// 000071 and 000052 leave them: a plain foreign key from user_id to users(id).
func credentialSchemaConn(t *testing.T) *sql.DB {
	t.Helper()
	admin := openPostgresTestDB(t)

	schema := fmt.Sprintf("cred_fk_test_%d", time.Now().UnixNano())
	if _, err := admin.Exec(`CREATE SCHEMA ` + schema); err != nil {
		t.Fatalf("create schema: %v", err)
	}
	t.Cleanup(func() { _, _ = admin.Exec(`DROP SCHEMA IF EXISTS ` + schema + ` CASCADE`) })

	dsn := stringsFirstNonEmpty(os.Getenv("POSTGRES_TEST_DSN"), os.Getenv("TEST_DATABASE_URL"))
	db, err := sql.Open("pgx", dsn)
	if err != nil {
		t.Fatalf("open postgres: %v", err)
	}
	db.SetMaxOpenConns(1)
	t.Cleanup(func() { _ = db.Close() })
	if _, err := db.Exec(`SET search_path TO ` + schema); err != nil {
		t.Fatalf("set search_path: %v", err)
	}

	for _, ddl := range []string{
		`CREATE TABLE users (
			id SERIAL PRIMARY KEY,
			username TEXT NOT NULL UNIQUE,
			email TEXT NOT NULL UNIQUE,
			hashed_password TEXT NOT NULL DEFAULT ''
		)`,
		`CREATE TABLE external_api_credentials (
			id SERIAL PRIMARY KEY,
			user_id INTEGER NOT NULL,
			provider TEXT NOT NULL,
			label TEXT NOT NULL DEFAULT '',
			encrypted_api_key TEXT NOT NULL,
			api_key_hash TEXT NOT NULL DEFAULT '',
			api_key_salt TEXT NOT NULL DEFAULT '',
			api_key_masked TEXT NOT NULL DEFAULT '',
			is_active BOOLEAN NOT NULL DEFAULT TRUE,
			created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
			updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
			CONSTRAINT uq_external_api_credentials_user_provider UNIQUE (user_id, provider)
		)`,
		`ALTER TABLE external_api_credentials
			ADD CONSTRAINT fk_external_api_credentials_user_id
			FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE RESTRICT`,
	} {
		if _, err := db.Exec(ddl); err != nil {
			t.Fatalf("fixture ddl: %v", err)
		}
	}
	return db
}

func applySharedCredentialMigration(t *testing.T, db *sql.DB) {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("..", "..", "migrations", "postgres", sharedCredentialMigration))
	if err != nil {
		t.Fatalf("read migration: %v", err)
	}
	if _, err := db.ExecContext(context.Background(), string(raw)); err != nil {
		t.Fatalf("apply %s: %v", sharedCredentialMigration, err)
	}
}

func sharedCredential(provider string) *models.ExternalAPICredential {
	return &models.ExternalAPICredential{
		UserID:          0,
		Provider:        provider,
		Label:           "shared",
		EncryptedAPIKey: "ciphertext",
		APIKeyMasked:    "sk_****",
		IsActive:        true,
	}
}

// Shared credentials use user_id = 0. With only the 000052 foreign key in
// place the insert is rejected; sqlite-backed tests never saw this.
func TestExternalAPICredential_SharedOwnerRejectedBeforeMigration(t *testing.T) {
	db := credentialSchemaConn(t)

	err := NewExternalAPICredentialRepository(db).Upsert(sharedCredential("plunk"))
	if err == nil || !strings.Contains(err.Error(), "fk_external_api_credentials_user_id") {
		t.Fatalf("expected the plain foreign key to reject user_id = 0, got %v", err)
	}
}

func TestExternalAPICredential_SharedOwnerAllowedAfterMigration(t *testing.T) {
	db := credentialSchemaConn(t)
	applySharedCredentialMigration(t, db)
	repo := NewExternalAPICredentialRepository(db)

	if err := repo.Upsert(sharedCredential("plunk")); err != nil {
		t.Fatalf("shared credential insert: %v", err)
	}
	rotated := sharedCredential("plunk")
	rotated.EncryptedAPIKey = "ciphertext-2"
	if err := repo.Upsert(rotated); err != nil {
		t.Fatalf("shared credential rotate: %v", err)
	}
	stored, err := repo.GetByUserAndProvider(0, "plunk")
	if err != nil || stored == nil {
		t.Fatalf("load shared credential: %v (%v)", stored, err)
	}
	if stored.EncryptedAPIKey != "ciphertext-2" {
		t.Fatalf("rotation did not replace the key: %q", stored.EncryptedAPIKey)
	}
}

func TestExternalAPICredential_UserOwnedRowsKeepIntegrityAfterMigration(t *testing.T) {
	db := credentialSchemaConn(t)
	applySharedCredentialMigration(t, db)
	repo := NewExternalAPICredentialRepository(db)

	orphan := sharedCredential("openai")
	orphan.UserID = 987654
	if err := repo.Upsert(orphan); err == nil {
		t.Fatal("a credential for a user that does not exist must be rejected")
	}

	negative := sharedCredential("openai")
	negative.UserID = -1
	if err := repo.Upsert(negative); err == nil {
		t.Fatal("a negative owner id must be rejected")
	}

	var userID int
	if err := db.QueryRow(`INSERT INTO users (username, email) VALUES ('owner', 'owner@example.com') RETURNING id`).Scan(&userID); err != nil {
		t.Fatalf("seed user: %v", err)
	}
	owned := sharedCredential("openai")
	owned.UserID = userID
	if err := repo.Upsert(owned); err != nil {
		t.Fatalf("user-owned credential insert: %v", err)
	}
	if _, err := db.Exec(`DELETE FROM users WHERE id = $1`, userID); err == nil {
		t.Fatal("deleting a user who still owns credentials must be restricted")
	}
}

func TestExternalAPICredential_MigrationIsIdempotent(t *testing.T) {
	db := credentialSchemaConn(t)
	applySharedCredentialMigration(t, db)
	applySharedCredentialMigration(t, db)
}
