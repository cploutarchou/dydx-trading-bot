package services

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// BotAPIClient handles communication with the Python bot API
type BotAPIClient struct {
	baseURL    string
	token      string
	httpClient *http.Client
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

// makeRequest makes an HTTP request to the bot API
func (c *BotAPIClient) makeRequest(method, endpoint string, body interface{}) (map[string]interface{}, error) {
	url := fmt.Sprintf("%s%s", c.baseURL, endpoint)

	var requestBody io.Reader
	if body != nil {
		bodyBytes, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal request body: %w", err)
		}
		requestBody = bytes.NewBuffer(bodyBytes)
	}

	req, err := http.NewRequest(method, url, requestBody)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	if c.token != "" {
		req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", c.token))
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()

	respBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}

	var result map[string]interface{}
	if err := json.Unmarshal(respBytes, &result); err != nil {
		return nil, fmt.Errorf("failed to unmarshal response: %w", err)
	}

	if resp.StatusCode >= 400 {
		errorMsg := "Unknown error"
		if errField, ok := result["message"]; ok {
			errorMsg = fmt.Sprintf("%v", errField)
		} else if errField, ok := result["error"]; ok {
			errorMsg = fmt.Sprintf("%v", errField)
		}
		return nil, fmt.Errorf("API error (status %d): %s", resp.StatusCode, errorMsg)
	}

	return result, nil
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

// GetBotInstanceHistory gets the history for a bot instance
func (c *BotAPIClient) GetBotInstanceHistory(instanceID string, limit int, offset int) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/history?limit=%d&offset=%d", instanceID, limit, offset)
	return c.makeRequest("GET", endpoint, nil)
}

// GetBotInstanceTrades gets trades for a bot instance
func (c *BotAPIClient) GetBotInstanceTrades(instanceID string, limit int, offset int, winningOnly bool) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/trades?limit=%d&offset=%d&winning_only=%v", instanceID, limit, offset, winningOnly)
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
