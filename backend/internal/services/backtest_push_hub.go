package services

import (
	"context"
	"fmt"
	"log/slog"
	"strings"
	"sync"

	"github.com/gorilla/websocket"
	"github.com/redis/go-redis/v9"
)

// BacktestPushHub subscribes to Redis backtest status channels and pushes
// messages to connected WebSocket clients.
type BacktestPushHub struct {
	mu        sync.RWMutex
	conns     map[string]map[*websocket.Conn]struct{} // run_id → set of WS connections
	redisOpts redis.Options
}

// NewBacktestPushHub creates a new hub and starts the Redis subscriber goroutine.
func NewBacktestPushHub(redisHost string, redisPort int, redisPassword string, redisDB int) *BacktestPushHub {
	h := &BacktestPushHub{
		conns: make(map[string]map[*websocket.Conn]struct{}),
		redisOpts: redis.Options{
			Addr:     fmt.Sprintf("%s:%d", redisHost, redisPort),
			Password: redisPassword,
			DB:       redisDB,
		},
	}
	go h.runSubscriber()
	return h
}

// Subscribe registers a WebSocket connection to receive pushes for run_id.
// The caller must call Unsubscribe when the connection closes.
func (h *BacktestPushHub) Subscribe(runID string, conn *websocket.Conn) {
	h.mu.Lock()
	defer h.mu.Unlock()
	if _, ok := h.conns[runID]; !ok {
		h.conns[runID] = make(map[*websocket.Conn]struct{})
	}
	h.conns[runID][conn] = struct{}{}
}

// Unsubscribe removes a connection from a run_id channel.
func (h *BacktestPushHub) Unsubscribe(runID string, conn *websocket.Conn) {
	h.mu.Lock()
	defer h.mu.Unlock()
	if set, ok := h.conns[runID]; ok {
		delete(set, conn)
		if len(set) == 0 {
			delete(h.conns, runID)
		}
	}
}

// push sends a raw JSON payload to all connections subscribed for run_id.
func (h *BacktestPushHub) push(runID string, payload []byte) {
	h.mu.RLock()
	set := h.conns[runID]
	h.mu.RUnlock()

	for conn := range set {
		if err := conn.WriteMessage(websocket.TextMessage, payload); err != nil {
			slog.Debug("backtest_push_hub write failed", "run_id", runID, "error", err)
			// Stale connections are cleaned up when the WS handler closes.
		}
	}
}

// runSubscriber blocks forever, consuming Redis pub/sub messages on backtest:*:status.
func (h *BacktestPushHub) runSubscriber() {
	rc := redis.NewClient(&h.redisOpts)
	defer func() { _ = rc.Close() }()

	ctx := context.Background()
	pubsub := rc.PSubscribe(ctx, "backtest:*:status")
	defer func() { _ = pubsub.Close() }()

	slog.Info("backtest_push_hub redis subscriber started")

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

	slog.Warn("backtest_push_hub redis subscriber channel closed")
}
