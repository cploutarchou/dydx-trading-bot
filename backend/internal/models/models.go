package models

import (
	"database/sql"
	"time"
)

// ==================== USER MODELS ====================

type User struct {
	ID                     int        `db:"id" json:"id"`
	Username               string     `db:"username" json:"username"`
	Email                  string     `db:"email" json:"email"`
	Role                   string     `db:"role" json:"role"`
	FullName               string     `db:"full_name" json:"full_name"`
	Avatar                 string     `db:"avatar" json:"avatar"`
	IsActive               bool       `db:"is_active" json:"is_active"`
	IsAdmin                bool       `db:"is_admin" json:"is_admin"`
	MFAEnabled             bool       `db:"mfa_enabled" json:"mfa_enabled"`
	PasswordChangeRequired bool       `db:"password_change_required" json:"password_change_required"`
	Password               string     `db:"password" json:"-"`
	LastLogin              *time.Time `db:"last_login" json:"last_login"`
	CreatedAt              time.Time  `db:"created_at" json:"created_at"`
	UpdatedAt              time.Time  `db:"updated_at" json:"updated_at"`
	// P1.8: Subscription fields
	SubscriptionPlan      string     `db:"subscription_plan" json:"subscription_plan"`
	SubscriptionStatus    string     `db:"subscription_status" json:"subscription_status"`
	SubscriptionExpiresAt *time.Time `db:"subscription_expires_at" json:"subscription_expires_at"`
	TrialStartedAt        *time.Time `db:"trial_started_at" json:"trial_started_at"`
	TrialEndsAt           *time.Time `db:"trial_ends_at" json:"trial_ends_at"`
}

type UserMFA struct {
	ID                   int        `db:"id" json:"id"`
	UserID               int        `db:"user_id" json:"user_id"`
	EncryptedSecret      string     `db:"encrypted_secret" json:"-"`
	EncryptedBackupCodes string     `db:"encrypted_backup_codes" json:"-"`
	Enabled              bool       `db:"enabled" json:"enabled"`
	VerifiedAt           *time.Time `db:"verified_at" json:"verified_at"`
	LastUsedAt           *time.Time `db:"last_used_at" json:"last_used_at"`
	CreatedAt            time.Time  `db:"created_at" json:"created_at"`
	UpdatedAt            time.Time  `db:"updated_at" json:"updated_at"`
}

// ==================== DYDX KEY MODELS ====================

type DYDXKey struct {
	ID              int       `db:"id" json:"id"`
	UserID          int       `db:"user_id" json:"user_id"`
	Network         string    `db:"network" json:"network"`
	ChainAddress    string    `db:"chain_address" json:"chain_address"`
	EncryptedSecret string    `db:"encrypted_secret" json:"-"`
	SecretHash      string    `db:"secret_hash" json:"-"`
	SecretMasked    string    `db:"secret_masked" json:"secret_masked"`
	IsActive        bool      `db:"is_active" json:"is_active"`
	CreatedAt       time.Time `db:"created_at" json:"created_at"`
	UpdatedAt       time.Time `db:"updated_at" json:"updated_at"`
}

type DYDXKeySettings struct {
	ID                int       `db:"id" json:"id"`
	UserID            int       `db:"user_id" json:"user_id"`
	DefaultNetwork    string    `db:"default_network" json:"default_network"`
	AutoSwitchTestnet bool      `db:"auto_switch_testnet" json:"auto_switch_testnet"`
	CreatedAt         time.Time `db:"created_at" json:"created_at"`
	UpdatedAt         time.Time `db:"updated_at" json:"updated_at"`
}

type ExternalAPICredential struct {
	ID              int       `db:"id" json:"id"`
	UserID          int       `db:"user_id" json:"user_id"`
	Provider        string    `db:"provider" json:"provider"`
	Label           string    `db:"label" json:"label"`
	EncryptedAPIKey string    `db:"encrypted_api_key" json:"-"`
	APIKeyHash      string    `db:"api_key_hash" json:"-"`
	APIKeyMasked    string    `db:"api_key_masked" json:"api_key_masked"`
	IsActive        bool      `db:"is_active" json:"is_active"`
	CreatedAt       time.Time `db:"created_at" json:"created_at"`
	UpdatedAt       time.Time `db:"updated_at" json:"updated_at"`
}

// ==================== SUBSCRIPTION MODELS (P1.8) ====================

