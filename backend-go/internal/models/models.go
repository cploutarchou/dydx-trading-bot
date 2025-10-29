package models

import (
	"database/sql"
	"time"
)

// ==================== USER MODELS ====================

type User struct {
	ID        int        `db:"id" json:"id"`
	Username  string     `db:"username" json:"username"`
	Email     string     `db:"email" json:"email"`
	FullName  string     `db:"full_name" json:"full_name"`
	Avatar    string     `db:"avatar" json:"avatar"`
	IsActive  bool       `db:"is_active" json:"is_active"`
	IsAdmin   bool       `db:"is_admin" json:"is_admin"`
	Password  string     `db:"password" json:"-"`
	LastLogin *time.Time `db:"last_login" json:"last_login"`
	CreatedAt time.Time  `db:"created_at" json:"created_at"`
	UpdatedAt time.Time  `db:"updated_at" json:"updated_at"`
}

// ==================== DYDX KEY MODELS ====================

type DYDXKey struct {
	ID              int       `db:"id" json:"id"`
	UserID          int       `db:"user_id" json:"user_id"`
	Network         string    `db:"network" json:"network"`
	ChainAddress    string    `db:"chain_address" json:"chain_address"`
	EncryptedSecret string    `db:"encrypted_secret" json:"-"`
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

// ==================== STRATEGY MODELS ====================

type BacktestStrategy struct {
	ID                     int        `db:"id" json:"id"`
	UserID                 int        `db:"user_id" json:"user_id"`
	Name                   string     `db:"name" json:"name"`
	Description            string     `db:"description" json:"description"`
	Category               string     `db:"category" json:"category"`
	IsPublic               bool       `db:"is_public" json:"is_public"`
	IsDefault              bool       `db:"is_default" json:"is_default"`
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
	ID         int            `db:"id" json:"id"`
	UserID     int            `db:"user_id" json:"user_id"`
	Action     string         `db:"action" json:"action"`
	Resource   string         `db:"resource" json:"resource"`
	ResourceID int            `db:"resource_id" json:"resource_id"`
	Details    sql.NullString `db:"details" json:"details"`
	CreatedAt  time.Time      `db:"created_at" json:"created_at"`
}

type TradeLog struct {
	ID        int            `db:"id" json:"id"`
	ResultID  int            `db:"result_id" json:"result_id"`
	TradeID   string         `db:"trade_id" json:"trade_id"`
	EntryTime time.Time      `db:"entry_time" json:"entry_time"`
	ExitTime  *time.Time     `db:"exit_time" json:"exit_time"`
	Pnl       *float64       `db:"pnl" json:"pnl"`
	Details   sql.NullString `db:"details" json:"details"`
	CreatedAt time.Time      `db:"created_at" json:"created_at"`
}

type BotSetting struct {
	ID          int       `db:"id" json:"id"`
	UpdatedByID int       `db:"updated_by_id" json:"updated_by_id"`
	Key         string    `db:"key" json:"key"`
	Value       string    `db:"value" json:"value"`
	Description string    `db:"description" json:"description"`
	Category    string    `db:"category" json:"category"`
	CreatedAt   time.Time `db:"created_at" json:"created_at"`
	UpdatedAt   time.Time `db:"updated_at" json:"updated_at"`
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
	Version         int            `db:"version" json:"version"`
	StrategyData    sql.NullString `db:"strategy_data" json:"strategy_data"`
	ChangeLog       string         `db:"change_log" json:"change_log"`
	CreatedAt       time.Time      `db:"created_at" json:"created_at"`
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
