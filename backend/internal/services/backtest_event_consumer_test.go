package services

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/nats"
)

func TestBacktestEventConsumer_ProcessRaw_ProjectsEvent(t *testing.T) {
	hub := &fakeBroadcaster{}
	projector := NewBacktestEventProjector(hub)
	consumer := NewBacktestEventConsumer("nats://localhost:4222", projector)
	if consumer == nil {
		t.Fatal("expected non-nil consumer")
	}

	evt := BacktestEvent{
		RunID: "run-raw-1", Event: BacktestEventActionCompleted, Progress: 100,
		OccurredAt: time.Now().UTC(),
	}
	payload, _ := json.Marshal(evt)
	env := nats.Envelope{
		MessageID: "m1", IdempotencyKey: "m1", CorrelationID: "c", OwnerType: "backtest",
		OwnerID: "run-raw-1", OccurredAt: evt.OccurredAt, ProducerService: "bot-worker",
		SchemaVersion: nats.DefaultSchemaVersion, Subject: BacktestEventSubject("completed"),
		Payload: payload,
	}
	data, _ := json.Marshal(env)

	if err := consumer.ProcessRaw(data); err != nil {
		t.Fatalf("ProcessRaw: %v", err)
	}
	if len(hub.calls) != 1 || hub.calls[0].runID != "run-raw-1" {
		t.Fatalf("expected one broadcast for run-raw-1, got %+v", hub.calls)
	}
}

func TestBacktestEventConsumer_ProcessRaw_RejectsBadInput(t *testing.T) {
	hub := &fakeBroadcaster{}
	consumer := NewBacktestEventConsumer("nats://localhost:4222", NewBacktestEventProjector(hub))

	// Garbage JSON.
	if err := consumer.ProcessRaw([]byte("not json")); err == nil {
		t.Fatal("expected error for garbage JSON")
	}
	// Valid envelope but invalid event payload (missing run_id).
	env, _ := json.Marshal(nats.Envelope{
		MessageID: "m", IdempotencyKey: "m", CorrelationID: "c", Subject: "backtest.event.started",
		OccurredAt: time.Now(), OwnerType: "backtest", OwnerID: "o",
		Payload: json.RawMessage(`{"event":"started"}`), // no run_id, no occurred_at in payload
	})
	if err := consumer.ProcessRaw(env); err == nil {
		t.Fatal("expected error for invalid event payload")
	}
	if len(hub.calls) != 0 {
		t.Fatalf("expected no broadcasts for rejected messages, got %d", len(hub.calls))
	}
}

func TestBacktestEventConsumer_NilWhenProjectorNil(t *testing.T) {
	if NewBacktestEventConsumer("nats://localhost:4222", nil) != nil {
		t.Fatal("expected nil consumer when projector is nil")
	}
}
