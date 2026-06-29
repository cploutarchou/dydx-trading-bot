// Package routes provides HTTP route registration and handlers for delegated bot API endpoints in the dYdX backend API.
package routes

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/nats"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
)

var websocketUpgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return middleware.IsAllowedBrowserOrigin(r.Header.Get("Origin"))
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
		"benchmark_symbol",
		"max_history_days",
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

func readPositiveIntEnv(defaultValue int, keys ...string) int {
	for _, key := range keys {
		raw := strings.TrimSpace(os.Getenv(key))
		if raw == "" {
			continue
		}
		value, err := strconv.Atoi(raw)
		if err != nil {
			continue
		}
		if value < 0 {
			return 0
		}
		return value
	}
	if defaultValue < 0 {
		return 0
	}
	return defaultValue
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

func stringSliceField(payload map[string]interface{}, keys ...string) []string {
	for _, key := range keys {
		value, exists := payload[key]
		if !exists || value == nil {
			continue
		}
		items := make([]string, 0)
		switch typed := value.(type) {
		case []interface{}:
			for _, item := range typed {
				cleaned := strings.ToUpper(strings.TrimSpace(fmt.Sprintf("%v", item)))
				if cleaned != "" {
					items = append(items, cleaned)
				}
			}
		case []string:
			for _, item := range typed {
				cleaned := strings.ToUpper(strings.TrimSpace(item))
				if cleaned != "" {
					items = append(items, cleaned)
				}
			}
		}
		if len(items) > 0 {
			seen := make(map[string]struct{}, len(items))
			deduped := make([]string, 0, len(items))
			for _, item := range items {
				if _, exists := seen[item]; exists {
					continue
				}
				seen[item] = struct{}{}
				deduped = append(deduped, item)
			}
			return deduped
		}
	}
	return []string{}
}

func pairLabelsToMarkets(pairLabels []string) []string {
	markets := make([]string, 0)
	seen := make(map[string]struct{})
	for _, label := range pairLabels {
		parts := strings.Split(strings.ToUpper(strings.TrimSpace(label)), "/")
		for _, part := range parts {
			market := strings.TrimSpace(part)
			if market == "" {
				continue
			}
			if _, exists := seen[market]; exists {
				continue
			}
			seen[market] = struct{}{}
			markets = append(markets, market)
		}
	}
	return markets
}

func buildPairLabelsFromMarkets(markets []string) []string {
	labels := make([]string, 0)
	for i := 0; i < len(markets)-1; i++ {
		for j := i + 1; j < len(markets); j++ {
			labels = append(labels, fmt.Sprintf("%s/%s", markets[i], markets[j]))
		}
	}
	return labels
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
	payload["status"] = normalizeBacktestRunStatus(payload, progress)

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

var orderedBacktestArtifactNames = []string{
	"request",
	"trades",
	"position_snapshots",
	"daily_pnl",
	"full_result",
	"run_root",
}

func buildBacktestArtifactPayload(runID string, payload map[string]interface{}, signer *services.MinIOArtifactSigner) (map[string]interface{}, error) {
	artifactRefs, source := resolveBacktestArtifactRefs(runID, payload, signer.DefaultBucket())
	artifacts := make([]interface{}, 0, len(artifactRefs))
	for _, name := range orderedBacktestArtifactNames {
		reference, ok := artifactRefs[name]
		if !ok {
			continue
		}
		entry, err := buildBacktestArtifactEntry(name, reference, signer)
		if err != nil {
			return nil, err
		}
		artifacts = append(artifacts, entry)
	}
	return map[string]interface{}{
		"artifacts":       artifacts,
		"count":           len(artifacts),
		"artifact_source": source,
	}, nil
}

func resolveBacktestArtifactRefs(runID string, payload map[string]interface{}, defaultBucket string) (map[string]string, string) {
	resolved := map[string]string{}
	if artifactRefMap := asMap(payload["artifact_refs"]); artifactRefMap != nil {
		for _, name := range orderedBacktestArtifactNames {
			if value, ok := artifactRefMap[name]; ok {
				ref := strings.TrimSpace(fmt.Sprintf("%v", value))
				if ref != "" {
					resolved[name] = ref
				}
			}
		}
	}
	if len(resolved) > 0 {
		return resolved, "upstream"
	}

	defaultBucket = strings.TrimSpace(defaultBucket)
	runID = strings.TrimSpace(runID)
	if defaultBucket == "" || runID == "" {
		return resolved, "missing"
	}

	basePrefix := fmt.Sprintf("s3://%s/backtests/%s", defaultBucket, runID)
	resolved["request"] = basePrefix + "/request.json"
	resolved["trades"] = basePrefix + "/trades.json"
	resolved["position_snapshots"] = basePrefix + "/position_snapshots.json"
	resolved["daily_pnl"] = basePrefix + "/daily_pnl.json"
	resolved["run_root"] = basePrefix
	progress := 0.0
	if value, ok := getNumberField(payload, "progress_pct", "progress_percent", "progress"); ok {
		progress = value
	}
	if strings.EqualFold(normalizeBacktestRunStatus(payload, progress), "completed") {
		resolved["full_result"] = basePrefix + "/full_result.json"
	}
	return resolved, "derived"
}

func buildBacktestArtifactEntry(name, reference string, signer *services.MinIOArtifactSigner) (map[string]interface{}, error) {
	entry := map[string]interface{}{
		"artifact_name":      name,
		"download_available": false,
	}
	parsed, err := url.Parse(reference)
	if err != nil {
		entry["storage_backend"] = "invalid_reference"
		entry["reference_scheme"] = "invalid"
		return entry, nil
	}

	scheme := strings.TrimSpace(parsed.Scheme)
	if scheme == "" {
		scheme = "path"
	}
	entry["reference_scheme"] = scheme

	switch parsed.Scheme {
	case "s3":
		bucket := strings.TrimSpace(parsed.Host)
		objectKey := strings.Trim(strings.TrimSpace(parsed.Path), "/")
		entry["storage_backend"] = "minio"
		entry["bucket"] = bucket
		entry["object_key"] = objectKey
		if name == "run_root" || bucket == "" || objectKey == "" {
			return entry, nil
		}
		downloadURL, expiresAt, err := signer.PresignGet(bucket, objectKey, 15*time.Minute)
		if err != nil {
			return nil, fmt.Errorf("presign artifact %s: %w", name, err)
		}
		entry["download_available"] = true
		entry["download_url"] = downloadURL
		entry["download_url_expires_at"] = expiresAt.UTC().Format(time.RFC3339)
	case "file":
		entry["storage_backend"] = "local_fallback"
	default:
		entry["storage_backend"] = "unsupported"
	}

	return entry, nil
}

func normalizeBacktestStatusFields(payload map[string]interface{}) map[string]interface{} {
	if payload == nil {
		payload = map[string]interface{}{}
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
	if value, ok := getNumberField(payload, "progress_pct", "progress_percent", "progress"); ok {
		progress = value
	}
	payload["status"] = normalizeBacktestRunStatus(payload, progress)
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

func normalizeBacktestRunStatus(payload map[string]interface{}, progress float64) string {
	status := strings.ToLower(strings.TrimSpace(fmt.Sprintf("%v", payload["status"])))
	switch status {
	case "", "<nil>":
		status = "pending"
	case "created", "queued", "scheduled", "retry":
		status = "pending"
	case "in_progress", "processing", "active", "retrying":
		status = "running"
	case "succeeded", "success", "done":
		status = "completed"
	case "error":
		status = "failed"
	case "timed_out":
		status = "timeout"
	case "stalled":
		status = "stale"
	case "canceled":
		status = "cancelled"
	}

	errorMessage := strings.TrimSpace(getStringField(payload, "error_message", "error"))
	currentTask := strings.ToLower(strings.TrimSpace(getStringField(payload, "current_task")))
	currentPair := strings.ToLower(strings.TrimSpace(getStringField(payload, "current_pair")))
	hasMetrics := false
	for _, key := range []string{"total_pnl", "win_rate", "sharpe_ratio", "profit_factor", "total_trades"} {
		if value, ok := getNumberField(payload, key); ok && value != 0 {
			hasMetrics = true
			break
		}
	}

	if status == "pending" {
		switch {
		case strings.Contains(currentTask, "cancel") || strings.TrimSpace(fmt.Sprintf("%v", payload["cancel_requested"])) == "true":
			status = "cancelled"
		case errorMessage != "":
			status = "failed"
		case progress >= 100 || currentTask == "complete" || currentPair == "complete":
			status = "completed"
		case progress > 0 || hasMetrics || (currentTask != "" && currentTask != "pending" && currentTask != "queued") || (currentPair != "" && currentPair != "pending" && currentPair != "queued"):
			status = "running"
		}
	}
	return status
}

func normalizeBacktestRunFields(payload map[string]interface{}) map[string]interface{} {
	if payload == nil {
		return map[string]interface{}{}
	}
	progress := 0.0
	if value, ok := getNumberField(payload, "progress_pct", "progress_percent", "progress"); ok {
		progress = value
	}
	payload["status"] = normalizeBacktestRunStatus(payload, progress)
	payload["progress_percent"] = progress
	payload["progress_pct"] = progress
	payload["progress"] = progress
	return payload
}

func normalizeBacktestListPayload(payload map[string]interface{}) map[string]interface{} {
	if payload == nil {
		return map[string]interface{}{}
	}
	if data := asMap(payload["data"]); data != nil {
		payload["data"] = normalizeBacktestListPayload(data)
		return payload
	}
	for _, key := range []string{"backtests", "runs"} {
		items := asSlice(payload[key])
		if items == nil {
			continue
		}
		for i, item := range items {
			if run := asMap(item); run != nil {
				items[i] = normalizeBacktestRunFields(run)
			}
		}
		payload[key] = items
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

func normalizeBotJobStatus(status interface{}) string {
	normalized := strings.ToLower(strings.TrimSpace(fmt.Sprintf("%v", status)))
	switch normalized {
	case "pending", "running", "completed", "failed", "cancelled":
		return normalized
	case "queued", "created", "scheduled", "retry":
		return "pending"
	case "in_progress", "processing", "active", "retrying":
		return "running"
	case "succeeded", "success", "done":
		return "completed"
	case "error":
		return "failed"
	case "canceled":
		return "cancelled"
	default:
		return normalized
	}
}

func normalizeBotJobFields(job map[string]interface{}) map[string]interface{} {
	if job == nil {
		return map[string]interface{}{}
	}

	// Normalize status to canonical lowercase values
	if status, exists := job["status"]; exists && status != nil {
		job["status"] = normalizeBotJobStatus(status)
	}

	// Normalize progress fields (progress_pct is canonical, create aliases for compatibility)
	if progress, ok := getNumberField(job, "progress_pct", "progress_percent", "progress"); ok {
		job["progress_pct"] = progress
		if _, exists := job["progress_percent"]; !exists {
			job["progress_percent"] = progress
		}
		if _, exists := job["progress"]; !exists {
			job["progress"] = progress
		}
	}

	// Preserve all new DB-backed fields from Bot Service:
	// These fields are present in the database-driven job responses and should pass through unchanged:
	// job_id, job_type, updated_at, process_id, execution_time_ms, cancellation_reason,
	// metadata, error_message, error_traceback, started_at, completed_at, created_at,
	// result, config, retry_count, max_retries
	// All DB fields are preserved as-is from the API response

	return job
}

func normalizeBotJobSlice(items []interface{}) []interface{} {
	if items == nil {
		return nil
	}

	for i, item := range items {
		if job := asMap(item); job != nil {
			items[i] = normalizeBotJobFields(job)
		}
	}
	return items
}

func normalizeBotJobsPayload(payload map[string]interface{}) map[string]interface{} {
	if payload == nil {
		return map[string]interface{}{}
	}

	if data := asMap(payload["data"]); data != nil {
		payload["data"] = normalizeBotJobsPayload(data)
		return payload
	}

	if jobs := asSlice(payload["jobs"]); jobs != nil {
		payload["jobs"] = normalizeBotJobSlice(jobs)
		return payload
	}
	if jobs := asSlice(payload["job_history"]); jobs != nil {
		payload["job_history"] = normalizeBotJobSlice(jobs)
		return payload
	}
	if _, hasStatus := payload["status"]; hasStatus {
		return normalizeBotJobFields(payload)
	}

	return payload
}

func ensureBotDBSyncDiagnostics(payload map[string]interface{}) map[string]interface{} {
	if payload == nil {
		return payload
	}
	data := asMap(payload["data"])
	if data == nil {
		return payload
	}
	if _, exists := data["bot_db_sync"]; exists {
		return payload
	}
	data["bot_db_sync"] = map[string]interface{}{
		"active":            false,
		"remaining_seconds": 0.0,
		"state":             "unavailable",
	}
	return payload
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

// correlateBacktestCommand performs the Phase 4 dual-write of a backtest command
// using the real run_id returned by the bot API as both the command owner_id and
// idempotency_key. It is best-effort: any failure is logged and swallowed so the
// authoritative HTTP/Celery path is unaffected. If the bot response carries no
// run_id, the dual-write is skipped (with a log) rather than fabricating one, so
// command state never references a non-existent run.
// extractBacktestRunID reads the authoritative run_id from a bot API response,
// checking the top level and then the wrapped "data" envelope. Returns "" when
// no run_id is present so callers can skip the dual-write instead of fabricating.
func extractBacktestRunID(result map[string]interface{}) string {
	if runID := getStringField(result, "run_id"); runID != "" {
		return runID
	}
	if dataMap := asMap(result["data"]); dataMap != nil {
		return getStringField(dataMap, "run_id")
	}
	return ""
}

// correlateBacktestCommand performs the Phase 4 dual-write of a backtest command
// using the real run_id returned by the bot API as both the command owner_id and
// idempotency_key. It is best-effort: any failure is logged and swallowed so the
// authoritative HTTP/Celery path is unaffected. If the bot response carries no
// run_id, the dual-write is skipped (with a log) rather than fabricating one, so
// command state never references a non-existent run.
func correlateBacktestCommand(
	c *gin.Context,
	natsCommandService *services.NATSCommandService,
	result map[string]interface{},
	config map[string]interface{},
) {
	runID := extractBacktestRunID(result)
	if runID == "" {
		log.Printf("NATS Command Service: skipping dual-write, no run_id in bot response (trace_id=%s)", middleware.GetTraceID(c))
		return
	}

	userIDValue, _ := c.Get("user_id")
	userID, _ := userIDValue.(int)
	if _, err := natsCommandService.PublishBacktestCommand(c.Request.Context(), runID, config, &userID, runID); err != nil {
		log.Printf("NATS Command Service: failed to publish backtest command for run %s: %v", runID, err)
	}
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
		"run_id":              getStringField(details, "run_id"),
		"status":              status,
		"created_at":          createdAt,
		"started_at":          startedAt,
		"completed_at":        completedAt,
		"total_trades":        int(totalTrades),
		"earliest_trade_date": earliestTradeDate,
		"latest_trade_date":   latestTradeDate,
		"configuration": map[string]interface{}{
			"num_pairs":        inferBacktestPairCount(details),
			"zscore_threshold": zscoreThreshold,
			"stats_window":     int(statsWindow),
			"usd_per_trade":    usdPerTrade,
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

func ensureBacktestRunAccess(c *gin.Context, runID string, backtestRepo *repository.BacktestRepository) bool {
	runID = strings.TrimSpace(runID)
	if runID == "" || backtestRepo == nil {
		return true
	}
	if c.GetBool("is_admin") {
		return true
	}

	userIDValue, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{
			"success":   false,
			"message":   "unauthorized",
			"error":     "unauthorized",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
			"trace_id":  middleware.GetTraceID(c),
		})
		return false
	}
	userID, ok := userIDValue.(int)
	if !ok || userID <= 0 {
		c.JSON(http.StatusUnauthorized, gin.H{
			"success":   false,
			"message":   "invalid user context",
			"error":     "invalid user context",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
			"trace_id":  middleware.GetTraceID(c),
		})
		return false
	}

	ownerID, err := backtestRepo.GetRunOwnerID(runID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"success":   false,
			"message":   "failed to verify backtest access",
			"error":     err.Error(),
			"timestamp": time.Now().UTC().Format(time.RFC3339),
			"trace_id":  middleware.GetTraceID(c),
		})
		return false
	}
	if ownerID == nil {
		return true
	}
	if *ownerID != userID {
		c.JSON(http.StatusNotFound, gin.H{
			"success":   false,
			"message":   "backtest not found",
			"error":     "backtest not found",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
			"trace_id":  middleware.GetTraceID(c),
		})
		return false
	}

	return true
}

// RegisterBotAPIDelegateRoutes registers all delegated bot API endpoints
// These routes proxy to the Python bot API (default 127.0.0.1:8889) and sync with the Go database
func RegisterBotAPIDelegateRoutes(router *gin.Engine, apiClient *services.BotAPIClient) {
	RegisterBotAPIDelegateRoutesWithSyncAndCache(router, apiClient, nil, nil, nil, nil, nil)
}

// RegisterBotAPIDelegateRoutesWithSync registers delegated bot API endpoints and
// optionally persists backtest run status snapshots into local DB tables.
func RegisterBotAPIDelegateRoutesWithSync(router *gin.Engine, apiClient *services.BotAPIClient, backtestSync *services.BacktestSyncService) {
	RegisterBotAPIDelegateRoutesWithSyncAndCache(router, apiClient, backtestSync, nil, nil, nil, nil)
}

// RegisterBotAPIDelegateRoutesWithSyncCacheAndPush registers delegated bot API endpoints
// with optional backtest sync, Redis-backed cache, and a Redis pub/sub push hub for
// WebSocket status streaming.
func RegisterBotAPIDelegateRoutesWithSyncCacheAndPush(
	router *gin.Engine,
	apiClient *services.BotAPIClient,
	backtestSync *services.BacktestSyncService,
	cache *services.CacheService,
	pushHub *services.BacktestPushHub,
	taskRepo *repository.TaskRepository,
	natsPublisher *nats.Publisher,
	natsCommandService *services.NATSCommandService,
) {
	RegisterBotAPIDelegateRoutesWithSyncAndCache(router, apiClient, backtestSync, cache, taskRepo, natsPublisher, natsCommandService)

	var backtestRepo *repository.BacktestRepository
	if backtestSync != nil && backtestSync.DB() != nil {
		backtestRepo = repository.NewBacktestRepository(backtestSync.DB())
	}

	if pushHub == nil {
		return
	}

	// WebSocket endpoint for Redis-backed backtest status push
	// GET /api/v1/backtests/:run_id/push  (requires auth)
	backtestPush := router.Group("/api/v1/backtests")
	backtestPush.Use(middleware.RequireAuth())
	backtestPush.GET("/:run_id/push", func(c *gin.Context) {
		runID := strings.TrimSpace(c.Param("run_id"))
		if runID == "" {
			c.JSON(http.StatusBadRequest, gin.H{"error": "run_id required"})
			return
		}
		if !ensureBacktestRunAccess(c, runID, backtestRepo) {
			return
		}
		conn, err := websocketUpgrader.Upgrade(c.Writer, c.Request, nil)
		if err != nil {
			return
		}
		pushHub.Subscribe(runID, conn)
		defer func() {
			pushHub.Unsubscribe(runID, conn)
			_ = conn.Close()
		}()
		// Block until the client disconnects
		for {
			if _, _, err := conn.ReadMessage(); err != nil {
				return
			}
		}
	})
}

// RegisterBotAPIDelegateRoutesWithSyncAndCache registers delegated bot API endpoints with
// optional backtest sync and optional Redis-backed response cache for hot polling paths.
func RegisterBotAPIDelegateRoutesWithSyncAndCache(router *gin.Engine, apiClient *services.BotAPIClient, backtestSync *services.BacktestSyncService, cache *services.CacheService, taskRepo *repository.TaskRepository, natsPublisher *nats.Publisher, natsCommandService *services.NATSCommandService) {
	backtestRepo := (*repository.BacktestRepository)(nil)
	userRepo := (*repository.UserRepository)(nil)
	strategyRepo := (*repository.StrategyRepository)(nil)
	if backtestSync != nil && backtestSync.DB() != nil {
		backtestRepo = repository.NewBacktestRepository(backtestSync.DB())
		userRepo = repository.NewUserRepository(backtestSync.DB())
		strategyRepo = repository.NewStrategyRepository(backtestSync.DB())
	}
	backtestDelegation := NewBacktestDelegationService(backtestSync)

	// CandleCacheService for post-completion prefetch (nil-safe if Redis is off)
	var candleCache *services.CandleCacheService
	if cache != nil && backtestRepo != nil {
		candleCache = services.NewCandleCacheServiceWithRepo(cache, backtestRepo)
	}

	minioSettings := config.MinIOSettings{}
	if config.ConfigInstance != nil {
		minioSettings = config.ConfigInstance.MinIO
	}
	artifactSigner, err := services.NewMinIOArtifactSigner(minioSettings)
	if err != nil {
		log.Printf("Backtest artifact signer disabled: %v", err)
		artifactSigner = nil
	}

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
		// After candles are synced, prefetch into Redis in the background so the
		// first chart render is served from cache rather than the DB.
		if candleCache != nil {
			run, err := backtestRepo.GetRunByID(runID)
			if err == nil && run != nil && strings.EqualFold(run.Status, "completed") {
				go func(runPK int) {
					if prefetchErr := candleCache.PrefetchCandlesForRun(runPK, 0); prefetchErr != nil {
						log.Printf("CandleCache: prefetch error for run %s (pk=%d): %v", runID, runPK, prefetchErr)
					}
				}(run.ID)
			}
		}
	}

	resyncBacktestRun := func(c *gin.Context, requestClient *services.BotAPIClient, runID string) (gin.H, error) {
		return backtestDelegation.ResyncBacktestRun(c, requestClient, runID, syncRun, syncChildren)
	}

	requireBacktestRunAccess := func(c *gin.Context, runID string) bool {
		return ensureBacktestRunAccess(c, runID, backtestRepo)
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
		requestClient := apiClient.
			WithTraceID(middleware.GetTraceID(c)).
			WithRequestContext(c.Request.Context())

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

	requireAdminAccess := func(c *gin.Context) bool {
		role := models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin"))
		if c.GetBool("is_admin") || role == "admin" || role == "super_admin" || role == "backoffice_admin" {
			return true
		}

		c.JSON(http.StatusForbidden, gin.H{
			"success":   false,
			"message":   "admin access required",
			"error":     "admin access required",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
			"trace_id":  middleware.GetTraceID(c),
		})
		return false
	}

	createBacktestHandler := func(c *gin.Context) {
		requestClient := getRequestBotAPIClient(c, apiClient)
		var config map[string]interface{}
		if err := c.ShouldBindJSON(&config); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body", "message": err.Error()})
			return
		}
		config = normalizeBacktestRunPayload(config)
		var selectedMarkets []string
		snapshotSource := "none"
		snapshotName := ""
		strategyID := 0

		if c.FullPath() == "/api/v1/backtests/run" {
			selectedMarkets = stringSliceField(config, "pairs")
			selectedPairLabels := stringSliceField(config, "selected_pairs")
			if len(selectedMarkets) == 0 && len(selectedPairLabels) > 0 {
				selectedMarkets = pairLabelsToMarkets(selectedPairLabels)
			}
			if len(selectedMarkets) < 2 {
				c.JSON(http.StatusUnprocessableEntity, gin.H{
					"success":   false,
					"message":   "SELECTED_PAIRS_MISSING: at least two selected pairs are required",
					"error":     "SELECTED_PAIRS_MISSING",
					"data":      gin.H{"error": "SELECTED_PAIRS_MISSING"},
					"timestamp": time.Now().UTC().Format(time.RFC3339),
					"trace_id":  middleware.GetTraceID(c),
				})
				return
			}
			if len(selectedPairLabels) == 0 {
				selectedPairLabels = buildPairLabelsFromMarkets(selectedMarkets)
			}
			if len(selectedPairLabels) == 0 {
				c.JSON(http.StatusUnprocessableEntity, gin.H{
					"success":   false,
					"message":   "SELECTED_PAIRS_MISSING: at least one explicit selected pair is required",
					"error":     "SELECTED_PAIRS_MISSING",
					"data":      gin.H{"error": "SELECTED_PAIRS_MISSING"},
					"timestamp": time.Now().UTC().Format(time.RFC3339),
					"trace_id":  middleware.GetTraceID(c),
				})
				return
			}
			config["pairs"] = selectedMarkets
			config["selected_pairs"] = selectedPairLabels
			if _, exists := config["source"]; !exists {
				config["source"] = "ui"
			}
			if userID, ok := c.Get("user_id"); ok {
				config["requested_by_user_id"] = userID
			}
			if _, exists := config["environment"]; !exists {
				if env := strings.TrimSpace(os.Getenv("APP_ENV")); env != "" {
					config["environment"] = env
				} else if env := strings.TrimSpace(os.Getenv("ENVIRONMENT")); env != "" {
					config["environment"] = env
				}
			}

			if strategyIDValue, ok := getNumberField(config, "strategy_id"); ok {
				strategyID = int(strategyIDValue)
				if strategyID > 0 {
					if strategyRepo != nil {
						strategy, strategyErr := strategyRepo.GetStrategyByID(strategyID)
						if strategyErr != nil {
							c.JSON(http.StatusInternalServerError, gin.H{
								"success":   false,
								"message":   "failed to verify strategy",
								"error":     "STRATEGY_LOOKUP_FAILED",
								"timestamp": time.Now().UTC().Format(time.RFC3339),
								"trace_id":  middleware.GetTraceID(c),
							})
							return
						}
						if strategy == nil || strategy.DeletedAt != nil {
							c.JSON(http.StatusNotFound, gin.H{
								"success":   false,
								"message":   fmt.Sprintf("STRATEGY_NOT_FOUND: strategy_id=%d", strategyID),
								"error":     "STRATEGY_NOT_FOUND",
								"data":      gin.H{"error": "STRATEGY_NOT_FOUND", "strategy_id": strategyID},
								"timestamp": time.Now().UTC().Format(time.RFC3339),
								"trace_id":  middleware.GetTraceID(c),
							})
							return
						}
						userID := c.GetInt("user_id")
						if !c.GetBool("is_admin") && strategy.UserID != userID {
							c.JSON(http.StatusNotFound, gin.H{
								"success":   false,
								"message":   fmt.Sprintf("STRATEGY_NOT_FOUND: strategy_id=%d", strategyID),
								"error":     "STRATEGY_NOT_FOUND",
								"data":      gin.H{"error": "STRATEGY_NOT_FOUND", "strategy_id": strategyID},
								"timestamp": time.Now().UTC().Format(time.RFC3339),
								"trace_id":  middleware.GetTraceID(c),
							})
							return
						}
						config["strategy_payload_snapshot"] = strategy.ToDict()
						snapshotSource = "backend_strategy_repo"
						snapshotName = strategy.Name
					} else if _, strategyErr := requestClient.GetStrategy(strategyID); strategyErr != nil {
						log.Printf(
							"strategy_not_found strategy_id=%d endpoint=/api/v1/backtests/run trace_id=%s",
							strategyID,
							middleware.GetTraceID(c),
						)
						var apiErr *services.BotAPIError
						if errors.As(strategyErr, &apiErr) && apiErr.StatusCode == http.StatusNotFound {
							c.JSON(http.StatusNotFound, gin.H{
								"success":   false,
								"message":   fmt.Sprintf("STRATEGY_NOT_FOUND: strategy_id=%d", strategyID),
								"error":     "STRATEGY_NOT_FOUND",
								"data":      gin.H{"error": "STRATEGY_NOT_FOUND", "strategy_id": strategyID},
								"timestamp": time.Now().UTC().Format(time.RFC3339),
								"trace_id":  middleware.GetTraceID(c),
							})
							return
						}
						respondBotAPIError(c, strategyErr)
						return
					} else if snapshot := asMap(config["strategy_payload_snapshot"]); snapshot != nil {
						snapshotSource = "request_strategy_snapshot"
						snapshotName = getStringField(snapshot, "name")
					} else {
						snapshotSource = "bot_strategy_lookup"
					}
				}
			} else if asMap(config["strategy_payload_snapshot"]) == nil {
				c.JSON(http.StatusUnprocessableEntity, gin.H{
					"success":   false,
					"message":   "STRATEGY_PAYLOAD_MISSING: one-off backtests require a strategy_payload_snapshot",
					"error":     "STRATEGY_PAYLOAD_MISSING",
					"data":      gin.H{"error": "STRATEGY_PAYLOAD_MISSING"},
					"timestamp": time.Now().UTC().Format(time.RFC3339),
					"trace_id":  middleware.GetTraceID(c),
				})
				return
			} else {
				snapshotSource = "manual_request_snapshot"
				snapshotName = getStringField(asMap(config["strategy_payload_snapshot"]), "name")
			}

			snapshotMarkets := stringSliceField(asMap(config["strategy_payload_snapshot"]), "selected_markets")
			if snapshotName == "" {
				snapshotName = getStringField(asMap(config["strategy_payload_snapshot"]), "name")
			}
			log.Printf(
				"backtest_run_contract trace_id=%s strategy_id=%d snapshot_source=%s snapshot_name=%q selected_pairs=%d snapshot_selected_markets=%d has_trading_parameters=%t",
				middleware.GetTraceID(c),
				strategyID,
				snapshotSource,
				snapshotName,
				len(selectedPairLabels),
				len(snapshotMarkets),
				asMap(config["trading_parameters"]) != nil,
			)
		}

		var (
			result map[string]interface{}
			err    error
		)

		executeCreate := func() error {
			if c.FullPath() == "/api/v1/backtests/run" {
				result, err = requestClient.CreateBacktestRun(config)
			} else {
				result, err = requestClient.CreateBacktest(config)
			}
			if err != nil {
				return err
			}

			// The bot service initial response may omit start_date/end_date (e.g.
			// when queued via Celery or the dates default to empty string).
			// Back-fill them from the request config so both the sync DB record and
			// the frontend response contain the period the user actually requested.
			for _, field := range []string{"start_date", "end_date"} {
				requestVal, hasInConfig := config[field]
				if !hasInConfig {
					continue
				}
				// Fix at root level (flat response from bot service)
				if existing, ok := result[field]; !ok || existing == nil || existing == "" {
					result[field] = requestVal
				}
				// Fix inside the wrapped "data" envelope (api_response wrapper)
				if dataMap, ok := result["data"].(map[string]interface{}); ok {
					if existing, ok := dataMap[field]; !ok || existing == nil || existing == "" {
						dataMap[field] = requestVal
					}
				}
			}
			if _, exists := result["config"]; !exists {
				result["config"] = config
			}
			if dataMap, ok := result["data"].(map[string]interface{}); ok {
				if _, exists := dataMap["config"]; !exists {
					dataMap["config"] = config
				}
			}

			syncRun(c, result)

			// Phase 4 dual-write: record the command AFTER the bot API returns the
			// real run_id, so the task command's owner_id and idempotency_key
			// correlate to the authoritative backtest run instead of a fabricated
			// key. This is best-effort: failures are logged and never block the
			// authoritative HTTP/Celery path. The run_id is also the idempotency
			// key, giving one stable command per backtest run.
			if natsCommandService != nil {
				correlateBacktestCommand(c, natsCommandService, result, config)
			}
			return nil
		}

		admissionEnabled := false
		admissionUserID := 0
		maxActivePerUser := 0
		if backtestRepo != nil {
			if userIDValue, exists := c.Get("user_id"); exists {
				if userID, ok := userIDValue.(int); ok && userID > 0 {
					admissionUserID = userID
					maxActivePerUser = 10
					if userRepo != nil {
						if user, userErr := userRepo.GetByID(admissionUserID); userErr == nil && user != nil && user.MaxActiveBacktests > 0 {
							maxActivePerUser = user.MaxActiveBacktests
						}
					}
					if maxActivePerUser <= 0 {
						maxActivePerUser = readPositiveIntEnv(
							10,
							"BACKTEST_MAX_ACTIVE_RUNS_PER_USER",
							"BACKEND_BACKTEST_MAX_ACTIVE_RUNS_PER_USER",
						)
					}
					admissionEnabled = maxActivePerUser > 0
				}
			}
		}

		if admissionEnabled {
			capacityReached := false
			activeCount := 0

			lockCtx, cancel := context.WithTimeout(c.Request.Context(), 45*time.Second)
			defer cancel()

			admissionErr := backtestRepo.WithUserAdmissionLock(lockCtx, admissionUserID, func() error {
				count, countErr := backtestRepo.CountActiveRunsByUserID(admissionUserID)
				if countErr != nil {
					return countErr
				}
				activeCount = count
				if activeCount >= maxActivePerUser {
					capacityReached = true
					return nil
				}
				return executeCreate()
			})
			if admissionErr != nil {
				var transportErr *services.BotAPITransportError
				var apiErr *services.BotAPIError
				if errors.As(admissionErr, &transportErr) || errors.As(admissionErr, &apiErr) {
					respondBotAPIError(c, admissionErr)
					return
				}

				c.JSON(http.StatusInternalServerError, gin.H{
					"success":   false,
					"message":   "Failed to evaluate backtest admission limits",
					"error":     admissionErr.Error(),
					"timestamp": time.Now().UTC().Format(time.RFC3339),
					"trace_id":  middleware.GetTraceID(c),
				})
				return
			}

			if capacityReached {
				c.Header("Retry-After", "15")
				respondBacktestEnvelope(c, http.StatusTooManyRequests, "Backtest capacity reached for this account", map[string]interface{}{
					"error":                 "backtest_user_capacity_reached",
					"active_runs":           activeCount,
					"max_active_runs":       maxActivePerUser,
					"retry_after_seconds":   15,
					"admission_scope":       "per_user",
					"admission_enforced_by": "backend_user_quota",
				})
				return
			}
		} else {
			if err := executeCreate(); err != nil {
				respondBotAPIError(c, err)
				return
			}
		}

		respondBacktestEnvelope(c, http.StatusOK, "Backtest created successfully", result)
	}

	interruptedBacktestsHandler := func(admin bool) gin.HandlerFunc {
		return func(c *gin.Context) {
			if admin && !requireAdminAccess(c) {
				return
			}

			requestClient := getRequestBotAPIClient(c, apiClient)
			limit := 50
			if l := c.Query("limit"); l != "" {
				if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
					limit = parsed
				}
			}

			result, err := requestClient.GetInterruptedBacktests(limit, admin)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			respondBacktestEnvelope(c, http.StatusOK, "Interrupted backtests fetched successfully", result)
		}
	}

	reconcileInterruptedBacktestsHandler := func(admin bool) gin.HandlerFunc {
		return func(c *gin.Context) {
			if admin && !requireAdminAccess(c) {
				return
			}

			requestClient := getRequestBotAPIClient(c, apiClient)
			dryRun := true
			if raw := strings.TrimSpace(c.Query("dry_run")); raw != "" {
				dryRun = !strings.EqualFold(raw, "false")
			}

			result, err := requestClient.ReconcileInterruptedBacktests(dryRun, admin)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			respondBacktestEnvelope(c, http.StatusOK, "Interrupted backtests reconciled successfully", result)
		}
	}

	router.GET("/api/v1/capabilities", middleware.RequireAuth(), withRequestScopedBotClient, func(c *gin.Context) {
		requestClient := getRequestBotAPIClient(c, apiClient)
		delegateJSON(c, apiClient, func(_ *services.BotAPIClient) (map[string]interface{}, error) {
			return requestClient.GetCapabilities()
		})
	})

	router.GET("/api/v1/runtime/db-config", middleware.RequireAuth(), withRequestScopedBotClient, func(c *gin.Context) {
		if !requireAdminAccess(c) {
			return
		}

		requestClient := getRequestBotAPIClient(c, apiClient)
		delegateJSON(c, apiClient, func(_ *services.BotAPIClient) (map[string]interface{}, error) {
			return requestClient.GetRuntimeDBConfig()
		})
	})

	router.GET("/api/v1/markets/perpetuals", middleware.RequireAuth(), withRequestScopedBotClient, func(c *gin.Context) {
		requestClient := getRequestBotAPIClient(c, apiClient)
		limit := 0
		if rawLimit := strings.TrimSpace(c.Query("limit")); rawLimit != "" {
			if parsed, err := strconv.Atoi(rawLimit); err == nil && parsed > 0 {
				limit = parsed
			}
		}
		delegateJSON(c, apiClient, func(_ *services.BotAPIClient) (map[string]interface{}, error) {
			return requestClient.GetPerpetualMarkets(limit)
		})
	})

	arbitrageGroup := router.Group("/api/v1/arbitrage")
	arbitrageGroup.Use(middleware.RequireAuth())
	arbitrageGroup.Use(withRequestScopedBotClient)
	{
		arbitrageGroup.GET("/improvement-metrics", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			delegateJSON(c, apiClient, func(_ *services.BotAPIClient) (map[string]interface{}, error) {
				return requestClient.GetArbitrageImprovementMetrics()
			})
		})

		arbitrageGroup.GET("/pair-priority", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			limit := 25
			if rawLimit := strings.TrimSpace(c.Query("limit")); rawLimit != "" {
				if parsed, err := strconv.Atoi(rawLimit); err == nil && parsed > 0 {
					limit = parsed
				}
			}
			delegateJSON(c, apiClient, func(_ *services.BotAPIClient) (map[string]interface{}, error) {
				return requestClient.GetArbitragePairPriority(limit)
			})
		})

		arbitrageGroup.GET("/opportunity/:opportunity_id/explain", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			opportunityID := strings.TrimSpace(c.Param("opportunity_id"))
			if opportunityID == "" {
				c.JSON(http.StatusBadRequest, gin.H{
					"success":   false,
					"message":   "opportunity_id is required",
					"error":     "opportunity_id is required",
					"timestamp": time.Now().UTC().Format(time.RFC3339),
					"trace_id":  middleware.GetTraceID(c),
				})
				return
			}
			delegateJSON(c, apiClient, func(_ *services.BotAPIClient) (map[string]interface{}, error) {
				return requestClient.GetArbitrageOpportunityExplain(opportunityID)
			})
		})
	}

	celeryGroup := router.Group("/api/v1/celery")
	celeryGroup.Use(middleware.RequireAuth())
	celeryGroup.Use(withRequestScopedBotClient)
	celeryGroup.Use(func(c *gin.Context) {
		if !requireAdminAccess(c) {
			c.Abort()
			return
		}
		c.Next()
	})
	{
		celeryGroup.GET("/tasks", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			rawQuery := c.Request.URL.RawQuery
			delegateJSON(c, apiClient, func(_ *services.BotAPIClient) (map[string]interface{}, error) {
				return requestClient.ListCeleryTasks(rawQuery)
			})
		})
		celeryGroup.GET("/tasks/:task_id", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			taskID := strings.TrimSpace(c.Param("task_id"))
			delegateJSON(c, apiClient, func(_ *services.BotAPIClient) (map[string]interface{}, error) {
				return requestClient.GetCeleryTask(taskID)
			})
		})
		celeryGroup.POST("/tasks/:task_id/revoke", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			taskID := strings.TrimSpace(c.Param("task_id"))
			var payload map[string]interface{}
			_ = c.ShouldBindJSON(&payload)
			terminate := false
			if payload != nil {
				terminate, _ = payload["terminate"].(bool)
			}
			delegateJSON(c, apiClient, func(_ *services.BotAPIClient) (map[string]interface{}, error) {
				return requestClient.RevokeCeleryTask(taskID, terminate)
			})
		})
		celeryGroup.POST("/tasks/:task_id/retry", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			taskID := strings.TrimSpace(c.Param("task_id"))
			delegateJSON(c, apiClient, func(_ *services.BotAPIClient) (map[string]interface{}, error) {
				return requestClient.RetryCeleryTask(taskID)
			})
		})
		celeryGroup.GET("/workers", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			delegateJSON(c, apiClient, func(_ *services.BotAPIClient) (map[string]interface{}, error) {
				return requestClient.ListCeleryWorkers()
			})
		})
		celeryGroup.GET("/queues", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			delegateJSON(c, apiClient, func(_ *services.BotAPIClient) (map[string]interface{}, error) {
				return requestClient.ListCeleryQueues()
			})
		})
		celeryGroup.GET("/health", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			delegateJSON(c, apiClient, func(_ *services.BotAPIClient) (map[string]interface{}, error) {
				return requestClient.GetCeleryHealth()
			})
		})
	}

	// Backtest proxy endpoints
	backtestGroup := router.Group("/api/v1/backtests")
	backtestGroup.Use(middleware.RequireAuth())
	backtestGroup.Use(withRequestScopedBotClient)
	backtestGroup.Use(func(c *gin.Context) {
		if runID := c.Param("run_id"); strings.TrimSpace(runID) != "" {
			if !requireBacktestRunAccess(c, runID) {
				c.Abort()
				return
			}
		}
		c.Next()
	})
	{
		// Backtest preflight for UI/operator fail-fast checks before submitting a run.
		backtestGroup.GET("/preflight", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			healthPayload, err := requestClient.HealthCheck()
			if err != nil {
				errorCode := "backtest_preflight_bot_api_not_ready"
				var errorMessage string
				upstreamStatus := http.StatusServiceUnavailable

				var transportErr *services.BotAPITransportError
				var apiErr *services.BotAPIError
				switch {
				case errors.As(err, &transportErr):
					errorCode = "backtest_preflight_bot_api_unreachable"
					errorMessage = transportErr.Message
					if transportErr.StatusCode > 0 {
						upstreamStatus = transportErr.StatusCode
					}
				case errors.As(err, &apiErr):
					errorCode = "backtest_preflight_bot_api_not_ready"
					errorMessage = apiErr.Message
					if apiErr.StatusCode > 0 {
						upstreamStatus = apiErr.StatusCode
					}
				default:
					errorMessage = err.Error()
				}

				respondBacktestEnvelope(c, http.StatusServiceUnavailable, "Backtest preflight failed", map[string]interface{}{
					"preflight_ready": false,
					"error_code":      errorCode,
					"error":           errorMessage,
					"bot_api": map[string]interface{}{
						"reachable":       false,
						"base_url":        requestClient.BaseURL(),
						"upstream_status": upstreamStatus,
					},
				})
				return
			}

			respondBacktestEnvelope(c, http.StatusOK, "Backtest preflight passed", map[string]interface{}{
				"preflight_ready": true,
				"bot_api": map[string]interface{}{
					"reachable": true,
					"base_url":  requestClient.BaseURL(),
					"health":    unwrapEnvelopePayload(healthPayload),
				},
			})
		})

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

		backtestGroup.GET("/interrupted", interruptedBacktestsHandler(false))
		backtestGroup.POST("/interrupted/reconcile", reconcileInterruptedBacktestsHandler(false))

		// Batch re-sync latest runs for current user to backfill historical metrics.
		backtestGroup.POST("/resync-recent", func(c *gin.Context) {
			if backtestSync == nil || backtestRepo == nil {
				c.JSON(http.StatusServiceUnavailable, gin.H{
					"success":   false,
					"error":     "backtest sync service unavailable",
					"timestamp": time.Now().UTC().Format(time.RFC3339),
				})
				return
			}

			userIDValue, exists := c.Get("user_id")
			userID, ok := userIDValue.(int)
			if !exists || !ok || userID <= 0 {
				c.JSON(http.StatusUnauthorized, gin.H{
					"success":   false,
					"message":   "invalid user context",
					"error":     "invalid user context",
					"timestamp": time.Now().UTC().Format(time.RFC3339),
					"trace_id":  middleware.GetTraceID(c),
				})
				return
			}

			limit := 25
			if l := c.Query("limit"); l != "" {
				if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
					limit = parsed
				}
			}
			if limit > 100 {
				limit = 100
			}

			runs, err := backtestRepo.GetRunsByUserID(userID, 0, limit)
			if err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{
					"success":   false,
					"message":   "Failed to list recent backtests",
					"error":     err.Error(),
					"timestamp": time.Now().UTC().Format(time.RFC3339),
					"trace_id":  middleware.GetTraceID(c),
				})
				return
			}

			requestClient := getRequestBotAPIClient(c, apiClient)
			results := make([]gin.H, 0, len(runs))
			successCount := 0
			failureCount := 0

			for _, run := range runs {
				runID := strings.TrimSpace(run.RunID)
				if runID == "" {
					continue
				}
				row, syncErr := resyncBacktestRun(c, requestClient, runID)
				if syncErr != nil {
					failureCount++
					row["sync_state"] = "failed"
					row["error"] = syncErr.Error()
					results = append(results, row)
					continue
				}
				successCount++
				results = append(results, row)
			}

			respondBacktestEnvelope(c, http.StatusOK, "Recent backtest re-sync completed", map[string]interface{}{
				"limit":            limit,
				"processed":        len(results),
				"success_count":    successCount,
				"failure_count":    failureCount,
				"run_sync_results": results,
			})
		})

		// Create backtest
		backtestGroup.POST("", createBacktestHandler)
		// Frontend compatibility alias
		backtestGroup.POST("/run", createBacktestHandler)

		// List backtests with filters
		backtestGroup.GET("", func(c *gin.Context) {
			limit := 50
			offset := parseBacktestListOffset(c)

			if l := c.Query("limit"); l != "" {
				var i int
				if _, err := parseIntQuery(l, &i); err == nil && i > 0 {
					limit = i
				}
			}
			if limit > 500 {
				limit = 500
			}

			if backtestRepo == nil {
				respondBacktestEnvelope(c, http.StatusOK, "Backtests fetched successfully", map[string]interface{}{
					"backtests": []interface{}{},
					"total":     0,
				})
				return
			}

			userIDValue, exists := c.Get("user_id")
			userID, ok := userIDValue.(int)
			if !exists || !ok || userID <= 0 {
				c.JSON(http.StatusUnauthorized, gin.H{
					"success":   false,
					"message":   "invalid user context",
					"error":     "invalid user context",
					"timestamp": time.Now().UTC().Format(time.RFC3339),
					"trace_id":  middleware.GetTraceID(c),
				})
				return
			}

			runs, err := backtestRepo.GetRunsByUserID(userID, offset, limit)
			if err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{
					"success":   false,
					"message":   "Failed to retrieve backtests",
					"error":     err.Error(),
					"timestamp": time.Now().UTC().Format(time.RFC3339),
					"trace_id":  middleware.GetTraceID(c),
				})
				return
			}
			total, err := backtestRepo.CountRunsByUserID(userID)
			if err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{
					"success":   false,
					"message":   "Failed to count backtests",
					"error":     err.Error(),
					"timestamp": time.Now().UTC().Format(time.RFC3339),
					"trace_id":  middleware.GetTraceID(c),
				})
				return
			}
			if runs == nil {
				runs = []models.BacktestRun{}
			}
			respondBacktestEnvelope(c, http.StatusOK, "Backtests fetched successfully", map[string]interface{}{
				"backtests": runs,
				"total":     total,
			})
		})

		backtestGroup.GET("/experiments", func(c *gin.Context) {
			if backtestRepo == nil {
				respondBacktestEnvelope(c, http.StatusOK, "Backtest experiments fetched successfully", map[string]interface{}{
					"experiments": []models.BacktestExperimentGroup{},
					"count":       0,
				})
				return
			}

			userIDValue, exists := c.Get("user_id")
			userID, ok := userIDValue.(int)
			if !exists || !ok || userID <= 0 {
				c.JSON(http.StatusUnauthorized, gin.H{
					"success":   false,
					"message":   "invalid user context",
					"error":     "invalid user context",
					"timestamp": time.Now().UTC().Format(time.RFC3339),
					"trace_id":  middleware.GetTraceID(c),
				})
				return
			}

			runScanLimit := 500
			if raw := c.Query("run_limit"); raw != "" {
				if parsed, err := strconv.Atoi(raw); err == nil && parsed > 0 {
					runScanLimit = parsed
				}
			}

			groupLimit := 100
			if raw := c.Query("limit"); raw != "" {
				if parsed, err := strconv.Atoi(raw); err == nil && parsed > 0 {
					groupLimit = parsed
				}
			}

			experiments, err := backtestRepo.GetExperimentGroupsByUserID(userID, runScanLimit, groupLimit)
			if err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{
					"success":   false,
					"message":   "Failed to retrieve backtest experiments",
					"error":     err.Error(),
					"timestamp": time.Now().UTC().Format(time.RFC3339),
					"trace_id":  middleware.GetTraceID(c),
				})
				return
			}

			respondBacktestEnvelope(c, http.StatusOK, "Backtest experiments fetched successfully", map[string]interface{}{
				"experiments": experiments,
				"count":       len(experiments),
			})
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
			if err := c.ShouldBindJSON(&config); err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body", "message": err.Error()})
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

		backtestGroup.GET("/:run_id/artifacts", func(c *gin.Context) {
			runID := strings.TrimSpace(c.Param("run_id"))
			if runID == "" {
				respondBacktestEnvelope(c, http.StatusBadRequest, "run_id required", map[string]interface{}{
					"error": "run_id required",
				})
				return
			}
			if !requireBacktestRunAccess(c, runID) {
				return
			}
			if artifactSigner == nil {
				respondBacktestEnvelope(c, http.StatusServiceUnavailable, "Backtest artifact signing unavailable", map[string]interface{}{
					"error": "backtest artifact signing unavailable",
				})
				return
			}

			requestClient := getRequestBotAPIClient(c, apiClient)
			detailsPayload, err := requestClient.GetBacktestDetails(runID)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			detailsPayload = normalizeBacktestDetailsPayload(detailsPayload)
			syncRun(c, detailsPayload)

			artifactPayload, err := buildBacktestArtifactPayload(runID, unwrapEnvelopePayload(detailsPayload), artifactSigner)
			if err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{
					"success":   false,
					"message":   "Failed to build backtest artifact metadata",
					"error":     err.Error(),
					"timestamp": time.Now().UTC().Format(time.RFC3339),
					"trace_id":  middleware.GetTraceID(c),
				})
				return
			}

			respondBacktestEnvelope(c, http.StatusOK, "Backtest artifacts fetched successfully", artifactPayload)
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
			runPrimaryKey := 0
			if backtestRepo != nil {
				if run, lookupErr := backtestRepo.GetRunByID(runID); lookupErr == nil && run != nil {
					runPrimaryKey = run.ID
				}
			}
			result, err := requestClient.DeleteBacktest(runID)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			if candleCache != nil && runPrimaryKey > 0 {
				if invalidateErr := candleCache.InvalidateCandleCache(runPrimaryKey); invalidateErr != nil {
					log.Printf("CandleCache: invalidate error for deleted run %s (pk=%d): %v", runID, runPrimaryKey, invalidateErr)
				}
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

		backtestGroup.POST("/:run_id/metadata", func(c *gin.Context) {
			runID := strings.TrimSpace(c.Param("run_id"))
			if runID == "" {
				respondBacktestEnvelope(c, http.StatusBadRequest, "run_id required", map[string]interface{}{
					"error": "run_id required",
				})
				return
			}

			requestClient := getRequestBotAPIClient(c, apiClient)
			var payload map[string]interface{}
			if err := c.ShouldBindJSON(&payload); err != nil {
				respondBacktestEnvelope(c, http.StatusBadRequest, "Invalid request body", map[string]interface{}{
					"error": err.Error(),
				})
				return
			}

			metadataPayload, err := requestClient.UpdateBacktestMetadata(runID, payload)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}

			respondBacktestEnvelope(c, http.StatusOK, "Backtest metadata updated successfully", metadataPayload)
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
			result, err := resyncBacktestRun(c, requestClient, runID)
			if err != nil {
				respondBotAPIError(c, err)
				return
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

		// Pause backtest
		backtestGroup.POST("/:run_id/pause", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			result, err := requestClient.PauseBacktest(runID)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			respondBacktestEnvelope(c, http.StatusOK, "Backtest pause requested successfully", result)
		})

		// Resume backtest
		backtestGroup.POST("/:run_id/resume", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			result, err := requestClient.ResumeBacktest(runID)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			respondBacktestEnvelope(c, http.StatusOK, "Backtest resume requested successfully", result)
		})

		// Restart backtest
		backtestGroup.POST("/:run_id/restart", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			result, err := requestClient.RestartBacktest(runID)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			respondBacktestEnvelope(c, http.StatusOK, "Backtest restarted successfully", result)
		})

		// Retry backtest
		backtestGroup.POST("/:run_id/retry", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			result, err := requestClient.RetryBacktest(runID)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			respondBacktestEnvelope(c, http.StatusOK, "Backtest retried successfully", result)
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

		backtestGroup.GET("/:run_id/analytics/summary", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			result, err := requestClient.GetBacktestAnalyticsSummary(runID)
			if err != nil {
				if isUpstreamNotFound(err) {
					respondBacktestEnvelope(c, http.StatusOK, "Backtest analytics summary fetched successfully", map[string]interface{}{
						"run_id":        runID,
						"total_pnl":     0.0,
						"total_pnl_usd": 0.0,
						"total_trades":  0,
						"win_rate":      0.0,
					})
					return
				}
				respondBotAPIError(c, err)
				return
			}

			data := unwrapEnvelopePayload(result)
			if data == nil {
				data = map[string]interface{}{}
			}
			if getStringField(data, "run_id") == "" {
				data["run_id"] = runID
			}
			if _, ok := data["total_pnl"]; !ok {
				if value, exists := data["total_pnl_usd"]; exists {
					data["total_pnl"] = value
				} else {
					data["total_pnl"] = 0.0
				}
			}
			if _, ok := data["total_pnl_usd"]; !ok {
				if value, exists := data["total_pnl"]; exists {
					data["total_pnl_usd"] = value
				} else {
					data["total_pnl_usd"] = 0.0
				}
			}
			if _, ok := data["total_trades"]; !ok {
				data["total_trades"] = 0
			}
			if _, ok := data["win_rate"]; !ok {
				data["win_rate"] = 0.0
			}

			respondBacktestEnvelope(c, http.StatusOK, "Backtest analytics summary fetched successfully", data)
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

	adminBacktestGroup := router.Group("/api/v1/admin/backtests")
	adminBacktestGroup.Use(middleware.RequireAuth())
	adminBacktestGroup.Use(withRequestScopedBotClient)
	{
		adminBacktestGroup.GET("/interrupted", interruptedBacktestsHandler(true))
		adminBacktestGroup.POST("/interrupted/reconcile", reconcileInterruptedBacktestsHandler(true))
		adminBacktestGroup.POST("/:run_id/repair-request", func(c *gin.Context) {
			if !requireAdminAccess(c) {
				return
			}

			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := strings.TrimSpace(c.Param("run_id"))
			if runID == "" {
				c.JSON(http.StatusBadRequest, gin.H{
					"success":   false,
					"message":   "run_id is required",
					"error":     "run_id is required",
					"timestamp": time.Now().UTC().Format(time.RFC3339),
					"trace_id":  middleware.GetTraceID(c),
				})
				return
			}

			dryRun := true
			if raw := strings.TrimSpace(c.Query("dry_run")); raw != "" {
				dryRun = !strings.EqualFold(raw, "false")
			}

			result, err := requestClient.RepairBacktestRequest(runID, dryRun)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}

			respondBacktestEnvelope(c, http.StatusOK, "Backtest request repaired successfully", result)
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

		// Get realtime stats (cached with 30-second TTL when Redis is available)
		botGroup.GET("/:instance_id/realtime-stats", func(c *gin.Context) {
			botID, err := normalizeRealtimeBotInstanceID(c.Param("instance_id"))
			if err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
				return
			}

			cacheKey := fmt.Sprintf("bot:realtime-stats:%s", botID)
			statsTTL := readPositiveIntEnv(30, "BOT_STATS_CACHE_TTL_SECONDS")

			// Try Redis cache first
			if cache != nil && statsTTL > 0 {
				if cached, cacheErr := cache.GetCache(cacheKey); cacheErr == nil && cached != nil {
					if mapped, ok := cached.(map[string]interface{}); ok {
						c.JSON(http.StatusOK, mapped)
						return
					}
				}
			}

			// Cache miss — delegate to Python bot API
			requestClient := getRequestBotAPIClient(c, apiClient)
			result, delegateErr := requestClient.GetRealtimeStats(botID)
			if delegateErr != nil {
				respondBotAPIError(c, delegateErr)
				return
			}

			// Store in cache (best-effort; don't fail if Redis is down)
			if cache != nil && statsTTL > 0 {
				_ = cache.SetCache(cacheKey, result, statsTTL)
			}

			c.JSON(http.StatusOK, result)
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
			requestClient := getRequestBotAPIClient(c, apiClient)
			result, err := requestClient.GetBotJobs(instanceID, days)
			if err != nil {
				respondBotAPIError(c, err)
				return
			}
			c.JSON(http.StatusOK, normalizeBotJobsPayload(result))
		})

		// Quick deploy bot
		botGroup.POST("/quick-deploy", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			instanceName := c.Query("instance_name")
			autoStart := c.DefaultQuery("auto_start", "true") == "true"

			var config map[string]interface{}
			if err := c.ShouldBindJSON(&config); err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body", "message": err.Error()})
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
			result, err := requestClient.SystemStatus()
			if err != nil {
				return nil, err
			}
			return ensureBotDBSyncDiagnostics(result), nil
		})
	})

	// Frontend and backend websocket compatibility endpoints.
	// Keep these on the backend origin and proxy upstream to the bot API channels.
	wsGroup := router.Group("/ws")
	wsGroup.Use(middleware.RequireAuth())
	wsGroup.Use(withRequestScopedBotClient)
	{
		wsGroup.GET("/strategies", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			proxyWebSocket(c, requestClient, "/ws/strategies")
		})

		wsGroup.GET("/backtests/:run_id", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			runID := c.Param("run_id")
			if !ensureBacktestRunAccess(c, runID, backtestRepo) {
				return
			}
			upstreamEndpoint := fmt.Sprintf("/ws/backtests/%s", runID)
			proxyWebSocket(c, requestClient, upstreamEndpoint)
		})

		wsGroup.GET("/bots/:instance_id", func(c *gin.Context) {
			requestClient := getRequestBotAPIClient(c, apiClient)
			instanceID := c.Param("instance_id")
			upstreamEndpoint := fmt.Sprintf("/ws/bots/%s", instanceID)
			proxyWebSocket(c, requestClient, upstreamEndpoint)
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

func parseBacktestListOffset(c *gin.Context) int {
	offset := 0
	if skip := c.Query("skip"); skip != "" {
		var i int
		if _, err := parseIntQuery(skip, &i); err == nil && i >= 0 {
			offset = i
		}
	}
	if rawOffset := c.Query("offset"); rawOffset != "" {
		var i int
		if _, err := parseIntQuery(rawOffset, &i); err == nil && i >= 0 {
			offset = i
		}
	}
	return offset
}

func normalizeRealtimeBotInstanceID(instanceID string) (string, error) {
	trimmed := strings.TrimSpace(instanceID)
	if trimmed == "" {
		return "", fmt.Errorf("instance_id is required")
	}
	return trimmed, nil
}
