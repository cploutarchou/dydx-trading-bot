package services

import (
	"fmt"
	"net/url"
	"strconv"
)

// ==================== AUTHENTICATION ENDPOINTS ====================

// UserLogin authenticates a user and returns access/refresh tokens
func (c *BotAPIClient) UserLogin(username, password string, totpToken *string) (map[string]interface{}, error) {
	payload := map[string]interface{}{
		"username": username,
		"password": password,
	}
	if totpToken != nil {
		payload["totp_token"] = *totpToken
	}

	return c.makeRequest("POST", "/api/v1/auth/login", payload)
}

// RefreshAccessToken refreshes the access token
func (c *BotAPIClient) RefreshAccessToken(refreshToken string) (map[string]interface{}, error) {
	payload := map[string]interface{}{
		"refresh_token": refreshToken,
	}

	return c.makeRequest("POST", "/api/v1/auth/refresh", payload)
}

// Logout logs out the current user
func (c *BotAPIClient) Logout() (map[string]interface{}, error) {
	return c.makeRequest("POST", "/api/v1/auth/logout", nil)
}

// LogoutAllSessions logs out from all sessions
func (c *BotAPIClient) LogoutAllSessions() (map[string]interface{}, error) {
	return c.makeRequest("POST", "/api/v1/auth/logout-all", nil)
}

// GetCurrentUser retrieves current authenticated user info
func (c *BotAPIClient) GetCurrentUser() (map[string]interface{}, error) {
	return c.makeRequest("GET", "/api/v1/users/me", nil)
}

// ==================== BOT INSTANCE MANAGEMENT (EXTENDED) ====================

// GetBotHistory retrieves bot event history
func (c *BotAPIClient) GetBotHistory(instanceID string, days int) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/history?days=%d", instanceID, days)
	return c.makeRequest("GET", endpoint, nil)
}

// GetBotJobs retrieves bot job history
func (c *BotAPIClient) GetBotJobs(instanceID string, days int) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/jobs?days=%d", instanceID, days)
	return c.makeRequest("GET", endpoint, nil)
}

// GetBotStats retrieves bot statistics
func (c *BotAPIClient) GetBotStats(instanceID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/stats", instanceID)
	return c.makeRequest("GET", endpoint, nil)
}

// StopBotInstanceWithForce stops a bot instance with optional force flag
func (c *BotAPIClient) StopBotInstanceWithForce(instanceID string, force bool) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/stop?force=%v", instanceID, force)
	return c.makeRequest("POST", endpoint, nil)
}

// ==================== BOT TRADES & POSITIONS ====================

// GetBotTrades retrieves bot trades with optional status filter
func (c *BotAPIClient) GetBotTrades(instanceID string, status *string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/trades", instanceID)
	if status != nil {
		endpoint += fmt.Sprintf("?status=%s", *status)
	}
	return c.makeRequest("GET", endpoint, nil)
}

// GetCurrentPositions retrieves currently open positions
func (c *BotAPIClient) GetCurrentPositions(botInstanceID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/positions/current", botInstanceID)
	return c.makeRequest("GET", endpoint, nil)
}

// GetPosition retrieves a specific position
func (c *BotAPIClient) GetPosition(botInstanceID string, positionID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/positions/%s", botInstanceID, positionID)
	return c.makeRequest("GET", endpoint, nil)
}

// GetPositionHistory retrieves historical P&L snapshots for a position
func (c *BotAPIClient) GetPositionHistory(botInstanceID string, positionID string, hours int) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/position-history/%s?hours=%d", botInstanceID, positionID, hours)
	return c.makeRequest("GET", endpoint, nil)
}

// ==================== BOT MARKET DATA & ALERTS ====================

// GetMarketData retrieves latest market data for all symbols
func (c *BotAPIClient) GetMarketData(botInstanceID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/market-data", botInstanceID)
	return c.makeRequest("GET", endpoint, nil)
}

// GetRealtimeStats retrieves real-time bot statistics
func (c *BotAPIClient) GetRealtimeStats(botInstanceID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/realtime-stats", botInstanceID)
	return c.makeRequest("GET", endpoint, nil)
}

// GetAlerts retrieves recent alerts for a bot
func (c *BotAPIClient) GetAlerts(botInstanceID string, limit int) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/%s/alerts?limit=%d", botInstanceID, limit)
	return c.makeRequest("GET", endpoint, nil)
}

// ==================== BACKTEST MANAGEMENT (EXTENDED) ====================