type Subscription struct {
	ID                    int        `db:"id" json:"id"`
	UserID                int        `db:"user_id" json:"user_id"`
	Plan                  string     `db:"plan" json:"plan"`     // explorer, performance, enterprise
	Status                string     `db:"status" json:"status"` // trial, active, expired, canceled
	ProfitSharePercentage float64    `db:"profit_share_percentage" json:"profit_share_percentage"`
	StartedAt             time.Time  `db:"started_at" json:"started_at"`
	ExpiresAt             *time.Time `db:"expires_at" json:"expires_at"`
	CanceledAt            *time.Time `db:"canceled_at" json:"canceled_at"`
	TrialStartedAt        *time.Time `db:"trial_started_at" json:"trial_started_at"`
	TrialEndsAt           *time.Time `db:"trial_ends_at" json:"trial_ends_at"`
	CreatedAt             time.Time  `db:"created_at" json:"created_at"`
	UpdatedAt             time.Time  `db:"updated_at" json:"updated_at"`
}

// SubscriptionFeature represents gated product features by subscription tier
type SubscriptionFeature struct {
	ID              int       `db:"id" json:"id"`
	FeatureName     string    `db:"feature_name" json:"feature_name"`
	Description     string    `db:"description" json:"description"`
	ExplorerTier    bool      `db:"explorer_tier" json:"explorer_tier"`
	PerformanceTier bool      `db:"performance_tier" json:"performance_tier"`
	EnterpriseTier  bool      `db:"enterprise_tier" json:"enterprise_tier"`
	CreatedAt       time.Time `db:"created_at" json:"created_at"`
}

type SubscriptionGate struct {
	ID        int    `db:"id" json:"id"`
	UserID    int    `db:"user_id" json:"user_id"`
	FeatureID int    `db:"feature_id" json:"feature_id"`
	Blocked   bool   `db:"blocked" json:"blocked"`
	Reason    string `db:"reason" json:"reason"`
}

// ==================== STRATEGY MODELS ====================

type BacktestStrategy struct {
	ID                     int        `db:"id" json:"id"`
	UserID                 int        `db:"user_id" json:"user_id"`
	Name                   string     `db:"name" json:"name"`
	Description            string     `db:"description" json:"description"`
	Category               string     `db:"category" json:"category"`
	IsPublic               bool       `db:"is_public" json:"is_public"`
	IsDefault              bool       `db:"is_default" json:"is_default"`
	RuntimeStrategy        string     `db:"runtime_strategy" json:"runtime_strategy"`
	RuntimeNetwork         string     `db:"runtime_network" json:"runtime_network"`
	RuntimeSubaccount      int        `db:"runtime_subaccount" json:"runtime_subaccount"`
	PairSelectionMode      string     `db:"pair_selection_mode" json:"pair_selection_mode"`
	ZscoreThreshold        float64    `db:"zscore_threshold" json:"zscore_threshold"`
	StatsWindow            int        `db:"stats_window" json:"stats_window"`
	MaxHalfLife            float64    `db:"max_half_life" json:"max_half_life"`
	UsdPerTrade            float64    `db:"usd_per_trade" json:"usd_per_trade"`
	UsdMinCollateral       float64    `db:"usd_min_collateral" json:"usd_min_collateral"`
	CloseAtZscoreCross     bool       `db:"close_at_zscore_cross" json:"close_at_zscore_cross"`
	FindCointegratedPairs  bool       `db:"find_cointegrated_pairs" json:"find_cointegrated_pairs"`
	ManageExits            bool       `db:"manage_exits" json:"manage_exits"`
	PlaceTrades            bool       `db:"place_trades" json:"place_trades"`
	AbortAllPositions      bool       `db:"abort_all_positions" json:"abort_all_positions"`
	MaxPositions           int        `db:"max_positions" json:"max_positions"`
	MaxDrawdownPct         float64    `db:"max_drawdown_pct" json:"max_drawdown_pct"`
	StopLossPct            float64    `db:"stop_loss_pct" json:"stop_loss_pct"`
	TakeProfitPct          float64    `db:"take_profit_pct" json:"take_profit_pct"`
	TrailingStopPct        float64    `db:"trailing_stop_pct" json:"trailing_stop_pct"`
	RebalanceIntervalHours int        `db:"rebalance_interval_hours" json:"rebalance_interval_hours"`
	PositionTimeoutHours   int        `db:"position_timeout_hours" json:"position_timeout_hours"`
	TransactionFee         float64    `db:"transaction_fee" json:"transaction_fee"`
	Slippage               float64    `db:"slippage" json:"slippage"`
	StartingBalance        float64    `db:"starting_balance" json:"starting_balance"`
	CandleResolution       string     `db:"candle_resolution" json:"candle_resolution"`
	MaxHistoryDays         int        `db:"max_history_days" json:"max_history_days"`
	BenchmarkSymbol        string     `db:"benchmark_symbol" json:"benchmark_symbol"`
	RiskFreeRate           float64    `db:"risk_free_rate" json:"risk_free_rate"`
	InitialAmount          float64    `db:"initial_amount" json:"initial_amount"`
	UsageCount             int        `db:"usage_count" json:"usage_count"`
	LastUsedAt             *time.Time `db:"last_used_at" json:"last_used_at"`
	DeletedAt              *time.Time `db:"deleted_at" json:"deleted_at"`
	CreatedAt              time.Time  `db:"created_at" json:"created_at"`
	UpdatedAt              time.Time  `db:"updated_at" json:"updated_at"`
}

