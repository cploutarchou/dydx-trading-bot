package services

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/nats"
	"github.com/google/uuid"
)

// fakeTaskStore records status transitions without a database.
type fakeTaskStore struct {
	mu       sync.Mutex
	statuses []statusUpdate
	command  *models.TaskCommand
	runID    string
}

type statusUpdate struct {
	id     string
	status string
}

func (f *fakeTaskStore) CreateTaskCommand(_ context.Context, commandType, ownerType, ownerID, idempotencyKey string, _ *int, payloadJSON []byte) (*models.TaskCommand, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	cmd := &models.TaskCommand{
		ID:             uuid.New().String(),
		CommandType:    commandType,
		OwnerType:      ownerType,
		OwnerID:        ownerID,
		IdempotencyKey: idempotencyKey,
		PayloadJSON:    payloadJSON,
		Status:         "pending",
		CreatedAt:      time.Now().UTC(),
	}
	f.command = cmd
	return cmd, nil
}

func (f *fakeTaskStore) UpdateTaskCommandStatus(_ context.Context, id, status string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.statuses = append(f.statuses, statusUpdate{id: id, status: status})
	return nil
}

func (f *fakeTaskStore) CreateTaskRun(_ context.Context, commandID, taskType string, maxRetries int) (*models.TaskRun, error) {
	return &models.TaskRun{ID: uuid.New().String(), CommandID: commandID, TaskType: taskType, MaxRetries: maxRetries}, nil
}

func (f *fakeTaskStore) hasPublished() bool {
	f.mu.Lock()
	defer f.mu.Unlock()
	for _, s := range f.statuses {
		if s.status == "published" {
			return true
		}
	}
	return false
}

// fakePublisher records the publish attempt and returns a configured outcome.
type fakePublisher struct {
	mu        sync.Mutex
	attempted int32
	wg        sync.WaitGroup
	result    *nats.PublishResult
	err       error
}

func newFakePublisher(result *nats.PublishResult, err error) *fakePublisher {
	fp := &fakePublisher{result: result, err: err}
	fp.wg.Add(1)
	return fp
}

func (f *fakePublisher) Publish(_ context.Context, _ nats.Envelope) (*nats.PublishResult, error) {
	f.mu.Lock()
	f.attempted++
	f.mu.Unlock()
	defer f.wg.Done()
	return f.result, f.err
}

// waitForPublished polls for the published transition up to timeout.
func waitForPublished(t *testing.T, store *fakeTaskStore, timeout time.Duration) bool {
	t.Helper()
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if store.hasPublished() {
			return true
		}
		time.Sleep(5 * time.Millisecond)
	}
	return store.hasPublished()
}

// TestPublishBacktestCommand_StatusPublishedOnlyOnTransportSuccess is the Phase 1
// regression test: command status must reach "published" only after the JetStream
// publish is acknowledged.
func TestPublishBacktestCommand_StatusPublishedOnlyOnTransportSuccess(t *testing.T) {
	store := &fakeTaskStore{}
	pub := newFakePublisher(&nats.PublishResult{Stream: "BACKTEST_COMMANDS", Sequence: 1}, nil)
	svc := &NATSCommandService{
		taskRepo:  store,
		publisher: pub,
		settings:  config.NATSSettings{Enabled: true},
		clock:     time.Now,
	}

	cmd, err := svc.PublishBacktestCommand(context.Background(), "run-1", map[string]interface{}{"name": "t"}, nil, "idem-1", "trace-1")
	if err != nil {
		t.Fatalf("PublishBacktestCommand: %v", err)
	}
	if cmd.Status != "pending" {
		t.Fatalf("command must remain pending synchronously, got %q", cmd.Status)
	}

	if !waitForPublished(t, store, 2*time.Second) {
		t.Fatal("expected command status to advance to published after successful transport")
	}
}

