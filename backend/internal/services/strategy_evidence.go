package services

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

// The strategy evidence is the data block the analysis prompts (parameter
// suggestions, backtest explanations, the strategy chat) and market selection
// reason over: completed backtests of one strategy, the per-pair ledger of
// the latest run, the live runtime's closed trades, open positions and entry
// halt, and the bot's stored pair scan. Every field is picked explicitly from
// the mirror rows and the bot payloads; nothing that identifies the user, the
// account or the deployment is copied. Units are converted in one place: money
// is USD, rates are percent, durations are hours.

// StrategyEvidenceSource gives market selection the pair statistics of a
// strategy the caller owns. botToken is the caller's bot API token, forwarded
// only on deployments without a service token.
type StrategyEvidenceSource interface {
	PairStatsForStrategy(ctx context.Context, userID int, isAdmin bool, strategyID int, botToken string) (pairs []EvidencePairStats, cointegrated []EvidenceCointegratedPair, notes []string, err error)
}

// Data notes the builder emits; the exact strings are test fixtures.
const (
	evidenceNoteUnits               = "Evidence units: money in USD, rates in percent (55 means 55%), durations in hours."
	evidenceNoteNoRuns              = "No completed backtests of this strategy were found."
	evidenceNoteRunsUnavailable     = "Backtest history could not be loaded for this reply."
	evidenceNoteLedgerMissing       = "The trade ledger of the latest run is not available; per-pair figures are missing."
	evidenceNoteCostsUnknown        = "Fee and slippage costs are not recorded per trade in this run."
	evidenceNoteLiveUnavailable     = "Live runtime data could not be read; treat the runtime as unknown."
	evidenceNoteNeverStarted        = "The strategy has never been started."
	evidenceNoteEntryHalt           = "Entry halt state could not be read."
	evidenceNoteNoPairScan          = "No stored pair scan is available for this strategy's runtime."
	evidenceNotePairScanUnavailable = "The stored pair scan could not be read."
	evidenceNoteLiveSkipped         = "Live runtime data was not requested."
	evidenceNoteTruncated           = "Some pair and position detail was omitted to keep the data block small."
	evidenceNoteLiveSnapshot        = "Live figures are a snapshot taken when this reply was prepared."
)

const (
	evidenceDefaultRuns          = 5
	evidenceMaxRuns              = 10
	evidenceDefaultTradeLimit    = 2000
	evidenceMaxTradeLimit        = 5000
	evidenceDefaultPairs         = 12
	evidenceMaxPairs             = 40
	evidenceDefaultLiveTimeout   = 4 * time.Second
	evidenceDefaultLedgerTimeout = 8 * time.Second
	evidenceLiveTradeCap         = 5000
	evidenceMaxOpenPositions     = 30
	evidenceMaxCointegrated      = 12
	evidenceMaxBytes             = 16 * 1024
)

// evidenceTickerPattern is the only shape a market ticker copied from a bot
// payload may have.
var evidenceTickerPattern = regexp.MustCompile(`^[A-Z0-9]+-[A-Z0-9]+$`)

// AIEvidenceSummary is the count of what the evidence holds, shown by the UI
// as "based on N runs, M trades, ...". Field names are part of the frontend
// contract.
type AIEvidenceSummary struct {
	CompletedRuns     int      `json:"completed_runs"`
	TradesAnalysed    int      `json:"trades_analysed"`
	PairsAnalysed     int      `json:"pairs_analysed"`
	LiveClosedTrades  int      `json:"live_closed_trades"`
	LiveOpenPositions int      `json:"live_open_positions"`
	LiveAvailable     bool     `json:"live_available"`
	CointegratedPairs int      `json:"cointegrated_pairs"`
	DataNotes         []string `json:"data_notes"`
}

// StrategyEvidence is the data block as the prompts see it.
type StrategyEvidence struct {
	Backtests     EvidenceBacktests      `json:"backtests"`
	Live          *EvidenceLive          `json:"live"`
	Cointegration *EvidenceCointegration `json:"cointegration"`
	DataNotes     []string               `json:"data_notes"`
	// Summary is for the API response, not for the prompt.
	Summary AIEvidenceSummary `json:"-"`
}

// EvidenceBacktests holds the completed runs of the strategy and the per-pair
// ledger of the newest one.
type EvidenceBacktests struct {
	CompletedRuns []EvidenceRun   `json:"completed_runs"`
	LatestRun     *EvidenceLedger `json:"latest_run"`
}

