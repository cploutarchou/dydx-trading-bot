package services

import (
	"context"
	"fmt"
	"log/slog"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"github.com/redis/go-redis/v9"
)

// hubSendBuffer bounds how many payloads may queue for one WebSocket
// subscriber before it is considered slow and disconnected.
const hubSendBuffer = 16

// hubSubscriber pairs a WebSocket connection with its dedicated writer
// goroutine. gorilla/websocket permits exactly one concurrent writer, so all
// pushes for a connection are funneled through the buffered send channel.
type hubSubscriber struct {
	conn *websocket.Conn
	send chan []byte
}

// BacktestPushHub subscribes to Redis backtest status channels and pushes
// messages to connected WebSocket clients. The JetStream projector pushes
// through the same hub via Broadcast; both paths serialize per connection
// through the subscriber writer goroutine.
type BacktestPushHub struct {
	mu        sync.RWMutex
	conns     map[string]map[*websocket.Conn]*hubSubscriber // run_id → conn → subscriber
	redisOpts redis.Options

	stop     chan struct{}
	stopOnce sync.Once
}

// NewBacktestPushHub creates a new hub and starts the Redis subscriber goroutine.
func NewBacktestPushHub(redisHost string, redisPort int, redisPassword string, redisDB int) *BacktestPushHub {
	h := &BacktestPushHub{
		conns: make(map[string]map[*websocket.Conn]*hubSubscriber),
		redisOpts: redis.Options{
			Addr:     fmt.Sprintf("%s:%d", redisHost, redisPort),
			Password: redisPassword,
			DB:       redisDB,
			Protocol: 2,
		},
		stop: make(chan struct{}),
	}
	go h.runSubscriber()
	return h
}

// Stop terminates the Redis subscriber and disconnects all subscribers. It is
// idempotent and intended for process shutdown.
func (h *BacktestPushHub) Stop() {
	if h == nil {
		return
	}
	h.stopOnce.Do(func() {
		close(h.stop)
	})

	h.mu.Lock()
	defer h.mu.Unlock()
	for runID, set := range h.conns {
		for conn, sub := range set {
			close(sub.send)
			_ = conn.Close()
			delete(set, conn)
		}
		delete(h.conns, runID)
	}
}

// Subscribe registers a WebSocket connection to receive pushes for run_id.
// The caller must call Unsubscribe when the connection closes.
func (h *BacktestPushHub) Subscribe(runID string, conn *websocket.Conn) {
	if h == nil || conn == nil || runID == "" {
		return
	}
	h.mu.Lock()
	if _, ok := h.conns[runID]; !ok {
		h.conns[runID] = make(map[*websocket.Conn]*hubSubscriber)
	}
	sub := &hubSubscriber{conn: conn, send: make(chan []byte, hubSendBuffer)}
	h.conns[runID][conn] = sub
	h.mu.Unlock()

	go h.writeLoop(runID, sub)
}

