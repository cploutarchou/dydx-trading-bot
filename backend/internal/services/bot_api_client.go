package services

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
)

// BotAPIClient handles communication with the Python bot API
type BotAPIClient struct {
	baseURL       string
	fallbackURLs  []string
	token         string
	fallbackToken string
	traceID       string
	requestCtx    context.Context
	httpClient    *http.Client
}

const defaultBotAPIRequestTimeout = 120 * time.Second

type BotAPIStatsSnapshot struct {
	TotalRequests        int64 `json:"total_requests"`
	SuccessfulRequests   int64 `json:"successful_requests"`
	FailedRequests       int64 `json:"failed_requests"`
	TransportFailures    int64 `json:"transport_failures"`
	Timeouts             int64 `json:"timeouts"`
	Upstream4xx          int64 `json:"upstream_4xx"`
	Upstream5xx          int64 `json:"upstream_5xx"`
	TotalLatencyMillis   int64 `json:"total_latency_ms"`
	AverageLatencyMillis int64 `json:"average_latency_ms"`
	MaxLatencyMillis     int64 `json:"max_latency_ms"`
}

type botAPIStatsCollector struct {
	totalRequests      atomic.Int64
	successfulRequests atomic.Int64
	failedRequests     atomic.Int64
	transportFailures  atomic.Int64
	timeouts           atomic.Int64
	upstream4xx        atomic.Int64
	upstream5xx        atomic.Int64
	totalLatencyMillis atomic.Int64
	maxLatencyMillis   atomic.Int64
}

var botAPIStats botAPIStatsCollector

func BotAPIStats() BotAPIStatsSnapshot {
	total := botAPIStats.totalRequests.Load()
	totalLatency := botAPIStats.totalLatencyMillis.Load()
	averageLatency := int64(0)
	if total > 0 {
		averageLatency = totalLatency / total
	}
	return BotAPIStatsSnapshot{
		TotalRequests:        total,
		SuccessfulRequests:   botAPIStats.successfulRequests.Load(),
		FailedRequests:       botAPIStats.failedRequests.Load(),
		TransportFailures:    botAPIStats.transportFailures.Load(),
		Timeouts:             botAPIStats.timeouts.Load(),
		Upstream4xx:          botAPIStats.upstream4xx.Load(),
		Upstream5xx:          botAPIStats.upstream5xx.Load(),
		TotalLatencyMillis:   totalLatency,
		AverageLatencyMillis: averageLatency,
		MaxLatencyMillis:     botAPIStats.maxLatencyMillis.Load(),
	}
}

func recordBotAPIRequest(statusCode int, latency time.Duration, err error) {
	latencyMillis := latency.Milliseconds()
	botAPIStats.totalRequests.Add(1)
	botAPIStats.totalLatencyMillis.Add(latencyMillis)
	for {
		current := botAPIStats.maxLatencyMillis.Load()
		if latencyMillis <= current || botAPIStats.maxLatencyMillis.CompareAndSwap(current, latencyMillis) {
			break
		}
	}

	if err != nil {
		botAPIStats.failedRequests.Add(1)
		var transportErr *BotAPITransportError
		if errors.As(err, &transportErr) {
			botAPIStats.transportFailures.Add(1)
			if transportErr.StatusCode == http.StatusGatewayTimeout {
				botAPIStats.timeouts.Add(1)
			}
		}
		return
	}

	if statusCode >= 200 && statusCode < 400 {
		botAPIStats.successfulRequests.Add(1)
		return
	}

	botAPIStats.failedRequests.Add(1)
	if statusCode >= 400 && statusCode < 500 {
		botAPIStats.upstream4xx.Add(1)
	} else if statusCode >= 500 {
		botAPIStats.upstream5xx.Add(1)
	}
}

// BotAPIError preserves upstream HTTP status and message for delegated routes.
type BotAPIError struct {
	StatusCode int
	Message    string
}

func (e *BotAPIError) Error() string {
	if e == nil {
		return "bot API error"
	}
	if strings.TrimSpace(e.Message) == "" {
		return fmt.Sprintf("API error (status %d)", e.StatusCode)
	}
	return fmt.Sprintf("API error (status %d): %s", e.StatusCode, e.Message)
}

