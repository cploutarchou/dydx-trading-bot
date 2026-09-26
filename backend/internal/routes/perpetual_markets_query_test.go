package routes

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestParsePerpetualMarketsQuery(t *testing.T) {
	gin.SetMode(gin.TestMode)

	tests := []struct {
		name            string
		query           string
		wantLimit       int
		wantIncludeSett bool
	}{
		{name: "defaults", query: "", wantLimit: 0, wantIncludeSett: false},
		{name: "limit forwarded", query: "limit=25", wantLimit: 25, wantIncludeSett: false},
		{name: "negative limit ignored", query: "limit=-5", wantLimit: 0, wantIncludeSett: false},
		{name: "non-numeric limit ignored", query: "limit=abc", wantLimit: 0, wantIncludeSett: false},
		{name: "include_settled true", query: "include_settled=true", wantLimit: 0, wantIncludeSett: true},
		{name: "include_settled 1", query: "include_settled=1", wantLimit: 0, wantIncludeSett: true},
		{name: "include_settled mixed case", query: "include_settled=TRUE", wantLimit: 0, wantIncludeSett: true},
		{name: "include_settled false", query: "include_settled=false", wantLimit: 0, wantIncludeSett: false},
		{name: "include_settled junk", query: "include_settled=maybe", wantLimit: 0, wantIncludeSett: false},
		{name: "both", query: "limit=3&include_settled=yes", wantLimit: 3, wantIncludeSett: true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			w := httptest.NewRecorder()
			c, _ := gin.CreateTestContext(w)
			c.Request = httptest.NewRequest(http.MethodGet, "/api/v1/markets/perpetuals?"+tt.query, nil)

			limit, includeSettled := parsePerpetualMarketsQuery(c)
			if limit != tt.wantLimit {
				t.Fatalf("limit: expected %d, got %d", tt.wantLimit, limit)
			}
			if includeSettled != tt.wantIncludeSett {
				t.Fatalf("include_settled: expected %t, got %t", tt.wantIncludeSett, includeSettled)
			}
		})
	}
}
