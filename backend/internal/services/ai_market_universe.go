package services

import (
	"context"
	"errors"
	"fmt"
	"log"
	"math"
	"net/http"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Market selection is grounded in the bot's perpetual-markets payload: the
// statistics of every active market are parsed into a universe, ranked
// deterministically, shown to the model as a numeric table and used again to
// validate the model's answer and to order the fallback. Nothing here judges a
// market by its name.

const (
	// marketUniverseCacheTTL serves a parsed universe without a bot call; the
	// bot itself caches the indexer payload for about a minute.
	marketUniverseCacheTTL = 60 * time.Second
	// marketUniverseStaleTTL is how old a cached universe may be when the bot
	// cannot be reached.
	marketUniverseStaleTTL = 10 * time.Minute
	// marketUniverseFetchTimeout bounds one bot call. The bot's endpoint waits
	// up to 10 s twice (connect, fetch) before serving its own stale cache.
	marketUniverseFetchTimeout = 20 * time.Second

	// aiMarketPromptRows is the least number of ranked rows in the prompt; a
	// larger limit shows as many rows as the caller may select.
	aiMarketPromptRows = 60
	// aiMarketThinVolumeUSD and aiMarketThinTrades mark a thin market for the
	// risk penalty. A market with unknown volume or trade count counts as thin.
	aiMarketThinVolumeUSD = 1_000_000.0
	aiMarketThinTrades    = 500
	// maxAIMarketPairSuggestions caps the pairs the model may propose so the
	// reply stays inside the market-selection output budget.
	maxAIMarketPairSuggestions = 12
	// aiMarketPairEvidenceRows caps each strategy evidence table in the prompt.
	aiMarketPairEvidenceRows = 20

	aiMarketSourceAI            = "ai"
	aiMarketSourceDeterministic = "deterministic_ranking"

	aiMarketPairSourceModel         = "model"
	aiMarketPairSourceHistory       = "strategy_history"
	aiMarketPairSourceCointegration = "cointegration"

	marketUniverseSourceBackendCache = "backend_cache"
	marketUniverseSourceBackendStale = "backend_stale"

	// marketUniverseNetwork labels the ranking statistics: the backtest-purpose
	// list is the bot's backtest market-data network, mainnet unless the bot is
	// configured otherwise, which the backend cannot observe.
	marketUniverseNetwork = "mainnet"

	marketUniversePurposeBacktest = "backtest"
	marketUniversePurposeRuntime  = "runtime"
)

var aiMarketTickerPattern = regexp.MustCompile(`^[A-Z0-9]+-[A-Z0-9]+$`)

// MarketStat is one market's statistics from the bot's perpetual-markets
// payload. Nil means the indexer did not report the value.
type MarketStat struct {
	Ticker          string
	Volume24hUSD    *float64
	OpenInterestUSD *float64
	Trades24h       *int
	// FundingRate is the hourly nextFundingRate as a fraction, unscaled.
	FundingRate *float64
	OraclePrice *float64
	// PriceChange24hPct is derived from the indexer's absolute 24 h change and
	// the oracle price; nil when either is missing.
	PriceChange24hPct *float64
}

// MarketUniverse is what the select route hands the service: the ranking
// statistics in the bot's order (24 h volume descending) and the tickers the
// runtime can trade.
type MarketUniverse struct {
	Stats []MarketStat
	// HasDetails is false when the bot sent names only (an older bot).
	HasDetails bool
	Network    string
	Source     string
	// Tradable lists the runtime market list; nil when it could not be read,
	// in which case no tradability filter is applied.
	Tradable []string
}

// ScoredMarket is a market with its deterministic pre-ranking score.
type ScoredMarket struct {
	MarketStat
	Score float64
	Thin  bool
}

// AIMarketSelectionBasis says what the ranking was built from.
type AIMarketSelectionBasis struct {
	UniverseCount       int      `json:"universe_count"`
	RankedCount         int      `json:"ranked_count"`
	Network             string   `json:"network"`
	Source              string   `json:"source"`
	CriteriaUsed        []string `json:"criteria_used"`
	CriteriaUnavailable []string `json:"criteria_unavailable"`
}

// AIMarketPair is a pair offered with the selection and where it came from.
type AIMarketPair struct {
	Market1 string `json:"market_1"`
	Market2 string `json:"market_2"`
	Reason  string `json:"reason"`
	Source  string `json:"source"`
}

// AIMarketStatRow is the statistics row of a selected market.
type AIMarketStatRow struct {
	Ticker            string   `json:"ticker"`
	Volume24hUSD      *float64 `json:"volume_24h_usd"`
	OpenInterestUSD   *float64 `json:"open_interest_usd"`
	Trades24h         *int     `json:"trades_24h"`
	FundingRate       *float64 `json:"funding_rate"`
	OraclePrice       *float64 `json:"oracle_price"`
	PriceChange24hPct *float64 `json:"price_change_24h_pct"`
	Score             float64  `json:"score"`
}

// SetStrategyEvidenceSource lets market selection offer a strategy's pair
// statistics when a request names a strategy the caller owns.
func (s *AIMarketService) SetStrategyEvidenceSource(source StrategyEvidenceSource) {
	s.marketEvidence = source
}

// ==================== universe loading ====================

type marketUniverseEntry struct {
	stats      []MarketStat
	hasDetails bool
	source     string
	fetchedAt  time.Time
}

type marketUniverseCache struct {
	mu      sync.Mutex
	entries map[string]*marketUniverseEntry
}

func (c *marketUniverseCache) get(purpose string, now time.Time, maxAge time.Duration) *marketUniverseEntry {
	c.mu.Lock()
	defer c.mu.Unlock()
	entry := c.entries[purpose]
	if entry == nil || now.Sub(entry.fetchedAt) > maxAge {
		return nil
	}
	return entry
}

func (c *marketUniverseCache) set(purpose string, entry *marketUniverseEntry) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.entries == nil {
		c.entries = map[string]*marketUniverseEntry{}
	}
	c.entries[purpose] = entry
}

