package repository

import (
	"context"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func TestBacktestRepository_WithUserAdmissionLockSerializesSameUser(t *testing.T) {
	repo := NewBacktestRepository(nil)

	var concurrent int32
	var maxConcurrent int32

	const workers = 10
	var wg sync.WaitGroup
	wg.Add(workers)

	for i := 0; i < workers; i++ {
		go func() {
			defer wg.Done()
			err := repo.WithUserAdmissionLock(context.Background(), 42, func() error {
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
				t.Errorf("WithUserAdmissionLock returned error: %v", err)
			}
		}()
	}

	wg.Wait()
	if got := atomic.LoadInt32(&maxConcurrent); got != 1 {
		t.Fatalf("expected max concurrency to be 1 for same user, got %d", got)
	}
}

func TestBacktestRepository_WithUserAdmissionLockAllowsDifferentUsers(t *testing.T) {
	repo := NewBacktestRepository(nil)

	holdUserA := make(chan struct{})
	userAEntered := make(chan struct{})
	userBEntered := make(chan struct{})

	go func() {
		_ = repo.WithUserAdmissionLock(context.Background(), 100, func() error {
			close(userAEntered)
			<-holdUserA
			return nil
		})
	}()

	select {
	case <-userAEntered:
	case <-time.After(500 * time.Millisecond):
		t.Fatal("user A did not enter admission lock in time")
	}

	go func() {
		_ = repo.WithUserAdmissionLock(context.Background(), 200, func() error {
			close(userBEntered)
			return nil
		})
	}()

	select {
	case <-userBEntered:
		// expected: different users should proceed concurrently
	case <-time.After(500 * time.Millisecond):
		t.Fatal("different user admission lock was blocked unexpectedly")
	}

	close(holdUserA)
}
