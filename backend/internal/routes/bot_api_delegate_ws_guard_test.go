package routes

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestEnsureSafeUpstreamPathSegment(t *testing.T) {
	cases := []struct {
		name    string
		value   string
		allowed bool
	}{
		{"plain id", "bot-1", true},
		{"hex run id", "0dbb26d46985", true},
		{"dots and underscores", "run_name.1-beta", true},
		{"empty", "", false},
		{"path traversal", "..", false},
		{"slash injection", "bot/1", false},
		{"encoded slash", "bot%2F1", false},
		{"query injection", "bot?x=1", false},
		{"fragment injection", "bot#x", false},
		{"leading dot", ".hidden", false},
		{"leading dash", "-flag", false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			gin.SetMode(gin.TestMode)
			w := httptest.NewRecorder()
			c, _ := gin.CreateTestContext(w)
			c.Request = httptest.NewRequest(http.MethodGet, "/ws/bots/x", nil)

			if got := ensureSafeUpstreamPathSegment(c, tc.value); got != tc.allowed {
				t.Fatalf("ensureSafeUpstreamPathSegment(%q) = %v, want %v", tc.value, got, tc.allowed)
			}
			if !tc.allowed && w.Code != http.StatusBadRequest {
				t.Fatalf("expected 400 for %q, got %d", tc.value, w.Code)
			}
		})
	}
}

func TestRequireBotInstanceOwnershipMiddleware(t *testing.T) {
	register := func() (*httptest.ResponseRecorder, *gin.Context) {
		gin.SetMode(gin.TestMode)
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest(http.MethodGet, "/ws/bots/bot-1", nil)
		return w, c
	}

	t.Run("skips when no instance id param", func(t *testing.T) {
		w, c := register()
		c.Params = nil
		requireBotInstanceOwnership(nil)(c)
		if w.Code != http.StatusOK {
			t.Fatalf("expected pass-through, got %d", w.Code)
		}
	})

	t.Run("admin bypasses", func(t *testing.T) {
		w, c := register()
		c.Params = gin.Params{{Key: "instance_id", Value: "bot-1"}}
		c.Set("is_admin", true)
		requireBotInstanceOwnership(nil)(c)
		if w.Code != http.StatusOK {
			t.Fatalf("expected admin bypass, got %d", w.Code)
		}
	})

	t.Run("missing registry fails closed 503", func(t *testing.T) {
		w, c := register()
		c.Params = gin.Params{{Key: "instance_id", Value: "bot-1"}}
		c.Set("user_id", 7)
		requireBotInstanceOwnership(nil)(c)
		if w.Code != http.StatusServiceUnavailable {
			t.Fatalf("expected 503 when ownership registry unavailable, got %d", w.Code)
		}
		if c.IsAborted() != true {
			t.Fatal("expected request aborted")
		}
	})

	t.Run("missing user context fails closed 401", func(t *testing.T) {
		// nil repo still must reject unknown users before any proxying.
		w, c := register()
		c.Params = gin.Params{{Key: "instance_id", Value: "bot-1"}}
		requireBotInstanceOwnership(nil)(c)
		if w.Code != http.StatusUnauthorized && w.Code != http.StatusServiceUnavailable {
			t.Fatalf("expected 401/503, got %d", w.Code)
		}
	})
}
