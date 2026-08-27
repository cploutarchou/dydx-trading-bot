// Package nats provides the backend-owned NATS JetStream publisher abstraction.
//
// It is the first Phase 4 slice: a real, fail-closed JetStream client that the
// backend can use to publish durable command/event envelopes without coupling
// application startup to bus availability and without replacing the existing
// HTTP/Celery control path. A nil Publisher (returned when NATS is disabled, the
// checked-in default) signals callers to fall back to the current path, mirroring
// the ClickHouseReader and MinIO signer fail-closed patterns.
package nats

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"sync"
	"time"

	natsclient "github.com/nats-io/nats.go"

	"github.com/dydx-trading-bot/backend-go/config"
)

// Sentinels returned to callers. They never represent a successful publish.
var (
	// ErrPublisherDisabled is returned when the publisher was never constructed
	// because NATS is disabled. Callers must treat this as a fail-closed signal.
	ErrPublisherDisabled = errors.New("nats publisher disabled")
	// ErrPublisherClosed is returned after Close has been called.
	ErrPublisherClosed = errors.New("nats publisher closed")
)

const (
	// DefaultSchemaVersion is stamped on every envelope until callers override it.
	DefaultSchemaVersion = "1"

	commandToken = "command"
	eventToken   = "event"

	botOwner      = "bot"
	backtestOwner = "backtest"

	connectTimeout = 5 * time.Second
	reconnectWait  = 2 * time.Second
)

// Subject namespace per docs/needed_improvements/nats-command-event-contract.md.
// Owners (bot, backtest) and kinds (command, event) combine with an action to
// form a subject, e.g. Subject(botOwner, commandToken, "start") -> "bot.command.start".
const (
	StreamBotCommands      = "BOT_COMMANDS"
	StreamBotEvents        = "BOT_EVENTS"
	StreamBacktestCommands = "BACKTEST_COMMANDS"
	StreamBacktestEvents   = "BACKTEST_EVENTS"
)

// Envelope is the canonical command/event payload envelope. It follows the
// nats-jetstream-plan "Event Payload Rules" and the contract's "Minimal payload
// shape": every message carries identity, idempotency, correlation, ownership,
// timing, producer, and schema fields, plus a small reference-heavy Payload.
// Large results must never be embedded; reference them and store them in
// PostgreSQL/ClickHouse/MinIO.
type Envelope struct {
	MessageID       string          `json:"message_id"`             // command_id or event_id
	IdempotencyKey  string          `json:"idempotency_key"`        // server-side dedupe key
	CorrelationID   string          `json:"correlation_id"`         // request/trace correlation
	CausationID     string          `json:"causation_id,omitempty"` // originating cause, if any
	OwnerType       string          `json:"owner_type"`             // e.g. "bot", "backtest"
	OwnerID         string          `json:"owner_id"`               // instance/run identifier
	OccurredAt      time.Time       `json:"occurred_at"`            // UTC event time
	ProducerService string          `json:"producer_service"`       // e.g. "backend-api"
	SchemaVersion   string          `json:"schema_version"`         // envelope schema version
	Subject         string          `json:"subject"`                // NATS subject published to
	Payload         json.RawMessage `json:"payload,omitempty"`      // small, reference-heavy payload
}

// Validate enforces the non-negotiable envelope identity fields so a caller can
// never publish a command that workers cannot deduplicate or correlate.
func (e Envelope) Validate() error {
	if strings.TrimSpace(e.MessageID) == "" {
		return errors.New("envelope message_id is required")
	}
	if strings.TrimSpace(e.IdempotencyKey) == "" {
		return errors.New("envelope idempotency_key is required")
	}
	if strings.TrimSpace(e.CorrelationID) == "" {
		return errors.New("envelope correlation_id is required")
	}
	if strings.TrimSpace(e.Subject) == "" {
		return errors.New("envelope subject is required")
	}
	if e.OccurredAt.IsZero() {
		return errors.New("envelope occurred_at is required")
	}
	return nil
}

// Subject builds a contract subject from an owner, kind, and action. It is the
// single source of truth for the subject namespace so callers never hand-build
// subject strings.
//
// Subject("bot", "command", "start")      -> "bot.command.start"
// Subject("backtest", "event", "completed") -> "backtest.event.completed"
func Subject(owner, kind, action string) string {
	return strings.Trim(owner, ".") + "." + strings.Trim(kind, ".") + "." + strings.Trim(action, ".")
}

// StreamFor maps a subject to its owning JetStream stream. Unknown subjects map
// to the empty string; callers must ensure a stream covers the subject before
// publishing (see Publisher.ensureStream).
func StreamFor(subject string) string {
	switch {
	case strings.HasPrefix(subject, botOwner+"."+commandToken+"."):
		return StreamBotCommands
	case strings.HasPrefix(subject, botOwner+"."+eventToken+"."):
		return StreamBotEvents
	case strings.HasPrefix(subject, backtestOwner+"."+commandToken+"."):
		return StreamBacktestCommands
	case strings.HasPrefix(subject, backtestOwner+"."+eventToken+"."):
		return StreamBacktestEvents
	default:
		return ""
	}
}

// PublishResult is the JetStream publish acknowledgement projected into a
// transport-agnostic shape so callers do not depend on nats.go types.
type PublishResult struct {
	Stream    string
	Sequence  uint64
	Duplicate bool
}