// ==================== BACKTEST RUN MODELS ====================

type BacktestRun struct {
	ID                int            `db:"id" json:"id"`
	UserID            *int           `db:"user_id" json:"user_id"`
	StrategyID        *int           `db:"strategy_id" json:"strategy_id"`
	StrategyVersionID *int           `db:"strategy_version_id" json:"strategy_version_id"`
	RunID             string         `db:"run_id" json:"run_id"`
	Status            string         `db:"status" json:"status"`
	StartDate         string         `db:"start_date" json:"start_date"`
	EndDate           string         `db:"end_date" json:"end_date"`
	NumPairs          int            `db:"num_pairs" json:"num_pairs"`
	TotalMarkets      int            `db:"total_markets" json:"total_markets"`
	Resolution        string         `db:"resolution" json:"resolution"`
	TotalTrades       int            `db:"total_trades" json:"total_trades"`
	ProfitableTrades  int            `db:"profitable_trades" json:"profitable_trades"`
	LosingTrades      int            `db:"losing_trades" json:"losing_trades"`
	WinRate           *float64       `db:"win_rate" json:"win_rate"`
	TotalPnL          float64        `db:"total_pnl" json:"total_pnl"`
	TotalPnLUSD       float64        `db:"total_pnl_usd" json:"total_pnl_usd"`
	SharpeRatio       *float64       `db:"sharpe_ratio" json:"sharpe_ratio"`
	SortinoRatio      *float64       `db:"sortino_ratio" json:"sortino_ratio"`
	CalmarRatio       *float64       `db:"calmar_ratio" json:"calmar_ratio"`
	MaxDrawdown       *float64       `db:"max_drawdown" json:"max_drawdown"`
	ProfitFactor      *float64       `db:"profit_factor" json:"profit_factor"`
	StartingBalance   float64        `db:"starting_balance" json:"starting_balance"`
	EndingBalance     *float64       `db:"ending_balance" json:"ending_balance"`
	MaxBalance        *float64       `db:"max_balance" json:"max_balance"`
	MinBalance        *float64       `db:"min_balance" json:"min_balance"`
	ErrorMessage      string         `db:"error_message" json:"error_message"`
	StartedAt         *time.Time     `db:"started_at" json:"started_at"`
	CompletedAt       *time.Time     `db:"completed_at" json:"completed_at"`
	DurationSeconds   *float64       `db:"duration_seconds" json:"duration_seconds"`
	Config            sql.NullString `db:"config" json:"config"`
	StrategySnapshot  sql.NullString `db:"strategy_snapshot" json:"strategy_snapshot"`
	CreatedAt         time.Time      `db:"created_at" json:"created_at"`
	UpdatedAt         time.Time      `db:"updated_at" json:"updated_at"`
}

// ==================== BACKTEST METRICS MODELS ====================

type BacktestMetrics struct {
	ID                    int       `db:"id" json:"id"`
	RunID                 int       `db:"run_id" json:"run_id"`
	TotalPnl              float64   `db:"total_pnl" json:"total_pnl"`
	TotalReturnPct        float64   `db:"total_return_pct" json:"total_return_pct"`
	TotalTrades           int       `db:"total_trades" json:"total_trades"`
	WinningTrades         int       `db:"winning_trades" json:"winning_trades"`
	LosingTrades          int       `db:"losing_trades" json:"losing_trades"`
	WinRate               float64   `db:"win_rate" json:"win_rate"`
	AvgWin                float64   `db:"avg_win" json:"avg_win"`
	AvgLoss               float64   `db:"avg_loss" json:"avg_loss"`
	ProfitFactor          float64   `db:"profit_factor" json:"profit_factor"`
	MaxDrawdown           float64   `db:"max_drawdown" json:"max_drawdown"`
	MaxDrawdownPct        float64   `db:"max_drawdown_pct" json:"max_drawdown_pct"`
	SharpeRatio           float64   `db:"sharpe_ratio" json:"sharpe_ratio"`
	CalmarRatio           float64   `db:"calmar_ratio" json:"calmar_ratio"`
	MaxConsecutiveLosses  int       `db:"max_consecutive_losses" json:"max_consecutive_losses"`
	AvgTradeDurationHours float64   `db:"avg_trade_duration_hours" json:"avg_trade_duration_hours"`
	CreatedAt             time.Time `db:"created_at" json:"created_at"`
}

// ==================== BACKTEST RESULT MODELS ====================

