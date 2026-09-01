package middleware

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

// APIRequestEventsMiddleware writes API request telemetry to ClickHouse.
// It captures high-volume API events without burdening PostgreSQL, enabling
// performance dashboards and SLO reporting. All writes are best-effort and
// fail closed (the request continues even if ClickHouse is unavailable).
func APIRequestEventsMiddleware(cfg *config.Config) gin.HandlerFunc {
	// Disabled by default - enable via ClickHouse + specific feature flag
	if !cfg.ClickHouse.Enabled {
		return func(c *gin.Context) {
			c.Next()
		}
	}

	// Build ClickHouse writer for API request events
	apiRequestWriter := services.NewAPIRequestWriter(
		services.NewClickHouseReader(cfg.ClickHouse),
	)

	// Nil writer means ClickHouse reads disabled, so skip writes too
	if apiRequestWriter == nil {
		return func(c *gin.Context) {
			c.Next()
		}
	}

	return func(c *gin.Context) {
		start := time.Now()

		// Process the request
		c.Next()

		// Capture request metrics
		latencyMs := time.Since(start).Milliseconds()
		statusCode := c.Writer.Status()

		// Extract request details
		method := strings.ToUpper(c.Request.Method)
		path := c.Request.URL.Path
		service := "backend"

		// Try to determine if this was rate limited
		rateLimited := uint8(0)
		if c.GetBool("rate_limited") {
			rateLimited = 1
		}

		// Extract user ID if available. RequireAuth stores user_id as an int;
		// a string is tolerated defensively for any non-standard setter.
		var userID *string
		if userIDVal, exists := c.Get("user_id"); exists && userIDVal != nil {
			switch uid := userIDVal.(type) {
			case int:
				if uid > 0 {
					formatted := strconv.Itoa(uid)
					userID = &formatted
				}
			case string:
				if uid != "" {
					userID = &uid
				}
			}
		}

		// Extract correlation/trace ID
		correlationID := GetTraceID(c)

		// Get client IP
		clientIP := c.ClientIP()

		// Record the API request event asynchronously to avoid blocking the request
		go func() {
			defer func() {
				// Recover from any panics in the async goroutine
				if r := recover(); r != nil {
					// Log but don't surface - this is best-effort analytics
					return
				}
			}()

			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			defer cancel()

			// Build the API request event
			event := services.APIRequestEvent{
				EventDate:     start.Format("2006-01-02"),
				EventTime:     start.Format(time.RFC3339Nano),
				Service:       service,
				Route:         path,
				Method:        method,
				StatusCode:    uint16(statusCode),
				LatencyMs:     uint32(latencyMs),
				UserID:        userID,
				CorrelationID: correlationID,
				ClientIP:      clientIP,
				RateLimited:   rateLimited,
			}

			// Write to ClickHouse - best effort, don't block on errors
			_ = apiRequestWriter.WriteEvent(ctx, event)
		}()
	}
}

// APIRequestEventsMiddlewareWithWriter uses an injected writer for testing.
func APIRequestEventsMiddlewareWithWriter(writer *services.APIRequestWriter) gin.HandlerFunc {
	if writer == nil {
		return func(c *gin.Context) {
			c.Next()
		}
	}

	return func(c *gin.Context) {
		start := time.Now()
		c.Next()

		latencyMs := time.Since(start).Milliseconds()
		statusCode := c.Writer.Status()

		method := strings.ToUpper(c.Request.Method)
		path := c.Request.URL.Path
		service := "backend"

		rateLimited := uint8(0)
		if c.GetBool("rate_limited") {
			rateLimited = 1
		}

		var userID *string
		if userIDVal, exists := c.Get("user_id"); exists && userIDVal != nil {
			if uid, ok := userIDVal.(string); ok && uid != "" {
				userID = &uid
			}
		}

		correlationID := GetTraceID(c)
		clientIP := c.ClientIP()

		go func() {
			defer func() {
				if r := recover(); r != nil {
					return
				}
			}()

			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			defer cancel()

			event := services.APIRequestEvent{
				EventDate:     start.Format("2006-01-02"),
				EventTime:     start.Format(time.RFC3339Nano),
				Service:       service,
				Route:         path,
				Method:        method,
				StatusCode:    uint16(statusCode),
				LatencyMs:     uint32(latencyMs),
				UserID:        userID,
				CorrelationID: correlationID,
				ClientIP:      clientIP,
				RateLimited:   rateLimited,
			}

			_ = writer.WriteEvent(ctx, event)
		}()
	}
}

// APIRequestEventBatchWriter provides batching for API request events
// to reduce ClickHouse load from high-volume endpoints.
type APIRequestEventBatchWriter struct {
	flusherDone chan struct{}
	closeOnce   sync.Once
	writer        *services.APIRequestWriter
	buffer        []services.APIRequestEvent
	bufferMux     sync.Mutex
	batchSize     int
	flushInterval time.Duration
	lastFlush     time.Time
	stopChan      chan struct{}
}

