package models

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"
)

// ============ BacktestStrategy Methods ============

// ToDict converts BacktestStrategy to dictionary
func (b *BacktestStrategy) ToDict() map[string]interface{} {
	return map[string]interface{}{
		"id":                       b.ID,
		"user_id":                  b.UserID,
		"name":                     b.Name,
		"description":              b.Description,
		"category":                 b.Category,
		"is_public":                b.IsPublic,
		"is_default":               b.IsDefault,
		"runtime_strategy":         b.RuntimeStrategy,
		"runtime_network":          b.RuntimeNetwork,
		"runtime_subaccount":       b.RuntimeSubaccount,
		"pair_selection_mode":      b.PairSelectionMode,
		"selected_markets":         b.SelectedMarketList(),
		"zscore_threshold":         b.ZscoreThreshold,
		"stats_window":             b.StatsWindow,
		"max_half_life":            b.MaxHalfLife,
		"usd_per_trade":            b.UsdPerTrade,
		"usd_min_collateral":       b.UsdMinCollateral,
		"close_at_zscore_cross":    b.CloseAtZscoreCross,
		"find_cointegrated_pairs":  b.FindCointegratedPairs,
		"manage_exits":             b.ManageExits,
		"place_trades":             b.PlaceTrades,
		"abort_all_positions":      b.AbortAllPositions,
		"max_positions":            b.MaxPositions,
		"max_drawdown_pct":         b.MaxDrawdownPct,
		"stop_loss_pct":            b.StopLossPct,
		"take_profit_pct":          b.TakeProfitPct,
		"trailing_stop_pct":        b.TrailingStopPct,
		"rebalance_interval_hours": b.RebalanceIntervalHours,
		"position_timeout_hours":   b.PositionTimeoutHours,
		"transaction_fee":          b.TransactionFee,
		"slippage":                 b.Slippage,
		"starting_balance":         b.StartingBalance,
		"resolution":               b.CandleResolution,
		"candle_resolution":        b.CandleResolution,
		"max_history_days":         b.MaxHistoryDays,
		"benchmark_symbol":         b.BenchmarkSymbol,
		"risk_free_rate":           b.RiskFreeRate,
		"initial_amount":           b.InitialAmount,
		"usage_count":              b.UsageCount,
		"last_used_at":             b.LastUsedAt,
		"deleted_at":               b.DeletedAt,
		"created_at":               b.CreatedAt,
		"updated_at":               b.UpdatedAt,
	}
}

// SelectedMarketList returns the persisted dYdX market universe for this strategy.
func (b *BacktestStrategy) SelectedMarketList() []string {
	raw := strings.TrimSpace(b.SelectedMarkets)
	if raw == "" {
		return []string{}
	}
	var markets []string
	if err := json.Unmarshal([]byte(raw), &markets); err != nil {
		return []string{}
	}
	return normalizeSelectedMarkets(markets)
}

// SetSelectedMarketList stores a normalized market list as JSON.
func (b *BacktestStrategy) SetSelectedMarketList(markets []string) {
	normalized := normalizeSelectedMarkets(markets)
	raw, err := json.Marshal(normalized)
	if err != nil {
		b.SelectedMarkets = "[]"
		return
	}
	b.SelectedMarkets = string(raw)
}

func normalizeSelectedMarkets(markets []string) []string {
	seen := map[string]bool{}
	normalized := make([]string, 0, len(markets))
	for _, market := range markets {
		cleaned := strings.TrimSpace(market)
		if cleaned == "" || seen[cleaned] {
			continue
		}
		seen[cleaned] = true
		normalized = append(normalized, cleaned)
	}
	return normalized
}

