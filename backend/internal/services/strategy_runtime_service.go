package services

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

type StrategyRuntimeState struct {
	InstanceID   string     `json:"instance_id,omitempty"`
	Network      string     `json:"network,omitempty"`
	Status       string     `json:"status,omitempty"`
	BotStatus    string     `json:"bot_status,omitempty"`
	LastError    string     `json:"last_error,omitempty"`
	ProcessID    *int       `json:"process_id,omitempty"`
	StartedAt    *time.Time `json:"started_at,omitempty"`
	StoppedAt    *time.Time `json:"stopped_at,omitempty"`
	LastSyncedAt *time.Time `json:"last_synced_at,omitempty"`
}

type StrategyRuntimeService struct {
	strategyService *StrategyService
	keyService      *KeyManagementService
	telegramService *TelegramService
	botService      *BotInstanceService
	botRepo         *repository.BotInstanceRepository
}

func NewStrategyRuntimeService(
	strategyService *StrategyService,
	keyService *KeyManagementService,
	telegramService *TelegramService,
	botService *BotInstanceService,
	botRepo *repository.BotInstanceRepository,
) *StrategyRuntimeService {
	return &StrategyRuntimeService{
		strategyService: strategyService,
		keyService:      keyService,
		telegramService: telegramService,
		botService:      botService,
		botRepo:         botRepo,
	}
}

func (s *StrategyRuntimeService) WithAuthToken(token string) *StrategyRuntimeService {
	if s == nil {
		return nil
	}

	return &StrategyRuntimeService{
		strategyService: s.strategyService,
		keyService:      s.keyService,
		telegramService: s.telegramService,
		botService:      s.botService.WithAuthToken(token),
		botRepo:         s.botRepo,
	}
}

func (s *StrategyRuntimeService) WithTraceID(traceID string) *StrategyRuntimeService {
	if s == nil {
		return nil
	}

	return &StrategyRuntimeService{
		strategyService: s.strategyService,
		keyService:      s.keyService,
		telegramService: s.telegramService,
		botService:      s.botService.WithTraceID(traceID),
		botRepo:         s.botRepo,
	}
}

func (s *StrategyRuntimeService) GetRuntimeStatus(strategy *models.BacktestStrategy) (map[string]interface{}, error) {
	executionState, err := s.getOrCreateExecutionState(strategy.ID)
	if err != nil {
		return nil, err
	}

	runtimeState := decodeStrategyRuntimeState(executionState.State)
	if strings.TrimSpace(runtimeState.InstanceID) == "" {
		runtimeState.InstanceID = strategyRuntimeInstanceID(strategy)
	}

	runtimeState, isRunning, err := s.reconcileRuntimeState(strategy, executionState, runtimeState)
	if err != nil {
		return nil, err
	}

	return buildStrategyRuntimeResponse(strategy, executionState, runtimeState, isRunning), nil
}

