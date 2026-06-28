package repository

import (
	"context"
	"errors"
	"testing"
	"time"
)

func TestTaskRepository_NilDB(t *testing.T) {
	repo := NewTaskRepository(nil)
	ctx := context.Background()

	// Test all methods with nil db return proper error
	err := repo.UpdateTaskCommandStatus(ctx, "test-id", "published")
	if err == nil || err.Error() != "task repository: nil db" {
		t.Errorf("expected nil db error, got: %v", err)
	}

	err = repo.UpdateTaskRunStatus(ctx, "test-id", "running")
	if err == nil || err.Error() != "task repository: nil db" {
		t.Errorf("expected nil db error, got: %v", err)
	}

	err = repo.UpdateTaskRunProgress(ctx, "test-id", 50.0)
	if err == nil || err.Error() != "task repository: nil db" {
		t.Errorf("expected nil db error, got: %v", err)
	}

	err = repo.UpdateTaskRunHeartbeat(ctx, "test-id", "", "", "")
	if err == nil || err.Error() != "task repository: nil db" {
		t.Errorf("expected nil db error, got: %v", err)
	}

	err = repo.UpdateTaskAttemptCompletion(ctx, "test-id", nil, "success", "", "")
	if err == nil || err.Error() != "task repository: nil db" {
		t.Errorf("expected nil db error, got: %v", err)
	}

	_, err = repo.GetTaskCommandByID(ctx, "test-id")
	if err == nil || err.Error() != "task repository: nil db" {
		t.Errorf("expected nil db error, got: %v", err)
	}

	_, err = repo.GetTaskRunByID(ctx, "test-id")
	if err == nil || err.Error() != "task repository: nil db" {
		t.Errorf("expected nil db error, got: %v", err)
	}

	_, err = repo.GetTaskRunsByCommandID(ctx, "test-id")
	if err == nil || err.Error() != "task repository: nil db" {
		t.Errorf("expected nil db error, got: %v", err)
	}

	_, err = repo.GetTaskAttemptsByTaskRunID(ctx, "test-id")
	if err == nil || err.Error() != "task repository: nil db" {
		t.Errorf("expected nil db error, got: %v", err)
	}

	_, err = repo.GetWorkerHeartbeat(ctx, "test-id")
	if err == nil || err.Error() != "task repository: nil db" {
		t.Errorf("expected nil db error, got: %v", err)
	}

	_, err = repo.GetStaleWorkerHeartbeats(ctx, nil)
	if err == nil || err.Error() != "task repository: nil db" {
		t.Errorf("expected nil db error, got: %v", err)
	}

	err = repo.DeleteWorkerHeartbeat(ctx, "test-id")
	if err == nil || err.Error() != "task repository: nil db" {
		t.Errorf("expected nil db error, got: %v", err)
	}
}

