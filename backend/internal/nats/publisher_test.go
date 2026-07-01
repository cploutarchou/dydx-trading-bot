package nats

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	nattest "github.com/nats-io/nats-server/v2/test"
	natsclient "github.com/nats-io/nats.go"

	"github.com/dydx-trading-bot/backend-go/config"
)

func TestNewPublisherNilWhenDisabled(t *testing.T) {
	if p := NewPublisher(config.NATSSettings{Enabled: false}); p != nil {
		t.Fatalf("expected nil publisher when disabled, got %+v", p)
	}
}

func TestEnvelopeValidate(t *testing.T) {
	base := Envelope{
		MessageID:      "cmd-1",
		IdempotencyKey: "idem-1",
		CorrelationID:  "corr-1",
		Subject:        Subject("bot", "command", "start"),
		OccurredAt:     time.Now().UTC(),
	}
	if err := base.Validate(); err != nil {
		t.Fatalf("valid envelope rejected: %v", err)
	}
	for _, mutate := range []func(*Envelope){
		func(e *Envelope) { e.MessageID = "" },
		func(e *Envelope) { e.IdempotencyKey = "  " },
		func(e *Envelope) { e.CorrelationID = "" },
		func(e *Envelope) { e.Subject = "" },
		func(e *Envelope) { e.OccurredAt = time.Time{} },
	} {
		clone := base
		mutate(&clone)
		if err := clone.Validate(); err == nil {
			t.Fatalf("expected validation error after mutation, got nil")
		}
	}
}

func TestSubjectAndStreamMapping(t *testing.T) {
	cases := []struct {
		subject string
		stream  string
	}{
		{Subject("bot", "command", "start"), StreamBotCommands},
		{Subject("bot", "event", "trade_opened"), StreamBotEvents},
		{Subject("backtest", "command", "cancel"), StreamBacktestCommands},
		{Subject("backtest", "event", "completed"), StreamBacktestEvents},
	}
	for _, c := range cases {
		if got := StreamFor(c.subject); got != c.stream {
			t.Fatalf("StreamFor(%q) = %q, want %q", c.subject, got, c.stream)
		}
	}
	if got := Subject("bot", "command", "start"); got != "bot.command.start" {
		t.Fatalf("unexpected subject: %q", got)
	}
	if got := StreamFor("unknown.thing.x"); got != "" {
		t.Fatalf("expected empty stream for unknown subject, got %q", got)
	}
}

func TestEnvelopeMarshalShape(t *testing.T) {
	payload, _ := json.Marshal(map[string]string{"run_id": "run-123"})
	env := Envelope{
		MessageID:       "evt-1",
		IdempotencyKey:  "idem-1",
		CorrelationID:   "corr-1",
		CausationID:     "cause-1",
		OwnerType:       "backtest",
		OwnerID:         "run-123",
		OccurredAt:      time.Date(2026, 6, 28, 21, 5, 0, 0, time.UTC),
		ProducerService: "backend-api",
		SchemaVersion:   DefaultSchemaVersion,
		Subject:         Subject("backtest", "event", "completed"),
		Payload:         payload,
	}
	raw, err := json.Marshal(env)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	var decoded map[string]json.RawMessage
	if err := json.Unmarshal(raw, &decoded); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	for _, key := range []string{"message_id", "idempotency_key", "correlation_id", "owner_type", "owner_id", "occurred_at", "producer_service", "schema_version", "subject", "payload"} {
		if _, ok := decoded[key]; !ok {
			t.Fatalf("envelope missing required field %q in JSON: %s", key, raw)
		}
	}
	var payloadMap map[string]string
	if err := json.Unmarshal(decoded["payload"], &payloadMap); err != nil || payloadMap["run_id"] != "run-123" {
		t.Fatalf("payload did not round-trip: %s", decoded["payload"])
	}
}

// runJetStream starts an in-process NATS server with JetStream enabled on a
// random port so publish/ack behavior is validated against a real bus, not a
// mock. The contract explicitly forbids silently dropping commands, so this is
// the strongest honest check that the publisher actually publishes. It returns
// the client URL the publisher should dial.
func runJetStream(t *testing.T) string {
	t.Helper()
	opts := nattest.DefaultTestOptions
	opts.Port = -1
	opts.JetStream = true
	// Unique store dir per test so JetStream file storage never leaks messages
	// (and thus dedupe state) across tests or across repeated runs.
	opts.StoreDir = t.TempDir()
	server := nattest.RunServer(&opts)
	t.Cleanup(server.Shutdown)
	return server.ClientURL()
}

