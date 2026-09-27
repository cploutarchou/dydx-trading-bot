package routes

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/auth"
	backenddb "github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	_ "modernc.org/sqlite"
)

var chatRouteSchema = []string{
	`CREATE TABLE users (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		username TEXT NOT NULL UNIQUE,
		email TEXT NOT NULL UNIQUE,
		hashed_password TEXT NOT NULL DEFAULT '',
		is_active BOOLEAN NOT NULL DEFAULT 1,
		is_admin BOOLEAN NOT NULL DEFAULT 0,
		max_strategies INTEGER DEFAULT 10,
		created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
		updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
	)`,
	`CREATE TABLE backtest_strategies (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER NOT NULL,
		name TEXT NOT NULL,
		description TEXT,
		category TEXT,
		is_public BOOLEAN NOT NULL DEFAULT 0,
		is_default BOOLEAN NOT NULL DEFAULT 0,
		runtime_strategy TEXT NOT NULL DEFAULT 'cointegration',
		runtime_network TEXT NOT NULL DEFAULT 'testnet',
		runtime_subaccount INTEGER NOT NULL DEFAULT 0,
		pair_selection_mode TEXT NOT NULL DEFAULT 'liquidity',
		selected_markets TEXT NOT NULL DEFAULT '[]',
		zscore_threshold REAL NOT NULL,
		stats_window INTEGER NOT NULL,
		max_half_life REAL NOT NULL,
		usd_per_trade REAL NOT NULL,
		usd_min_collateral REAL NOT NULL,
		close_at_zscore_cross BOOLEAN NOT NULL,
		find_cointegrated_pairs BOOLEAN NOT NULL,
		manage_exits BOOLEAN NOT NULL,
		place_trades BOOLEAN NOT NULL,
		abort_all_positions BOOLEAN NOT NULL,
		max_positions INTEGER NOT NULL,
		max_drawdown_pct REAL NOT NULL,
		stop_loss_pct REAL NOT NULL,
		take_profit_pct REAL NOT NULL,
		trailing_stop_pct REAL NOT NULL,
		rebalance_interval_hours INTEGER NOT NULL,
		position_timeout_hours INTEGER NOT NULL,
		transaction_fee REAL NOT NULL,
		slippage REAL NOT NULL,
		starting_balance REAL NOT NULL,
		candle_resolution TEXT NOT NULL,
		max_history_days INTEGER NOT NULL,
		benchmark_symbol TEXT NOT NULL,
		risk_free_rate REAL NOT NULL,
		initial_amount REAL NOT NULL,
		usage_count INTEGER NOT NULL DEFAULT 0,
		last_used_at DATETIME,
		deleted_at DATETIME,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL
	)`,
	`CREATE TABLE strategy_execution_states (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		strategy_id INTEGER NOT NULL UNIQUE,
		is_running BOOLEAN NOT NULL DEFAULT 0,
		last_run_at DATETIME,
		next_run_at DATETIME,
		state TEXT,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL
	)`,
	`CREATE TABLE strategy_version_history (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		strategy_id INTEGER NOT NULL,
		version_number INTEGER NOT NULL,
		change_description TEXT,
		config_snapshot TEXT NOT NULL,
		changes TEXT,
		created_at DATETIME,
		created_by_user_id INTEGER,
		UNIQUE (strategy_id, version_number)
	)`,
	`CREATE TABLE backtest_runs (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER,
		strategy_id INTEGER,
		strategy_version_id INTEGER,
		run_id TEXT NOT NULL,
		status TEXT,
		start_date TEXT NOT NULL DEFAULT '',
		end_date TEXT NOT NULL DEFAULT '',
		num_pairs INTEGER NOT NULL DEFAULT 0,
		total_markets INTEGER NOT NULL DEFAULT 0,
		resolution TEXT,
		total_trades INTEGER,
		profitable_trades INTEGER,
		losing_trades INTEGER,
		win_rate REAL,
		total_pnl REAL,
		total_pnl_usd REAL,
		sharpe_ratio REAL,
		sortino_ratio REAL,
		calmar_ratio REAL,
		max_drawdown REAL,
		profit_factor REAL,
		starting_balance REAL,
		ending_balance REAL,
		max_balance REAL,
		min_balance REAL,
		error_message TEXT,
		started_at DATETIME,
		completed_at DATETIME,
		duration_seconds REAL,
		created_at DATETIME NOT NULL
	)`,
	`CREATE TABLE external_api_credentials (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER NOT NULL,
		provider TEXT NOT NULL,
		label TEXT NOT NULL DEFAULT '',
		encrypted_api_key TEXT NOT NULL,
		api_key_hash TEXT NOT NULL DEFAULT '',
		api_key_salt TEXT NOT NULL DEFAULT '',
		api_key_masked TEXT NOT NULL DEFAULT '',
		is_active BOOLEAN NOT NULL DEFAULT 1,
		created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
		updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
		UNIQUE (user_id, provider)
	)`,
	`CREATE TABLE audit_logs (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER,
		action TEXT NOT NULL,
		resource_type TEXT NOT NULL,
		resource_id TEXT,
		details TEXT,
		status TEXT,
		ip_address TEXT,
		created_at DATETIME
	)`,
	`CREATE TABLE strategy_chat_sessions (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER NOT NULL,
		strategy_id INTEGER NOT NULL,
		title TEXT NOT NULL DEFAULT '',
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL,
		archived_at DATETIME
	)`,
	`CREATE TABLE strategy_chat_messages (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		session_id INTEGER NOT NULL REFERENCES strategy_chat_sessions (id) ON DELETE CASCADE,
		role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
		content TEXT NOT NULL,
		proposal TEXT,
		proposal_status TEXT CHECK (proposal_status IN ('pending', 'applied', 'created', 'dismissed')),
		proposal_result TEXT,
		provider TEXT NOT NULL DEFAULT '',
		model TEXT NOT NULL DEFAULT '',
		input_tokens INTEGER NOT NULL DEFAULT 0,
		output_tokens INTEGER NOT NULL DEFAULT 0,
		created_at DATETIME NOT NULL
	)`,
}