func TestTaskRepository_Constants(t *testing.T) {
	// Test that constants are defined correctly
	if TaskCommandStatusPending != "pending" {
		t.Errorf("expected TaskCommandStatusPending to be 'pending', got '%s'", TaskCommandStatusPending)
	}
	if TaskCommandStatusPublished != "published" {
		t.Errorf("expected TaskCommandStatusPublished to be 'published', got '%s'", TaskCommandStatusPublished)
	}
	if TaskCommandStatusCompleted != "completed" {
		t.Errorf("expected TaskCommandStatusCompleted to be 'completed', got '%s'", TaskCommandStatusCompleted)
	}
	if TaskCommandStatusFailed != "failed" {
		t.Errorf("expected TaskCommandStatusFailed to be 'failed', got '%s'", TaskCommandStatusFailed)
	}

	if TaskRunStatusPending != "pending" {
		t.Errorf("expected TaskRunStatusPending to be 'pending', got '%s'", TaskRunStatusPending)
	}
	if TaskRunStatusRunning != "running" {
		t.Errorf("expected TaskRunStatusRunning to be 'running', got '%s'", TaskRunStatusRunning)
	}
	if TaskRunStatusCompleted != "completed" {
		t.Errorf("expected TaskRunStatusCompleted to be 'completed', got '%s'", TaskRunStatusCompleted)
	}
	if TaskRunStatusFailed != "failed" {
		t.Errorf("expected TaskRunStatusFailed to be 'failed', got '%s'", TaskRunStatusFailed)
	}
	if TaskRunStatusCancelled != "cancelled" {
		t.Errorf("expected TaskRunStatusCancelled to be 'cancelled', got '%s'", TaskRunStatusCancelled)
	}

	if TaskAttemptOutcomeSuccess != "success" {
		t.Errorf("expected TaskAttemptOutcomeSuccess to be 'success', got '%s'", TaskAttemptOutcomeSuccess)
	}
	if TaskAttemptOutcomeFailed != "failed" {
		t.Errorf("expected TaskAttemptOutcomeFailed to be 'failed', got '%s'", TaskAttemptOutcomeFailed)
	}
	if TaskAttemptOutcomeTimeout != "timeout" {
		t.Errorf("expected TaskAttemptOutcomeTimeout to be 'timeout', got '%s'", TaskAttemptOutcomeTimeout)
	}

	if WorkerStatusActive != "active" {
		t.Errorf("expected WorkerStatusActive to be 'active', got '%s'", WorkerStatusActive)
	}
	if WorkerStatusStale != "stale" {
		t.Errorf("expected WorkerStatusStale to be 'stale', got '%s'", WorkerStatusStale)
	}
	if WorkerStatusDead != "dead" {
		t.Errorf("expected WorkerStatusDead to be 'dead', got '%s'", WorkerStatusDead)
	}
	if WorkerStatusStopped != "stopped" {
		t.Errorf("expected WorkerStatusStopped to be 'stopped', got '%s'", WorkerStatusStopped)
	}
}

func TestTaskRepository_NewTaskRepository(t *testing.T) {
	// Test that NewTaskRepository returns a non-nil repository
	repo := NewTaskRepository(nil)
	if repo == nil {
		t.Error("expected NewTaskRepository to return non-nil")
	}

	// Test with a mock db (nil is acceptable per the pattern)
	if repo.db != nil {
		t.Error("expected db to be nil when passed nil")
	}
}

func TestTaskRepository_ErrorHandling(t *testing.T) {
	// Test error wrapping
	repo := NewTaskRepository(nil)
	ctx := context.Background()

	// These should all return the same nil db error
	expectedErr := errors.New("task repository: nil db")

	testCases := []struct {
		name string
		fn   func() error
	}{
		{"UpdateTaskCommandStatus", func() error { return repo.UpdateTaskCommandStatus(ctx, "", "") }},
		{"UpdateTaskRunStatus", func() error { return repo.UpdateTaskRunStatus(ctx, "", "") }},
		{"UpdateTaskRunProgress", func() error { return repo.UpdateTaskRunProgress(ctx, "", 0) }},
		{"UpdateTaskRunHeartbeat", func() error { return repo.UpdateTaskRunHeartbeat(ctx, "", "", "", "") }},
		{"UpdateTaskRunWorkerAssignment", func() error { return repo.UpdateTaskRunWorkerAssignment(ctx, "", "", "", "", time.Now()) }},
		{"UpdateTaskRunCompletion", func() error { return repo.UpdateTaskRunCompletion(ctx, "", time.Now(), nil, nil, nil) }},
		{"IncrementTaskRunRetry", func() error { return repo.IncrementTaskRunRetry(ctx, "", "", "") }},
		{"UpdateTaskAttemptCompletion", func() error { return repo.UpdateTaskAttemptCompletion(ctx, "", nil, "", "", "") }},
		{"UpdateWorkerHeartbeatStatus", func() error { return repo.UpdateWorkerHeartbeatStatus(ctx, "", "") }},
		{"UpdateWorkerHeartbeatWithMetadata", func() error { return repo.UpdateWorkerHeartbeatWithMetadata(ctx, "", nil) }},
		{"DeleteWorkerHeartbeat", func() error { return repo.DeleteWorkerHeartbeat(ctx, "") }},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			err := tc.fn()
			if err == nil {
				t.Error("expected error, got nil")
			} else if err.Error() != expectedErr.Error() {
				t.Errorf("expected error '%s', got '%s'", expectedErr.Error(), err.Error())
			}
		})
	}
}
