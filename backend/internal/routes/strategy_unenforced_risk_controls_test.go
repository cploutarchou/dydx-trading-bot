//go:build integration

package routes

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// unsupportedRiskControlMessages mirrors bot/src/shared/live_risk_controls.py so the
// upstream double refuses exactly what the real bot refuses.
var unsupportedRiskControlMessages = []struct {
	field   string
	message string
}{
	{"max_drawdown_pct", "max_drawdown_pct is not enforced by the live runtime and is rejected until bot-level drawdown policy is implemented."},
	{"trailing_stop_pct", "trailing_stop_pct is not enforced by the live runtime and is rejected until per-position trailing stop logic is implemented."},
	{"capital_allocation_usd", "capital_allocation_usd is not enforced by the live runtime and is rejected until capital-allocation checks are enforced during live order entry."},
}

// botPreflightLikeTheRealBot answers /api/v1/runtime/preflight the way the bot does:
// 422 UNSUPPORTED_RISK_CONTROL when an unenforced control is > 0, ready otherwise.
func botPreflightLikeTheRealBot(t *testing.T, structured bool) http.HandlerFunc {
	t.Helper()
	return func(w http.ResponseWriter, r *http.Request) {
		defer func() { _ = r.Body.Close() }()
		var payload map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode preflight payload: %v", err)
		}
		tradingParams, _ := payload["trading_params"].(map[string]interface{})

		unsupported := make([]map[string]interface{}, 0)
		messages := make([]string, 0)
		for _, control := range unsupportedRiskControlMessages {
			if value, _ := tradingParams[control.field].(float64); value > 0 {
				unsupported = append(unsupported, map[string]interface{}{
					"field": control.field, "value": value, "message": control.message,
				})
				messages = append(messages, control.message)
			}
		}

		w.Header().Set("Content-Type", "application/json")
		if len(unsupported) > 0 {
			data := map[string]interface{}{"error": "UNSUPPORTED_RISK_CONTROL"}
			if structured {
				data["unsupported_fields"] = unsupported
			}
			w.WriteHeader(http.StatusUnprocessableEntity)
			_ = json.NewEncoder(w).Encode(map[string]interface{}{
				"success": false,
				"message": "Validation error: " + strings.Join(messages, " "),
				"data":    data,
			})
			return
		}
		_, _ = w.Write([]byte(`{"success":true,"data":{"selected_runtime_network":"testnet","selected_subaccount":0,"wallet_ready":true,"account_exists":true,"available_collateral":250.0,"equity":250.0,"open_positions":0,"usd_per_trade":10.0,"usd_min_collateral":100.0,"capital_allocation_usd":0.0,"trade_size_to_collateral_ratio":0.04,"sufficient_for_trade_size":true,"sufficient_for_min_collateral":true,"ready":true,"blockers":[],"warnings":[]}}`))
	}
}

func ensureAuditLogSchema(t *testing.T, dbConn *sql.DB) {
	t.Helper()
	if _, err := dbConn.Exec(`CREATE TABLE IF NOT EXISTS audit_logs (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER,
		action TEXT NOT NULL,
		resource_type TEXT NOT NULL,
		resource_id TEXT,
		details TEXT,
		status TEXT,
		ip_address TEXT,
		created_at DATETIME
	)`); err != nil {
		t.Fatalf("create audit_logs: %v", err)
	}
}

func strategyRequest(t *testing.T, method, url, token string, body interface{}) (int, map[string]interface{}) {
	t.Helper()
	var reader *bytes.Reader
	if body != nil {
		encoded, err := json.Marshal(body)
		if err != nil {
			t.Fatalf("encode request body: %v", err)
		}
		reader = bytes.NewReader(encoded)
	} else {
		reader = bytes.NewReader(nil)
	}
	req, _ := http.NewRequest(method, url, reader)
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("%s %s failed: %v", method, url, err)
	}
	defer func() { _ = resp.Body.Close() }()
	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		t.Fatalf("decode %s %s response: %v", method, url, err)
	}
	return resp.StatusCode, payload
}

