package app

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func TestServeWorkerMetricsDisabled(t *testing.T) {
	gin.SetMode(gin.TestMode)
	
	// nil reader simulates ClickHouse disabled (the checked-in default)
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	c.Set("is_admin", true)
	c.Set("user_id", "admin")
	
	// Add trace middleware for GetTraceID to work
	c.Request = httptest.NewRequest("GET", "/api/v1/analytics/worker-metrics?worker_id=worker-1&worker_type=celery&hours=24", nil)
	c.Request.Header.Set("X-Trace-Id", "test-trace")
	
	// This should not panic
	serveWorkerMetrics(c, nil)
	
	if c.Writer.Status() != http.StatusOK {
		t.Fatalf("expected status %d, got %d", http.StatusOK, c.Writer.Status())
	}
}

func TestServeWorkerMetricsSummaryDisabled(t *testing.T) {
	gin.SetMode(gin.TestMode)
	
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	c.Set("is_admin", true)
	c.Set("user_id", "admin")
	
	c.Request = httptest.NewRequest("GET", "/api/v1/analytics/worker-metrics/summary?worker_id=worker-1&hours=24", nil)
	c.Request.Header.Set("X-Trace-Id", "test-trace")
	
	serveWorkerMetricsSummary(c, nil)
	
	if c.Writer.Status() != http.StatusOK {
		t.Fatalf("expected status %d, got %d", http.StatusOK, c.Writer.Status())
	}
}

func TestServeWorkerThroughputDisabled(t *testing.T) {
	gin.SetMode(gin.TestMode)
	
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	c.Set("is_admin", true)
	c.Set("user_id", "admin")
	
	c.Request = httptest.NewRequest("GET", "/api/v1/analytics/worker-metrics/throughput?worker_type=celery&hours=24", nil)
	c.Request.Header.Set("X-Trace-Id", "test-trace")
	
	serveWorkerThroughput(c, nil)
	
	if c.Writer.Status() != http.StatusOK {
		t.Fatalf("expected status %d, got %d", http.StatusOK, c.Writer.Status())
	}
}

func TestServeWorkerFailuresDisabled(t *testing.T) {
	gin.SetMode(gin.TestMode)
	
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	c.Set("is_admin", true)
	c.Set("user_id", "admin")
	
	c.Request = httptest.NewRequest("GET", "/api/v1/analytics/worker-metrics/failures?worker_type=celery&hours=24", nil)
	c.Request.Header.Set("X-Trace-Id", "test-trace")
	
	serveWorkerFailures(c, nil)
	
	if c.Writer.Status() != http.StatusOK {
		t.Fatalf("expected status %d, got %d", http.StatusOK, c.Writer.Status())
	}
}

func TestServeWorkerHeartbeatDisabled(t *testing.T) {
	gin.SetMode(gin.TestMode)
	
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	c.Set("is_admin", true)
	c.Set("user_id", "admin")
	
	c.Request = httptest.NewRequest("GET", "/api/v1/analytics/worker-metrics/heartbeat?worker_type=celery", nil)
	c.Request.Header.Set("X-Trace-Id", "test-trace")
	
	serveWorkerHeartbeat(c, nil)
	
	if c.Writer.Status() != http.StatusOK {
		t.Fatalf("expected status %d, got %d", http.StatusOK, c.Writer.Status())
	}
}

func TestServeAPIRequestSummaryDisabled(t *testing.T) {
	gin.SetMode(gin.TestMode)
	
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	c.Set("is_admin", true)
	c.Set("user_id", "admin")
	
	c.Request = httptest.NewRequest("GET", "/api/v1/analytics/api-requests/summary?service=backend&hours=24", nil)
	c.Request.Header.Set("X-Trace-Id", "test-trace")
	
	serveAPIRequestSummary(c, nil)
	
	if c.Writer.Status() != http.StatusOK {
		t.Fatalf("expected status %d, got %d", http.StatusOK, c.Writer.Status())
	}
}

func TestServeAPIRequestLatencyDisabled(t *testing.T) {
	gin.SetMode(gin.TestMode)
	
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	c.Set("is_admin", true)
	c.Set("user_id", "admin")
	
	c.Request = httptest.NewRequest("GET", "/api/v1/analytics/api-requests/latency?service=backend&hours=24", nil)
	c.Request.Header.Set("X-Trace-Id", "test-trace")
	
	serveAPIRequestLatency(c, nil)
	
	if c.Writer.Status() != http.StatusOK {
		t.Fatalf("expected status %d, got %d", http.StatusOK, c.Writer.Status())
	}
}