// MarketUniverseLoader fetches the universe for AI market selection: the
// mainnet statistics (the bot's backtest market-data list) for ranking and
// the runtime list for tradability. Each list is cached for a minute and kept
// ten minutes as a stale fallback while the bot is unreachable.
type MarketUniverseLoader struct {
	client *BotAPIClient
	cache  *marketUniverseCache
	now    func() time.Time
}

func NewMarketUniverseLoader(client *BotAPIClient) *MarketUniverseLoader {
	return &MarketUniverseLoader{client: client, cache: &marketUniverseCache{}, now: time.Now}
}

// Load returns the universe or the bot error when no statistics are
// available live or cached. A missing runtime list only drops the
// tradability filter.
func (l *MarketUniverseLoader) Load(ctx context.Context) (*MarketUniverse, error) {
	if l == nil || l.client == nil {
		return nil, errors.New("bot market client is not configured")
	}
	type fetched struct {
		entry  *marketUniverseEntry
		source string
		err    error
	}
	var stats, runtime fetched
	var wg sync.WaitGroup
	wg.Add(2)
	go func() {
		defer wg.Done()
		stats.entry, stats.source, stats.err = l.fetch(ctx, true)
	}()
	go func() {
		defer wg.Done()
		runtime.entry, runtime.source, runtime.err = l.fetch(ctx, false)
	}()
	wg.Wait()
	if stats.err != nil {
		return nil, stats.err
	}
	universe := &MarketUniverse{
		Stats:      stats.entry.stats,
		HasDetails: stats.entry.hasDetails,
		Network:    marketUniverseNetwork,
		Source:     stats.source,
	}
	if runtime.err != nil {
		log.Printf("ai_market_universe runtime market list unavailable, tradability filter skipped: %v", runtime.err)
		return universe, nil
	}
	universe.Tradable = make([]string, 0, len(runtime.entry.stats))
	for _, stat := range runtime.entry.stats {
		universe.Tradable = append(universe.Tradable, stat.Ticker)
	}
	return universe, nil
}

// fetch serves a fresh cache entry, otherwise calls the bot, otherwise serves
// a stale entry. The source names which of the three answered.
func (l *MarketUniverseLoader) fetch(ctx context.Context, forBacktest bool) (*marketUniverseEntry, string, error) {
	purpose := marketUniversePurposeRuntime
	if forBacktest {
		purpose = marketUniversePurposeBacktest
	}
	now := l.now()
	if entry := l.cache.get(purpose, now, marketUniverseCacheTTL); entry != nil {
		return entry, marketUniverseSourceBackendCache, nil
	}

	fetchCtx, cancel := context.WithTimeout(ctx, marketUniverseFetchTimeout)
	defer cancel()
	payload, err := l.client.WithRequestContext(fetchCtx).GetPerpetualMarketsFor(0, false, forBacktest)
	if err == nil {
		stats, source, hasDetails := parseMarketUniverse(payload)
		if len(stats) > 0 {
			entry := &marketUniverseEntry{stats: stats, hasDetails: hasDetails, source: source, fetchedAt: now}
			l.cache.set(purpose, entry)
			return entry, source, nil
		}
		err = fmt.Errorf("dYdX market universe (%s) did not return any market", purpose)
	}
	if entry := l.cache.get(purpose, now, marketUniverseStaleTTL); entry != nil {
		log.Printf("ai_market_universe serving stale %s universe fetched %s ago: %v", purpose, now.Sub(entry.fetchedAt).Round(time.Second), err)
		return entry, marketUniverseSourceBackendStale, nil
	}
	return nil, "", err
}

// parseMarketUniverse reads the bot's payload ({data: {markets,
// market_details, source}}) with explicit field picks. An old bot without
// market_details yields names only, in the bot's order.
func parseMarketUniverse(payload map[string]interface{}) (stats []MarketStat, source string, hasDetails bool) {
	if payload == nil {
		return nil, "", false
	}
	data := payload
	if nested, ok := payload["data"].(map[string]interface{}); ok {
		data = nested
	}
	source = strings.TrimSpace(fmt.Sprint(data["source"]))
	if source == "" || source == "<nil>" {
		source = "dydx"
	}
	source = sanitizeStrategyChatText(source, 32)

	seen := map[string]bool{}
	if details, ok := data["market_details"].([]interface{}); ok {
		for _, item := range details {
			row, ok := item.(map[string]interface{})
			if !ok {
				continue
			}
			ticker := normalizeAIMarketTicker(row["ticker"])
			if ticker == "" || seen[ticker] {
				continue
			}
			seen[ticker] = true
			stat := MarketStat{
				Ticker:          ticker,
				Volume24hUSD:    marketFloatField(row["volume_24h"]),
				OpenInterestUSD: marketFloatField(row["open_interest_usd"]),
				Trades24h:       marketIntField(row["trades_24h"]),
				FundingRate:     marketFloatField(row["next_funding_rate"]),
				OraclePrice:     marketFloatField(row["oracle_price"]),
			}
			stat.PriceChange24hPct = priceChangePercent(marketFloatField(row["price_change_24h"]), stat.OraclePrice)
			stats = append(stats, stat)
		}
		if len(stats) > 0 {
			return stats, source, true
		}
	}
	if names, ok := data["markets"].([]interface{}); ok {
		for _, item := range names {
			ticker := normalizeAIMarketTicker(item)
			if ticker == "" || seen[ticker] {
				continue
			}
			seen[ticker] = true
			stats = append(stats, MarketStat{Ticker: ticker})
		}
	}
	return stats, source, false
}