// EvidenceRun is one completed run from the backtest_runs mirror.
type EvidenceRun struct {
	RunRef         string         `json:"run_ref"`
	StartDate      string         `json:"start_date,omitempty"`
	EndDate        string         `json:"end_date,omitempty"`
	Resolution     string         `json:"resolution,omitempty"`
	NumPairs       int            `json:"num_pairs"`
	TotalTrades    int            `json:"total_trades"`
	WinRatePct     *float64       `json:"win_rate_pct"`
	TotalPnLUSD    float64        `json:"total_pnl_usd"`
	SharpeRatio    *float64       `json:"sharpe_ratio"`
	MaxDrawdownPct *float64       `json:"max_drawdown_pct"`
	ProfitFactor   *float64       `json:"profit_factor"`
	CompletedAt    string         `json:"completed_at,omitempty"`
	Settings       map[string]any `json:"settings,omitempty"`
}

// EvidenceLedger is the per-pair aggregate of one run's trades.
type EvidenceLedger struct {
	RunRef              string                `json:"run_ref"`
	TradesAnalysed      int                   `json:"trades_analysed"`
	TradesTotal         int                   `json:"trades_total"`
	Truncated           bool                  `json:"truncated"`
	Wins                int                   `json:"wins"`
	WinRatePct          float64               `json:"win_rate_pct"`
	PnLUSD              float64               `json:"pnl_usd"`
	CostsKnown          bool                  `json:"costs_known"`
	FeesUSD             *float64              `json:"fees_usd"`
	SlippageUSD         *float64              `json:"slippage_usd"`
	AvgDurationHours    float64               `json:"avg_duration_hours"`
	MedianDurationHours float64               `json:"median_duration_hours"`
	AvgAbsEntryZScore   float64               `json:"avg_abs_entry_zscore"`
	ExitReasons         map[string]int        `json:"exit_reasons,omitempty"`
	DrawdownHalt        *EvidenceDrawdownHalt `json:"drawdown_halt"`
	MarketDataNetwork   string                `json:"market_data_network,omitempty"`
	Pairs               []EvidencePairStats   `json:"pairs"`
	PairsOmitted        int                   `json:"pairs_omitted"`
	Other               *EvidencePairStats    `json:"other_pairs,omitempty"`
}

// EvidencePairStats is the aggregate of one pair's closed trades: from a
// backtest ledger or from the live runtime. Money is USD, rates are percent.
type EvidencePairStats struct {
	Pair             string         `json:"pair"` // "BTC-USD/ETH-USD"
	Trades           int            `json:"trades"`
	Wins             int            `json:"wins"`
	WinRatePct       float64        `json:"win_rate_pct"`
	PnLUSD           float64        `json:"pnl_usd"`
	FeesUSD          *float64       `json:"fees_usd"`
	AvgPnLPct        float64        `json:"avg_pnl_pct"` // mean of pnl_pct, percent of the size per trade
	AvgDurationHours float64        `json:"avg_duration_hours"`
	MaxWinUSD        float64        `json:"max_win_usd"`
	MaxLossUSD       float64        `json:"max_loss_usd"`
	ExitReasons      map[string]int `json:"exit_reasons,omitempty"`
}

// EvidenceDrawdownHalt is the run's drawdown-limit record.
type EvidenceDrawdownHalt struct {
	LimitPct      float64 `json:"limit_pct"`
	Reached       bool    `json:"reached"`
	TradesSkipped int     `json:"trades_skipped"`
}

// EvidenceLive is the strategy's runtime as the bot reported it.
type EvidenceLive struct {
	Available       bool                   `json:"available"`
	ActiveOrUnknown bool                   `json:"active_or_unknown"`
	Status          string                 `json:"status"`
	Network         string                 `json:"network,omitempty"`
	LastConfirmedAt string                 `json:"last_confirmed_at,omitempty"`
	ClosedTrades    *EvidenceLiveTrades    `json:"closed_trades"`
	OpenPositions   []EvidenceOpenPosition `json:"open_positions"`
	Exposure        *EvidenceExposure      `json:"exposure"`
	EntryHalt       *EvidenceEntryHalt     `json:"entry_halt"`
}

// EvidenceLiveTrades aggregates the runtime's closed trades.
type EvidenceLiveTrades struct {
	Count            int                 `json:"count"`
	Wins             int                 `json:"wins"`
	WinRatePct       float64             `json:"win_rate_pct"`
	RealizedPnLUSD   float64             `json:"realized_pnl_usd"`
	AvgDurationHours float64             `json:"avg_duration_hours"`
	Truncated        bool                `json:"truncated"`
	Pairs            []EvidencePairStats `json:"pairs"`
	PairsOmitted     int                 `json:"pairs_omitted"`
}