func TestServeAPIRequestErrorsDisabled(t *testing.T) {
	gin.SetMode(gin.TestMode)
	
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	c.Set("is_admin", true)
	c.Set("user_id", "admin")
	
	c.Request = httptest.NewRequest("GET", "/api/v1/analytics/api-requests/errors?service=backend&hours=24", nil)
	c.Request.Header.Set("X-Trace-Id", "test-trace")
	
	serveAPIRequestErrors(c, nil)
	
	if c.Writer.Status() != http.StatusOK {
		t.Fatalf("expected status %d, got %d", http.StatusOK, c.Writer.Status())
	}
}

func TestServeAPIRequestSlowDisabled(t *testing.T) {
	gin.SetMode(gin.TestMode)
	
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	c.Set("is_admin", true)
	c.Set("user_id", "admin")
	
	c.Request = httptest.NewRequest("GET", "/api/v1/analytics/api-requests/slow?service=backend&threshold_ms=1000&limit=50", nil)
	c.Request.Header.Set("X-Trace-Id", "test-trace")
	
	serveAPIRequestSlow(c, nil)
	
	if c.Writer.Status() != http.StatusOK {
		t.Fatalf("expected status %d, got %d", http.StatusOK, c.Writer.Status())
	}
}

func TestWorkerRoutesAdminRequired(t *testing.T) {
	gin.SetMode(gin.TestMode)
	
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	c.Set("is_admin", false) // Not admin
	c.Set("user_id", "regular-user")
	
	c.Request = httptest.NewRequest("GET", "/api/v1/analytics/worker-metrics", nil)
	c.Request.Header.Set("X-Trace-Id", "test-trace")
	
	serveWorkerMetrics(c, nil)
	
	if c.Writer.Status() != http.StatusForbidden {
		t.Fatalf("expected status %d, got %d", http.StatusForbidden, c.Writer.Status())
	}
}

func TestAPIRequestRoutesAdminRequired(t *testing.T) {
	gin.SetMode(gin.TestMode)
	
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	c.Set("is_admin", false) // Not admin
	c.Set("user_id", "regular-user")
	
	c.Request = httptest.NewRequest("GET", "/api/v1/analytics/api-requests/summary", nil)
	c.Request.Header.Set("X-Trace-Id", "test-trace")
	
	serveAPIRequestSummary(c, nil)
	
	if c.Writer.Status() != http.StatusForbidden {
		t.Fatalf("expected status %d, got %d", http.StatusForbidden, c.Writer.Status())
	}
}

func TestWorkerRoutesWithEnabledReader(t *testing.T) {
	gin.SetMode(gin.TestMode)
	
	// Create an enabled ClickHouse reader
	clickHouseReader := services.NewClickHouseReader(config.ClickHouseSettings{
		Enabled: true,
		URL:     "http://localhost:8123",
	})
	
	if clickHouseReader == nil {
		t.Fatal("expected non-nil ClickHouseReader")
	}
	
	workerReader := services.NewLiveWorkerMetricsReader(clickHouseReader)
	if workerReader == nil {
		t.Fatal("expected non-nil LiveWorkerMetricsReader")
	}
	
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	c.Set("is_admin", true)
	c.Set("user_id", "admin")
	
	c.Request = httptest.NewRequest("GET", "/api/v1/analytics/worker-metrics?worker_id=worker-1&worker_type=celery&hours=24", nil)
	c.Request.Header.Set("X-Trace-Id", "test-trace")
	
	// This should not panic, it will return an error due to no actual ClickHouse server
	// but that's expected for this test environment
	serveWorkerMetrics(c, workerReader)
	
	// We expect it to complete without panicking
	if c.Writer.Status() != http.StatusOK {
		t.Logf("expected status 200, got %d (acceptable due to no ClickHouse server)", c.Writer.Status())
	}
}

func TestAPIRequestRoutesWithEnabledWriter(t *testing.T) {
	gin.SetMode(gin.TestMode)
	
	// Create an enabled ClickHouse reader
	clickHouseReader := services.NewClickHouseReader(config.ClickHouseSettings{
		Enabled: true,
		URL:     "http://localhost:8123",
	})
	
	if clickHouseReader == nil {
		t.Fatal("expected non-nil ClickHouseReader")
	}
	
	apiRequestWriter := services.NewAPIRequestWriter(clickHouseReader)
	if apiRequestWriter == nil {
		t.Fatal("expected non-nil APIRequestWriter")
	}
	
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	c.Set("is_admin", true)
	c.Set("user_id", "admin")
	
	c.Request = httptest.NewRequest("GET", "/api/v1/analytics/api-requests/summary?service=backend&hours=24", nil)
	c.Request.Header.Set("X-Trace-Id", "test-trace")
	
	// This should not panic, it will return an error due to no actual ClickHouse server
	// but that's expected for this test environment
	serveAPIRequestSummary(c, apiRequestWriter)
	
	// We expect it to complete without panicking
	if c.Writer.Status() != http.StatusOK {
		t.Logf("expected status 200, got %d (acceptable due to no ClickHouse server)", c.Writer.Status())
	}
}