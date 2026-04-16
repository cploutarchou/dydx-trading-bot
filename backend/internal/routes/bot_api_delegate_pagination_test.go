package routes

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestParseBacktestListOffsetAcceptsFrontendSkipAlias(t *testing.T) {
	gin.SetMode(gin.TestMode)

	tests := []struct {
		name     string
		query    string
		expected int
	}{
		{name: "skip alias", query: "skip=200&limit=50", expected: 200},
		{name: "offset canonical", query: "offset=150&limit=50", expected: 150},
		{name: "offset wins when both are present", query: "skip=200&offset=300", expected: 300},
		{name: "negative skip ignored", query: "skip=-1", expected: 0},
		{name: "invalid offset ignored after valid skip", query: "skip=75&offset=bad", expected: 75},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			w := httptest.NewRecorder()
			c, _ := gin.CreateTestContext(w)
			req := httptest.NewRequest(http.MethodGet, "/api/v1/backtests?"+tt.query, nil)
			c.Request = req

			if got := parseBacktestListOffset(c); got != tt.expected {
				t.Fatalf("expected offset %d, got %d", tt.expected, got)
			}
		})
	}
}
