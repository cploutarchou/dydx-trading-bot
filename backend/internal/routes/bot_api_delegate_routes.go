package routes

import (
	"errors"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
)

var websocketUpgrader = websocket.Upgrader{
	CheckOrigin: func(_ *http.Request) bool {
		// CORS/auth middleware already guards access; keep origin check permissive here.
		return true
	},
}

func extractBotAuthToken(c *gin.Context) string {
	return middleware.ExtractRequestAccessToken(c)
}

func getRequestBotAPIClient(c *gin.Context, fallback *services.BotAPIClient) *services.BotAPIClient {
	clientValue, exists := c.Get("bot_api_client")
	if exists {
		if client, ok := clientValue.(*services.BotAPIClient); ok && client != nil {
			return client
		}
	}
	return fallback
}

func respondBotAPIError(c *gin.Context, err error) {
	traceID := middleware.GetTraceID(c)
	// Transport-level failures (connection refused, timeout) carry a pre-classified
	// status code so callers receive a clean 502/504 without raw Go error messages.
	var transportErr *services.BotAPITransportError
	if errors.As(err, &transportErr) {
		status := transportErr.StatusCode
		if status <= 0 {
			status = http.StatusBadGateway
		}
		c.JSON(status, gin.H{"error": transportErr.Message, "message": transportErr.Message, "trace_id": traceID})
		return
	}
	var apiErr *services.BotAPIError
	if errors.As(err, &apiErr) {
		status := apiErr.StatusCode
		if status <= 0 {
			status = http.StatusBadGateway
		}
		message := strings.TrimSpace(apiErr.Message)
		if message == "" {
			message = "upstream bot API request failed"
		}
		c.JSON(status, gin.H{"error": message, "message": message, "trace_id": traceID})
		return
	}
	c.JSON(http.StatusBadGateway, gin.H{"error": err.Error(), "message": err.Error(), "trace_id": traceID})
}

func delegateJSON(c *gin.Context, fallback *services.BotAPIClient, call func(*services.BotAPIClient) (map[string]interface{}, error)) {
	requestClient := getRequestBotAPIClient(c, fallback)
	result, err := call(requestClient)
	if err != nil {
		respondBotAPIError(c, err)
		return
	}
	c.JSON(http.StatusOK, result)
}

func normalizeBacktestRunPayload(config map[string]interface{}) map[string]interface{} {
	if config == nil {
		return nil
	}

	normalized := make(map[string]interface{}, len(config)+1)
	for k, v := range config {
		normalized[k] = v
	}

	tradingParameters, _ := normalized["trading_parameters"].(map[string]interface{})
	if tradingParameters == nil {
		tradingParameters = map[string]interface{}{}
	}

	legacyTradingParameterFields := []string{
		"zscore_threshold",
		"stats_window",
		"max_half_life",
		"usd_per_trade",
		"usd_min_collateral",
		"close_at_zscore_cross",
		"find_cointegrated_pairs",
		"manage_exits",
		"place_trades",
		"abort_all_positions",
		"max_positions",
		"max_drawdown_pct",
		"stop_loss_pct",
		"take_profit_pct",
		"trailing_stop_pct",
		"rebalance_interval_hours",
		"position_timeout_hours",
		"transaction_fee",
		"slippage",
		"risk_free_rate",
		"resolution",
		"candle_resolution",
	}

	for _, field := range legacyTradingParameterFields {
		if _, exists := tradingParameters[field]; exists {
			continue
		}
		if value, exists := normalized[field]; exists {
			tradingParameters[field] = value
			delete(normalized, field)
		}
	}

	if value, exists := normalized["num_pairs"]; exists {
		if _, hasMaxPairs := normalized["max_pairs"]; !hasMaxPairs {
			normalized["max_pairs"] = value
		}
		delete(normalized, "num_pairs")
	}

	if value, exists := normalized["pair_selection_mode"]; exists {
		if _, ok := tradingParameters["pair_selection_mode"]; !ok {
			tradingParameters["pair_selection_mode"] = value
		}
	}

	if value, exists := normalized["max_pairs"]; exists {
		if _, ok := tradingParameters["max_pairs"]; !ok {
			tradingParameters["max_pairs"] = value
		}
	}

	if len(tradingParameters) > 0 {
		normalized["trading_parameters"] = tradingParameters
	}

	return normalized
}

func asMap(value interface{}) map[string]interface{} {
	if mapped, ok := value.(map[string]interface{}); ok {
		return mapped
	}
	return nil
}

func asSlice(value interface{}) []interface{} {
	if items, ok := value.([]interface{}); ok {
		return items
	}
	return nil
}

func getNumberField(payload map[string]interface{}, keys ...string) (float64, bool) {
	for _, key := range keys {
		v, ok := payload[key]
		if !ok || v == nil {
			continue
		}
		switch typed := v.(type) {
		case float64:
			return typed, true
		case float32:
			return float64(typed), true
		case int:
			return float64(typed), true
		case int32:
			return float64(typed), true
		case int64:
			return float64(typed), true
		}
	}
	return 0, false
}

func unwrapEnvelopePayload(payload map[string]interface{}) map[string]interface{} {
	if payload == nil {
		return map[string]interface{}{}
	}
	if data := asMap(payload["data"]); data != nil {
		return data
	}
	return payload
}

func getEnvelopeMessage(payload map[string]interface{}, fallback string) string {
	if payload != nil {
		if message, ok := payload["message"].(string); ok && strings.TrimSpace(message) != "" {
			return message
		}
	}
	return fallback
}

func respondBacktestEnvelope(c *gin.Context, statusCode int, fallbackMessage string, payload map[string]interface{}) {
	data := unwrapEnvelopePayload(payload)
	message := getEnvelopeMessage(payload, fallbackMessage)
	response := gin.H{
		"success":   statusCode >= 200 && statusCode < 300,
		"message":   message,
		"data":      data,
		"timestamp": time.Now().UTC().Format(time.RFC3339),
		"trace_id":  middleware.GetTraceID(c),
	}
	for key, value := range data {
		switch key {
		case "success", "message", "data", "timestamp":
			continue
		default:
			response[key] = value
		}
	}
	c.JSON(statusCode, response)
}