func unenforcedFields(t *testing.T, data map[string]interface{}) []string {
	t.Helper()
	raw, ok := data["unenforced_risk_controls"].([]interface{})
	if !ok {
		t.Fatalf("expected unenforced_risk_controls array, got %#v", data["unenforced_risk_controls"])
	}
	fields := make([]string, 0, len(raw))
	for _, entry := range raw {
		control, _ := entry.(map[string]interface{})
		field, _ := control["field"].(string)
		fields = append(fields, field)
	}
	return fields
}

// The seeded strategy carries max_drawdown_pct=15, trailing_stop_pct=1 and
// initial_amount=1000, which is what a strategy promoted from a backtest looks like.
func TestStartReadinessReportsUnenforcedRiskControlsAndStaysBlocked(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/runtime/preflight", botPreflightLikeTheRealBot(t, true))

	router, dbConn, upstreamServer := setupStrategyRuntimeRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()
	ensureAuditLogSchema(t, dbConn)

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginStrategyRuntimeUser(t, backendServer.URL)
	readinessURL := backendServer.URL + "/api/v1/strategies/101/start-readiness?network=testnet"
	disableURL := backendServer.URL + "/api/v1/strategies/101/unenforced-risk-controls/disable"

	status, payload := strategyRequest(t, http.MethodGet, readinessURL, token, nil)
	if status != http.StatusOK {
		t.Fatalf("the bot's refusal is a readiness verdict, not a server error: got status %d (%v)", status, payload["error"])
	}
	data, _ := payload["data"].(map[string]interface{})
	if ready, _ := data["ready"].(bool); ready {
		t.Fatal("a strategy with unenforced risk controls must not be ready")
	}
	if got := strings.Join(unenforcedFields(t, data), ","); got != "max_drawdown_pct,trailing_stop_pct" {
		t.Fatalf("expected the two operator-set controls and no invented capital allocation, got %q", got)
	}
	blockers, _ := data["blockers"].([]interface{})
	if len(blockers) != 2 {
		t.Fatalf("expected one blocker per control, got %#v", blockers)
	}

	// Turning a control off needs an explicit acknowledgement and a known field.
	if status, _ = strategyRequest(t, http.MethodPost, disableURL, token, map[string]interface{}{
		"fields": []string{"max_drawdown_pct"}, "acknowledged": false,
	}); status != http.StatusBadRequest {
		t.Fatalf("missing acknowledgement must be rejected, got %d", status)
	}
	if status, _ = strategyRequest(t, http.MethodPost, disableURL, token, map[string]interface{}{
		"fields": []string{"stop_loss_pct"}, "acknowledged": true,
	}); status != http.StatusBadRequest {
		t.Fatalf("an enforced control must not be disableable here, got %d", status)
	}

	status, payload = strategyRequest(t, http.MethodPost, disableURL, token, map[string]interface{}{
		"fields": []string{"max_drawdown_pct", "trailing_stop_pct"}, "acknowledged": true, "network": "testnet",
	})
	if status != http.StatusOK {
		t.Fatalf("acknowledged disable failed: %d (%v)", status, payload["error"])
	}
	data, _ = payload["data"].(map[string]interface{})
	if got, _ := data["max_drawdown_pct"].(float64); got != 0 {
		t.Fatalf("expected max_drawdown_pct 0 after disable, got %v", data["max_drawdown_pct"])
	}
	if got, _ := data["trailing_stop_pct"].(float64); got != 0 {
		t.Fatalf("expected trailing_stop_pct 0 after disable, got %v", data["trailing_stop_pct"])
	}

	var action, resourceID, details string
	if err := dbConn.QueryRow(`SELECT action, resource_id, details FROM audit_logs ORDER BY id DESC LIMIT 1`).Scan(&action, &resourceID, &details); err != nil {
		t.Fatalf("expected an audit log row for the operator's decision: %v", err)
	}
	if action != "strategy.risk_controls.disable_unenforced" || resourceID != "101" {
		t.Fatalf("unexpected audit row action=%q resource_id=%q", action, resourceID)
	}
	if !strings.Contains(details, `"previous_value":15`) || !strings.Contains(details, `"previous_value":1`) {
		t.Fatalf("audit details must record the previous values, got %s", details)
	}

	status, payload = strategyRequest(t, http.MethodGet, readinessURL, token, nil)
	if status != http.StatusOK {
		t.Fatalf("unexpected readiness status after disable: %d", status)
	}
	data, _ = payload["data"].(map[string]interface{})
	if ready, _ := data["ready"].(bool); !ready {
		t.Fatalf("expected ready after the operator turned the controls off, blockers=%#v", data["blockers"])
	}
	if got := unenforcedFields(t, data); len(got) != 0 {
		t.Fatalf("expected no unenforced controls left, got %v", got)
	}
	if got, _ := data["capital_allocation_usd"].(float64); got != 1000 {
		t.Fatalf("backtest capital stays visible as information, got %v", data["capital_allocation_usd"])
	}
	warnings, _ := data["warnings"].([]interface{})
	disclosed := false
	for _, warning := range warnings {
		if text, _ := warning.(string); strings.Contains(text, "not a live limit") {
			disclosed = true
		}
	}
	if !disclosed {
		t.Fatalf("expected a warning that backtest capital is not a live limit, got %#v", warnings)
	}
}