// ListBacktestsWithFilters lists backtest runs with filtering options
func (c *BotAPIClient) ListBacktestsWithFilters(limit, offset int, status *string, days *int) (map[string]interface{}, error) {
	query := url.Values{}
	query.Set("limit", strconv.Itoa(limit))
	query.Set("offset", strconv.Itoa(offset))

	if status != nil {
		query.Set("status", *status)
	}
	if days != nil {
		query.Set("days", strconv.Itoa(*days))
	}

	endpoint := fmt.Sprintf("/api/v1/backtests?%s", query.Encode())
	return c.makeRequest("GET", endpoint, nil)
}

// GetBacktestDetails retrieves detailed backtest results
func (c *BotAPIClient) GetBacktestDetails(runID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s", runID)
	return c.makeRequest("GET", endpoint, nil)
}

// GetBacktestTradesWithFilters GetBacktestTrades retrieves trades for a specific backtest run
func (c *BotAPIClient) GetBacktestTradesWithFilters(runID string, limit, offset int, winningOnly bool) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s/trades?limit=%d&offset=%d&winning_only=%v", runID, limit, offset, winningOnly)
	return c.makeRequest("GET", endpoint, nil)
}

// GetBacktestDetailedTrades retrieves enriched trade details for a run.
func (c *BotAPIClient) GetBacktestDetailedTrades(runID string, limit, offset int) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s/trades/detailed?limit=%d&offset=%d", runID, limit, offset)
	return c.makeRequest("GET", endpoint, nil)
}

// GetBacktestLogs retrieves textual/log events for a run.
func (c *BotAPIClient) GetBacktestLogs(runID string, limit int) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s/logs?limit=%d", runID, limit)
	return c.makeRequest("GET", endpoint, nil)
}

// GetBacktestAnalytics retrieves comprehensive analytics for a backtest
func (c *BotAPIClient) GetBacktestAnalytics(runID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s/analytics", runID)
	return c.makeRequest("GET", endpoint, nil)
}

// GetBacktestAnalyticsSummary retrieves a compact analytics summary for a backtest.
func (c *BotAPIClient) GetBacktestAnalyticsSummary(runID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s/analytics/summary", runID)
	return c.makeRequest("GET", endpoint, nil)
}

// GetPositionSnapshots retrieves position snapshots for backtest tracking
func (c *BotAPIClient) GetPositionSnapshots(runID string, limit, offset int, marketPair *string) (map[string]interface{}, error) {
	query := url.Values{}
	query.Set("limit", strconv.Itoa(limit))
	query.Set("offset", strconv.Itoa(offset))

	if marketPair != nil {
		query.Set("market_pair", *marketPair)
	}

	endpoint := fmt.Sprintf("/api/v1/backtests/%s/position-snapshots?%s", runID, query.Encode())
	return c.makeRequest("GET", endpoint, nil)
}

// CompareBacktests compares multiple backtest runs
func (c *BotAPIClient) CompareBacktests(config map[string]interface{}) (map[string]interface{}, error) {
	return c.makeRequest("POST", "/api/v1/backtests/compare", config)
}

// GetBacktestSummaryStats retrieves backtest summary statistics
func (c *BotAPIClient) GetBacktestSummaryStats(days int) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/stats/summary?days=%d", days)
	return c.makeRequest("GET", endpoint, nil)
}

// ValidateAgainstdYdXData validates backtest results against real dYdX market data
func (c *BotAPIClient) ValidateAgainstdYdXData(runID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s/dydx-validation", runID)
	return c.makeRequest("GET", endpoint, nil)
}

// GetAdvancedPerformanceMetrics retrieves advanced performance metrics
func (c *BotAPIClient) GetAdvancedPerformanceMetrics(runID string, benchmark string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s/performance-metrics?benchmark=%s", runID, benchmark)
	return c.makeRequest("GET", endpoint, nil)
}

// GetLiveProgress retrieves real-time backtest progress
func (c *BotAPIClient) GetLiveProgress(runID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/backtests/%s/live-progress", runID)
	return c.makeRequest("GET", endpoint, nil)
}

// QuickDeployBot quickly deploys and optionally starts a new bot instance
func (c *BotAPIClient) QuickDeployBot(instanceName string, autoStart bool, config map[string]interface{}) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/bots/quick-deploy?instance_name=%s&auto_start=%v", instanceName, autoStart)
	return c.makeRequest("POST", endpoint, config)
}

// HealthCheck performs a health check
func (c *BotAPIClient) HealthCheck() (map[string]interface{}, error) {
	return c.makeRequest("GET", "/health", nil)
}