func normalizeBacktestDetailsFields(payload map[string]interface{}) map[string]interface{} {
	if payload == nil {
		payload = map[string]interface{}{}
	}
	if _, ok := payload["status"]; !ok {
		payload["status"] = "unknown"
	}
	if _, ok := payload["error_message"]; !ok {
		if errorMessage := getStringField(payload, "error"); errorMessage != "" {
			payload["error_message"] = errorMessage
		}
	}
	if _, ok := payload["error"]; !ok {
		if errorMessage := getStringField(payload, "error_message"); errorMessage != "" {
			payload["error"] = errorMessage
		}
	}

	progress := 0.0
	if value, ok := getNumberField(payload, "progress_percent", "progress_pct", "progress"); ok {
		progress = value
	}
	payload["progress_percent"] = progress
	payload["progress_pct"] = progress
	payload["progress"] = progress

	for _, key := range []string{"total_pnl", "win_rate", "sharpe_ratio", "max_drawdown_pct", "total_trades"} {
		if _, ok := payload[key]; !ok {
			payload[key] = nil
		}
	}
	if winRate, ok := getNumberField(payload, "win_rate"); ok && winRate >= 0 && winRate <= 1 {
		payload["win_rate"] = winRate * 100.0
	}
	if payload["max_drawdown_pct"] == nil {
		if drawdown, ok := getNumberField(payload, "max_drawdown"); ok {
			payload["max_drawdown_pct"] = drawdown
		}
	}
	if _, ok := payload["max_drawdown"]; !ok {
		if drawdown, ok := getNumberField(payload, "max_drawdown_pct"); ok {
			payload["max_drawdown"] = drawdown
		}
	}

	return payload
}

func normalizeBacktestDetailsPayload(payload map[string]interface{}) map[string]interface{} {
	if payload == nil {
		payload = map[string]interface{}{}
	}
	if data := asMap(payload["data"]); data != nil {
		payload["data"] = normalizeBacktestDetailsFields(data)
		return payload
	}
	return normalizeBacktestDetailsFields(payload)
}

func normalizeBacktestStatusFields(payload map[string]interface{}) map[string]interface{} {
	if payload == nil {
		payload = map[string]interface{}{}
	}
	status := strings.ToLower(strings.TrimSpace(fmt.Sprintf("%v", payload["status"])))
	if _, ok := payload["error_message"]; !ok {
		if errorMessage := getStringField(payload, "error"); errorMessage != "" {
			payload["error_message"] = errorMessage
		}
	}
	if _, ok := payload["error"]; !ok {
		if errorMessage := getStringField(payload, "error_message"); errorMessage != "" {
			payload["error"] = errorMessage
		}
	}
	progress := 0.0
	if value, ok := getNumberField(payload, "progress_pct", "progress_percent", "progress"); ok {
		progress = value
	}
	if status == "pending" || status == "queued" {
		progress = 0.0
		payload["current_task"] = nil
	}
	payload["progress_percent"] = progress
	payload["progress_pct"] = progress
	payload["progress"] = progress
	if _, ok := payload["current_task"]; !ok {
		payload["current_task"] = nil
	}
	if _, ok := payload["current_pair"]; !ok {
		payload["current_pair"] = nil
	}
	return payload
}

func normalizeBacktestStatusPayload(payload map[string]interface{}) map[string]interface{} {
	if payload == nil {
		payload = map[string]interface{}{}
	}
	if data := asMap(payload["data"]); data != nil {
		payload["data"] = normalizeBacktestStatusFields(data)
		return payload
	}
	return normalizeBacktestStatusFields(payload)
}

func normalizedPercentValue(value float64) float64 {
	if value >= 0 && value <= 1 {
		return value * 100.0
	}
	return value
}

func getStringField(payload map[string]interface{}, keys ...string) string {
	for _, key := range keys {
		if payload == nil {
			continue
		}
		value, ok := payload[key]
		if !ok || value == nil {
			continue
		}
		switch typed := value.(type) {
		case string:
			if strings.TrimSpace(typed) != "" {
				return strings.TrimSpace(typed)
			}
		default:
			text := strings.TrimSpace(fmt.Sprintf("%v", typed))
			if text != "" && text != "<nil>" {
				return text
			}
		}
	}
	return ""
}

func extractBacktestTrades(payload map[string]interface{}) []interface{} {
	data := unwrapEnvelopePayload(payload)
	for _, key := range []string{"trades", "all_trades"} {
		if trades := asSlice(data[key]); trades != nil {
			return trades
		}
	}
	return nil
}

func resolveBacktestTradeLimit(details map[string]interface{}) int {
	limit := 500
	if totalTrades, ok := getNumberField(details, "total_trades"); ok && int(totalTrades) > 0 {
		limit = int(totalTrades)
	}
	if limit > 5000 {
		limit = 5000
	}
	return limit
}

func parseBacktestTime(value interface{}) (time.Time, bool) {
	text := strings.TrimSpace(fmt.Sprintf("%v", value))
	if text == "" || text == "<nil>" {
		return time.Time{}, false
	}

	for _, layout := range []string{
		time.RFC3339Nano,
		time.RFC3339,
		"2006-01-02 15:04:05",
		"2006-01-02",
	} {
		if parsed, err := time.Parse(layout, text); err == nil {
			return parsed, true
		}
	}

	return time.Time{}, false
}

func inferBacktestPairCount(details map[string]interface{}) int {
	if pairs, ok := getNumberField(details, "num_pairs", "max_pairs"); ok {
		return int(pairs)
	}

	requestPayload := asMap(details["request"])
	if requestPayload == nil {
		return 0
	}

	if pairs, ok := getNumberField(requestPayload, "num_pairs", "max_pairs"); ok {
		return int(pairs)
	}

	if params := asMap(requestPayload["trading_parameters"]); params != nil {
		if pairs, ok := getNumberField(params, "num_pairs", "max_pairs"); ok {
			return int(pairs)
		}
	}

	markets := asSlice(requestPayload["pairs"])
	if len(markets) < 2 {
		return len(markets)
	}
	return len(markets) * (len(markets) - 1) / 2
}

