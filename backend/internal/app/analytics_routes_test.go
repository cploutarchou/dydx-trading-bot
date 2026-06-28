package app

import (
	"database/sql"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	_ "modernc.org/sqlite"
)

func newAnalyticsTestContext(t *testing.T, target string) (*gin.Context, *httptest.ResponseRecorder) {
	t.Helper()
	gin.SetMode(gin.TestMode)
	recorder := httptest.NewRecorder()
	ctx, _ := gin.CreateTestContext(recorder)
	ctx.Request = httptest.NewRequest(http.MethodGet, target, nil)
	return ctx, recorder
}

func decodeAnalyticsBody(t *testing.T, recorder *httptest.ResponseRecorder) map[string]interface{} {
	t.Helper()
	var body map[string]interface{}
	if err := json.Unmarshal(recorder.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response body: %v (raw=%q)", err, recorder.Body.String())
	}
	return body
}

func TestServeLivePositionHistoryRequiresAdmin(t *testing.T) {
	ctx, recorder := newAnalyticsTestContext(t, "/?instance_id=inst-1")
	// is_admin intentionally unset
	serveLivePositionHistory(ctx, nil)

	if recorder.Code != http.StatusForbidden {
		t.Fatalf("expected 403 for non-admin, got %d", recorder.Code)
	}
}

func TestServeLivePositionHistoryRequiresInstanceID(t *testing.T) {
	ctx, recorder := newAnalyticsTestContext(t, "/")
	ctx.Set("is_admin", true)
	serveLivePositionHistory(ctx, services.NewLivePositionReader(services.NewClickHouseReader(config.ClickHouseSettings{Enabled: true, URL: "http://localhost:8123"})))

	if recorder.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 for missing instance_id, got %d", recorder.Code)
	}
}

func TestServeLivePositionHistoryDisabledFailsClosed(t *testing.T) {
	ctx, recorder := newAnalyticsTestContext(t, "/?instance_id=inst-1")
	ctx.Set("is_admin", true)

	// nil position reader simulates ClickHouse disabled (the checked-in default).
	serveLivePositionHistory(ctx, nil)

	if recorder.Code != http.StatusOK {
		t.Fatalf("expected 200 degraded response when disabled, got %d", recorder.Code)
	}
	body := decodeAnalyticsBody(t, recorder)
	if body["enabled"] != false {
		t.Fatalf("expected enabled=false, got %v", body["enabled"])
	}
	if body["source"] != "disabled" {
		t.Fatalf("expected source=disabled, got %v", body["source"])
	}
	data, ok := body["data"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected data object, got %T", body["data"])
	}
	snapshots, ok := data["snapshots"].([]interface{})
	if !ok || len(snapshots) != 0 {
		t.Fatalf("expected empty snapshots, got %v", data["snapshots"])
	}
}

func TestServeLivePositionHistoryServesClickHouseRows(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, `{"snapshot_time":"2026-06-28 16:09:57.000","position_id":"pos-1","instance_id":"inst-1","bot_id":"42","pair1":"ETH-USD","pair2":"BTC-USD","side1":"buy","side2":"sell","status":"open","event_kind":"open","entry_price1":3000.5,"entry_price2":60000.25,"current_price1":null,"current_price2":null,"entry_size1":1.0,"entry_size2":0.05,"unrealized_pnl":5.0,"unrealized_pnl_pct":0.004,"realized_pnl":0,"realized_pnl_pct":0,"z_score_current":null}`+"\n")
	}))
	t.Cleanup(server.Close)

	positionReader := services.NewLivePositionReader(services.NewClickHouseReader(config.ClickHouseSettings{
		Enabled: true,
		URL:     server.URL,
	}))

	ctx, recorder := newAnalyticsTestContext(t, "/?instance_id=inst-1&position_id=pos-1&hours=12")
	ctx.Set("is_admin", true)
	serveLivePositionHistory(ctx, positionReader)

	if recorder.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d (body=%s)", recorder.Code, recorder.Body.String())
	}
	body := decodeAnalyticsBody(t, recorder)
	if body["enabled"] != true || body["source"] != "clickhouse" {
		t.Fatalf("expected enabled=true/source=clickhouse, got %+v", body)
	}
	data := body["data"].(map[string]interface{})
	if data["count"] != float64(1) {
		t.Fatalf("expected count=1, got %v", data["count"])
	}
	snapshots := data["snapshots"].([]interface{})
	first := snapshots[0].(map[string]interface{})
	if first["instance_id"] != "inst-1" || first["position_id"] != "pos-1" {
		t.Fatalf("unexpected snapshot row: %+v", first)
	}
}