type BacktestResult struct {
	ID                      int       `db:"id" json:"id"`
	RunID                   int       `db:"run_id" json:"run_id"`
	Market1                 string    `db:"market_1" json:"market_1"`
	Market2                 string    `db:"market_2" json:"market_2"`
	TotalTrades             int       `db:"total_trades" json:"total_trades"`
	EntryTrades             int       `db:"entry_trades" json:"entry_trades"`
	ExitTrades              int       `db:"exit_trades" json:"exit_trades"`
	ProfitableTrades        int       `db:"profitable_trades" json:"profitable_trades"`
	LosingTrades            int       `db:"losing_trades" json:"losing_trades"`
	Pnl                     float64   `db:"pnl" json:"pnl"`
	PnlUSD                  float64   `db:"pnl_usd" json:"pnl_usd"`
	WinRate                 *float64  `db:"win_rate" json:"win_rate"`
	AvgWin                  *float64  `db:"avg_win" json:"avg_win"`
	AvgLoss                 *float64  `db:"avg_loss" json:"avg_loss"`
	ProfitFactor            *float64  `db:"profit_factor" json:"profit_factor"`
	MaxDrawdown             *float64  `db:"max_drawdown" json:"max_drawdown"`
	SharpeRatio             *float64  `db:"sharpe_ratio" json:"sharpe_ratio"`
	SortinoRatio            *float64  `db:"sortino_ratio" json:"sortino_ratio"`
	CalmarRatio             *float64  `db:"calmar_ratio" json:"calmar_ratio"`
	AvgTradeDurationHours   *float64  `db:"avg_trade_duration_hours" json:"avg_trade_duration_hours"`
	AvgWinningTradeDuration *float64  `db:"avg_winning_trade_duration" json:"avg_winning_trade_duration"`
	AvgLosingTradeDuration  *float64  `db:"avg_losing_trade_duration" json:"avg_losing_trade_duration"`
	CointegrationScore      *float64  `db:"cointegration_score" json:"cointegration_score"`
	Correlation             *float64  `db:"correlation" json:"correlation"`
	ZscoreMean              *float64  `db:"zscore_mean" json:"zscore_mean"`
	ZscoreStd               *float64  `db:"zscore_std" json:"zscore_std"`
	CreatedAt               time.Time `db:"created_at" json:"created_at"`
	UpdatedAt               time.Time `db:"updated_at" json:"updated_at"`
}

// ==================== BACKTEST TRADE MODELS ====================

type BacktestTrade struct {
	ID                      int        `db:"id" json:"id"`
	RunID                   int        `db:"run_id" json:"run_id"`
	TradeID                 string     `db:"trade_id" json:"trade_id"`
	Market1                 string     `db:"market_1" json:"market_1"`
	Market2                 string     `db:"market_2" json:"market_2"`
	EntryPrice1             float64    `db:"entry_price_1" json:"entry_price_1"`
	EntryPrice2             float64    `db:"entry_price_2" json:"entry_price_2"`
	EntryZScore             float64    `db:"entry_z_score" json:"entry_z_score"`
	ExitPrice1              *float64   `db:"exit_price_1" json:"exit_price_1"`
	ExitPrice2              *float64   `db:"exit_price_2" json:"exit_price_2"`
	ExitZScore              *float64   `db:"exit_z_score" json:"exit_z_score"`
	Side1                   string     `db:"side_1" json:"side_1"`
	Side2                   string     `db:"side_2" json:"side_2"`
	Size1                   float64    `db:"size_1" json:"size_1"`
	Size2                   float64    `db:"size_2" json:"size_2"`
	HedgeRatio              float64    `db:"hedge_ratio" json:"hedge_ratio"`
	TransactionFee          float64    `db:"transaction_fee" json:"transaction_fee"`
	Slippage                float64    `db:"slippage" json:"slippage"`
	Pnl                     *float64   `db:"pnl" json:"pnl"`
	PnlPct                  *float64   `db:"pnl_pct" json:"pnl_pct"`
	DurationHours           *float64   `db:"duration_hours" json:"duration_hours"`
	EntryTimestamp          time.Time  `db:"entry_timestamp" json:"entry_timestamp"`
	ExitTimestamp           *time.Time `db:"exit_timestamp" json:"exit_timestamp"`
	StrategyID              *int       `db:"strategy_id" json:"strategy_id"`
	StrategyName            *string    `db:"strategy_name" json:"strategy_name"`
	StrategyZscoreThreshold *float64   `db:"strategy_zscore_threshold" json:"strategy_zscore_threshold"`
}

// ==================== BACKTEST CANDLE MODELS ====================

type BacktestCandle struct {
	ID          int       `db:"id" json:"id"`
	RunID       int       `db:"run_id" json:"run_id"`
	Market      string    `db:"market" json:"market"`
	Resolution  string    `db:"resolution" json:"resolution"`
	OpenPrice   float64   `db:"open_price" json:"open_price"`
	HighPrice   float64   `db:"high_price" json:"high_price"`
	LowPrice    float64   `db:"low_price" json:"low_price"`
	ClosePrice  float64   `db:"close_price" json:"close_price"`
	Volume      float64   `db:"volume" json:"volume"`
	TradesCount int       `db:"trades_count" json:"trades_count"`
	Timestamp   time.Time `db:"timestamp" json:"timestamp"`
}