func (s *StrategyRuntimeService) StartRuntime(strategy *models.BacktestStrategy, requestedNetwork string) (map[string]interface{}, error) {
	executionState, err := s.getOrCreateExecutionState(strategy.ID)
	if err != nil {
		return nil, err
	}

	runtimeState := decodeStrategyRuntimeState(executionState.State)
	if strings.TrimSpace(runtimeState.InstanceID) == "" {
		runtimeState.InstanceID = strategyRuntimeInstanceID(strategy)
	}

	runtimeState, isRunning, err := s.reconcileRuntimeState(strategy, executionState, runtimeState)
	if err != nil {
		return nil, err
	}
	if isRunning {
		return buildStrategyRuntimeResponse(strategy, executionState, runtimeState, true), nil
	}

	networkHint := strings.TrimSpace(requestedNetwork)
	if networkHint == "" {
		networkHint = strings.TrimSpace(runtimeState.Network)
	}

	runtimeKey, err := s.resolveRuntimeKey(strategy.UserID, networkHint)
	if err != nil {
		return nil, err
	}
	runtimeState.Network = runtimeKey.Network

	instanceRecord, existsLocally, err := s.ensureRuntimeInstance(strategy, runtimeState.InstanceID, runtimeKey)
	if err != nil {
		return nil, err
	}

	remoteStatus, remoteExists, err := s.fetchRemoteRuntimeStatus(runtimeState.InstanceID)
	if err != nil {
		return nil, err
	}
	if !existsLocally && remoteExists && instanceRecord != nil {
		if createErr := s.botService.CreateBotInstance(instanceRecord); createErr != nil {
			return nil, fmt.Errorf("failed to persist runtime instance metadata: %w", createErr)
		}
	}
	if !remoteExists {
		createPayload := s.buildBotCreatePayload(strategy, runtimeState.InstanceID, runtimeKey)
		if instanceRecord == nil {
			instanceRecord = s.buildBotInstanceRecord(strategy, runtimeState.InstanceID, runtimeKey)
		}
		if existsLocally {
			if _, createErr := s.botService.GetRemoteBotInstance(runtimeState.InstanceID); createErr != nil {
				if _, ok := createErr.(*BotAPIError); ok {
					if createRemoteErr := s.botService.CreateBotInstanceWithConfig(instanceRecord, createPayload); createRemoteErr != nil {
						return nil, fmt.Errorf("failed to create runtime instance: %w", createRemoteErr)
					}
				}
			}
		} else {
			if createErr := s.botService.CreateBotInstanceWithConfig(instanceRecord, createPayload); createErr != nil {
				return nil, fmt.Errorf("failed to create runtime instance: %w", createErr)
			}
		}
		remoteStatus = nil
	}

	if !isBotStatusRunning(remoteStatus) {
		if err := s.botService.StartBotInstance(runtimeState.InstanceID); err != nil {
			runtimeState.Status = "error"
			runtimeState.BotStatus = "error"
			runtimeState.LastError = err.Error()
			if persistErr := s.persistRuntimeState(executionState, runtimeState, false); persistErr != nil {
				log.Printf("⚠️ failed to persist strategy runtime error state strategy_id=%d: %v", strategy.ID, persistErr)
			}
			return nil, fmt.Errorf("failed to start strategy runtime: %w", err)
		}
	}

	now := time.Now().UTC()
	runtimeState.Status = "running"
	runtimeState.BotStatus = "running"
	runtimeState.LastError = ""
	runtimeState.StoppedAt = nil
	runtimeState.StartedAt = &now
	if refreshedStatus, refreshedExists, refreshedErr := s.fetchRemoteRuntimeStatus(runtimeState.InstanceID); refreshedErr == nil && refreshedExists {
		runtimeState = mergeRemoteRuntimeState(runtimeState, refreshedStatus)
	}
	if err := s.persistRuntimeState(executionState, runtimeState, true); err != nil {
		return nil, err
	}

	log.Printf("✅ strategy runtime started strategy_id=%d instance_id=%s network=%s", strategy.ID, runtimeState.InstanceID, runtimeState.Network)
	return buildStrategyRuntimeResponse(strategy, executionState, runtimeState, true), nil
}

func (s *StrategyRuntimeService) StopRuntime(strategy *models.BacktestStrategy, force bool) (map[string]interface{}, error) {
	executionState, err := s.getOrCreateExecutionState(strategy.ID)
	if err != nil {
		return nil, err
	}

	runtimeState := decodeStrategyRuntimeState(executionState.State)
	if strings.TrimSpace(runtimeState.InstanceID) == "" {
		runtimeState.InstanceID = strategyRuntimeInstanceID(strategy)
	}

	_, remoteExists, err := s.fetchRemoteRuntimeStatus(runtimeState.InstanceID)
	if err != nil {
		return nil, err
	}
	if remoteExists {
		if err := s.botService.StopBotInstanceWithForce(runtimeState.InstanceID, force); err != nil {
			runtimeState.Status = "error"
			runtimeState.BotStatus = "error"
			runtimeState.LastError = err.Error()
			if persistErr := s.persistRuntimeState(executionState, runtimeState, false); persistErr != nil {
				log.Printf("⚠️ failed to persist strategy runtime error state strategy_id=%d: %v", strategy.ID, persistErr)
			}
			return nil, fmt.Errorf("failed to stop strategy runtime: %w", err)
		}
	}

	now := time.Now().UTC()
	runtimeState.Status = "stopped"
	runtimeState.BotStatus = "stopped"
	runtimeState.LastError = ""
	runtimeState.ProcessID = nil
	runtimeState.StoppedAt = &now
	if err := s.persistRuntimeState(executionState, runtimeState, false); err != nil {
		return nil, err
	}

	log.Printf("✅ strategy runtime stopped strategy_id=%d instance_id=%s force=%t", strategy.ID, runtimeState.InstanceID, force)
	return buildStrategyRuntimeResponse(strategy, executionState, runtimeState, false), nil
}