func buildBacktestSummaryPayload(detailsPayload map[string]interface{}, tradesPayload map[string]interface{}, runID string) map[string]interface{} {
	details := unwrapEnvelopePayload(normalizeBacktestDetailsPayload(detailsPayload))
	requestPayload := asMap(details["request"])
	params := asMap(nil)
	if requestPayload != nil {
		params = asMap(requestPayload["trading_parameters"])
	}

	earliestTradeDate := ""
	latestTradeDate := ""
	for _, trade := range extractBacktestTrades(tradesPayload) {
		tradeMap := asMap(trade)
		if tradeMap == nil {
			continue
		}

		entryTime, entryOK := parseBacktestTime(tradeMap["entry_timestamp"])
		if entryOK && (earliestTradeDate == "" || entryTime.Format(time.RFC3339) < earliestTradeDate) {
			earliestTradeDate = entryTime.Format(time.RFC3339)
		}

		exitValue := tradeMap["exit_timestamp"]
		if exitValue == nil || strings.TrimSpace(fmt.Sprintf("%v", exitValue)) == "" {
			exitValue = tradeMap["entry_timestamp"]
		}
		exitTime, exitOK := parseBacktestTime(exitValue)
		if exitOK && (latestTradeDate == "" || exitTime.Format(time.RFC3339) > latestTradeDate) {
			latestTradeDate = exitTime.Format(time.RFC3339)
		}
	}

	if earliestTradeDate == "" {
		earliestTradeDate = getStringField(details, "start_date")
	}
	if latestTradeDate == "" {
		latestTradeDate = getStringField(details, "end_date")
	}

	status := getStringField(details, "status")
	createdAt := getStringField(details, "created_at")
	startedAt := getStringField(details, "started_at")
	if startedAt == "" {
		startedAt = createdAt
	}
	completedAt := getStringField(details, "completed_at")
	if completedAt == "" && (status == "completed" || status == "failed" || status == "cancelled") {
		completedAt = getStringField(details, "updated_at")
	}

	zscoreThreshold, _ := getNumberField(params, "zscore_threshold")
	statsWindow, _ := getNumberField(params, "stats_window")
	usdPerTrade, _ := getNumberField(params, "usd_per_trade")
	totalTrades, _ := getNumberField(details, "total_trades")

	return map[string]interface{}{
		"run_id":             getStringField(details, "run_id"),
		"status":             status,
		"created_at":         createdAt,
		"started_at":         startedAt,
		"completed_at":       completedAt,
		"total_trades":       int(totalTrades),
		"earliest_trade_date": earliestTradeDate,
		"latest_trade_date":   latestTradeDate,
		"configuration": map[string]interface{}{
			"num_pairs":         inferBacktestPairCount(details),
			"zscore_threshold":  zscoreThreshold,
			"stats_window":      int(statsWindow),
			"usd_per_trade":     usdPerTrade,
		},
		"requested_run_id": runID,
	}
}

func buildBacktestPerformancePayload(detailsPayload map[string]interface{}, metricsPayload map[string]interface{}, tradesPayload map[string]interface{}, runID string) map[string]interface{} {
	details := unwrapEnvelopePayload(normalizeBacktestDetailsPayload(detailsPayload))
	metrics := unwrapEnvelopePayload(metricsPayload)

	totalTrades := 0
	if value, ok := getNumberField(details, "total_trades"); ok {
		totalTrades = int(value)
	}

	totalPnl, totalPnlSet := getNumberField(details, "total_pnl", "total_pnl_usd")
	winRate, winRateSet := getNumberField(details, "win_rate")
	if winRateSet {
		winRate = normalizedPercentValue(winRate)
	}
	sharpeRatio, sharpeSet := getNumberField(metrics, "sharpe_ratio")
	if !sharpeSet {
		sharpeRatio, _ = getNumberField(details, "sharpe_ratio")
	}
	maxDrawdown, drawdownSet := getNumberField(metrics, "max_drawdown", "max_drawdown_pct")
	if !drawdownSet {
		if risk := asMap(metrics["risk"]); risk != nil {
			maxDrawdown, drawdownSet = getNumberField(risk, "max_drawdown", "max_drawdown_pct")
		}
	}
	if !drawdownSet {
		maxDrawdown, _ = getNumberField(details, "max_drawdown", "max_drawdown_pct")
	}

	winningTrades := 0
	losingTrades := 0
	maxWin := 0.0
	maxLoss := 0.0
	totalDurationHours := 0.0
	durationCount := 0

	trades := extractBacktestTrades(tradesPayload)
	for _, trade := range trades {
		tradeMap := asMap(trade)
		if tradeMap == nil {
			continue
		}

		pnl, hasPnL := getNumberField(tradeMap, "pnl_usd", "pnl", "realized_pnl", "total_pnl_usd")
		if hasPnL {
			if pnl > 0 {
				winningTrades++
				if pnl > maxWin {
					maxWin = pnl
				}
			} else {
				losingTrades++
				if pnl < maxLoss {
					maxLoss = pnl
				}
			}
		}

		durationHours, hasDuration := getNumberField(tradeMap, "duration_hours")
		if !hasDuration {
			entryTime, entryOK := parseBacktestTime(tradeMap["entry_timestamp"])
			exitTime, exitOK := parseBacktestTime(tradeMap["exit_timestamp"])
			if entryOK && exitOK {
				durationHours = exitTime.Sub(entryTime).Hours()
				hasDuration = true
			}
		}
		if hasDuration && durationHours >= 0 {
			totalDurationHours += durationHours
			durationCount++
		}
	}

	if totalTrades == 0 {
		totalTrades = len(trades)
	}
	if totalTrades == 0 {
		totalTrades = winningTrades + losingTrades
	}

	if winningTrades+losingTrades == 0 && totalTrades > 0 && winRateSet {
		winningTrades = int((winRate / 100.0 * float64(totalTrades)) + 0.5)
		if winningTrades > totalTrades {
			winningTrades = totalTrades
		}
		losingTrades = totalTrades - winningTrades
	}
	if !winRateSet && totalTrades > 0 {
		winRate = (float64(winningTrades) / float64(totalTrades)) * 100.0
	}
	if !totalPnlSet {
		totalPnl = 0
	}

	averagePnL := 0.0
	if totalTrades > 0 {
		averagePnL = totalPnl / float64(totalTrades)
	}

	averageDuration := 0.0
	if durationCount > 0 {
		averageDuration = totalDurationHours / float64(durationCount)
	}

	return map[string]interface{}{
		"run_id":           getStringField(details, "run_id"),
		"requested_run_id": runID,
		"total_trades":     totalTrades,
		"winning_trades":   winningTrades,
		"losing_trades":    losingTrades,
		"win_rate":         winRate,
		"total_pnl":        totalPnl,
		"average_pnl":      averagePnL,
		"max_win":          maxWin,
		"max_loss":         maxLoss,
		"sharpe_ratio":     sharpeRatio,
		"max_drawdown":     maxDrawdown,
		"average_duration": averageDuration,
	}
}

