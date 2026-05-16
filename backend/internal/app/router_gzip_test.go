package app

import (
	"net/http"
	"testing"
)

func TestShouldCompressResponse_NilRequest(t *testing.T) {
	if isWebSocketUpgradeRequest(nil) {
		t.Fatal("expected nil request to not be treated as websocket upgrade")
	}
}

func TestShouldCompressResponse_RegularHTTPRequest(t *testing.T) {
	req, err := http.NewRequest(http.MethodGet, "http://localhost:8888/api/v1/backtests", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}

	if isWebSocketUpgradeRequest(req) {
		t.Fatal("expected standard HTTP request to not be websocket upgrade")
	}
}

func TestShouldCompressResponse_WebSocketUpgradeRequest(t *testing.T) {
	req, err := http.NewRequest(http.MethodGet, "http://localhost:8888/ws/strategies", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Connection", "keep-alive, Upgrade")
	req.Header.Set("Upgrade", "websocket")

	if !isWebSocketUpgradeRequest(req) {
		t.Fatal("expected websocket upgrade request to be detected")
	}
}