const chatRouteProposalReply = `{"reply":"Raise the entry threshold slightly. Backtests do not guarantee future results.","proposal":{"kind":"update","title":"Fewer entries","summary":"Trade less often.","suggested_name":"Majors calmer","changes":[{"field":"zscore_threshold","value":2.0,"reason":"Fewer weak signals."},{"field":"stats_window","value":30,"reason":"Steadier estimates."}]}}`

// chatRouteXAI stands in for the xAI Responses API on loopback.
type chatRouteXAI struct {
	mu       sync.Mutex
	status   int
	body     string
	requests []map[string]any
	gate     chan struct{}
	entered  chan struct{}
}

func (x *chatRouteXAI) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	var payload map[string]any
	_ = json.NewDecoder(r.Body).Decode(&payload)
	x.mu.Lock()
	x.requests = append(x.requests, payload)
	gate, entered, status, body := x.gate, x.entered, x.status, x.body
	x.mu.Unlock()
	if entered != nil {
		entered <- struct{}{}
	}
	if gate != nil {
		<-gate
	}
	if status == 0 {
		status = http.StatusOK
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = io.WriteString(w, body)
}

func (x *chatRouteXAI) respond(status int, body string) {
	x.mu.Lock()
	defer x.mu.Unlock()
	x.status, x.body = status, body
}

func (x *chatRouteXAI) requestCount() int {
	x.mu.Lock()
	defer x.mu.Unlock()
	return len(x.requests)
}

func chatRouteCompleted(text string) string {
	encoded, _ := json.Marshal(text)
	return `{"status":"completed","model":"grok-4.3","output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":` +
		string(encoded) + `}]}],"usage":{"input_tokens":900,"output_tokens":120,"output_tokens_details":{"reasoning_tokens":300}}}`
}

type chatRouteFixture struct {
	router     *gin.Engine
	db         *sql.DB
	xai        *chatRouteXAI
	ownerToken string
	otherToken string
	strategyID int
}

