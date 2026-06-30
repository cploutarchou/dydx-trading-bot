package services

import (
	"encoding/json"
	"strings"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/nats"
)

// fakeBroadcaster records every Broadcast call for assertions.
type fakeBroadcaster struct {
	calls []broadcastCall
}

type broadcastCall struct {
	runID   string
	payload []byte
}

func (f *fakeBroadcaster) Broadcast(runID string, payload []byte) {
	f.calls = append(f.calls, broadcastCall{runID: runID, payload: payload})
}

func validEvent(event string) BacktestEvent {
	evt := BacktestEvent{
		RunID:      "run-1",
		Event:      event,
		OccurredAt: time.Date(2026, 6, 30, 12, 0, 0, 0, time.UTC),
	}
	if event == BacktestEventActionFailed {
		evt.ErrorCode = "BACKTEST_FAILED"
	}
	return evt
}

func TestBacktestEventProjector_ProjectProgress(t *testing.T) {
	hub := &fakeBroadcaster{}
	p := NewBacktestEventProjector(hub)

	evt := validEvent(BacktestEventActionProgress)
	evt.Progress = 42.5
	evt.Phase = "backtest"
	evt.CurrentPair = "BTC-USD"

	if err := p.Project(evt); err != nil {
		t.Fatalf("Project: %v", err)
	}
	if len(hub.calls) != 1 {
		t.Fatalf("expected 1 broadcast, got %d", len(hub.calls))
	}
	if hub.calls[0].runID != "run-1" {
		t.Fatalf("expected broadcast for run-1, got %q", hub.calls[0].runID)
	}

	var got BacktestEvent
	if err := json.Unmarshal(hub.calls[0].payload, &got); err != nil {
		t.Fatalf("broadcast payload not a BacktestEvent: %v", err)
	}
	if got.Progress != 42.5 || got.CurrentPair != "BTC-USD" || got.Event != "progress" {
		t.Fatalf("unexpected payload: %+v", got)
	}
}

func TestBacktestEventProjector_ProjectCompleted(t *testing.T) {
	hub := &fakeBroadcaster{}
	p := NewBacktestEventProjector(hub)

	evt := validEvent(BacktestEventActionCompleted)
	evt.Progress = 100
	if err := p.Project(evt); err != nil {
		t.Fatalf("Project: %v", err)
	}
	var got BacktestEvent
	_ = json.Unmarshal(hub.calls[0].payload, &got)
	if got.Event != "completed" || got.Progress != 100 {
		t.Fatalf("unexpected completed payload: %+v", got)
	}
}

func TestBacktestEventProjector_ProjectFailedRequiresErrorCode(t *testing.T) {
	hub := &fakeBroadcaster{}
	p := NewBacktestEventProjector(hub)

	// failed event without error_code is invalid -> no broadcast.
	evt := validEvent(BacktestEventActionFailed)
	evt.ErrorCode = ""
	if err := p.Project(evt); err == nil {
		t.Fatal("expected error for failed event without error_code")
	}
	if len(hub.calls) != 0 {
		t.Fatalf("expected no broadcast on invalid event, got %d", len(hub.calls))
	}

	// With error_code it projects.
	evt.ErrorCode = "BACKTEST_TIMEOUT"
	evt.ErrorMessage = "soft time limit"
	if err := p.Project(evt); err != nil {
		t.Fatalf("Project: %v", err)
	}
	var got BacktestEvent
	_ = json.Unmarshal(hub.calls[0].payload, &got)
	if got.ErrorCode != "BACKTEST_TIMEOUT" {
		t.Fatalf("expected error_code preserved, got %+v", got)
	}
}

func TestBacktestEventProjector_InvalidEventsAreRejected(t *testing.T) {
	hub := &fakeBroadcaster{}
	p := NewBacktestEventProjector(hub)

	cases := []BacktestEvent{
		{Event: BacktestEventActionStarted, OccurredAt: time.Now()},                                 // missing run_id
		{RunID: "run-1", Event: "unknown", OccurredAt: time.Now()},                                  // bad event
		{RunID: "run-1", Event: BacktestEventActionProgress, Progress: 150, OccurredAt: time.Now()}, // progress > 100
		{RunID: "run-1", Event: BacktestEventActionProgress, Progress: -1, OccurredAt: time.Now()},  // progress < 0
		{RunID: "run-1", Event: BacktestEventActionStarted},                                         // zero occurred_at
	}
	for i, evt := range cases {
		if err := p.Project(evt); err == nil {
			t.Fatalf("case %d: expected validation error for %+v", i, evt)
		}
	}
	if len(hub.calls) != 0 {
		t.Fatalf("expected zero broadcasts for invalid events, got %d", len(hub.calls))
	}
}

