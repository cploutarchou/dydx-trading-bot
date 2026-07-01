//go:build integration

// Real NATS integration tests for the backend JetStream publisher.
//
// These produce the Phase 2 pre-cutover evidence the Final Application
// Improvement Plan requires: that a published command lands on the correct
// stream/subject with the idempotency key as the JetStream Msg-Id, that
// duplicate publishes are suppressed, and that transport failure is observable
// (fail-closed). They run only against a live NATS server:
//
//	NATS_TEST_URL=nats://localhost:4222 \
//	  go test -tags=integration ./internal/nats/ -run TestPublisherIntegration -v
//
// Skipped automatically when NATS is unreachable so the normal suite is unaffected.
package nats

import (
	"context"
	"encoding/json"
	"os"
	"strings"
	"testing"
	"time"

	natsclient "github.com/nats-io/nats.go"

	"github.com/dydx-trading-bot/backend-go/config"
)

func testNATSURL(t *testing.T) string {
	t.Helper()
	url := os.Getenv("NATS_TEST_URL")
	if url == "" {
		url = "nats://localhost:4222"
	}
	return url
}

// skipIfNoNATS connects to NATS and skips the test if it is unavailable.
func skipIfNoNATS(t *testing.T, url string) *natsclient.Conn {
	t.Helper()
	conn, err := natsclient.Connect(url, natsclient.Timeout(3*time.Second), natsclient.ReconnectWait(0))
	if err != nil {
		t.Skipf("NATS unavailable at %s: %v (set NATS_TEST_URL to target a server)", url, err)
	}
	return conn
}

// TestPublisherIntegration_RealPublishSubjectAndMsgId proves the publisher
// delivers the command to BACKTEST_COMMANDS on subject backtest.command.start
// with the idempotency key stamped as the JetStream Msg-Id and the authoritative
// command_id/run_id/owner preserved in the envelope.
func TestPublisherIntegration_RealPublishSubjectAndMsgId(t *testing.T) {
	url := testNATSURL(t)
	verifyConn := skipIfNoNATS(t, url)
	defer verifyConn.Close()
	verifyJS, err := verifyConn.JetStream()
	if err != nil {
		t.Fatalf("verify JetStream context: %v", err)
	}
	// Clean slate so prior runs do not interfere with GetMsg by sequence.
	_ = verifyJS.DeleteStream(StreamBacktestCommands)

	pub := NewPublisher(config.NATSSettings{Enabled: true, URL: url})
	if pub == nil {
		t.Fatal("expected non-nil publisher when enabled")
	}
	defer pub.Close()

	const (
		commandID = "cmd-real-1"
		runID     = "run-real-1"
		idemKey   = "backtest-run-real-1"
	)
	env := Envelope{
		MessageID:       commandID,
		IdempotencyKey:  idemKey,
		CorrelationID:   "trace-real-1",
		OwnerType:       "backtest",
		OwnerID:         runID,
		OccurredAt:      time.Now().UTC(),
		ProducerService: "backend-api",
		SchemaVersion:   DefaultSchemaVersion,
		Subject:         Subject("backtest", "command", "start"),
		Payload:         json.RawMessage(`{"command_id":"` + commandID + `"}`),
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	res, err := pub.Publish(ctx, env)
	if err != nil {
		t.Fatalf("Publish: %v", err)
	}
	if res.Stream != StreamBacktestCommands {
		t.Fatalf("expected stream %s, got %s", StreamBacktestCommands, res.Stream)
	}

	// Read the exact message back by sequence and assert the wire contract.
	msg, err := verifyJS.GetMsg(res.Stream, res.Sequence)
	if err != nil {
		t.Fatalf("GetMsg(%s,%d): %v", res.Stream, res.Sequence, err)
	}
	if msg.Subject != "backtest.command.start" {
		t.Fatalf("expected subject backtest.command.start, got %q", msg.Subject)
	}
	if got := msg.Header.Get("Nats-Msg-Id"); got != idemKey {
		t.Fatalf("expected JetStream Msg-Id %q, got %q", idemKey, got)
	}

	var got Envelope
	if err := json.Unmarshal(msg.Data, &got); err != nil {
		t.Fatalf("unmarshal envelope: %v", err)
	}
	if got.MessageID != commandID || got.OwnerID != runID || got.IdempotencyKey != idemKey {
		t.Fatalf("envelope identity drift: %+v", got)
	}
	if got.Subject != "backtest.command.start" {
		t.Fatalf("envelope subject drift: %q", got.Subject)
	}
}

// TestPublisherIntegration_DuplicateSuppressed proves repeating a publish with
// the same idempotency key is deduplicated by JetStream Msg-Id.
func TestPublisherIntegration_DuplicateSuppressed(t *testing.T) {
	url := testNATSURL(t)
	verifyConn := skipIfNoNATS(t, url)
	defer verifyConn.Close()
	verifyJS, err := verifyConn.JetStream()
	if err != nil {
		t.Fatalf("verify JetStream context: %v", err)
	}
	_ = verifyJS.DeleteStream(StreamBacktestCommands)

	pub := NewPublisher(config.NATSSettings{Enabled: true, URL: url})
	defer pub.Close()

	const idemKey = "backtest-dup-1"
	mk := func() Envelope {
		return Envelope{
			MessageID: "cmd-dup-1", IdempotencyKey: idemKey, CorrelationID: "c",
			OwnerType: "backtest", OwnerID: "run-dup-1", OccurredAt: time.Now().UTC(),
			ProducerService: "backend-api", SchemaVersion: DefaultSchemaVersion,
			Subject: Subject("backtest", "command", "start"),
			Payload: json.RawMessage(`{}`),
		}
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	first, err := pub.Publish(ctx, mk())
	if err != nil {
		t.Fatalf("first publish: %v", err)
	}
	if first.Duplicate {
		t.Fatal("first publish should not be reported as duplicate on a clean stream")
	}
	second, err := pub.Publish(ctx, mk())
	if err != nil {
		t.Fatalf("second publish: %v", err)
	}
	if !second.Duplicate {
		t.Fatal("expected second publish with same Msg-Id to be deduplicated (Duplicate=true)")
	}
}

// TestPublisherIntegration_FailClosedOnBadURL proves an unreachable bus surfaces
// an error instead of a silent success (fail-closed transport).
func TestPublisherIntegration_FailClosedOnBadURL(t *testing.T) {
	pub := NewPublisher(config.NATSSettings{Enabled: true, URL: "nats://127.0.0.1:9"}) // unused port
	if pub == nil {
		t.Fatal("expected non-nil publisher")
	}
	defer pub.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()
	_, err := pub.Publish(ctx, Envelope{
		MessageID: "cmd-fail", IdempotencyKey: "idem-fail", CorrelationID: "c",
		OwnerType: "backtest", OwnerID: "run-fail", OccurredAt: time.Now().UTC(),
		ProducerService: "backend-api", SchemaVersion: DefaultSchemaVersion,
		Subject: Subject("backtest", "command", "start"),
		Payload: json.RawMessage(`{}`),
	})
	if err == nil {
		t.Fatal("expected publish to a bad URL to fail closed, got nil error")
	}
	if !strings.Contains(err.Error(), "backtest.command.start") && !strings.Contains(strings.ToLower(err.Error()), "publish") && !strings.Contains(strings.ToLower(err.Error()), "connect") {
		t.Fatalf("expected a transport/connect/publish error, got %v", err)
	}
}