func setupChatRouteFixture(t *testing.T) *chatRouteFixture {
	t.Helper()
	gin.SetMode(gin.TestMode)

	xai := &chatRouteXAI{body: chatRouteCompleted(chatRouteProposalReply)}
	upstream := httptest.NewServer(xai)
	t.Cleanup(upstream.Close)

	// The repositories gate FOR UPDATE on the driver name.
	t.Setenv("DB_TYPE", "sqlite")
	t.Setenv("ENCRYPTION_KEY", "strategy-chat-route-test-key-1234")
	t.Setenv("XAI_BASE_URL", upstream.URL+"/v1/responses")
	t.Setenv("XAI_API_KEY", "test-xai-key")
	t.Setenv("XAI_MODEL", "")
	t.Setenv("XAI_ANALYSIS_MODEL", "")
	t.Setenv("XAI_REASONING_EFFORT", "")
	t.Setenv("XAI_ANALYSIS_REASONING_EFFORT", "")
	t.Setenv("AI_PROVIDER_GROK_ENABLED", "")
	t.Setenv("AI_CHAT_HTTP_TIMEOUT_SECONDS", "")
	t.Setenv("BOT_API_URL", "http://127.0.0.1:1")
	// With both set, the bot client does not load the developer's structured
	// config into the process environment, which would replace the JWT secret.
	t.Setenv("BOT_API_TOKEN", "strategy-chat-route-bot-token")
	t.Setenv("BOT_API_USE_SERVICE_TOKEN", "false")

	const jwtSecret = "strategy-chat-route-secret"
	t.Setenv("JWT_SECRET_KEY", jwtSecret)
	middleware.InitAuthMiddleware(&config.Config{
		Auth: config.AuthSettings{
			JWTSecretKey:             jwtSecret,
			JWTAlgorithm:             "HS256",
			AccessTokenExpireMinutes: 30,
			RefreshTokenExpireDays:   7,
		},
	})

	conn, err := sql.Open("sqlite", "file:chat-route-"+strings.ReplaceAll(t.Name(), "/", "_")+"?mode=memory&cache=shared")
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	conn.SetMaxOpenConns(1)
	t.Cleanup(func() { _ = conn.Close() })
	for _, statement := range chatRouteSchema {
		if _, err := conn.Exec(statement); err != nil {
			t.Fatalf("create schema: %v", err)
		}
	}
	for id := 1; id <= 2; id++ {
		if _, err := conn.Exec(`INSERT INTO users (id, username, email) VALUES (?, ?, ?)`,
			id, fmt.Sprintf("chat-user-%d", id), fmt.Sprintf("chat-user-%d@example.local", id)); err != nil {
			t.Fatalf("insert user: %v", err)
		}
	}
	strategies := services.NewStrategyService(repository.NewStrategyRepository(conn))
	strategy, err := strategies.CreateStrategy(1, "Majors pairs", "BTC/ETH pairs", "pairs_trading", false, false)
	if err != nil {
		t.Fatalf("create strategy: %v", err)
	}
	strategy.MaxDrawdownPct = 15
	strategy.SetSelectedMarketList([]string{"BTC-USD", "ETH-USD"})
	if err := strategies.UpdateStrategy(strategy); err != nil {
		t.Fatalf("update strategy: %v", err)
	}

	manager := auth.NewManager(auth.JWTConfig{Secret: jwtSecret, ExpiryHours: 1, RefreshExpiryDays: 7})
	ownerToken, _, err := manager.CreateAccessToken(1, "chat-user-1", "chat-user-1@example.local", false)
	if err != nil {
		t.Fatalf("create token: %v", err)
	}
	otherToken, _, err := manager.CreateAccessToken(2, "chat-user-2", "chat-user-2@example.local", false)
	if err != nil {
		t.Fatalf("create token: %v", err)
	}

	router := gin.New()
	RegisterStrategyRoutes(router, &backenddb.Database{DB: conn})
	return &chatRouteFixture{router: router, db: conn, xai: xai, ownerToken: ownerToken, otherToken: otherToken, strategyID: strategy.ID}
}

// serve runs one request through the router; it is safe off the test goroutine.
func (f *chatRouteFixture) serve(method, path, token string, body any) (int, map[string]any, error) {
	var reader io.Reader = http.NoBody
	if body != nil {
		encoded, err := json.Marshal(body)
		if err != nil {
			return 0, nil, err
		}
		reader = bytes.NewReader(encoded)
	}
	request := httptest.NewRequest(method, path, reader)
	request.Header.Set("Authorization", "Bearer "+token)
	request.Header.Set("Content-Type", "application/json")
	recorder := httptest.NewRecorder()
	f.router.ServeHTTP(recorder, request)
	var envelope map[string]any
	if err := json.Unmarshal(recorder.Body.Bytes(), &envelope); err != nil {
		return recorder.Code, nil, fmt.Errorf("decode %s %s response %q: %w", method, path, recorder.Body.String(), err)
	}
	return recorder.Code, envelope, nil
}

func (f *chatRouteFixture) call(t *testing.T, method, path, token string, body any) (int, map[string]any) {
	t.Helper()
	status, envelope, err := f.serve(method, path, token, body)
	if err != nil {
		t.Fatal(err)
	}
	return status, envelope
}

func (f *chatRouteFixture) chatPath(suffix string) string {
	return fmt.Sprintf("/api/v1/strategies/%d/chat%s", f.strategyID, suffix)
}

func (f *chatRouteFixture) send(t *testing.T, content string) (int, map[string]any) {
	t.Helper()
	return f.call(t, http.MethodPost, f.chatPath("/messages"), f.ownerToken, map[string]any{"content": content})
}

func chatRouteExpectError(t *testing.T, status int, envelope map[string]any, wantStatus int, wantCode string) {
	t.Helper()
	if status != wantStatus || envelope["code"] != wantCode || envelope["success"] != false {
		t.Fatalf("expected %d %s, got %d %+v", wantStatus, wantCode, status, envelope)
	}
	if message, _ := envelope["error"].(string); message == "" {
		t.Fatalf("expected a human error message, got %+v", envelope)
	}
	if _, ok := envelope["timestamp"].(string); !ok {
		t.Fatalf("expected a timestamp, got %+v", envelope)
	}
}

