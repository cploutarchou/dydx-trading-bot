package services

import (
	"context"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/dydx-trading-bot/backend-go/config"
)

func TestLivePositionReaderNilFailsClosed(t *testing.T) {
	var reader *LivePositionReader
	rows, err := reader.GetHistory(context.Background(), "inst-1", "", 24)
	if !errors.Is(err, ErrClickHouseDisabled) {
		t.Fatalf("expected ErrClickHouseDisabled, got %v", err)
	}
	if rows != nil {
		t.Fatalf("expected nil rows, got %v", rows)
	}
}

func TestLivePositionReaderRequiresInstanceID(t *testing.T) {
	reader := NewLivePositionReader(NewClickHouseReader(config.ClickHouseSettings{Enabled: true, URL: "http://localhost:8123"}))
	if reader == nil {
		t.Fatalf("expected non-nil reader")
	}
	if _, err := reader.GetHistory(context.Background(), "  ", "", 24); err == nil {
		t.Fatalf("expected error for missing instance_id")
	}
}

func TestLivePositionReaderGetHistoryQueriesAndDecodes(t *testing.T) {
	var capturedBody string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		buf := new(strings.Builder)
		_, _ = io.Copy(buf, r.Body)
		capturedBody = buf.String()
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, strings.TrimSpace(`
{"snapshot_time":"2026-06-28 16:09:57.000","position_id":"pos-1","instance_id":"inst-1","bot_id":"42","pair1":"ETH-USD","pair2":"BTC-USD","side1":"buy","side2":"sell","status":"open","event_kind":"update","entry_price1":3000.5,"entry_price2":60000.25,"current_price1":3050.0,"current_price2":null,"entry_size1":1.0,"entry_size2":0.05,"unrealized_pnl":12.5,"unrealized_pnl_pct":0.01,"realized_pnl":0,"realized_pnl_pct":0,"z_score_current":1.23}
{"snapshot_time":"2026-06-28 17:00:00.000","position_id":"pos-1","instance_id":"inst-1","bot_id":"42","pair1":"ETH-USD","pair2":"BTC-USD","side1":"buy","side2":"sell","status":"closed","event_kind":"close","entry_price1":3000.5,"entry_price2":60000.25,"current_price1":null,"current_price2":null,"entry_size1":1.0,"entry_size2":0.05,"unrealized_pnl":0,"unrealized_pnl_pct":0,"realized_pnl":42.0,"realized_pnl_pct":0.03,"z_score_current":null}
`)+"\n")
	}))
	t.Cleanup(server.Close)

	reader := NewLivePositionReader(NewClickHouseReader(config.ClickHouseSettings{
		Enabled:  true,
		URL:      server.URL,
		Database: "dydx_analytics",
	}))
	if reader == nil {
		t.Fatalf("expected non-nil reader")
	}

	rows, err := reader.GetHistory(context.Background(), "inst-1", "pos-1", 12)
	if err != nil {
		t.Fatalf("GetHistory: %v", err)
	}
	if len(rows) != 2 {
		t.Fatalf("expected 2 snapshots, got %d", len(rows))
	}

	first := rows[0]
	if first.InstanceID != "inst-1" || first.PositionID != "pos-1" {
		t.Fatalf("unexpected identity fields: %+v", first)
	}
	if first.UnrealizedPnL != 12.5 || first.ZScoreCurrent == nil || *first.ZScoreCurrent != 1.23 {
		t.Fatalf("unexpected first row analytics: %+v", first)
	}
	if first.CurrentPrice2 != nil {
		t.Fatalf("expected nullable current_price2 to be nil, got %v", first.CurrentPrice2)
	}
	second := rows[1]
	if second.RealizedPnL != 42.0 || second.ZScoreCurrent != nil {
		t.Fatalf("unexpected second row analytics: %+v", second)
	}

	// The query must key by instance_id, filter by position_id, and bind values
	// server-side through placeholders rather than interpolation.
	if !strings.Contains(capturedBody, "FROM position_snapshots") {
		t.Fatalf("expected table reference in query, got %q", capturedBody)
	}
	if !strings.Contains(capturedBody, "instance_id = {instance_id:String}") {
		t.Fatalf("expected instance_id placeholder, got %q", capturedBody)
	}
	if !strings.Contains(capturedBody, "position_id = {position_id:String}") {
		t.Fatalf("expected position_id placeholder, got %q", capturedBody)
	}
	if strings.Contains(capturedBody, "inst-1") {
		t.Fatalf("instance_id value must not be interpolated into query body, got %q", capturedBody)
	}
}
