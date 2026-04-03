package services

import (
	"context"
	"errors"
	"net"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// ── helpers ──────────────────────────────────────────────────────────────────

// testNetTimeout is a net.Error whose Timeout() returns true.
type testNetTimeout struct{ msg string }

func (e *testNetTimeout) Error() string   { return e.msg }
func (e *testNetTimeout) Timeout() bool   { return true }
func (e *testNetTimeout) Temporary() bool { return false }

// ── classifyTransportError unit tests ────────────────────────────────────────

func TestClassifyTransportError_ContextDeadline_Returns504(t *testing.T) {
	got := classifyTransportError("GET", "http://127.0.0.1:8889/api/health", context.DeadlineExceeded)

	if got.StatusCode != http.StatusGatewayTimeout {
		t.Fatalf("want 504, got %d", got.StatusCode)
	}
	if !errors.Is(got, context.DeadlineExceeded) {
		t.Fatal("expected errors.Is to find DeadlineExceeded through Unwrap chain")
	}
}

func TestClassifyTransportError_NetTimeout_Returns504(t *testing.T) {
	netErr := &net.OpError{Op: "dial", Net: "tcp", Err: &testNetTimeout{msg: "i/o timeout"}}
	got := classifyTransportError("POST", "http://127.0.0.1:8889/api/v1/backtests", netErr)

	if got.StatusCode != http.StatusGatewayTimeout {
		t.Fatalf("want 504, got %d", got.StatusCode)
	}
}

func TestClassifyTransportError_ConnectionRefused_Returns502(t *testing.T) {
	err := errors.New("dial tcp 127.0.0.1:8889: connect: connection refused")
	got := classifyTransportError("GET", "http://127.0.0.1:8889/api/v1/bots", err)

	if got.StatusCode != http.StatusBadGateway {
		t.Fatalf("want 502, got %d", got.StatusCode)
	}
	if got.Endpoint != "http://127.0.0.1:8889/api/v1/bots" {
		t.Fatalf("unexpected endpoint: %q", got.Endpoint)
	}
}

func TestClassifyTransportError_WindowsActivelyRefused_Returns502(t *testing.T) {
	err := errors.New("No connection could be made because the target machine actively refused it")
	got := classifyTransportError("POST", "http://127.0.0.1:8889/api/v1/backtests/run", err)

	if got.StatusCode != http.StatusBadGateway {
		t.Fatalf("want 502, got %d", got.StatusCode)
	}
}

func TestClassifyTransportError_GenericTransportError_Returns502(t *testing.T) {
	err := errors.New("some unknown network failure")
	got := classifyTransportError("GET", "http://127.0.0.1:8889/api/v1/bots", err)

	if got.StatusCode != http.StatusBadGateway {
		t.Fatalf("want 502, got %d", got.StatusCode)
	}
}

func TestBotAPITransportError_Unwrap_ChainWorks(t *testing.T) {
	transportErr := &BotAPITransportError{
		StatusCode: http.StatusGatewayTimeout,
		Message:    "timed out",
		Endpoint:   "http://example.com",
		Cause:      context.DeadlineExceeded,
	}

	if !errors.Is(transportErr, context.DeadlineExceeded) {
		t.Fatal("expected errors.Is to find DeadlineExceeded through Unwrap")
	}
}

func TestBotAPITransportError_Error_IncludesEndpoint(t *testing.T) {
	e := &BotAPITransportError{
		StatusCode: http.StatusBadGateway,
		Message:    "connection refused",
		Endpoint:   "http://127.0.0.1:8889/api/health",
	}
	msg := e.Error()
	if msg == "" {
		t.Fatal("Error() returned empty string")
	}
	// The endpoint should appear in the string for log readability.
	if !contains(msg, "127.0.0.1") {
		t.Fatalf("expected endpoint in Error() output, got: %q", msg)
	}
}

func contains(s, sub string) bool {
	return len(s) >= len(sub) && (s == sub || len(sub) == 0 ||
		func() bool {
			for i := 0; i <= len(s)-len(sub); i++ {
				if s[i:i+len(sub)] == sub {
					return true
				}
			}
			return false
		}())
}

// ── makeRequest integration tests ─────────────────────────────────────────────

// TestMakeRequest_ConnectionRefused_ReturnsBotAPITransportError dials a port
// with nothing listening and expects a typed *BotAPITransportError with 502.
func TestMakeRequest_ConnectionRefused_ReturnsBotAPITransportError(t *testing.T) {
	// Start a server just to grab a free OS-assigned port, then immediately close it.
	dummy := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {}))
	closedURL := dummy.URL
	dummy.Close() // connection-refused after this point

	client := NewBotAPIClient(closedURL, "")
	_, err := client.HealthCheck()
	if err == nil {
		t.Fatal("expected error, got nil")
	}

	var transportErr *BotAPITransportError
	if !errors.As(err, &transportErr) {
		t.Fatalf("expected *BotAPITransportError, got %T: %v", err, err)
	}
	if transportErr.StatusCode != http.StatusBadGateway {
		t.Fatalf("want 502, got %d", transportErr.StatusCode)
	}
}

// TestMakeRequest_Timeout_ReturnsBotAPITransportError points the client at a
// server that never responds. A 50 ms client timeout keeps the test fast.
func TestMakeRequest_Timeout_ReturnsBotAPITransportError(t *testing.T) {
	hangServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Block until the client disconnects or the server is closed.
		<-r.Context().Done()
	}))
	t.Cleanup(hangServer.Close)

	fastClient := &http.Client{Timeout: 50 * time.Millisecond}
	client := NewBotAPIClient(hangServer.URL, "").WithHTTPClient(fastClient)

	_, err := client.HealthCheck()
	if err == nil {
		t.Fatal("expected timeout error, got nil")
	}

	var transportErr *BotAPITransportError
	if !errors.As(err, &transportErr) {
		t.Fatalf("expected *BotAPITransportError, got %T: %v", err, err)
	}
	if transportErr.StatusCode != http.StatusGatewayTimeout {
		t.Fatalf("want 504, got %d", transportErr.StatusCode)
	}
}

// TestMakeRequest_UpstreamHTTPError_ReturnsBotAPIError ensures non-transport HTTP
// errors (4xx/5xx responses) still return *BotAPIError and NOT *BotAPITransportError.
func TestMakeRequest_UpstreamHTTPError_ReturnsBotAPIError(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = w.Write([]byte(`{"error":"invalid token"}`))
	}))
	t.Cleanup(upstream.Close)

	client := NewBotAPIClient(upstream.URL, "bad-token")
	_, err := client.HealthCheck()
	if err == nil {
		t.Fatal("expected error, got nil")
	}

	var transportErr *BotAPITransportError
	if errors.As(err, &transportErr) {
		t.Fatalf("expected *BotAPIError, but got *BotAPITransportError: %v", err)
	}

	var apiErr *BotAPIError
	if !errors.As(err, &apiErr) {
		t.Fatalf("expected *BotAPIError, got %T: %v", err, err)
	}
	if apiErr.StatusCode != http.StatusUnauthorized {
		t.Fatalf("want 401, got %d", apiErr.StatusCode)
	}
}

