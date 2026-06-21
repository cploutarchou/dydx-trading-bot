package repository

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"fmt"
	"strings"
	"testing"
	"time"
)

func resetBacktestRunSyncOutcomeCounters(t *testing.T) {
	t.Helper()
	originalInsert := backtestRunSyncFreshInsertTotal.Load()
	originalUpdate := backtestRunSyncRerunUpdateTotal.Load()
	backtestRunSyncFreshInsertTotal.Store(0)
	backtestRunSyncRerunUpdateTotal.Store(0)
	t.Cleanup(func() {
		backtestRunSyncFreshInsertTotal.Store(originalInsert)
		backtestRunSyncRerunUpdateTotal.Store(originalUpdate)
	})
}

// TestUpsertBacktestRunPreservesErrorMessageWhenPayloadNil verifies that
// UpsertBacktestRun passes nil for error_message when the payload's ErrorMessage
// is invalid (null), letting the COALESCE in the SQL preserve the DB value.
func TestUpsertBacktestRunPreservesErrorMessageWhenPayloadNil(t *testing.T) {
	db := openBacktestScriptedDB(t, []backtestScriptedStep{
		{
			op:            "query",
			queryContains: "SELECT id FROM backtest_runs",
			err:           sql.ErrNoRows,
		},
		{
			op:            "exec",
			queryContains: "INSERT INTO backtest_runs",
			assertArgs: func(t *testing.T, args []driver.NamedValue) {
				t.Helper()
				if len(args) < 21 {
					t.Fatalf("expected at least 21 args for UPSERT, got %d", len(args))
				}
				// ? is the error_message value; must be nil when ErrorMessage.Valid == false
				if args[20].Value != nil {
					t.Fatalf("expected error_message arg ? to be nil, got %#v", args[20].Value)
				}
			},
			result: driver.RowsAffected(1),
		},
	})
	defer func() { _ = db.Close() }()

	repo := NewBacktestSyncRepository(db)
	durationSeconds := 123.45
	err := repo.UpsertBacktestRun(BacktestRunSyncPayload{
		RunID:           "run-sync-1",
		UserID:          7,
		Status:          "completed",
		StartDate:       "2026-04-01",
		EndDate:         "2026-04-02",
		NumPairs:        2,
		TotalMarkets:    10,
		DurationSeconds: &durationSeconds,
		Resolution:      sql.NullString{},
		Config:          sql.NullString{},
		ErrorMessage:    sql.NullString{}, // not valid → nil → COALESCE preserves DB value
		TotalTrades:     sql.NullInt64{},
		WinningTrades:   sql.NullInt64{},
		LosingTrades:    sql.NullInt64{},
		WinRate:         sql.NullFloat64{},
		TotalPnL:        sql.NullFloat64{},
		TotalPnLUSD:     sql.NullFloat64{},
	})
	if err != nil {
		t.Fatalf("UpsertBacktestRun returned error: %v", err)
	}
}

// TestUpsertBacktestRunUpsertsByRunID verifies the repository executes a single
// run_id-keyed upsert statement (safe for reruns that reuse the same run_id).
func TestUpsertBacktestRunUpsertsByRunID(t *testing.T) {
	db := openBacktestScriptedDB(t, []backtestScriptedStep{
		{
			op:            "query",
			queryContains: "SELECT id FROM backtest_runs",
			rows:          singleRowRows("id", []driver.Value{1}),
		},
		{
			op:            "exec",
			queryContains: "INSERT INTO backtest_runs",
			assertArgs: func(t *testing.T, args []driver.NamedValue) {
				t.Helper()
				if len(args) < 1 || args[0].Value != "run-new-1" {
					t.Fatalf("expected run_id run-new-1 as ?, got %#v", args[0].Value)
				}
			},
			result: driver.RowsAffected(1),
		},
	})
	defer func() { _ = db.Close() }()

	repo := NewBacktestSyncRepository(db)
	err := repo.UpsertBacktestRun(BacktestRunSyncPayload{
		RunID: "run-new-1", UserID: 5, Status: "queued",
		StartDate: "2026-04-01", EndDate: "2026-04-02", NumPairs: 1, TotalMarkets: 5,
	})
	if err != nil {
		t.Fatalf("UpsertBacktestRun returned error: %v", err)
	}
}