// TestPublishBacktestCommand_StatusStaysPendingOnTransportFailure proves the
// fail-closed behavior: a publish failure must never mark the command published.
func TestPublishBacktestCommand_StatusStaysPendingOnTransportFailure(t *testing.T) {
	store := &fakeTaskStore{}
	pub := newFakePublisher(nil, errors.New("nats unavailable"))
	svc := &NATSCommandService{
		taskRepo:  store,
		publisher: pub,
		settings:  config.NATSSettings{Enabled: true},
		clock:     time.Now,
	}

	if _, err := svc.PublishBacktestCommand(context.Background(), "run-2", map[string]interface{}{"name": "t"}, nil, "idem-2", "trace-2"); err != nil {
		t.Fatalf("PublishBacktestCommand: %v", err)
	}

	// Wait until the publish attempt has executed so the goroutine has decided.
	_ = pub.WaitTimeout(2 * time.Second)

	// Give the goroutine a moment to misbehave, then assert it did not.
	time.Sleep(50 * time.Millisecond)
	if store.hasPublished() {
		t.Fatal("command must NOT be marked published when transport failed")
	}
}

// TestPublishBacktestCommand_StatusStaysPendingWhenDisabled proves NATS-disabled
// leaves command state truthful (pending), not falsely published.
func TestPublishBacktestCommand_StatusStaysPendingWhenDisabled(t *testing.T) {
	store := &fakeTaskStore{}
	pub := newFakePublisher(&nats.PublishResult{Stream: "BACKTEST_COMMANDS", Sequence: 1}, nil)
	svc := &NATSCommandService{
		taskRepo:  store,
		publisher: pub, // present but NATS disabled
		settings:  config.NATSSettings{Enabled: false},
		clock:     time.Now,
	}

	if _, err := svc.PublishBacktestCommand(context.Background(), "run-3", map[string]interface{}{"name": "t"}, nil, "idem-3", "trace-3"); err != nil {
		t.Fatalf("PublishBacktestCommand: %v", err)
	}

	time.Sleep(50 * time.Millisecond)
	if store.hasPublished() {
		t.Fatal("command must NOT be marked published when NATS is disabled")
	}
	pub.mu.Lock()
	attempts := pub.attempted
	pub.mu.Unlock()
	if attempts != 0 {
		t.Fatalf("disabled service must not attempt publish, got %d attempts", attempts)
	}
}

// WaitTimeout is a helper for the fake publisher's WaitGroup.
func (f *fakePublisher) WaitTimeout(timeout time.Duration) bool {
	done := make(chan struct{})
	go func() {
		f.wg.Wait()
		close(done)
	}()
	select {
	case <-done:
		return true
	case <-time.After(timeout):
		return false
	}
}

// TestPublishBacktestCommand_CorrelatesRunID proves the Phase 1 correlation fix:
// the run_id passed to PublishBacktestCommand is used as BOTH the command owner_id
// and idempotency_key, so command state correlates to the authoritative backtest
// run instead of a fabricated key.
func TestPublishBacktestCommand_CorrelatesRunID(t *testing.T) {
	store := &fakeTaskStore{}
	pub := newFakePublisher(&nats.PublishResult{Stream: "BACKTEST_COMMANDS", Sequence: 7}, nil)
	svc := &NATSCommandService{
		taskRepo:  store,
		publisher: pub,
		settings:  config.NATSSettings{Enabled: true},
		clock:     time.Now,
	}

	const runID = "run-real-123"
	if _, err := svc.PublishBacktestCommand(context.Background(), runID, map[string]interface{}{"name": "t"}, nil, runID, "trace-correlate"); err != nil {
		t.Fatalf("PublishBacktestCommand: %v", err)
	}

	store.mu.Lock()
	cmd := store.command
	store.mu.Unlock()
	if cmd == nil {
		t.Fatal("expected a task command to be created")
	}
	if cmd.OwnerID != runID {
		t.Fatalf("command owner_id must equal the real run_id, got owner_id=%q want %q", cmd.OwnerID, runID)
	}
	if cmd.IdempotencyKey != runID {
		t.Fatalf("command idempotency_key must equal the real run_id, got idempotency_key=%q want %q", cmd.IdempotencyKey, runID)
	}
}