// BotAPITransportError represents a transport-level failure when communicating
// with the upstream bot API (e.g. connection refused, timeout).
// StatusCode is 502 (Bad Gateway) for connectivity failures and 504 (Gateway
// Timeout) for deadline/timeout failures, so callers can propagate the correct
// HTTP status to the client without further inspection.
type BotAPITransportError struct {
	StatusCode int    // 502 or 504
	Message    string // human-readable, safe to surface to API clients
	Endpoint   string // full request URL — for log context only
	Cause      error  // original transport error
}

func (e *BotAPITransportError) Error() string {
	if e == nil {
		return "bot API transport error"
	}
	return fmt.Sprintf("%s [upstream: %s]", e.Message, e.Endpoint)
}

// Unwrap allows errors.Is / errors.As to inspect the underlying transport error.
func (e *BotAPITransportError) Unwrap() error {
	return e.Cause
}

// classifyTransportError maps a raw HTTP-transport error to a BotAPITransportError
// with an actionable status code and message:
//   - context.DeadlineExceeded or net.Error.Timeout() → 504 Gateway Timeout
//   - connection refused (any OS phrasing)              → 502 Bad Gateway
//   - all other transport failures                      → 502 Bad Gateway
func classifyTransportError(method, requestURL string, err error) *BotAPITransportError {
	// --- timeout ---
	if errors.Is(err, context.DeadlineExceeded) {
		return &BotAPITransportError{
			StatusCode: http.StatusGatewayTimeout,
			Message:    "upstream bot API request timed out",
			Endpoint:   requestURL,
			Cause:      err,
		}
	}
	var netErr net.Error
	if errors.As(err, &netErr) && netErr.Timeout() {
		return &BotAPITransportError{
			StatusCode: http.StatusGatewayTimeout,
			Message:    "upstream bot API request timed out",
			Endpoint:   requestURL,
			Cause:      err,
		}
	}

	// --- connection refused (cross-platform string match covers common OS-specific phrasing) ---
	lowerMsg := strings.ToLower(err.Error())
	if strings.Contains(lowerMsg, "connection refused") ||
		strings.Contains(lowerMsg, "actively refused") {
		return &BotAPITransportError{
			StatusCode: http.StatusBadGateway,
			Message:    "upstream bot API is not reachable (connection refused) – ensure the bot service is running",
			Endpoint:   requestURL,
			Cause:      err,
		}
	}

	// --- generic transport failure (DNS, TLS, etc.) ---
	return &BotAPITransportError{
		StatusCode: http.StatusBadGateway,
		Message:    "upstream bot API transport failure",
		Endpoint:   requestURL,
		Cause:      err,
	}
}

func ensureStructuredBotAPIEnvLoaded() {
	if strings.TrimSpace(os.Getenv("BOT_API_TOKEN")) != "" && strings.TrimSpace(os.Getenv("BOT_API_USE_SERVICE_TOKEN")) != "" {
		return
	}
	_, _ = config.AutoLoadStructuredConfigEnv(false)
}

// ResolveConfiguredBotAPIServiceToken returns the configured shared token used
// for backend→bot API delegation, best-effort loading structured config first
// when the current process environment was not preloaded.
func ResolveConfiguredBotAPIServiceToken() string {
	ensureStructuredBotAPIEnvLoaded()
	return strings.TrimSpace(os.Getenv("BOT_API_TOKEN"))
}

// UseConfiguredBotAPIServiceToken reports whether downstream bot API requests
// should prefer the configured shared service token instead of forwarding the
// caller JWT. A configured token defaults to enabled unless explicitly set to
// false via BOT_API_USE_SERVICE_TOKEN=false.
func UseConfiguredBotAPIServiceToken() bool {
	ensureStructuredBotAPIEnvLoaded()
	if ResolveConfiguredBotAPIServiceToken() == "" {
		return false
	}

	switch strings.ToLower(strings.TrimSpace(os.Getenv("BOT_API_USE_SERVICE_TOKEN"))) {
	case "", "1", "true", "yes", "on":
		return true
	default:
		return false
	}
}