func TestUpsertBacktestRunOutcomeCounters(t *testing.T) {
	resetBacktestRunSyncOutcomeCounters(t)

	insertDB := openBacktestScriptedDB(t, []backtestScriptedStep{
		{op: "query", queryContains: "SELECT id FROM backtest_runs", err: sql.ErrNoRows},
		{op: "exec", queryContains: "INSERT INTO backtest_runs", result: driver.RowsAffected(1)},
	})
	defer func() { _ = insertDB.Close() }()

	insertRepo := NewBacktestSyncRepository(insertDB)
	if err := insertRepo.UpsertBacktestRun(BacktestRunSyncPayload{
		RunID: "run-insert-1", UserID: 101, Status: "queued",
		StartDate: "2026-04-01", EndDate: "2026-04-02", NumPairs: 1, TotalMarkets: 3,
	}); err != nil {
		t.Fatalf("insert upsert returned error: %v", err)
	}

	afterInsert := BacktestRunSyncOutcomeCounters()
	if afterInsert["fresh_inserts_total"] != 1 {
		t.Fatalf("expected fresh_inserts_total=1, got %d", afterInsert["fresh_inserts_total"])
	}
	if afterInsert["rerun_updates_total"] != 0 {
		t.Fatalf("expected rerun_updates_total=0, got %d", afterInsert["rerun_updates_total"])
	}

	updateDB := openBacktestScriptedDB(t, []backtestScriptedStep{
		{op: "query", queryContains: "SELECT id FROM backtest_runs", rows: singleRowRows("id", []driver.Value{1})},
		{op: "exec", queryContains: "INSERT INTO backtest_runs", result: driver.RowsAffected(0)},
	})
	defer func() { _ = updateDB.Close() }()

	updateRepo := NewBacktestSyncRepository(updateDB)
	if err := updateRepo.UpsertBacktestRun(BacktestRunSyncPayload{
		RunID: "run-insert-1", UserID: 101, Status: "running",
		StartDate: "2026-04-01", EndDate: "2026-04-02", NumPairs: 1, TotalMarkets: 3,
	}); err != nil {
		t.Fatalf("update upsert returned error: %v", err)
	}

	afterUpdate := BacktestRunSyncOutcomeCounters()
	if afterUpdate["fresh_inserts_total"] != 1 {
		t.Fatalf("expected fresh_inserts_total=1 after update, got %d", afterUpdate["fresh_inserts_total"])
	}
	if afterUpdate["rerun_updates_total"] != 1 {
		t.Fatalf("expected rerun_updates_total=1 after update, got %d", afterUpdate["rerun_updates_total"])
	}
}

// ─── minimal scripted driver ──────────────────────────────────────────────────

type backtestScriptedStep struct {
	op            string
	queryContains string
	assertArgs    func(*testing.T, []driver.NamedValue)
	rows          driver.Rows
	result        driver.Result
	err           error
}

type backtestScriptedScenario struct {
	t     *testing.T
	steps []backtestScriptedStep
	index int
}

func (s *backtestScriptedScenario) next(op, query string, args []driver.NamedValue) backtestScriptedStep {
	s.t.Helper()
	if s.index >= len(s.steps) {
		s.t.Fatalf("unexpected %s call for query %q (all %d steps consumed)", op, query, len(s.steps))
	}
	step := s.steps[s.index]
	s.index++
	if step.op != op {
		s.t.Fatalf("expected op %q, got %q (query: %q)", step.op, op, query)
	}
	if step.queryContains != "" && !strings.Contains(strings.ToUpper(query), strings.ToUpper(step.queryContains)) {
		s.t.Fatalf("expected query containing %q, got: %q", step.queryContains, query)
	}
	if step.assertArgs != nil {
		step.assertArgs(s.t, args)
	}
	return step
}

var backtestScenarioStore = make(map[string]*backtestScriptedScenario)
var backtestSeq int

func init() {
	sql.Register("backtest_sync_scripted", &backtestScriptedDriver{})
}

func openBacktestScriptedDB(t *testing.T, steps []backtestScriptedStep) *sql.DB {
	t.Helper()
	backtestSeq++
	dsn := t.Name() + "_" + time.Now().Format("20060102150405.000000000")
	sc := &backtestScriptedScenario{t: t, steps: steps}
	backtestScenarioStore[dsn] = sc
	db, err := sql.Open("backtest_sync_scripted", dsn)
	if err != nil {
		t.Fatalf("open backtest scripted db: %v", err)
	}
	t.Cleanup(func() {
		if sc.index != len(sc.steps) {
			t.Errorf("backtest scripted DB: consumed %d/%d steps", sc.index, len(sc.steps))
		}
		delete(backtestScenarioStore, dsn)
	})
	return db
}

type backtestScriptedDriver struct{}

func (backtestScriptedDriver) Open(name string) (driver.Conn, error) {
	sc := backtestScenarioStore[name]
	return &backtestScriptedConn{sc: sc}, nil
}

type backtestScriptedConn struct{ sc *backtestScriptedScenario }

func (c *backtestScriptedConn) Prepare(string) (driver.Stmt, error) { return nil, nil }
func (c *backtestScriptedConn) Close() error                        { return nil }
func (c *backtestScriptedConn) Begin() (driver.Tx, error)           { return nil, nil }
func (c *backtestScriptedConn) ExecContext(_ context.Context, query string, args []driver.NamedValue) (driver.Result, error) {
	if c.sc == nil {
		return driver.RowsAffected(0), nil
	}
	step := c.sc.next("exec", query, args)
	if step.result == nil {
		step.result = driver.RowsAffected(0)
	}
	return step.result, step.err
}
func (c *backtestScriptedConn) QueryContext(_ context.Context, query string, args []driver.NamedValue) (driver.Rows, error) {
	if c.sc == nil {
		return nil, nil
	}
	step := c.sc.next("query", query, args)
	if step.rows == nil {
		return nil, step.err
	}
	return step.rows, step.err
}
func (c *backtestScriptedConn) CheckNamedValue(*driver.NamedValue) error { return nil }

type singleRowFakeRows struct {
	cols []string
	vals []driver.Value
	done bool
}

func singleRowRows(column string, values []driver.Value) driver.Rows {
	return &singleRowFakeRows{cols: []string{column}, vals: values}
}

func (r *singleRowFakeRows) Columns() []string { return r.cols }
func (r *singleRowFakeRows) Close() error       { return nil }
func (r *singleRowFakeRows) Next(dest []driver.Value) error {
	if r.done {
		return fmt.Errorf("EOF")
	}
	for i := range dest {
		if i < len(r.vals) {
			dest[i] = r.vals[i]
		}
	}
	r.done = true
	return nil
}