func newEnvelope(id, subject string) Envelope {
	return Envelope{
		MessageID:       id,
		IdempotencyKey:  id, // reuse as the dedupe key for a deterministic test
		CorrelationID:   "corr-" + id,
		OwnerType:       "bot",
		OwnerID:         "bot-1",
		OccurredAt:      time.Now().UTC(),
		ProducerService: "backend-api",
		SchemaVersion:   DefaultSchemaVersion,
		Subject:         subject,
		Payload:         json.RawMessage(`{"action":"start"}`),
	}
}

func TestPublisherPublishAckAndDedupe(t *testing.T) {
	url := runJetStream(t)
	pub := NewPublisher(config.NATSSettings{Enabled: true, URL: url})
	if pub == nil {
		t.Fatalf("expected non-nil publisher")
	}
	t.Cleanup(pub.Close)

	subject := Subject("bot", "command", "start")
	env := newEnvelope("cmd-start-1", subject)

	res, err := pub.Publish(context.Background(), env)
	if err != nil {
		t.Fatalf("Publish: %v", err)
	}
	if res.Stream != StreamBotCommands {
		t.Fatalf("expected ack stream %q, got %q", StreamBotCommands, res.Stream)
	}
	if res.Sequence == 0 {
		t.Fatalf("expected non-zero sequence, got %d", res.Sequence)
	}
	if res.Duplicate {
		t.Fatalf("first publish must not be a duplicate")
	}

	// Same idempotency key again: JetStream must report Duplicate=true and not
	// enqueue a second command.
	res2, err := pub.Publish(context.Background(), newEnvelope("cmd-start-1", subject))
	if err != nil {
		t.Fatalf("dedupe Publish: %v", err)
	}
	if !res2.Duplicate {
		t.Fatalf("expected duplicate ack for repeated idempotency key, got %+v", res2)
	}
}

func TestPublisherPublishDeliversPayload(t *testing.T) {
	url := runJetStream(t)
	pub := NewPublisher(config.NATSSettings{Enabled: true, URL: url})
	t.Cleanup(pub.Close)

	// A second, independent connection subscribes to verify the exact payload
	// that lands on the bus — proving the envelope (not a stub) is delivered.
	nc, err := natsclient.Connect(url)
	if err != nil {
		t.Fatalf("verify conn: %v", err)
	}
	t.Cleanup(nc.Close)
	js, err := nc.JetStream()
	if err != nil {
		t.Fatalf("verify js: %v", err)
	}

	env := newEnvelope("evt-completed-1", Subject("backtest", "event", "completed"))
	// Publish first so the publisher lazily provisions the covering stream, then
	// subscribe. An ephemeral pull consumer defaults to delivering all stored
	// messages, so a subscriber created after the publish still receives it.
	if _, err := pub.Publish(context.Background(), env); err != nil {
		t.Fatalf("Publish: %v", err)
	}

	sub, err := js.PullSubscribe(Subject("backtest", "event", "completed"), "")
	if err != nil {
		t.Fatalf("PullSubscribe: %v", err)
	}
	msgs, err := sub.Fetch(1, natsclient.MaxWait(2*time.Second))
	if err != nil {
		t.Fatalf("Fetch: %v", err)
	}
	if len(msgs) != 1 {
		t.Fatalf("expected 1 delivered message, got %d", len(msgs))
	}
	var got Envelope
	if err := json.Unmarshal(msgs[0].Data, &got); err != nil {
		t.Fatalf("unmarshal delivered envelope: %v", err)
	}
	if got.MessageID != env.MessageID || got.Subject != env.Subject {
		t.Fatalf("delivered envelope mismatch: %+v", got)
	}
}

func TestPublisherPublishUnreachableFailsClosed(t *testing.T) {
	// Point at a port with nothing listening. The lazy dial must fail fast and
	// Publish must return an error rather than hang, panic, or silently succeed.
	pub := NewPublisher(config.NATSSettings{Enabled: true, URL: "nats://127.0.0.1:1"})
	if pub == nil {
		t.Fatalf("expected non-nil publisher")
	}
	t.Cleanup(pub.Close)

	_, err := pub.Publish(context.Background(), newEnvelope("cmd-x", Subject("bot", "command", "start")))
	if err == nil {
		t.Fatalf("expected error publishing to unreachable bus, got nil")
	}
}

func TestNilPublisherPublishFailsClosed(t *testing.T) {
	var pub *Publisher
	if _, err := pub.Publish(context.Background(), newEnvelope("cmd-x", Subject("bot", "command", "start"))); err != ErrPublisherDisabled {
		t.Fatalf("expected ErrPublisherDisabled, got %v", err)
	}
}