func chatRouteKeys(value any) []string {
	object, _ := value.(map[string]any)
	keys := make([]string, 0, len(object))
	for key := range object {
		keys = append(keys, key)
	}
	return keys
}

func chatRouteRequireKeys(t *testing.T, what string, value any, keys ...string) map[string]any {
	t.Helper()
	object, ok := value.(map[string]any)
	if !ok {
		t.Fatalf("expected %s to be an object, got %#v", what, value)
	}
	for _, key := range keys {
		if _, present := object[key]; !present {
			t.Fatalf("expected %s.%s, got keys %v", what, key, chatRouteKeys(value))
		}
	}
	return object
}

func (f *chatRouteFixture) count(t *testing.T, query string, args ...any) int {
	t.Helper()
	var count int
	if err := f.db.QueryRow(query, args...).Scan(&count); err != nil {
		t.Fatalf("count: %v", err)
	}
	return count
}

func TestStrategyChatRoutesContract(t *testing.T) {
	f := setupChatRouteFixture(t)

	status, envelope := f.call(t, http.MethodGet, f.chatPath(""), f.ownerToken, nil)
	data := chatRouteRequireKeys(t, "data", envelope["data"], "session", "messages", "runtime_active")
	if status != http.StatusOK || envelope["success"] != true || data["session"] != nil || data["runtime_active"] != false {
		t.Fatalf("unexpected empty chat %d %+v", status, envelope)
	}
	if messages, _ := data["messages"].([]any); messages == nil || len(messages) != 0 {
		t.Fatalf("expected messages [], got %#v", data["messages"])
	}

	status, envelope = f.send(t, "Should I trade less often?")
	if status != http.StatusOK {
		t.Fatalf("expected 200, got %d %+v", status, envelope)
	}
	data = chatRouteRequireKeys(t, "data", envelope["data"], "session", "messages")
	chatRouteRequireKeys(t, "session", data["session"], "id", "strategy_id", "title", "created_at", "updated_at")
	messages, _ := data["messages"].([]any)
	if len(messages) != 2 {
		t.Fatalf("expected [user, assistant], got %#v", data["messages"])
	}
	messageKeys := []string{"id", "session_id", "role", "content", "proposal", "proposal_status", "proposal_result", "provider", "model", "created_at"}
	user := chatRouteRequireKeys(t, "user message", messages[0], messageKeys...)
	assistant := chatRouteRequireKeys(t, "assistant message", messages[1], messageKeys...)
	if user["role"] != "user" || user["proposal"] != nil || user["proposal_status"] != nil || user["provider"] != "grok" {
		t.Fatalf("unexpected user message %+v", user)
	}
	if assistant["role"] != "assistant" || assistant["proposal_status"] != "pending" || assistant["proposal_result"] != nil || assistant["model"] != "grok-4.7" {
		t.Fatalf("unexpected assistant message %+v", assistant)
	}
	proposal := chatRouteRequireKeys(t, "proposal", assistant["proposal"], "kind", "title", "summary", "suggested_name", "changes", "dropped")
	changes, _ := proposal["changes"].([]any)
	if len(changes) != 2 {
		t.Fatalf("expected two changes, got %#v", proposal["changes"])
	}
	change := chatRouteRequireKeys(t, "change", changes[0], "field", "label", "unit", "current", "proposed", "reason", "risk", "backtest_only")
	if change["field"] != "zscore_threshold" || change["current"] != 1.5 || change["proposed"] != 2.0 || change["risk"] != "normal" {
		t.Fatalf("unexpected change %+v", change)
	}

	// The provider saw a stateless, strict Responses API request.
	if f.xai.requestCount() != 1 {
		t.Fatalf("expected one provider call, got %d", f.xai.requestCount())
	}
	f.xai.mu.Lock()
	sent := f.xai.requests[0]
	f.xai.mu.Unlock()
	if sent["store"] != false || sent["model"] != "grok-4.7" || sent["temperature"] != nil {
		t.Fatalf("unexpected provider request %+v", sent)
	}
	input, _ := sent["input"].([]any)
	system := input[0].(map[string]any)["content"].(string)
	if !strings.Contains(system, "<strategy_data>") || strings.Contains(system, `"user_id"`) || strings.Contains(system, "chat-user-1@example.local") {
		t.Fatalf("unexpected system prompt: %s", system)
	}

	// An unrelated snapshot first, so the apply's row id differs from its
	// version number and the two cannot be confused below.
	if _, err := f.db.Exec(`INSERT INTO strategy_version_history (strategy_id, version_number, config_snapshot, created_at) VALUES (999, 1, '{}', ?)`, time.Now().UTC()); err != nil {
		t.Fatalf("insert unrelated version: %v", err)
	}
	messageID := int64(assistant["id"].(float64))
	status, envelope = f.call(t, http.MethodPost, f.chatPath(fmt.Sprintf("/messages/%d/apply", messageID)), f.ownerToken, map[string]any{"fields": []string{"zscore_threshold"}})
	if status != http.StatusOK {
		t.Fatalf("expected apply 200, got %d %+v", status, envelope)
	}
	data = chatRouteRequireKeys(t, "data", envelope["data"], "strategy", "message")
	strategy := chatRouteRequireKeys(t, "strategy", data["strategy"], "id", "zscore_threshold", "stats_window", "candle_resolution")
	if strategy["zscore_threshold"] != 2.0 || strategy["stats_window"] != float64(21) {
		t.Fatalf("expected only zscore_threshold applied, got %+v", strategy)
	}
	applied := chatRouteRequireKeys(t, "message", data["message"], messageKeys...)
	result := chatRouteRequireKeys(t, "proposal_result", applied["proposal_result"], "applied_fields", "unchanged_fields", "version_id", "at")
	if applied["proposal_status"] != "applied" {
		t.Fatalf("expected applied, got %+v", applied)
	}
	var snapshotID, snapshotNumber int
	if err := f.db.QueryRow(`SELECT id, version_number FROM strategy_version_history WHERE strategy_id = ?`, f.strategyID).Scan(&snapshotID, &snapshotNumber); err != nil {
		t.Fatalf("read snapshot row: %v", err)
	}
	if result["version_id"] != float64(snapshotID) || snapshotID == snapshotNumber {
		t.Fatalf("expected version_id to be the row id %d, not the version number %d, got %v", snapshotID, snapshotNumber, result["version_id"])
	}

	var action, details string
	if err := f.db.QueryRow(`SELECT action, details FROM audit_logs ORDER BY id DESC LIMIT 1`).Scan(&action, &details); err != nil {
		t.Fatalf("read audit log: %v", err)
	}
	if action != "strategy.assistant.apply" || !strings.Contains(details, `"before"`) || !strings.Contains(details, `"after"`) {
		t.Fatalf("unexpected audit row %s %s", action, details)
	}

	// The saved snapshot restores the strategy through the existing revert route.
	versionID := int(result["version_id"].(float64))
	status, envelope = f.call(t, http.MethodPost, fmt.Sprintf("/api/v1/strategies/%d/versions/%d/revert", f.strategyID, versionID), f.ownerToken, nil)
	reverted, _ := envelope["data"].(map[string]any)
	if status != http.StatusOK || reverted["zscore_threshold"] != 1.5 || reverted["max_drawdown_pct"] != 15.0 || reverted["user_id"] != float64(1) {
		t.Fatalf("expected revert to restore zscore 1.5, got %d %+v", status, envelope)
	}

	status, envelope = f.call(t, http.MethodPost, f.chatPath(fmt.Sprintf("/messages/%d/apply", messageID)), f.ownerToken, nil)
	chatRouteExpectError(t, status, envelope, http.StatusConflict, "PROPOSAL_NOT_PENDING")
}