// normalizeAIMarketTicker upper-cases a ticker and rejects anything that is
// not BASE-QUOTE of letters and digits.
func normalizeAIMarketTicker(value interface{}) string {
	text, ok := value.(string)
	if !ok {
		return ""
	}
	ticker := strings.ToUpper(strings.TrimSpace(text))
	if !aiMarketTickerPattern.MatchString(ticker) {
		return ""
	}
	return ticker
}

func marketFloatField(value interface{}) *float64 {
	var parsed float64
	switch v := value.(type) {
	case float64:
		parsed = v
	case float32:
		parsed = float64(v)
	case int:
		parsed = float64(v)
	case int64:
		parsed = float64(v)
	case string:
		number, err := strconv.ParseFloat(strings.TrimSpace(v), 64)
		if err != nil {
			return nil
		}
		parsed = number
	default:
		return nil
	}
	if math.IsNaN(parsed) || math.IsInf(parsed, 0) {
		return nil
	}
	return &parsed
}

func marketIntField(value interface{}) *int {
	parsed := marketFloatField(value)
	if parsed == nil {
		return nil
	}
	count := int(*parsed)
	return &count
}

// priceChangePercent turns the indexer's absolute 24 h oracle-price change
// into a percent of the price 24 h ago (oracle - change).
func priceChangePercent(change *float64, oracle *float64) *float64 {
	if change == nil || oracle == nil {
		return nil
	}
	base := *oracle - *change
	if base <= 0 {
		return nil
	}
	pct := *change / base * 100
	return &pct
}

// ==================== ranking ====================

// restrictMarketUniverse keeps the statistics of the markets the runtime can
// trade and, when the request names markets, of those markets only. The
// bot's order is preserved.
func restrictMarketUniverse(universe *MarketUniverse, requested []string) []MarketStat {
	var tradable map[string]bool
	if universe.Tradable != nil {
		tradable = map[string]bool{}
		for _, ticker := range universe.Tradable {
			tradable[ticker] = true
		}
	}
	var wanted map[string]bool
	if len(requested) > 0 {
		wanted = map[string]bool{}
		for _, item := range requested {
			if ticker := normalizeAIMarketTicker(item); ticker != "" {
				wanted[ticker] = true
			}
		}
	}
	stats := make([]MarketStat, 0, len(universe.Stats))
	for _, stat := range universe.Stats {
		if tradable != nil && !tradable[stat.Ticker] {
			continue
		}
		if wanted != nil && !wanted[stat.Ticker] {
			continue
		}
		stats = append(stats, stat)
	}
	return stats
}

// marketStatsFromTickers is a names-only universe in the given order.
func marketStatsFromTickers(tickers []string) []MarketStat {
	seen := map[string]bool{}
	stats := make([]MarketStat, 0, len(tickers))
	for _, item := range tickers {
		ticker := normalizeAIMarketTicker(item)
		if ticker == "" || seen[ticker] {
			continue
		}
		seen[ticker] = true
		stats = append(stats, MarketStat{Ticker: ticker})
	}
	return stats
}

type rankedColumn struct {
	values []float64
	known  int
}

// rankColumn rank-normalises one statistic to (0, 1]: the smallest known
// value scores 1/n, the largest 1, equal values share a rank and unknown
// values score 0 so they sort last.
func rankColumn(stats []MarketStat, pick func(MarketStat) *float64) rankedColumn {
	known := make([]float64, 0, len(stats))
	for _, stat := range stats {
		if value := pick(stat); value != nil {
			known = append(known, *value)
		}
	}
	sort.Float64s(known)
	column := rankedColumn{values: make([]float64, len(stats)), known: len(known)}
	if len(known) == 0 {
		return column
	}
	for i, stat := range stats {
		value := pick(stat)
		if value == nil {
			continue
		}
		below := sort.SearchFloat64s(known, *value)
		column.values[i] = float64(below+1) / float64(len(known))
	}
	return column
}

