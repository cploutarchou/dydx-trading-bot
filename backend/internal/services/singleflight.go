package services

import (
	"fmt"
	"sync"
)

// SingleFlight coalesces concurrent identical calls: the first caller executes
// fn while the rest wait for its result. Cleanup is deferred and panics are
// converted to errors, so a failing fetch can never wedge the key or leave
// waiters blocked forever.
type SingleFlight[T any] struct {
	mu       sync.Mutex
	inFlight map[string]*singleFlightCall[T]
}

type singleFlightCall[T any] struct {
	done  chan struct{}
	value T
	err   error
}

func NewSingleFlight[T any]() *SingleFlight[T] {
	return &SingleFlight[T]{inFlight: make(map[string]*singleFlightCall[T])}
}

// Do executes fn for key, or joins the in-flight execution if one exists.
func (s *SingleFlight[T]) Do(key string, fn func() (T, error)) (T, error) {
	s.mu.Lock()
	if s.inFlight == nil {
		s.inFlight = make(map[string]*singleFlightCall[T])
	}
	if call, ok := s.inFlight[key]; ok {
		s.mu.Unlock()
		<-call.done
		return call.value, call.err
	}

	call := &singleFlightCall[T]{done: make(chan struct{})}
	s.inFlight[key] = call
	s.mu.Unlock()

	defer func() {
		s.mu.Lock()
		delete(s.inFlight, key)
		close(call.done)
		s.mu.Unlock()
	}()

	func() {
		defer func() {
			if r := recover(); r != nil {
				var zero T
				call.value = zero
				call.err = fmt.Errorf("singleflight panic: %v", r)
			}
		}()
		call.value, call.err = fn()
	}()

	return call.value, call.err
}