type runtimeKeyMaterial struct {
	Network      string
	ChainAddress string
	SecretPhrase string
}

func (s *StrategyRuntimeService) resolveRuntimeKey(userID int, requestedNetwork string) (*runtimeKeyMaterial, error) {
	network := strings.ToLower(strings.TrimSpace(requestedNetwork))
	if network != "" {
		key, err := s.keyService.GetKey(userID, network)
		if err != nil {
			return nil, fmt.Errorf("failed to load dYdX key for %s: %w", network, err)
		}
		if key == nil {
			return nil, fmt.Errorf("no active dYdX key configured for %s", network)
		}
		return &runtimeKeyMaterial{
			Network:      network,
			ChainAddress: fmt.Sprintf("%v", key["chain_address"]),
			SecretPhrase: fmt.Sprintf("%v", key["secret_phrase"]),
		}, nil
	}

	activeKeys, err := s.keyService.GetActiveKeys(userID)
	if err != nil {
		return nil, fmt.Errorf("failed to load active dYdX keys: %w", err)
	}
	if len(activeKeys) == 0 {
		return nil, fmt.Errorf("an active dYdX key is required before starting a strategy runtime")
	}

	selectedNetwork := ""
	for _, candidate := range []string{"testnet", "mainnet"} {
		for _, key := range activeKeys {
			if strings.EqualFold(fmt.Sprintf("%v", key["network"]), candidate) {
				selectedNetwork = candidate
				break
			}
		}
		if selectedNetwork != "" {
			break
		}
	}
	if selectedNetwork == "" {
		selectedNetwork = strings.ToLower(strings.TrimSpace(fmt.Sprintf("%v", activeKeys[0]["network"])))
	}

	return s.resolveRuntimeKey(userID, selectedNetwork)
}

func (s *StrategyRuntimeService) getOrCreateExecutionState(strategyID int) (*models.StrategyExecutionState, error) {
	executionState, err := s.strategyService.GetExecutionState(strategyID)
	if err != nil {
		return nil, err
	}
	if executionState != nil {
		return executionState, nil
	}

	return s.strategyService.CreateExecutionState(strategyID)
}

func (s *StrategyRuntimeService) ensureRuntimeInstance(
	strategy *models.BacktestStrategy,
	instanceID string,
	runtimeKey *runtimeKeyMaterial,
) (*models.BotInstance, bool, error) {
	existing, err := s.botRepo.GetBotInstanceByInstanceID(instanceID)
	if err == nil && existing != nil {
		return existing, true, nil
	}

	instance := s.buildBotInstanceRecord(strategy, instanceID, runtimeKey)
	if err != nil && !strings.Contains(strings.ToLower(err.Error()), "not found") {
		return nil, false, fmt.Errorf("failed to inspect existing runtime instance: %w", err)
	}

	return instance, false, nil
}