// NewBotAPIClient creates a new bot API client
func NewBotAPIClient(baseURL string, token string) *BotAPIClient {
	token = strings.TrimSpace(token)
	if token == "" {
		token = ResolveConfiguredBotAPIServiceToken()
	}
	requestTimeout := resolveBotAPIRequestTimeout()
	primaryURL := strings.TrimRight(strings.TrimSpace(baseURL), "/")
	fallbackURLs := resolveBotAPIFallbackURLs(primaryURL)
	return &BotAPIClient{
		baseURL:       primaryURL,
		fallbackURLs:  fallbackURLs,
		token:         token,
		fallbackToken: token,
		requestCtx:    context.Background(),
		httpClient: &http.Client{
			Timeout: requestTimeout,
		},
	}
}

func resolveBotAPIFallbackURLs(primaryURL string) []string {
	raw := strings.TrimSpace(os.Getenv("BOT_API_FALLBACK_URLS"))
	if raw == "" {
		return []string{}
	}

	parts := strings.Split(raw, ",")
	seen := map[string]struct{}{}
	result := make([]string, 0, len(parts))
	primaryURL = strings.TrimRight(strings.TrimSpace(primaryURL), "/")

	for _, part := range parts {
		candidate := strings.TrimRight(strings.TrimSpace(part), "/")
		if candidate == "" || strings.EqualFold(candidate, primaryURL) {
			continue
		}
		if _, exists := seen[strings.ToLower(candidate)]; exists {
			continue
		}
		seen[strings.ToLower(candidate)] = struct{}{}
		result = append(result, candidate)
	}

	return result
}

func resolveBotAPIRequestTimeout() time.Duration {
	for _, key := range []string{"BOT_API_TIMEOUT_SECONDS", "BOT_API_TIMEOUT"} {
		raw := strings.TrimSpace(os.Getenv(key))
		if raw == "" {
			continue
		}
		seconds, err := strconv.Atoi(raw)
		if err != nil || seconds <= 0 {
			log.Printf("⚠️  Invalid %s=%q; using default timeout %s", key, raw, defaultBotAPIRequestTimeout)
			return defaultBotAPIRequestTimeout
		}
		return time.Duration(seconds) * time.Second
	}
	return defaultBotAPIRequestTimeout
}

// SetToken sets the authentication token
func (c *BotAPIClient) SetToken(token string) {
	token = strings.TrimSpace(token)
	c.token = token
	c.fallbackToken = token
}

// BaseURL returns the configured upstream bot API base URL.
func (c *BotAPIClient) BaseURL() string {
	return c.baseURL
}

// AuthToken returns the configured token (if any).
func (c *BotAPIClient) AuthToken() string {
	token := strings.TrimSpace(c.token)
	if token != "" {
		return token
	}
	return c.effectiveFallbackToken()
}

func (c *BotAPIClient) effectiveFallbackToken() string {
	fallbackToken := strings.TrimSpace(c.fallbackToken)
	if fallbackToken != "" {
		return fallbackToken
	}
	return ResolveConfiguredBotAPIServiceToken()
}

// WebSocketURL builds a websocket URL from the configured base URL and endpoint.
func (c *BotAPIClient) WebSocketURL(endpoint string) (string, error) {
	base, err := url.Parse(c.baseURL)
	if err != nil {
		return "", fmt.Errorf("failed to parse bot API base URL: %w", err)
	}

	switch strings.ToLower(base.Scheme) {
	case "http":
		base.Scheme = "ws"
	case "https":
		base.Scheme = "wss"
	case "ws", "wss":
		// already a websocket URL
	default:
		return "", fmt.Errorf("unsupported bot API URL scheme: %s", base.Scheme)
	}

	trimmedEndpoint := strings.TrimSpace(endpoint)
	if trimmedEndpoint == "" {
		trimmedEndpoint = "/"
	}
	if !strings.HasPrefix(trimmedEndpoint, "/") {
		trimmedEndpoint = "/" + trimmedEndpoint
	}

	base.Path = strings.TrimRight(base.Path, "/") + trimmedEndpoint
	base.RawQuery = ""

	return base.String(), nil
}

