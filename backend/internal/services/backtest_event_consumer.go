package services

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"strings"
	"time"

	natsclient "github.com/nats-io/nats.go"

	"github.com/dydx-trading-bot/backend-go/internal/nats"
)

// Backend JetStream consumer for durable backtest events (Phase 2 consume side).
//
// It subscribes to backtest.event.> on the BACKTEST_EVENTS stream, decodes each
// message's wire envelope, and projects the event to the user-facing push feed
// via BacktestEventProjector. It runs ALONGSIDE the existing Redis pub/sub push
// (dual-push); removing the Redis path is a later cutover step.
//
// Fail-closed: connection/fetch/decode errors are logged and the loop retries.
// A bad message is NAK'd for redelivery; a successfully projected message is
// ACK'd. The consumer must never panic or block backend startup.

const (
	backtestEventStreamName    = "BACKTEST_EVENTS"
	backtestEventStreamSubject = "backtest.event.>"
	defaultEventConsumerName   = "backend-backtest-event-projector"
	defaultEventFetchBatch     = 64
	defaultEventFetchWait      = 2 * time.Second
	eventReconnectWait         = 5 * time.Second

	// eventConsumerAckWait bounds how long an unacked message waits before
	// redelivery; it must exceed the slowest legitimate projection.
	eventConsumerAckWait = 60 * time.Second
	// eventConsumerMaxDeliver caps redeliveries of a failing message; past it
	// the message is dropped (with a dead-letter record) instead of looping.
	eventConsumerMaxDeliver = 16
	eventNakBaseDelay       = 500 * time.Millisecond
	eventNakMaxDelay        = 30 * time.Second
)

// BacktestEventConsumer consumes durable backtest events and projects them.
type BacktestEventConsumer struct {
	natsURL       string
	projector     *BacktestEventProjector
	consumerName  string
	metrics       *AsyncMetrics
	lastMessageAt time.Time
	startedAt     time.Time
}

// NewBacktestEventConsumer returns nil when the projector is nil (disabled).
func NewBacktestEventConsumer(natsURL string, projector *BacktestEventProjector) *BacktestEventConsumer {
	return newBacktestEventConsumer(natsURL, projector, defaultEventConsumerName)
}

func newBacktestEventConsumer(natsURL string, projector *BacktestEventProjector, consumerName string) *BacktestEventConsumer {
	url := strings.TrimSpace(natsURL)
	if url == "" || projector == nil {
		return nil
	}
	return &BacktestEventConsumer{
		natsURL:      url,
		projector:    projector,
		consumerName: consumerName,
		metrics:      GetAsyncMetrics(),
		startedAt:    time.Now().UTC(),
	}
}

// ProcessRaw decodes a wire envelope fetched from JetStream and projects the
// event. It is the testable per-message core; Run calls it for each fetched msg.
func (c *BacktestEventConsumer) ProcessRaw(data []byte) error {
	if c == nil || c.projector == nil {
		return errors.New("backtest event consumer: nil consumer/projector")
	}
	var env nats.Envelope
	if err := json.Unmarshal(data, &env); err != nil {
		return err
	}
	return c.projector.ProcessEnvelope(env)
}

// Run blocks, consuming backtest events until ctx is cancelled. It is intended
// to run in its own goroutine. It never returns a terminal error for transient
// failures; it logs and reconnects.
func (c *BacktestEventConsumer) Run(ctx context.Context) error {
	if c == nil {
		return errors.New("backtest event consumer: nil")
	}
	for {
		if err := ctx.Err(); err != nil {
			return err
		}
		if err := c.runOnce(ctx); err != nil {
			if ctx.Err() != nil {
				return ctx.Err()
			}
			slog.Warn("backtest_event_consumer loop error; reconnecting", "error", err, "retry_in", eventReconnectWait)
			if !sleepCtx(ctx, eventReconnectWait) {
				return ctx.Err()
			}
		}
	}
}

func (c *BacktestEventConsumer) runOnce(ctx context.Context) error {
	conn, js, err := c.connect()
	if err != nil {
		return err
	}
	defer conn.Close()

	if err := ensureEventStream(js); err != nil {
		return err
	}
	if err := ensureEventConsumer(js); err != nil {
		return err
	}

	sub, err := js.PullSubscribe(
		backtestEventStreamSubject,
		c.consumerName,
		natsclient.BindStream(backtestEventStreamName),
		natsclient.ManualAck(),
	)
	if err != nil {
		return err
	}

	slog.Info("backtest_event_consumer subscribed", "stream", backtestEventStreamName, "consumer", c.consumerName)
	for {
		if err := ctx.Err(); err != nil {
			return err
		}
		msgs, err := sub.Fetch(defaultEventFetchBatch, natsclient.MaxWait(defaultEventFetchWait))
		if err != nil {
			if errors.Is(err, natsclient.ErrTimeout) {
				continue
			}
			return err
		}
		for _, msg := range msgs {
			c.handleMessage(msg)
		}
	}
}