func (s *StrategyRuntimeService) buildBotInstanceRecord(
	strategy *models.BacktestStrategy,
	instanceID string,
	runtimeKey *runtimeKeyMaterial,
) *models.BotInstance {
	tradingParamsRaw, _ := json.Marshal(s.buildTradingParams(strategy, runtimeKey.Network))
	configRaw, _ := json.Marshal(map[string]interface{}{
		"strategy_id":        strategy.ID,
		"strategy_name":      strategy.Name,
		"managed_by":         "strategy_runtime",
		"runtime_strategy":   resolvedRuntimeStrategy(strategy),
		"backtesting_params": s.buildBacktestingParams(strategy),
	})

	return &models.BotInstance{
		InstanceID:   instanceID,
		InstanceName: strategy.Name,
		UserID:       strategy.UserID,
		Status:       "stopped",
		Network:      runtimeKey.Network,
		Strategy:     resolvedRuntimeStrategy(strategy),
		Config: sql.NullString{
			String: string(configRaw),
			Valid:  len(configRaw) > 0,
		},
		TradingParams: sql.NullString{
			String: string(tradingParamsRaw),
			Valid:  len(tradingParamsRaw) > 0,
		},
	}
}

func (s *StrategyRuntimeService) buildBotCreatePayload(
	strategy *models.BacktestStrategy,
	instanceID string,
	runtimeKey *runtimeKeyMaterial,
) map[string]interface{} {
	return map[string]interface{}{
		"instance_id":   instanceID,
		"instance_name": strategy.Name,
		"credentials": map[string]interface{}{
			"chain_id": chainIDForNetwork(runtimeKey.Network),
			"address":  runtimeKey.ChainAddress,
			"mnemonic": runtimeKey.SecretPhrase,
		},
		"telegram":           s.buildTelegramParams(),
		"trading_params":     s.buildTradingParams(strategy, runtimeKey.Network),
		"backtesting_params": s.buildBacktestingParams(strategy),
	}
}

func (s *StrategyRuntimeService) buildTelegramParams() map[string]interface{} {
	if s.telegramService == nil {
		return map[string]interface{}{
			"token":   "",
			"chat_id": "",
		}
	}

	config, configured, err := s.telegramService.ResolveSharedConfig()
	if err != nil {
		log.Printf("⚠️ failed to resolve Telegram settings for runtime payload: %v", err)
		return map[string]interface{}{
			"token":   "",
			"chat_id": "",
		}
	}
	if !configured || config == nil {
		return map[string]interface{}{
			"token":   "",
			"chat_id": "",
		}
	}

	return map[string]interface{}{
		"token":   config.BotToken,
		"chat_id": config.ChatID,
	}
}

func (s *StrategyRuntimeService) buildTradingParams(strategy *models.BacktestStrategy, network string) map[string]interface{} {
	return map[string]interface{}{
		"is_testnet":               !strings.EqualFold(network, "mainnet"),
		"find_cointegrated_pairs":  strategy.FindCointegratedPairs,
		"manage_exits":             strategy.ManageExits,
		"place_trades":             strategy.PlaceTrades,
		"abort_all_positions":      strategy.AbortAllPositions,
		"resolution_timeframe":     strategy.CandleResolution,
		"strategy":                 resolvedRuntimeStrategy(strategy),
		"stats_window":             strategy.StatsWindow,
		"max_half_life":            int(strategy.MaxHalfLife),
		"zscore_threshold":         strategy.ZscoreThreshold,
		"usd_per_trade":            strategy.UsdPerTrade,
		"usd_min_collateral":       strategy.UsdMinCollateral,
		"close_at_zscore_cross":    strategy.CloseAtZscoreCross,
		"max_positions":            strategy.MaxPositions,
		"max_drawdown_pct":         strategy.MaxDrawdownPct,
		"stop_loss_pct":            strategy.StopLossPct,
		"take_profit_pct":          strategy.TakeProfitPct,
		"trailing_stop_pct":        strategy.TrailingStopPct,
		"rebalance_interval_hours": strategy.RebalanceIntervalHours,
		"position_timeout_hours":   strategy.PositionTimeoutHours,
	}
}

func (s *StrategyRuntimeService) buildBacktestingParams(strategy *models.BacktestStrategy) map[string]interface{} {
	return map[string]interface{}{
		"candle_resolution": strategy.CandleResolution,
		"max_history_days":  strategy.MaxHistoryDays,
		"starting_balance":  strategy.StartingBalance,
		"transaction_fee":   strategy.TransactionFee,
		"slippage":          strategy.Slippage,
		"benchmark_symbol":  strategy.BenchmarkSymbol,
		"risk_free_rate":    strategy.RiskFreeRate,
	}
}

