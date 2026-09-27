package repository

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// strategyChatSchemaConn returns one connection pinned to a throwaway schema
// holding the tables of migration 000075, applied twice to prove it is
// idempotent.
func strategyChatSchemaConn(t *testing.T) *sql.DB {
	t.Helper()
	admin := openPostgresTestDB(t)

	schema := fmt.Sprintf("strategy_chat_test_%d", time.Now().UnixNano())
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
	for i := 0; i < 2; i++ {
		applyStrategyChatMigration(t, db, "up")
	}
	return db
}

func applyStrategyChatMigration(t *testing.T, db *sql.DB, direction string) {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("..", "..", "migrations", "postgres", "000075_create_strategy_chat."+direction+".sql"))
	if err != nil {
		t.Fatalf("read migration: %v", err)
	}
	if _, err := db.ExecContext(context.Background(), string(raw)); err != nil {
		t.Fatalf("apply 000075 %s: %v", direction, err)
	}
}

func TestStrategyChatRepositoryOnPostgres(t *testing.T) {
	db := strategyChatSchemaConn(t)
	repo := NewStrategyChatRepository(db)

	proposal := `{"kind":"update","title":"Fewer entries","summary":"s","suggested_name":"","changes":[{"field":"zscore_threshold","current":1.5,"proposed":2}],"dropped":[]}`
	session := &models.StrategyChatSession{UserID: 1, StrategyID: 2, Title: "First question"}
	user := &models.StrategyChatMessage{Role: models.StrategyChatRoleUser, Content: "question", Provider: "grok"}
	assistant := &models.StrategyChatMessage{
		Role: models.StrategyChatRoleAssistant, Content: "answer", Provider: "grok", Model: "grok-4.3",
		InputTokens: 900, OutputTokens: 120,
		Proposal:       sql.NullString{String: proposal, Valid: true},
		ProposalStatus: sql.NullString{String: models.StrategyChatProposalPending, Valid: true},
	}
	if err := repo.AppendTurn(session, user, assistant); err != nil {
		t.Fatalf("AppendTurn: %v", err)
	}
	if session.ID == 0 || user.ID == 0 || assistant.ID <= user.ID || assistant.SessionID != session.ID {
		t.Fatalf("expected ids assigned, got session=%d user=%d assistant=%d", session.ID, user.ID, assistant.ID)
	}

	stored, err := repo.GetMessage(assistant.ID)
	if err != nil || stored == nil {
		t.Fatalf("GetMessage: %v", err)
	}
	var want, got any
	_ = json.Unmarshal([]byte(proposal), &want)
	if err := json.Unmarshal([]byte(stored.Proposal.String), &got); err != nil || !reflect.DeepEqual(want, got) {
		t.Fatalf("expected the JSONB proposal to round-trip, got %q (%v)", stored.Proposal.String, err)
	}
	if stored.ProposalResult.Valid || stored.InputTokens != 900 {
		t.Fatalf("unexpected stored message %+v", stored)
	}

	changed, err := repo.TransitionProposal(assistant.ID, models.StrategyChatProposalPending, models.StrategyChatProposalApplied,
		sql.NullString{String: `{"applied_fields":["zscore_threshold"],"at":"2026-09-26T00:00:00Z"}`, Valid: true})
	if err != nil || !changed {
		t.Fatalf("expected the first transition to win, got %v %v", changed, err)
	}
	changed, err = repo.TransitionProposal(assistant.ID, models.StrategyChatProposalPending, models.StrategyChatProposalDismissed, sql.NullString{})
	if err != nil || changed {
		t.Fatalf("expected a second transition from pending to lose, got %v %v", changed, err)
	}

	next := &models.StrategyChatSession{ID: session.ID, UserID: 1, StrategyID: 2, Title: "ignored"}
	if err := repo.AppendTurn(next,
		&models.StrategyChatMessage{Role: models.StrategyChatRoleUser, Content: "q2"},
		&models.StrategyChatMessage{Role: models.StrategyChatRoleAssistant, Content: "a2"},
	); err != nil {
		t.Fatalf("second AppendTurn: %v", err)
	}
	messages, err := repo.ListRecentMessages(session.ID, 3)
	if err != nil || len(messages) != 3 || messages[0].Content != "answer" || messages[2].Content != "a2" {
		t.Fatalf("expected the three newest messages oldest first, got %+v %v", messages, err)
	}
	reloaded, _ := repo.GetSession(session.ID)
	if reloaded.Title != "First question" {
		t.Fatalf("expected an existing title kept, got %q", reloaded.Title)
	}

	fresh, err := repo.StartSession(1, 2)
	if err != nil {
		t.Fatalf("StartSession: %v", err)
	}
	active, err := repo.GetActiveSession(1, 2)
	if err != nil || active == nil || active.ID != fresh.ID {
		t.Fatalf("expected the new session to be active, got %+v %v", active, err)
	}
	archived, _ := repo.GetSession(session.ID)
	if archived.ArchivedAt == nil {
		t.Fatal("expected the previous session archived")
	}

	if _, err := db.Exec(`INSERT INTO strategy_chat_messages (session_id, role, content) VALUES ($1, 'system', 'x')`, session.ID); err == nil {
		t.Fatal("expected the role CHECK constraint to refuse 'system'")
	}
	if _, err := db.Exec(`UPDATE strategy_chat_messages SET proposal_status = 'maybe' WHERE id = $1`, assistant.ID); err == nil {
		t.Fatal("expected the proposal_status CHECK constraint to refuse 'maybe'")
	}

	applyStrategyChatMigration(t, db, "down")
	var remaining int
	if err := db.QueryRow(`SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = current_schema() AND table_name LIKE 'strategy_chat_%'`).Scan(&remaining); err != nil || remaining != 0 {
		t.Fatalf("expected the down migration to drop both tables, got %d (%v)", remaining, err)
	}
}