// GetCapabilities retrieves the upstream bot control-plane capability map.
func (c *BotAPIClient) GetCapabilities() (map[string]interface{}, error) {
	return c.makeRequest("GET", "/api/v1/capabilities", nil)
}

// GetRuntimeDBConfig retrieves sanitized runtime DB diagnostics from the bot API.
func (c *BotAPIClient) GetRuntimeDBConfig() (map[string]interface{}, error) {
	return c.makeRequest("GET", "/api/v1/runtime/db-config", nil)
}

// GetPerpetualMarkets retrieves the available dYdX perpetual market symbols.
func (c *BotAPIClient) GetPerpetualMarkets(limit int) (map[string]interface{}, error) {
	query := url.Values{}
	if limit > 0 {
		query.Set("limit", strconv.Itoa(limit))
	}

	endpoint := "/api/v1/markets/perpetuals"
	if encoded := query.Encode(); encoded != "" {
		endpoint += "?" + encoded
	}
	return c.makeRequest("GET", endpoint, nil)
}

// GetArbitrageImprovementMetrics retrieves bot-side arbitrage efficiency counters.
func (c *BotAPIClient) GetArbitrageImprovementMetrics() (map[string]interface{}, error) {
	return c.makeRequest("GET", "/api/v1/arbitrage/improvement-metrics", nil)
}

// GetArbitragePairPriority retrieves the optional pair-priority ranking diagnostics.
func (c *BotAPIClient) GetArbitragePairPriority(limit int) (map[string]interface{}, error) {
	query := url.Values{}
	if limit > 0 {
		query.Set("limit", strconv.Itoa(limit))
	}

	endpoint := "/api/v1/arbitrage/pair-priority"
	if encoded := query.Encode(); encoded != "" {
		endpoint += "?" + encoded
	}
	return c.makeRequest("GET", endpoint, nil)
}

// GetArbitrageOpportunityExplain retrieves additive explainability diagnostics for an opportunity id.
func (c *BotAPIClient) GetArbitrageOpportunityExplain(opportunityID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("/api/v1/arbitrage/opportunity/%s/explain", url.PathEscape(opportunityID))
	return c.makeRequest("GET", endpoint, nil)
}

// GetArbitrageRuntimeSettings retrieves bot-side runtime arbitrage settings.
func (c *BotAPIClient) GetArbitrageRuntimeSettings() (map[string]interface{}, error) {
	return c.makeRequest("GET", "/api/v1/arbitrage/runtime-settings", nil)
}

// UpdateArbitrageRuntimeSettings pushes runtime arbitrage settings to the bot process.
func (c *BotAPIClient) UpdateArbitrageRuntimeSettings(settings map[string]interface{}) (map[string]interface{}, error) {
	return c.makeRequest("PUT", "/api/v1/arbitrage/runtime-settings", settings)
}

// GetRuntimePreflight evaluates whether a runtime can safely start on the upstream bot service.
func (c *BotAPIClient) GetRuntimePreflight(config map[string]interface{}) (map[string]interface{}, error) {
	return c.makeRequest("POST", "/api/v1/runtime/preflight", config)
}

// GetInterruptedBacktests retrieves interrupted/orphaned backtest visibility data.
func (c *BotAPIClient) GetInterruptedBacktests(limit int, admin bool) (map[string]interface{}, error) {
	query := url.Values{}
	if limit > 0 {
		query.Set("limit", strconv.Itoa(limit))
	}

	basePath := "/api/v1/backtests/interrupted"
	if admin {
		basePath = "/api/v1/admin/backtests/interrupted"
	}
	if encoded := query.Encode(); encoded != "" {
		basePath += "?" + encoded
	}

	return c.makeRequest("GET", basePath, nil)
}

// ReconcileInterruptedBacktests triggers interrupted/orphaned run reconciliation.
func (c *BotAPIClient) ReconcileInterruptedBacktests(dryRun bool, admin bool) (map[string]interface{}, error) {
	query := url.Values{}
	query.Set("dry_run", strconv.FormatBool(dryRun))

	basePath := "/api/v1/backtests/interrupted/reconcile"
	if admin {
		basePath = "/api/v1/admin/backtests/interrupted/reconcile"
	}
	basePath += "?" + query.Encode()

	return c.makeRequest("POST", basePath, nil)
}

// SystemStatus retrieves system status and statistics
func (c *BotAPIClient) SystemStatus() (map[string]interface{}, error) {
	return c.makeRequest("GET", "/api/v1/system/status", nil)
}