func TestStrategyChatRoutesErrorCodes(t *testing.T) {
	f := setupChatRouteFixture(t)

	status, envelope := f.call(t, http.MethodGet, f.chatPath(""), f.otherToken, nil)
	chatRouteExpectError(t, status, envelope, http.StatusNotFound, "NOT_FOUND")
	status, envelope = f.call(t, http.MethodPost, f.chatPath("/messages"), f.otherToken, map[string]any{"content": "hi"})
	chatRouteExpectError(t, status, envelope, http.StatusNotFound, "NOT_FOUND")
	status, envelope = f.call(t, http.MethodGet, "/api/v1/strategies/9999/chat", f.ownerToken, nil)
	chatRouteExpectError(t, status, envelope, http.StatusNotFound, "NOT_FOUND")

	status, envelope = f.send(t, "   ")
	chatRouteExpectError(t, status, envelope, http.StatusBadRequest, "INVALID_REQUEST")
	status, envelope = f.send(t, strings.Repeat("x", 4001))
	chatRouteExpectError(t, status, envelope, http.StatusBadRequest, "INVALID_REQUEST")
	status, envelope = f.call(t, http.MethodPost, f.chatPath("/messages"), f.ownerToken, map[string]any{"content": "hi", "provider": "gemini"})
	chatRouteExpectError(t, status, envelope, http.StatusBadRequest, "INVALID_REQUEST")
	status, envelope = f.call(t, http.MethodPost, f.chatPath("/messages/abc/apply"), f.ownerToken, nil)
	chatRouteExpectError(t, status, envelope, http.StatusBadRequest, "INVALID_REQUEST")
	status, envelope = f.call(t, http.MethodPost, f.chatPath("/messages/12345/dismiss"), f.ownerToken, nil)
	chatRouteExpectError(t, status, envelope, http.StatusNotFound, "NOT_FOUND")
	if f.xai.requestCount() != 0 {
		t.Fatal("expected no provider call for refused requests")
	}

	f.xai.respond(http.StatusInternalServerError, `{"error":{"message":"overloaded"}}`)
	status, envelope = f.send(t, "hello")
	chatRouteExpectError(t, status, envelope, http.StatusBadGateway, "AI_PROVIDER_ERROR")
	if f.count(t, `SELECT COUNT(*) FROM strategy_chat_messages`) != 0 || f.count(t, `SELECT COUNT(*) FROM strategy_chat_sessions`) != 0 {
		t.Fatal("expected nothing persisted after a provider failure")
	}
}

