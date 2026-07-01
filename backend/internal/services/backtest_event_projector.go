package services

import (
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/nats"
)

// Backtest event contract (Phase 2).
//
// These are the canonical durable lifecycle/progress events a backtest worker
// emits to JetStream, and that a backend projector consumes to drive the
// user-facing push feed. Subjects use the singular owner.kind.action form
// (backtest.event.<action>) matching backend/internal/nats Subject() and the
// Python consumer's BACKTEST_EVENTS stream (backtest.event.>).
//
// This file defines the contract + a projector. Wiring the projector to a live
// JetStream subscribe loop is the JetStream-primary cutover, which the plan
// gates until the end-to-end path is proven in staging.
const (
	BacktestEventActionStarted   = "started"
	BacktestEventActionProgress  = "progress"
	BacktestEventActionCompleted = "completed"
	BacktestEventActionFailed    = "failed"
)

// BacktestEventSubject returns the canonical JetStream subject for a backtest
// event action, e.g. BacktestEventSubject("completed") -> "backtest.event.completed".
func BacktestEventSubject(action string) string {
	return "backtest.event." + strings.Trim(action, ".")
}

// BacktestEvent is the typed payload carried inside a JetStream envelope's
// Payload field for a backtest lifecycle/progress event.
type BacktestEvent struct {
	RunID        string    `json:"run_id"`
	Event        string    `json:"event"` // one of BacktestEventAction*
	Progress     float64   `json:"progress,omitempty"`
	Phase        string    `json:"phase,omitempty"`
	CurrentPair  string    `json:"current_pair,omitempty"`
	ErrorCode    string    `json:"error_code,omitempty"`
	ErrorMessage string    `json:"error_message,omitempty"`
	OccurredAt   time.Time `json:"occurred_at"`
}

// Validate enforces the contract so a projector can never broadcast a malformed
// or ambiguous event to clients.
func (e BacktestEvent) Validate() error {
	if strings.TrimSpace(e.RunID) == "" {
		return errors.New("backtest event: run_id is required")
	}
	switch e.Event {
	case BacktestEventActionStarted, BacktestEventActionProgress,
		BacktestEventActionCompleted, BacktestEventActionFailed:
	default:
		return fmt.Errorf("backtest event: unknown event %q", e.Event)
	}
	if e.OccurredAt.IsZero() {
		return errors.New("backtest event: occurred_at is required")
	}
	if e.Progress < 0 || e.Progress > 100 {
		return fmt.Errorf("backtest event: progress %v out of range [0,100]", e.Progress)
	}
	if e.Event == BacktestEventActionFailed && strings.TrimSpace(e.ErrorCode) == "" {
		return errors.New("backtest event: error_code is required for failed events")
	}
	return nil
}

// Broadcaster is the projection target: something that can push a payload to
// subscribers for a run. *BacktestPushHub satisfies it; tests inject a fake.
type Broadcaster interface {
	Broadcast(runID string, payload []byte)
}

// BacktestEventProjector validates a backtest event, marshals it, and broadcasts
// it to the user-facing push feed. It is the durable-event replacement for the
// Redis pub/sub status path; the JetStream subscribe loop that feeds it is the
// gated cutover step.
type BacktestEventProjector struct {
	hub Broadcaster
}

// NewBacktestEventProjector returns nil when hub is nil so callers can treat a
// disabled projector as a no-op (fail-closed construction).
func NewBacktestEventProjector(hub Broadcaster) *BacktestEventProjector {
	if hub == nil {
		return nil
	}
	return &BacktestEventProjector{hub: hub}
}

// Project validates the event and broadcasts its JSON to the run's subscribers.
// Returns an error and broadcasts nothing if the event is invalid.
func (p *BacktestEventProjector) Project(evt BacktestEvent) error {
	if p == nil {
		return errors.New("backtest event projector: nil projector")
	}
	if err := evt.Validate(); err != nil {
		return err
	}
	payload, err := json.Marshal(evt)
	if err != nil {
		return fmt.Errorf("backtest event projector: marshal: %w", err)
	}
	p.hub.Broadcast(evt.RunID, payload)
	return nil
}

// ProcessEnvelope is the per-message core a JetStream event consumer calls. It
// validates the wire envelope, decodes the BacktestEvent from its Payload, and
// projects it to the push feed. The long-running subscribe loop that feeds this
// is the JetStream-primary cutover (plan-gated); this method is the tested,
// reusable projection step.
func (p *BacktestEventProjector) ProcessEnvelope(env nats.Envelope) error {
	if p == nil {
		return errors.New("backtest event projector: nil projector")
	}
	if err := env.Validate(); err != nil {
		return fmt.Errorf("backtest event projector: invalid envelope: %w", err)
	}
	if len(env.Payload) == 0 {
		return errors.New("backtest event projector: empty payload")
	}
	var evt BacktestEvent
	if err := json.Unmarshal(env.Payload, &evt); err != nil {
		return fmt.Errorf("backtest event projector: decode payload: %w", err)
	}
	// The envelope's owner_id is the authoritative run id; prefer it when the
	// payload did not carry one (defensive against producers that omit run_id).
	if strings.TrimSpace(evt.RunID) == "" {
		evt.RunID = env.OwnerID
	}
	return p.Project(evt)
}
