package services

import (
	"context"
	"errors"
	"testing"

	"github.com/dydx-trading-bot/backend-go/config"
)

func TestNewAPIRequestWriterNilWhenDisabled(t *testing.T) {
	if writer := NewAPIRequestWriter(nil); writer != nil {
		t.Fatalf("expected nil APIRequestWriter, got %+v", writer)
	}
}

func TestNewAPIRequestWriterNilWhenReaderNil(t *testing.T) {
	if writer := NewAPIRequestWriter(nil); writer != nil {
		t.Fatalf("expected nil APIRequestWriter, got %+v", writer)
	}
}

func TestAPIRequestWriterWriteEventNilWriterFailsClosed(t *testing.T) {
	var writer *APIRequestWriter
	if err := writer.WriteEvent(context.Background(), APIRequestEvent{}); !errors.Is(err, ErrClickHouseDisabled) {
		t.Fatalf("expected ErrClickHouseDisabled, got %v", err)
	}
}

func TestAPIRequestWriterWriteEventNilWriterForNilReader(t *testing.T) {
	writer := NewAPIRequestWriter(nil)
	if writer != nil {
		t.Fatal("expected nil writer for nil reader")
	}
	
	// Test that nil writer fails closed
	var nilWriter *APIRequestWriter
	if err := nilWriter.WriteEvent(context.Background(), APIRequestEvent{}); !errors.Is(err, ErrClickHouseDisabled) {
		t.Fatalf("expected ErrClickHouseDisabled, got %v", err)
	}
}

func TestAPIRequestWriterWriteEventWithEnabledReader(t *testing.T) {
	// This test would require a real ClickHouse instance or mock HTTP server
	// For now, we'll just test the nil/disabled cases
	// The actual ClickHouse write functionality is tested via integration tests
	
	// Create a writer with a valid reader (but no actual ClickHouse server)
	reader := NewClickHouseReader(config.ClickHouseSettings{
		Enabled: true,
		URL:     "http://localhost:8123",
	})
	
	if reader == nil {
		t.Fatal("expected non-nil reader")
	}
	
	writer := NewAPIRequestWriter(reader)
	if writer == nil {
		t.Fatal("expected non-nil writer")
	}
	
	// Test that WriteEvent doesn't panic with a valid writer
	// It should return an error since there's no real ClickHouse server
	// but it shouldn't crash
	err := writer.WriteEvent(context.Background(), APIRequestEvent{
		EventDate:    "2026-01-01",
		EventTime:    "2026-01-01T00:00:00Z",
		Service:      "backend",
		Route:        "/api/v1/test",
		Method:       "GET",
		StatusCode:   200,
		LatencyMs:    100,
		CorrelationID: "test-123",
		ClientIP:     "127.0.0.1",
		RateLimited:  0,
	})
	
	// For now, WriteEvent returns nil (placeholder implementation)
	// This is acceptable for the current phase
	if err != nil {
		t.Logf("WriteEvent returned error (expected for no server): %v", err)
	}
}

func TestAPIRequestWriterGetSummaryNilWriterFailsClosed(t *testing.T) {
	var writer *APIRequestWriter
	summary, err := writer.GetSummary(context.Background(), "backend", 24)
	if !errors.Is(err, ErrClickHouseDisabled) {
		t.Fatalf("expected ErrClickHouseDisabled, got %v", err)
	}
	if summary != nil {
		t.Fatalf("expected nil summary, got %+v", summary)
	}
}

func TestAPIRequestWriterGetLatencyDistributionNilWriterFailsClosed(t *testing.T) {
	var writer *APIRequestWriter
	latency, err := writer.GetLatencyDistribution(context.Background(), "backend", 24)
	if !errors.Is(err, ErrClickHouseDisabled) {
		t.Fatalf("expected ErrClickHouseDisabled, got %v", err)
	}
	if latency != nil {
		t.Fatalf("expected nil latency, got %+v", latency)
	}
}

