package services

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/dydx-trading-bot/backend-go/config"
)

func TestNewClickHouseReaderNilWhenDisabled(t *testing.T) {
	if reader := NewClickHouseReader(config.ClickHouseSettings{Enabled: false}); reader != nil {
		t.Fatalf("expected nil reader when disabled, got %+v", reader)
	}
	if reader := NewClickHouseReader(config.ClickHouseSettings{Enabled: true}); reader != nil {
		t.Fatalf("expected nil reader when endpoint missing, got %+v", reader)
	}
}

func TestNewClickHouseReaderBuildsBaseURLFromHostPort(t *testing.T) {
	reader := NewClickHouseReader(config.ClickHouseSettings{
		Enabled:  true,
		Host:     "analytics.internal",
		Port:     8123,
		Database: "dydx_analytics",
		User:     "analytics",
		Password: "secret",
	})
	if reader == nil {
		t.Fatalf("expected non-nil reader")
	}
	if got, want := reader.baseURL, "http://analytics.internal:8123"; got != want {
		t.Fatalf("baseURL: got %q want %q", got, want)
	}
	if reader.database != "dydx_analytics" || reader.user != "analytics" || reader.password != "secret" {
		t.Fatalf("credentials not stored: %+v", reader)
	}

	secure := NewClickHouseReader(config.ClickHouseSettings{Enabled: true, Host: "analytics.internal", Port: 8443, Secure: true})
	if got, want := secure.baseURL, "https://analytics.internal:8443"; got != want {
		t.Fatalf("secure baseURL: got %q want %q", got, want)
	}
}

func TestNewClickHouseReaderPrefersExplicitURL(t *testing.T) {
	reader := NewClickHouseReader(config.ClickHouseSettings{
		Enabled: true,
		URL:     "http://ch-proxy.internal:8123/path",
	})
	if reader == nil {
		t.Fatalf("expected non-nil reader")
	}
	if got, want := reader.baseURL, "http://ch-proxy.internal:8123/path"; got != want {
		t.Fatalf("baseURL: got %q want %q", got, want)
	}
}

func TestClickHouseReaderQueryNilReaderFailsClosed(t *testing.T) {
	var reader *ClickHouseReader
	rows, err := reader.Query(context.Background(), "SELECT 1", nil)
	if !errors.Is(err, ErrClickHouseDisabled) {
		t.Fatalf("expected ErrClickHouseDisabled, got %v", err)
	}
	if rows != nil {
		t.Fatalf("expected nil rows, got %v", rows)
	}
}

func TestClickHouseReaderQueryParsesJSONEachRow(t *testing.T) {
	var (
		capturedRequest *http.Request
		capturedBody    string
	)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedRequest = r
		buf := new(strings.Builder)
		_, _ = io.Copy(buf, r.Body)
		capturedBody = buf.String()
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w,
			`{"position_id":"p1","unrealized_pnl":12.5}`+"\n"+
				`{"position_id":"p2","unrealized_pnl":-3.0}`+"\n")
	}))
	t.Cleanup(server.Close)

	reader := NewClickHouseReader(config.ClickHouseSettings{
		Enabled:  true,
		URL:      server.URL,
		Database: "dydx_analytics",
		User:     "analytics",
		Password: "secret",
	})
	if reader == nil {
		t.Fatalf("expected non-nil reader")
	}

	rows, err := reader.Query(context.Background(),
		"SELECT position_id, unrealized_pnl FROM position_snapshots WHERE instance_id = {instance_id:String}",
		map[string]string{"instance_id": "inst-1"})
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if len(rows) != 2 {
		t.Fatalf("expected 2 rows, got %d", len(rows))
	}

	var first struct {
		PositionID    string  `json:"position_id"`
		UnrealizedPnL float64 `json:"unrealized_pnl"`
	}
	if err := json.Unmarshal(rows[0], &first); err != nil {
		t.Fatalf("decode first row: %v", err)
	}
	if first.PositionID != "p1" || first.UnrealizedPnL != 12.5 {
		t.Fatalf("unexpected first row: %+v", first)
	}

	if capturedRequest == nil {
		t.Fatalf("no request captured")
	}
	if capturedRequest.Method != http.MethodPost {
		t.Fatalf("expected POST, got %s", capturedRequest.Method)
	}
	if got := capturedRequest.URL.Query().Get("database"); got != "dydx_analytics" {
		t.Fatalf("expected database param, got %q", got)
	}
	if got := capturedRequest.URL.Query().Get("param_instance_id"); got != "inst-1" {
		t.Fatalf("expected bound param_instance_id=inst-1, got %q", got)
	}
	if got := capturedRequest.Header.Get("X-ClickHouse-User"); got != "analytics" {
		t.Fatalf("expected auth user header, got %q", got)
	}
	if !strings.Contains(capturedBody, "FORMAT JSONEachRow") {
		t.Fatalf("expected FORMAT appended to body, got %q", capturedBody)
	}
	if !strings.Contains(capturedBody, "{instance_id:String}") {
		t.Fatalf("expected placeholder preserved in body, got %q", capturedBody)
	}
	if strings.Contains(capturedBody, "inst-1") {
		t.Fatalf("instance_id value must not be interpolated into query body, got %q", capturedBody)
	}
}

func TestClickHouseReaderQueryFailsClosedOnUpstreamError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = io.WriteString(w, "Code: 48. DB::Exception: table missing\n")
	}))
	t.Cleanup(server.Close)

	reader := NewClickHouseReader(config.ClickHouseSettings{Enabled: true, URL: server.URL})
	rows, err := reader.Query(context.Background(), "SELECT 1", nil)
	if !errors.Is(err, ErrClickHouseUnavailable) {
		t.Fatalf("expected ErrClickHouseUnavailable, got %v", err)
	}
	if rows != nil {
		t.Fatalf("expected nil rows on upstream error, got %v", rows)
	}
}

func TestEnsureJSONEachRowFormatDoesNotDuplicate(t *testing.T) {
	if got := ensureJSONEachRowFormat("SELECT 1"); !strings.Contains(got, "FORMAT JSONEachRow") {
		t.Fatalf("expected FORMAT appended, got %q", got)
	}
	// A query that already specifies FORMAT must be returned untouched to avoid
	// ClickHouse rejecting a duplicate format clause.
	existing := "SELECT 1\nFORMAT TabSeparated"
	if got := ensureJSONEachRowFormat(existing); got != existing {
		t.Fatalf("expected existing FORMAT untouched, got %q", got)
	}
}
