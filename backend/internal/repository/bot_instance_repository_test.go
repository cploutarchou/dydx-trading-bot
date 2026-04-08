package repository

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"fmt"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/lib/pq"
	_ "modernc.org/sqlite"
)

func TestUpdateBotInstanceErrorUpdatesMatchingInstance(t *testing.T) {
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite db: %v", err)
	}
	defer func() { _ = db.Close() }()

	if _, err := db.Exec(`
		CREATE TABLE bot_instances (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			instance_id TEXT NOT NULL UNIQUE,
			error_message TEXT,
			last_error_at DATETIME,
			status TEXT,
			updated_at DATETIME
		)
	`); err != nil {
		t.Fatalf("create bot_instances table: %v", err)
	}

	if _, err := db.Exec(
		`INSERT INTO bot_instances (instance_id, status, updated_at) VALUES (?, ?, ?)`,
		"bot-1",
		"RUNNING",
		time.Now().UTC(),
	); err != nil {
		t.Fatalf("insert bot instance: %v", err)
	}

	repo := NewBotInstanceRepository(db)
	if err := repo.UpdateBotInstanceError("bot-1", "boom"); err != nil {
		t.Fatalf("UpdateBotInstanceError returned error: %v", err)
	}

	var errorMessage string
	var status string
	var hasLastErrorAt bool
	var hasUpdatedAt bool
	if err := db.QueryRow(
		`SELECT error_message, status, last_error_at IS NOT NULL, updated_at IS NOT NULL FROM bot_instances WHERE instance_id = ?`,
		"bot-1",
	).Scan(&errorMessage, &status, &hasLastErrorAt, &hasUpdatedAt); err != nil {
		t.Fatalf("query updated bot instance: %v", err)
	}

	if errorMessage != "boom" {
		t.Fatalf("expected error_message=boom, got %q", errorMessage)
	}
	if status != "ERROR" {
		t.Fatalf("expected status=ERROR, got %q", status)
	}
	if !hasLastErrorAt {
		t.Fatal("expected last_error_at to be set")
	}
	if !hasUpdatedAt {
		t.Fatal("expected updated_at to be set")
	}
}

func TestUpdateBotInstanceErrorFallbackUsesInstanceID(t *testing.T) {
	db := openScriptedDB(t, []scriptedStep{
		{
			op:            "exec",
			queryContains: "SET error_message = $1, last_error_at = $2, status = $3, updated_at = $4",
			assertArgs: func(t *testing.T, args []driver.NamedValue) {
				t.Helper()
				if len(args) != 5 {
					t.Fatalf("expected 5 args for primary update, got %d", len(args))
				}
				if args[0].Value != "boom" {
					t.Fatalf("expected error message arg to be boom, got %#v", args[0].Value)
				}
				if args[2].Value != "ERROR" {
					t.Fatalf("expected normalized status arg to be ERROR, got %#v", args[2].Value)
				}
				if args[4].Value != "bot-1" {
					t.Fatalf("expected WHERE arg to be bot-1, got %#v", args[4].Value)
				}
			},
			err: &pq.Error{Code: "42703"},
		},
		{
			op:            "exec",
			queryContains: "SET status = $1, updated_at = $2",
			assertArgs: func(t *testing.T, args []driver.NamedValue) {
				t.Helper()
				if len(args) != 3 {
					t.Fatalf("expected 3 args for fallback update, got %d", len(args))
				}
				if args[0].Value != "ERROR" {
					t.Fatalf("expected fallback status arg to be ERROR, got %#v", args[0].Value)
				}
				if args[2].Value != "bot-1" {
					t.Fatalf("expected fallback WHERE arg to be bot-1, got %#v", args[2].Value)
				}
			},
			result: driver.RowsAffected(1),
		},
	})
	defer func() { _ = db.Close() }()

	repo := NewBotInstanceRepository(db)
	if err := repo.UpdateBotInstanceError("bot-1", "boom"); err != nil {
		t.Fatalf("UpdateBotInstanceError returned error: %v", err)
	}
}