// ==================== BACKTEST POSITION MODELS ====================

type BacktestPosition struct {
	ID             int        `db:"id" json:"id"`
	RunID          int        `db:"run_id" json:"run_id"`
	PositionID     string     `db:"position_id" json:"position_id"`
	Market1        string     `db:"market_1" json:"market_1"`
	Market2        string     `db:"market_2" json:"market_2"`
	Status         string     `db:"status" json:"status"`
	EntryPrice1    float64    `db:"entry_price_1" json:"entry_price_1"`
	EntryPrice2    float64    `db:"entry_price_2" json:"entry_price_2"`
	EntryZScore    *float64   `db:"entry_z_score" json:"entry_z_score"`
	ExitPrice1     *float64   `db:"exit_price_1" json:"exit_price_1"`
	ExitPrice2     *float64   `db:"exit_price_2" json:"exit_price_2"`
	CurrentPrice1  *float64   `db:"current_price_1" json:"current_price_1"`
	CurrentPrice2  *float64   `db:"current_price_2" json:"current_price_2"`
	CurrentZScore  *float64   `db:"current_z_score" json:"current_z_score"`
	Side1          string     `db:"side_1" json:"side_1"`
	Side2          string     `db:"side_2" json:"side_2"`
	Size1          float64    `db:"size_1" json:"size_1"`
	Size2          float64    `db:"size_2" json:"size_2"`
	HedgeRatio     float64    `db:"hedge_ratio" json:"hedge_ratio"`
	UnrealizedPnl  *float64   `db:"unrealized_pnl" json:"unrealized_pnl"`
	RealizedPnl    *float64   `db:"realized_pnl" json:"realized_pnl"`
	EntryTimestamp time.Time  `db:"entry_timestamp" json:"entry_timestamp"`
	ExitTimestamp  *time.Time `db:"exit_timestamp" json:"exit_timestamp"`
}

// ==================== ADDITIONAL MODELS ====================

type BacktestLog struct {
	ID        int       `db:"id" json:"id"`
	RunID     int       `db:"run_id" json:"run_id"`
	Level     string    `db:"level" json:"level"`
	Message   string    `db:"message" json:"message"`
	Timestamp time.Time `db:"timestamp" json:"timestamp"`
}

type AuditLog struct {
	ID           int         `db:"id" json:"id"`
	UserID       *int        `db:"user_id" json:"user_id"`
	Action       string      `db:"action" json:"action"`
	ResourceType string      `db:"resource_type" json:"resource_type"`
	ResourceID   *string     `db:"resource_id" json:"resource_id"`
	Details      interface{} `db:"details" json:"details"`
	Status       *string     `db:"status" json:"status"`
	IPAddress    *string     `db:"ip_address" json:"ip_address"`
	CreatedAt    *time.Time  `db:"created_at" json:"created_at"`
}

type TradeLog struct {
	ID             int        `db:"id" json:"id"`
	ResultIDFK     int        `db:"result_id_fk" json:"result_id_fk"`
	TradeNumber    *int       `db:"trade_number" json:"trade_number"`
	EntryPrice1    *float64   `db:"entry_price_1" json:"entry_price_1"`
	EntryPrice2    *float64   `db:"entry_price_2" json:"entry_price_2"`
	ExitPrice1     *float64   `db:"exit_price_1" json:"exit_price_1"`
	ExitPrice2     *float64   `db:"exit_price_2" json:"exit_price_2"`
	Quantity1      *float64   `db:"quantity_1" json:"quantity_1"`
	Quantity2      *float64   `db:"quantity_2" json:"quantity_2"`
	Side1          *string    `db:"side_1" json:"side_1"`
	Side2          *string    `db:"side_2" json:"side_2"`
	Pnl            *float64   `db:"pnl" json:"pnl"`
	PnlUSD         *float64   `db:"pnl_usd" json:"pnl_usd"`
	EntryZScore    *float64   `db:"entry_zscore" json:"entry_zscore"`
	ExitZScore     *float64   `db:"exit_zscore" json:"exit_zscore"`
	EntryTimestamp *time.Time `db:"entry_timestamp" json:"entry_timestamp"`
	ExitTimestamp  *time.Time `db:"exit_timestamp" json:"exit_timestamp"`
	CreatedAt      time.Time  `db:"created_at" json:"created_at"`
}

