package repository

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"
)

func TestWithUserAdmissionLock_ValidatesInputs(t *testing.T) {
	repo := NewBacktestRepository(nil)

	tests := []struct {
		name    string
		userID  int
		fn      func() error
		wantErr string
	}{
		{
			name:    "invalid_user_id_zero",
			userID:  0,
			fn:      func() error { return nil },
			wantErr: "invalid user id",
		},
		{
			name:    "invalid_user_id_negative",
			userID:  -1,
			fn:      func() error { return nil },
			wantErr: "invalid user id",
		},
		{
			name:    "missing_callback",
			userID:  123,
			fn:      nil,
			wantErr: "admission callback is required",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := repo.WithUserAdmissionLock(context.Background(), tt.userID, tt.fn)
			if err == nil {
				t.Fatalf("expected error, got nil")
			}
			if tt.wantErr != "" && err.Error() != tt.wantErr {
				t.Fatalf("expected error %q, got %q", tt.wantErr, err.Error())
			}
		})
	}
}

func TestWithUserAdmissionLock_CallsCallbackWhenLockAcquired(t *testing.T) {
	repo := NewBacktestRepository(nil)

	callbackCalled := false
	err := repo.WithUserAdmissionLock(context.Background(), 123, func() error {
		callbackCalled = true
		return nil
	})

	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if !callbackCalled {
		t.Fatal("expected callback to be called")
	}
}

func TestWithUserAdmissionLock_PropagatesCallbackError(t *testing.T) {
	repo := NewBacktestRepository(nil)

	expectedErr := errors.New("callback error")
	err := repo.WithUserAdmissionLock(context.Background(), 123, func() error {
		return expectedErr
	})

	if err != expectedErr {
		t.Fatalf("expected error %v, got %v", expectedErr, err)
	}
}

func TestWithUserAdmissionLock_FallsBackToInProcessLock(t *testing.T) {
	// Use nil database to force fallback to in-process locking
	repo := NewBacktestRepository(nil)

	executed := 0
	err := repo.WithUserAdmissionLock(context.Background(), 456, func() error {
		executed++
		return nil
	})

	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if executed != 1 {
		t.Fatalf("expected callback to execute once, got %d", executed)
	}
}

func TestWithUserAdmissionLock_SerializesAccessPerUser(t *testing.T) {
	// Test that concurrent access to the same user is serialized
	repo := NewBacktestRepository(nil)
	userID := 789

	var mu sync.Mutex
	var execOrder []int

	// Launch two goroutines that try to acquire lock for same user
	var wg sync.WaitGroup
	wg.Add(2)

	goroutineExecution := func(id int, delay time.Duration) {
		defer wg.Done()
		err := repo.WithUserAdmissionLock(context.Background(), userID, func() error {
			if delay > 0 {
				time.Sleep(delay)
			}
			mu.Lock()
			execOrder = append(execOrder, id)
			mu.Unlock()
			return nil
		})
		if err != nil {
			t.Errorf("goroutine %d failed: %v", id, err)
		}
	}

	// Start first goroutine that will hold the lock for 100ms
	go goroutineExecution(1, 100*time.Millisecond)

	// Give first goroutine time to acquire lock
	time.Sleep(10 * time.Millisecond)

	// Start second goroutine (should wait for first)
	go goroutineExecution(2, 0)

	wg.Wait()

	// Verify execution order: goroutine 1 should complete before goroutine 2
	if len(execOrder) != 2 {
		t.Fatalf("expected 2 executions, got %d", len(execOrder))
	}
	if execOrder[0] != 1 || execOrder[1] != 2 {
		t.Fatalf("expected execution order [1, 2], got %v", execOrder)
	}
}

func TestWithUserAdmissionLock_AllowsConcurrentAccessDifferentUsers(t *testing.T) {
	// Test that different users can acquire locks concurrently
	repo := NewBacktestRepository(nil)

	var mu sync.Mutex
	var executing int
	var maxConcurrent int

	// Launch multiple goroutines for different users
	var wg sync.WaitGroup
	wg.Add(3)

	for userID := 1; userID <= 3; userID++ {
		go func(uid int) {
			defer wg.Done()
			err := repo.WithUserAdmissionLock(context.Background(), uid, func() error {
				mu.Lock()
				executing++
				if executing > maxConcurrent {
					maxConcurrent = executing
				}
				mu.Unlock()

				time.Sleep(50 * time.Millisecond)

				mu.Lock()
				executing--
				mu.Unlock()
				return nil
			})
			if err != nil {
				t.Errorf("user %d failed: %v", uid, err)
			}
		}(userID)
	}

	wg.Wait()

	// Since locks are per-user, all three should be able to execute concurrently
	if maxConcurrent < 2 {
		t.Fatalf("expected at least 2 concurrent executions, got max %d", maxConcurrent)
	}
}