func TestBacktestEventProjector_NilIsNoop(t *testing.T) {
	var p *BacktestEventProjector
	if err := p.Project(validEvent(BacktestEventActionStarted)); err == nil {
		t.Fatal("expected error projecting on nil projector")
	}
	if NewBacktestEventProjector(nil) != nil {
		t.Fatal("NewBacktestEventProjector(nil) should return nil")
	}
}

func TestBacktestEventSubject(t *testing.T) {
	if got := BacktestEventSubject("completed"); got != "backtest.event.completed" {
		t.Fatalf("expected backtest.event.completed, got %q", got)
	}
	// Trims stray dots so a caller cannot build a malformed subject.
	if strings.Contains(BacktestEventSubject(".progress."), "..") {
		t.Fatal("subject must not contain double dots")
	}
}

// validEnvelope wraps a BacktestEvent payload in a valid wire envelope.
func validEnvelope(evt BacktestEvent, ownerID string) nats.Envelope {
	payload, _ := json.Marshal(evt)
	return nats.Envelope{
		MessageID:       "evt-msg",
		IdempotencyKey:  "evt-msg",
		CorrelationID:   "trace",
		OwnerType:       "backtest",
		OwnerID:         ownerID,
		OccurredAt:      evt.OccurredAt,
		ProducerService: "backend-api",
		SchemaVersion:   nats.DefaultSchemaVersion,
		Subject:         BacktestEventSubject(evt.Event),
		Payload:         payload,
	}
}

func TestBacktestEventProjector_ProcessEnvelope_HappyPath(t *testing.T) {
	hub := &fakeBroadcaster{}
	p := NewBacktestEventProjector(hub)
	evt := validEvent(BacktestEventActionCompleted)
	evt.Progress = 100
	evt.RunID = "run-env-1"

	if err := p.ProcessEnvelope(validEnvelope(evt, "run-env-1")); err != nil {
		t.Fatalf("ProcessEnvelope: %v", err)
	}
	if len(hub.calls) != 1 || hub.calls[0].runID != "run-env-1" {
		t.Fatalf("expected one broadcast for run-env-1, got %+v", hub.calls)
	}
}

func TestBacktestEventProjector_ProcessEnvelope_RunIDFallsBackToOwner(t *testing.T) {
	hub := &fakeBroadcaster{}
	p := NewBacktestEventProjector(hub)
	// Payload omits run_id; the envelope owner_id must be used instead.
	evt := validEvent(BacktestEventActionStarted)
	evt.RunID = ""
	env := validEnvelope(evt, "run-owner-1")
	// Force payload to actually omit run_id (validEnvelope marshals evt with empty run_id).
	if err := p.ProcessEnvelope(env); err != nil {
		t.Fatalf("ProcessEnvelope: %v", err)
	}
	if hub.calls[0].runID != "run-owner-1" {
		t.Fatalf("expected run_id fallback to owner_id run-owner-1, got %q", hub.calls[0].runID)
	}
}

func TestBacktestEventProjector_ProcessEnvelope_RejectsBadInput(t *testing.T) {
	hub := &fakeBroadcaster{}
	p := NewBacktestEventProjector(hub)

	// Empty payload.
	goodEvt := validEvent(BacktestEventActionStarted)
	emptyPayload := validEnvelope(goodEvt, "run-1")
	emptyPayload.Payload = nil
	if err := p.ProcessEnvelope(emptyPayload); err == nil {
		t.Fatal("expected error for empty payload")
	}

	// Invalid envelope (missing required fields).
	if err := p.ProcessEnvelope(nats.Envelope{Payload: []byte(`{}`)}); err == nil {
		t.Fatal("expected error for invalid envelope")
	}

	// Payload that decodes to an invalid event (bad event action).
	badEnv := validEnvelope(BacktestEvent{RunID: "r", Event: "bogus", OccurredAt: time.Now()}, "r")
	if err := p.ProcessEnvelope(badEnv); err == nil {
		t.Fatal("expected error for invalid event payload")
	}

	if len(hub.calls) != 0 {
		t.Fatalf("expected no broadcasts for rejected envelopes, got %d", len(hub.calls))
	}
}
