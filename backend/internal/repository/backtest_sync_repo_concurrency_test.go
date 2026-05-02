package repository

import (
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func TestBacktestSyncRepository_WithRunLockSerializesSameRunID(t *testing.T) {
	repo := &BacktestSyncRepository{}

	var concurrent int32
	var maxConcurrent int32

	const goroutines = 12
	var wg sync.WaitGroup
	wg.Add(goroutines)

	for i := 0; i < goroutines; i++ {
		go func() {
			defer wg.Done()
			err := repo.withRunLock("run-123", func() error {
				current := atomic.AddInt32(&concurrent, 1)
				for {
					prev := atomic.LoadInt32(&maxConcurrent)
					if current <= prev || atomic.CompareAndSwapInt32(&maxConcurrent, prev, current) {
						break
					}
				}
				time.Sleep(5 * time.Millisecond)
				atomic.AddInt32(&concurrent, -1)
				return nil
			})
			if err != nil {
				t.Errorf("withRunLock returned error: %v", err)
			}
		}()
	}

	wg.Wait()
	if got := atomic.LoadInt32(&maxConcurrent); got != 1 {
		t.Fatalf("expected max concurrency for same run_id to be 1, got %d", got)
	}
}

func TestBacktestSyncRepository_WithRunLockAllowsDifferentRunIDs(t *testing.T) {
	repo := &BacktestSyncRepository{}

	holdFirst := make(chan struct{})
	firstEntered := make(chan struct{})
	secondEntered := make(chan struct{})

	go func() {
		_ = repo.withRunLock("run-a", func() error {
			close(firstEntered)
			<-holdFirst
			return nil
		})
	}()

	select {
	case <-firstEntered:
	case <-time.After(500 * time.Millisecond):
		t.Fatal("first lock holder did not enter critical section in time")
	}

	go func() {
		_ = repo.withRunLock("run-b", func() error {
			close(secondEntered)
			return nil
		})
	}()

	select {
	case <-secondEntered:
		// expected: different run ids should not block each other
	case <-time.After(500 * time.Millisecond):
		t.Fatal("different run_id lock acquisition blocked unexpectedly")
	}

	close(holdFirst)
}