// EvidenceOpenPosition is one open pair position.
type EvidenceOpenPosition struct {
	Pair             string   `json:"pair"`
	UnrealizedPnLUSD float64  `json:"unrealized_pnl_usd"`
	UnrealizedPnLPct float64  `json:"unrealized_pnl_pct"`
	ZScoreEntry      *float64 `json:"zscore_entry"`
	ZScoreCurrent    *float64 `json:"zscore_current"`
	OpenHours        float64  `json:"open_hours"`
}

// EvidenceExposure is the runtime's open exposure from its realtime stats.
type EvidenceExposure struct {
	OpenPositions         int     `json:"open_positions"`
	TotalUnrealizedPnLUSD float64 `json:"total_unrealized_pnl_usd"`
	TotalUnrealizedPnLPct float64 `json:"total_unrealized_pnl_pct"`
}

// EvidenceEntryHalt is the allowlisted part of the bot's entry halt: never
// the address, the subaccount or the instance id.
type EvidenceEntryHalt struct {
	Halted     bool   `json:"halted"`
	Unverified bool   `json:"unverified"`
	Kind       string `json:"kind,omitempty"`
	Reason     string `json:"reason,omitempty"`
	HaltedAt   string `json:"halted_at,omitempty"`
}

// EvidenceCointegration is the bot's stored pair scan of the runtime.
type EvidenceCointegration struct {
	AnalyzedAt   string                     `json:"analyzed_at,omitempty"`
	Count        int                        `json:"count"`
	Pairs        []EvidenceCointegratedPair `json:"pairs"`
	PairsOmitted int                        `json:"pairs_omitted"`
}

// EvidenceCointegratedPair is one row of the bot's stored pair scan for the
// strategy's runtime instance. Statistics the old bot does not send stay nil.
type EvidenceCointegratedPair struct {
	Pair          string   `json:"pair"`
	HedgeRatio    *float64 `json:"hedge_ratio"`
	HalfLife      *float64 `json:"half_life"`
	PValue        *float64 `json:"p_value"`
	ZScoreMean    *float64 `json:"z_score_mean"`
	ZScoreStd     *float64 `json:"z_score_std"`
	Confidence    *float64 `json:"confidence"`
	ZeroCrossings *int     `json:"zero_crossings"`
	AnalyzedAt    string   `json:"analyzed_at,omitempty"`
}

// EvidenceOptions bounds one Build.
type EvidenceOptions struct {
	Runs        int           // completed runs listed; default 5, max 10
	TradeLimit  int           // trades of the latest run analysed; default 2000, max 5000
	Pairs       int           // pairs kept per ledger, the rest folded; default 12
	IncludeLive bool          // read the live runtime
	LiveTimeout time.Duration // per live bot call; default 4 s
	// LedgerTimeout bounds each of the two bot reads of the latest run's
	// ledger (trades, status); default 8 s.
	LedgerTimeout time.Duration
	// BotToken is the caller's bot API token, used only when the deployment
	// forwards user tokens instead of a service token.
	BotToken string
}

// DefaultEvidenceOptions is a Build with live data and default bounds.
func DefaultEvidenceOptions() EvidenceOptions {
	return EvidenceOptions{IncludeLive: true}
}

func (o EvidenceOptions) normalized() EvidenceOptions {
	if o.Runs <= 0 {
		o.Runs = evidenceDefaultRuns
	}
	if o.Runs > evidenceMaxRuns {
		o.Runs = evidenceMaxRuns
	}
	if o.TradeLimit <= 0 {
		o.TradeLimit = evidenceDefaultTradeLimit
	}
	if o.TradeLimit > evidenceMaxTradeLimit {
		o.TradeLimit = evidenceMaxTradeLimit
	}
	if o.Pairs <= 0 {
		o.Pairs = evidenceDefaultPairs
	}
	if o.Pairs > evidenceMaxPairs {
		o.Pairs = evidenceMaxPairs
	}
	if o.LiveTimeout <= 0 {
		o.LiveTimeout = evidenceDefaultLiveTimeout
	}
	if o.LedgerTimeout <= 0 {
		o.LedgerTimeout = evidenceDefaultLedgerTimeout
	}
	return o
}

// BotEvidenceClient is the read-only slice of the bot API client the builder
// needs; tests use a fake.
type BotEvidenceClient interface {
	GetBacktestStatus(runID string) (map[string]interface{}, error)
	GetBacktestTradesWithFilters(runID string, limit, offset int, winningOnly bool) (map[string]interface{}, error)
	GetBotInstanceTrades(instanceID string, status *string, limit *int, offset *int) (map[string]interface{}, error)
	GetCurrentPositions(instanceID string) (map[string]interface{}, error)
	GetRealtimeStats(instanceID string) (map[string]interface{}, error)
	GetBotEntryHalt(instanceID string) (map[string]interface{}, error)
	GetBotCointegratedPairs(instanceID string) (map[string]interface{}, error)
	WithRequestContext(ctx context.Context) BotEvidenceClient
	WithToken(token string) BotEvidenceClient
}