func isUpstreamNotFound(err error) bool {
	var apiErr *services.BotAPIError
	return errors.As(err, &apiErr) && apiErr.StatusCode == http.StatusNotFound
}

// RegisterBotAPIDelegateRoutes registers all delegated bot API endpoints
// These routes proxy to the Python bot API (default 127.0.0.1:8889) and sync with the Go database
func RegisterBotAPIDelegateRoutes(router *gin.Engine, apiClient *services.BotAPIClient) {
	RegisterBotAPIDelegateRoutesWithSync(router, apiClient, nil)
}

// RegisterBotAPIDelegateRoutesWithSync registers delegated bot API endpoints and
// optionally persists backtest run status snapshots into local DB tables.
func RegisterBotAPIDelegateRoutesWithSync(router *gin.Engine, apiClient *services.BotAPIClient, backtestSync *services.BacktestSyncService) {
	syncRun := func(c *gin.Context, payload map[string]interface{}) {
		if backtestSync == nil {
			return
		}
		userIDValue, exists := c.Get("user_id")
		if !exists {
			return
		}
		userID, ok := userIDValue.(int)
		if !ok || userID <= 0 {
			return
		}
		if err := backtestSync.SyncBacktestRun(userID, payload); err != nil {
			log.Printf("Backtest sync warning: failed to sync delegated backtest payload: %v", err)
		}
	}

	syncRunList := func(c *gin.Context, payload map[string]interface{}) {
		if backtestSync == nil || payload == nil {
			return
		}
		root := payload
		if data, ok := payload["data"].(map[string]interface{}); ok {
			root = data
		}
		runs, ok := root["backtests"].([]interface{})
		if !ok {
			return
		}
		for _, item := range runs {
			runPayload, ok := item.(map[string]interface{})
			if !ok {
				continue
			}
			syncRun(c, runPayload)
		}
	}

	syncChildren := func(c *gin.Context, runID string, payload map[string]interface{}) {
		if backtestSync == nil || strings.TrimSpace(runID) == "" {
			return
		}
		if err := backtestSync.SyncBacktestTrades(runID, payload); err != nil {
			log.Printf("Backtest sync warning: failed syncing trades for run %s: %v", runID, err)
		}
		if err := backtestSync.SyncBacktestPositions(runID, payload); err != nil {
			log.Printf("Backtest sync warning: failed syncing positions for run %s: %v", runID, err)
		}
		if err := backtestSync.SyncBacktestCandles(runID, payload); err != nil {
			log.Printf("Backtest sync warning: failed syncing candles for run %s: %v", runID, err)
		}
	}

	proxyWebSocket := func(c *gin.Context, requestClient *services.BotAPIClient, upstreamEndpoint string) {
		clientConn, err := websocketUpgrader.Upgrade(c.Writer, c.Request, nil)
		if err != nil {
			return
		}
		defer func() { _ = clientConn.Close() }()

		upstreamWSURL, err := requestClient.WebSocketURL(upstreamEndpoint)
		if err != nil {
			_ = clientConn.WriteMessage(
				websocket.CloseMessage,
				websocket.FormatCloseMessage(websocket.CloseInternalServerErr, err.Error()),
			)
			return
		}

		requestHeaders := http.Header{}
		if token := strings.TrimSpace(requestClient.AuthToken()); token != "" {
			requestHeaders.Set("Authorization", "Bearer "+token)
		}
		if traceID := middleware.GetTraceID(c); traceID != "" {
			requestHeaders.Set(middleware.TraceIDHeader, traceID)
		}

		upstreamConn, upstreamResp, err := websocket.DefaultDialer.Dial(upstreamWSURL, requestHeaders)
		if upstreamResp != nil && upstreamResp.Body != nil {
			defer func() { _ = upstreamResp.Body.Close() }()
		}
		if err != nil {
			_ = clientConn.WriteMessage(
				websocket.CloseMessage,
				websocket.FormatCloseMessage(websocket.CloseTryAgainLater, "failed to connect upstream websocket"),
			)
			return
		}
		defer func() { _ = upstreamConn.Close() }()

		forward := func(src *websocket.Conn, dst *websocket.Conn, done chan<- struct{}) {
			defer func() { done <- struct{}{} }()
			for {
				messageType, payload, readErr := src.ReadMessage()
				if readErr != nil {
					_ = dst.WriteMessage(
						websocket.CloseMessage,
						websocket.FormatCloseMessage(websocket.CloseNormalClosure, ""),
					)
					return
				}

				if writeErr := dst.WriteMessage(messageType, payload); writeErr != nil {
					return
				}
			}
		}

		done := make(chan struct{}, 2)
		go forward(clientConn, upstreamConn, done)
		go forward(upstreamConn, clientConn, done)

		<-done
	}

	withRequestScopedBotClient := func(c *gin.Context) {
		requestClient := apiClient.WithTraceID(middleware.GetTraceID(c))

		if services.UseConfiguredBotAPIServiceToken() {
			// Service-token model: keep configured BOT_API_TOKEN and do not
			// override upstream auth with caller JWT.
			c.Set("bot_api_client", requestClient)
			c.Next()
			return
		}

		token := extractBotAuthToken(c)
		if token != "" {
			c.Set("bot_api_client", requestClient.WithToken(token))
		} else {
			c.Set("bot_api_client", requestClient)
		}
		c.Next()
	}

	createBacktestHandler := func(c *gin.Context) {
		requestClient := getRequestBotAPIClient(c, apiClient)
		var config map[string]interface{}
		if err := c.BindJSON(&config); err != nil {
			c.JSON(400, gin.H{"error": "Invalid request body"})
			return
		}
		config = normalizeBacktestRunPayload(config)

		var (
			result map[string]interface{}
			err    error
		)
		if c.FullPath() == "/api/v1/backtests/run" {
			result, err = requestClient.CreateBacktestRun(config)
		} else {
			result, err = requestClient.CreateBacktest(config)
		}
		if err != nil {
			respondBotAPIError(c, err)
			return
		}
		syncRun(c, result)
		respondBacktestEnvelope(c, http.StatusOK, "Backtest created successfully", result)
	}

	// Backtest proxy endpoints
	backtestGroup := router.Group("/api/v1/backtests")
	backtestGroup.Use(middleware.RequireAuth())
	backtestGroup.Use(withRequestScopedBotClient)
	{
		// Local DB sync-health dashboard for delegated backtests.
		backtestGroup.GET("/sync-health", func(c *gin.Context) {
			if backtestSync == nil {
				c.JSON(http.StatusServiceUnavailable, gin.H{
					"success":   false,
					"error":     "backtest sync service unavailable",
					"timestamp": time.Now().UTC().Format(time.RFC3339),
				})
				return
			}

			userIDValue, exists := c.Get("user_id")
			if !exists {
				c.JSON(http.StatusUnauthorized, gin.H{
					"success":   false,
					"error":     "unauthorized",
					"timestamp": time.Now().UTC().Format(time.RFC3339),
				})
				return
			}
			userID, ok := userIDValue.(int)
			if !ok || userID <= 0 {
				c.JSON(http.StatusUnauthorized, gin.H{
					"success":   false,
					"error":     "invalid user context",
					"timestamp": time.Now().UTC().Format(time.RFC3339),
				})
				return
			}

			runID := strings.TrimSpace(c.Query("run_id"))
			limit := 20
			if l := c.Query("limit"); l != "" {
				if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 && parsed <= 200 {
					limit = parsed
				}
			}

			health, err := backtestSync.GetSyncHealthByRun(userID, runID, limit)
			if err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{
					"success":   false,
					"error":     err.Error(),
					"timestamp": time.Now().UTC().Format(time.RFC3339),
				})
				return
			}

			respondBacktestEnvelope(c, http.StatusOK, "Backtest sync health fetched successfully", map[string]interface{}{
				"runs":  health,
				"count": len(health),
			})
		})

		// Create backtest
		backtestGroup.POST("", createBacktestHandler)
		// Frontend compatibility alias
		backtestGroup.POST("/run", createBacktestHandler)

		// List backtests with filters
		backtestGroup.GET("", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			limit := 50
			offset := 0
			var status, days *string

			if l := c.Query("limit"); l != "" {
				var i int
				if _, err := parseIntQuery(l, &i); err == nil && i > 0 {
					limit = i
				}
			}
			if o := c.Query("offset"); o != "" {
				var i int
				if _, err := parseIntQuery(o, &i); err == nil && i >= 0 {
					offset = i
				}
			}
			if s := c.Query("status"); s != "" {
				status = &s
			}
			if d := c.Query("days"); d != "" {
				days = &d
			}

			result, err := requestClient.ListBacktestsWithFilters(limit, offset, status, parseIntPtr(days))
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			syncRunList(c, result)
			respondBacktestEnvelope(c, http.StatusOK, "Backtests fetched successfully", result)
		})

		// Get backtest summary stats
		backtestGroup.GET("/stats/summary", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			days := 30
			if d := c.Query("days"); d != "" {
				if v, err := parseIntQuery(d, &days); err == nil {
					days = v
				}
			}
			result, err := requestClient.GetBacktestSummaryStats(days)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			respondBacktestEnvelope(c, http.StatusOK, "Backtest summary stats fetched successfully", result)
		})

		// Compare backtests
		backtestGroup.POST("/compare", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			var config map[string]interface{}
			if err := c.BindJSON(&config); err != nil {
				c.JSON(400, gin.H{"error": "Invalid request body"})
				return
			}
			result, err := requestClient.CompareBacktests(config)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			respondBacktestEnvelope(c, http.StatusOK, "Backtest comparison completed successfully", result)
		})

		// Get backtest by ID
		backtestGroup.GET("/:run_id", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			result, err := requestClient.GetBacktestDetails(runID)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			result = normalizeBacktestDetailsPayload(result)
			syncRun(c, result)
			syncChildren(c, runID, result)
			respondBacktestEnvelope(c, http.StatusOK, "Backtest fetched successfully", result)
		})

		backtestGroup.GET("/:run_id/summary", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")

			details, err := requestClient.GetBacktestDetails(runID)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			details = normalizeBacktestDetailsPayload(details)
			detailData := unwrapEnvelopePayload(details)
			syncRun(c, details)
			syncChildren(c, runID, details)

			tradeLimit := resolveBacktestTradeLimit(detailData)
			tradesPayload, tradesErr := requestClient.GetBacktestDetailedTrades(runID, tradeLimit, 0)
			if tradesErr != nil {
				if !isUpstreamNotFound(tradesErr) {
					tradesPayload, tradesErr = requestClient.GetBacktestTradesWithFilters(runID, tradeLimit, 0, false)
				}
				if tradesErr != nil && !isUpstreamNotFound(tradesErr) {
					respondBotAPIError(c, tradesErr)
					return
				}
				if tradesErr != nil {
					tradesPayload = map[string]interface{}{"trades": []interface{}{}, "total": 0}
				}
			}
			syncChildren(c, runID, tradesPayload)

			respondBacktestEnvelope(
				c,
				http.StatusOK,
				"Backtest summary fetched successfully",
				buildBacktestSummaryPayload(details, tradesPayload, runID),
			)
		})

		// Delete backtest
		backtestGroup.DELETE("/:run_id", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			result, err := requestClient.DeleteBacktest(runID)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			respondBacktestEnvelope(c, http.StatusOK, "Backtest deleted successfully", result)
		})

		// Get backtest status
		backtestGroup.GET("/:run_id/status", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			result, err := requestClient.GetBacktestStatus(runID)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			result = normalizeBacktestStatusPayload(result)
			syncRun(c, result)
			respondBacktestEnvelope(c, http.StatusOK, "Backtest status fetched successfully", result)
		})

		backtestGroup.GET("/:run_id/logs", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			limit := 200
			if l := c.Query("limit"); l != "" {
				if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
					limit = parsed
				}
			}
			result, err := requestClient.GetBacktestLogs(runID, limit)
			if err != nil {
				if isUpstreamNotFound(err) {
					respondBacktestEnvelope(c, http.StatusOK, "Backtest logs fetched successfully", map[string]interface{}{"logs": []interface{}{}, "total": 0})
					return
				}
				respondBotAPIError(c, err)
				return
			}

			data := asMap(result["data"])
			if data == nil {
				data = map[string]interface{}{}
			}
			logs := asSlice(data["logs"])
			if logs == nil {
				logs = asSlice(result["logs"])
			}
			if logs == nil {
				logs = []interface{}{}
			}
			total, hasTotal := getNumberField(data, "total")
			if !hasTotal {
				total = float64(len(logs))
			}
			respondBacktestEnvelope(c, http.StatusOK, "Backtest logs fetched successfully", map[string]interface{}{"logs": logs, "total": total})
		})

		// Force re-sync run + child artifacts from upstream bot API into local DB.
		backtestGroup.POST("/:run_id/resync", func(c *gin.Context) {
			if backtestSync == nil {
				c.JSON(http.StatusServiceUnavailable, gin.H{
					"success":   false,
					"error":     "backtest sync service unavailable",
					"timestamp": time.Now().UTC().Format(time.RFC3339),
				})
				return
			}

			runID := strings.TrimSpace(c.Param("run_id"))
			if runID == "" {
				c.JSON(http.StatusBadRequest, gin.H{
					"success":   false,
					"error":     "run_id is required",
					"timestamp": time.Now().UTC().Format(time.RFC3339),
				})
				return
			}

			requestClient := getRequestBotAPIClient(c, apiClient)
			result := gin.H{
				"run_synced":       false,
				"trades_synced":    false,
				"positions_synced": false,
				"candles_synced":   false,
				"run_id":           runID,
				"status":           "unknown",
				"progress_percent": 0.0,
				"progress_pct":     0.0,
				"progress":         0.0,
				"current_task":     nil,
				"current_pair":     nil,
				"sync_state":       "partial",
			}

			details, err := requestClient.GetBacktestDetails(runID)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			details = normalizeBacktestDetailsPayload(details)
			state := normalizeBacktestStatusFields(unwrapEnvelopePayload(details))
			if v, ok := state["run_id"]; ok && strings.TrimSpace(fmt.Sprintf("%v", v)) != "" {
				result["run_id"] = v
			}
			if v, ok := state["status"]; ok {
				result["status"] = v
			}
			for _, key := range []string{"progress_percent", "progress_pct", "progress", "current_task", "current_pair"} {
				if v, ok := state[key]; ok {
					result[key] = v
				}
			}
			syncRun(c, details)
			syncChildren(c, runID, details)
			result["run_synced"] = true

			tradesPayload, err := requestClient.GetBacktestTradesWithFilters(runID, 500, 0, false)
			if err == nil {
				syncChildren(c, runID, tradesPayload)
				result["trades_synced"] = true
			}

			positionsPayload, err := requestClient.GetPositionSnapshots(runID, 500, 0, nil)
			if err == nil {
				syncChildren(c, runID, positionsPayload)
				result["positions_synced"] = true
			}

			metricsPayload, err := requestClient.GetAdvancedPerformanceMetrics(runID, "BTC-USD")
			if err == nil {
				syncChildren(c, runID, metricsPayload)
				result["candles_synced"] = true
			}

			if result["run_synced"] == true && result["trades_synced"] == true && result["positions_synced"] == true && result["candles_synced"] == true {
				result["sync_state"] = "completed"
			}

			respondBacktestEnvelope(c, http.StatusOK, "Backtest re-sync completed successfully", result)
		})

		// Get backtest trades
		backtestGroup.GET("/:run_id/trades", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			limit := 100
			offset := 0
			winningOnly := false

			if l := c.Query("limit"); l != "" {
				if v, err := parseIntQuery(l, &limit); err == nil {
					limit = v
				}
			}
			if o := c.Query("offset"); o != "" {
				if v, err := parseIntQuery(o, &offset); err == nil {
					offset = v
				}
			}
			if c.Query("winning_only") == "true" {
				winningOnly = true
			}

			result, err := requestClient.GetBacktestTradesWithFilters(runID, limit, offset, winningOnly)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			syncChildren(c, runID, result)
			respondBacktestEnvelope(c, http.StatusOK, "Backtest trades fetched successfully", result)
		})

		backtestGroup.GET("/:run_id/trades/detailed", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			limit := 100
			offset := 0
			if l := c.Query("limit"); l != "" {
				if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
					limit = parsed
				}
			}
			if o := c.Query("offset"); o != "" {
				if parsed, err := strconv.Atoi(o); err == nil && parsed >= 0 {
					offset = parsed
				}
			}

			result, err := requestClient.GetBacktestDetailedTrades(runID, limit, offset)
			if err != nil {
				if isUpstreamNotFound(err) {
					fallbackResult, fallbackErr := requestClient.GetBacktestTradesWithFilters(runID, limit, offset, false)
					if fallbackErr != nil {
						if isUpstreamNotFound(fallbackErr) {
							respondBacktestEnvelope(c, http.StatusOK, "Backtest detailed trades fetched successfully", map[string]interface{}{"trades": []interface{}{}, "total": 0})
							return
						}
						respondBotAPIError(c, fallbackErr)
						return
					}
					syncChildren(c, runID, fallbackResult)
					fallbackData := asMap(fallbackResult["data"])
					if fallbackData == nil {
						fallbackData = map[string]interface{}{}
					}
					fallbackTrades := asSlice(fallbackData["trades"])
					if fallbackTrades == nil {
						fallbackTrades = asSlice(fallbackResult["trades"])
					}
					if fallbackTrades == nil {
						fallbackTrades = []interface{}{}
					}
					total, hasTotal := getNumberField(fallbackData, "total")
					if !hasTotal {
						total = float64(len(fallbackTrades))
					}
					respondBacktestEnvelope(c, http.StatusOK, "Backtest detailed trades fetched successfully", map[string]interface{}{"trades": fallbackTrades, "total": total})
					return
				}
				respondBotAPIError(c, err)
				return
			}

			data := asMap(result["data"])
			if data == nil {
				data = map[string]interface{}{}
			}
			trades := asSlice(data["trades"])
			if trades == nil {
				trades = asSlice(result["trades"])
			}
			if trades == nil {
				trades = []interface{}{}
			}
			total, hasTotal := getNumberField(data, "total")
			if !hasTotal {
				total = float64(len(trades))
			}
			respondBacktestEnvelope(c, http.StatusOK, "Backtest detailed trades fetched successfully", map[string]interface{}{"trades": trades, "total": total})
		})

		// Cancel backtest
		backtestGroup.POST("/:run_id/cancel", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			result, err := requestClient.CancelBacktest(runID)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			respondBacktestEnvelope(c, http.StatusOK, "Backtest cancelled successfully", result)
		})

		// Get backtest analytics
		backtestGroup.GET("/:run_id/analytics", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			result, err := requestClient.GetBacktestAnalytics(runID)
			if err != nil {
				if isUpstreamNotFound(err) {
					respondBacktestEnvelope(c, http.StatusOK, "Backtest analytics fetched successfully", map[string]interface{}{"daily_pnl": []interface{}{}})
					return
				}
				respondBotAPIError(c, err)
				return
			}
			syncChildren(c, runID, result)
			data := asMap(result["data"])
			if data == nil {
				data = map[string]interface{}{}
			}
			daily := asSlice(data["daily_pnl"])
			if daily == nil {
				daily = asSlice(result["daily_pnl"])
			}
			if daily == nil {
				daily = []interface{}{}
			}
			data["daily_pnl"] = daily
			respondBacktestEnvelope(c, http.StatusOK, "Backtest analytics fetched successfully", data)
		})

		// Get position snapshots
		backtestGroup.GET("/:run_id/position-snapshots", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			limit := 100
			offset := 0
			var marketPair *string

			if l := c.Query("limit"); l != "" {
				if v, err := parseIntQuery(l, &limit); err == nil {
					limit = v
				}
			}
			if o := c.Query("offset"); o != "" {
				if v, err := parseIntQuery(o, &offset); err == nil {
					offset = v
				}
			}
			if m := c.Query("market_pair"); m != "" {
				marketPair = &m
			}

			result, err := requestClient.GetPositionSnapshots(runID, limit, offset, marketPair)
			if err != nil {
				if isUpstreamNotFound(err) {
					respondBacktestEnvelope(c, http.StatusOK, "Backtest position snapshots fetched successfully", map[string]interface{}{"snapshots": []interface{}{}})
					return
				}
				respondBotAPIError(c, err)
				return
			}
			syncChildren(c, runID, result)
			data := asMap(result["data"])
			if data == nil {
				data = map[string]interface{}{}
			}
			snapshots := asSlice(data["snapshots"])
			if snapshots == nil {
				snapshots = asSlice(data["position_snapshots"])
			}
			if snapshots == nil {
				snapshots = asSlice(result["position_snapshots"])
			}
			if snapshots == nil {
				snapshots = []interface{}{}
			}
			data["snapshots"] = snapshots
			respondBacktestEnvelope(c, http.StatusOK, "Backtest position snapshots fetched successfully", data)
		})

		// Frontend compatibility alias for snapshots endpoint.
		backtestGroup.GET("/:run_id/positions/snapshots", func(c *gin.Context) {
			c.Request.URL.Path = strings.Replace(c.Request.URL.Path, "/positions/snapshots", "/position-snapshots", 1)
			c.Params = append(c.Params, gin.Param{Key: "__alias__", Value: "positions/snapshots"})
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			result, err := requestClient.GetPositionSnapshots(runID, 100, 0, nil)
			if err != nil {
				if isUpstreamNotFound(err) {
					respondBacktestEnvelope(c, http.StatusOK, "Backtest position snapshots fetched successfully", map[string]interface{}{"snapshots": []interface{}{}})
					return
				}
				respondBotAPIError(c, err)
				return
			}
			syncChildren(c, runID, result)
			data := asMap(result["data"])
			if data == nil {
				data = map[string]interface{}{}
			}
			snapshots := asSlice(data["snapshots"])
			if snapshots == nil {
				snapshots = asSlice(result["position_snapshots"])
			}
			if snapshots == nil {
				snapshots = []interface{}{}
			}
			data["snapshots"] = snapshots
			respondBacktestEnvelope(c, http.StatusOK, "Backtest position snapshots fetched successfully", data)
		})

		// Get dYdX validation
		backtestGroup.GET("/:run_id/dydx-validation", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			result, err := requestClient.ValidateAgainstdYdXData(runID)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			respondBacktestEnvelope(c, http.StatusOK, "dYdX validation fetched successfully", result)
		})

		// Get performance metrics
		backtestGroup.GET("/:run_id/performance-metrics", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			benchmark := c.DefaultQuery("benchmark", "BTC-USD")
			result, err := requestClient.GetAdvancedPerformanceMetrics(runID, benchmark)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			syncChildren(c, runID, result)
			respondBacktestEnvelope(c, http.StatusOK, "Backtest performance metrics fetched successfully", result)
		})

		backtestGroup.GET("/:run_id/performance", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			benchmark := c.DefaultQuery("benchmark", "BTC-USD")

			details, err := requestClient.GetBacktestDetails(runID)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			details = normalizeBacktestDetailsPayload(details)
			detailData := unwrapEnvelopePayload(details)
			syncRun(c, details)
			syncChildren(c, runID, details)

			metricsPayload, metricsErr := requestClient.GetAdvancedPerformanceMetrics(runID, benchmark)
			if metricsErr != nil && !isUpstreamNotFound(metricsErr) {
				respondBotAPIError(c, metricsErr)
				return
			}
			if metricsErr != nil {
				metricsPayload = map[string]interface{}{}
			}

			tradeLimit := resolveBacktestTradeLimit(detailData)
			tradesPayload, tradesErr := requestClient.GetBacktestDetailedTrades(runID, tradeLimit, 0)
			if tradesErr != nil {
				if !isUpstreamNotFound(tradesErr) {
					tradesPayload, tradesErr = requestClient.GetBacktestTradesWithFilters(runID, tradeLimit, 0, false)
				}
				if tradesErr != nil && !isUpstreamNotFound(tradesErr) {
					respondBotAPIError(c, tradesErr)
					return
				}
				if tradesErr != nil {
					tradesPayload = map[string]interface{}{"trades": []interface{}{}, "total": 0}
				}
			}
			syncChildren(c, runID, tradesPayload)

			respondBacktestEnvelope(
				c,
				http.StatusOK,
				"Backtest performance fetched successfully",
				buildBacktestPerformancePayload(details, metricsPayload, tradesPayload, runID),
			)
		})

		// Get live progress
		backtestGroup.GET("/:run_id/live-progress", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			result, err := requestClient.GetLiveProgress(runID)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			respondBacktestEnvelope(c, http.StatusOK, "Backtest live progress fetched successfully", result)
		})

		// WebSocket proxy for backtest live updates
		backtestGroup.GET("/:run_id/live", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			upstreamEndpoint := fmt.Sprintf("/api/v1/backtests/%s/live", runID)
			proxyWebSocket(c, requestClient, upstreamEndpoint)
		})
	}

	// Bot real-time data endpoints
	botGroup := router.Group("/api/v1/bots")
	botGroup.Use(middleware.RequireAuth())
	botGroup.Use(withRequestScopedBotClient)
	{
		// Get current positions
		botGroup.GET("/:instance_id/positions/current", func(c *gin.Context) {
			botID := c.Param("instance_id")
			delegateJSON(c, apiClient, func(requestClient *services.BotAPIClient) (map[string]interface{}, error) {
				return requestClient.GetCurrentPositions(botID)
			})
		})

		// Get specific position
		botGroup.GET("/:instance_id/positions/:position_id", func(c *gin.Context) {
			botID, err := normalizeRealtimeBotInstanceID(c.Param("instance_id"))
			if err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
				return
			}
			positionID := c.Param("position_id")
			delegateJSON(c, apiClient, func(requestClient *services.BotAPIClient) (map[string]interface{}, error) {
				return requestClient.GetPosition(botID, positionID)
			})
		})

		// Get position history
		botGroup.GET("/:instance_id/position-history/:position_id", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			botID, err := normalizeRealtimeBotInstanceID(c.Param("instance_id"))
			if err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
				return
			}
			positionID := c.Param("position_id")
			hours := 24
			if h := c.Query("hours"); h != "" {
				if v, err := parseIntQuery(h, &hours); err == nil {
					hours = v
				}
			}
			result, err := requestClient.GetPositionHistory(botID, positionID, hours)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			c.JSON(200, result)
		})

		// Get market data
		botGroup.GET("/:instance_id/market-data", func(c *gin.Context) {
			botID, err := normalizeRealtimeBotInstanceID(c.Param("instance_id"))
			if err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
				return
			}
			delegateJSON(c, apiClient, func(requestClient *services.BotAPIClient) (map[string]interface{}, error) {
				return requestClient.GetMarketData(botID)
			})
		})

		// Get realtime stats
		botGroup.GET("/:instance_id/realtime-stats", func(c *gin.Context) {
			botID, err := normalizeRealtimeBotInstanceID(c.Param("instance_id"))
			if err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
				return
			}
			delegateJSON(c, apiClient, func(requestClient *services.BotAPIClient) (map[string]interface{}, error) {
				return requestClient.GetRealtimeStats(botID)
			})
		})

		// Get alerts
		botGroup.GET("/:instance_id/alerts", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			botID, err := normalizeRealtimeBotInstanceID(c.Param("instance_id"))
			if err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
				return
			}
			limit := 50
			if l := c.Query("limit"); l != "" {
				if v, err := parseIntQuery(l, &limit); err == nil {
					limit = v
				}
			}
			result, err := requestClient.GetAlerts(botID, limit)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			c.JSON(200, result)
		})

		// Get bot history
		botGroup.GET("/:instance_id/history", func(c *gin.Context) {
			instanceID := c.Param("instance_id")
			days := 7
			if d := c.Query("days"); d != "" {
				if v, err := parseIntQuery(d, &days); err == nil {
					days = v
				}
			}
			delegateJSON(c, apiClient, func(requestClient *services.BotAPIClient) (map[string]interface{}, error) {
				return requestClient.GetBotHistory(instanceID, days)
			})
		})

		// Get bot jobs
		botGroup.GET("/:instance_id/jobs", func(c *gin.Context) {
			instanceID := c.Param("instance_id")
			days := 7
			if d := c.Query("days"); d != "" {
				if v, err := parseIntQuery(d, &days); err == nil {
					days = v
				}
			}
			delegateJSON(c, apiClient, func(requestClient *services.BotAPIClient) (map[string]interface{}, error) {
				return requestClient.GetBotJobs(instanceID, days)
			})
		})

		// Quick deploy bot
		botGroup.POST("/quick-deploy", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			instanceName := c.Query("instance_name")
			autoStart := c.DefaultQuery("auto_start", "true") == "true"

			var config map[string]interface{}
			if err := c.BindJSON(&config); err != nil {
				c.JSON(400, gin.H{"error": "Invalid request body"})
				return
			}

			result, err := requestClient.QuickDeployBot(instanceName, autoStart, config)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			c.JSON(200, result)
		})

		// WebSocket proxies for bot live channels
		botGroup.GET("/:instance_id/positions/live", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			instanceID := c.Param("instance_id")
			upstreamEndpoint := fmt.Sprintf("/api/v1/bots/%s/positions/live", instanceID)
			proxyWebSocket(c, requestClient, upstreamEndpoint)
		})

		botGroup.GET("/:instance_id/market/live", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			instanceID := c.Param("instance_id")
			upstreamEndpoint := fmt.Sprintf("/api/v1/bots/%s/market/live", instanceID)
			proxyWebSocket(c, requestClient, upstreamEndpoint)
		})

		botGroup.GET("/:instance_id/alerts/live", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			instanceID := c.Param("instance_id")
			upstreamEndpoint := fmt.Sprintf("/api/v1/bots/%s/alerts/live", instanceID)
			proxyWebSocket(c, requestClient, upstreamEndpoint)
		})
	}

	// System status endpoint
	router.GET("/api/v1/system/status", middleware.RequireAuth(), func(c *gin.Context) {
		requestClient := apiClient.WithTraceID(middleware.GetTraceID(c))
		if !services.UseConfiguredBotAPIServiceToken() {
			if token := extractBotAuthToken(c); token != "" {
				requestClient = requestClient.WithToken(token)
			}
		}
		c.Set("bot_api_client", requestClient)
		delegateJSON(c, apiClient, func(requestClient *services.BotAPIClient) (map[string]interface{}, error) {
			return requestClient.SystemStatus()
		})
	})

	// Frontend strategy websocket compatibility endpoint.
	// The UI currently connects to /ws/strategies, so keep this on backend origin
	// and proxy upstream to the bot API channel.
	strategyWSGroup := router.Group("/ws")
	strategyWSGroup.Use(middleware.RequireAuth())
	strategyWSGroup.Use(withRequestScopedBotClient)
	{
		strategyWSGroup.GET("/strategies", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			proxyWebSocket(c, requestClient, "/ws/strategies")
		})
	}
}

// Helper functions
func parseIntQuery(s string, target *int) (int, error) {
	i, err := strconv.Atoi(s)
	if err == nil {
		*target = i
	}
	return i, err
}

func parseIntPtr(s *string) *int {
	if s == nil {
		return nil
	}
	if i, err := strconv.Atoi(*s); err == nil {
		return &i
	}
	return nil
}

func normalizeRealtimeBotInstanceID(instanceID string) (string, error) {
	trimmed := strings.TrimSpace(instanceID)
	if trimmed == "" {
		return "", fmt.Errorf("instance_id is required")
	}
	return trimmed, nil
}