// scoreMarkets ranks the universe deterministically: rank-normalised 24 h
// volume, open interest and trade count weighted by the caller's volume,
// liquidity and tradeability weights, plus the momentum weight on the 24 h
// price change when the bot reports it, minus the risk weight for a thin
// market. Ties keep the bot's order (24 h volume descending), so a universe
// without statistics still ranks by volume and never alphabetically.
func scoreMarkets(stats []MarketStat, criteria AIMarketCriteria) []ScoredMarket {
	volume := rankColumn(stats, func(m MarketStat) *float64 { return m.Volume24hUSD })
	openInterest := rankColumn(stats, func(m MarketStat) *float64 { return m.OpenInterestUSD })
	trades := rankColumn(stats, func(m MarketStat) *float64 {
		if m.Trades24h == nil {
			return nil
		}
		value := float64(*m.Trades24h)
		return &value
	})
	change := rankColumn(stats, func(m MarketStat) *float64 { return m.PriceChange24hPct })

	ranked := make([]ScoredMarket, 0, len(stats))
	for i, stat := range stats {
		thin := stat.Volume24hUSD == nil || *stat.Volume24hUSD < aiMarketThinVolumeUSD ||
			stat.Trades24h == nil || *stat.Trades24h < aiMarketThinTrades
		score := criteria.VolumeWeight*volume.values[i] +
			criteria.LiquidityWeight*openInterest.values[i] +
			criteria.TradeabilityWeight*trades.values[i]
		if change.known > 0 {
			score += criteria.MomentumWeight * change.values[i]
		}
		if thin {
			score -= criteria.RiskWeight
		}
		ranked = append(ranked, ScoredMarket{MarketStat: stat, Score: math.Round(score*1e4) / 1e4, Thin: thin})
	}
	sort.SliceStable(ranked, func(a, b int) bool { return ranked[a].Score > ranked[b].Score })
	return ranked
}

func marketsHavePriceChange(stats []MarketStat) bool {
	for _, stat := range stats {
		if stat.PriceChange24hPct != nil {
			return true
		}
	}
	return false
}

// aiMarketPromptRowCount is how many ranked rows the prompt shows: at least
// aiMarketPromptRows and never fewer than the caller may select.
func aiMarketPromptRowCount(universe int, limit int) int {
	rows := aiMarketPromptRows
	if limit > rows {
		rows = limit
	}
	if rows > universe {
		rows = universe
	}
	return rows
}

// aiMarketPairCap is how many pairs the model may propose for a limit.
func aiMarketPairCap(limit int) int {
	pairs := limit / 2
	if pairs > maxAIMarketPairSuggestions {
		pairs = maxAIMarketPairSuggestions
	}
	if pairs < 1 {
		pairs = 1
	}
	return pairs
}

// ==================== prompt ====================

// aiMarketPairEvidence is the strategy's own pair statistics offered to the
// model, restricted to tickers of the universe.
type aiMarketPairEvidence struct {
	Pairs        []EvidencePairStats
	Cointegrated []EvidenceCointegratedPair
	Notes        []string
}

type aiMarketPromptInput struct {
	Mode       string
	Limit      int
	Strategy   string
	Criteria   AIMarketCriteria
	Ranked     []ScoredMarket
	Rows       int
	Network    string
	Source     string
	HasDetails bool
	Evidence   *aiMarketPairEvidence
}

const aiMarketTableUnits = "Units: vol_24h_usd = 24 h notional volume in USD; oi_usd = open interest in USD (base open interest x oracle price); " +
	"trades_24h = number of trades in 24 h; funding_1h_frac = hourly funding rate as a fraction (0.0001 = 0.01 % per hour, positive = longs pay); " +
	"oracle_price_usd = oracle price in USD; 24h change % = 24 h oracle price change in percent of the price 24 h ago; " +
	"score = deterministic pre-ranking, higher is better; thin = volume below $1,000,000 or fewer than 500 trades in 24 h (or unknown); n/a = not reported by the indexer."

// buildMarketTable renders the top rows as a pipe-separated table with the
// units stated above the header. The 24 h change column appears only when
// the bot reports it for at least one shown row.
func buildMarketTable(ranked []ScoredMarket, rows int) string {
	if rows > len(ranked) {
		rows = len(ranked)
	}
	if rows < 0 {
		rows = 0
	}
	shown := ranked[:rows]
	showChange := false
	for _, market := range shown {
		if market.PriceChange24hPct != nil {
			showChange = true
			break
		}
	}

	var b strings.Builder
	b.WriteString(aiMarketTableUnits)
	b.WriteString("\nrank | ticker | vol_24h_usd | oi_usd | trades_24h | funding_1h_frac | oracle_price_usd")
	if showChange {
		b.WriteString(" | 24h change %")
	}
	b.WriteString(" | score | thin\n")
	for i, market := range shown {
		fmt.Fprintf(&b, "%d | %s | %s | %s | %s | %s | %s",
			i+1,
			market.Ticker,
			formatMarketUSD(market.Volume24hUSD),
			formatMarketUSD(market.OpenInterestUSD),
			formatMarketCount(market.Trades24h),
			formatMarketFraction(market.FundingRate),
			formatMarketPrice(market.OraclePrice),
		)
		if showChange {
			fmt.Fprintf(&b, " | %s", formatMarketPercent(market.PriceChange24hPct))
		}
		fmt.Fprintf(&b, " | %.4f | %s\n", market.Score, formatMarketBool(market.Thin))
	}
	return strings.TrimRight(b.String(), "\n")
}

func formatMarketUSD(value *float64) string {
	if value == nil {
		return "n/a"
	}
	return strconv.FormatFloat(math.Round(*value), 'f', 0, 64)
}

func formatMarketCount(value *int) string {
	if value == nil {
		return "n/a"
	}
	return strconv.Itoa(*value)
}

func formatMarketFraction(value *float64) string {
	if value == nil {
		return "n/a"
	}
	return trimMarketZeros(strconv.FormatFloat(*value, 'f', 8, 64))
}