// botEvidenceAdapter adapts *BotAPIClient to BotEvidenceClient.
type botEvidenceAdapter struct {
	client *BotAPIClient
}

// NewBotEvidenceClient wraps a bot API client for the evidence builder; a nil
// client gives a nil evidence client (bot data unavailable, noted).
func NewBotEvidenceClient(client *BotAPIClient) BotEvidenceClient {
	if client == nil {
		return nil
	}
	return botEvidenceAdapter{client: client}
}

func (a botEvidenceAdapter) GetBacktestStatus(runID string) (map[string]interface{}, error) {
	return a.client.GetBacktestStatus(runID)
}

func (a botEvidenceAdapter) GetBacktestTradesWithFilters(runID string, limit, offset int, winningOnly bool) (map[string]interface{}, error) {
	return a.client.GetBacktestTradesWithFilters(runID, limit, offset, winningOnly)
}

func (a botEvidenceAdapter) GetBotInstanceTrades(instanceID string, status *string, limit *int, offset *int) (map[string]interface{}, error) {
	return a.client.GetBotInstanceTrades(instanceID, status, limit, offset)
}

func (a botEvidenceAdapter) GetCurrentPositions(instanceID string) (map[string]interface{}, error) {
	return a.client.GetCurrentPositions(instanceID)
}

func (a botEvidenceAdapter) GetRealtimeStats(instanceID string) (map[string]interface{}, error) {
	return a.client.GetRealtimeStats(instanceID)
}

func (a botEvidenceAdapter) GetBotEntryHalt(instanceID string) (map[string]interface{}, error) {
	return a.client.GetBotEntryHalt(instanceID)
}

func (a botEvidenceAdapter) GetBotCointegratedPairs(instanceID string) (map[string]interface{}, error) {
	return a.client.GetBotCointegratedPairs(instanceID)
}

func (a botEvidenceAdapter) WithRequestContext(ctx context.Context) BotEvidenceClient {
	return botEvidenceAdapter{client: a.client.WithRequestContext(ctx)}
}

func (a botEvidenceAdapter) WithToken(token string) BotEvidenceClient {
	return botEvidenceAdapter{client: a.client.WithToken(token)}
}

// StrategyEvidenceBuilder assembles the evidence from the backtest mirror and
// the bot. Build never fails: every missing source becomes a data note.
type StrategyEvidenceBuilder struct {
	backtests *repository.BacktestRepository
	bot       BotEvidenceClient
	runs      *evidenceRunCache
	now       func() time.Time
}

// NewStrategyEvidenceBuilder creates a builder; a nil bot client means the
// ledger, live and pair-scan blocks are unavailable (noted).
func NewStrategyEvidenceBuilder(backtests *repository.BacktestRepository, bot BotEvidenceClient) *StrategyEvidenceBuilder {
	return &StrategyEvidenceBuilder{
		backtests: backtests,
		bot:       bot,
		runs:      newEvidenceRunCache(evidenceRunCacheTTL, evidenceRunCacheSize),
		now:       time.Now,
	}
}

// requestClient derives the bot client for one Build: bound to ctx and, on
// deployments that forward user tokens, carrying the caller's token.
func (b *StrategyEvidenceBuilder) requestClient(ctx context.Context, token string) BotEvidenceClient {
	if b == nil || b.bot == nil {
		return nil
	}
	client := b.bot.WithRequestContext(ctx)
	if token = strings.TrimSpace(token); token != "" && !UseConfiguredBotAPIServiceToken() {
		client = client.WithToken(token)
	}
	return client
}

// evidenceBotCall runs one bot read under its own deadline.
func evidenceBotCall(ctx context.Context, client BotEvidenceClient, timeout time.Duration, call func(BotEvidenceClient) (map[string]interface{}, error)) (map[string]interface{}, error) {
	if client == nil {
		return nil, errors.New("bot client is not configured")
	}
	callCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	return call(client.WithRequestContext(callCtx))
}

