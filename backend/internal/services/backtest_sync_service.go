package services

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

type BacktestSyncService struct {
	repo *repository.BacktestSyncRepository
}

func (s *BacktestSyncService) DB() *sql.DB {
	if s == nil || s.repo == nil {
		return nil
	}
	return s.repo.DB()
}

func (s *BacktestSyncService) GetSyncHealthByRun(userID int, runID string, limit int) ([]repository.BacktestSyncHealth, error) {
	if s == nil || s.repo == nil {
		return []repository.BacktestSyncHealth{}, nil
	}
	return s.repo.GetSyncHealthByRun(userID, runID, limit)
}

func NewBacktestSyncService(repo *repository.BacktestSyncRepository) *BacktestSyncService {
	return &BacktestSyncService{repo: repo}
}

func (s *BacktestSyncService) SyncBacktestRun(userID int, upstream map[string]interface{}) error {
	if s == nil || s.repo == nil {
		return nil
	}
	if userID <= 0 {
		return fmt.Errorf("invalid user id")
	}
	if upstream == nil {
		return nil
	}

	payload := extractRunPayload(upstream)
	runID := getString(payload, "run_id", "id")
	if runID == "" {
		return nil
	}

	startDate := getString(payload, "start_date")
	endDate := getString(payload, "end_date")
	if startDate == "" {
		startDate = time.Now().UTC().Format("2006-01-02")
	}
	if endDate == "" {
		endDate = startDate
	}

	numPairs := getInt(payload, "num_pairs", "max_pairs")
	totalMarkets := getInt(payload, "total_markets")
	resolution := getString(payload, "resolution", "candle_resolution")

	config := sql.NullString{}
	if cfgRaw, ok := payload["config"]; ok {
		if cfgBytes, err := json.Marshal(cfgRaw); err == nil {
			cfgString := strings.TrimSpace(string(cfgBytes))
			if cfgString != "" && cfgString != "null" {
				config = sql.NullString{String: cfgString, Valid: true}
			}
		}
	}
	strategyID := nullableIntField(payload, "strategy_id")
	if !strategyID.Valid {
		if cfg := asMap(payload["config"]); cfg != nil {
			strategyID = nullableIntField(cfg, "strategy_id")
		}
	}

	syncPayload := repository.BacktestRunSyncPayload{
		RunID:           runID,
		UserID:          userID,
		Status:          normalizeBacktestStatus(getString(payload, "status"), payload),
		StartDate:       startDate,
		EndDate:         endDate,
		NumPairs:        numPairs,
		TotalMarkets:    totalMarkets,
		Resolution:      nullableString(resolution),
		Config:          config,
		StrategyID:      strategyID,
		StartedAt:       parseTimePtr(payload, "started_at"),
		CompletedAt:     parseTimePtr(payload, "completed_at"),
		DurationSeconds: parseFloatPtr(payload, "duration_seconds"),
		ErrorMessage:    nullableString(getString(payload, "error_message", "error")),
		TotalTrades:     nullableIntField(payload, "total_trades"),
		WinningTrades:   nullableIntField(payload, "profitable_trades", "winning_trades"),
		LosingTrades:    nullableIntField(payload, "losing_trades"),
		WinRate:         nullableFloatField(payload, "win_rate"),
		TotalPnL:        nullableFloatField(payload, "total_pnl"),
		TotalPnLUSD:     nullableFloatField(payload, "total_pnl_usd", "total_pnl"),
		SharpeRatio:     nullableFloatField(payload, "sharpe_ratio"),
		MaxDrawdown:     nullableFloatField(payload, "max_drawdown", "max_drawdown_pct"),
	}

	return s.repo.UpsertBacktestRun(syncPayload)
}

