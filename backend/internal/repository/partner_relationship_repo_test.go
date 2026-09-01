package repository

import (
	"database/sql"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	_ "modernc.org/sqlite"
)

func setupPartnerRelationshipTestDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
	}
	t.Cleanup(func() { _ = db.Close() })

	// Mirrors migrations/postgres/000035: partner_user_id is the UNIQUE key.
	schema := `
		CREATE TABLE partner_relationships (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			sponsor_user_id INTEGER NOT NULL,
			partner_user_id INTEGER NOT NULL UNIQUE,
			relationship_type TEXT NOT NULL,
			source_application_id INTEGER,
			is_active BOOLEAN NOT NULL DEFAULT 1,
			created_at TIMESTAMP NOT NULL,
			updated_at TIMESTAMP NOT NULL
		);
	`
	if _, err := db.Exec(schema); err != nil {
		t.Fatalf("create partner_relationships schema: %v", err)
	}
	return db
}

// Regression test: Upsert previously targeted ON CONFLICT (sponsor_user_id,
// partner_user_id), for which no unique index exists — the statement failed on
// every partner application approval.
func TestPartnerRelationshipUpsert_InsertsThenUpdates(t *testing.T) {
	db := setupPartnerRelationshipTestDB(t)
	repo := NewPartnerRelationshipRepository(db)

	rel := &models.PartnerRelationship{
		SponsorUserID:   1,
		PartnerUserID:   2,
		RelationshipType: "ib",
		IsActive:        true,
	}
	if err := repo.Upsert(rel); err != nil {
		t.Fatalf("Upsert (insert): %v", err)
	}
	if rel.ID == 0 {
		t.Fatal("expected relationship id to be set after insert")
	}

	rel.RelationshipType = "sub_ib"
	rel.IsActive = false
	if err := repo.Upsert(rel); err != nil {
		t.Fatalf("Upsert (update): %v", err)
	}

	var count int
	if err := db.QueryRow(`SELECT COUNT(*) FROM partner_relationships`).Scan(&count); err != nil {
		t.Fatalf("count relationships: %v", err)
	}
	if count != 1 {
		t.Fatalf("expected upsert to keep a single row, got %d", count)
	}
	stored, err := repo.GetByPartner(2)
	if err != nil || stored == nil {
		t.Fatalf("GetByPartner: %v, %v", stored, err)
	}
	if stored.RelationshipType != "sub_ib" || stored.IsActive {
		t.Fatalf("expected updated fields persisted, got type=%s active=%v", stored.RelationshipType, stored.IsActive)
	}
}

// Regression test: List previously referenced $2/$3 while binding only two
// arguments, failing on every call.
func TestPartnerRelationshipList_ReturnsRows(t *testing.T) {
	db := setupPartnerRelationshipTestDB(t)
	repo := NewPartnerRelationshipRepository(db)

	now := time.Now().UTC()
	for _, pair := range [][2]int{{1, 2}, {1, 3}, {1, 4}} {
		if _, err := db.Exec(
			`INSERT INTO partner_relationships (sponsor_user_id, partner_user_id, relationship_type, is_active, created_at, updated_at) VALUES (?, ?, 'ib', 1, ?, ?)`,
			pair[0], pair[1], now, now,
		); err != nil {
			t.Fatalf("seed relationship: %v", err)
		}
	}

	rows, err := repo.List(2, 0)
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(rows) != 2 {
		t.Fatalf("expected 2 rows with limit=2, got %d", len(rows))
	}

	all, err := repo.List(10, 0)
	if err != nil {
		t.Fatalf("List (all): %v", err)
	}
	if len(all) != 3 {
		t.Fatalf("expected 3 rows total, got %d", len(all))
	}
}