// Build assembles the evidence of one strategy. state and stateErr are the
// persisted runtime state (nil state: never started; stateErr: unknown, which
// counts as active).
func (b *StrategyEvidenceBuilder) Build(ctx context.Context, strategy *models.BacktestStrategy, state *models.StrategyExecutionState, stateErr error, opts EvidenceOptions) *StrategyEvidence {
	opts = opts.normalized()
	evidence := &StrategyEvidence{
		Backtests: EvidenceBacktests{CompletedRuns: make([]EvidenceRun, 0)},
		DataNotes: []string{evidenceNoteUnits},
	}
	if b == nil || strategy == nil {
		evidence.DataNotes = append(evidence.DataNotes, evidenceNoteRunsUnavailable)
		evidence.Summary = evidence.summary()
		return evidence
	}
	client := b.requestClient(ctx, opts.BotToken)

	// Completed runs of this strategy, newest first.
	var runs []models.BacktestRun
	runsErr := errors.New("backtest repository is not configured")
	if b.backtests != nil {
		runs, runsErr = b.backtests.GetRunsByStrategyID(strategy.UserID, strategy.ID, opts.Runs)
	}
	switch {
	case runsErr != nil:
		log.Printf("strategy_evidence backtest history unavailable strategy_id=%d: %v", strategy.ID, runsErr)
		evidence.DataNotes = append(evidence.DataNotes, evidenceNoteRunsUnavailable)
	case len(runs) == 0:
		evidence.DataNotes = append(evidence.DataNotes, evidenceNoteNoRuns)
	}
	if len(runs) > opts.Runs {
		runs = runs[:opts.Runs]
	}
	evidence.Backtests.CompletedRuns = b.runBlocks(ctx, runs)

	// Per-pair ledger of the newest run.
	if len(runs) > 0 {
		ledger, notes := b.BuildRunBlock(ctx, client, &runs[0], opts)
		evidence.Backtests.LatestRun = ledger
		evidence.DataNotes = append(evidence.DataNotes, notes...)
	}

	// Live runtime and the stored pair scan need a runtime instance.
	switch {
	case stateErr != nil:
		evidence.Live = &EvidenceLive{Available: false, ActiveOrUnknown: true, Status: "unknown", OpenPositions: make([]EvidenceOpenPosition, 0)}
		evidence.DataNotes = append(evidence.DataNotes, evidenceNoteLiveUnavailable)
	case state == nil:
		evidence.DataNotes = append(evidence.DataNotes, evidenceNoteNeverStarted)
	case !opts.IncludeLive:
		evidence.DataNotes = append(evidence.DataNotes, evidenceNoteLiveSkipped)
	default:
		live, notes := b.buildLive(ctx, client, strategy, state, opts)
		evidence.Live = live
		evidence.DataNotes = append(evidence.DataNotes, notes...)
	}
	if state != nil && stateErr == nil {
		cointegration, note := b.buildCointegration(ctx, client, strategyRuntimeInstanceID(strategy), opts)
		evidence.Cointegration = cointegration
		if note != "" {
			evidence.DataNotes = append(evidence.DataNotes, note)
		}
	}

	if truncateEvidence(evidence, evidenceMaxBytes) {
		evidence.DataNotes = append(evidence.DataNotes, evidenceNoteTruncated)
	}
	evidence.Summary = evidence.summary()
	return evidence
}

// runBlocks converts mirror rows into run blocks, with the allowlisted
// settings snapshot of each run when the mirror holds one.
func (b *StrategyEvidenceBuilder) runBlocks(ctx context.Context, runs []models.BacktestRun) []EvidenceRun {
	blocks := make([]EvidenceRun, 0, len(runs))
	if len(runs) == 0 {
		return blocks
	}
	configs := map[string]string{}
	if b.backtests != nil {
		runIDs := make([]string, 0, len(runs))
		for _, run := range runs {
			runIDs = append(runIDs, run.RunID)
		}
		loaded, err := b.backtests.GetRunConfigsContext(ctx, runIDs)
		if err != nil {
			// The settings snapshot is optional context; the run metrics stand
			// on their own.
			log.Printf("strategy_evidence run settings unavailable: %v", err)
		} else {
			configs = loaded
		}
	}
	for _, run := range runs {
		block := evidenceRunFromMirror(run)
		if config, ok := configs[run.RunID]; ok {
			block.Settings = evidenceSettingsFromConfig(config)
		}
		blocks = append(blocks, block)
	}
	return blocks
}

// evidenceRunFromMirror picks the run metrics from a mirror row; win rate is
// normalized to percent once, drawdown is already percent.
func evidenceRunFromMirror(run models.BacktestRun) EvidenceRun {
	return EvidenceRun{
		RunRef:         strategyChatRunRef(run.RunID),
		StartDate:      strings.TrimSpace(run.StartDate),
		EndDate:        strings.TrimSpace(run.EndDate),
		Resolution:     strings.TrimSpace(run.Resolution),
		NumPairs:       run.NumPairs,
		TotalTrades:    run.TotalTrades,
		WinRatePct:     strategyChatRound(normalizeWinRatePercent(run.WinRate), 2),
		TotalPnLUSD:    evidenceRound(run.TotalPnLUSD, 2),
		SharpeRatio:    strategyChatRound(run.SharpeRatio, 3),
		MaxDrawdownPct: strategyChatRound(run.MaxDrawdown, 2),
		ProfitFactor:   strategyChatRound(run.ProfitFactor, 3),
		CompletedAt:    strategyChatTime(run.CompletedAt),
	}
}