func normalizeBacktestStatus(status string, payload map[string]interface{}) string {
	normalized := strings.ToLower(strings.TrimSpace(status))
	switch normalized {
	case "", "<nil>":
		normalized = "pending"
	case "created", "queued", "scheduled", "retry":
		normalized = "pending"
	case "in_progress", "processing", "active", "retrying":
		normalized = "running"
	case "succeeded", "success", "done":
		normalized = "completed"
	case "error":
		normalized = "failed"
	case "timed_out":
		normalized = "timeout"
	case "stalled":
		normalized = "stale"
	case "canceled":
		normalized = "cancelled"
	}

	progress := parseFloatField(payload, "progress_pct", "progress_percent", "progress")
	hasMetrics := getInt(payload, "total_trades") > 0
	for _, key := range []string{"total_pnl", "win_rate", "sharpe_ratio", "profit_factor"} {
		if parseFloatField(payload, key) != 0 {
			hasMetrics = true
			break
		}
	}
	errorMessage := getString(payload, "error_message", "error")
	currentTask := strings.ToLower(getString(payload, "current_task"))
	currentPair := strings.ToLower(getString(payload, "current_pair"))
	if normalized == "pending" {
		switch {
		case getBool(payload, "cancel_requested") || strings.Contains(currentTask, "cancel"):
			normalized = "cancelled"
		case errorMessage != "":
			normalized = "failed"
		case progress >= 100 || currentTask == "complete" || currentPair == "complete":
			normalized = "completed"
		case progress > 0 || hasMetrics ||
			(currentTask != "" && currentTask != "pending" && currentTask != "queued") ||
			(currentPair != "" && currentPair != "pending" && currentPair != "queued"):
			normalized = "running"
		}
	}
	return normalized
}

func (s *BacktestSyncService) SyncBacktestTrades(runID string, upstream map[string]interface{}) error {
	if s == nil || s.repo == nil || strings.TrimSpace(runID) == "" {
		return nil
	}
	items := extractItems(upstream, "trades")
	if len(items) == 0 {
		return nil
	}

	trades := make([]repository.BacktestTradeSyncPayload, 0, len(items))
	for _, item := range items {
		tradeID := getString(item, "trade_id", "id")
		if strings.TrimSpace(tradeID) == "" {
			continue
		}
		entryTS := parseTimePtr(item, "entry_timestamp")
		trades = append(trades, repository.BacktestTradeSyncPayload{
			TradeID:        tradeID,
			Market1:        getString(item, "market_1", "market1"),
			Market2:        getString(item, "market_2", "market2"),
			EntryTimestamp: entryTS,
			EntryPrice1:    parseFloatField(item, "entry_price_1", "entry_price_m1"),
			EntryPrice2:    parseFloatField(item, "entry_price_2", "entry_price_m2"),
			EntryZScore:    parseFloatField(item, "entry_z_score", "entry_zscore"),
			Side1:          getString(item, "side_1"),
			Side2:          getString(item, "side_2"),
			Size1:          parseFloatField(item, "size_1"),
			Size2:          parseFloatField(item, "size_2"),
			ExitTimestamp:  parseTimePtr(item, "exit_timestamp"),
			ExitPrice1:     parseFloatPtr(item, "exit_price_1", "exit_price_m1"),
			ExitPrice2:     parseFloatPtr(item, "exit_price_2", "exit_price_m2"),
			ExitZScore:     parseFloatPtr(item, "exit_z_score", "exit_zscore"),
			PnL:            parseFloatPtr(item, "pnl", "pnl_usd"),
			PnLPct:         parseFloatPtr(item, "pnl_pct"),
			DurationHours:  parseFloatPtr(item, "duration_hours"),
			HedgeRatio:     parseFloatField(item, "hedge_ratio"),
			TransactionFee: parseFloatField(item, "transaction_fee"),
			Slippage:       parseFloatField(item, "slippage"),
		})
	}

	return s.repo.UpsertBacktestTrades(runID, trades)
}

