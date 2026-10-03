package services

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
)

func captureUpstreamQuery(t *testing.T, call func(c *BotAPIClient) error) url.Values {
	t.Helper()
	var got url.Values
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got = r.URL.Query()
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{"ok": true})
	}))
	defer srv.Close()

	if err := call(NewBotAPIClient(srv.URL, "")); err != nil {
		t.Fatalf("upstream call failed: %v", err)
	}
	return got
}

func TestQuickDeployBot_InstanceNameCannotInjectQueryParameters(t *testing.T) {
	const hostile = "desk&auto_start=true&extra=1"

	got := captureUpstreamQuery(t, func(c *BotAPIClient) error {
		_, err := c.QuickDeployBot(hostile, false, map[string]interface{}{})
		return err
	})

	if len(got) != 2 {
		t.Fatalf("upstream saw %d query keys (%v), want exactly instance_name and auto_start", len(got), got)
	}
	if got.Get("instance_name") != hostile {
		t.Fatalf("instance_name = %q, want the literal input %q", got.Get("instance_name"), hostile)
	}
	if got.Get("auto_start") != "false" {
		t.Fatalf("auto_start = %q, want false (caller value must not be overridden)", got.Get("auto_start"))
	}
}

func TestGetAdvancedPerformanceMetrics_BenchmarkIsQueryEscaped(t *testing.T) {
	const benchmark = "BTC+ETH&window=1"

	got := captureUpstreamQuery(t, func(c *BotAPIClient) error {
		_, err := c.GetAdvancedPerformanceMetrics("run-1", benchmark)
		return err
	})

	if len(got) != 1 || got.Get("benchmark") != benchmark {
		t.Fatalf("upstream query = %v, want only benchmark=%q", got, benchmark)
	}
}