// BuildRunBlock returns the per-pair ledger of one completed run (cached per
// run id, completed runs are immutable) and the notes that describe its
// gaps. A missing ledger is nil plus a note, never an error.
func (b *StrategyEvidenceBuilder) BuildRunBlock(ctx context.Context, client BotEvidenceClient, run *models.BacktestRun, opts EvidenceOptions) (*EvidenceLedger, []string) {
	opts = opts.normalized()
	if b == nil || run == nil || client == nil {
		return nil, []string{evidenceNoteLedgerMissing}
	}
	key := fmt.Sprintf("%s|%d", strings.TrimSpace(run.RunID), opts.TradeLimit)
	full, err := b.runs.getOrBuild(key, func() (*EvidenceLedger, error) {
		return b.fetchLedger(ctx, client, run, opts)
	})
	if err != nil {
		log.Printf("strategy_evidence ledger unavailable run=%s: %v", strategyChatRunRef(run.RunID), err)
		return nil, []string{evidenceNoteLedgerMissing}
	}
	ledger := foldLedgerPairs(full, opts.Pairs)
	notes := make([]string, 0, 2)
	if ledger.Truncated {
		notes = append(notes, fmt.Sprintf("Only the first %d of %d trades were analysed.", ledger.TradesAnalysed, ledger.TradesTotal))
	}
	if !ledger.CostsKnown {
		notes = append(notes, evidenceNoteCostsUnknown)
	}
	return ledger, notes
}

// fetchLedger reads the run's trades (and its light status overview for the
// drawdown halt and market-data network) from the bot and aggregates them.
func (b *StrategyEvidenceBuilder) fetchLedger(ctx context.Context, client BotEvidenceClient, run *models.BacktestRun, opts EvidenceOptions) (*EvidenceLedger, error) {
	tradesPayload, err := evidenceBotCall(ctx, client, opts.LedgerTimeout, func(c BotEvidenceClient) (map[string]interface{}, error) {
		return c.GetBacktestTradesWithFilters(run.RunID, opts.TradeLimit, 0, false)
	})
	if err != nil {
		return nil, err
	}
	trades, err := parseBotBacktestTrades(tradesPayload)
	if err != nil {
		return nil, err
	}
	if len(trades) == 0 {
		// Nothing to aggregate. An error is never cached, so the next call
		// asks the bot again instead of serving an empty ledger for the TTL.
		return nil, errors.New("bot reply carries no trades")
	}
	ledger := aggregateBacktestLedger(run, trades, opts.TradeLimit)

	statusPayload, statusErr := evidenceBotCall(ctx, client, opts.LedgerTimeout, func(c BotEvidenceClient) (map[string]interface{}, error) {
		return c.GetBacktestStatus(run.RunID)
	})
	if statusErr == nil {
		applyBacktestStatusToLedger(ledger, statusPayload)
	}
	return ledger, nil
}