// NewAPIRequestEventBatchWriter creates a new batching writer.
func NewAPIRequestEventBatchWriter(writer *services.APIRequestWriter, batchSize int, flushInterval time.Duration) *APIRequestEventBatchWriter {
	if writer == nil {
		return nil
	}

	if flushInterval <= 0 {
		flushInterval = 5 * time.Second
	}
	if batchSize <= 0 {
		batchSize = 64
	}
	bw := &APIRequestEventBatchWriter{
		writer:        writer,
		buffer:        make([]services.APIRequestEvent, 0, batchSize),
		batchSize:     batchSize,
		flushInterval: flushInterval,
		lastFlush:     time.Now(),
		stopChan:      make(chan struct{}),
		flusherDone:   make(chan struct{}),
	}

	// Start background flusher
	go bw.backgroundFlush()

	return bw
}

func (bw *APIRequestEventBatchWriter) backgroundFlush() {
	defer close(bw.flusherDone)

	ticker := time.NewTicker(bw.flushInterval / 2)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			bw.maybeFlush()
		case <-bw.stopChan:
			// Synchronous final flush so shutdown cannot drop buffered events.
			bw.flushSynchronously()
			return
		}
	}
}

func (bw *APIRequestEventBatchWriter) maybeFlush() {
	bw.bufferMux.Lock()
	defer bw.bufferMux.Unlock()

	if len(bw.buffer) >= bw.batchSize || time.Since(bw.lastFlush) >= bw.flushInterval {
		if len(bw.buffer) > 0 {
			bw.flushLocked()
		}
	}
}

func (bw *APIRequestEventBatchWriter) flushLocked() {
	if len(bw.buffer) == 0 {
		return
	}

	// Send buffer to writer
	events := make([]services.APIRequestEvent, len(bw.buffer))
	copy(events, bw.buffer)
	bw.buffer = bw.buffer[:0] // Clear buffer
	bw.lastFlush = time.Now()

	go func() {
		defer func() {
			if r := recover(); r != nil {
				return
			}
		}()

		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		for _, event := range events {
			_ = bw.writer.WriteEvent(ctx, event)
		}
	}()
}

// WriteEvent adds an event to the buffer.
func (bw *APIRequestEventBatchWriter) WriteEvent(ctx context.Context, event services.APIRequestEvent) error {
	if bw == nil || bw.writer == nil {
		return fmt.Errorf("batch writer not initialized")
	}

	bw.bufferMux.Lock()
	bw.buffer = append(bw.buffer, event)
	bw.bufferMux.Unlock()

	bw.maybeFlush()
	return nil
}

// ForceFlush immediately flushes all buffered events.
func (bw *APIRequestEventBatchWriter) ForceFlush() {
	bw.bufferMux.Lock()
	bw.flushLocked()
	bw.bufferMux.Unlock()
}

// Close stops the background flusher, flushes remaining events, and waits
// for the flusher to finish. Safe to call multiple times.
func (bw *APIRequestEventBatchWriter) Close() {
	bw.closeOnce.Do(func() {
		close(bw.stopChan)
	})
	<-bw.flusherDone
}

// flushSynchronously writes buffered events on the calling goroutine.
func (bw *APIRequestEventBatchWriter) flushSynchronously() {
	bw.bufferMux.Lock()
	defer bw.bufferMux.Unlock()

	if len(bw.buffer) == 0 {
		return
	}
	events := make([]services.APIRequestEvent, len(bw.buffer))
	copy(events, bw.buffer)
	bw.buffer = bw.buffer[:0]
	bw.lastFlush = time.Now()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	for _, event := range events {
		_ = bw.writer.WriteEvent(ctx, event)
	}
}

// APIRequestEventsMiddlewareWithBatchWriter uses a batching writer for high-volume scenarios.
func APIRequestEventsMiddlewareWithBatchWriter(batchWriter *APIRequestEventBatchWriter) gin.HandlerFunc {
	if batchWriter == nil {
		return func(c *gin.Context) {
			c.Next()
		}
	}

	return func(c *gin.Context) {
		start := time.Now()
		c.Next()

		latencyMs := time.Since(start).Milliseconds()
		statusCode := c.Writer.Status()

		method := strings.ToUpper(c.Request.Method)
		path := c.Request.URL.Path
		service := "backend"

		rateLimited := uint8(0)
		if c.GetBool("rate_limited") {
			rateLimited = 1
		}

		var userID *string
		if userIDVal, exists := c.Get("user_id"); exists && userIDVal != nil {
			if uid, ok := userIDVal.(string); ok && uid != "" {
				userID = &uid
			}
		}

		correlationID := GetTraceID(c)
		clientIP := c.ClientIP()

		event := services.APIRequestEvent{
			EventDate:     start.Format("2006-01-02"),
			EventTime:     start.Format(time.RFC3339Nano),
			Service:       service,
			Route:         path,
			Method:        method,
			StatusCode:    uint16(statusCode),
			LatencyMs:     uint32(latencyMs),
			UserID:        userID,
			CorrelationID: correlationID,
			ClientIP:      clientIP,
			RateLimited:   rateLimited,
		}

		// Write to batch writer (async within the writer)
		_ = batchWriter.WriteEvent(c.Request.Context(), event)
	}
}