func TestStrategyChatRoutesProviderAccessCodes(t *testing.T) {
	f := setupChatRouteFixture(t)
	t.Setenv("AI_PROVIDER_GROK_ENABLED", "false")
	status, envelope := f.send(t, "hello")
	chatRouteExpectError(t, status, envelope, http.StatusForbidden, "AI_PROVIDER_DISABLED")

	t.Setenv("AI_PROVIDER_GROK_ENABLED", "")
	t.Setenv("XAI_API_KEY", "")
	status, envelope = f.send(t, "hello")
	chatRouteExpectError(t, status, envelope, http.StatusConflict, "AI_PROVIDER_NOT_CONFIGURED")
	if f.xai.requestCount() != 0 {
		t.Fatal("expected no provider call without access")
	}
}

func TestStrategyChatRoutesRateLimit(t *testing.T) {
	f := setupChatRouteFixture(t)
	for i := 0; i < 3; i++ {
		if status, envelope := f.send(t, fmt.Sprintf("question %d", i)); status != http.StatusOK {
			t.Fatalf("turn %d: expected 200, got %d %+v", i, status, envelope)
		}
	}
	status, envelope := f.send(t, "one more")
	chatRouteExpectError(t, status, envelope, http.StatusTooManyRequests, "CHAT_RATE_LIMITED")
}

func TestStrategyChatRoutesOneTurnInFlightPerUser(t *testing.T) {
	f := setupChatRouteFixture(t)
	gate := make(chan struct{})
	f.xai.mu.Lock()
	f.xai.gate = gate
	f.xai.entered = make(chan struct{}, 4)
	f.xai.mu.Unlock()

	firstStatus := make(chan int, 1)
	go func() {
		status, _, _ := f.serve(http.MethodPost, f.chatPath("/messages"), f.ownerToken, map[string]any{"content": "slow question"})
		firstStatus <- status
	}()
	select {
	case <-f.xai.entered:
	case <-time.After(5 * time.Second):
		t.Fatal("first turn never reached the provider")
	}

	status, envelope := f.send(t, "impatient question")
	chatRouteExpectError(t, status, envelope, http.StatusTooManyRequests, "CHAT_BUSY")

	f.xai.mu.Lock()
	f.xai.gate = nil
	f.xai.entered = nil
	f.xai.mu.Unlock()
	close(gate)
	if status := <-firstStatus; status != http.StatusOK {
		t.Fatalf("expected the first turn to finish, got %d", status)
	}

	// The slot was released, including after a failed turn.
	f.xai.respond(http.StatusBadRequest, `{"code":"bad","error":"nope"}`)
	status, envelope = f.send(t, "fails")
	chatRouteExpectError(t, status, envelope, http.StatusBadGateway, "AI_PROVIDER_ERROR")
	f.xai.respond(http.StatusOK, chatRouteCompleted(chatRouteProposalReply))
	// Third token of the burst: the refused CHAT_BUSY call did not use one.
	if status, envelope := f.send(t, "after"); status != http.StatusOK {
		t.Fatalf("expected the in-flight slot released, got %d %+v", status, envelope)
	}
}