// buildLive reads the runtime's closed trades, open positions, exposure and
// entry halt; each call has its own deadline and its own note on failure.
func (b *StrategyEvidenceBuilder) buildLive(ctx context.Context, client BotEvidenceClient, strategy *models.BacktestStrategy, state *models.StrategyExecutionState, opts EvidenceOptions) (*EvidenceLive, []string) {
	instanceID := strategyRuntimeInstanceID(strategy)
	decoded := decodeStrategyRuntimeState(state.State)
	live := &EvidenceLive{
		ActiveOrUnknown: strategyChatRuntimeActive(state, nil),
		Status:          sanitizeStrategyChatText(decoded.Status, 40),
		Network:         sanitizeStrategyChatText(decoded.Network, 40),
		LastConfirmedAt: strategyChatTime(decoded.LastConfirmedAt),
		OpenPositions:   make([]EvidenceOpenPosition, 0),
	}
	if client == nil {
		return &EvidenceLive{Available: false, ActiveOrUnknown: live.ActiveOrUnknown, Status: live.Status, Network: live.Network, OpenPositions: live.OpenPositions}, []string{evidenceNoteLiveUnavailable}
	}
	notes := make([]string, 0, 3)
	now := b.now()

	closedStatus := "CLOSED"
	limit := evidenceLiveTradeCap
	offset := 0
	tradesPayload, tradesErr := evidenceBotCall(ctx, client, opts.LiveTimeout, func(c BotEvidenceClient) (map[string]interface{}, error) {
		return c.GetBotInstanceTrades(instanceID, &closedStatus, &limit, &offset)
	})
	if tradesErr == nil {
		trades, total := parseBotLiveTrades(tradesPayload)
		live.ClosedTrades = aggregateLiveTrades(trades, total, evidenceLiveTradeCap, opts.Pairs)
		if live.ClosedTrades.Truncated {
			notes = append(notes, liveTradesTruncatedNote(live.ClosedTrades.Count, total))
		}
	}

	positionsPayload, positionsErr := evidenceBotCall(ctx, client, opts.LiveTimeout, func(c BotEvidenceClient) (map[string]interface{}, error) {
		return c.GetCurrentPositions(instanceID)
	})
	if positionsErr == nil {
		live.OpenPositions = parseBotPositions(positionsPayload, now)
	}

	if tradesErr != nil && positionsErr != nil {
		log.Printf("strategy_evidence live runtime unavailable strategy_id=%d: trades=%v positions=%v", strategy.ID, tradesErr, positionsErr)
		return &EvidenceLive{Available: false, ActiveOrUnknown: live.ActiveOrUnknown, Status: live.Status, Network: live.Network, LastConfirmedAt: live.LastConfirmedAt, OpenPositions: make([]EvidenceOpenPosition, 0)},
			[]string{evidenceNoteLiveUnavailable}
	}
	live.Available = true
	notes = append(notes, evidenceNoteLiveSnapshot)
	if tradesErr != nil {
		notes = append(notes, "Live closed trades could not be read.")
	}
	if positionsErr != nil {
		notes = append(notes, "Live open positions could not be read.")
	}

	statsPayload, statsErr := evidenceBotCall(ctx, client, opts.LiveTimeout, func(c BotEvidenceClient) (map[string]interface{}, error) {
		return c.GetRealtimeStats(instanceID)
	})
	if statsErr == nil {
		live.Exposure = parseBotExposure(statsPayload)
	}

	haltPayload, haltErr := evidenceBotCall(ctx, client, opts.LiveTimeout, func(c BotEvidenceClient) (map[string]interface{}, error) {
		return c.GetBotEntryHalt(instanceID)
	})
	switch {
	case haltErr == nil:
		live.EntryHalt = parseEntryHalt(haltPayload)
	case isBotNotFound(haltErr):
		// No runtime on the bot: nothing is halted for it.
		live.EntryHalt = &EvidenceEntryHalt{}
	default:
		notes = append(notes, evidenceNoteEntryHalt)
	}
	return live, notes
}

// liveTradesTruncatedNote says how many of the runtime's closed trades were
// analysed, out of the bot's count of matching trades when it reported one.
func liveTradesTruncatedNote(analysed int, total *int) string {
	if total != nil && *total > analysed {
		return fmt.Sprintf("Only the newest %d of %d live closed trades were analysed.", analysed, *total)
	}
	return fmt.Sprintf("Only the newest %d live closed trades were analysed.", analysed)
}

// buildCointegration reads the bot's stored pair scan of the instance.
func (b *StrategyEvidenceBuilder) buildCointegration(ctx context.Context, client BotEvidenceClient, instanceID string, opts EvidenceOptions) (*EvidenceCointegration, string) {
	if client == nil {
		return nil, evidenceNotePairScanUnavailable
	}
	payload, err := evidenceBotCall(ctx, client, opts.LiveTimeout, func(c BotEvidenceClient) (map[string]interface{}, error) {
		return c.GetBotCointegratedPairs(instanceID)
	})
	if err != nil {
		if isBotNotFound(err) {
			return nil, evidenceNoteNoPairScan
		}
		log.Printf("strategy_evidence pair scan unavailable instance=%s: %v", strategyChatRunRef(instanceID), err)
		return nil, evidenceNotePairScanUnavailable
	}
	cointegration := parseBotCointegratedPairs(payload, evidenceMaxCointegrated)
	if cointegration == nil || cointegration.Count == 0 {
		return nil, evidenceNoteNoPairScan
	}
	return cointegration, ""
}

// summary counts what the evidence holds.
func (e *StrategyEvidence) summary() AIEvidenceSummary {
	summary := AIEvidenceSummary{
		CompletedRuns: len(e.Backtests.CompletedRuns),
		DataNotes:     append([]string{}, e.DataNotes...),
	}
	if ledger := e.Backtests.LatestRun; ledger != nil {
		summary.TradesAnalysed = ledger.TradesAnalysed
		summary.PairsAnalysed = len(ledger.Pairs) + ledger.PairsOmitted
	}
	if live := e.Live; live != nil {
		summary.LiveAvailable = live.Available
		if live.ClosedTrades != nil {
			summary.LiveClosedTrades = live.ClosedTrades.Count
		}
		summary.LiveOpenPositions = len(live.OpenPositions)
	}
	if e.Cointegration != nil {
		summary.CointegratedPairs = e.Cointegration.Count
	}
	return summary
}

