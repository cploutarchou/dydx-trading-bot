package middleware

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestErrorHandlingMiddleware_LogsPanicWithRouteAndHandlerContext(t *testing.T) {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(RequestTraceMiddleware())
	r.Use(ErrorHandlingMiddleware())

	r.GET("/api/v1/panic", func(c *gin.Context) {
		panic("boom")
	})

	output := captureStdLogOutput(t, func() {
		req := httptest.NewRequest(http.MethodGet, "/api/v1/panic", nil)
		req.Header.Set(TraceIDHeader, "req-panic-123")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusInternalServerError {
			t.Fatalf("expected 500, got %d", w.Code)
		}
	})

	if !strings.Contains(output, "panic recovered trace_id=req-panic-123") {
		t.Fatalf("expected panic log with trace_id, got %q", output)
	}
	if !strings.Contains(output, "route=/api/v1/panic") {
		t.Fatalf("expected route in panic log, got %q", output)
	}
	if !strings.Contains(output, "handler=") {
		t.Fatalf("expected handler in panic log, got %q", output)
	}
	if !strings.Contains(output, "err=boom") {
		t.Fatalf("expected panic error in log, got %q", output)
	}
}