func TestStrategyChatRoutesRunningAckCreateAndDismiss(t *testing.T) {
	f := setupChatRouteFixture(t)
	_, first := f.send(t, "tune it")
	firstID := int64(first["data"].(map[string]any)["messages"].([]any)[1].(map[string]any)["id"].(float64))
	_, second := f.send(t, "and a variant")
	secondID := int64(second["data"].(map[string]any)["messages"].([]any)[1].(map[string]any)["id"].(float64))

	now := time.Now().UTC()
	if _, err := f.db.Exec(`INSERT INTO strategy_execution_states (strategy_id, is_running, state, created_at, updated_at) VALUES (?, 1, '{"status":"running"}', ?, ?)`,
		f.strategyID, now, now); err != nil {
		t.Fatalf("insert execution state: %v", err)
	}
	status, envelope := f.call(t, http.MethodGet, f.chatPath(""), f.ownerToken, nil)
	if status != http.StatusOK || envelope["data"].(map[string]any)["runtime_active"] != true {
		t.Fatalf("expected runtime_active true, got %d %+v", status, envelope)
	}
	status, envelope = f.call(t, http.MethodPost, f.chatPath(fmt.Sprintf("/messages/%d/apply", firstID)), f.ownerToken, map[string]any{})
	chatRouteExpectError(t, status, envelope, http.StatusConflict, "STRATEGY_RUNNING_ACK_REQUIRED")
	status, envelope = f.call(t, http.MethodPost, f.chatPath(fmt.Sprintf("/messages/%d/apply", firstID)), f.ownerToken, map[string]any{"fields": []string{"nope"}, "acknowledge_running": true})
	chatRouteExpectError(t, status, envelope, http.StatusBadRequest, "INVALID_PROPOSAL_FIELDS")
	status, envelope = f.call(t, http.MethodPost, f.chatPath(fmt.Sprintf("/messages/%d/apply", firstID)), f.ownerToken, map[string]any{"acknowledge_running": true})
	if status != http.StatusOK {
		t.Fatalf("expected apply with acknowledgement, got %d %+v", status, envelope)
	}
	result := envelope["data"].(map[string]any)["message"].(map[string]any)["proposal_result"].(map[string]any)
	if result["acknowledged_running"] != true {
		t.Fatalf("expected acknowledged_running recorded, got %+v", result)
	}

	status, envelope = f.call(t, http.MethodPost, f.chatPath(fmt.Sprintf("/messages/%d/create-strategy", secondID)), f.ownerToken, map[string]any{"name": "Majors calmer copy"})
	if status != http.StatusCreated {
		t.Fatalf("expected 201, got %d %+v", status, envelope)
	}
	data := chatRouteRequireKeys(t, "data", envelope["data"], "strategy", "message")
	created := data["strategy"].(map[string]any)
	if created["name"] != "Majors calmer copy" || created["user_id"] != float64(1) || created["is_public"] != false || created["id"] == float64(f.strategyID) {
		t.Fatalf("unexpected created strategy %+v", created)
	}
	message := data["message"].(map[string]any)
	createdResult := chatRouteRequireKeys(t, "proposal_result", message["proposal_result"], "applied_fields", "unchanged_fields", "new_strategy_id", "at")
	if message["proposal_status"] != "created" || createdResult["new_strategy_id"] != created["id"] {
		t.Fatalf("unexpected created message %+v", message)
	}
	// Every selected change already matched the source (the first apply set
	// the same values), so applied_fields is present and empty.
	if appliedFields, ok := createdResult["applied_fields"].([]any); !ok || len(appliedFields) != 0 {
		t.Fatalf("expected applied_fields [], got %#v", createdResult["applied_fields"])
	}
	if unchanged, _ := createdResult["unchanged_fields"].([]any); len(unchanged) != 2 || unchanged[0] != "zscore_threshold" || unchanged[1] != "stats_window" {
		t.Fatalf("expected unchanged_fields [zscore_threshold stats_window], got %#v", createdResult["unchanged_fields"])
	}
	if created["stats_window"] != float64(30) {
		t.Fatalf("expected the copy to carry the source's current stats_window 30, got %v", created["stats_window"])
	}
	if f.count(t, `SELECT COUNT(*) FROM audit_logs WHERE action = 'strategy.assistant.create' AND details LIKE '%source_strategy_id%'`) != 1 {
		t.Fatal("expected a strategy.assistant.create audit row")
	}

	status, envelope = f.call(t, http.MethodPost, f.chatPath(fmt.Sprintf("/messages/%d/dismiss", secondID)), f.ownerToken, nil)
	chatRouteExpectError(t, status, envelope, http.StatusConflict, "PROPOSAL_NOT_PENDING")

	if _, err := f.db.Exec(`UPDATE users SET max_strategies = 2 WHERE id = 1`); err != nil {
		t.Fatalf("set quota: %v", err)
	}
	_, third := f.send(t, "another variant")
	thirdID := int64(third["data"].(map[string]any)["messages"].([]any)[1].(map[string]any)["id"].(float64))
	status, envelope = f.call(t, http.MethodPost, f.chatPath(fmt.Sprintf("/messages/%d/create-strategy", thirdID)), f.ownerToken, nil)
	chatRouteExpectError(t, status, envelope, http.StatusTooManyRequests, "STRATEGY_QUOTA_EXCEEDED")

	status, envelope = f.call(t, http.MethodPost, f.chatPath(fmt.Sprintf("/messages/%d/dismiss", thirdID)), f.ownerToken, nil)
	if status != http.StatusOK || envelope["data"].(map[string]any)["message"].(map[string]any)["proposal_status"] != "dismissed" {
		t.Fatalf("expected dismiss 200, got %d %+v", status, envelope)
	}

	status, envelope = f.call(t, http.MethodPost, f.chatPath("/sessions"), f.ownerToken, nil)
	fresh := chatRouteRequireKeys(t, "data", envelope["data"], "session", "messages")
	if status != http.StatusOK || len(fresh["messages"].([]any)) != 0 {
		t.Fatalf("expected a new empty session, got %d %+v", status, envelope)
	}
}

