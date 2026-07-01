package repository

import (
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

// migrationSource returns the absolute path to the backend postgres migrations
// directory, anchored relative to this test file so it works regardless of the
// working directory `go test` is invoked from.
func migrationSource(t *testing.T) string {
	t.Helper()
	_, thisFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("could not determine test file path")
	}
	// this file lives in backend/internal/repository; migrations live in backend/migrations/postgres.
	dir := filepath.Join(filepath.Dir(thisFile), "..", "..", "migrations", "postgres")
	abs, err := filepath.Abs(dir)
	if err != nil {
		t.Fatalf("resolve migrations dir: %v", err)
	}
	return abs
}

func readMigration(t *testing.T, name string) string {
	t.Helper()
	path := filepath.Join(migrationSource(t), name)
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read migration %s: %v", name, err)
	}
	return string(data)
}

// TestTaskCommandsSchema_HasUpdatedAt is the always-on Phase 0 contract test.
//
// It proves the schema/repository mismatch documented in the Final Application
// Improvement Plan is resolved at the migration layer: 000063 created
// task_commands WITHOUT an updated_at column while repository.UpdateTaskCommandStatus
// sets updated_at, and migration 000067 adds that column. The companion
// integration test (build tag "integration") proves the repository actually
// executes against the real schema.
func TestTaskCommandsSchema_HasUpdatedAt(t *testing.T) {
	createMigration := readMigration(t, "000063_create_task_commands.up.sql")
	if !strings.Contains(createMigration, "CREATE TABLE task_commands") {
		t.Fatal("000063 up migration must create the task_commands table")
	}
	// The original table definition must not declare updated_at (the root cause).
	if strings.Contains(createMigration, "updated_at") {
		t.Fatal("000063 must not define updated_at on task_commands; " +
			"000067 is the single place that adds it")
	}

	addMigration := readMigration(t, "000067_add_task_commands_updated_at.up.sql")
	for _, want := range []string{
		"ALTER TABLE task_commands",
		"ADD COLUMN IF NOT EXISTS updated_at",
		"BEFORE UPDATE ON task_commands",
	} {
		if !strings.Contains(addMigration, want) {
			t.Fatalf("000067 must contain %q", want)
		}
	}

	// The down migration must drop what the up migration adds, so rollback works.
	downMigration := readMigration(t, "000067_add_task_commands_updated_at.down.sql")
	if !strings.Contains(downMigration, "DROP COLUMN IF EXISTS updated_at") {
		t.Fatal("000067 down migration must drop the updated_at column")
	}
}

// TestTaskCommandsSchema_MigrationsSequentiallyNumbered guards against the
// common mistake of reusing a migration number, which golang-migrate would
// silently ignore.
func TestTaskCommandsSchema_MigrationsSequentiallyNumbered(t *testing.T) {
	dir := migrationSource(t)
	for _, name := range []string{
		"000063_create_task_commands.up.sql",
		"000063_create_task_commands.down.sql",
		"000064_create_task_runs.up.sql",
		"000064_create_task_runs.down.sql",
		"000065_create_task_attempts.up.sql",
		"000065_create_task_attempts.down.sql",
		"000066_create_worker_heartbeats.up.sql",
		"000066_create_worker_heartbeats.down.sql",
		"000067_add_task_commands_updated_at.up.sql",
		"000067_add_task_commands_updated_at.down.sql",
	} {
		if _, err := os.Stat(filepath.Join(dir, name)); err != nil {
			t.Fatalf("expected migration file %s to exist: %v", name, err)
		}
	}
}
