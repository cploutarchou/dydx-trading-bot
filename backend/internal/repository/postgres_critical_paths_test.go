package repository

import (
	"database/sql"
	"fmt"
	"os"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	_ "github.com/jackc/pgx/v5/stdlib"
)

// openPostgresTestDB connects to a real PostgreSQL instance for critical-path
// SQL tests — the class of bugs (placeholder dialect, argument-count drift)
// that sqlmock and sqlite both hide. Set POSTGRES_TEST_DSN to enable; tests
// skip otherwise so local/CI runs without a database stay green.
//
//	POSTGRES_TEST_DSN="postgres://user:pass@127.0.0.1:5432/db?sslmode=disable" go test ./internal/repository/
func openPostgresTestDB(t *testing.T) *sql.DB {
	t.Helper()
	dsn := stringsFirstNonEmpty(
		os.Getenv("POSTGRES_TEST_DSN"),
		os.Getenv("TEST_DATABASE_URL"),
	)
	if dsn == "" {
		t.Skip("POSTGRES_TEST_DSN not set; skipping PostgreSQL integration test")
	}

	db, err := sql.Open("pgx", dsn)
	if err != nil {
		t.Fatalf("open postgres: %v", err)
	}
	t.Cleanup(func() { _ = db.Close() })
	if err := db.Ping(); err != nil {
		t.Fatalf("ping postgres: %v", err)
	}
	return db
}

func stringsFirstNonEmpty(values ...string) string {
	for _, v := range values {
		if v != "" {
			return v
		}
	}
	return ""
}

func setupPostgresFixture(t *testing.T, db *sql.DB) {
	t.Helper()
	for _, ddl := range []string{
		`CREATE TABLE IF NOT EXISTS invitation_tokens (
			id BIGSERIAL PRIMARY KEY,
			token_code TEXT NOT NULL UNIQUE,
			label TEXT NOT NULL DEFAULT '',
			ib_name TEXT NOT NULL DEFAULT '',
			campaign_name TEXT NOT NULL DEFAULT '',
			max_uses INTEGER NOT NULL DEFAULT 1,
			used_count INTEGER NOT NULL DEFAULT 0,
			created_by_user_id BIGINT,
			last_used_by_user_id BIGINT,
			expires_at TIMESTAMPTZ,
			last_used_at TIMESTAMPTZ,
			revoked_at TIMESTAMPTZ,
			created_at TIMESTAMPTZ NOT NULL,
			updated_at TIMESTAMPTZ NOT NULL
		)`,
		`CREATE TABLE IF NOT EXISTS partner_relationships (
			id BIGSERIAL PRIMARY KEY,
			sponsor_user_id BIGINT NOT NULL,
			partner_user_id BIGINT NOT NULL UNIQUE,
			relationship_type TEXT NOT NULL,
			source_application_id BIGINT,
			is_active BOOLEAN NOT NULL DEFAULT TRUE,
			created_at TIMESTAMPTZ NOT NULL,
			updated_at TIMESTAMPTZ NOT NULL
		)`,
		`CREATE TABLE IF NOT EXISTS backtest_runs (
			id BIGSERIAL PRIMARY KEY,
			user_id BIGINT NOT NULL,
			run_id TEXT,
			created_at TIMESTAMPTZ NOT NULL DEFAULT now()
		)`,
		`CREATE TABLE IF NOT EXISTS backtest_results (
			id BIGSERIAL PRIMARY KEY,
			run_id_fk BIGINT NOT NULL,
			market_1 TEXT NOT NULL DEFAULT '',
			market_2 TEXT NOT NULL DEFAULT '',
			created_at TIMESTAMPTZ DEFAULT now()
		)`,
		`CREATE TABLE IF NOT EXISTS trade_logs (
			id SERIAL PRIMARY KEY,
			result_id_fk INTEGER NOT NULL,
			trade_number INTEGER NOT NULL,
			entry_timestamp TIMESTAMP NOT NULL,
			exit_timestamp TIMESTAMP,
			entry_price_1 REAL NOT NULL,
			entry_price_2 REAL NOT NULL,
			exit_price_1 REAL,
			exit_price_2 REAL,
			quantity_1 REAL NOT NULL,
			quantity_2 REAL NOT NULL,
			side_1 VARCHAR(10) NOT NULL,
			side_2 VARCHAR(10) NOT NULL,
			pnl REAL,
			pnl_usd REAL,
			entry_zscore REAL,
			exit_zscore REAL,
			created_at TIMESTAMP
		)`,
	} {
		if _, err := db.Exec(ddl); err != nil {
			t.Fatalf("fixture ddl: %v", err)
		}
	}
}