func formatMarketPrice(value *float64) string {
	if value == nil {
		return "n/a"
	}
	decimals := 2
	switch magnitude := math.Abs(*value); {
	case magnitude < 0.01:
		decimals = 8
	case magnitude < 1:
		decimals = 4
	}
	return trimMarketZeros(strconv.FormatFloat(*value, 'f', decimals, 64))
}

func formatMarketPercent(value *float64) string {
	if value == nil {
		return "n/a"
	}
	return strconv.FormatFloat(*value, 'f', 2, 64)
}

func formatMarketBool(value bool) string {
	if value {
		return "yes"
	}
	return "no"
}

func trimMarketZeros(text string) string {
	if !strings.Contains(text, ".") {
		return text
	}
	text = strings.TrimRight(text, "0")
	return strings.TrimSuffix(text, ".")
}

// buildAIMarketPromptWithTable is the market-selection prompt: the caller's
// intent, what data is and is not available, the numeric table and the
// strategy's pair evidence when offered. The model is told to rank by the
// numbers only and never to claim profitability.
func buildAIMarketPromptWithTable(in aiMarketPromptInput) string {
	strategy := sanitizeStrategyChatText(in.Strategy, 400)
	if strategy == "" {
		strategy = "cointegration pairs trading with controlled liquidity, volatility, and backtest coverage"
	}
	notes := sanitizeStrategyChatText(in.Criteria.Notes, 600)
	if notes == "" {
		notes = "none"
	}
	objective := sanitizeStrategyChatText(in.Criteria.Objective, 64)
	if objective == "" {
		objective = in.Mode
	}
	limit := in.Limit
	if limit <= 0 {
		limit = defaultAIMarketLimit
	}
	pairCap := aiMarketPairCap(limit)
	hasChange := in.HasDetails && marketsHavePriceChange(marketStatsOf(in.Ranked))

	available := "none (the bot sent no statistics for this universe; rows are in the bot's 24 h volume order and every numeric cell is n/a)"
	unavailable := "24 h volume, open interest, trade count, funding, price, momentum, volatility, cointegration"
	if in.HasDetails {
		available = "24 h volume, open interest, 24 h trade count, hourly funding rate, oracle price"
		unavailable = "momentum (no 24 h price change), volatility, cointegration"
		if hasChange {
			available += ", 24 h price change"
			unavailable = "volatility, cointegration"
		}
	}

	caveats := []string{}
	switch in.Mode {
	case "most_profitable":
		caveats = append(caveats, "No profitability data exists for any market; do not claim or predict profitability, rank by the table.")
	case "most_popular":
		caveats = append(caveats, "Popularity means 24 h volume and trade count in the table.")
	}
	if in.Criteria.FutureGainers && !hasChange {
		caveats = append(caveats, "No 24 h price change is available, so momentum cannot be judged; do not guess it.")
	}
	caveatText := ""
	if len(caveats) > 0 {
		caveatText = strings.Join(caveats, " ") + "\n"
	}

	rows := in.Rows
	if rows <= 0 || rows > len(in.Ranked) {
		rows = len(in.Ranked)
	}
	network := strings.TrimSpace(in.Network)
	if network == "" {
		network = marketUniverseNetwork
	}
	source := strings.TrimSpace(in.Source)
	if source == "" {
		source = "dydx"
	}

	var b strings.Builder
	fmt.Fprintf(&b, "Select dYdX perpetual markets for %s.\n\n", strategy)
	fmt.Fprintf(&b, "Mode: %s\nObjective: %s\n", in.Mode, objective)
	fmt.Fprintf(&b, "Select exactly %d markets when possible, never more than %d, using only tickers from the table below.\n\n", limit, limit)
	fmt.Fprintf(&b, "Caller weights (0-1): volume %.2f, liquidity %.2f, tradeability %.2f, momentum %.2f, volatility %.2f, cointegration %.2f, risk %.2f; future_gainers: %t.\n",
		in.Criteria.VolumeWeight, in.Criteria.LiquidityWeight, in.Criteria.TradeabilityWeight, in.Criteria.MomentumWeight,
		in.Criteria.VolatilityWeight, in.Criteria.CointegrationWeight, in.Criteria.RiskWeight, in.Criteria.FutureGainers)
	fmt.Fprintf(&b, "The table comes from the dYdX %s indexer through the trading bot (source: %s).\n", network, source)
	fmt.Fprintf(&b, "Statistics available: %s.\n", available)
	fmt.Fprintf(&b, "Statistics NOT available: %s. Do not infer them from ticker names or outside knowledge; judge only by the numbers shown.\n", unavailable)
	b.WriteString(caveatText)
	fmt.Fprintf(&b, "The score column is a deterministic pre-ranking: rank-normalised 24 h volume, open interest and trade count (and 24 h price change when shown) weighted by the caller weights, minus the risk weight for a thin market. Rows are sorted by score; %d of %d eligible markets are shown.\n", rows, len(in.Ranked))
	fmt.Fprintf(&b, "Additional strategy notes: %s\n\n", notes)
	b.WriteString(buildMarketTable(in.Ranked, rows))
	b.WriteString("\n")
	if in.Evidence != nil {
		b.WriteString(buildMarketPairEvidenceBlock(in.Evidence))
	}
	b.WriteString("\nReturn JSON in this shape:\n")
	b.WriteString(`{"selected_markets":["BTC-USD","ETH-USD"],"pairs":[{"market_1":"BTC-USD","market_2":"ETH-USD","reason":"short reason citing the table"}],"rationale":"two or three sentences citing the numbers","confidence":0.7}`)
	b.WriteString("\nRules:\n")
	fmt.Fprintf(&b, "- selected_markets: tickers from the table only, best first, no duplicates, at most %d.\n", limit)
	fmt.Fprintf(&b, "- pairs: at most %d pairs whose two legs are both in selected_markets and that are worth a cointegration test by the strategy's own scan; cite the figures you relied on in reason; return [] when the data does not support any. Pairs are hypotheses, not statistical findings.\n", pairCap)
	b.WriteString("- rationale: cite the table (and the strategy's pair results when given); never claim profitability.\n")
	b.WriteString("- confidence: 0 to 1.")
	return b.String()
}