func (c *BacktestEventConsumer) handleMessage(msg *natsclient.Msg) {
	// Record heartbeat on each message
	if c.metrics != nil {
		c.metrics.RecordHeartbeat()
	}

	// Calculate and record consumer lag
	now := time.Now().UTC()
	if !c.lastMessageAt.IsZero() {
		lagMs := uint64(now.Sub(c.lastMessageAt).Milliseconds())
		if c.metrics != nil && lagMs > 0 {
			// Update consumer lag (simple approach: time since last message)
			c.metrics.SetNATSConsumerLag(lagMs)
		}
	}
	c.lastMessageAt = now

	// A message that cannot be decoded can never succeed on redelivery;
	// retrying it forever would wedge the pipeline in a hot loop. Treat
	// undecodable envelopes as terminal: acknowledge and dead-letter.
	var env nats.Envelope
	if err := json.Unmarshal(msg.Data, &env); err != nil {
		slog.Error("backtest_event_consumer dropping malformed envelope",
			"error", err, "subject", msg.Subject, "size", len(msg.Data))
		c.dropMessage(msg, "malformed envelope")
		return
	}

	if err := c.projector.ProcessEnvelope(env); err != nil {
		if c.exceededMaxDeliveries(msg) {
			slog.Error("backtest_event_consumer message exceeded max deliveries; dropping",
				"error", err, "subject", msg.Subject, "max_deliver", eventConsumerMaxDeliver)
			c.dropMessage(msg, "max deliveries exceeded")
			return
		}
		delay := eventNakDelay(msg)
		slog.Warn("backtest_event_consumer project failed; NAK with backoff",
			"error", err, "subject", msg.Subject, "retry_in", delay)
		_ = msg.NakWithDelay(delay)
		return
	}
	if err := msg.Ack(); err != nil {
		// A failed ack means the message will be redelivered; projection must
		// tolerate that (broadcast consumers are at-least-once).
		slog.Warn("backtest_event_consumer ack failed; message will be redelivered",
			"error", err, "subject", msg.Subject)
	}
}

// dropMessage terminally acknowledges a message and records it as dead-lettered.
func (c *BacktestEventConsumer) dropMessage(msg *natsclient.Msg, reason string) {
	if c.metrics != nil {
		c.metrics.RecordDeadLetter()
	}
	if err := msg.Ack(); err != nil {
		slog.Warn("backtest_event_consumer terminal ack failed; message will be redelivered",
			"error", err, "subject", msg.Subject, "reason", reason)
	}
}

// exceededMaxDeliveries reports whether the message has exhausted its
// redelivery budget.
func (c *BacktestEventConsumer) exceededMaxDeliveries(msg *natsclient.Msg) bool {
	meta, err := msg.Metadata()
	if err != nil {
		return false
	}
	return meta.NumDelivered >= eventConsumerMaxDeliver
}

// eventNakDelay derives an exponential backoff from the delivery count:
// 0.5s, 1s, 2s, ... capped at 30s.
func eventNakDelay(msg *natsclient.Msg) time.Duration {
	meta, err := msg.Metadata()
	if err != nil || meta.NumDelivered <= 1 {
		return eventNakBaseDelay
	}
	shift := meta.NumDelivered - 2
	if shift > 20 {
		shift = 20
	}
	delay := eventNakBaseDelay << shift
	if delay <= 0 || delay > eventNakMaxDelay {
		return eventNakMaxDelay
	}
	return delay
}

func (c *BacktestEventConsumer) connect() (*natsclient.Conn, natsclient.JetStreamContext, error) {
	conn, err := natsclient.Connect(
		c.natsURL,
		natsclient.Name("dydx-backend-event-consumer"),
		natsclient.Timeout(5*time.Second),
		natsclient.ReconnectWait(eventReconnectWait),
		natsclient.MaxReconnects(-1),
	)
	if err != nil {
		return nil, nil, err
	}
	js, err := conn.JetStream()
	if err != nil {
		conn.Close()
		return nil, nil, err
	}
	return conn, js, nil
}

// ensureEventStream idempotently creates BACKTEST_EVENTS with the same config the
// bot emitter uses (backtest.event.>, limits retention), so the consumer can
// start before any event has been emitted. AddStream is a no-op if the stream
// already exists with the same config.
func ensureEventStream(js natsclient.JetStreamContext) error {
	_, err := js.StreamInfo(backtestEventStreamName)
	if err == nil {
		return nil
	}
	_, err = js.AddStream(&natsclient.StreamConfig{
		Name:      backtestEventStreamName,
		Subjects:  []string{backtestEventStreamSubject},
		Retention: natsclient.LimitsPolicy,
		Storage:   natsclient.FileStorage,
		MaxAge:    7 * 24 * time.Hour,
	})
	if err != nil && !isAlreadyExists(err) {
		return err
	}
	return nil
}

func isAlreadyExists(err error) bool {
	return err != nil && strings.Contains(strings.ToLower(err.Error()), "already in use")
}

// ensureEventConsumer idempotently provisions the durable consumer with
// explicit AckWait/MaxDeliver/MaxAckPending so poison messages back off and
// eventually dead-letter instead of hot-looping on immediate redelivery.
func ensureEventConsumer(js natsclient.JetStreamContext) error {
	want := &natsclient.ConsumerConfig{
		Durable:       defaultEventConsumerName,
		FilterSubject: backtestEventStreamSubject,
		AckPolicy:     natsclient.AckExplicitPolicy,
		AckWait:       eventConsumerAckWait,
		MaxDeliver:    eventConsumerMaxDeliver,
		MaxAckPending: 256,
	}

	if _, err := js.ConsumerInfo(backtestEventStreamName, defaultEventConsumerName); err == nil {
		if _, err := js.UpdateConsumer(backtestEventStreamName, want); err != nil {
			// An existing durable with immutable-field drift keeps its config;
			// the consumer still works with the previous delivery semantics.
			slog.Warn("backtest_event_consumer unable to update durable config; keeping existing",
				"error", err, "consumer", defaultEventConsumerName)
		}
		return nil
	}

	_, err := js.AddConsumer(backtestEventStreamName, want)
	if err != nil && !isAlreadyExists(err) {
		return err
	}
	return nil
}

// sleepCtx sleeps for d or returns false when ctx is cancelled.
func sleepCtx(ctx context.Context, d time.Duration) bool {
	timer := time.NewTimer(d)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return false
	case <-timer.C:
		return true
	}
}