type BotSetting struct {
	ID           int       `db:"id" json:"id"`
	Section      string    `db:"section" json:"section"`
	Key          string    `db:"key" json:"key"`
	Value        string    `db:"value" json:"value"`
	ValueType    string    `db:"value_type" json:"value_type"`
	Description  string    `db:"description" json:"description"`
	DefaultValue string    `db:"default_value" json:"default_value"`
	IsActive     bool      `db:"is_active" json:"is_active"`
	Version      int       `db:"version" json:"version"`
	CreatedAt    time.Time `db:"created_at" json:"created_at"`
	UpdatedAt    time.Time `db:"updated_at" json:"updated_at"`
}

type InvitationToken struct {
	ID               int        `db:"id" json:"id"`
	TokenCode        string     `db:"token_code" json:"token_code"`
	Label            string     `db:"label" json:"label"`
	IBName           string     `db:"ib_name" json:"ib_name"`
	CampaignName     string     `db:"campaign_name" json:"campaign_name"`
	MaxUses          int        `db:"max_uses" json:"max_uses"`
	UsedCount        int        `db:"used_count" json:"used_count"`
	CreatedByUserID  *int       `db:"created_by_user_id" json:"created_by_user_id"`
	LastUsedByUserID *int       `db:"last_used_by_user_id" json:"last_used_by_user_id"`
	ExpiresAt        *time.Time `db:"expires_at" json:"expires_at"`
	LastUsedAt       *time.Time `db:"last_used_at" json:"last_used_at"`
	RevokedAt        *time.Time `db:"revoked_at" json:"revoked_at"`
	CreatedAt        time.Time  `db:"created_at" json:"created_at"`
	UpdatedAt        time.Time  `db:"updated_at" json:"updated_at"`
}

type PartnerApplication struct {
	ID               int        `db:"id" json:"id"`
	ApplicantUserID  int        `db:"applicant_user_id" json:"applicant_user_id"`
	SponsorUserID    *int       `db:"sponsor_user_id" json:"sponsor_user_id"`
	RequestedRole    string     `db:"requested_role" json:"requested_role"`
	Status           string     `db:"status" json:"status"`
	BusinessName     string     `db:"business_name" json:"business_name"`
	Notes            string     `db:"notes" json:"notes"`
	ReviewNotes      string     `db:"review_notes" json:"review_notes"`
	ReviewedByUserID *int       `db:"reviewed_by_user_id" json:"reviewed_by_user_id"`
	ReviewedAt       *time.Time `db:"reviewed_at" json:"reviewed_at"`
	CreatedAt        time.Time  `db:"created_at" json:"created_at"`
	UpdatedAt        time.Time  `db:"updated_at" json:"updated_at"`
}

type PartnerRelationship struct {
	ID                  int       `db:"id" json:"id"`
	SponsorUserID       int       `db:"sponsor_user_id" json:"sponsor_user_id"`
	PartnerUserID       int       `db:"partner_user_id" json:"partner_user_id"`
	RelationshipType    string    `db:"relationship_type" json:"relationship_type"`
	SourceApplicationID *int      `db:"source_application_id" json:"source_application_id"`
	IsActive            bool      `db:"is_active" json:"is_active"`
	CreatedAt           time.Time `db:"created_at" json:"created_at"`
	UpdatedAt           time.Time `db:"updated_at" json:"updated_at"`
}

type PartnerCommissionMetric struct {
	ID                 int       `db:"id" json:"id"`
	UserID             int       `db:"user_id" json:"user_id"`
	PeriodStart        time.Time `db:"period_start" json:"period_start"`
	PeriodEnd          time.Time `db:"period_end" json:"period_end"`
	DirectClients      int       `db:"direct_clients" json:"direct_clients"`
	SubIBCount         int       `db:"sub_ib_count" json:"sub_ib_count"`
	NotionalVolumeUSD  float64   `db:"notional_volume_usd" json:"notional_volume_usd"`
	GrossCommissionUSD float64   `db:"gross_commission_usd" json:"gross_commission_usd"`
	RebateUSD          float64   `db:"rebate_usd" json:"rebate_usd"`
	NetCommissionUSD   float64   `db:"net_commission_usd" json:"net_commission_usd"`
	CreatedAt          time.Time `db:"created_at" json:"created_at"`
	UpdatedAt          time.Time `db:"updated_at" json:"updated_at"`
}

type RedisSetting struct {
	ID        int       `db:"id" json:"id"`
	Enabled   bool      `db:"enabled" json:"enabled"`
	Host      string    `db:"host" json:"host"`
	Port      int       `db:"port" json:"port"`
	Db        int       `db:"db" json:"db"`
	Password  string    `db:"password" json:"password"`
	SSL       bool      `db:"ssl" json:"ssl"`
	CreatedAt time.Time `db:"created_at" json:"created_at"`
	UpdatedAt time.Time `db:"updated_at" json:"updated_at"`
}