func marketStatsOf(ranked []ScoredMarket) []MarketStat {
	stats := make([]MarketStat, 0, len(ranked))
	for _, market := range ranked {
		stats = append(stats, market.MarketStat)
	}
	return stats
}

// buildMarketPairEvidenceBlock renders the strategy's completed-run pair
// results and stored cointegration scan as small tables with their units.
func buildMarketPairEvidenceBlock(evidence *aiMarketPairEvidence) string {
	var b strings.Builder
	if len(evidence.Pairs) > 0 {
		b.WriteString("\nCompleted backtests of the caller's strategy, per pair (win_rate_pct in percent, pnl_usd = realised P&L in USD, avg_hold_h in hours):\n")
		b.WriteString("pair | trades | win_rate_pct | pnl_usd | avg_hold_h\n")
		for i, pair := range evidence.Pairs {
			if i >= aiMarketPairEvidenceRows {
				fmt.Fprintf(&b, "... %d more pairs not shown\n", len(evidence.Pairs)-i)
				break
			}
			fmt.Fprintf(&b, "%s | %d | %.1f | %.2f | %.1f\n", pair.Pair, pair.Trades, pair.WinRatePct, pair.PnLUSD, pair.AvgDurationHours)
		}
	}
	if len(evidence.Cointegrated) > 0 {
		b.WriteString("\nStored pair scan of the strategy's last runtime (p_value, half_life_bars = candles of the scan's resolution, confidence 0-1, analysed_at):\n")
		b.WriteString("pair | p_value | half_life_bars | confidence | analysed_at\n")
		for i, pair := range evidence.Cointegrated {
			if i >= aiMarketPairEvidenceRows {
				fmt.Fprintf(&b, "... %d more pairs not shown\n", len(evidence.Cointegrated)-i)
				break
			}
			fmt.Fprintf(&b, "%s | %s | %s | %s | %s\n", pair.Pair, formatEvidenceFloat(pair.PValue, 4), formatEvidenceFloat(pair.HalfLife, 1), formatEvidenceFloat(pair.Confidence, 2), formatEvidenceTimestamp(pair.AnalyzedAt))
		}
	}
	if len(evidence.Notes) > 0 {
		b.WriteString("\nNotes on the strategy data:\n")
		for _, note := range evidence.Notes {
			fmt.Fprintf(&b, "- %s\n", note)
		}
	}
	return b.String()
}

func formatEvidenceFloat(value *float64, decimals int) string {
	if value == nil {
		return "n/a"
	}
	return strconv.FormatFloat(*value, 'f', decimals, 64)
}

func formatEvidenceTimestamp(value string) string {
	value = sanitizeStrategyChatText(value, 40)
	if value == "" {
		return "n/a"
	}
	return value
}

// ==================== strategy pair evidence ====================

// marketPairEvidence loads the strategy's pair statistics through the
// evidence source (with the caller's bot token) and keeps the pairs whose
// legs are in the universe. Any failure (including a strategy the caller does
// not own) is logged and yields no evidence: the pairs are an optional extra
// of the selection.
func (s *AIMarketService) marketPairEvidence(ctx context.Context, actor AIAnalysisActor, strategyID int, ranked []ScoredMarket) (*aiMarketPairEvidence, error) {
	if strategyID <= 0 {
		return nil, nil
	}
	if s.marketEvidence == nil {
		return nil, errors.New("strategy evidence source is not configured")
	}
	pairs, cointegrated, notes, err := s.marketEvidence.PairStatsForStrategy(ctx, actor.UserID, actor.IsAdmin, strategyID, actor.BotToken)
	if err != nil {
		return nil, err
	}
	inUniverse := map[string]bool{}
	for _, market := range ranked {
		inUniverse[market.Ticker] = true
	}
	evidence := &aiMarketPairEvidence{}
	for _, pair := range pairs {
		leg1, leg2, ok := splitEvidencePair(pair.Pair)
		if !ok || !inUniverse[leg1] || !inUniverse[leg2] {
			continue
		}
		pair.Pair = leg1 + "/" + leg2
		evidence.Pairs = append(evidence.Pairs, pair)
	}
	for _, pair := range cointegrated {
		leg1, leg2, ok := splitEvidencePair(pair.Pair)
		if !ok || !inUniverse[leg1] || !inUniverse[leg2] {
			continue
		}
		pair.Pair = leg1 + "/" + leg2
		evidence.Cointegrated = append(evidence.Cointegrated, pair)
	}
	for _, note := range notes {
		if text := sanitizeStrategyChatText(note, 200); text != "" {
			evidence.Notes = append(evidence.Notes, text)
		}
		if len(evidence.Notes) >= 6 {
			break
		}
	}
	return evidence, nil
}

