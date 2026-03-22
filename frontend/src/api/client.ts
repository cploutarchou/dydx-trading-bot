// Compatibility API client shim.
// This file intentionally re-exports the maintained enhanced client so older imports
// continue to work without duplicating HTTP logic.

export { enhancedApiClient as apiClient, default } from './enhancedClient';
export type {
    ApiError,
    ApiResponse,
    AuthResponse,
    Backtest,
    BacktestConfig,
    BacktestMetrics,
    BacktestProgress,
    BotAlert,
    BotInstance,
    BotPosition,
    BotRealtimeStats,
    BotStats,
    BotTrade,
    CreateBotRequest,
    ListAlertsParams,
    ListBacktestsParams,
    ListBotsParams,
    ListTradesParams,
    MarketData,
    StartBotRequest,
    SystemStatus,
    UpdateBotRequest,
    User
} from './types';