func TestServeLivePositionHistoryClampsInvalidHours(t *testing.T) {
	if got := parseHistoryHours(""); got != 24 {
		t.Fatalf("default hours: got %d", got)
	}
	if got := parseHistoryHours("not-a-number"); got != 24 {
		t.Fatalf("invalid hours fallback: got %d", got)
	}
	if got := parseHistoryHours("-5"); got != 24 {
		t.Fatalf("negative hours fallback: got %d", got)
	}
	if got := parseHistoryHours("6"); got != 6 {
		t.Fatalf("valid hours: got %d", got)
	}
}

func TestServeLiveTradeSummaryRequiresAdmin(t *testing.T) {
	ctx, recorder := newAnalyticsTestContext(t, "/?instance_id=inst-1")
	// is_admin intentionally unset
	serveLiveTradeSummary(ctx, nil)

	if recorder.Code != http.StatusForbidden {
		t.Fatalf("expected 403 for non-admin, got %d", recorder.Code)
	}
}

func TestServeLiveTradeSummaryRequiresInstanceID(t *testing.T) {
	ctx, recorder := newAnalyticsTestContext(t, "/")
	ctx.Set("is_admin", true)
	serveLiveTradeSummary(ctx, services.NewLiveTradeSummaryReader(services.NewClickHouseReader(config.ClickHouseSettings{Enabled: true, URL: "http://localhost:8123"})))

	if recorder.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 for missing instance_id, got %d", recorder.Code)
	}
}

func TestServeLiveTradeSummaryDisabledFailsClosed(t *testing.T) {
	ctx, recorder := newAnalyticsTestContext(t, "/?instance_id=inst-1")
	ctx.Set("is_admin", true)

	// nil summary reader simulates ClickHouse disabled (the checked-in default).
	serveLiveTradeSummary(ctx, nil)

	if recorder.Code != http.StatusOK {
		t.Fatalf("expected 200 degraded response when disabled, got %d", recorder.Code)
	}
	body := decodeAnalyticsBody(t, recorder)
	if body["enabled"] != false || body["source"] != "disabled" {
		t.Fatalf("expected enabled=false/source=disabled, got %+v", body)
	}
	data, ok := body["data"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected data object, got %T", body["data"])
	}
	if data["instance_id"] != "inst-1" {
		t.Fatalf("expected degraded data to echo instance_id, got %v", data["instance_id"])
	}
	if totals, ok := data["totals"].(map[string]interface{}); !ok || totals["trade_events"] != float64(0) {
		t.Fatalf("expected zeroed totals in degraded payload, got %v", data["totals"])
	}
	if daily, ok := data["daily"].([]interface{}); !ok || len(daily) != 0 {
		t.Fatalf("expected empty daily slice in degraded payload, got %v", data["daily"])
	}
}