// splitEvidencePair reads "BTC-USD/ETH-USD" into two validated tickers.
func splitEvidencePair(pair string) (string, string, bool) {
	parts := strings.Split(pair, "/")
	if len(parts) != 2 {
		return "", "", false
	}
	leg1 := normalizeAIMarketTicker(parts[0])
	leg2 := normalizeAIMarketTicker(parts[1])
	if leg1 == "" || leg2 == "" || leg1 == leg2 {
		return "", "", false
	}
	return leg1, leg2, true
}

// evidencePairsWithin turns the strategy evidence into response pairs whose
// legs are both selected, history first, then the stored scan.
func evidencePairsWithin(selected []string, evidence *aiMarketPairEvidence) []AIMarketPair {
	pairs := []AIMarketPair{}
	if evidence == nil {
		return pairs
	}
	chosen := map[string]bool{}
	for _, ticker := range selected {
		chosen[ticker] = true
	}
	seen := map[string]bool{}
	for _, pair := range evidence.Pairs {
		leg1, leg2, ok := splitEvidencePair(pair.Pair)
		if !ok || !chosen[leg1] || !chosen[leg2] || seen[pairKey(leg1, leg2)] {
			continue
		}
		seen[pairKey(leg1, leg2)] = true
		pairs = append(pairs, AIMarketPair{
			Market1: leg1,
			Market2: leg2,
			Reason: fmt.Sprintf("Completed backtests of this strategy: %d trades, win rate %.1f%%, realised P&L %.2f USD, average hold %.1f h.",
				pair.Trades, pair.WinRatePct, pair.PnLUSD, pair.AvgDurationHours),
			Source: aiMarketPairSourceHistory,
		})
	}
	for _, pair := range evidence.Cointegrated {
		leg1, leg2, ok := splitEvidencePair(pair.Pair)
		if !ok || !chosen[leg1] || !chosen[leg2] || seen[pairKey(leg1, leg2)] {
			continue
		}
		seen[pairKey(leg1, leg2)] = true
		pairs = append(pairs, AIMarketPair{
			Market1: leg1,
			Market2: leg2,
			Reason: fmt.Sprintf("Stored pair scan of the strategy's last runtime: p-value %s, half-life %s bars, confidence %s, analysed %s.",
				formatEvidenceFloat(pair.PValue, 4), formatEvidenceFloat(pair.HalfLife, 1), formatEvidenceFloat(pair.Confidence, 2), formatEvidenceTimestamp(pair.AnalyzedAt)),
			Source: aiMarketPairSourceCointegration,
		})
	}
	return pairs
}

func pairKey(leg1 string, leg2 string) string {
	if leg2 < leg1 {
		leg1, leg2 = leg2, leg1
	}
	return leg1 + "/" + leg2
}

// ==================== validation and response ====================

// marketSelection is the ranked state one selection is answered from, by
// the model or by the deterministic fallback.
type marketSelection struct {
	provider   string
	mode       string
	limit      int
	ranked     []ScoredMarket
	hasDetails bool
	basis      AIMarketSelectionBasis
	evidence   *aiMarketPairEvidence
}

func (sel marketSelection) response(source string, selected []string, pairs []AIMarketPair, rationale string, confidence float64, usedAI bool, fallbackReason string, dropped int) *AIMarketSelectionResponse {
	if pairs == nil {
		pairs = []AIMarketPair{}
	}
	return &AIMarketSelectionResponse{
		Provider:        sel.provider,
		Mode:            sel.mode,
		Source:          source,
		SelectedMarkets: selected,
		Rationale:       rationale,
		Confidence:      confidence,
		UsedAI:          usedAI,
		FallbackReason:  fallbackReason,
		Basis:           sel.basis,
		Pairs:           pairs,
		MarketStats:     marketStatRows(selected, sel.ranked),
		DroppedCount:    dropped,
	}
}

// validateMarketSelection keeps the model's tickers that exist in the ranked
// universe (no duplicates, at most limit) and its pairs whose legs are both
// selected. Everything else is dropped and counted.
func validateMarketSelection(reply *AIMarketSelectionResponse, ranked []ScoredMarket, limit int) (selected []string, pairs []AIMarketPair, dropped int) {
	selected = []string{}
	pairs = []AIMarketPair{}
	if reply == nil {
		return selected, pairs, 0
	}
	universe := map[string]bool{}
	for _, market := range ranked {
		universe[market.Ticker] = true
	}
	chosen := map[string]bool{}
	for _, item := range reply.SelectedMarkets {
		ticker := normalizeAIMarketTicker(item)
		if ticker == "" || !universe[ticker] || chosen[ticker] || len(selected) >= limit {
			dropped++
			continue
		}
		chosen[ticker] = true
		selected = append(selected, ticker)
	}
	pairCap := aiMarketPairCap(limit)
	seen := map[string]bool{}
	for _, pair := range reply.Pairs {
		leg1 := normalizeAIMarketTicker(pair.Market1)
		leg2 := normalizeAIMarketTicker(pair.Market2)
		if leg1 == "" || leg2 == "" || leg1 == leg2 || !chosen[leg1] || !chosen[leg2] || seen[pairKey(leg1, leg2)] || len(pairs) >= pairCap {
			dropped++
			continue
		}
		seen[pairKey(leg1, leg2)] = true
		pairs = append(pairs, AIMarketPair{
			Market1: leg1,
			Market2: leg2,
			Reason:  sanitizeStrategyChatText(pair.Reason, 240),
			Source:  aiMarketPairSourceModel,
		})
	}
	return selected, pairs, dropped
}