// seedPostgresUser inserts a minimal users row (satisfying FK targets on
// fully-migrated schemas) and returns its id.
func seedPostgresUser(t *testing.T, db *sql.DB, username string) int {
	t.Helper()
	var id int
	// Unique suffix: FK-blocked cleanups from earlier runs may leave rows.
	unique := fmt.Sprintf("%s_%d", username, time.Now().UnixNano())
	err := db.QueryRow(`
		INSERT INTO users (username, email, role, hashed_password, is_active, is_admin, created_at, updated_at)
		VALUES ($1, $2, 'client', 'x', TRUE, FALSE, now(), now())
		RETURNING id`, unique, unique+"@pgtest.local").Scan(&id)
	if err != nil {
		t.Fatalf("seed user %s: %v", username, err)
	}
	t.Cleanup(func() {
		_, _ = db.Exec(`DELETE FROM users WHERE id = $1`, id)
	})
	return id
}

// TestPostgres_InvitationRedeemRevoke guards the placeholder/argument parity
// of the invitation repository (regression: Redeem shipped with 5 placeholders
// and 3 arguments, which sqlmock-based tests never caught).
func TestPostgres_InvitationRedeemRevoke(t *testing.T) {
	db := openPostgresTestDB(t)
	setupPostgresFixture(t, db)

	code := "pgtest-invite-" + time.Now().Format("150405.000000000")
	now := time.Now().UTC()
	if _, err := db.Exec(
		`INSERT INTO invitation_tokens (token_code, max_uses, used_count, expires_at, created_at, updated_at)
		 VALUES ($1, 2, 0, $2, $3, $4)`, code, now.Add(time.Hour), now, now,
	); err != nil {
		t.Fatalf("seed token: %v", err)
	}
	t.Cleanup(func() {
		_, _ = db.Exec(`DELETE FROM invitation_tokens WHERE token_code = $1`, code)
	})

	repo := NewInvitationTokenRepository(db)
	ok, err := repo.Redeem(code, seedPostgresUser(t, db, "pgtest_invite_user"))
	if err != nil {
		t.Fatalf("Redeem on PostgreSQL: %v", err)
	}
	if !ok {
		t.Fatal("expected successful redemption")
	}
	if err := repo.RevokeByTokenCode(code); err != nil {
		t.Fatalf("RevokeByTokenCode on PostgreSQL: %v", err)
	}
}

// TestPostgres_PartnerRelationshipUpsertList guards the ON CONFLICT target and
// pagination placeholders (regression: unindexed conflict target and $2/$3
// with two arguments both failed only on PostgreSQL).
func TestPostgres_PartnerRelationshipUpsertList(t *testing.T) {
	db := openPostgresTestDB(t)
	setupPostgresFixture(t, db)

	repo := NewPartnerRelationshipRepository(db)
	rel := &testPartnerRelationship{
		sponsor: seedPostgresUser(t, db, "pgtest_sponsor"),
		partner: seedPostgresUser(t, db, "pgtest_partner"),
		relType: "ib",
	}
	t.Cleanup(func() {
		_, _ = db.Exec(`DELETE FROM partner_relationships WHERE partner_user_id = $1`, rel.partner)
	})

	if err := repo.Upsert(rel.model()); err != nil {
		t.Fatalf("Upsert on PostgreSQL: %v", err)
	}
	rows, err := repo.List(10, 0)
	if err != nil {
		t.Fatalf("List on PostgreSQL: %v", err)
	}
	if len(rows) < 1 {
		t.Fatal("expected upserted relationship in listing")
	}
}