// WithHTTPClient returns a new BotAPIClient that uses the provided http.Client.
// Primarily intended for testing and custom transport configuration.
func (c *BotAPIClient) WithHTTPClient(httpClient *http.Client) *BotAPIClient {
	return &BotAPIClient{
		baseURL:       c.baseURL,
		fallbackURLs:  c.fallbackURLs,
		token:         c.token,
		fallbackToken: c.fallbackToken,
		traceID:       c.traceID,
		requestCtx:    c.requestCtx,
		httpClient:    httpClient,
	}
}

// WithToken returns a new client instance that shares transport settings
// but uses a request-scoped token. This avoids mutating shared client state
// across concurrent requests.
func (c *BotAPIClient) WithToken(token string) *BotAPIClient {
	token = strings.TrimSpace(token)
	if strings.HasPrefix(strings.ToLower(token), "bearer ") {
		token = strings.TrimSpace(token[7:])
	}
	if token == "" {
		token = strings.TrimSpace(c.token)
	}

	return &BotAPIClient{
		baseURL:       c.baseURL,
		fallbackURLs:  c.fallbackURLs,
		token:         token,
		fallbackToken: c.fallbackToken,
		traceID:       c.traceID,
		requestCtx:    c.requestCtx,
		httpClient:    c.httpClient,
	}
}

// WithTraceID returns a new client instance that carries a request-scoped
// trace ID to the upstream bot API.
func (c *BotAPIClient) WithTraceID(traceID string) *BotAPIClient {
	return &BotAPIClient{
		baseURL:       c.baseURL,
		fallbackURLs:  c.fallbackURLs,
		token:         c.token,
		fallbackToken: c.fallbackToken,
		traceID:       strings.TrimSpace(traceID),
		requestCtx:    c.requestCtx,
		httpClient:    c.httpClient,
	}
}

// WithRequestContext returns a new client instance that cancels upstream bot API
// requests when the owning HTTP request is cancelled.
func (c *BotAPIClient) WithRequestContext(ctx context.Context) *BotAPIClient {
	if ctx == nil {
		ctx = context.Background()
	}
	return &BotAPIClient{
		baseURL:       c.baseURL,
		fallbackURLs:  c.fallbackURLs,
		token:         c.token,
		fallbackToken: c.fallbackToken,
		traceID:       c.traceID,
		requestCtx:    ctx,
		httpClient:    c.httpClient,
	}
}

// makeRequest makes an HTTP request to the bot API
func (c *BotAPIClient) makeRequest(method, endpoint string, body interface{}) (map[string]interface{}, error) {
	requestURL := fmt.Sprintf("%s%s", c.baseURL, endpoint)

	var requestBytes []byte
	if body != nil {
		bodyBytes, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal request body: %w", err)
		}
		requestBytes = bodyBytes
	}

	result, statusCode, respBytes, err := c.doRequest(method, requestURL, requestBytes, c.token)
	if err != nil {
		if fallbackResult, fallbackStatus, fallbackResp, fallbackErr := c.tryFallbackRequest(method, endpoint, requestBytes, c.token, err); fallbackErr == nil {
			return fallbackResult, nil
		} else if fallbackStatus == http.StatusUnauthorized && c.shouldRetryWithFallback(c.token) {
			fallbackToken := c.effectiveFallbackToken()
			if retryResult, retryStatus, retryResp, retryErr := c.tryFallbackRequest(method, endpoint, requestBytes, fallbackToken, fallbackErr); retryErr == nil {
				return retryResult, nil
			} else if retryStatus >= 400 && retryStatus < 600 {
				_ = retryResp
				return nil, parseBotAPIError(retryStatus, retryResp)
			}
		} else if fallbackStatus >= 400 && fallbackStatus < 600 {
			_ = fallbackResp
			return nil, parseBotAPIError(fallbackStatus, fallbackResp)
		}
		return nil, err
	}

	if statusCode == http.StatusUnauthorized && c.shouldRetryWithFallback(c.token) {
		fallbackToken := c.effectiveFallbackToken()
		log.Printf("⚠️  Bot API auth rejected request token; retrying with configured service token: %s %s", method, requestURL)
		result, statusCode, respBytes, err = c.doRequest(method, requestURL, requestBytes, fallbackToken)
		if err != nil {
			return nil, err
		}
	}

	if statusCode >= 400 {
		return nil, parseBotAPIError(statusCode, respBytes)
	}

	return result, nil
}

