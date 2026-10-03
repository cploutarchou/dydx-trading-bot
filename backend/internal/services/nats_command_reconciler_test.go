package services

import (
	"context"
	"encoding/json"
	"sync"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/nats"
)

// pendingStore returns a fixed set of pending commands to the reconciler.
type pendingStore struct {
	*fakeTaskStore
	pending []*models.TaskCommand
}

func (p *pendingStore) ListTaskCommandsPendingSince(_ context.Context, _ time.Time, _ int) ([]*models.TaskCommand, error) {
	return p.pending, nil
}

// recordingPublisher keeps every envelope it is asked to publish.
type recordingPublisher struct {
	mu        sync.Mutex
	envelopes []nats.Envelope
}

func (r *recordingPublisher) Publish(_ context.Context, env nats.Envelope) (*nats.PublishResult, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.envelopes = append(r.envelopes, env)
	return &nats.PublishResult{}, nil
}

func newReconcilerFixture(payloadJSON []byte) (*NATSCommandService, *pendingStore, *recordingPublisher) {
	store := &pendingStore{
		fakeTaskStore: &fakeTaskStore{},
		pending: []*models.TaskCommand{{
			ID:             "cmd-123",
			CommandType:    "backtest",
			OwnerType:      "backtest",
			OwnerID:        "run-42",
			IdempotencyKey: "idem-42",
			Status:         "pending",
			PayloadJSON:    payloadJSON,
			CreatedAt:      time.Date(2026, 9, 1, 12, 0, 0, 0, time.UTC),
		}},
	}
	pub := &recordingPublisher{}
	svc := &NATSCommandService{
		taskRepo:  store,
		publisher: pub,
		settings:  config.NATSSettings{Enabled: true, CommandBusEnabled: true},
		clock:     time.Now,
	}
	return svc, store, pub
}

// The reconciler used to build an envelope without a correlation id, which
// Envelope.Validate rejects, so no pending command was ever re-published.
func TestReconcilePendingCommands_RepublishesValidEnvelope(t *testing.T) {
	svc, store, pub := newReconcilerFixture([]byte(`{"name":"nightly","strategy_id":7,"pairs":["BTC-USD"]}`))

	requeued, err := svc.ReconcilePendingCommands(context.Background(), time.Minute, 10)
	if err != nil {
		t.Fatalf("ReconcilePendingCommands: %v", err)
	}
	if requeued != 1 {
		t.Fatalf("requeued = %d, want 1", requeued)
	}
	if len(pub.envelopes) != 1 {
		t.Fatalf("published %d envelopes, want 1", len(pub.envelopes))
	}
	env := pub.envelopes[0]
	if err := env.Validate(); err != nil {
		t.Fatalf("re-published envelope is invalid: %v", err)
	}
	if env.CorrelationID != "cmd-123" || env.IdempotencyKey != "idem-42" || env.MessageID != "cmd-123" {
		t.Fatalf("unexpected envelope identity: %+v", env)
	}
	if !store.hasPublished() {
		t.Fatal("command was not marked published after a successful re-publish")
	}
}

// The consumer resolves the run from the message body, so a re-publish must
// carry the same reference fields as the first publish, not the stored config.
func TestReconcilePendingCommands_PayloadMatchesFirstPublishShape(t *testing.T) {
	svc, _, pub := newReconcilerFixture([]byte(`{"name":"nightly","strategy_id":7,"pairs":["BTC-USD"]}`))

	if _, err := svc.ReconcilePendingCommands(context.Background(), time.Minute, 10); err != nil {
		t.Fatalf("ReconcilePendingCommands: %v", err)
	}
	if len(pub.envelopes) != 1 {
		t.Fatalf("published %d envelopes, want 1", len(pub.envelopes))
	}

	var body map[string]interface{}
	if err := json.Unmarshal(pub.envelopes[0].Payload, &body); err != nil {
		t.Fatalf("payload is not JSON: %v", err)
	}
	want := map[string]interface{}{
		"command_id":      "cmd-123",
		"run_id":          "run-42",
		"owner_id":        "run-42",
		"owner_type":      "backtest",
		"command_type":    "backtest",
		"idempotency_key": "idem-42",
		"name":            "nightly",
		"strategy_id":     float64(7),
	}
	for key, value := range want {
		if body[key] != value {
			t.Errorf("payload[%q] = %v, want %v", key, body[key], value)
		}
	}
	if _, leaked := body["pairs"]; leaked {
		t.Error("payload must stay reference-only; the stored config leaked into the message")
	}
}

func TestReconcilePendingCommands_UnparseableStoredConfigStillRepublishes(t *testing.T) {
	svc, _, pub := newReconcilerFixture([]byte(`not-json`))

	requeued, err := svc.ReconcilePendingCommands(context.Background(), time.Minute, 10)
	if err != nil {
		t.Fatalf("ReconcilePendingCommands: %v", err)
	}
	if requeued != 1 || len(pub.envelopes) != 1 {
		t.Fatalf("requeued=%d published=%d, want 1/1", requeued, len(pub.envelopes))
	}
	var body map[string]interface{}
	if err := json.Unmarshal(pub.envelopes[0].Payload, &body); err != nil {
		t.Fatalf("payload is not JSON: %v", err)
	}
	if body["run_id"] != "run-42" {
		t.Fatalf("run_id = %v, want run-42", body["run_id"])
	}
}