// AIRequestError is a request the AI endpoints refuse with a fixed status
// and message (missing input, a strategy or run that is not the caller's).
type AIRequestError struct {
	Status  int
	Message string
}

func (e *AIRequestError) Error() string {
	if e == nil {
		return "AI request error"
	}
	return e.Message
}

func aiRequestError(status int, message string) *AIRequestError {
	return &AIRequestError{Status: status, Message: message}
}

// SetStrategyEvidence wires the evidence builder and the strategy store into
// the AI service, which the parameter suggestions, backtest explanations and
// market selection read through.
func (s *AIMarketService) SetStrategyEvidence(builder *StrategyEvidenceBuilder, strategies *StrategyService, backtests *repository.BacktestRepository) {
	s.evidence = builder
	s.strategies = strategies
	s.backtests = backtests
}

// authorizeAIStrategy loads a strategy the caller owns (admins may read any);
// missing, deleted and foreign strategies are all not found.
func (s *AIMarketService) authorizeAIStrategy(userID int, isAdmin bool, strategyID int) (*models.BacktestStrategy, error) {
	if s.strategies == nil {
		return nil, aiRequestError(http.StatusServiceUnavailable, "Strategy evidence is not configured")
	}
	if strategyID <= 0 || userID <= 0 {
		return nil, aiRequestError(http.StatusNotFound, "Strategy not found")
	}
	strategy, err := s.strategies.GetStrategy(strategyID)
	if err != nil {
		log.Printf("ai strategy lookup failed strategy_id=%d: %v", strategyID, err)
		return nil, aiRequestError(http.StatusInternalServerError, "Failed to load the strategy")
	}
	if strategy == nil || strategy.DeletedAt != nil || (strategy.UserID != userID && !isAdmin) {
		return nil, aiRequestError(http.StatusNotFound, "Strategy not found")
	}
	return strategy, nil
}

// AuthorizeAIStrategy reports whether the caller may analyse the strategy
// (a typed 404 otherwise). Handlers call it before spending the caller's
// analysis budget; the analysis itself checks again.
func (s *AIMarketService) AuthorizeAIStrategy(actor AIAnalysisActor, strategyID int) error {
	_, err := s.authorizeAIStrategy(actor.UserID, actor.IsAdmin, strategyID)
	return err
}

// buildStrategyEvidence loads the runtime state and builds the evidence of an
// authorized strategy.
func (s *AIMarketService) buildStrategyEvidence(ctx context.Context, strategy *models.BacktestStrategy, opts EvidenceOptions) *StrategyEvidence {
	var state *models.StrategyExecutionState
	var stateErr error
	if s.strategies != nil {
		state, stateErr = s.strategies.GetExecutionState(strategy.ID)
	}
	return s.evidence.Build(ctx, strategy, state, stateErr, opts)
}

// PairStatsForStrategy gives market selection the latest completed run's
// per-pair results and the stored pair scan of a strategy the caller owns;
// the bot reads carry the caller's token. An unwired service answers with a
// note, not an error.
func (s *AIMarketService) PairStatsForStrategy(ctx context.Context, userID int, isAdmin bool, strategyID int, botToken string) ([]EvidencePairStats, []EvidenceCointegratedPair, []string, error) {
	if s == nil || s.evidence == nil || s.strategies == nil {
		return nil, nil, []string{"Strategy evidence is not configured."}, nil
	}
	strategy, err := s.authorizeAIStrategy(userID, isAdmin, strategyID)
	if err != nil {
		return nil, nil, nil, err
	}
	evidence := s.buildStrategyEvidence(ctx, strategy, EvidenceOptions{IncludeLive: false, Pairs: evidenceMaxPairs, BotToken: botToken})
	pairs := make([]EvidencePairStats, 0)
	if evidence.Backtests.LatestRun != nil {
		pairs = append(pairs, evidence.Backtests.LatestRun.Pairs...)
	}
	cointegrated := make([]EvidenceCointegratedPair, 0)
	if evidence.Cointegration != nil {
		cointegrated = append(cointegrated, evidence.Cointegration.Pairs...)
	}
	return pairs, cointegrated, evidence.DataNotes, nil
}

var _ StrategyEvidenceSource = (*AIMarketService)(nil)