func (c *BotAPIClient) tryFallbackRequest(method, endpoint string, requestBytes []byte, token string, primaryErr error) (map[string]interface{}, int, []byte, error) {
	if len(c.fallbackURLs) == 0 {
		return nil, 0, nil, primaryErr
	}

	var transportErr *BotAPITransportError
	if !errors.As(primaryErr, &transportErr) {
		return nil, 0, nil, primaryErr
	}

	for _, fallbackBase := range c.fallbackURLs {
		fallbackURL := fmt.Sprintf("%s%s", strings.TrimRight(strings.TrimSpace(fallbackBase), "/"), endpoint)
		result, statusCode, respBytes, err := c.doRequest(method, fallbackURL, requestBytes, token)
		if err == nil {
			log.Printf("⚠️  Bot API primary upstream unavailable (%s); request succeeded via fallback upstream: %s", c.baseURL, fallbackBase)
			return result, statusCode, respBytes, nil
		}
	}

	return nil, 0, nil, primaryErr
}

func (c *BotAPIClient) shouldRetryWithFallback(currentToken string) bool {
	currentToken = strings.TrimSpace(currentToken)
	fallbackToken := c.effectiveFallbackToken()
	if fallbackToken == "" {
		return false
	}
	if !UseConfiguredBotAPIServiceToken() {
		return false
	}
	return !strings.EqualFold(currentToken, fallbackToken)
}

func (c *BotAPIClient) doRequest(method, requestURL string, requestBytes []byte, token string) (map[string]interface{}, int, []byte, error) {
	startedAt := time.Now()
	var requestBody io.Reader
	if len(requestBytes) > 0 {
		requestBody = bytes.NewReader(requestBytes)
	}

	// Build a per-request context whose deadline mirrors the http.Client timeout.
	// This lets classifyTransportError detect context.DeadlineExceeded cleanly for
	// 504 classification while the client-level timeout remains a safety net.
	timeout := c.httpClient.Timeout
	if timeout <= 0 {
		timeout = defaultBotAPIRequestTimeout
	}
	parentCtx := c.requestCtx
	if parentCtx == nil {
		parentCtx = context.Background()
	}
	ctx, cancel := context.WithTimeout(parentCtx, timeout)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, method, requestURL, requestBody)
	if err != nil {
		return nil, 0, nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	if strings.TrimSpace(token) != "" {
		req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", strings.TrimSpace(token)))
	}
	if c.traceID != "" {
		req.Header.Set("X-Trace-Id", c.traceID)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		transportErr := classifyTransportError(method, requestURL, err)
		recordBotAPIRequest(transportErr.StatusCode, time.Since(startedAt), transportErr)
		log.Printf("⚠️  Bot API transport error trace_id=%s: %s %s → HTTP %d (%s) | cause: %v",
			strings.TrimSpace(c.traceID), method, requestURL, transportErr.StatusCode, transportErr.Message, err)
		return nil, 0, nil, transportErr
	}
	defer func() { _ = resp.Body.Close() }()

	respBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		recordBotAPIRequest(resp.StatusCode, time.Since(startedAt), err)
		return nil, 0, nil, fmt.Errorf("failed to read response body: %w", err)
	}
	recordBotAPIRequest(resp.StatusCode, time.Since(startedAt), nil)

	var result map[string]interface{}
	if len(respBytes) == 0 {
		return map[string]interface{}{}, resp.StatusCode, respBytes, nil
	}
	if resp.StatusCode < 400 {
		if err := json.Unmarshal(respBytes, &result); err != nil {
			return nil, 0, nil, fmt.Errorf("failed to unmarshal response: %w", err)
		}
	}

	return result, resp.StatusCode, respBytes, nil
}

