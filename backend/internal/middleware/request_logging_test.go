package middleware

import (
	"bytes"
	"errors"
	"log"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
)

func captureStdLogOutput(t *testing.T, run func()) string {
	t.Helper()

	originalWriter := log.Writer()
	originalFlags := log.Flags()
	originalPrefix := log.Prefix()

	var buffer bytes.Buffer
	log.SetOutput(&buffer)
	log.SetFlags(0)
	log.SetPrefix("")
	defer func() {
		log.SetOutput(originalWriter)
		log.SetFlags(originalFlags)
		log.SetPrefix(originalPrefix)
	}()

	run()
	return buffer.String()
}

func TestRequestLoggingMiddleware_LogsErrorContextOnServerError(t *testing.T) {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(RequestTraceMiddleware())
	r.Use(RequestLoggingMiddleware())

	r.GET("/api/v1/settings", func(c *gin.Context) {
		_ = c.Error(errors.New("settings query failed"))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "db failed"})
	})

	output := captureStdLogOutput(t, func() {
		req := httptest.NewRequest(http.MethodGet, "/api/v1/settings", nil)
		req.Header.Set(TraceIDHeader, "req-test-500")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusInternalServerError {
			t.Fatalf("expected 500, got %d", w.Code)
		}
	})

	if !strings.Contains(output, "request trace_id=req-test-500") {
		t.Fatalf("expected base request log, got %q", output)
	}
	if !strings.Contains(output, "request_error trace_id=req-test-500") {
		t.Fatalf("expected request_error log, got %q", output)
	}
	if !strings.Contains(output, "route=/api/v1/settings") {
		t.Fatalf("expected route in error log, got %q", output)
	}
	if !strings.Contains(output, "handler=") {
		t.Fatalf("expected handler in error log, got %q", output)
	}
	if !strings.Contains(output, "status=500") {
		t.Fatalf("expected 500 in error log, got %q", output)
	}
	if !strings.Contains(output, "last_error=\"settings query failed\"") {
		t.Fatalf("expected last error in error log, got %q", output)
	}
}

func TestRequestLoggingMiddleware_DoesNotEmitErrorLogOnSuccess(t *testing.T) {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(RequestTraceMiddleware())
	r.Use(RequestLoggingMiddleware())

	r.GET("/api/v1/settings/schema", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"ok": true})
	})

	output := captureStdLogOutput(t, func() {
		req := httptest.NewRequest(http.MethodGet, "/api/v1/settings/schema", nil)
		req.Header.Set(TraceIDHeader, "req-test-200")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("expected 200, got %d", w.Code)
		}
	})

	if !strings.Contains(output, "request trace_id=req-test-200") {
		t.Fatalf("expected base request log, got %q", output)
	}
	if strings.Contains(output, "request_error") {
		t.Fatalf("did not expect request_error log on success, got %q", output)
	}
}
