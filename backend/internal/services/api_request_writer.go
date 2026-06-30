package services

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
)

const (
	apiRequestEventsTable  = "api_request_events"
	maxAPIRequestRows      = 1000
	defaultAPIRequestHours = 24
)

// APIRequestEvent represents a single API request event for ClickHouse storage.
// All fields map directly to the ClickHouse api_request_events table schema.
type APIRequestEvent struct {
	// Core event fields
	EventDate  string `json:"event_date"`
	EventTime  string `json:"event_time"`
	Service    string `json:"service"`
	Route      string `json:"route"`
	Method     string `json:"method"`
	StatusCode uint16 `json:"status_code"`
	LatencyMs  uint32 `json:"latency_ms"`

	// Context fields
	UserID        *string `json:"user_id,omitempty"`
	CorrelationID string  `json:"correlation_id"`
	ClientIP      string  `json:"client_ip"`

	// Telemetry fields
	RateLimited uint8 `json:"rate_limited"`
}

// APIRequestSummary provides aggregated API request metrics for a given time range.
type APIRequestSummary struct {
	Service      string  `json:"service"`
	Route        string  `json:"route"`
	Method       string  `json:"method"`
	RequestCount uint64  `json:"request_count"`
	AvgLatencyMs float64 `json:"avg_latency_ms"`
	ErrorCount   uint64  `json:"error_count"`
	RateLimited  uint64  `json:"rate_limited"`
}

// APIRequestLatencyDistribution provides latency percentile distribution.
type APIRequestLatencyDistribution struct {
	Service    string  `json:"service"`
	Route      string  `json:"route"`
	P50Ms      float64 `json:"p50_ms"`
	P95Ms      float64 `json:"p95_ms"`
	P99Ms      float64 `json:"p99_ms"`
	MaxMs      float64 `json:"max_ms"`
	SampleSize uint64  `json:"sample_size"`
}

// APIRequestWriter writes API request events to ClickHouse.
// It provides typed access to the api_request_events table for analytics.
type APIRequestWriter struct {
	reader *ClickHouseReader
}

// NewAPIRequestWriter creates a new APIRequestWriter.
// Returns nil when ClickHouse reads are disabled.
func NewAPIRequestWriter(reader *ClickHouseReader) *APIRequestWriter {
	if reader == nil {
		return nil
	}
	return &APIRequestWriter{reader: reader}
}

// WriteEvent writes a single API request event to ClickHouse.
// This is a best-effort write that fails closed (returns error but doesn't block callers).
//
// It delegates to WriteEvents so the single-event path uses the SAME real insert
// path as the batch path (writeRows -> ClickHouse HTTP JSONEachRow insert). It
// must never return success without attempting the write: callers (the API
// request events middleware) rely on this being truthful when ClickHouse is enabled.
func (w *APIRequestWriter) WriteEvent(ctx context.Context, event APIRequestEvent) error {
	if w == nil {
		return ErrClickHouseDisabled
	}
	return w.WriteEvents(ctx, []APIRequestEvent{event})
}

// WriteEvents writes multiple API request events in a batch.
func (w *APIRequestWriter) WriteEvents(ctx context.Context, events []APIRequestEvent) error {
	if w == nil {
		return ErrClickHouseDisabled
	}
	if len(events) == 0 {
		return nil
	}

	rows := make([]map[string]interface{}, len(events))
	for i, event := range events {
		row := map[string]interface{}{
			"event_date":     event.EventDate,
			"event_time":     event.EventTime,
			"service":        event.Service,
			"route":          event.Route,
			"method":         event.Method,
			"status_code":    int(event.StatusCode),
			"latency_ms":     int(event.LatencyMs),
			"correlation_id": event.CorrelationID,
			"client_ip":      event.ClientIP,
			"rate_limited":   int(event.RateLimited),
		}

		if event.UserID != nil {
			row["user_id"] = *event.UserID
		}

		rows[i] = row
	}

	return w.writeRows(ctx, rows)
}

func (w *APIRequestWriter) writeRows(ctx context.Context, rows []map[string]interface{}) error {
	if w.reader == nil {
		return ErrClickHouseDisabled
	}

	// Use the base ClickHouse reader to insert rows over the HTTP interface
	// using the JSONEachRow format (the same interface ClickHouseReader.Query
	// POSTs for reads). Values are passed in the request body, never interpolated.
	if len(rows) == 0 {
		return nil
	}

	// Ensure table exists (idempotent). Provisioning is otherwise handled
	// externally by the bot-side ClickHouse writer DDL.
	_ = w.ensureTable(ctx)

	// Use ClickHouse HTTP insert with JSONEachRow format
	insertSQL := fmt.Sprintf("INSERT INTO %s FORMAT JSONEachRow", apiRequestEventsTable)

	// Convert rows to JSONEachRow format
	var jsonRows [][]byte
	for _, row := range rows {
		jsonData, err := json.Marshal(row)
		if err != nil {
			continue // Skip malformed rows
		}
		jsonRows = append(jsonRows, jsonData)
	}

	if len(jsonRows) == 0 {
		return nil
	}

	// Join all JSON rows with newlines for JSONEachRow format
	body := strings.Join(stringBytes(jsonRows), "\n")

	// Execute the insert
	_, err := w.reader.Query(ctx, insertSQL+"\n"+body, nil)
	return err
}

func (w *APIRequestWriter) ensureTable(ctx context.Context) error {
	// For now, we assume table provisioning is handled externally
	// or by the ClickHouseReader DDL mechanism
	return nil
}