func parseBotAPIError(statusCode int, respBytes []byte) error {
	errorMsg := "Unknown error"

	var result map[string]interface{}
	if len(respBytes) > 0 && json.Unmarshal(respBytes, &result) == nil {
		if errField, ok := result["message"]; ok {
			errorMsg = fmt.Sprintf("%v", errField)
		} else if errField, ok := result["error"]; ok {
			errorMsg = fmt.Sprintf("%v", errField)
		} else if errField, ok := result["detail"]; ok {
			errorMsg = fmt.Sprintf("%v", errField)
		}
	} else if trimmed := strings.TrimSpace(string(respBytes)); trimmed != "" {
		errorMsg = trimmed
	}

	return &BotAPIError{StatusCode: statusCode, Message: errorMsg}
}

// CreateBotInstance creates a new bot instance via the bot API
func (c *BotAPIClient) CreateBotInstance(config map[string]interface{}) (map[string]interface{}, error) {
	return c.makeRequest("POST", "/api/v1/bots", config)
}

// ListBotInstances lists all bot instances
func (c *BotAPIClient) ListBotInstances() (map[string]interface{}, error) {
	return c.makeRequest("GET", "/api/v1/bots", nil)
}

// GetBotInstance gets a specific bot instance
func (c *BotAPIClient) GetBotInstance(instanceID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s", instanceID)
	return c.makeRequest("GET", endpoint, nil)
}

// StartBotInstance starts a bot instance
func (c *BotAPIClient) StartBotInstance(instanceID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/start", instanceID)
	return c.makeRequest("POST", endpoint, nil)
}

// StopBotInstance stops a bot instance
func (c *BotAPIClient) StopBotInstance(instanceID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/stop", instanceID)
	return c.makeRequest("POST", endpoint, nil)
}

// RestartBotInstance restarts a bot instance
func (c *BotAPIClient) RestartBotInstance(instanceID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/restart", instanceID)
	return c.makeRequest("POST", endpoint, nil)
}

// DeleteBotInstance deletes a bot instance
func (c *BotAPIClient) DeleteBotInstance(instanceID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s", instanceID)
	return c.makeRequest("DELETE", endpoint, nil)
}

// GetBotInstanceTrades gets trades for a bot instance using the upstream status and pagination filter contract.
func (c *BotAPIClient) GetBotInstanceTrades(instanceID string, status *string, limit *int, offset *int) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/trades", instanceID)

	params := url.Values{}
	if status != nil && strings.TrimSpace(*status) != "" {
		params.Set("status", strings.TrimSpace(*status))
	}
	if limit != nil && *limit > 0 {
		params.Set("limit", strconv.Itoa(*limit))
	}
	if offset != nil && *offset >= 0 {
		params.Set("offset", strconv.Itoa(*offset))
	}
	if encoded := params.Encode(); encoded != "" {
		endpoint += "?" + encoded
	}

	return c.makeRequest("GET", endpoint, nil)
}

// GetBotInstanceStats gets statistics for a bot instance
func (c *BotAPIClient) GetBotInstanceStats(instanceID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/stats", instanceID)
	return c.makeRequest("GET", endpoint, nil)
}

// ListCeleryTasks returns admin Celery task monitoring data from the bot API.
func (c *BotAPIClient) ListCeleryTasks(rawQuery string) (map[string]interface{}, error) {
	endpoint := "/api/v1/celery/tasks"
	if strings.TrimSpace(rawQuery) != "" {
		endpoint += "?" + strings.TrimSpace(rawQuery)
	}
	return c.makeRequest("GET", endpoint, nil)
}

// GetCeleryTask returns a single Celery task detail from the bot API.
func (c *BotAPIClient) GetCeleryTask(taskID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/celery/tasks/%s", url.PathEscape(taskID))
	return c.makeRequest("GET", endpoint, nil)
}

// RevokeCeleryTask revokes a Celery task through the bot API.
func (c *BotAPIClient) RevokeCeleryTask(taskID string, terminate bool) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/celery/tasks/%s/revoke", url.PathEscape(taskID))
	return c.makeRequest("POST", endpoint, map[string]interface{}{"terminate": terminate})
}

// RetryCeleryTask retries a supported failed Celery task through the bot API.
func (c *BotAPIClient) RetryCeleryTask(taskID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/celery/tasks/%s/retry", url.PathEscape(taskID))
	return c.makeRequest("POST", endpoint, nil)
}