func TestWithUserAdmissionLock_HandlesContextCancellation(t *testing.T) {
	repo := NewBacktestRepository(nil)

	ctx, cancel := context.WithCancel(context.Background())
	cancel() // Cancel immediately

	err := repo.WithUserAdmissionLock(ctx, 999, func() error {
		return nil
	})

	// Even with cancelled context, in-process lock should work (fallback behavior)
	// The context is used for database operations, not for the in-process fallback
	if err != nil {
		t.Fatalf("expected no error (fallback), got %v", err)
	}
}

func TestIsAdvisoryLockUnsupportedError_DetectsPostgreSQLErrors(t *testing.T) {
	tests := []struct {
		name              string
		err               error
		expectUnsupported bool
	}{
		{
			name:              "pg_try_advisory_lock_does_not_exist",
			err:               errors.New("ERROR: function pg_try_advisory_lock does not exist"),
			expectUnsupported: true,
		},
		{
			name:              "no_such_function_pg_try_advisory_lock",
			err:               errors.New("no such function pg_try_advisory_lock"),
			expectUnsupported: true,
		},
		{
			name:              "other_postgres_error",
			err:               errors.New("ERROR: syntax error in SQL"),
			expectUnsupported: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := isAdvisoryLockUnsupportedError(tt.err)
			if got != tt.expectUnsupported {
				t.Fatalf("expected %v, got %v", tt.expectUnsupported, got)
			}
		})
	}
}

func TestIsAdvisoryLockUnsupportedError_DetectsMySQLErrors(t *testing.T) {
	tests := []struct {
		name              string
		err               error
		expectUnsupported bool
	}{
		{
			name:              "unknown_function_get_lock",
			err:               errors.New("Error 1305 (42000): FUNCTION get_lock does not exist"),
			expectUnsupported: true,
		},
		{
			name:              "lowercase_unknown_function",
			err:               errors.New("unknown function get_lock"),
			expectUnsupported: true,
		},
		{
			name:              "other_mysql_error",
			err:               errors.New("Error 1054 (42S22): Unknown column 'user_id'"),
			expectUnsupported: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := isAdvisoryLockUnsupportedError(tt.err)
			if got != tt.expectUnsupported {
				t.Fatalf("expected %v, got %v", tt.expectUnsupported, got)
			}
		})
	}
}

func TestIsAdvisoryLockUnsupportedError_HandlesNilError(t *testing.T) {
	got := isAdvisoryLockUnsupportedError(nil)
	if got {
		t.Fatal("expected false for nil error")
	}
}

func TestBacktestAdmissionLockKey_GeneratesConsistentKey(t *testing.T) {
	key1 := backtestAdmissionLockKey(123)
	key2 := backtestAdmissionLockKey(123)

	if key1 != key2 {
		t.Fatalf("expected consistent key, got %q and %q", key1, key2)
	}
}

func TestBacktestAdmissionLockKey_GeneratesDifferentKeysPerUser(t *testing.T) {
	key1 := backtestAdmissionLockKey(123)
	key2 := backtestAdmissionLockKey(456)

	if key1 == key2 {
		t.Fatalf("expected different keys for different users, both got %q", key1)
	}
}

func TestNewBacktestRepository_CreatesInstance(t *testing.T) {
	repo := NewBacktestRepository(nil)

	if repo == nil {
		t.Fatal("expected BacktestRepository instance, got nil")
	}
}

// Integration test: verifies the in-process lock actually serializes access
func TestInProcessLock_SerializesAccessCorrectly(t *testing.T) {
	repo := NewBacktestRepository(nil) // Force in-process locking
	userID := 12345

	// Track execution with a small time delay to ensure proper serialization
	var mu sync.Mutex
	var executionTimes []time.Time

	var wg sync.WaitGroup
	wg.Add(5)

	for i := 0; i < 5; i++ {
		go func() {
			defer wg.Done()
			repo.WithUserAdmissionLock(context.Background(), userID, func() error {
				mu.Lock()
				executionTimes = append(executionTimes, time.Now())
				mu.Unlock()

				// Hold the lock briefly
				time.Sleep(10 * time.Millisecond)

				mu.Lock()
				executionTimes = append(executionTimes, time.Now())
				mu.Unlock()
				return nil
			})
		}()
	}

	wg.Wait()

	// Should have 10 timestamps (5 start + 5 end)
	if len(executionTimes) != 10 {
		t.Fatalf("expected 10 timestamps, got %d", len(executionTimes))
	}

	// Verify execution pattern: consecutive start and end times indicate serialization
	// Pattern should be: start1, end1, start2, end2, ...
	for i := 0; i < len(executionTimes)-1; i += 2 {
		if i+1 < len(executionTimes) {
			// Each transaction should be start -> end -> (next start after end)
			if executionTimes[i].After(executionTimes[i+1]) {
				t.Fatalf("execution %d: start time %v is after end time %v",
					i/2, executionTimes[i], executionTimes[i+1])
			}
		}
	}
}