func TestServeLiveTradeSummaryServesClickHouseAggregates(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		buf := new(strings.Builder)
		_, _ = io.Copy(buf, r.Body)
		body := buf.String()
		w.Header().Set("Content-Type", "application/json")
		switch {
		case strings.Contains(body, "FROM order_events"):
			_, _ = io.WriteString(w, `{"status":"filled","count":10}`+"\n")
		case strings.Contains(body, "GROUP BY day"):
			_, _ = io.WriteString(w, `{"day":"2026-06-28","trade_events":4,"closed_trades":2,"total_realized_pnl":50.0}`+"\n")
		default:
			_, _ = io.WriteString(w, `{"trade_events":4,"trades_opened":2,"trades_closed":2,"total_realized_pnl":50.0,"total_realized_pnl_pct":0.05,"winning_trades":2,"losing_trades":0}`+"\n")
		}
	}))
	t.Cleanup(server.Close)

	summaryReader := services.NewLiveTradeSummaryReader(services.NewClickHouseReader(config.ClickHouseSettings{
		Enabled: true,
		URL:     server.URL,
	}))

	ctx, recorder := newAnalyticsTestContext(t, "/?instance_id=inst-1&hours=12")
	ctx.Set("is_admin", true)
	serveLiveTradeSummary(ctx, summaryReader)

	if recorder.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d (body=%s)", recorder.Code, recorder.Body.String())
	}
	body := decodeAnalyticsBody(t, recorder)
	if body["enabled"] != true || body["source"] != "clickhouse" {
		t.Fatalf("expected enabled=true/source=clickhouse, got %+v", body)
	}
	data := body["data"].(map[string]interface{})
	if data["instance_id"] != "inst-1" || data["hours"] != float64(12) {
		t.Fatalf("unexpected envelope context: %+v", data)
	}
	totals := data["totals"].(map[string]interface{})
	if totals["trade_events"] != float64(4) || totals["trades_closed"] != float64(2) {
		t.Fatalf("unexpected totals: %+v", totals)
	}
	if totals["total_realized_pnl"] != float64(50.0) {
		t.Fatalf("unexpected total_realized_pnl: %v", totals["total_realized_pnl"])
	}
	orders := data["orders_by_status"].([]interface{})
	if len(orders) != 1 {
		t.Fatalf("expected 1 order-status row, got %d", len(orders))
	}
	if data["order_events"] != float64(10) {
		t.Fatalf("expected order_events=10, got %v", data["order_events"])
	}
}

// Ensure the analytics route is registered on a fully built router so the
// manifest stays honest. Uses the same sqlite-backed BuildRouter pattern as the
// existing manifest test.
func TestBuildRouterRegistersAnalyticsPositionHistoryRoute(t *testing.T) {
	if !analyticsRouteRegistered(t, "/api/v1/analytics/position-history") {
		t.Fatalf("analytics position-history route was not registered")
	}
}

func TestBuildRouterRegistersAnalyticsTradeSummaryRoute(t *testing.T) {
	if !analyticsRouteRegistered(t, "/api/v1/analytics/trade-summary") {
		t.Fatalf("analytics trade-summary route was not registered")
	}
}

// analyticsRouteRegistered builds a fully wired router on an in-memory sqlite DB
// and reports whether the given admin analytics route was registered.
func analyticsRouteRegistered(t *testing.T, suffix string) bool {
	t.Helper()
	gin.SetMode(gin.TestMode)
	cfg := &config.Config{}
	cfg.Auth.JWTSecretKey = "analytics-route-test-secret"
	cfg.Auth.AccessTokenExpireMinutes = 30
	cfg.Auth.RefreshTokenExpireDays = 7
	cfg.Redis.Enabled = false
	middleware.InitAuthMiddleware(cfg)

	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	t.Cleanup(func() { _ = dbConn.Close() })

	router, err := BuildRouter(cfg, Dependencies{
		Database:     &db.Database{DB: dbConn},
		BotAPIURL:    "http://127.0.0.1:8889",
		BotAPIClient: services.NewBotAPIClient("http://127.0.0.1:8889", ""),
		StartTime:    time.Now(),
	})
	if err != nil {
		t.Fatalf("BuildRouter returned error: %v", err)
	}

	for _, route := range router.Routes() {
		if route.Method == http.MethodGet && strings.HasSuffix(route.Path, suffix) {
			return true
		}
	}
	return false
}