// ListCeleryWorkers returns Celery worker inspection data from the bot API.
func (c *BotAPIClient) ListCeleryWorkers() (map[string]interface{}, error) {
	return c.makeRequest("GET", "/api/v1/celery/workers", nil)
}

// ListCeleryQueues returns Celery queue overview data from the bot API.
func (c *BotAPIClient) ListCeleryQueues() (map[string]interface{}, error) {
	return c.makeRequest("GET", "/api/v1/celery/queues", nil)
}

// GetCeleryHealth returns Celery broker/backend/worker health from the bot API.
func (c *BotAPIClient) GetCeleryHealth() (map[string]interface{}, error) {
	return c.makeRequest("GET", "/api/v1/celery/health", nil)
}

// CreateBacktest creates a new backtest via the bot API
func (c *BotAPIClient) CreateBacktest(config map[string]interface{}) (map[string]interface{}, error) {
	return c.makeRequest("POST", "/api/v1/backtests", config)
}

// CreateBacktestRun creates a new backtest via the compatibility /run upstream path.
func (c *BotAPIClient) CreateBacktestRun(config map[string]interface{}) (map[string]interface{}, error) {
	return c.makeRequest("POST", "/api/v1/backtests/run", config)
}

// GetStrategy fetches a strategy from the bot strategy store.
func (c *BotAPIClient) GetStrategy(strategyID int) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/strategies/%d", strategyID)
	return c.makeRequest("GET", endpoint, nil)
}

// ListBacktests lists all backtests
func (c *BotAPIClient) ListBacktests(limit int, offset int, status string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests?limit=%d&offset=%d", limit, offset)
	if status != "" {
		endpoint += fmt.Sprintf("&status=%s", status)
	}
	return c.makeRequest("GET", endpoint, nil)
}

// GetBacktest gets a specific backtest
func (c *BotAPIClient) GetBacktest(runID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s", runID)
	return c.makeRequest("GET", endpoint, nil)
}

// GetBacktestStatus gets the status of a backtest
func (c *BotAPIClient) GetBacktestStatus(runID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s/status", runID)
	return c.makeRequest("GET", endpoint, nil)
}

// GetBacktestTrades gets trades for a specific backtest
func (c *BotAPIClient) GetBacktestTrades(runID string, limit int, offset int) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s/trades?limit=%d&offset=%d", runID, limit, offset)
	return c.makeRequest("GET", endpoint, nil)
}

// CancelBacktest cancels a running backtest
func (c *BotAPIClient) CancelBacktest(runID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s/cancel", runID)
	return c.makeRequest("POST", endpoint, nil)
}

// PauseBacktest requests a cooperative pause for a running backtest
func (c *BotAPIClient) PauseBacktest(runID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s/pause", runID)
	return c.makeRequest("POST", endpoint, nil)
}

// ResumeBacktest resumes a paused backtest
func (c *BotAPIClient) ResumeBacktest(runID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s/resume", runID)
	return c.makeRequest("POST", endpoint, nil)
}

// RestartBacktest starts a fresh run from the same backtest request
func (c *BotAPIClient) RestartBacktest(runID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s/restart", runID)
	return c.makeRequest("POST", endpoint, nil)
}

// RetryBacktest starts a fresh run from the same backtest request
func (c *BotAPIClient) RetryBacktest(runID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s/retry", runID)
	return c.makeRequest("POST", endpoint, nil)
}

// RepairBacktestRequest reconstructs and persists a missing backtest request payload.
func (c *BotAPIClient) RepairBacktestRequest(runID string, dryRun bool) (map[string]interface{}, error) {
	query := url.Values{}
	query.Set("dry_run", strconv.FormatBool(dryRun))
	endpoint := fmt.Sprintf("/api/v1/admin/backtests/%s/repair-request?%s", runID, query.Encode())
	return c.makeRequest("POST", endpoint, nil)
}

// DeleteBacktest deletes a backtest
func (c *BotAPIClient) DeleteBacktest(runID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s", runID)
	return c.makeRequest("DELETE", endpoint, nil)
}