func (s *BacktestSyncService) SyncBacktestPositions(runID string, upstream map[string]interface{}) error {
	if s == nil || s.repo == nil || strings.TrimSpace(runID) == "" {
		return nil
	}
	items := extractItems(upstream, "positions", "position_snapshots")
	if len(items) == 0 {
		return nil
	}

	positions := make([]repository.BacktestPositionSyncPayload, 0, len(items))
	for _, item := range items {
		positionID := getString(item, "position_id", "id")
		if strings.TrimSpace(positionID) == "" {
			continue
		}
		positions = append(positions, repository.BacktestPositionSyncPayload{
			PositionID:     positionID,
			Market1:        getString(item, "market_1", "market1"),
			Market2:        getString(item, "market_2", "market2"),
			Status:         getString(item, "status"),
			EntryTimestamp: parseTimePtr(item, "entry_timestamp"),
			CloseTimestamp: parseTimePtr(item, "close_timestamp", "exit_timestamp"),
			EntryPrice1:    parseFloatField(item, "entry_price_1", "entry_price_m1"),
			EntryPrice2:    parseFloatField(item, "entry_price_2", "entry_price_m2"),
			EntryZScore:    parseFloatField(item, "entry_z_score", "entry_zscore"),
			CurrentPrice1:  parseFloatPtr(item, "current_price_1"),
			CurrentPrice2:  parseFloatPtr(item, "current_price_2"),
			CurrentZScore:  parseFloatPtr(item, "current_z_score"),
			Size1:          parseFloatField(item, "size_1"),
			Size2:          parseFloatField(item, "size_2"),
			Side1:          getString(item, "side_1"),
			Side2:          getString(item, "side_2"),
			HedgeRatio:     parseFloatField(item, "hedge_ratio"),
			UnrealizedPnL:  parseFloatPtr(item, "unrealized_pnl"),
			RealizedPnL:    parseFloatPtr(item, "realized_pnl"),
		})
	}

	return s.repo.UpsertBacktestPositions(runID, positions)
}

func (s *BacktestSyncService) SyncBacktestCandles(runID string, upstream map[string]interface{}) error {
	if s == nil || s.repo == nil || strings.TrimSpace(runID) == "" {
		return nil
	}
	items := extractItems(upstream, "candles")
	if len(items) == 0 {
		return nil
	}

	candles := make([]repository.BacktestCandleSyncPayload, 0, len(items))
	for _, item := range items {
		ts := parseTimePtr(item, "timestamp")
		if ts == nil {
			continue
		}
		candles = append(candles, repository.BacktestCandleSyncPayload{
			Market:      getString(item, "market"),
			Timestamp:   ts,
			Resolution:  getString(item, "resolution"),
			OpenPrice:   parseFloatField(item, "open", "open_price"),
			HighPrice:   parseFloatField(item, "high", "high_price"),
			LowPrice:    parseFloatField(item, "low", "low_price"),
			ClosePrice:  parseFloatField(item, "close", "close_price"),
			Volume:      parseFloatField(item, "volume"),
			TradesCount: parseIntPtr(item, "trades_count"),
		})
	}

	return s.repo.UpsertBacktestCandles(runID, candles)
}

func extractRunPayload(root map[string]interface{}) map[string]interface{} {
	if data, ok := root["data"].(map[string]interface{}); ok {
		return data
	}
	return root
}

func asMap(value interface{}) map[string]interface{} {
	if mapped, ok := value.(map[string]interface{}); ok {
		return mapped
	}
	return nil
}

func getString(source map[string]interface{}, keys ...string) string {
	for _, k := range keys {
		v, ok := source[k]
		if !ok || v == nil {
			continue
		}
		switch typed := v.(type) {
		case string:
			trimmed := strings.TrimSpace(typed)
			if trimmed != "" {
				return trimmed
			}
		default:
			asText := strings.TrimSpace(fmt.Sprintf("%v", typed))
			if asText != "" && asText != "<nil>" {
				return asText
			}
		}
	}
	return ""
}

func getInt(source map[string]interface{}, keys ...string) int {
	for _, k := range keys {
		v, ok := source[k]
		if !ok || v == nil {
			continue
		}
		switch typed := v.(type) {
		case int:
			return typed
		case int32:
			return int(typed)
		case int64:
			return int(typed)
		case float64:
			return int(typed)
		case float32:
			return int(typed)
		case string:
			if parsed, err := strconv.Atoi(strings.TrimSpace(typed)); err == nil {
				return parsed
			}
		}
	}
	return 0
}