// Publisher publishes durable command/event envelopes to NATS JetStream. It
// connects lazily on first publish so constructing it never couples application
// startup to bus availability (per the contract operational rules). A nil
// Publisher means NATS is disabled and callers must fall back.
type Publisher struct {
	settings config.NATSSettings

	mu     sync.Mutex
	conn   *natsclient.Conn
	js     natsclient.JetStreamContext
	closed bool

	// ensuredStreams caches streams already created via AddStream so steady-state
	// publishes do not pay a server round-trip per message.
	ensuredStreams map[string]struct{}
}

// NewPublisher returns nil when NATS reads/publishes are not enabled, mirroring
// the ClickHouseReader fail-closed construction. When enabled it returns a
// Publisher that connects lazily; the returned error from later Publish calls is
// the signal that the bus is unavailable, never a startup failure.
func NewPublisher(settings config.NATSSettings) *Publisher {
	if !settings.Enabled {
		return nil
	}
	return &Publisher{settings: settings, ensuredStreams: make(map[string]struct{})}
}

// Publish marshals the envelope, ensures a connection and the covering stream
// exist, and publishes with the idempotency key as the JetStream Msg-Id header so
// the server suppresses duplicates. It returns the ack or an error; callers must
// not treat an error as success (no silent drops).
func (p *Publisher) Publish(ctx context.Context, env Envelope) (*PublishResult, error) {
	if p == nil {
		return nil, ErrPublisherDisabled
	}
	if ctx == nil {
		ctx = context.Background()
	}
	if err := ctx.Err(); err != nil {
		return nil, fmt.Errorf("publish %s: %w", env.Subject, err)
	}
	if err := env.Validate(); err != nil {
		return nil, err
	}
	if err := p.ensureConnected(); err != nil {
		return nil, err
	}
	if err := p.ensureStream(env.Subject); err != nil {
		return nil, err
	}
	if err := ctx.Err(); err != nil {
		return nil, fmt.Errorf("publish %s: %w", env.Subject, err)
	}

	data, err := json.Marshal(env)
	if err != nil {
		return nil, fmt.Errorf("marshal envelope: %w", err)
	}

	ack, err := p.js.Publish(env.Subject, data, natsclient.MsgId(env.IdempotencyKey), natsclient.Context(ctx))
	if err != nil {
		return nil, fmt.Errorf("publish %s: %w", env.Subject, err)
	}
	return &PublishResult{
		Stream:    ack.Stream,
		Sequence:  ack.Sequence,
		Duplicate: ack.Duplicate,
	}, nil
}

// Close releases the underlying connection. It is safe to call on a nil or
// already-closed publisher.
func (p *Publisher) Close() {
	if p == nil {
		return
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	p.closed = true
	if p.conn != nil {
		p.conn.Close()
		p.conn = nil
		p.js = nil
	}
}

// ensureConnected lazily dials NATS. It is intentionally not called at
// construction time so a missing bus never blocks startup. A failed dial is
// returned as an error, not a panic, so callers can fall back gracefully.
func (p *Publisher) ensureConnected() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	if p.closed {
		return ErrPublisherClosed
	}
	if p.conn != nil && p.conn.IsConnected() {
		return nil
	}
	if p.conn != nil {
		p.conn.Close()
		p.conn = nil
		p.js = nil
	}

	url := strings.TrimSpace(p.settings.URL)
	if url == "" {
		return errors.New("nats url is not configured")
	}

	conn, err := natsclient.Connect(url,
		natsclient.Name("dydx-backend-jetstream-publisher"),
		natsclient.Timeout(connectTimeout),
		natsclient.ReconnectWait(reconnectWait),
		natsclient.MaxReconnects(-1),
	)
	if err != nil {
		return fmt.Errorf("nats connect %s: %w", url, err)
	}
	js, err := conn.JetStream()
	if err != nil {
		conn.Close()
		return fmt.Errorf("jetstream context: %w", err)
	}
	p.conn = conn
	p.js = js
	return nil
}

// ensureStream idempotently creates or updates the JetStream stream covering the
// subject so publishes never fail because a stream is missing. Stream configs
// follow nats-jetstream-plan: work-queue retention for commands, limits
// retention for events.
func (p *Publisher) ensureStream(subject string) error {
	stream := StreamFor(subject)
	if stream == "" {
		return fmt.Errorf("no stream mapping for subject %q", subject)
	}

	p.mu.Lock()
	if _, ok := p.ensuredStreams[stream]; ok {
		p.mu.Unlock()
		return nil
	}
	cfg := streamConfig(stream, subject)
	_, addErr := p.js.AddStream(cfg)
	if addErr == nil {
		p.ensuredStreams[stream] = struct{}{}
	}
	p.mu.Unlock()

	if addErr != nil {
		// AddStream is idempotent only across identical configs; a config drift
		// surfaces an error that operators should resolve, but it must not crash.
		return fmt.Errorf("ensure stream %s: %w", stream, addErr)
	}
	return nil
}

func streamConfig(stream, subject string) *natsclient.StreamConfig {
	cfg := &natsclient.StreamConfig{
		Name:     stream,
		Subjects: []string{subjectToken(subject) + ".*"},
		MaxAge:   7 * 24 * time.Hour,
		Storage:  natsclient.FileStorage,
	}
	if strings.Contains(subject, "."+commandToken+".") {
		cfg.Retention = natsclient.WorkQueuePolicy
	} else {
		cfg.Retention = natsclient.LimitsPolicy
	}
	return cfg
}

// subjectToken returns the first two dotted tokens of a subject ("bot.command"
// from "bot.command.start") so a stream covers every action under that pair.
func subjectToken(subject string) string {
	parts := strings.SplitN(subject, ".", 3)
	if len(parts) < 2 {
		return subject
	}
	return parts[0] + "." + parts[1]
}
