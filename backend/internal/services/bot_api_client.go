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
	"strings"
	"time"
)

// BotAPIClient handles communication with the Python bot API
type BotAPIClient struct {
	baseURL    string
	token      string
	httpClient *http.Client
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

// NewBotAPIClient creates a new bot API client
func NewBotAPIClient(baseURL string, token string) *BotAPIClient {
	return &BotAPIClient{
		baseURL: baseURL,
		token:   token,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// SetToken sets the authentication token
func (c *BotAPIClient) SetToken(token string) {
	c.token = token
}

// BaseURL returns the configured upstream bot API base URL.
func (c *BotAPIClient) BaseURL() string {
	return c.baseURL
}

// AuthToken returns the configured token (if any).
func (c *BotAPIClient) AuthToken() string {
	return strings.TrimSpace(c.token)
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
		baseURL:    c.baseURL,
		token:      c.token,
		httpClient: httpClient,
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
		baseURL:    c.baseURL,
		token:      token,
		httpClient: c.httpClient,
	}
}

// makeRequest makes an HTTP request to the bot API
func (c *BotAPIClient) makeRequest(method, endpoint string, body interface{}) (map[string]interface{}, error) {
	requestURL := fmt.Sprintf("%s%s", c.baseURL, endpoint)

	var requestBody io.Reader
	if body != nil {
		bodyBytes, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal request body: %w", err)
		}
		requestBody = bytes.NewBuffer(bodyBytes)
	}

	// Build a per-request context whose deadline mirrors the http.Client timeout.
	// This lets classifyTransportError detect context.DeadlineExceeded cleanly for
	// 504 classification while the client-level timeout remains a safety net.
	timeout := c.httpClient.Timeout
	if timeout <= 0 {
		timeout = 30 * time.Second
	}
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, method, requestURL, requestBody)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	if c.token != "" {
		req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", c.token))
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		transportErr := classifyTransportError(method, requestURL, err)
		log.Printf("⚠️  Bot API transport error: %s %s → HTTP %d (%s) | cause: %v",
			method, requestURL, transportErr.StatusCode, transportErr.Message, err)
		return nil, transportErr
	}
	defer func() { _ = resp.Body.Close() }()

	respBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}

	if resp.StatusCode >= 400 {
		return nil, parseBotAPIError(resp.StatusCode, respBytes)
	}

	var result map[string]interface{}
	if len(respBytes) == 0 {
		return map[string]interface{}{}, nil
	}
	if err := json.Unmarshal(respBytes, &result); err != nil {
		return nil, fmt.Errorf("failed to unmarshal response: %w", err)
	}

	return result, nil
}

func parseBotAPIError(statusCode int, respBytes []byte) error {
	errorMsg := "Unknown error"

	var result map[string]interface{}
	if len(respBytes) > 0 && json.Unmarshal(respBytes, &result) == nil {
		if errField, ok := result["message"]; ok {
			errorMsg = fmt.Sprintf("%v", errField)
		} else if errField, ok := result["error"]; ok {
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

// GetBotInstanceTrades gets trades for a bot instance using the upstream status filter contract.
func (c *BotAPIClient) GetBotInstanceTrades(instanceID string, status *string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/trades", instanceID)
	if status != nil && strings.TrimSpace(*status) != "" {
		endpoint += fmt.Sprintf("?status=%s", strings.TrimSpace(*status))
	}
	return c.makeRequest("GET", endpoint, nil)
}

// GetBotInstanceStats gets statistics for a bot instance
func (c *BotAPIClient) GetBotInstanceStats(instanceID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/stats", instanceID)
	return c.makeRequest("GET", endpoint, nil)
}

// CreateBacktest creates a new backtest via the bot API
func (c *BotAPIClient) CreateBacktest(config map[string]interface{}) (map[string]interface{}, error) {
	return c.makeRequest("POST", "/api/v1/backtests", config)
}

// CreateBacktestRun creates a new backtest via the compatibility /run upstream path.
func (c *BotAPIClient) CreateBacktestRun(config map[string]interface{}) (map[string]interface{}, error) {
	return c.makeRequest("POST", "/api/v1/backtests/run", config)
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

// DeleteBacktest deletes a backtest
func (c *BotAPIClient) DeleteBacktest(runID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s", runID)
	return c.makeRequest("DELETE", endpoint, nil)
}
