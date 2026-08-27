package app

import (
	"context"
	"net/http"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
)

// TestRunServer_GracefulShutdownOnContextCancel verifies SIGTERM-style
// shutdown: cancellation drains the server and RunServer returns nil instead
// of blocking forever.
func TestRunServer_GracefulShutdownOnContextCancel(t *testing.T) {
	gin.SetMode(gin.TestMode)

	router := gin.New()
	router.GET("/api/v1/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"ok": true})
	})

	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() {
		done <- RunServer(ctx, router, "0")
	}()

	// Give the listener a moment to bind.
	time.Sleep(200 * time.Millisecond)
	cancel()

	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("expected nil error after graceful shutdown, got %v", err)
		}
	case <-time.After(10 * time.Second):
		t.Fatal("RunServer did not return after context cancellation")
	}
}
