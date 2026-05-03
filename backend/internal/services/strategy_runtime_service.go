package services

import (
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

type StrategyRuntimeState struct {
	InstanceID       string     `json:"instance_id,omitempty"`
	Network          string     `json:"network,omitempty"`
	Status           string     `json:"status,omitempty"`
	BotStatus        string     `json:"bot_status,omitempty"`
	LastError        string     `json:"last_error,omitempty"`
	ProcessID        *int       `json:"process_id,omitempty"`
	TradesExecuted   *int       `json:"trades_executed,omitempty"`
	Pnl              *float64   `json:"pnl,omitempty"`
	WinRate          *float64   `json:"win_rate,omitempty"`
	OpenPositions    *int       `json:"open_positions,omitempty"`
	UptimeSeconds    *int       `json:"uptime_seconds,omitempty"`
	StartedAt        *time.Time `json:"started_at,omitempty"`
	StoppedAt        *time.Time `json:"stopped_at,omitempty"`
	RuntimeUpdatedAt *time.Time `json:"runtime_updated_at,omitempty"`
	LastSyncedAt     *time.Time `json:"last_synced_at,omitempty"`
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
	return s.startRuntime(strategy, requestedNetwork, false)
}

func (s *StrategyRuntimeService) GetRuntimeStartReadiness(strategy *models.BacktestStrategy, requestedNetwork string) (map[string]interface{}, error) {
	network := strings.TrimSpace(requestedNetwork)
	if network == "" {
		network = strings.TrimSpace(strategy.RuntimeNetwork)
	}
	if network == "" {
		network = "testnet"
	}
	network = strings.ToLower(network)

	configuredSelectedMarkets := strategy.SelectedMarketList()
	validSelectedMarkets := sanitizeRuntimeSelectedMarkets(configuredSelectedMarkets)
	blockers := make([]string, 0)
	warnings := make([]string, 0)

	if len(configuredSelectedMarkets) > 0 && len(validSelectedMarkets) == 0 {
		blockers = append(
			blockers,
			"Selected markets must include at least two active dYdX perpetual symbols (e.g., BTC-USD and ETH-USD). Remove placeholders like PORTFOLIO or add additional markets before launching.",
		)
	}

	if len(configuredSelectedMarkets) == 0 {
		blockers = append(
			blockers,
			"Selected pairs are required before launching a strategy runtime. Choose at least two dYdX perpetual markets or explicitly save an all-market strategy selection.",
		)
	}

	response := map[string]interface{}{
		"strategy_id":                 strategy.ID,
		"strategy_name":               strategy.Name,
		"selected_runtime_network":    network,
		"selected_subaccount":         strategy.RuntimeSubaccount,
		"configured_selected_markets": configuredSelectedMarkets,
		"valid_selected_markets":      validSelectedMarkets,
		"usd_per_trade":               strategy.UsdPerTrade,
		"usd_min_collateral":          strategy.UsdMinCollateral,
		"capital_allocation_usd":      resolveCapitalAllocation(strategy),
		"key_exists":                  false,
		"ready":                       false,
		"blockers":                    blockers,
		"warnings":                    warnings,
	}

	keyInfo, err := s.keyService.GetKeyInfo(strategy.UserID, network)
	if err != nil {
		return nil, fmt.Errorf("failed to inspect runtime key: %w", err)
	}
	if keyInfo == nil {
		blockers = append(blockers, fmt.Sprintf("No active %s dYdX key is stored for this user.", network))
		response["blockers"] = dedupeOrderedStrings(blockers)
		response["warnings"] = dedupeOrderedStrings(warnings)
		return response, nil
	}
	response["key_exists"] = true
	response["key_chain_address"] = keyInfo.ChainAddress

	keyPayload, err := s.keyService.GetKey(strategy.UserID, network)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve runtime key material: %w", err)
	}
	if keyPayload == nil {
		blockers = append(blockers, fmt.Sprintf("No active %s dYdX key is stored for this user.", network))
		response["blockers"] = dedupeOrderedStrings(blockers)
		response["warnings"] = dedupeOrderedStrings(warnings)
		return response, nil
	}

	preflightPayload := map[string]interface{}{
		"instance_name": strategy.Name,
		"credentials": map[string]interface{}{
			"chain_id": chainIDForNetwork(network),
			"address":  keyPayload.ChainAddress,
			"mnemonic": keyPayload.SecretPhrase,
		},
		"trading_params": s.buildTradingParams(strategy, network),
	}

	result, err := s.botService.GetRuntimePreflight(preflightPayload)
	if err != nil {
		return nil, fmt.Errorf("failed to evaluate runtime readiness: %w", err)
	}

	preflight := unwrapBotEnvelope(result)
	for key, value := range preflight {
		if key == "blockers" || key == "warnings" || key == "ready" {
			continue
		}
		response[key] = value
	}
	blockers = append(blockers, stringifyRuntimeBlockers(preflight["blockers"])...)
	warnings = append(warnings, stringifyRuntimeBlockers(preflight["warnings"])...)

	preflightReady, _ := preflight["ready"].(bool)
	response["selected_runtime_network"] = network
	response["selected_subaccount"] = strategy.RuntimeSubaccount
	response["key_exists"] = true
	response["key_chain_address"] = keyInfo.ChainAddress
	response["blockers"] = dedupeOrderedStrings(blockers)
	response["warnings"] = dedupeOrderedStrings(warnings)
	response["ready"] = preflightReady && len(dedupeOrderedStrings(blockers)) == 0
	return response, nil
}