// stringBytes converts [][]byte to []string for Join
func stringBytes(bytesSlice [][]byte) []string {
	strings := make([]string, len(bytesSlice))
	for i, b := range bytesSlice {
		strings[i] = string(b)
	}
	return strings
}

// GetSummary returns aggregated API request metrics for a given service and time range.
func (w *APIRequestWriter) GetSummary(
	ctx context.Context,
	service string,
	hours int,
) ([]APIRequestSummary, error) {
	if w == nil {
		return nil, ErrClickHouseDisabled
	}
	if hours <= 0 {
		hours = defaultAPIRequestHours
	}

	// Values are bound server-side via ClickHouse {name:Type} placeholders
	query := fmt.Sprintf(`
SELECT
    service,
    route,
    method,
    count() AS request_count,
    avg(latency_ms) AS avg_latency_ms,
    countIf(status_code >= 400) AS error_count,
    sum(rate_limited) AS rate_limited
FROM %s
WHERE service = {service:String}
  AND event_time >= now() - toIntervalHour({hours:UInt32})
GROUP BY service, route, method
ORDER BY request_count DESC
LIMIT {limit:UInt32}`, apiRequestEventsTable)

	rows, err := w.reader.Query(ctx, query, map[string]string{
		"service": service,
		"hours":   fmt.Sprintf("%d", hours),
		"limit":   fmt.Sprintf("%d", maxAPIRequestRows),
	})
	if err != nil {
		return nil, err
	}

	return DecodeRows[APIRequestSummary](rows)
}

// GetLatencyDistribution returns latency percentile distribution for API routes.
func (w *APIRequestWriter) GetLatencyDistribution(
	ctx context.Context,
	service string,
	hours int,
) ([]APIRequestLatencyDistribution, error) {
	if w == nil {
		return nil, ErrClickHouseDisabled
	}
	if hours <= 0 {
		hours = defaultAPIRequestHours
	}

	// ClickHouse quantiles function for latency distribution
	query := fmt.Sprintf(`
SELECT
    service,
    route,
    quantile(0.50)(latency_ms) AS p50_ms,
    quantile(0.95)(latency_ms) AS p95_ms,
    quantile(0.99)(latency_ms) AS p99_ms,
    max(latency_ms) AS max_ms,
    count() AS sample_size
FROM %s
WHERE service = {service:String}
  AND event_time >= now() - toIntervalHour({hours:UInt32})
GROUP BY service, route
ORDER BY sample_size DESC
LIMIT {limit:UInt32}`, apiRequestEventsTable)

	rows, err := w.reader.Query(ctx, query, map[string]string{
		"service": service,
		"hours":   fmt.Sprintf("%d", hours),
		"limit":   fmt.Sprintf("%d", maxAPIRequestRows),
	})
	if err != nil {
		return nil, err
	}

	return DecodeRows[APIRequestLatencyDistribution](rows)
}

// GetHighLatencyRequests returns the slowest API requests for debugging.
func (w *APIRequestWriter) GetHighLatencyRequests(
	ctx context.Context,
	service string,
	thresholdMs int,
	limit int,
) ([]APIRequestEvent, error) {
	if w == nil {
		return nil, ErrClickHouseDisabled
	}
	if limit <= 0 {
		limit = 50
	}
	if thresholdMs <= 0 {
		thresholdMs = 1000 // 1 second default
	}

	query := fmt.Sprintf(`
SELECT
    event_date,
    event_time,
    service,
    route,
    method,
    status_code,
    latency_ms,
    user_id,
    correlation_id,
    client_ip,
    rate_limited
FROM %s
WHERE service = {service:String}
  AND latency_ms >= {threshold:UInt32}
  AND event_time >= now() - toIntervalHour(24)
ORDER BY latency_ms DESC
LIMIT {limit:UInt32}`, apiRequestEventsTable)

	rows, err := w.reader.Query(ctx, query, map[string]string{
		"service":   service,
		"threshold": fmt.Sprintf("%d", thresholdMs),
		"limit":     fmt.Sprintf("%d", limit),
	})
	if err != nil {
		return nil, err
	}

	return DecodeRows[APIRequestEvent](rows)
}

// ErrorRateResult defines the structure for error rate metrics.
type ErrorRateResult struct {
	Route      string  `json:"route"`
	Method     string  `json:"method"`
	TotalCount uint64  `json:"total_count"`
	ErrorCount uint64  `json:"error_count"`
	ErrorRate  float64 `json:"error_rate"`
}

// GetErrorRate returns error rate metrics for API routes.
func (w *APIRequestWriter) GetErrorRate(
	ctx context.Context,
	service string,
	hours int,
) ([]ErrorRateResult, error) {
	if w == nil {
		return nil, ErrClickHouseDisabled
	}
	if hours <= 0 {
		hours = defaultAPIRequestHours
	}

	query := fmt.Sprintf(`
SELECT
    route,
    method,
    count() AS total_count,
    countIf(status_code >= 400) AS error_count,
    (countIf(status_code >= 400) * 100.0 / count()) AS error_rate
FROM %s
WHERE service = {service:String}
  AND event_time >= now() - toIntervalHour({hours:UInt32})
GROUP BY route, method
HAVING total_count > 0
ORDER BY error_rate DESC
LIMIT {limit:UInt32}`, apiRequestEventsTable)

	rows, err := w.reader.Query(ctx, query, map[string]string{
		"service": service,
		"hours":   fmt.Sprintf("%d", hours),
		"limit":   fmt.Sprintf("%d", maxAPIRequestRows),
	})
	if err != nil {
		return nil, err
	}

	return DecodeRows[ErrorRateResult](rows)
}

// Check if the interface is properly implemented
var _ error = ErrClickHouseDisabled
