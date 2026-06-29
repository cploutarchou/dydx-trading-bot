//go:build integration

// Integration tests for TaskRepository against a real PostgreSQL schema.
//
// These validate Phase 0 acceptance criteria that cannot be proven without a
// database: specifically that task-command status updates work against the real
// schema after migration 000067 added the updated_at column to task_commands
// (the repository previously SET updated_at on a column that did not exist).
//
// Run with:
//
//	TASK_REPO_TEST_DSN='postgres://user:pass@localhost:5432/dydx_task_test?sslmode=disable' \
//	  go test -tags=integration ./internal/repository/ -run TestTaskRepository_Integration -v
//
// The DSN must point at a database with migrations 000063..000067 applied.
// Skipped automatically when TASK_REPO_TEST_DSN is unset so this never breaks
// the normal test suite.
package repository

import (
	"context"
	"database/sql"
	"errors"
	"os"
	"testing"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
)

func integrationDSN(t *testing.T) string {
	t.Helper()
	dsn := os.Getenv("TASK_REPO_TEST_DSN")
	if dsn == "" {
		t.Skip("TASK_REPO_TEST_DSN not set; skipping task repository integration test")
	}
	return dsn
}

func openTaskDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("pgx", integrationDSN(t))
	if err != nil {
		t.Fatalf("open db: %v", err)
	}
	db.SetMaxOpenConns(2)
	if err := db.PingContext(testContext(t, 5*time.Second)); err != nil {
		t.Fatalf("ping db: %v", err)
	}
	// Clean slate so the test is order-independent and repeatable.
	for _, tbl := range []string{"task_attempts", "task_runs", "task_commands"} {
		if _, err := db.ExecContext(testContext(t, 5*time.Second), "TRUNCATE TABLE "+tbl+" CASCADE"); err != nil {
			t.Fatalf("truncate %s: %v", tbl, err)
		}
	}
	return db
}

func testContext(t *testing.T, timeout time.Duration) context.Context {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	t.Cleanup(cancel)
	return ctx
}

// TestTaskRepository_Integration_CommandStatusUpdate proves the Phase 0 fix:
// UpdateTaskCommandStatus no longer fails on the missing updated_at column and
// status transitions persist correctly.
func TestTaskRepository_Integration_CommandStatusUpdate(t *testing.T) {
	db := openTaskDB(t)
	t.Cleanup(func() { _ = db.Close() })
	repo := NewTaskRepository(db)
	ctx := testContext(t, 10*time.Second)

	created, err := repo.CreateTaskCommand(ctx, "backtest", "backtest", "run-1", "idem-1", intPtr(7), []byte(`{"ok":true}`))
	if err != nil {
		t.Fatalf("CreateTaskCommand: %v", err)
	}
	if created.Status != TaskCommandStatusPending {
		t.Fatalf("expected pending status after create, got %q", created.Status)
	}

	// Capture updated_at immediately after create via the DB (trigger/default).
	var updatedAtAfterCreate sql.NullTime
	if err := db.QueryRowContext(ctx, "SELECT updated_at FROM task_commands WHERE id=$1", created.ID).Scan(&updatedAtAfterCreate); err != nil {
		t.Fatalf("select updated_at: %v", err)
	}
	if !updatedAtAfterCreate.Valid {
		t.Fatal("updated_at should be populated by DEFAULT NOW() at create time")
	}

	// Sleep a tick so the trigger-bumped updated_at is strictly newer.
	time.Sleep(20 * time.Millisecond)

	// This call previously failed: "column "updated_at" of relation "task_commands" does not exist".
	if err := repo.UpdateTaskCommandStatus(ctx, created.ID, TaskCommandStatusPublished); err != nil {
		t.Fatalf("UpdateTaskCommandStatus failed against real schema: %v", err)
	}

	got, err := repo.GetTaskCommandByID(ctx, created.ID)
	if err != nil {
		t.Fatalf("GetTaskCommandByID: %v", err)
	}
	if got.Status != TaskCommandStatusPublished {
		t.Fatalf("expected published status after update, got %q", got.Status)
	}

	var updatedAtAfterUpdate sql.NullTime
	if err := db.QueryRowContext(ctx, "SELECT updated_at FROM task_commands WHERE id=$1", created.ID).Scan(&updatedAtAfterUpdate); err != nil {
		t.Fatalf("select updated_at after update: %v", err)
	}
	if !updatedAtAfterUpdate.Valid || !updatedAtAfterUpdate.Time.After(updatedAtAfterCreate.Time) {
		t.Fatalf("expected trigger to advance updated_at on UPDATE; before=%v after=%v",
			updatedAtAfterCreate.Time, updatedAtAfterUpdate.Time)
	}
}

// TestTaskRepository_Integration_CommandStatusUpdate_UnknownID confirms the
// status update fails closed (sql.ErrNoRows) for an unknown command rather than
// silently reporting success.
func TestTaskRepository_Integration_CommandStatusUpdate_UnknownID(t *testing.T) {
	db := openTaskDB(t)
	t.Cleanup(func() { _ = db.Close() })
	repo := NewTaskRepository(db)
	ctx := testContext(t, 5*time.Second)

	err := repo.UpdateTaskCommandStatus(ctx, "00000000-0000-0000-0000-000000000000", TaskCommandStatusFailed)
	if !errors.Is(err, sql.ErrNoRows) {
		t.Fatalf("expected sql.ErrNoRows for unknown command, got %v", err)
	}
}

// TestTaskRepository_Integration_RunLifecycle exercises CreateTaskRun and the
// run status/progress/heartbeat updates against the real task_runs schema.
func TestTaskRepository_Integration_RunLifecycle(t *testing.T) {
	db := openTaskDB(t)
	t.Cleanup(func() { _ = db.Close() })
	repo := NewTaskRepository(db)
	ctx := testContext(t, 10*time.Second)

	cmd, err := repo.CreateTaskCommand(ctx, "backtest", "backtest", "run-2", "idem-2", nil, []byte(`{}`))
	if err != nil {
		t.Fatalf("CreateTaskCommand: %v", err)
	}
	run, err := repo.CreateTaskRun(ctx, cmd.ID, "backtest_execution", 3)
	if err != nil {
		t.Fatalf("CreateTaskRun: %v", err)
	}
	if err := repo.UpdateTaskRunWorkerAssignment(ctx, run.ID, "celery", "bot", "task-xyz", time.Now().UTC()); err != nil {
		t.Fatalf("UpdateTaskRunWorkerAssignment: %v", err)
	}
	if err := repo.UpdateTaskRunProgress(ctx, run.ID, 42.0); err != nil {
		t.Fatalf("UpdateTaskRunProgress: %v", err)
	}
	if err := repo.UpdateTaskRunCompletion(ctx, run.ID, time.Now().UTC(), []byte(`{"pnl":1.0}`), nil, nil); err != nil {
		t.Fatalf("UpdateTaskRunCompletion: %v", err)
	}
	got, err := repo.GetTaskRunByID(ctx, run.ID)
	if err != nil {
		t.Fatalf("GetTaskRunByID: %v", err)
	}
	if got.Status != TaskRunStatusCompleted || got.ProgressPct != 42.0 {
		t.Fatalf("unexpected run state: status=%q progress=%v", got.Status, got.ProgressPct)
	}
}

func intPtr(v int) *int { return &v }
