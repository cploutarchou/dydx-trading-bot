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
)

// BacktestEventConsumer consumes durable backtest events and projects them.
type BacktestEventConsumer struct {
	natsURL      string
	projector    *BacktestEventProjector
	consumerName string
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
	return &BacktestEventConsumer{natsURL: url, projector: projector, consumerName: consumerName}
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
	if err := c.ProcessRaw(msg.Data); err != nil {
		slog.Warn("backtest_event_consumer project failed; NAK", "error", err, "subject", msg.Subject)
		_ = msg.Nak()
		return
	}
	_ = msg.Ack()
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
		Name:     backtestEventStreamName,
		Subjects: []string{backtestEventStreamSubject},
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