// FromDict populates BacktestStrategy from a dictionary
func (b *BacktestStrategy) FromDict(data map[string]interface{}) {
	if id, ok := data["id"].(float64); ok {
		b.ID = int(id)
	}
	if userID, ok := data["user_id"].(float64); ok {
		b.UserID = int(userID)
	}
	if name, ok := data["name"].(string); ok {
		b.Name = name
	}
	if description, ok := data["description"].(string); ok {
		b.Description = description
	}
	if category, ok := data["category"].(string); ok {
		b.Category = category
	}
	if isPublic, ok := data["is_public"].(bool); ok {
		b.IsPublic = isPublic
	}
	if isDefault, ok := data["is_default"].(bool); ok {
		b.IsDefault = isDefault
	}
	if runtimeStrategy, ok := data["runtime_strategy"].(string); ok {
		b.RuntimeStrategy = runtimeStrategy
	}
	if runtimeNetwork, ok := data["runtime_network"].(string); ok {
		b.RuntimeNetwork = runtimeNetwork
	}
	if runtimeSubaccount, ok := data["runtime_subaccount"].(float64); ok {
		b.RuntimeSubaccount = int(runtimeSubaccount)
	}
	if pairSelectionMode, ok := data["pair_selection_mode"].(string); ok {
		b.PairSelectionMode = pairSelectionMode
	}
	if selectedMarkets, ok := data["selected_markets"].([]interface{}); ok {
		markets := make([]string, 0, len(selectedMarkets))
		for _, market := range selectedMarkets {
			markets = append(markets, strings.TrimSpace(strings.Trim(fmt.Sprintf("%v", market), "\"")))
		}
		b.SetSelectedMarketList(markets)
	} else if selectedMarkets, ok := data["selected_markets"].([]string); ok {
		b.SetSelectedMarketList(selectedMarkets)
	}
	if zscore, ok := data["zscore_threshold"].(float64); ok {
		b.ZscoreThreshold = zscore
	}
	if statsWindow, ok := data["stats_window"].(float64); ok {
		b.StatsWindow = int(statsWindow)
	}
	if maxHalfLife, ok := data["max_half_life"].(float64); ok {
		b.MaxHalfLife = maxHalfLife
	}
	if usdPerTrade, ok := data["usd_per_trade"].(float64); ok {
		b.UsdPerTrade = usdPerTrade
	}
	if usdMinCollateral, ok := data["usd_min_collateral"].(float64); ok {
		b.UsdMinCollateral = usdMinCollateral
	}
	if closeAtZscoreCross, ok := data["close_at_zscore_cross"].(bool); ok {
		b.CloseAtZscoreCross = closeAtZscoreCross
	}
	if findCointegratedPairs, ok := data["find_cointegrated_pairs"].(bool); ok {
		b.FindCointegratedPairs = findCointegratedPairs
	}
	if manageExits, ok := data["manage_exits"].(bool); ok {
		b.ManageExits = manageExits
	}
	if placeTrades, ok := data["place_trades"].(bool); ok {
		b.PlaceTrades = placeTrades
	}
	if abortAllPositions, ok := data["abort_all_positions"].(bool); ok {
		b.AbortAllPositions = abortAllPositions
	}
	if maxPositions, ok := data["max_positions"].(float64); ok {
		b.MaxPositions = int(maxPositions)
	}
	if maxDrawdownPct, ok := data["max_drawdown_pct"].(float64); ok {
		b.MaxDrawdownPct = maxDrawdownPct
	}
	if stopLossPct, ok := data["stop_loss_pct"].(float64); ok {
		b.StopLossPct = stopLossPct
	}
	if takeProfitPct, ok := data["take_profit_pct"].(float64); ok {
		b.TakeProfitPct = takeProfitPct
	}
	if trailingStopPct, ok := data["trailing_stop_pct"].(float64); ok {
		b.TrailingStopPct = trailingStopPct
	}
	if rebalanceIntervalHours, ok := data["rebalance_interval_hours"].(float64); ok {
		b.RebalanceIntervalHours = int(rebalanceIntervalHours)
	}
	if positionTimeoutHours, ok := data["position_timeout_hours"].(float64); ok {
		b.PositionTimeoutHours = int(positionTimeoutHours)
	}
	if transactionFee, ok := data["transaction_fee"].(float64); ok {
		b.TransactionFee = transactionFee
	}
	if slippage, ok := data["slippage"].(float64); ok {
		b.Slippage = slippage
	}
	if startingBalance, ok := data["starting_balance"].(float64); ok {
		b.StartingBalance = startingBalance
	}
	if resolution, ok := data["resolution"].(string); ok {
		b.CandleResolution = resolution
	}
	if candleResolution, ok := data["candle_resolution"].(string); ok {
		b.CandleResolution = candleResolution
	}
	if maxHistoryDays, ok := data["max_history_days"].(float64); ok {
		b.MaxHistoryDays = int(maxHistoryDays)
	}
	if benchmarkSymbol, ok := data["benchmark_symbol"].(string); ok {
		b.BenchmarkSymbol = benchmarkSymbol
	}
	if riskFreeRate, ok := data["risk_free_rate"].(float64); ok {
		b.RiskFreeRate = riskFreeRate
	}
	if initialAmount, ok := data["initial_amount"].(float64); ok {
		b.InitialAmount = initialAmount
	}
	if usageCount, ok := data["usage_count"].(float64); ok {
		b.UsageCount = int(usageCount)
	}
	if lastUsedAt, ok := data["last_used_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, lastUsedAt); err == nil {
			b.LastUsedAt = &t
		}
	}
	if deletedAt, ok := data["deleted_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, deletedAt); err == nil {
			b.DeletedAt = &t
		}
	}
	if createdAt, ok := data["created_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, createdAt); err == nil {
			b.CreatedAt = t
		}
	}
	if updatedAt, ok := data["updated_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, updatedAt); err == nil {
			b.UpdatedAt = t
		}
	}
}

