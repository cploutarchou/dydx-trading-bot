package services

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
)

func TestGetBotInstanceTrades_BuildsStatusAndPaginationQuery(t *testing.T) {
	var gotPath string
	var gotQuery string

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath = r.URL.Path
		gotQuery = r.URL.RawQuery
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{"ok": true})
	}))
	defer srv.Close()

	client := NewBotAPIClient(srv.URL, "")
	status := "open"
	limit := 50
	offset := 100

	if _, err := client.GetBotInstanceTrades("inst-1", &status, &limit, &offset); err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if gotPath != "/api/v1/bots/inst-1/trades" {
		t.Fatalf("unexpected path: %s", gotPath)
	}

	values, err := url.ParseQuery(gotQuery)
	if err != nil {
		t.Fatalf("failed to parse query: %v", err)
	}
	if values.Get("status") != "open" {
		t.Fatalf("expected status=open, got %q", values.Get("status"))
	}
	if values.Get("limit") != "50" {
		t.Fatalf("expected limit=50, got %q", values.Get("limit"))
	}
	if values.Get("offset") != "100" {
		t.Fatalf("expected offset=100, got %q", values.Get("offset"))
	}
}

func TestGetBotInstanceTrades_OmitsEmptyFilters(t *testing.T) {
	var gotQuery string

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotQuery = r.URL.RawQuery
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{"ok": true})
	}))
	defer srv.Close()

	client := NewBotAPIClient(srv.URL, "")

	if _, err := client.GetBotInstanceTrades("inst-2", nil, nil, nil); err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if gotQuery != "" {
		t.Fatalf("expected empty query, got %q", gotQuery)
	}
}