// TestPostgres_UpdateTradeLog guards the placeholder syntax of the trade-log
// update (regression: `?0..?5` suffixes compiled into non-existent $100+
// parameters).
func TestPostgres_UpdateTradeLog(t *testing.T) {
	db := openPostgresTestDB(t)
	setupPostgresFixture(t, db)

	// Seed the ownership chain the scoped read joins through.
	var runPK int
	if err := db.QueryRow(`
		INSERT INTO backtest_runs (user_id, run_id, status, start_date, end_date, num_pairs, total_markets, created_at)
		VALUES ($1, $2, 'completed', '2026-01-01', '2026-01-31', 1, 1, now()) RETURNING id`,
		seedPostgresUser(t, db, "pgtest_run_owner"), fmt.Sprintf("pg%d", time.Now().UnixNano()%100000000)).Scan(&runPK); err != nil {
		t.Fatalf("seed backtest run: %v", err)
	}
	t.Cleanup(func() {
		_, _ = db.Exec(`DELETE FROM trade_logs WHERE result_id_fk = $1`, 900100)
		_, _ = db.Exec(`DELETE FROM backtest_results WHERE id = $1`, 900100)
		_, _ = db.Exec(`DELETE FROM backtest_runs WHERE id = $1`, runPK)
	})
	if _, err := db.Exec(
		`INSERT INTO backtest_results (id, run_id_fk, market_1, market_2) VALUES (900100, $1, 'BTC-USD', 'ETH-USD')`, runPK); err != nil {
		t.Fatalf("seed backtest result: %v", err)
	}

	repo := NewTradeLogRepository(db)
	now := time.Now().UTC()
	tradeNumber := 1
	entryPrice := 100.5
	created := newTestTradeLog(900100, tradeNumber, entryPrice, &now)
	if err := repo.CreateTradeLog(created); err != nil {
		t.Fatalf("CreateTradeLog on PostgreSQL: %v", err)
	}

	pnl := 12.5
	created.Pnl = &pnl
	if err := repo.UpdateTradeLog(created); err != nil {
		t.Fatalf("UpdateTradeLog on PostgreSQL: %v", err)
	}
	got, err := repo.GetTradeLogByID(created.ID, 0)
	if err != nil || got == nil {
		t.Fatalf("read back: %v %v", got, err)
	}
	if got.Pnl == nil || *got.Pnl != pnl {
		t.Fatalf("expected pnl persisted, got %+v", got.Pnl)
	}
}

type testPartnerRelationship struct {
	sponsor, partner int
	relType          string
}

func (t *testPartnerRelationship) model() *models.PartnerRelationship {
	return &models.PartnerRelationship{
		SponsorUserID:    t.sponsor,
		PartnerUserID:    t.partner,
		RelationshipType: t.relType,
		IsActive:         true,
	}
}

// newTestTradeLog builds a minimal TradeLog for the round-trip test.
func newTestTradeLog(resultIDFK, tradeNumber int, entryPrice float64, at *time.Time) *models.TradeLog {
	side := "long"
	return &models.TradeLog{
		ResultIDFK:     resultIDFK,
		TradeNumber:    &tradeNumber,
		EntryPrice1:    &entryPrice,
		EntryPrice2:    &entryPrice,
		Quantity1:      &entryPrice,
		Quantity2:      &entryPrice,
		Side1:          &side,
		Side2:          &side,
		EntryTimestamp: at,
	}
}