// A bot that predates unsupported_fields still produces a readable blocker.
func TestStartReadinessHandlesRefusalWithoutStructuredFields(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/runtime/preflight", botPreflightLikeTheRealBot(t, false))

	router, dbConn, upstreamServer := setupStrategyRuntimeRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginStrategyRuntimeUser(t, backendServer.URL)

	status, payload := strategyRequest(t, http.MethodGet, backendServer.URL+"/api/v1/strategies/101/start-readiness?network=testnet", token, nil)
	if status != http.StatusOK {
		t.Fatalf("expected 200, got %d (%v)", status, payload["error"])
	}
	data, _ := payload["data"].(map[string]interface{})
	if ready, _ := data["ready"].(bool); ready {
		t.Fatal("must not be ready")
	}
	blockers, _ := data["blockers"].([]interface{})
	if len(blockers) != 1 || !strings.Contains(blockers[0].(string), "max_drawdown_pct is not enforced") {
		t.Fatalf("expected the bot's refusal as the blocker, got %#v", blockers)
	}
	if strings.HasPrefix(blockers[0].(string), "Validation error:") {
		t.Fatalf("blocker should not carry the transport prefix: %q", blockers[0])
	}
}

// An upstream failure that is not the risk-control refusal is still an error.
func TestStartReadinessStillFailsOnOtherUpstreamErrors(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/runtime/preflight", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnprocessableEntity)
		_, _ = w.Write([]byte(`{"success":false,"message":"Validation error: stats_window must be >= 2","data":{"error":"VALIDATION_ERROR"}}`))
	})

	router, dbConn, upstreamServer := setupStrategyRuntimeRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginStrategyRuntimeUser(t, backendServer.URL)

	status, _ := strategyRequest(t, http.MethodGet, backendServer.URL+"/api/v1/strategies/101/start-readiness?network=testnet", token, nil)
	if status != http.StatusInternalServerError {
		t.Fatalf("only the risk-control refusal is a readiness verdict; expected 500, got %d", status)
	}
}

func TestUpdateStrategyHonoursExplicitZeroForUnenforcedControls(t *testing.T) {
	router, dbConn, upstreamServer := setupStrategyRuntimeRouter(t, http.NewServeMux())
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginStrategyRuntimeUser(t, backendServer.URL)
	strategyURL := backendServer.URL + "/api/v1/strategies/101"

	status, payload := strategyRequest(t, http.MethodPut, strategyURL, token, map[string]interface{}{
		"name": "Runtime Strategy", "max_drawdown_pct": 0,
	})
	if status != http.StatusOK {
		t.Fatalf("update failed: %d (%v)", status, payload["error"])
	}
	data, _ := payload["data"].(map[string]interface{})
	if got, _ := data["max_drawdown_pct"].(float64); got != 0 {
		t.Fatalf("explicit 0 must be stored, got %v", data["max_drawdown_pct"])
	}
	if got, _ := data["trailing_stop_pct"].(float64); got != 1 {
		t.Fatalf("an omitted control must keep its value, got %v", data["trailing_stop_pct"])
	}
}