// ToJSON converts BacktestStrategy to JSON
func (b *BacktestStrategy) ToJSON() ([]byte, error) {
	return json.Marshal(b.ToDict())
}

// FromJSON populates BacktestStrategy from JSON
func (b *BacktestStrategy) FromJSON(data []byte) error {
	var dict map[string]interface{}
	if err := json.Unmarshal(data, &dict); err != nil {
		return err
	}
	b.FromDict(dict)
	return nil
}

// ============ StrategyVersionHistory Methods ============

// ToDict converts StrategyVersionHistory to dictionary
func (s *StrategyVersionHistory) ToDict() map[string]interface{} {
	return map[string]interface{}{
		"id":                 s.ID,
		"strategy_id":        s.StrategyID,
		"created_by_user_id": s.CreatedByUserID,
		"version_number":     s.Version,
		"version":            s.Version,
		"config_snapshot":    s.StrategyData,
		"strategy_data":      s.StrategyData,
		"change_description": s.ChangeLog,
		"change_log":         s.ChangeLog,
		"created_at":         s.CreatedAt,
	}
}

// FromDict populates StrategyVersionHistory from a dictionary
func (s *StrategyVersionHistory) FromDict(data map[string]interface{}) {
	if id, ok := data["id"].(float64); ok {
		s.ID = int(id)
	}
	if strategyID, ok := data["strategy_id"].(float64); ok {
		s.StrategyID = int(strategyID)
	}
	if createdByUserID, ok := data["created_by_user_id"].(float64); ok {
		s.CreatedByUserID = int(createdByUserID)
	}
	if versionNumber, ok := data["version_number"].(float64); ok {
		s.Version = int(versionNumber)
	} else if version, ok := data["version"].(float64); ok {
		s.Version = int(version)
	}
	if configSnapshot, ok := data["config_snapshot"].(string); ok {
		s.StrategyData = nullString(configSnapshot)
	} else if strategyData, ok := data["strategy_data"].(string); ok {
		s.StrategyData = nullString(strategyData)
	}
	if changeDescription, ok := data["change_description"].(string); ok {
		s.ChangeLog = changeDescription
	} else if changeLog, ok := data["change_log"].(string); ok {
		s.ChangeLog = changeLog
	}
	if createdAt, ok := data["created_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, createdAt); err == nil {
			s.CreatedAt = t
		}
	}
}

// ToJSON converts StrategyVersionHistory to JSON
func (s *StrategyVersionHistory) ToJSON() ([]byte, error) {
	return json.Marshal(s.ToDict())
}

// FromJSON populates StrategyVersionHistory from JSON
func (s *StrategyVersionHistory) FromJSON(data []byte) error {
	var dict map[string]interface{}
	if err := json.Unmarshal(data, &dict); err != nil {
		return err
	}
	s.FromDict(dict)
	return nil
}

func nullString(value string) sql.NullString {
	return sql.NullString{
		String: value,
		Valid:  value != "",
	}
}

// ============ StrategyExecutionState Methods ============

// ToDict converts StrategyExecutionState to dictionary
func (s *StrategyExecutionState) ToDict() map[string]interface{} {
	return map[string]interface{}{
		"id":          s.ID,
		"strategy_id": s.StrategyID,
		"is_running":  s.IsRunning,
		"last_run_at": s.LastRunAt,
		"next_run_at": s.NextRunAt,
		"state":       s.State,
		"created_at":  s.CreatedAt,
		"updated_at":  s.UpdatedAt,
	}
}

// FromDict populates StrategyExecutionState from a dictionary
func (s *StrategyExecutionState) FromDict(data map[string]interface{}) {
	if id, ok := data["id"].(float64); ok {
		s.ID = int(id)
	}
	if strategyID, ok := data["strategy_id"].(float64); ok {
		s.StrategyID = int(strategyID)
	}
	if isRunning, ok := data["is_running"].(bool); ok {
		s.IsRunning = isRunning
	}
	if lastRunAt, ok := data["last_run_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, lastRunAt); err == nil {
			s.LastRunAt = &t
		}
	}
	if nextRunAt, ok := data["next_run_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, nextRunAt); err == nil {
			s.NextRunAt = &t
		}
	}
	if createdAt, ok := data["created_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, createdAt); err == nil {
			s.CreatedAt = t
		}
	}
	if updatedAt, ok := data["updated_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, updatedAt); err == nil {
			s.UpdatedAt = t
		}
	}
}

// ToJSON converts StrategyExecutionState to JSON
func (s *StrategyExecutionState) ToJSON() ([]byte, error) {
	return json.Marshal(s.ToDict())
}

// FromJSON populates StrategyExecutionState from JSON
func (s *StrategyExecutionState) FromJSON(data []byte) error {
	var dict map[string]interface{}
	if err := json.Unmarshal(data, &dict); err != nil {
		return err
	}
	s.FromDict(dict)
	return nil
}
