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

func TestLiveTradeSummaryReaderNilFailsClosed(t *testing.T) {
	var reader *LiveTradeSummaryReader
	summary, err := reader.GetSummary(context.Background(), "inst-1", 24)
	if !errors.Is(err, ErrClickHouseDisabled) {
		t.Fatalf("expected ErrClickHouseDisabled, got %v", err)
	}
	if summary != nil {
		t.Fatalf("expected nil summary, got %v", summary)
	}
}

func TestLiveTradeSummaryReaderRequiresInstanceID(t *testing.T) {
	reader := NewLiveTradeSummaryReader(NewClickHouseReader(config.ClickHouseSettings{Enabled: true, URL: "http://localhost:8123"}))
	if reader == nil {
		t.Fatalf("expected non-nil reader")
	}
	if _, err := reader.GetSummary(context.Background(), "  ", 24); err == nil {
		t.Fatalf("expected error for missing instance_id")
	}
}

// summaryQueryServer routes each ClickHouse request to a fixed fixture by
// inspecting the query body, so the reader's three aggregate queries can be
// exercised against a single httptest.Server. It also captures every request so
// the test can assert that values are bound server-side rather than interpolated.
func summaryQueryServer(t *testing.T, captured *[]string) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		buf := new(strings.Builder)
		_, _ = io.Copy(buf, r.Body)
		body := buf.String()
		if captured != nil {
			*captured = append(*captured, body)
		}
		w.Header().Set("Content-Type", "application/json")

		switch {
		case strings.Contains(body, "FROM order_events"):
			_, _ = io.WriteString(w, strings.TrimSpace(`
{"status":"filled","count":18}
{"status":"closed","count":7}
{"status":"orphaned","count":1}
`)+"\n")
		case strings.Contains(body, "GROUP BY day"):
			_, _ = io.WriteString(w, strings.TrimSpace(`
{"day":"2026-06-27","trade_events":10,"closed_trades":4,"total_realized_pnl":120.5}
{"day":"2026-06-28","trade_events":6,"closed_trades":3,"total_realized_pnl":-15.25}
`)+"\n")
		default:
			// single-row trade-event totals (no GROUP BY)
			_, _ = io.WriteString(w, strings.TrimSpace(`
{"trade_events":16,"trades_opened":9,"trades_closed":7,"total_realized_pnl":105.25,"total_realized_pnl_pct":0.084,"winning_trades":5,"losing_trades":2}
`)+"\n")
		}
	}))
}

func TestLiveTradeSummaryReaderGetSummaryAggregates(t *testing.T) {
	var captured []string
	server := summaryQueryServer(t, &captured)
	t.Cleanup(server.Close)

	reader := NewLiveTradeSummaryReader(NewClickHouseReader(config.ClickHouseSettings{
		Enabled:  true,
		URL:      server.URL,
		Database: "dydx_analytics",
	}))
	if reader == nil {
		t.Fatalf("expected non-nil reader")
	}

	summary, err := reader.GetSummary(context.Background(), "inst-1", 12)
	if err != nil {
		t.Fatalf("GetSummary: %v", err)
	}
	if summary == nil {
		t.Fatalf("expected non-nil summary")
	}
	if summary.InstanceID != "inst-1" || summary.Hours != 12 {
		t.Fatalf("unexpected envelope context: %+v", summary)
	}

	if summary.Totals.TradeEvents != 16 || summary.Totals.TradesClosed != 7 {
		t.Fatalf("unexpected totals: %+v", summary.Totals)
	}
	if summary.Totals.TotalRealizedPnL != 105.25 || summary.Totals.WinningTrades != 5 || summary.Totals.LosingTrades != 2 {
		t.Fatalf("unexpected pnl aggregates: %+v", summary.Totals)
	}

	if len(summary.Daily) != 2 {
		t.Fatalf("expected 2 daily rows, got %d", len(summary.Daily))
	}
	if summary.Daily[0].Day != "2026-06-27" || summary.Daily[0].TotalRealizedPnL != 120.5 {
		t.Fatalf("unexpected first daily row: %+v", summary.Daily[0])
	}

	if len(summary.OrdersByStatus) != 3 {
		t.Fatalf("expected 3 order-status rows, got %d", len(summary.OrdersByStatus))
	}
	// 18 + 7 + 1 = 26 order events total
	if summary.OrderEvents != 26 {
		t.Fatalf("expected order_events total 26, got %d", summary.OrderEvents)
	}

	// All three queries must key by instance_id and bind values server-side.
	joined := strings.Join(captured, "\n")
	if !strings.Contains(joined, "instance_id = {instance_id:String}") {
		t.Fatalf("expected instance_id placeholder, got %q", joined)
	}
	if !strings.Contains(joined, "FROM trade_events") || !strings.Contains(joined, "FROM order_events") {
		t.Fatalf("expected both table references, got %q", joined)
	}
	if strings.Contains(joined, "inst-1") {
		t.Fatalf("instance_id value must not be interpolated into query bodies, got %q", joined)
	}
}

func TestLiveTradeSummaryReaderClampsHours(t *testing.T) {
	server := summaryQueryServer(t, nil)
	t.Cleanup(server.Close)

	reader := NewLiveTradeSummaryReader(NewClickHouseReader(config.ClickHouseSettings{Enabled: true, URL: server.URL}))

	// hours<=0 falls back to the default; a huge window is clamped to the cap.
	for _, in := range []int{0, -5, maxSummaryHours + 100} {
		summary, err := reader.GetSummary(context.Background(), "inst-1", in)
		if err != nil {
			t.Fatalf("GetSummary(hours=%d): %v", in, err)
		}
		if summary.Hours <= 0 || summary.Hours > maxSummaryHours {
			t.Fatalf("hours=%d produced out-of-range window %d", in, summary.Hours)
		}
	}
}

func TestLiveTradeSummaryReaderFailsClosedOnUpstreamError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = io.WriteString(w, "Code: 60. DB::Exception: table missing\n")
	}))
	t.Cleanup(server.Close)

	reader := NewLiveTradeSummaryReader(NewClickHouseReader(config.ClickHouseSettings{Enabled: true, URL: server.URL}))
	if _, err := reader.GetSummary(context.Background(), "inst-1", 24); !errors.Is(err, ErrClickHouseUnavailable) {
		t.Fatalf("expected ErrClickHouseUnavailable, got %v", err)
	}
}