func getBool(source map[string]interface{}, keys ...string) bool {
	for _, k := range keys {
		v, ok := source[k]
		if !ok || v == nil {
			continue
		}
		switch typed := v.(type) {
		case bool:
			return typed
		case string:
			return strings.EqualFold(strings.TrimSpace(typed), "true")
		}
	}
	return false
}

func parseFloatField(source map[string]interface{}, keys ...string) float64 {
	for _, k := range keys {
		v, ok := source[k]
		if !ok || v == nil {
			continue
		}
		switch typed := v.(type) {
		case float64:
			return typed
		case float32:
			return float64(typed)
		case int:
			return float64(typed)
		case int64:
			return float64(typed)
		case string:
			if parsed, err := strconv.ParseFloat(strings.TrimSpace(typed), 64); err == nil {
				return parsed
			}
		}
	}
	return 0
}

func parseFloatPtr(source map[string]interface{}, keys ...string) *float64 {
	for _, k := range keys {
		if _, ok := source[k]; !ok {
			continue
		}
		value := parseFloatField(source, k)
		return &value
	}
	return nil
}

func parseIntPtr(source map[string]interface{}, keys ...string) *int {
	for _, k := range keys {
		v, ok := source[k]
		if !ok || v == nil {
			continue
		}
		switch typed := v.(type) {
		case int:
			return &typed
		case int32:
			v := int(typed)
			return &v
		case int64:
			v := int(typed)
			return &v
		case float64:
			v := int(typed)
			return &v
		case string:
			if parsed, err := strconv.Atoi(strings.TrimSpace(typed)); err == nil {
				return &parsed
			}
		}
	}
	return nil
}

func extractItems(root map[string]interface{}, keys ...string) []map[string]interface{} {
	if root == nil {
		return nil
	}
	queue := []map[string]interface{}{root}
	visited := 0
	for len(queue) > 0 && visited < 32 {
		current := queue[0]
		queue = queue[1:]
		visited++

		for _, key := range keys {
			raw, ok := current[key]
			if !ok || raw == nil {
				continue
			}
			arr, ok := raw.([]interface{})
			if !ok {
				continue
			}
			result := make([]map[string]interface{}, 0, len(arr))
			for _, item := range arr {
				if mapped, ok := item.(map[string]interface{}); ok {
					result = append(result, mapped)
				}
			}
			if len(result) > 0 {
				return result
			}
		}

		for _, value := range current {
			if nested, ok := value.(map[string]interface{}); ok {
				queue = append(queue, nested)
			}
		}
	}

	return nil
}

func parseTimePtr(source map[string]interface{}, keys ...string) *time.Time {
	for _, k := range keys {
		value := getString(source, k)
		if value == "" {
			continue
		}
		if parsed, err := time.Parse(time.RFC3339, value); err == nil {
			parsed = parsed.UTC()
			return &parsed
		}
	}
	return nil
}

func nullableString(value string) sql.NullString {
	value = strings.TrimSpace(value)
	if value == "" {
		return sql.NullString{}
	}
	return sql.NullString{String: value, Valid: true}
}

func nullableIntField(source map[string]interface{}, keys ...string) sql.NullInt64 {
	for _, k := range keys {
		v, ok := source[k]
		if !ok || v == nil {
			continue
		}
		return sql.NullInt64{Int64: int64(getInt(source, k)), Valid: true}
	}
	return sql.NullInt64{}
}

func nullableFloatField(source map[string]interface{}, keys ...string) sql.NullFloat64 {
	for _, k := range keys {
		v, ok := source[k]
		if !ok || v == nil {
			continue
		}
		return sql.NullFloat64{Float64: parseFloatField(source, k), Valid: true}
	}
	return sql.NullFloat64{}
}
