package services

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/dydx-trading-bot/backend-go/config"
)

// TestAPIRequestWriter_WriteEventPerformsRealInsert proves the Phase 1 fix:
// WriteEvent actually performs a ClickHouse JSONEachRow insert (it previously
// returned nil without writing).
func TestAPIRequestWriter_WriteEventPerformsRealInsert(t *testing.T) {
	var gotBody string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		gotBody = string(b)
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(""))
	}))
	defer srv.Close()

	reader := NewClickHouseReaderWithClient(config.ClickHouseSettings{Enabled: true, URL: srv.URL}, srv.Client())
	if reader == nil {
		t.Fatal("expected non-nil reader")
	}
	writer := NewAPIRequestWriter(reader)

	err := writer.WriteEvent(context.Background(), APIRequestEvent{
		EventDate:     "2024-01-02",
		EventTime:     "2024-01-02T03:04:05.000Z",
		Service:       "backend",
		Route:         "/api/v1/backtests",
		Method:        "GET",
		StatusCode:    200,
		LatencyMs:     42,
		CorrelationID: "trace-1",
		ClientIP:      "10.0.0.1",
		RateLimited:   0,
	})
	if err != nil {
		t.Fatalf("WriteEvent returned error: %v", err)
	}

	if !strings.Contains(gotBody, "INSERT INTO api_request_events FORMAT JSONEachRow") {
		t.Fatalf("expected a real ClickHouse INSERT in request body, got %q", gotBody)
	}
	for _, want := range []string{`"client_ip":"10.0.0.1"`, `"route":"/api/v1/backtests"`, `"status_code":200`} {
		if !strings.Contains(gotBody, want) {
			t.Fatalf("request body missing %q, got %q", want, gotBody)
		}
	}
}

// TestAPIRequestWriter_WriteEventFailsClosedOnNon2xx proves WriteEvent surfaces a
// ClickHouse error instead of silently reporting success.
func TestAPIRequestWriter_WriteEventFailsClosedOnNon2xx(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "boom", http.StatusInternalServerError)
	}))
	defer srv.Close()

	reader := NewClickHouseReaderWithClient(config.ClickHouseSettings{Enabled: true, URL: srv.URL}, srv.Client())
	writer := NewAPIRequestWriter(reader)

	if err := writer.WriteEvent(context.Background(), APIRequestEvent{Service: "backend"}); err == nil {
		t.Fatal("expected WriteEvent to fail closed on non-2xx ClickHouse response")
	}
}

// TestAPIRequestWriter_WriteEventNilDisabled proves the nil/disabled writer fails
// closed rather than pretending to write.
func TestAPIRequestWriter_WriteEventNilDisabled(t *testing.T) {
	// A nil *APIRequestWriter (NATS/ClickHouse never constructed) fails closed.
	var nilWriter *APIRequestWriter
	if err := nilWriter.WriteEvent(context.Background(), APIRequestEvent{}); err != ErrClickHouseDisabled {
		t.Fatalf("nil writer: expected ErrClickHouseDisabled, got %v", err)
	}
	// A writer whose underlying reader is nil (ClickHouse disabled) must fail closed.
	w := &APIRequestWriter{reader: nil}
	if err := w.WriteEvent(context.Background(), APIRequestEvent{}); err != ErrClickHouseDisabled {
		t.Fatalf("disabled writer: expected ErrClickHouseDisabled, got %v", err)
	}
}