func resolvedRuntimeStrategy(strategy *models.BacktestStrategy) string {
	runtimeStrategy := strings.TrimSpace(strategy.RuntimeStrategy)
	if runtimeStrategy == "" {
		return "cointegration"
	}
	return runtimeStrategy
}

func (s *StrategyRuntimeService) reconcileRuntimeState(
	strategy *models.BacktestStrategy,
	executionState *models.StrategyExecutionState,
	runtimeState StrategyRuntimeState,
) (StrategyRuntimeState, bool, error) {
	remoteStatus, remoteExists, err := s.fetchRemoteRuntimeStatus(runtimeState.InstanceID)
	if err != nil {
		return runtimeState, false, err
	}

	if remoteExists {
		runtimeState = mergeRemoteRuntimeState(runtimeState, remoteStatus)
		isRunning := isBotStatusRunning(remoteStatus)
		if err := s.persistRuntimeState(executionState, runtimeState, isRunning); err != nil {
			return runtimeState, isRunning, err
		}
		return runtimeState, isRunning, nil
	}

	localInstance, localErr := s.botRepo.GetBotInstanceByInstanceID(runtimeState.InstanceID)
	if localErr == nil && localInstance != nil {
		localStatus := strings.ToLower(strings.TrimSpace(localInstance.Status))
		if localStatus == "running" || localStatus == "starting" {
			runtimeState.Status = "error"
			runtimeState.BotStatus = "missing"
			runtimeState.LastError = "runtime instance missing from bot API"
			if persistErr := s.persistRuntimeState(executionState, runtimeState, false); persistErr != nil {
				return runtimeState, false, persistErr
			}
			_ = s.botRepo.UpdateBotInstanceError(runtimeState.InstanceID, runtimeState.LastError)
			return runtimeState, false, nil
		}
	}

	if runtimeState.Status == "" {
		runtimeState.Status = "stopped"
	}
	if runtimeState.BotStatus == "" {
		runtimeState.BotStatus = "stopped"
	}

	return runtimeState, false, nil
}

func (s *StrategyRuntimeService) fetchRemoteRuntimeStatus(instanceID string) (map[string]interface{}, bool, error) {
	if strings.TrimSpace(instanceID) == "" {
		return nil, false, nil
	}

	result, err := s.botService.GetRemoteBotInstance(instanceID)
	if err != nil {
		if apiErr, ok := err.(*BotAPIError); ok && apiErr.StatusCode == 404 {
			return nil, false, nil
		}
		return nil, false, fmt.Errorf("failed to query bot runtime instance %s: %w", instanceID, err)
	}

	return unwrapBotEnvelope(result), true, nil
}

func (s *StrategyRuntimeService) persistRuntimeState(
	executionState *models.StrategyExecutionState,
	runtimeState StrategyRuntimeState,
	isRunning bool,
) error {
	now := time.Now().UTC()
	runtimeState.LastSyncedAt = &now
	if isRunning && runtimeState.StartedAt == nil {
		runtimeState.StartedAt = &now
	}
	if !isRunning && runtimeState.StoppedAt == nil {
		runtimeState.StoppedAt = &now
	}

	rawState, err := json.Marshal(runtimeState)
	if err != nil {
		return fmt.Errorf("failed to marshal strategy runtime state: %w", err)
	}

	executionState.IsRunning = isRunning
	executionState.NextRunAt = nil
	executionState.State = sql.NullString{
		String: string(rawState),
		Valid:  true,
	}
	if isRunning {
		executionState.LastRunAt = &now
	}

	return s.strategyService.UpdateExecutionState(executionState)
}