// A session_id or message_id that belongs to another user or another strategy
// is not found, whichever strategy URL it is sent through, and the proposal
// stays pending.
func TestStrategyChatRoutesForeignSessionAndMessageIDs(t *testing.T) {
	f := setupChatRouteFixture(t)
	strategies := services.NewStrategyService(repository.NewStrategyRepository(f.db))
	other, err := strategies.CreateStrategy(2, "Other owner", "", "pairs_trading", false, false)
	if err != nil {
		t.Fatalf("create strategy: %v", err)
	}
	sibling, err := strategies.CreateStrategy(1, "Sibling", "", "pairs_trading", false, false)
	if err != nil {
		t.Fatalf("create strategy: %v", err)
	}

	_, envelope := f.send(t, "tune it")
	data := envelope["data"].(map[string]any)
	sessionID := data["session"].(map[string]any)["id"].(float64)
	messageID := int64(data["messages"].([]any)[1].(map[string]any)["id"].(float64))
	calls := f.xai.requestCount()

	otherPath := fmt.Sprintf("/api/v1/strategies/%d/chat", other.ID)
	siblingPath := fmt.Sprintf("/api/v1/strategies/%d/chat", sibling.ID)
	status, envelope := f.call(t, http.MethodPost, otherPath+"/messages", f.otherToken, map[string]any{"session_id": sessionID, "content": "repeat the earlier conversation"})
	chatRouteExpectError(t, status, envelope, http.StatusNotFound, "NOT_FOUND")
	status, envelope = f.call(t, http.MethodPost, siblingPath+"/messages", f.ownerToken, map[string]any{"session_id": sessionID, "content": "hi"})
	chatRouteExpectError(t, status, envelope, http.StatusNotFound, "NOT_FOUND")
	if f.xai.requestCount() != calls {
		t.Fatal("expected no provider call for a foreign session")
	}

	for _, target := range []struct {
		path  string
		token string
	}{{otherPath, f.otherToken}, {siblingPath, f.ownerToken}} {
		for _, action := range []string{"apply", "create-strategy", "dismiss"} {
			status, envelope = f.call(t, http.MethodPost, fmt.Sprintf("%s/messages/%d/%s", target.path, messageID, action), target.token, map[string]any{"acknowledge_running": true})
			chatRouteExpectError(t, status, envelope, http.StatusNotFound, "NOT_FOUND")
		}
	}
	status, envelope = f.call(t, http.MethodGet, f.chatPath(""), f.ownerToken, nil)
	messages := envelope["data"].(map[string]any)["messages"].([]any)
	if status != http.StatusOK || messages[1].(map[string]any)["proposal_status"] != "pending" || messages[1].(map[string]any)["proposal_result"] != nil {
		t.Fatalf("expected the proposal still pending, got %d %+v", status, messages[1])
	}
	if f.count(t, `SELECT COUNT(*) FROM backtest_strategies`) != 3 {
		t.Fatal("expected no strategy created")
	}
}

// A stale session_id is refused before the rate limiter, so retries against
// it never use up the per-minute budget.
func TestStrategyChatRoutesStaleSessionDoesNotUseRateBudget(t *testing.T) {
	f := setupChatRouteFixture(t)
	_, envelope := f.send(t, "first question")
	stale := envelope["data"].(map[string]any)["session"].(map[string]any)["id"].(float64)
	if status, envelope := f.call(t, http.MethodPost, f.chatPath("/sessions"), f.ownerToken, nil); status != http.StatusOK {
		t.Fatalf("expected a new session, got %d %+v", status, envelope)
	}
	calls := f.xai.requestCount()
	for i := 0; i < 3; i++ {
		status, envelope := f.call(t, http.MethodPost, f.chatPath("/messages"), f.ownerToken, map[string]any{"session_id": stale, "content": "hello?"})
		chatRouteExpectError(t, status, envelope, http.StatusNotFound, "NOT_FOUND")
	}
	if f.xai.requestCount() != calls {
		t.Fatal("expected no provider call for a stale session")
	}
	// The first turn used one of the three burst tokens; two are left.
	for i := 0; i < 2; i++ {
		if status, envelope := f.send(t, fmt.Sprintf("question %d", i)); status != http.StatusOK {
			t.Fatalf("turn %d: expected the budget untouched by stale sends, got %d %+v", i, status, envelope)
		}
	}
	status, envelope := f.send(t, "one more")
	chatRouteExpectError(t, status, envelope, http.StatusTooManyRequests, "CHAT_RATE_LIMITED")
}
