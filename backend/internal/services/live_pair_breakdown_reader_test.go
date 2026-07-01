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

func TestLivePairBreakdownReaderNilFailsClosed(t *testing.T) {
	var reader *LivePairBreakdownReader
	summary, err := reader.GetBreakdown(context.Background(), "inst-1", 24)
	if !errors.Is(err, ErrClickHouseDisabled) {
		t.Fatalf("expected ErrClickHouseDisabled, got %v", err)
	}
	if summary != nil {
		t.Fatalf("expected nil summary, got %v", summary)
	}
}

func TestLivePairBreakdownReaderRequiresInstanceID(t *testing.T) {
	reader := NewLivePairBreakdownReader(NewClickHouseReader(config.ClickHouseSettings{Enabled: true, URL: "http://localhost:8123"}))
	if reader == nil {
		t.Fatalf("expected non-nil reader")
	}
	if _, err := reader.GetBreakdown(context.Background(), "  ", 24); err == nil {
		t.Fatalf("expected error for missing instance_id")
	}
}

func TestLivePairBreakdownReaderGetBreakdownAggregates(t *testing.T) {
	var capturedBody string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		buf := new(strings.Builder)
		_, _ = io.Copy(buf, r.Body)
		capturedBody = buf.String()
		w.Header().Set("Content-Type", "application/json")
		// Two traded pairs, ordered by total_realized_pnl DESC as the query requests.
		_, _ = io.WriteString(w, strings.TrimSpace(`
{"pair1":"ETH-USD","pair2":"BTC-USD","trades_closed":5,"total_realized_pnl":150.0,"avg_realized_pnl_pct":0.03,"winning_trades":4,"losing_trades":1,"best_realized_pnl":80.0,"worst_realized_pnl":-10.0}
{"pair1":"SOL-USD","pair2":"BTC-USD","trades_closed":3,"total_realized_pnl":-20.0,"avg_realized_pnl_pct":-0.01,"winning_trades":1,"losing_trades":2,"best_realized_pnl":5.0,"worst_realized_pnl":-15.0}
`)+"\n")
	}))
	t.Cleanup(server.Close)

	reader := NewLivePairBreakdownReader(NewClickHouseReader(config.ClickHouseSettings{
		Enabled:  true,
		URL:      server.URL,
		Database: "dydx_analytics",
	}))
	if reader == nil {
		t.Fatalf("expected non-nil reader")
	}

	summary, err := reader.GetBreakdown(context.Background(), "inst-1", 12)
	if err != nil {
		t.Fatalf("GetBreakdown: %v", err)
	}
	if summary == nil {
		t.Fatalf("expected non-nil summary")
	}
	if summary.InstanceID != "inst-1" || summary.Hours != 12 {
		t.Fatalf("unexpected envelope context: %+v", summary)
	}
	if len(summary.Pairs) != 2 {
		t.Fatalf("expected 2 pairs, got %d", len(summary.Pairs))
	}

	top := summary.Pairs[0]
	if top.Pair1 != "ETH-USD" || top.Pair2 != "BTC-USD" || top.TradesClosed != 5 {
		t.Fatalf("unexpected top pair: %+v", top)
	}
	if top.TotalRealizedPnL != 150.0 || top.WinningTrades != 4 || top.LosingTrades != 1 {
		t.Fatalf("unexpected top pair aggregates: %+v", top)
	}
	if top.BestRealizedPnL != 80.0 || top.WorstRealizedPnL != -10.0 {
		t.Fatalf("unexpected best/worst pnl: %+v", top)
	}
	second := summary.Pairs[1]
	if second.TotalRealizedPnL != -20.0 {
		t.Fatalf("unexpected second pair pnl: %+v", second)
	}

	// The query must filter to closed lifecycle rows, key by instance_id, group by
	// the pair, and bind values server-side rather than interpolating them.
	if !strings.Contains(capturedBody, "FROM trade_events") {
		t.Fatalf("expected trade_events reference, got %q", capturedBody)
	}
	if !strings.Contains(capturedBody, "event_kind = 'closed'") {
		t.Fatalf("expected closed-only filter, got %q", capturedBody)
	}
	if !strings.Contains(capturedBody, "GROUP BY pair1, pair2") {
		t.Fatalf("expected pair grouping, got %q", capturedBody)
	}
	if !strings.Contains(capturedBody, "instance_id = {instance_id:String}") {
		t.Fatalf("expected instance_id placeholder, got %q", capturedBody)
	}
	if strings.Contains(capturedBody, "inst-1") {
		t.Fatalf("instance_id value must not be interpolated into query body, got %q", capturedBody)
	}
}

func TestLivePairBreakdownReaderEmptyResult(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		// No closed rows in window → GROUP BY yields zero rows → empty body.
		_, _ = io.WriteString(w, "")
	}))
	t.Cleanup(server.Close)

	reader := NewLivePairBreakdownReader(NewClickHouseReader(config.ClickHouseSettings{Enabled: true, URL: server.URL}))
	summary, err := reader.GetBreakdown(context.Background(), "inst-1", 24)
	if err != nil {
		t.Fatalf("GetBreakdown on empty result: %v", err)
	}
	if summary.Pairs == nil || len(summary.Pairs) != 0 {
		t.Fatalf("expected empty (non-nil) pairs slice, got %v", summary.Pairs)
	}
}

func TestLivePairBreakdownReaderClampsHours(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = io.WriteString(w, "")
	}))
	t.Cleanup(server.Close)

	reader := NewLivePairBreakdownReader(NewClickHouseReader(config.ClickHouseSettings{Enabled: true, URL: server.URL}))
	for _, in := range []int{0, -5, maxSummaryHours + 100} {
		summary, err := reader.GetBreakdown(context.Background(), "inst-1", in)
		if err != nil {
			t.Fatalf("GetBreakdown(hours=%d): %v", in, err)
		}
		if summary.Hours <= 0 || summary.Hours > maxSummaryHours {
			t.Fatalf("hours=%d produced out-of-range window %d", in, summary.Hours)
		}
	}
}

func TestLivePairBreakdownReaderFailsClosedOnUpstreamError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
		_, _ = io.WriteString(w, "Code: 210. DB::Exception: connection refused\n")
	}))
	t.Cleanup(server.Close)

	reader := NewLivePairBreakdownReader(NewClickHouseReader(config.ClickHouseSettings{Enabled: true, URL: server.URL}))
	if _, err := reader.GetBreakdown(context.Background(), "inst-1", 24); !errors.Is(err, ErrClickHouseUnavailable) {
		t.Fatalf("expected ErrClickHouseUnavailable, got %v", err)
	}
}