func decodeStrategyRuntimeState(rawState sql.NullString) StrategyRuntimeState {
	if !rawState.Valid || strings.TrimSpace(rawState.String) == "" {
		return StrategyRuntimeState{
			Status:    "stopped",
			BotStatus: "stopped",
		}
	}

	var runtimeState StrategyRuntimeState
	if err := json.Unmarshal([]byte(rawState.String), &runtimeState); err != nil {
		return StrategyRuntimeState{
			Status:    "stopped",
			BotStatus: "stopped",
			LastError: "failed to decode persisted runtime state",
		}
	}

	if strings.TrimSpace(runtimeState.Status) == "" {
		runtimeState.Status = "stopped"
	}
	if strings.TrimSpace(runtimeState.BotStatus) == "" {
		runtimeState.BotStatus = runtimeState.Status
	}
	return runtimeState
}

func mergeRemoteRuntimeState(runtimeState StrategyRuntimeState, remote map[string]interface{}) StrategyRuntimeState {
	status := strings.ToLower(strings.TrimSpace(fmt.Sprintf("%v", remote["status"])))
	if status == "" {
		status = "unknown"
	}

	now := time.Now().UTC()
	runtimeState.Status = status
	runtimeState.BotStatus = status
	runtimeState.ProcessID = extractIntPointer(remote["process_id"])
	runtimeState.LastSyncedAt = &now
	if strings.TrimSpace(runtimeState.Network) == "" {
		config := nestedMap(remote, "config")
		tradingParams := nestedMap(config, "trading_params")
		if isTestnet, ok := tradingParams["is_testnet"].(bool); ok {
			if isTestnet {
				runtimeState.Network = "testnet"
			} else {
				runtimeState.Network = "mainnet"
			}
		}
	}
	if status == "running" {
		runtimeState.StoppedAt = nil
		if runtimeState.StartedAt == nil {
			runtimeState.StartedAt = &now
		}
	} else if status == "stopped" {
		runtimeState.ProcessID = nil
		runtimeState.StoppedAt = &now
	}

	return runtimeState
}

func buildStrategyRuntimeResponse(
	strategy *models.BacktestStrategy,
	executionState *models.StrategyExecutionState,
	runtimeState StrategyRuntimeState,
	isRunning bool,
) map[string]interface{} {
	return map[string]interface{}{
		"strategy_id":    strategy.ID,
		"strategy_name":  strategy.Name,
		"instance_id":    runtimeState.InstanceID,
		"network":        runtimeState.Network,
		"status":         runtimeState.Status,
		"bot_status":     runtimeState.BotStatus,
		"is_running":     isRunning,
		"process_id":     runtimeState.ProcessID,
		"last_error":     runtimeState.LastError,
		"started_at":     runtimeState.StartedAt,
		"stopped_at":     runtimeState.StoppedAt,
		"last_run_at":    executionState.LastRunAt,
		"next_run_at":    executionState.NextRunAt,
		"updated_at":     executionState.UpdatedAt,
		"last_synced_at": runtimeState.LastSyncedAt,
	}
}

func strategyRuntimeInstanceID(strategy *models.BacktestStrategy) string {
	return fmt.Sprintf("strategy-%d-%d", strategy.UserID, strategy.ID)
}

func chainIDForNetwork(network string) string {
	if strings.EqualFold(network, "mainnet") {
		return "dydx-mainnet"
	}
	return "dydx-testnet-4"
}

func unwrapBotEnvelope(payload map[string]interface{}) map[string]interface{} {
	if payload == nil {
		return map[string]interface{}{}
	}
	if data, ok := payload["data"].(map[string]interface{}); ok {
		return data
	}
	return payload
}

func nestedMap(payload map[string]interface{}, key string) map[string]interface{} {
	if payload == nil {
		return nil
	}
	if nested, ok := payload[key].(map[string]interface{}); ok {
		return nested
	}
	return nil
}

func extractIntPointer(value interface{}) *int {
	switch typed := value.(type) {
	case int:
		result := typed
		return &result
	case int32:
		result := int(typed)
		return &result
	case int64:
		result := int(typed)
		return &result
	case float64:
		result := int(typed)
		return &result
	default:
		return nil
	}
}

func isBotStatusRunning(remote map[string]interface{}) bool {
	status := strings.ToLower(strings.TrimSpace(fmt.Sprintf("%v", remote["status"])))
	return status == "running" || status == "starting"
}