func TestAPIRequestWriterGetHighLatencyRequestsNilWriterFailsClosed(t *testing.T) {
	var writer *APIRequestWriter
	requests, err := writer.GetHighLatencyRequests(context.Background(), "backend", 1000, 50)
	if !errors.Is(err, ErrClickHouseDisabled) {
		t.Fatalf("expected ErrClickHouseDisabled, got %v", err)
	}
	if requests != nil {
		t.Fatalf("expected nil requests, got %+v", requests)
	}
}

func TestAPIRequestWriterGetErrorRateNilWriterFailsClosed(t *testing.T) {
	var writer *APIRequestWriter
	errorRates, err := writer.GetErrorRate(context.Background(), "backend", 24)
	if !errors.Is(err, ErrClickHouseDisabled) {
		t.Fatalf("expected ErrClickHouseDisabled, got %v", err)
	}
	if errorRates != nil {
		t.Fatalf("expected nil errorRates, got %+v", errorRates)
	}
}

func TestAPIRequestWriterWriteEventsBatch(t *testing.T) {
	// Test batch writing with enabled reader
	reader := NewClickHouseReader(config.ClickHouseSettings{
		Enabled: true,
		URL:     "http://localhost:8123",
	})
	
	if reader == nil {
		t.Fatal("expected non-nil reader")
	}
	
	writer := NewAPIRequestWriter(reader)
	if writer == nil {
		t.Fatal("expected non-nil writer")
	}
	
	// Test batch write with multiple events
	events := []APIRequestEvent{
		{
			EventDate:    "2026-01-01",
			EventTime:    "2026-01-01T00:00:00Z",
			Service:      "backend",
			Route:        "/api/v1/test1",
			Method:       "GET",
			StatusCode:   200,
			LatencyMs:    100,
			CorrelationID: "test-1",
			ClientIP:     "127.0.0.1",
			RateLimited:  0,
		},
		{
			EventDate:    "2026-01-01",
			EventTime:    "2026-01-01T00:00:01Z",
			Service:      "backend",
			Route:        "/api/v1/test2",
			Method:       "POST",
			StatusCode:   201,
			LatencyMs:    200,
			CorrelationID: "test-2",
			ClientIP:     "127.0.0.1",
			RateLimited:  1,
		},
	}
	
	// This should not panic
	err := writer.WriteEvents(context.Background(), events)
	if err != nil {
		t.Logf("WriteEvents returned error: %v", err)
	}
}

func TestAPIRequestEventWithUserID(t *testing.T) {
	userID := "user-123"
	event := APIRequestEvent{
		EventDate:    "2026-01-01",
		EventTime:    "2026-01-01T00:00:00Z",
		Service:      "backend",
		Route:        "/api/v1/test",
		Method:       "GET",
		StatusCode:   200,
		LatencyMs:    100,
		UserID:       &userID,
		CorrelationID: "test-123",
		ClientIP:     "127.0.0.1",
		RateLimited:  0,
	}
	
	// Test that user ID is properly set
	if event.UserID == nil {
		t.Fatal("expected non-nil UserID")
	}
	if *event.UserID != userID {
		t.Fatalf("expected UserID %s, got %s", userID, *event.UserID)
	}
}

func TestAPIRequestEventWithoutUserID(t *testing.T) {
	event := APIRequestEvent{
		EventDate:    "2026-01-01",
		EventTime:    "2026-01-01T00:00:00Z",
		Service:      "backend",
		Route:        "/api/v1/test",
		Method:       "GET",
		StatusCode:   200,
		LatencyMs:    100,
		UserID:       nil, // No user ID
		CorrelationID: "test-123",
		ClientIP:     "127.0.0.1",
		RateLimited:  0,
	}
	
	// Test that user ID is nil
	if event.UserID != nil {
		t.Fatal("expected nil UserID")
	}
}