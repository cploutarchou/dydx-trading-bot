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
	conns := make([]*websocket.Conn, 0, len(set))
	for conn := range set {
		conns = append(conns, conn)
	}
	h.mu.RUnlock()

	if len(conns) == 0 {
		return
	}

	deadConns := make([]*websocket.Conn, 0)
	for _, conn := range conns {
		_ = conn.SetWriteDeadline(time.Now().Add(5 * time.Second))
		if err := conn.WriteMessage(websocket.TextMessage, payload); err != nil {
			slog.Debug("backtest_push_hub write failed", "run_id", runID, "error", err)
			deadConns = append(deadConns, conn)
		}
		_ = conn.SetWriteDeadline(time.Time{})
	}

	if len(deadConns) > 0 {
		h.mu.Lock()
		if set, ok := h.conns[runID]; ok {
			for _, deadConn := range deadConns {
				delete(set, deadConn)
				_ = deadConn.Close()
			}
			if len(set) == 0 {
				delete(h.conns, runID)
			}
		}
		h.mu.Unlock()
	}
}

// runSubscriber blocks forever, consuming Redis pub/sub messages on backtest:*:status.
func (h *BacktestPushHub) runSubscriber() {
	const (
		initialBackoff = time.Second
		maxBackoff     = 30 * time.Second
	)

	backoff := initialBackoff

	for {
		rc := redis.NewClient(&h.redisOpts)
		ctx := context.Background()

		if err := rc.Ping(ctx).Err(); err != nil {
			slog.Warn("backtest_push_hub redis ping failed", "error", err, "retry_in", backoff.String())
			_ = rc.Close()
			time.Sleep(backoff)
			if backoff < maxBackoff {
				backoff *= 2
				if backoff > maxBackoff {
					backoff = maxBackoff
				}
			}
			continue
		}

		pubsub := rc.PSubscribe(ctx, "backtest:*:status")
		if _, err := pubsub.Receive(ctx); err != nil {
			slog.Warn("backtest_push_hub subscribe failed", "error", err, "retry_in", backoff.String())
			_ = pubsub.Close()
			_ = rc.Close()
			time.Sleep(backoff)
			if backoff < maxBackoff {
				backoff *= 2
				if backoff > maxBackoff {
					backoff = maxBackoff
				}
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

		slog.Warn("backtest_push_hub redis subscriber channel closed; reconnecting", "retry_in", backoff.String())
		_ = pubsub.Close()
		_ = rc.Close()
		time.Sleep(backoff)
		if backoff < maxBackoff {
			backoff *= 2
			if backoff > maxBackoff {
				backoff = maxBackoff
			}
		}
	}
}