func (s *StrategyRuntimeService) StartRuntimeWithForceRecreate(strategy *models.BacktestStrategy, requestedNetwork string) (map[string]interface{}, error) {
	return s.startRuntime(strategy, requestedNetwork, true)
}

func (s *StrategyRuntimeService) startRuntime(
	strategy *models.BacktestStrategy,
	requestedNetwork string,
	forceRecreate bool,
) (map[string]interface{}, error) {
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
		networkHint = strings.TrimSpace(strategy.RuntimeNetwork)
	}
	if networkHint == "" {
		networkHint = strings.TrimSpace(runtimeState.Network)
	}

	readiness, readinessErr := s.GetRuntimeStartReadiness(strategy, networkHint)
	if readinessErr != nil {
		return nil, fmt.Errorf("failed to validate runtime readiness: %w", readinessErr)
	}

	ready, _ := readiness["ready"].(bool)
	if !ready {
		blockers := stringifyRuntimeBlockers(readiness["blockers"])
		if len(blockers) == 0 {
			blockers = append(blockers, "runtime readiness checks did not pass")
		}
		return nil, fmt.Errorf("runtime readiness failed: %s", strings.Join(blockers, "; "))
	}

	runtimeKey, err := s.resolveRuntimeKey(strategy.UserID, networkHint)
	if err != nil {
		return nil, err
	}
	runtimeState.Network = runtimeKey.Network
	log.Printf(
		"ℹ️ strategy_runtime_promotion strategy_id=%d target_environment=%s selected_pairs=%v",
		strategy.ID,
		runtimeKey.Network,
		sanitizeRuntimeSelectedMarkets(strategy.SelectedMarketList()),
	)

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

	createPayload := s.buildBotCreatePayload(strategy, runtimeState.InstanceID, runtimeKey)
	if instanceRecord == nil {
		instanceRecord = s.buildBotInstanceRecord(strategy, runtimeState.InstanceID, runtimeKey)
	}

	if !forceRecreate && existsLocally && shouldRecreateForTelegramRefresh(instanceRecord, createPayload) {
		log.Printf(
			"ℹ️ refreshing runtime instance %s to apply updated Telegram delivery settings",
			runtimeState.InstanceID,
		)
		forceRecreate = true
	}

	if forceRecreate {
		if recreateErr := s.botService.RecreateBotInstanceWithConfig(instanceRecord, createPayload); recreateErr != nil {
			return nil, fmt.Errorf("failed to recreate runtime instance: %w", recreateErr)
		}
		remoteStatus = nil
	} else if !remoteExists {
		if existsLocally {
			if _, createErr := s.botService.GetRemoteBotInstance(runtimeState.InstanceID); createErr != nil {
				var apiErr *BotAPIError
				if errors.As(createErr, &apiErr) {
					if createRemoteErr := s.botService.CreateBotInstanceWithConfig(instanceRecord, createPayload); createRemoteErr != nil {
						if isRuntimeInstanceAlreadyExistsError(createRemoteErr) {
							return nil, fmt.Errorf(
								"stale runtime instance detected for %s; confirm recreate to replace it",
								runtimeState.InstanceID,
							)
						}
						return nil, fmt.Errorf("failed to create runtime instance: %w", createRemoteErr)
					}
				}
			}
		} else {
			if createErr := s.botService.CreateBotInstanceWithConfig(instanceRecord, createPayload); createErr != nil {
				if isRuntimeInstanceAlreadyExistsError(createErr) {
					return nil, fmt.Errorf(
						"stale runtime instance detected for %s; confirm recreate to replace it",
						runtimeState.InstanceID,
					)
				}
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

func isRuntimeInstanceAlreadyExistsError(err error) bool {
	if err == nil {
		return false
	}

	var apiErr *BotAPIError
	if errors.As(err, &apiErr) {
		return strings.Contains(strings.ToLower(strings.TrimSpace(apiErr.Message)), "instance_id already exists")
	}

	return strings.Contains(strings.ToLower(err.Error()), "instance_id already exists")
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
			ChainAddress: key.ChainAddress,
			SecretPhrase: key.SecretPhrase,
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
			if strings.EqualFold(key.Network, candidate) {
				selectedNetwork = candidate
				break
			}
		}
		if selectedNetwork != "" {
			break
		}
	}
	if selectedNetwork == "" {
		selectedNetwork = strings.ToLower(strings.TrimSpace(activeKeys[0].Network))
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
	tradingParams := s.buildTradingParams(strategy, runtimeKey.Network)
	configPayload := map[string]interface{}{
		"instance_name": strategy.Name,
		"credentials": map[string]interface{}{
			"chain_id": chainIDForNetwork(runtimeKey.Network),
			"address":  runtimeKey.ChainAddress,
			"mnemonic": runtimeKey.SecretPhrase,
		},
		"telegram":           s.buildTelegramParams(strategy.UserID),
		"trading_params":     tradingParams,
		"backtesting_params": s.buildBacktestingParams(strategy),
		"strategy_id":        strategy.ID,
		"strategy_name":      strategy.Name,
		"managed_by":         "strategy_runtime",
		"runtime_strategy":   resolvedRuntimeStrategy(strategy),
		"runtime_network":    runtimeKey.Network,
		"runtime_subaccount": strategy.RuntimeSubaccount,
	}
	tradingParamsRaw, _ := json.Marshal(tradingParams)
	configRaw, _ := json.Marshal(configPayload)

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
		"telegram":           s.buildTelegramParams(strategy.UserID),
		"trading_params":     s.buildTradingParams(strategy, runtimeKey.Network),
		"backtesting_params": s.buildBacktestingParams(strategy),
		"runtime_network":    runtimeKey.Network,
		"runtime_subaccount": strategy.RuntimeSubaccount,
	}
}

func (s *StrategyRuntimeService) buildTelegramParams(userID int) map[string]interface{} {
	if s.telegramService == nil {
		return map[string]interface{}{
			"token":   "",
			"chat_id": "",
		}
	}

	resolved, err := s.telegramService.ResolveEffectiveConfig(userID)
	if err != nil {
		log.Printf("⚠️ failed to resolve Telegram settings for runtime payload user_id=%d: %v", userID, err)
		return map[string]interface{}{
			"token":   "",
			"chat_id": "",
			"source":  string(TelegramConfigSourceNone),
		}
	}
	if resolved == nil || resolved.Config == nil || resolved.Source == TelegramConfigSourceNone {
		return map[string]interface{}{
			"token":   "",
			"chat_id": "",
			"source":  string(TelegramConfigSourceNone),
		}
	}

	log.Printf("ℹ️ using Telegram config source=%s for user_id=%d", resolved.Source, userID)
	return map[string]interface{}{
		"token":   resolved.Config.BotToken,
		"chat_id": resolved.Config.ChatID,
		"source":  string(resolved.Source),
	}
}

func (s *StrategyRuntimeService) buildTradingParams(strategy *models.BacktestStrategy, network string) map[string]interface{} {
	resolution := normalizeDydxCandleResolution(strategy.CandleResolution)
	selectedMarkets := sanitizeRuntimeSelectedMarkets(strategy.SelectedMarketList())
	log.Printf(
		"ℹ️ strategy_runtime_selected_pairs strategy_id=%d network=%s selected_pairs=%v",
		strategy.ID,
		network,
		selectedMarkets,
	)
	return map[string]interface{}{
		"is_testnet":               !strings.EqualFold(network, "mainnet"),
		"subaccount_number":        strategy.RuntimeSubaccount,
		"capital_allocation_usd":   resolveCapitalAllocation(strategy),
		"find_cointegrated_pairs":  strategy.FindCointegratedPairs,
		"manage_exits":             strategy.ManageExits,
		"place_trades":             strategy.PlaceTrades,
		"abort_all_positions":      strategy.AbortAllPositions,
		"resolution_timeframe":     resolution,
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
		"pair_selection_mode":      strategy.PairSelectionMode,
		"selected_markets":         selectedMarkets,
		"selected_pairs":           selectedMarkets,
	}
}

func sanitizeRuntimeSelectedMarkets(markets []string) []string {
	if len(markets) == 0 {
		return []string{}
	}

	seen := make(map[string]struct{}, len(markets))
	result := make([]string, 0, len(markets))
	for _, market := range markets {
		normalized := strings.ToUpper(strings.TrimSpace(market))
		if normalized == "" {
			continue
		}

		// Runtime market universes must be concrete dYdX perpetual symbols.
		if normalized == "PORTFOLIO" || !strings.Contains(normalized, "-") {
			continue
		}

		if _, exists := seen[normalized]; exists {
			continue
		}
		seen[normalized] = struct{}{}
		result = append(result, normalized)
	}

	// Pair-trading runtime requires at least two valid markets. Readiness blocks
	// runtime launch when fewer are configured.
	if len(result) < 2 {
		return []string{}
	}

	return result
}

func (s *StrategyRuntimeService) buildBacktestingParams(strategy *models.BacktestStrategy) map[string]interface{} {
	resolution := normalizeDydxCandleResolution(strategy.CandleResolution)
	return map[string]interface{}{
		"candle_resolution": resolution,
		"max_history_days":  strategy.MaxHistoryDays,
		"starting_balance":  strategy.StartingBalance,
		"transaction_fee":   strategy.TransactionFee,
		"slippage":          strategy.Slippage,
		"benchmark_symbol":  strategy.BenchmarkSymbol,
		"risk_free_rate":    strategy.RiskFreeRate,
	}
}

func normalizeDydxCandleResolution(value string) string {
	switch strings.ToUpper(strings.TrimSpace(value)) {
	case "M1", "1M", "1MIN", "1MINUTE", "1MINUTES":
		return "1MIN"
	case "M5", "5M", "5MIN", "5MINS", "5MINUTE", "5MINUTES":
		return "5MINS"
	case "M15", "15M", "15MIN", "15MINS", "15MINUTE", "15MINUTES":
		return "15MINS"
	case "M30", "30M", "30MIN", "30MINS", "30MINUTE", "30MINUTES":
		return "30MINS"
	case "H1", "1H", "1HR", "1HOUR", "1HOURS":
		return "1HOUR"
	case "H4", "4H", "4HR", "4HOUR", "4HOURS":
		return "4HOURS"
	case "D1", "1D", "1DAY", "1DAYS":
		return "1DAY"
	default:
		return "1HOUR"
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
		if !shouldGracefullyDegradeRuntimeSyncError(err) {
			return runtimeState, false, err
		}

		// P1.7: Keep error status for backward compat, but set bot_status to unavailable for clarity
		runtimeState.Status = "error"
		runtimeState.BotStatus = "unavailable"
		runtimeState.LastError = runtimeSyncErrorMessage(err)
		if persistErr := s.persistRuntimeState(executionState, runtimeState, false); persistErr != nil {
			return runtimeState, false, persistErr
		}
		log.Printf(
			"⚠️ strategy runtime sync degraded strategy_id=%d instance_id=%s: %s",
			strategy.ID,
			runtimeState.InstanceID,
			runtimeState.LastError,
		)
		return runtimeState, false, nil
	}

	if remoteExists {
		runtimeState = mergeRemoteRuntimeState(runtimeState, remoteStatus)
		// P1.7: Detect recovery and degraded states from remote
		botStatus := strings.ToLower(strings.TrimSpace(fmt.Sprintf("%v", remoteStatus["status"])))
		if botStatus == "recovering" || botStatus == "degraded" || botStatus == "safeguarded" {
			runtimeState.Status = botStatus
			runtimeState.BotStatus = botStatus
		}
		isRunning := isBotStatusRunning(remoteStatus)
		if err := s.persistRuntimeState(executionState, runtimeState, isRunning); err != nil {
			log.Printf(
				"⚠️ failed to persist reconciled runtime state strategy_id=%d instance_id=%s: %v",
				strategy.ID,
				runtimeState.InstanceID,
				err,
			)
		}
		return runtimeState, isRunning, nil
	}

	localInstance, localErr := s.botRepo.GetBotInstanceByInstanceID(runtimeState.InstanceID)
	if localErr == nil && localInstance != nil {
		localStatus := strings.ToLower(strings.TrimSpace(localInstance.Status))
		// P1.7: Include recovery states in missing detection
		if localStatus == "running" || localStatus == "starting" || localStatus == "recovering" {
			runtimeState.Status = "error"
			runtimeState.BotStatus = "missing"
			runtimeState.LastError = "runtime instance missing from bot API; may be recovering"
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
		var apiErr *BotAPIError
		if errors.As(err, &apiErr) && apiErr.StatusCode == 404 {
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
	if !isRunning && runtimeState.StoppedAt == nil && strings.EqualFold(runtimeState.Status, "stopped") {
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

func shouldGracefullyDegradeRuntimeSyncError(err error) bool {
	var transportErr *BotAPITransportError
	if errors.As(err, &transportErr) {
		return true
	}

	var apiErr *BotAPIError
	if errors.As(err, &apiErr) {
		return apiErr.StatusCode == 401 || apiErr.StatusCode == 403 || apiErr.StatusCode >= 500
	}

	return false
}

func runtimeSyncErrorMessage(err error) string {
	var transportErr *BotAPITransportError
	if errors.As(err, &transportErr) {
		return transportErr.Message
	}

	var apiErr *BotAPIError
	if errors.As(err, &apiErr) && strings.TrimSpace(apiErr.Message) != "" {
		return apiErr.Message
	}

	return err.Error()
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
	stats := nestedMap(remote, "stats")
	performance := nestedMap(remote, "performance")
	runtime := nestedMap(remote, "runtime")

	runtimeState.Status = status
	runtimeState.BotStatus = status
	runtimeState.ProcessID = extractIntPointer(remote["process_id"])
	runtimeState.TradesExecuted = extractIntPointerPrioritized(
		[]string{"trades_executed", "total_trades", "trades_count"},
		remote,
		stats,
		performance,
		runtime,
	)
	runtimeState.Pnl = extractFloatPointerPrioritized(
		[]string{"pnl", "total_pnl", "total_pnl_usd", "realized_pnl", "pnl_usd"},
		remote,
		stats,
		performance,
		runtime,
	)
	runtimeState.WinRate = normalizeWinRatePercent(extractFloatPointerPrioritized(
		[]string{"win_rate", "win_rate_pct", "win_rate_percent"},
		remote,
		stats,
		performance,
		runtime,
	))
	runtimeState.OpenPositions = resolveOpenPositions(remote, stats, performance, runtime)
	runtimeState.RuntimeUpdatedAt = extractTimePointerPrioritized(
		[]string{"runtime_updated_at", "updated_at", "last_update_at", "last_updated_at", "last_heartbeat_at"},
		remote,
		stats,
		performance,
		runtime,
	)
	runtimeState.UptimeSeconds = resolveUptimeSeconds(remote, stats, runtime, runtimeState.StartedAt, status)
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
		runtimeState.LastError = ""
		runtimeState.StoppedAt = nil
		if runtimeState.StartedAt == nil {
			runtimeState.StartedAt = &now
		}
	} else if status == "starting" || status == "stopping" {
		runtimeState.LastError = ""
	} else if status == "stopped" {
		runtimeState.LastError = ""
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
	uptimeSeconds := runtimeState.UptimeSeconds
	if uptimeSeconds == nil && isRunning && runtimeState.StartedAt != nil {
		elapsed := int(time.Since(*runtimeState.StartedAt).Seconds())
		if elapsed >= 0 {
			uptimeSeconds = &elapsed
		}
	}

	return map[string]interface{}{
		"strategy_id":            strategy.ID,
		"strategy_name":          strategy.Name,
		"instance_id":            runtimeState.InstanceID,
		"runtime_network":        strategy.RuntimeNetwork,
		"runtime_subaccount":     strategy.RuntimeSubaccount,
		"capital_allocation_usd": resolveCapitalAllocation(strategy),
		"network":                runtimeState.Network,
		"status":                 runtimeState.Status,
		"bot_status":             runtimeState.BotStatus,
		"is_running":             isRunning,
		"process_id":             runtimeState.ProcessID,
		"trades_executed":        runtimeState.TradesExecuted,
		"pnl":                    runtimeState.Pnl,
		"win_rate":               runtimeState.WinRate,
		"open_positions":         runtimeState.OpenPositions,
		"uptime_seconds":         uptimeSeconds,
		"last_error":             runtimeState.LastError,
		"started_at":             runtimeState.StartedAt,
		"stopped_at":             runtimeState.StoppedAt,
		"runtime_updated_at":     runtimeState.RuntimeUpdatedAt,
		"last_run_at":            executionState.LastRunAt,
		"next_run_at":            executionState.NextRunAt,
		"updated_at":             executionState.UpdatedAt,
		"last_synced_at":         runtimeState.LastSyncedAt,
	}
}

func resolveCapitalAllocation(strategy *models.BacktestStrategy) float64 {
	if strategy == nil {
		return 0
	}
	if strategy.InitialAmount > 0 {
		return strategy.InitialAmount
	}
	return strategy.UsdMinCollateral
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

func extractFloatPointer(value interface{}) *float64 {
	switch typed := value.(type) {
	case float64:
		result := typed
		return &result
	case float32:
		result := float64(typed)
		return &result
	case int:
		result := float64(typed)
		return &result
	case int32:
		result := float64(typed)
		return &result
	case int64:
		result := float64(typed)
		return &result
	case string:
		parsed, err := strconv.ParseFloat(strings.TrimSpace(typed), 64)
		if err != nil {
			return nil
		}
		return &parsed
	default:
		return nil
	}
}

func extractIntPointerPrioritized(keys []string, payloads ...map[string]interface{}) *int {
	for _, payload := range payloads {
		if payload == nil {
			continue
		}
		for _, key := range keys {
			if value, exists := payload[key]; exists {
				if extracted := extractIntPointer(value); extracted != nil {
					return extracted
				}
			}
		}
	}
	return nil
}

func extractFloatPointerPrioritized(keys []string, payloads ...map[string]interface{}) *float64 {
	for _, payload := range payloads {
		if payload == nil {
			continue
		}
		for _, key := range keys {
			if value, exists := payload[key]; exists {
				if extracted := extractFloatPointer(value); extracted != nil {
					return extracted
				}
			}
		}
	}
	return nil
}

func extractTimePointer(value interface{}) *time.Time {
	text := strings.TrimSpace(fmt.Sprintf("%v", value))
	if text == "" || text == "<nil>" {
		return nil
	}

	for _, layout := range []string{time.RFC3339Nano, time.RFC3339, "2006-01-02 15:04:05"} {
		parsed, err := time.Parse(layout, text)
		if err == nil {
			parsedUTC := parsed.UTC()
			return &parsedUTC
		}
	}

	return nil
}

func extractTimePointerPrioritized(keys []string, payloads ...map[string]interface{}) *time.Time {
	for _, payload := range payloads {
		if payload == nil {
			continue
		}
		for _, key := range keys {
			if value, exists := payload[key]; exists {
				if extracted := extractTimePointer(value); extracted != nil {
					return extracted
				}
			}
		}
	}
	return nil
}

func resolveOpenPositions(payloads ...map[string]interface{}) *int {
	countKeys := []string{"open_positions", "open_positions_count", "positions_open", "active_positions"}
	if count := extractIntPointerPrioritized(countKeys, payloads...); count != nil {
		return count
	}

	for _, payload := range payloads {
		if payload == nil {
			continue
		}
		for _, key := range []string{"positions", "open_positions_list"} {
			if raw, exists := payload[key]; exists {
				if items, ok := raw.([]interface{}); ok {
					count := len(items)
					return &count
				}
			}
		}
	}

	return nil
}

func resolveUptimeSeconds(
	remote map[string]interface{},
	stats map[string]interface{},
	runtime map[string]interface{},
	startedAt *time.Time,
	status string,
) *int {
	uptime := extractIntPointerPrioritized(
		[]string{"uptime_seconds", "uptime_secs", "runtime_uptime_seconds"},
		remote,
		stats,
		runtime,
	)
	if uptime != nil {
		return uptime
	}

	if startedAt == nil {
		return nil
	}

	if status != "running" && status != "starting" && status != "degraded" && status != "recovering" && status != "safeguarded" {
		return nil
	}

	elapsed := int(time.Since(*startedAt).Seconds())
	if elapsed < 0 {
		return nil
	}
	return &elapsed
}

func normalizeWinRatePercent(value *float64) *float64 {
	if value == nil {
		return nil
	}
	normalized := *value
	if normalized >= 0 && normalized <= 1 {
		normalized *= 100
	}
	return &normalized
}

func isBotStatusRunning(remote map[string]interface{}) bool {
	status := strings.ToLower(strings.TrimSpace(fmt.Sprintf("%v", remote["status"])))
	// P1.7: degraded and recovering are "running" in the sense they don't mean stopped
	return status == "running" || status == "starting" || status == "degraded" || status == "recovering" || status == "safeguarded"
}

func stringifyRuntimeBlockers(raw interface{}) []string {
	switch typed := raw.(type) {
	case []string:
		return typed
	case []interface{}:
		results := make([]string, 0, len(typed))
		for _, entry := range typed {
			candidate := strings.TrimSpace(fmt.Sprintf("%v", entry))
			if candidate != "" {
				results = append(results, candidate)
			}
		}
		return results
	default:
		candidate := strings.TrimSpace(fmt.Sprintf("%v", raw))
		if candidate == "" || candidate == "<nil>" {
			return []string{}
		}
		return []string{candidate}
	}
}

func dedupeOrderedStrings(values []string) []string {
	if len(values) == 0 {
		return []string{}
	}

	seen := make(map[string]struct{}, len(values))
	result := make([]string, 0, len(values))
	for _, value := range values {
		normalized := strings.TrimSpace(value)
		if normalized == "" {
			continue
		}
		if _, exists := seen[normalized]; exists {
			continue
		}
		seen[normalized] = struct{}{}
		result = append(result, normalized)
	}
	return result
}

func shouldRecreateForTelegramRefresh(
	instance *models.BotInstance,
	desiredPayload map[string]interface{},
) bool {
	if instance == nil {
		return false
	}

	desiredToken, desiredChatID := extractTelegramCredentials(desiredPayload)
	currentToken, currentChatID := extractTelegramCredentialsFromStoredConfig(instance.Config)

	return strings.TrimSpace(desiredToken) != strings.TrimSpace(currentToken) ||
		strings.TrimSpace(desiredChatID) != strings.TrimSpace(currentChatID)
}

func extractTelegramCredentials(payload map[string]interface{}) (token string, chatID string) {
	telegramRaw, ok := payload["telegram"]
	if !ok || telegramRaw == nil {
		return "", ""
	}

	telegram, ok := telegramRaw.(map[string]interface{})
	if !ok {
		return "", ""
	}

	return strings.TrimSpace(fmt.Sprintf("%v", telegram["token"])),
		strings.TrimSpace(fmt.Sprintf("%v", telegram["chat_id"]))
}

func extractTelegramCredentialsFromStoredConfig(config sql.NullString) (token string, chatID string) {
	if !config.Valid || strings.TrimSpace(config.String) == "" {
		return "", ""
	}

	var payload map[string]interface{}
	if err := json.Unmarshal([]byte(config.String), &payload); err != nil {
		return "", ""
	}

	return extractTelegramCredentials(payload)
}
