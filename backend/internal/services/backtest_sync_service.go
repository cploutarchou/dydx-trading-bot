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

	syncPayload := repository.BacktestRunSyncPayload{
		RunID:           runID,
		UserID:          userID,
		Status:          getString(payload, "status"),
		StartDate:       startDate,
		EndDate:         endDate,
		NumPairs:        numPairs,
		TotalMarkets:    totalMarkets,
		Resolution:      nullableString(resolution),
		Config:          config,
		StartedAt:       parseTimePtr(payload, "started_at"),
		CompletedAt:     parseTimePtr(payload, "completed_at"),
		DurationSeconds: parseFloatPtr(payload, "duration_seconds"),
		ErrorMessage:    nullableString(getString(payload, "error_message", "error")),
		TotalTrades:     nullableInt(getInt(payload, "total_trades")),
		WinningTrades:   nullableInt(getInt(payload, "profitable_trades", "winning_trades")),
		LosingTrades:    nullableInt(getInt(payload, "losing_trades")),
		WinRate:         nullableFloat(parseFloatField(payload, "win_rate")),
		TotalPnL:        nullableFloat(parseFloatField(payload, "total_pnl")),
		TotalPnLUSD:     nullableFloat(parseFloatField(payload, "total_pnl_usd")),
	}

	if syncPayload.Status == "" {
		syncPayload.Status = "queued"
	}

	return s.repo.UpsertBacktestRun(syncPayload)
}

func extractRunPayload(root map[string]interface{}) map[string]interface{} {
	if data, ok := root["data"].(map[string]interface{}); ok {
		return data
	}
	return root
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

func nullableInt(value int) sql.NullInt64 {
	if value == 0 {
		return sql.NullInt64{}
	}
	return sql.NullInt64{Int64: int64(value), Valid: true}
}

func nullableFloat(value float64) sql.NullFloat64 {
	if value == 0 {
		return sql.NullFloat64{}
	}
	return sql.NullFloat64{Float64: value, Valid: true}
}
