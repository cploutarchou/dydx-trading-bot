//go:build integration

// Real-NATS integration test for the backend backtest event consumer.
//
// Proves the Phase 2 consume side end to end: a durable backtest event is
// published to BACKTEST_EVENTS, the consumer's Run loop fetches it, decodes the
// envelope, and projects it to the push feed. Runs against a live NATS server:
//
//	NATS_TEST_URL=nats://localhost:4222 \
//	  go test -tags=integration ./internal/services/ -run TestBacktestEventConsumerIntegration -v
package services

import (
	"context"
	"encoding/json"
	"os"
	"testing"
	"time"

	natsclient "github.com/nats-io/nats.go"
)

func TestBacktestEventConsumerIntegration_FetchAndProject(t *testing.T) {
	url := os.Getenv("NATS_TEST_URL")
	if url == "" {
		url = "nats://localhost:4222"
	}
	conn, err := natsclient.Connect(url, natsclient.Timeout(3*time.Second))
	if err != nil {
		t.Skipf("NATS unavailable at %s: %v", url, err)
	}
	defer conn.Close()
	js, err := conn.JetStream()
	if err != nil {
		t.Fatalf("JetStream context: %v", err)
	}

	// Clean slate: drop the stream (and any prior consumer) so the test is
	// independent of other runs.
	_ = js.DeleteConsumer(backtestEventStreamName, "it-event-projector")
	_ = js.DeleteStream(backtestEventStreamName)

	hub := &fakeBroadcaster{}
	projector := NewBacktestEventProjector(hub)
	consumer := newBacktestEventConsumer(url, projector, "it-event-projector")
	if consumer == nil {
		t.Fatal("expected non-nil consumer")
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	done := make(chan struct{})
	go func() {
		_ = consumer.Run(ctx)
		close(done)
	}()

	// Publish a canonical completed event (mirrors the bot emitter shape).
	evt := BacktestEvent{
		RunID: "run-it-1", Event: BacktestEventActionCompleted, Progress: 100,
		OccurredAt: time.Now().UTC(),
	}
	envelope := map[string]any{
		"message_id":       "evt-it-1",
		"idempotency_key":  "evt-it-1",
		"correlation_id":   "trace-it-1",
		"owner_type":       "backtest",
		"owner_id":         "run-it-1",
		"occurred_at":      evt.OccurredAt.Format(time.RFC3339Nano),
		"producer_service": "bot-worker",
		"schema_version":   "1",
		"subject":          "backtest.event.completed",
		"payload":          evt,
	}
	data, _ := json.Marshal(envelope)

	// Give the consumer a moment to ensure the stream + subscribe, then publish.
	// (ensureEventStream is idempotent, so this is race-safe.)
	time.Sleep(300 * time.Millisecond)
	if _, err := js.Publish("backtest.event.completed", data, natsclient.MsgId("evt-it-1")); err != nil {
		t.Fatalf("publish event: %v", err)
	}

	// Wait for the projection to land on the push feed.
	deadline := time.Now().Add(4 * time.Second)
	for time.Now().Before(deadline) && len(hub.calls) == 0 {
		time.Sleep(25 * time.Millisecond)
	}
	cancel()
	<-done

	if len(hub.calls) != 1 {
		t.Fatalf("expected 1 broadcast, got %d", len(hub.calls))
	}
	if hub.calls[0].runID != "run-it-1" {
		t.Fatalf("expected broadcast for run-it-1, got %q", hub.calls[0].runID)
	}
	var got BacktestEvent
	if err := json.Unmarshal(hub.calls[0].payload, &got); err != nil {
		t.Fatalf("broadcast payload not a BacktestEvent: %v", err)
	}
	if got.Event != BacktestEventActionCompleted {
		t.Fatalf("expected completed event, got %q", got.Event)
	}

	// Cleanup.
	_ = js.DeleteConsumer(backtestEventStreamName, "it-event-projector")
	_ = js.DeleteStream(backtestEventStreamName)
}