func TestListBotInstancesByUserIDUndefinedUserIDFailsClosed(t *testing.T) {
	db := openScriptedDB(t, []scriptedStep{
		{
			op:            "query",
			queryContains: "WHERE user_id = $1",
			assertArgs: func(t *testing.T, args []driver.NamedValue) {
				t.Helper()
				if len(args) != 3 {
					t.Fatalf("expected 3 args for list query, got %d", len(args))
				}
				if fmt.Sprint(args[0].Value) != "42" {
					t.Fatalf("expected user_id arg 42, got %#v", args[0].Value)
				}
			},
			err: &pq.Error{Code: "42703"},
		},
	})
	defer func() { _ = db.Close() }()

	repo := NewBotInstanceRepository(db)
	instances, err := repo.ListBotInstancesByUserID(42, 10, 0)
	if err == nil {
		t.Fatal("expected error when user_id column is missing")
	}
	if instances != nil {
		t.Fatalf("expected nil instances on fail-closed path, got %#v", instances)
	}
	if !strings.Contains(err.Error(), "current schema missing user_id") {
		t.Fatalf("expected migration guidance in error, got %v", err)
	}
}

type scriptedStep struct {
	op            string
	queryContains string
	assertArgs    func(*testing.T, []driver.NamedValue)
	result        driver.Result
	rows          driver.Rows
	err           error
}

type scriptedScenario struct {
	t     *testing.T
	steps []scriptedStep
	mu    sync.Mutex
	index int
}

func (s *scriptedScenario) next(op string, query string, args []driver.NamedValue) scriptedStep {
	s.t.Helper()

	s.mu.Lock()
	defer s.mu.Unlock()

	if s.index >= len(s.steps) {
		s.t.Fatalf("unexpected %s call with query %q", op, query)
	}

	step := s.steps[s.index]
	s.index++

	if step.op != op {
		s.t.Fatalf("expected %s call, got %s for query %q", step.op, op, query)
	}
	if step.queryContains != "" && !strings.Contains(query, step.queryContains) {
		s.t.Fatalf("expected query containing %q, got %q", step.queryContains, query)
	}
	if step.assertArgs != nil {
		step.assertArgs(s.t, args)
	}

	return step
}

func (s *scriptedScenario) assertComplete() {
	s.t.Helper()

	s.mu.Lock()
	defer s.mu.Unlock()

	if s.index != len(s.steps) {
		s.t.Fatalf("consumed %d/%d scripted DB steps", s.index, len(s.steps))
	}
}

var (
	scriptedDriverOnce sync.Once
	scriptedScenarios  sync.Map
	scriptedCounter    uint64
)

func openScriptedDB(t *testing.T, steps []scriptedStep) *sql.DB {
	t.Helper()

	scriptedDriverOnce.Do(func() {
		sql.Register("bot_instance_repository_scripted", scriptedDriver{})
	})

	scriptedCounter++
	dsn := fmt.Sprintf("scenario-%d-%d", time.Now().UnixNano(), scriptedCounter)
	scenario := &scriptedScenario{t: t, steps: steps}
	scriptedScenarios.Store(dsn, scenario)

	db, err := sql.Open("bot_instance_repository_scripted", dsn)
	if err != nil {
		t.Fatalf("open scripted db: %v", err)
	}

	t.Cleanup(func() {
		scenario.assertComplete()
		scriptedScenarios.Delete(dsn)
	})

	return db
}

type scriptedDriver struct{}

func (scriptedDriver) Open(name string) (driver.Conn, error) {
	scenarioValue, ok := scriptedScenarios.Load(name)
	if !ok {
		return nil, fmt.Errorf("missing scripted scenario: %s", name)
	}
	return &scriptedConn{scenario: scenarioValue.(*scriptedScenario)}, nil
}

type scriptedConn struct {
	scenario *scriptedScenario
}

func (c *scriptedConn) Prepare(string) (driver.Stmt, error) {
	return nil, fmt.Errorf("prepare not implemented")
}

func (c *scriptedConn) Close() error {
	return nil
}

func (c *scriptedConn) Begin() (driver.Tx, error) {
	return nil, fmt.Errorf("transactions not implemented")
}

func (c *scriptedConn) ExecContext(_ context.Context, query string, args []driver.NamedValue) (driver.Result, error) {
	step := c.scenario.next("exec", query, args)
	if step.result == nil {
		step.result = driver.RowsAffected(0)
	}
	return step.result, step.err
}

func (c *scriptedConn) QueryContext(_ context.Context, query string, args []driver.NamedValue) (driver.Rows, error) {
	step := c.scenario.next("query", query, args)
	return step.rows, step.err
}

func (c *scriptedConn) CheckNamedValue(*driver.NamedValue) error {
	return nil
}