// Unsubscribe removes a connection from a run_id channel.
func (h *BacktestPushHub) Unsubscribe(runID string, conn *websocket.Conn) {
	if h == nil {
		return
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	h.removeLocked(runID, conn)
}

// removeLocked disconnects a subscriber; h.mu must be held.
func (h *BacktestPushHub) removeLocked(runID string, conn *websocket.Conn) {
	set, ok := h.conns[runID]
	if !ok {
		return
	}
	sub, ok := set[conn]
	if !ok {
		return
	}
	delete(set, conn)
	// Closing the send channel terminates the writer goroutine; only the
	// remover closes it, so there is exactly one close per channel.
	close(sub.send)
	_ = conn.Close()
	if len(set) == 0 {
		delete(h.conns, runID)
	}
}

// Broadcast sends a raw JSON payload to all WebSocket connections subscribed
// for run_id. It is the durable-event entry point: a backend projector that
// consumes backtest.event.* from JetStream calls this to push updates to
// clients without going through the Redis pub/sub path.
func (h *BacktestPushHub) Broadcast(runID string, payload []byte) {
	if h == nil || runID == "" {
		return
	}
	h.push(runID, payload)
}

// push offers the payload to every subscriber for run_id without blocking:
// a full send buffer marks the subscriber as too slow and disconnects it.
// This keeps the Redis subscriber and the JetStream Fetch loop responsive
// regardless of client behavior.
func (h *BacktestPushHub) push(runID string, payload []byte) {
	h.mu.RLock()
	subs := make([]*hubSubscriber, 0, len(h.conns[runID]))
	for _, sub := range h.conns[runID] {
		subs = append(subs, sub)
	}
	h.mu.RUnlock()

	for _, sub := range subs {
		select {
		case sub.send <- payload:
		default:
			slog.Warn("backtest_push_hub subscriber too slow; disconnecting", "run_id", runID)
			h.mu.Lock()
			h.removeLocked(runID, sub.conn)
			h.mu.Unlock()
		}
	}
}

// writeLoop is the single writer for one subscriber connection.
func (h *BacktestPushHub) writeLoop(runID string, sub *hubSubscriber) {
	for payload := range sub.send {
		_ = sub.conn.SetWriteDeadline(time.Now().Add(5 * time.Second))
		if err := sub.conn.WriteMessage(websocket.TextMessage, payload); err != nil {
			slog.Debug("backtest_push_hub write failed", "run_id", runID, "error", err)
			h.mu.Lock()
			h.removeLocked(runID, sub.conn)
			h.mu.Unlock()
			return
		}
	}
}

// runSubscriber blocks until stopped, consuming Redis pub/sub messages on
// backtest:*:status.
func (h *BacktestPushHub) runSubscriber() {
	const (
		initialBackoff = time.Second
		maxBackoff     = 30 * time.Second
	)

	backoff := initialBackoff

	for {
		if h.isStopped() {
			return
		}
		rc := redis.NewClient(&h.redisOpts)
		ctx := context.Background()

		if err := rc.Ping(ctx).Err(); err != nil {
			slog.Warn("backtest_push_hub redis ping failed", "error", err, "retry_in", backoff.String())
			_ = rc.Close()
			if !h.sleepBackoff(backoff, &backoff, maxBackoff, initialBackoff) {
				return
			}
			continue
		}

		pubsub := rc.PSubscribe(ctx, "backtest:*:status")
		if _, err := pubsub.Receive(ctx); err != nil {
			slog.Warn("backtest_push_hub subscribe failed", "error", err, "retry_in", backoff.String())
			_ = pubsub.Close()
			_ = rc.Close()
			if !h.sleepBackoff(backoff, &backoff, maxBackoff, initialBackoff) {
				return
			}
			continue
		}

		slog.Info("backtest_push_hub redis subscriber started")
		backoff = initialBackoff

		ch := pubsub.Channel()
		for msg := range ch {
			// Channel pattern: backtest:{run_id}:status
			parts := strings.SplitN(msg.Channel, ":", 3)
			if len(parts) != 3 {
				continue
			}
			runID := parts[1]
			if runID == "" {
				continue
			}
			h.push(runID, []byte(msg.Payload))
		}

		if h.isStopped() {
			_ = pubsub.Close()
			_ = rc.Close()
			return
		}
		slog.Warn("backtest_push_hub redis subscriber channel closed; reconnecting", "retry_in", backoff.String())
		_ = pubsub.Close()
		_ = rc.Close()
		if !h.sleepBackoff(backoff, &backoff, maxBackoff, initialBackoff) {
			return
		}
	}
}

func (h *BacktestPushHub) isStopped() bool {
	select {
	case <-h.stop:
		return true
	default:
		return false
	}
}

// sleepBackoff waits for the current backoff, doubling it (capped) for the
// next attempt. It returns false when the hub was stopped while sleeping.
func (h *BacktestPushHub) sleepBackoff(current time.Duration, backoff *time.Duration, max, reset time.Duration) bool {
	timer := time.NewTimer(current)
	defer timer.Stop()
	select {
	case <-h.stop:
		return false
	case <-timer.C:
	}
	*backoff *= 2
	if *backoff > max {
		*backoff = max
	}
	// Caller resets backoff to `reset` after a successful connection.
	_ = reset
	return true
}
