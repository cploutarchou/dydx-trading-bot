package routes

import (
	"database/sql"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	_ "modernc.org/sqlite"
)

// The credential endpoints share one tight per-IP budget; other clients and
// non-credential auth routes are unaffected.
func TestAuthCredentialEndpointsAreRateLimitedPerIP(t *testing.T) {
	gin.SetMode(gin.TestMode)
	// An empty in-memory database: handlers may answer 4xx/5xx, which is fine
	// here; the test only distinguishes "limited" from "reached the handler".
	database, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	t.Cleanup(func() { _ = database.Close() })

	router := gin.New()
	router.Use(gin.Recovery())
	RegisterAuthRoutes(router, database)

	post := func(path, remoteAddr string) int {
		req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(""))
		req.Header.Set("Content-Type", "application/json")
		req.RemoteAddr = remoteAddr
		res := httptest.NewRecorder()
		router.ServeHTTP(res, req)
		return res.Code
	}

	attacker := "203.0.113.50:40000"
	paths := []string{"/api/v1/auth/login", "/api/v1/auth/forgot-password", "/api/v1/auth/reset-password", "/api/v1/auth/register"}
	for i := 0; i < authCredentialBurst; i++ {
		if code := post(paths[i%len(paths)], attacker); code == http.StatusTooManyRequests {
			t.Fatalf("request %d was limited inside the burst of %d", i+1, authCredentialBurst)
		}
	}
	for _, path := range paths {
		if code := post(path, attacker); code != http.StatusTooManyRequests {
			t.Fatalf("%s after the burst: got %d, want 429 (budget must be shared across endpoints)", path, code)
		}
	}

	if code := post("/api/v1/auth/login", "198.51.100.20:40000"); code == http.StatusTooManyRequests {
		t.Fatal("a different client IP must have its own budget")
	}
}