// mergeMarketPairs lists the evidence pairs first and adds the model's pairs
// that are not already covered.
func mergeMarketPairs(evidencePairs []AIMarketPair, modelPairs []AIMarketPair) []AIMarketPair {
	merged := make([]AIMarketPair, 0, len(evidencePairs)+len(modelPairs))
	seen := map[string]bool{}
	for _, pair := range evidencePairs {
		merged = append(merged, pair)
		seen[pairKey(pair.Market1, pair.Market2)] = true
	}
	for _, pair := range modelPairs {
		if seen[pairKey(pair.Market1, pair.Market2)] {
			continue
		}
		seen[pairKey(pair.Market1, pair.Market2)] = true
		merged = append(merged, pair)
	}
	return merged
}

// marketStatRows are the statistics of the selected tickers in selection order.
func marketStatRows(selected []string, ranked []ScoredMarket) []AIMarketStatRow {
	byTicker := map[string]ScoredMarket{}
	for _, market := range ranked {
		byTicker[market.Ticker] = market
	}
	rows := make([]AIMarketStatRow, 0, len(selected))
	for _, ticker := range selected {
		market, ok := byTicker[ticker]
		if !ok {
			continue
		}
		rows = append(rows, AIMarketStatRow{
			Ticker:            market.Ticker,
			Volume24hUSD:      market.Volume24hUSD,
			OpenInterestUSD:   market.OpenInterestUSD,
			Trades24h:         market.Trades24h,
			FundingRate:       market.FundingRate,
			OraclePrice:       market.OraclePrice,
			PriceChange24hPct: market.PriceChange24hPct,
			Score:             market.Score,
		})
	}
	return rows
}

// marketSelectionBasis describes the data behind a selection: which score
// criteria had data and which strategy evidence was offered.
func marketSelectionBasis(universe *MarketUniverse, ranked []ScoredMarket, rows int, evidence *aiMarketPairEvidence) AIMarketSelectionBasis {
	basis := AIMarketSelectionBasis{
		UniverseCount:       len(ranked),
		RankedCount:         rows,
		Network:             universe.Network,
		Source:              universe.Source,
		CriteriaUsed:        []string{},
		CriteriaUnavailable: []string{},
	}
	if basis.Network == "" {
		basis.Network = marketUniverseNetwork
	}
	if universe.HasDetails {
		basis.CriteriaUsed = append(basis.CriteriaUsed, "volume", "liquidity", "tradeability", "risk")
		if marketsHavePriceChange(marketStatsOf(ranked)) {
			basis.CriteriaUsed = append(basis.CriteriaUsed, "momentum")
		} else {
			basis.CriteriaUnavailable = append(basis.CriteriaUnavailable, "momentum")
		}
	} else {
		basis.CriteriaUnavailable = append(basis.CriteriaUnavailable, "volume", "liquidity", "tradeability", "risk", "momentum")
	}
	basis.CriteriaUnavailable = append(basis.CriteriaUnavailable, "volatility")
	if evidence != nil && len(evidence.Pairs) > 0 {
		basis.CriteriaUsed = append(basis.CriteriaUsed, "pair_history")
	}
	if evidence != nil && len(evidence.Cointegrated) > 0 {
		basis.CriteriaUsed = append(basis.CriteriaUsed, "cointegration")
	} else {
		basis.CriteriaUnavailable = append(basis.CriteriaUnavailable, "cointegration")
	}
	if universe.Tradable == nil {
		basis.CriteriaUnavailable = append(basis.CriteriaUnavailable, "tradability")
	}
	return basis
}

// aiMarketFallbackReason is the provider failure a caller may see: a fixed
// message by failure class, with the provider's own text only for admins.
// The wording follows the strategy chat's classification.
func aiMarketFallbackReason(provider string, err error, isAdmin bool) string {
	name := providerDisplayName(provider)
	if name == "" {
		name = "The AI provider"
	}
	var message string
	var callErr *aiProviderCallError
	var cutOff *aiReplyCutOffError
	switch {
	case errors.Is(err, context.DeadlineExceeded) || isAIClientTimeout(err):
		message = fmt.Sprintf("%s did not answer in time. Try again.", name)
	case errors.As(err, &cutOff):
		message = aiReplyCutOffMessage
	case errors.As(err, &callErr) && callErr.StatusCode == http.StatusTooManyRequests:
		message = fmt.Sprintf("%s rate limit reached. Try again in a minute.", name)
	case errors.As(err, &callErr) && callErr.StatusCode >= 500:
		message = fmt.Sprintf("%s is having trouble. Try again.", name)
	case errors.As(err, &callErr) && callErr.StatusCode >= 400:
		message = fmt.Sprintf("%s rejected the request or the model is not available. Ask an admin to check the AI provider settings.", name)
	case errors.As(err, &callErr):
		message = fmt.Sprintf("Could not reach %s. Try again.", name)
	default:
		message = fmt.Sprintf("%s could not answer. Try again.", name)
	}
	if isAdmin && err != nil {
		message += " Provider detail: " + truncateAIText(err.Error(), 400)
	}
	return message
}
