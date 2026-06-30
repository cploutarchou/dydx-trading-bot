//go:build integration

// Real-NATS integration test for the durable backtest event projection pipeline.
//
// Proves the Phase 2 read-side path end to end against a live NATS server:
// publish a backtest.event.completed envelope -> fetch it from JetStream ->
// ProcessEnvelope decodes + validates + broadcasts to the push feed. The
// long-running subscribe loop that feeds ProcessEnvelope in production is the
// JetStream-primary cutover (plan-gated); this test exercises the per-message
// projection step against the real transport.
//
//	NATS_TEST_URL=nats://localhost:4222 \
//	  go test -tags=integration ./internal/services/ -run TestBacktestEventProjectorIntegration -v
package services

import (
	"context"
	"encoding/json"
	"os"
	"testing"
	"time"

	natsclient "github.com/nats-io/nats.go"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/nats"
)

func TestBacktestEventProjectorIntegration_PublishConsumeProject(t *testing.T) {
	url := os.Getenv("NATS_TEST_URL")
	if url == "" {
		url = "nats://localhost:4222"
	}
	verifyConn, err := natsclient.Connect(url, natsclient.Timeout(3*time.Second))
	if err != nil {
		t.Skipf("NATS unavailable at %s: %v", url, err)
	}
	defer verifyConn.Close()
	verifyJS, err := verifyConn.JetStream()
	if err != nil {
		t.Fatalf("JetStream context: %v", err)
	}
	_ = verifyJS.DeleteStream(nats.StreamBacktestEvents) // clean slate

	pub := nats.NewPublisher(config.NATSSettings{Enabled: true, URL: url})
	if pub == nil {
		t.Fatal("expected non-nil publisher")
	}
	defer pub.Close()

	// Build a canonical completed event as the envelope payload.
	evt := BacktestEvent{
		RunID:      "run-evt-1",
		Event:      BacktestEventActionCompleted,
		Progress:   100,
		OccurredAt: time.Date(2026, 6, 30, 12, 0, 0, 0, time.UTC),
	}
	payload, err := json.Marshal(evt)
	if err != nil {
		t.Fatalf("marshal event: %v", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	res, err := pub.Publish(ctx, nats.Envelope{
		MessageID:       "evt-1",
		IdempotencyKey:  "evt-1",
		CorrelationID:   "trace-evt-1",
		OwnerType:       "backtest",
		OwnerID:         "run-evt-1",
		OccurredAt:      evt.OccurredAt,
		ProducerService: "backend-api",
		SchemaVersion:   nats.DefaultSchemaVersion,
		Subject:         nats.Subject("backtest", "event", "completed"),
		Payload:         payload,
	})
	if err != nil {
		t.Fatalf("Publish event: %v", err)
	}
	if res.Stream != nats.StreamBacktestEvents {
		t.Fatalf("expected stream %s, got %s", nats.StreamBacktestEvents, res.Stream)
	}

	// Fetch the exact message back by sequence.
	msg, err := verifyJS.GetMsg(res.Stream, res.Sequence)
	if err != nil {
		t.Fatalf("GetMsg: %v", err)
	}
	if msg.Subject != "backtest.event.completed" {
		t.Fatalf("expected subject backtest.event.completed, got %q", msg.Subject)
	}

	// Decode the wire envelope and project it.
	var env nats.Envelope
	if err := json.Unmarshal(msg.Data, &env); err != nil {
		t.Fatalf("unmarshal envelope: %v", err)
	}
	hub := &fakeBroadcaster{}
	projector := NewBacktestEventProjector(hub)
	if err := projector.ProcessEnvelope(env); err != nil {
		t.Fatalf("ProcessEnvelope: %v", err)
	}

	if len(hub.calls) != 1 {
		t.Fatalf("expected 1 broadcast, got %d", len(hub.calls))
	}
	if hub.calls[0].runID != "run-evt-1" {
		t.Fatalf("expected broadcast for run-evt-1, got %q", hub.calls[0].runID)
	}
	var got BacktestEvent
	if err := json.Unmarshal(hub.calls[0].payload, &got); err != nil {
		t.Fatalf("broadcast payload not a BacktestEvent: %v", err)
	}
	if got.Event != BacktestEventActionCompleted || got.Progress != 100 {
		t.Fatalf("unexpected projected event: %+v", got)
	}
}