type BacktestComparison struct {
	ID             int            `db:"id" json:"id"`
	UserID         int            `db:"user_id" json:"user_id"`
	Run1ID         int            `db:"run_1_id" json:"run_1_id"`
	Run2ID         int            `db:"run_2_id" json:"run_2_id"`
	Strategy1ID    int            `db:"strategy_1_id" json:"strategy_1_id"`
	Strategy2ID    int            `db:"strategy_2_id" json:"strategy_2_id"`
	ComparisonData sql.NullString `db:"comparison_data" json:"comparison_data"`
	CreatedAt      time.Time      `db:"created_at" json:"created_at"`
}

type StrategyExecutionState struct {
	ID         int            `db:"id" json:"id"`
	StrategyID int            `db:"strategy_id" json:"strategy_id"`
	IsRunning  bool           `db:"is_running" json:"is_running"`
	LastRunAt  *time.Time     `db:"last_run_at" json:"last_run_at"`
	NextRunAt  *time.Time     `db:"next_run_at" json:"next_run_at"`
	State      sql.NullString `db:"state" json:"state"`
	CreatedAt  time.Time      `db:"created_at" json:"created_at"`
	UpdatedAt  time.Time      `db:"updated_at" json:"updated_at"`
}

type StrategyVersionHistory struct {
	ID              int            `db:"id" json:"id"`
	StrategyID      int            `db:"strategy_id" json:"strategy_id"`
	CreatedByUserID int            `db:"created_by_user_id" json:"created_by_user_id"`
	Version         int            `db:"version_number" json:"version_number"`
	StrategyData    sql.NullString `db:"config_snapshot" json:"config_snapshot"`
	ChangeLog       string         `db:"change_description" json:"change_description"`
	CreatedAt       time.Time      `db:"created_at" json:"created_at"`
	UpdatedAt       time.Time      `db:"updated_at" json:"updated_at"`
}

// ==================== COINTEGRATION MODELS ====================

type CointegrationResult struct {
	ID                int       `db:"id" json:"id"`
	BaseMarket        string    `db:"base_market" json:"base_market"`
	QuoteMarket       string    `db:"quote_market" json:"quote_market"`
	HedgeRatio        float64   `db:"hedge_ratio" json:"hedge_ratio"`
	HalfLife          float64   `db:"half_life" json:"half_life"`
	ZeroCrossings     int       `db:"zero_crossings" json:"zero_crossings"`
	PValue            float64   `db:"p_value" json:"p_value"`
	ZScoreMean        float64   `db:"z_score_mean" json:"z_score_mean"`
	ZScoreStd         float64   `db:"z_score_std" json:"zscore_std"`
	AnalysisTimestamp string    `db:"analysis_timestamp" json:"analysis_timestamp"`
	ConfidenceScore   float64   `db:"confidence_score" json:"confidence_score"`
	CreatedAt         time.Time `db:"created_at" json:"created_at"`
	UpdatedAt         time.Time `db:"updated_at" json:"updated_at"`
}

// ==================== BOT INSTANCE MODELS ====================

type BotInstance struct {
	ID              int            `db:"id" json:"id"`
	InstanceID      string         `db:"instance_id" json:"instance_id"`
	InstanceName    string         `db:"instance_name" json:"instance_name"`
	UserID          int            `db:"user_id" json:"user_id"`
	Status          string         `db:"status" json:"status"`   // running, stopped, error, paused
	Network         string         `db:"network" json:"network"` // testnet, mainnet
	Strategy        string         `db:"strategy" json:"strategy"`
	Config          sql.NullString `db:"config" json:"config"`
	TradingParams   sql.NullString `db:"trading_params" json:"trading_params"`
	TotalTrades     int            `db:"total_trades" json:"total_trades"`
	TotalPnL        *float64       `db:"total_pnl" json:"total_pnl"`
	CurrentBalance  *float64       `db:"current_balance" json:"current_balance"`
	StartingBalance *float64       `db:"starting_balance" json:"starting_balance"`
	ProcessID       *int           `db:"process_id" json:"process_id"`
	PID             *string        `db:"pid" json:"pid"`
	Host            *string        `db:"host" json:"host"`
	Port            *int           `db:"port" json:"port"`
	ErrorMessage    *string        `db:"error_message" json:"error_message"`
	LastErrorAt     *time.Time     `db:"last_error_at" json:"last_error_at"`
	StartedAt       *time.Time     `db:"started_at" json:"started_at"`
	StoppedAt       *time.Time     `db:"stopped_at" json:"stopped_at"`
	CreatedAt       time.Time      `db:"created_at" json:"created_at"`
	UpdatedAt       time.Time      `db:"updated_at" json:"updated_at"`
}

type BotTrade struct {
	ID                      int        `db:"id" json:"id"`
	BotInstanceID           int        `db:"bot_instance_id" json:"bot_instance_id"`
	TradeID                 string     `db:"trade_id" json:"trade_id"`
	Market1                 string     `db:"market_1" json:"market_1"`
	Market2                 string     `db:"market_2" json:"market_2"`
	EntryTimestamp          time.Time  `db:"entry_timestamp" json:"entry_timestamp"`
	EntryPrice1             float64    `db:"entry_price_1" json:"entry_price_1"`
	EntryPrice2             float64    `db:"entry_price_2" json:"entry_price_2"`
	EntryZScore             *float64   `db:"entry_zscore" json:"entry_zscore"`
	Side1                   string     `db:"side_1" json:"side_1"`
	Side2                   string     `db:"side_2" json:"side_2"`
	Size1                   float64    `db:"size_1" json:"size_1"`
	Size2                   float64    `db:"size_2" json:"size_2"`
	HedgeRatio              *float64   `db:"hedge_ratio" json:"hedge_ratio"`
	ExitTimestamp           *time.Time `db:"exit_timestamp" json:"exit_timestamp"`
	ExitPrice1              *float64   `db:"exit_price_1" json:"exit_price_1"`
	ExitPrice2              *float64   `db:"exit_price_2" json:"exit_price_2"`
	ExitZScore              *float64   `db:"exit_zscore" json:"exit_zscore"`
	PnL                     *float64   `db:"pnl" json:"pnl"`
	PnLPct                  *float64   `db:"pnl_pct" json:"pnl_pct"`
	DurationHours           *float64   `db:"duration_hours" json:"duration_hours"`
	StrategyZscoreThreshold *float64   `db:"strategy_zscore_threshold" json:"strategy_zscore_threshold"`
	CreatedAt               time.Time  `db:"created_at" json:"created_at"`
	UpdatedAt               time.Time  `db:"updated_at" json:"updated_at"`
}

type BotPosition struct {
	ID               int        `db:"id" json:"id"`
	BotInstanceID    int        `db:"bot_instance_id" json:"bot_instance_id"`
	PositionID       string     `db:"position_id" json:"position_id"`
	Market1          string     `db:"market_1" json:"market_1"`
	Market2          string     `db:"market_2" json:"market_2"`
	Status           string     `db:"status" json:"status"` // open, closed, error
	IsActive         int        `db:"is_active" json:"is_active"`
	EntryTimestamp   time.Time  `db:"entry_timestamp" json:"entry_timestamp"`
	EntryPrice1      float64    `db:"entry_price_1" json:"entry_price_1"`
	EntryPrice2      float64    `db:"entry_price_2" json:"entry_price_2"`
	EntryZScore      *float64   `db:"entry_zscore" json:"entry_zscore"`
	Side1            string     `db:"side_1" json:"side_1"`
	Side2            string     `db:"side_2" json:"side_2"`
	Size1            float64    `db:"size_1" json:"size_1"`
	Size2            float64    `db:"size_2" json:"size_2"`
	HedgeRatio       *float64   `db:"hedge_ratio" json:"hedge_ratio"`
	CurrentPrice1    *float64   `db:"current_price_1" json:"current_price_1"`
	CurrentPrice2    *float64   `db:"current_price_2" json:"current_price_2"`
	CurrentZScore    *float64   `db:"current_zscore" json:"current_zscore"`
	UnrealizedPnL    *float64   `db:"unrealized_pnl" json:"unrealized_pnl"`
	UnrealizedPnLPct *float64   `db:"unrealized_pnl_pct" json:"unrealized_pnl_pct"`
	ExitTimestamp    *time.Time `db:"exit_timestamp" json:"exit_timestamp"`
	ExitPrice1       *float64   `db:"exit_price_1" json:"exit_price_1"`
	ExitPrice2       *float64   `db:"exit_price_2" json:"exit_price_2"`
	ExitZScore       *float64   `db:"exit_zscore" json:"exit_zscore"`
	RealizedPnL      *float64   `db:"realized_pnl" json:"realized_pnl"`
	RealizedPnLPct   *float64   `db:"realized_pnl_pct" json:"realized_pnl_pct"`
	DurationHours    *float64   `db:"duration_hours" json:"duration_hours"`
	CreatedAt        time.Time  `db:"created_at" json:"created_at"`
	UpdatedAt        time.Time  `db:"updated_at" json:"updated_at"`
}

type BotAlert struct {
	ID             int            `db:"id" json:"id"`
	BotInstanceID  int            `db:"bot_instance_id" json:"bot_instance_id"`
	AlertType      string         `db:"alert_type" json:"alert_type"`
	Severity       string         `db:"severity" json:"severity"`
	Title          string         `db:"title" json:"title"`
	Message        string         `db:"message" json:"message"`
	Details        sql.NullString `db:"details" json:"details"`
	IsRead         int            `db:"is_read" json:"is_read"`
	AcknowledgedAt *time.Time     `db:"acknowledged_at" json:"acknowledged_at"`
	CreatedAt      time.Time      `db:"created_at" json:"created_at"`
	UpdatedAt      time.Time      `db:"updated_at" json:"updated_at"`
}
