package services

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

func marketFloat(value float64) *float64 { return &value }

func marketInt(value int) *int { return &value }

// marketUniverseFixtureDetails are six active markets as the bot lists them
// (24 h volume descending) plus one malformed ticker and one market without
// statistics. Numbers are float64 as JSON decoding produces them.
func marketUniverseFixtureDetails(withChange bool) []interface{} {
	row := func(ticker string, volume, oiUSD float64, trades int, funding, price float64) map[string]interface{} {
		return map[string]interface{}{
			"ticker":            ticker,
			"status":            "ACTIVE",
			"volume_24h":        volume,
			"open_interest":     oiUSD / price,
			"open_interest_usd": oiUSD,
			"next_funding_rate": funding,
			"oracle_price":      price,
			"trades_24h":        float64(trades),
			"price_change_24h":  nil,
		}
	}
	btc := row("BTC-USD", 2.5e9, 1.2e9, 300000, 0.0000125, 84350)
	if withChange {
		btc["price_change_24h"] = 273.98913
	}
	return []interface{}{
		btc,
		row("ETH-USD", 1.1e9, 6e8, 200000, 0.00001, 3200),
		row("SOL-USD", 4e8, 2e8, 90000, -0.000005, 150),
		row("AAVE-USD", 5e7, 2e7, 4000, 0.00002, 300),
		row("ZRO-USD", 5e5, 1e6, 300, 0.00003, 3),
		map[string]interface{}{"ticker": "btc usd", "volume_24h": 1.0},
		map[string]interface{}{"ticker": "NOSTATS-USD", "volume_24h": nil, "oracle_price": "abc", "trades_24h": "n/a"},
	}
}

func marketUniverseFixturePayload(source string, withChange bool) map[string]interface{} {
	details := marketUniverseFixtureDetails(withChange)
	names := make([]interface{}, 0, len(details))
	for _, item := range details {
		names = append(names, item.(map[string]interface{})["ticker"])
	}
	return map[string]interface{}{
		"success": true,
		"data": map[string]interface{}{
			"markets":        names,
			"market_details": details,
			"source":         source,
			"count":          len(details),
		},
	}
}

func fixtureMarketUniverse(t *testing.T, withChange bool, tradable []string) *MarketUniverse {
	t.Helper()
	stats, source, hasDetails := parseMarketUniverse(marketUniverseFixturePayload("dydx", withChange))
	if !hasDetails || len(stats) != 6 {
		t.Fatalf("fixture parse: hasDetails=%v stats=%d", hasDetails, len(stats))
	}
	return &MarketUniverse{Stats: stats, HasDetails: true, Network: marketUniverseNetwork, Source: source, Tradable: tradable}
}

type fakeMarketEvidenceSource struct {
	mu           sync.Mutex
	calls        []string
	tokens       []string
	pairs        []EvidencePairStats
	cointegrated []EvidenceCointegratedPair
	notes        []string
	err          error
}

func (f *fakeMarketEvidenceSource) PairStatsForStrategy(ctx context.Context, userID int, isAdmin bool, strategyID int, botToken string) ([]EvidencePairStats, []EvidenceCointegratedPair, []string, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.calls = append(f.calls, fmt.Sprintf("%d/%t/%d", userID, isAdmin, strategyID))
	f.tokens = append(f.tokens, botToken)
	return f.pairs, f.cointegrated, f.notes, f.err
}

func fixtureMarketEvidence() *fakeMarketEvidenceSource {
	return &fakeMarketEvidenceSource{
		pairs: []EvidencePairStats{
			{Pair: "BTC-USD/ETH-USD", Trades: 12, Wins: 7, WinRatePct: 58.3, PnLUSD: -41.2, AvgDurationHours: 18.5},
			{Pair: "SOL-USD/AAVE-USD", Trades: 3, Wins: 1, WinRatePct: 33.3, PnLUSD: 5, AvgDurationHours: 9},
			{Pair: "not-a-pair", Trades: 1},
		},
		cointegrated: []EvidenceCointegratedPair{
			{Pair: "BTC-USD/SOL-USD", PValue: marketFloat(0.012), HalfLife: marketFloat(18.5), Confidence: marketFloat(0.81), AnalyzedAt: "2026-09-20T10:00:00Z"},
			{Pair: "DOGE-USD/ETH-USD", PValue: marketFloat(0.2)},
		},
		notes: []string{"Only the first 2000 of 3000 trades were analysed.", "runtime strategy-7-42 at http://bot:8889 reported no positions"},
	}
}

func TestParseMarketUniverseReadsDetailsAndToleratesOldBot(t *testing.T) {
	stats, source, hasDetails := parseMarketUniverse(marketUniverseFixturePayload("cache_stale", true))
	if !hasDetails || source != "cache_stale" {
		t.Fatalf("expected details from source cache_stale, got hasDetails=%v source=%q", hasDetails, source)
	}
	got := make([]string, 0, len(stats))
	for _, stat := range stats {
		got = append(got, stat.Ticker)
	}
	if strings.Join(got, ",") != "BTC-USD,ETH-USD,SOL-USD,AAVE-USD,ZRO-USD,NOSTATS-USD" {
		t.Fatalf("expected the bot's order without the malformed ticker, got %v", got)
	}
	btc := stats[0]
	if btc.Volume24hUSD == nil || *btc.Volume24hUSD != 2.5e9 || btc.Trades24h == nil || *btc.Trades24h != 300000 || btc.FundingRate == nil || *btc.FundingRate != 0.0000125 {
		t.Fatalf("unexpected BTC statistics: %+v", btc)
	}
	if btc.PriceChange24hPct == nil || math.Abs(*btc.PriceChange24hPct-0.32586) > 0.001 {
		t.Fatalf("expected the absolute change converted to a percent of the price 24 h ago (~0.326), got %v", btc.PriceChange24hPct)
	}
	if stats[1].PriceChange24hPct != nil {
		t.Fatalf("expected no percent change without an indexer value, got %v", *stats[1].PriceChange24hPct)
	}
	noStats := stats[5]
	if noStats.Volume24hUSD != nil || noStats.OraclePrice != nil || noStats.Trades24h != nil || noStats.PriceChange24hPct != nil {
		t.Fatalf("expected unparseable values to stay nil, got %+v", noStats)
	}

	old, source, hasDetails := parseMarketUniverse(map[string]interface{}{
		"success": true,
		"data":    map[string]interface{}{"markets": []interface{}{"SOL-USD", "BTC-USD", "eth-usd", "bad ticker", "BTC-USD"}},
	})
	if hasDetails || source != "dydx" {
		t.Fatalf("expected a names-only universe with the default source, got hasDetails=%v source=%q", hasDetails, source)
	}
	got = got[:0]
	for _, stat := range old {
		got = append(got, stat.Ticker)
	}
	if strings.Join(got, ",") != "SOL-USD,BTC-USD,ETH-USD" {
		t.Fatalf("expected the bot's order, upper-cased and de-duplicated, got %v", got)
	}
	if stats, _, _ := parseMarketUniverse(nil); stats != nil {
		t.Fatalf("expected nil for a nil payload, got %v", stats)
	}
}

// The bot passes the indexer's priceChange24H through unchanged: the absolute
// 24 h change of the oracle price in quote currency, not a percent. The
// values below were read live on mainnet.
func TestPriceChangePercentUsesTheIndexersAbsoluteChange(t *testing.T) {
	btc := priceChangePercent(marketFloat(273.98913), marketFloat(84350))
	if btc == nil || math.Abs(*btc-0.326) > 0.001 {
		t.Fatalf("expected BTC-USD +273.98913 on 84350 to be about +0.326 %%, got %v", btc)
	}
	eth := priceChangePercent(marketFloat(-0.266), marketFloat(2691.77))
	if eth == nil || math.Abs(*eth-(-0.0099)) > 0.0001 {
		t.Fatalf("expected ETH-USD -0.266 on 2691.77 to be about -0.0099 %%, got %v", eth)
	}
	if priceChangePercent(nil, marketFloat(2691.77)) != nil || priceChangePercent(marketFloat(1), nil) != nil {
		t.Fatal("expected nil when either value is missing")
	}
	if priceChangePercent(marketFloat(84350), marketFloat(84350)) != nil || priceChangePercent(marketFloat(90000), marketFloat(84350)) != nil {
		t.Fatal("expected nil when the price 24 h ago would not be positive")
	}
	rows := []interface{}{
		map[string]interface{}{"ticker": "BTC-USD", "oracle_price": 84350.0, "price_change_24h": 273.98913},
		map[string]interface{}{"ticker": "ETH-USD", "oracle_price": 2691.77, "price_change_24h": -0.266},
		map[string]interface{}{"ticker": "OLD-USD", "oracle_price": 10.0},
	}
	stats, _, _ := parseMarketUniverse(map[string]interface{}{"data": map[string]interface{}{"market_details": rows}})
	if len(stats) != 3 || stats[0].PriceChange24hPct == nil || math.Abs(*stats[0].PriceChange24hPct-0.326) > 0.001 ||
		stats[1].PriceChange24hPct == nil || math.Abs(*stats[1].PriceChange24hPct-(-0.0099)) > 0.0001 || stats[2].PriceChange24hPct != nil {
		t.Fatalf("expected the percent derived per row and nil when the old bot omits the field, got %+v", stats)
	}
}

func TestScoreMarketsIsDeterministicAndPenalisesThinMarkets(t *testing.T) {
	universe := fixtureMarketUniverse(t, true, nil)
	criteria := normalizeAIMarketCriteria(AIMarketCriteria{}, "ai_recommended")

	first := scoreMarkets(universe.Stats, criteria)
	second := scoreMarkets(universe.Stats, criteria)
	order := func(ranked []ScoredMarket) string {
		tickers := make([]string, 0, len(ranked))
		for _, market := range ranked {
			tickers = append(tickers, market.Ticker)
		}
		return strings.Join(tickers, ",")
	}
	if order(first) != order(second) {
		t.Fatalf("expected a deterministic order, got %s then %s", order(first), order(second))
	}
	if order(first) != "BTC-USD,ETH-USD,SOL-USD,AAVE-USD,ZRO-USD,NOSTATS-USD" {
		t.Fatalf("unexpected score order %s", order(first))
	}
	// BTC tops every rank-normalised column (1.0 each) and is the only market
	// with a 24 h change: 0.65 + 0.75 + 0.75 + 0.35 = 2.5.
	if first[0].Score != 2.5 || first[0].Thin {
		t.Fatalf("expected BTC score 2.5 and not thin, got %+v", first[0])
	}
	// ZRO: volume below $1M and 300 trades -> thin -> risk penalty 0.55.
	zro := first[4]
	if zro.Ticker != "ZRO-USD" || !zro.Thin || math.Abs(zro.Score-(-0.12)) > 1e-9 {
		t.Fatalf("expected ZRO thin with score -0.12, got %+v", zro)
	}
	// Unknown statistics rank last and count as thin: score = -risk weight.
	if noStats := first[5]; noStats.Ticker != "NOSTATS-USD" || !noStats.Thin || noStats.Score != -0.55 {
		t.Fatalf("expected the market without statistics last, thin, score -0.55, got %+v", noStats)
	}
	for _, market := range first[:4] {
		if market.Thin {
			t.Fatalf("expected %s not to be thin", market.Ticker)
		}
	}

	// Names only: every score is equal, and the bot's order (24 h volume) is
	// kept instead of an alphabetical one.
	names := scoreMarkets(marketStatsFromTickers([]string{"SOL-USD", "BTC-USD", "ETH-USD"}), criteria)
	if order(names) != "SOL-USD,BTC-USD,ETH-USD" {
		t.Fatalf("expected ties to keep the bot's order, got %s", order(names))
	}
}

func TestBuildMarketTableStatesUnitsAndCapsRows(t *testing.T) {
	tickers := make([]string, 0, 70)
	for i := 0; i < 70; i++ {
		tickers = append(tickers, fmt.Sprintf("M%02d-USD", i))
	}
	ranked := scoreMarkets(marketStatsFromTickers(tickers), normalizeAIMarketCriteria(AIMarketCriteria{}, "ai_recommended"))
	rows := aiMarketPromptRowCount(len(ranked), defaultAIMarketLimit)
	if rows != aiMarketPromptRows {
		t.Fatalf("expected %d rows for a 70-market universe and the default limit, got %d", aiMarketPromptRows, rows)
	}
	table := buildMarketTable(ranked, rows)
	lines := strings.Split(table, "\n")
	if len(lines) != rows+2 {
		t.Fatalf("expected units, header and %d rows, got %d lines", rows, len(lines))
	}
	for _, want := range []string{"vol_24h_usd", "24 h notional volume in USD", "oi_usd", "trades_24h", "funding_1h_frac", "hourly funding rate as a fraction", "oracle_price_usd", "n/a = not reported"} {
		if !strings.Contains(lines[0]+lines[1], want) {
			t.Fatalf("expected the header to state %q, got:\n%s\n%s", want, lines[0], lines[1])
		}
	}
	if strings.Contains(lines[1], "24h change %") {
		t.Fatalf("expected no change column without change data, got %s", lines[1])
	}
	if !strings.Contains(table, "60 | M59-USD | n/a | n/a | n/a | n/a | n/a | -0.5500 | yes") || strings.Contains(table, "M60-USD") {
		t.Fatalf("expected exactly the first 60 markets in bot order with n/a cells, got:\n%s", table)
	}
	for _, tc := range []struct{ universe, limit, want int }{{70, 100, 70}, {200, 100, 100}, {10, 5, 10}, {200, 20, 60}} {
		if got := aiMarketPromptRowCount(tc.universe, tc.limit); got != tc.want {
			t.Fatalf("aiMarketPromptRowCount(%d, %d) = %d, want %d", tc.universe, tc.limit, got, tc.want)
		}
	}

	universe := fixtureMarketUniverse(t, true, nil)
	withData := buildMarketTable(scoreMarkets(universe.Stats, normalizeAIMarketCriteria(AIMarketCriteria{}, "ai_recommended")), 6)
	if !strings.Contains(withData, "| 24h change % |") || !strings.Contains(withData, "1 | BTC-USD | 2500000000 | 1200000000 | 300000 | 0.0000125 | 84350 | 0.33 | 2.5000 | no") {
		t.Fatalf("expected the BTC row with USD, count, fraction, price and percent cells, got:\n%s", withData)
	}
	if !strings.Contains(withData, "6 | NOSTATS-USD | n/a | n/a | n/a | n/a | n/a | n/a | -0.5500 | yes") {
		t.Fatalf("expected n/a cells for the market without statistics, got:\n%s", withData)
	}
}

func TestValidateMarketSelectionDropsUnknownDuplicatesAndHalfPairs(t *testing.T) {
	universe := fixtureMarketUniverse(t, false, nil)
	ranked := scoreMarkets(universe.Stats, normalizeAIMarketCriteria(AIMarketCriteria{}, "ai_recommended"))
	reply := &AIMarketSelectionResponse{
		SelectedMarkets: []string{" btc-usd ", "BTC-USD", "ETH-USD", "DOGE-USD", "SOL-USD", "AAVE-USD"},
		Pairs: []AIMarketPair{
			{Market1: "BTC-USD", Market2: "ETH-USD", Reason: "both lead volume; see http://bot:8889 and dydx1qy352euf40x77qfrg4ncn27daufrg4ncn27dau"},
			{Market1: "btc-usd", Market2: "SOL-USD", Reason: "deep books"},
			{Market1: "ETH-USD", Market2: "BTC-USD", Reason: "duplicate of the first"},
			{Market1: "BTC-USD", Market2: "AAVE-USD", Reason: "AAVE is not selected"},
			{Market1: "BTC-USD", Market2: "BTC-USD", Reason: "same leg"},
			{Market1: "BTC-USD", Market2: "ZRO-USD", Reason: "ZRO is not selected"},
		},
	}
	selected, pairs, dropped := validateMarketSelection(reply, ranked, 3)
	if strings.Join(selected, ",") != "BTC-USD,ETH-USD,SOL-USD" {
		t.Fatalf("expected three validated tickers, got %v", selected)
	}
	if len(pairs) != 1 || pairs[0].Market1 != "BTC-USD" || pairs[0].Market2 != "ETH-USD" || pairs[0].Source != aiMarketPairSourceModel {
		t.Fatalf("expected one model pair within the pair cap for limit 3, got %+v", pairs)
	}
	if strings.Contains(pairs[0].Reason, "http://") || strings.Contains(pairs[0].Reason, "dydx1") || strings.Contains(pairs[0].Reason, "8889") {
		t.Fatalf("expected the pair reason to be sanitized, got %q", pairs[0].Reason)
	}
	// Dropped: duplicate BTC, unknown DOGE, AAVE beyond the limit, and five
	// pairs (one over the cap of 1, one duplicate, two with an unselected
	// leg, one with equal legs).
	if dropped != 8 {
		t.Fatalf("expected 8 dropped items, got %d", dropped)
	}

	selected, pairs, dropped = validateMarketSelection(reply, ranked, 4)
	if strings.Join(selected, ",") != "BTC-USD,ETH-USD,SOL-USD,AAVE-USD" || len(pairs) != 2 || pairs[1].Market2 != "SOL-USD" || dropped != 6 {
		t.Fatalf("expected four tickers, two pairs and 6 dropped for limit 4, got %v %+v %d", selected, pairs, dropped)
	}
	if selected, pairs, dropped := validateMarketSelection(nil, ranked, 3); len(selected) != 0 || pairs == nil || dropped != 0 {
		t.Fatalf("expected empty slices for a nil reply, got %v %v %d", selected, pairs, dropped)
	}
}

func TestFallbackAIMarketSelectionFollowsScoreOrderNotAlphabet(t *testing.T) {
	universe := fixtureMarketUniverse(t, false, nil)
	ranked := scoreMarkets(universe.Stats, normalizeAIMarketCriteria(AIMarketCriteria{}, "ai_recommended"))
	evidence := &aiMarketPairEvidence{
		Pairs:        []EvidencePairStats{{Pair: "BTC-USD/ETH-USD", Trades: 12, WinRatePct: 58.3, PnLUSD: -41.2, AvgDurationHours: 18.5}, {Pair: "SOL-USD/AAVE-USD", Trades: 3}},
		Cointegrated: []EvidenceCointegratedPair{{Pair: "ETH-USD/SOL-USD", PValue: marketFloat(0.03)}},
	}
	sel := marketSelection{
		provider:   ExternalAPIProviderGrok,
		mode:       "ai_recommended",
		limit:      3,
		ranked:     ranked,
		hasDetails: true,
		basis:      marketSelectionBasis(universe, ranked, 6, evidence),
		evidence:   evidence,
	}
	result := fallbackAIMarketSelection(sel, "Grok is having trouble. Try again.")
	if strings.Join(result.SelectedMarkets, ",") != "BTC-USD,ETH-USD,SOL-USD" {
		t.Fatalf("expected the score order (alphabetical would start with AAVE-USD), got %v", result.SelectedMarkets)
	}
	if result.Source != aiMarketSourceDeterministic || result.UsedAI || result.Confidence != 0 || result.FallbackReason != "Grok is having trouble. Try again." {
		t.Fatalf("unexpected fallback envelope: %+v", result)
	}
	if !strings.Contains(result.Rationale, "24 h volume, open interest and trade count") || strings.Contains(strings.ToLower(result.Rationale), "first active") {
		t.Fatalf("expected an honest data-driven rationale, got %q", result.Rationale)
	}
	if len(result.Pairs) != 2 || result.Pairs[0].Source != aiMarketPairSourceHistory || result.Pairs[0].Market1 != "BTC-USD" || result.Pairs[1].Source != aiMarketPairSourceCointegration || result.Pairs[1].Market1 != "ETH-USD" {
		t.Fatalf("expected the strategy's pairs among the selected markets, got %+v", result.Pairs)
	}
	if !strings.Contains(result.Pairs[0].Reason, "12 trades, win rate 58.3%, realised P&L -41.20 USD, average hold 18.5 h") {
		t.Fatalf("expected the pair figures in the reason, got %q", result.Pairs[0].Reason)
	}
	if len(result.MarketStats) != 3 || result.MarketStats[0].Ticker != "BTC-USD" || result.MarketStats[0].Score != 2.15 || result.MarketStats[0].Volume24hUSD == nil {
		t.Fatalf("expected statistics rows for the selected markets, got %+v", result.MarketStats)
	}
	if result.Basis.UniverseCount != 6 || result.Basis.RankedCount != 6 || result.Basis.Network != "mainnet" || result.Basis.Source != "dydx" {
		t.Fatalf("unexpected basis %+v", result.Basis)
	}
	if strings.Join(result.Basis.CriteriaUsed, ",") != "volume,liquidity,tradeability,risk,pair_history,cointegration" || strings.Join(result.Basis.CriteriaUnavailable, ",") != "momentum,volatility,tradability" {
		t.Fatalf("unexpected criteria %+v", result.Basis)
	}

	names := scoreMarkets(marketStatsFromTickers([]string{"SOL-USD", "BTC-USD", "ETH-USD"}), normalizeAIMarketCriteria(AIMarketCriteria{}, "ai_recommended"))
	namesOnly := fallbackAIMarketSelection(marketSelection{provider: ExternalAPIProviderGrok, mode: "ai_recommended", limit: 5, ranked: names}, "reason")
	if strings.Join(namesOnly.SelectedMarkets, ",") != "SOL-USD,BTC-USD,ETH-USD" || !strings.Contains(namesOnly.Rationale, "bot's 24 h volume order") {
		t.Fatalf("expected the bot's order and a rationale saying so, got %+v", namesOnly)
	}
	if namesOnly.Pairs == nil || len(namesOnly.Pairs) != 0 || len(namesOnly.MarketStats) != 3 {
		t.Fatalf("expected empty pairs and statistics rows, got %+v", namesOnly)
	}
}

// marketUniverseBotStub serves the bot's perpetual-markets route for both
// purposes and counts the requests it receives.
type marketUniverseBotStub struct {
	server   *httptest.Server
	mu       sync.Mutex
	requests []string
	fail     map[string]bool
}

func newMarketUniverseBotStub(t *testing.T) *marketUniverseBotStub {
	t.Helper()
	stub := &marketUniverseBotStub{fail: map[string]bool{}}
	stub.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/markets/perpetuals" {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		purpose := r.URL.Query().Get("purpose")
		if purpose == "" {
			purpose = marketUniversePurposeRuntime
		}
		stub.mu.Lock()
		stub.requests = append(stub.requests, purpose)
		failing := stub.fail[purpose]
		stub.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		if failing {
			w.WriteHeader(http.StatusServiceUnavailable)
			_, _ = w.Write([]byte(`{"success":false,"message":"market data unavailable","data":null}`))
			return
		}
		payload := marketUniverseFixturePayload("dydx", purpose == marketUniversePurposeBacktest)
		if purpose == marketUniversePurposeRuntime {
			// The runtime list (testnet-style) lacks AAVE and carries no change.
			data := payload["data"].(map[string]interface{})
			data["markets"] = []interface{}{"BTC-USD", "ETH-USD", "SOL-USD", "ZRO-USD", "NOSTATS-USD"}
			details := []interface{}{}
			for _, item := range data["market_details"].([]interface{}) {
				if item.(map[string]interface{})["ticker"] != "AAVE-USD" {
					details = append(details, item)
				}
			}
			data["market_details"] = details
		}
		_ = json.NewEncoder(w).Encode(payload)
	}))
	t.Cleanup(stub.server.Close)
	return stub
}

func (s *marketUniverseBotStub) setFailing(purpose string, failing bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.fail[purpose] = failing
}

func (s *marketUniverseBotStub) count(purpose string) int {
	s.mu.Lock()
	defer s.mu.Unlock()
	n := 0
	for _, p := range s.requests {
		if p == purpose {
			n++
		}
	}
	return n
}

func TestMarketUniverseLoaderCachesAndServesStaleWhenBotIsDown(t *testing.T) {
	stub := newMarketUniverseBotStub(t)
	loader := NewMarketUniverseLoader(NewBotAPIClient(stub.server.URL, ""))
	now := time.Date(2026, 9, 27, 12, 0, 0, 0, time.UTC)
	loader.now = func() time.Time { return now }

	universe, err := loader.Load(context.Background())
	if err != nil {
		t.Fatalf("first load: %v", err)
	}
	if stub.count(marketUniversePurposeBacktest) != 1 || stub.count(marketUniversePurposeRuntime) != 1 {
		t.Fatalf("expected one backtest-purpose and one runtime request, got %v", stub.requests)
	}
	if universe.Source != "dydx" || universe.Network != "mainnet" || !universe.HasDetails || len(universe.Stats) != 6 {
		t.Fatalf("unexpected universe %+v", universe)
	}
	if strings.Join(universe.Tradable, ",") != "BTC-USD,ETH-USD,SOL-USD,ZRO-USD,NOSTATS-USD" {
		t.Fatalf("expected the runtime tickers as the tradable list, got %v", universe.Tradable)
	}
	if universe.Stats[0].PriceChange24hPct == nil {
		t.Fatal("expected the mainnet statistics (with the 24 h change) to be the ranking data")
	}

	now = now.Add(30 * time.Second)
	cached, err := loader.Load(context.Background())
	if err != nil {
		t.Fatalf("cached load: %v", err)
	}
	if cached.Source != marketUniverseSourceBackendCache || len(stub.requests) != 2 {
		t.Fatalf("expected a fresh backend cache hit without bot calls, got source=%q requests=%v", cached.Source, stub.requests)
	}

	stub.setFailing(marketUniversePurposeBacktest, true)
	stub.setFailing(marketUniversePurposeRuntime, true)
	now = now.Add(5 * time.Minute)
	stale, err := loader.Load(context.Background())
	if err != nil {
		t.Fatalf("stale load: %v", err)
	}
	if stale.Source != marketUniverseSourceBackendStale || len(stale.Stats) != 6 || len(stale.Tradable) != 5 || len(stub.requests) != 4 {
		t.Fatalf("expected the stale universe after failed bot calls, got source=%q stats=%d tradable=%d requests=%v", stale.Source, len(stale.Stats), len(stale.Tradable), stub.requests)
	}

	now = now.Add(6 * time.Minute)
	if _, err := loader.Load(context.Background()); err == nil {
		t.Fatal("expected an error once the stale universe is older than ten minutes and the bot is down")
	} else {
		var apiErr *BotAPIError
		if !errors.As(err, &apiErr) || apiErr.StatusCode != http.StatusServiceUnavailable {
			t.Fatalf("expected the bot's 503 to surface, got %v", err)
		}
	}

	// Only the runtime list failing drops the tradability filter.
	stub.setFailing(marketUniversePurposeBacktest, false)
	now = now.Add(time.Hour)
	partial, err := loader.Load(context.Background())
	if err != nil {
		t.Fatalf("partial load: %v", err)
	}
	if partial.Tradable != nil || partial.Source != "dydx" || len(partial.Stats) != 6 {
		t.Fatalf("expected statistics without a tradable list, got %+v", partial)
	}
	if _, err := (*MarketUniverseLoader)(nil).Load(context.Background()); err == nil {
		t.Fatal("expected a nil loader to refuse")
	}
}

func TestSelectMarketsGroundsPromptAndValidatesReply(t *testing.T) {
	grokChatEnv(t)
	var captured map[string]any
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		captured = decodeAIRequest(t, req)
		return aiJSONResponse(http.StatusOK, xaiCompletedResponse(`{"selected_markets":["BTC-USD","ETH-USD","SOL-USD","AAVE-USD","BTC-USD"],"pairs":[{"market_1":"BTC-USD","market_2":"ETH-USD","reason":"top two by volume"},{"market_1":"ETH-USD","market_2":"SOL-USD","reason":"both above 90000 trades"}],"rationale":"BTC and ETH lead on volume and open interest; SOL follows.","confidence":0.8}`)), nil
	})
	evidence := fixtureMarketEvidence()
	service.SetStrategyEvidenceSource(evidence)
	universe := fixtureMarketUniverse(t, true, []string{"BTC-USD", "ETH-USD", "SOL-USD", "ZRO-USD", "NOSTATS-USD"})

	result, err := service.SelectMarkets(context.Background(), AIAnalysisActor{UserID: 7, BotToken: "user-jwt"}, AIMarketSelectionRequest{
		Provider:   "grok",
		Mode:       "ai_recommended",
		Limit:      4,
		Strategy:   "mean reversion on majors",
		StrategyID: 42,
		Markets:    []string{"BTC-USD", "ETH-USD", "SOL-USD", "AAVE-USD", "ZRO-USD", "NOSTATS-USD"},
		Criteria: AIMarketCriteria{
			Objective: "Liquid Majors; see http://bot:8889 for strategy-7-42 " + strings.Repeat("x", 100),
			Notes:     "avoid meme coins; runtime strategy-7-42 at http://bot:8889",
		},
	}, universe)
	if err != nil {
		t.Fatalf("SelectMarkets returned error: %v", err)
	}

	if captured["model"] != "grok-4.3" || captured["max_output_tokens"] != float64(4000) {
		t.Fatalf("expected grok-4.3 with a 4000 token budget, got model=%v tokens=%v", captured["model"], captured["max_output_tokens"])
	}
	reasoning, _ := captured["reasoning"].(map[string]any)
	if reasoning["effort"] != "low" {
		t.Fatalf("expected low effort for market selection, got %#v", captured["reasoning"])
	}
	text, _ := captured["text"].(map[string]any)
	format, _ := text["format"].(map[string]any)
	schema, _ := format["schema"].(map[string]any)
	required, _ := schema["required"].([]any)
	properties, _ := schema["properties"].(map[string]any)
	selectedSchema, _ := properties["selected_markets"].(map[string]any)
	pairsSchema, _ := properties["pairs"].(map[string]any)
	confidenceSchema, _ := properties["confidence"].(map[string]any)
	if format["strict"] != true || len(required) != 4 || selectedSchema["maxItems"] != float64(4) || pairsSchema["maxItems"] != float64(2) || confidenceSchema["maximum"] != float64(1) {
		t.Fatalf("unexpected strict schema: %#v", schema)
	}
	input, _ := captured["input"].([]any)
	if len(input) != 2 {
		t.Fatalf("expected a system and a user turn, got %d", len(input))
	}
	prompt, _ := input[1].(map[string]any)["content"].(string)
	for _, want := range []string{
		"mean reversion on majors",
		"Statistics available: 24 h volume, open interest, 24 h trade count, hourly funding rate, oracle price, 24 h price change.",
		"Statistics NOT available: volatility, cointegration.",
		"rank | ticker | vol_24h_usd | oi_usd | trades_24h | funding_1h_frac | oracle_price_usd | 24h change % | score | thin",
		"1 | BTC-USD | 2500000000 | 1200000000 | 300000 | 0.0000125 | 84350 | 0.33 | 2.5000 | no",
		"5 of 5 eligible markets are shown",
		"BTC-USD/ETH-USD | 12 | 58.3 | -41.20 | 18.5",
		"BTC-USD/SOL-USD | 0.0120 | 18.5 | 0.81 | 2026-09-20T10:00:00Z",
		"- Only the first 2000 of 3000 trades were analysed.",
		"- runtime the runtime at <url> reported no positions",
		"avoid meme coins; runtime the runtime at <url>",
		// The objective is sanitized, lower-cased and cut at 64 characters.
		"Objective: liquid majors; see <url> for the runtime xxxx",
		"at most 2 pairs",
		"never claim profitability",
	} {
		if !strings.Contains(prompt, want) {
			t.Fatalf("expected the prompt to contain %q, got:\n%s", want, prompt)
		}
	}
	for _, forbidden := range []string{"AAVE-USD", "DOGE-USD", "strategy-7-42", "http://", "8889", "not-a-pair", strings.Repeat("x", 30)} {
		if strings.Contains(prompt, forbidden) {
			t.Fatalf("expected the prompt not to contain %q, got:\n%s", forbidden, prompt)
		}
	}
	if len(prompt) > 6*1024 {
		t.Fatalf("expected a compact prompt, got %d bytes", len(prompt))
	}
	if len(evidence.calls) != 1 || evidence.calls[0] != "7/false/42" || evidence.tokens[0] != "user-jwt" {
		t.Fatalf("expected the evidence source to be asked once for the caller's strategy with the caller's bot token, got %v %v", evidence.calls, evidence.tokens)
	}

	if result.Source != aiMarketSourceAI || !result.UsedAI || result.Confidence != 0.8 || result.FallbackReason != "" {
		t.Fatalf("unexpected envelope %+v", result)
	}
	if strings.Join(result.SelectedMarkets, ",") != "BTC-USD,ETH-USD,SOL-USD" || result.DroppedCount != 2 {
		t.Fatalf("expected the validated tickers with AAVE (not tradable) and the duplicate dropped, got %v dropped=%d", result.SelectedMarkets, result.DroppedCount)
	}
	if len(result.Pairs) != 3 ||
		result.Pairs[0].Source != aiMarketPairSourceHistory || result.Pairs[0].Market1 != "BTC-USD" || result.Pairs[0].Market2 != "ETH-USD" ||
		result.Pairs[1].Source != aiMarketPairSourceCointegration || result.Pairs[1].Market2 != "SOL-USD" ||
		result.Pairs[2].Source != aiMarketPairSourceModel || result.Pairs[2].Market1 != "ETH-USD" || result.Pairs[2].Reason != "both above 90000 trades" {
		t.Fatalf("expected history, scan and model pairs in that order, got %+v", result.Pairs)
	}
	if result.Basis.UniverseCount != 5 || result.Basis.RankedCount != 5 || result.Basis.Network != "mainnet" || result.Basis.Source != "dydx" {
		t.Fatalf("unexpected basis %+v", result.Basis)
	}
	if strings.Join(result.Basis.CriteriaUsed, ",") != "volume,liquidity,tradeability,risk,momentum,pair_history,cointegration" || strings.Join(result.Basis.CriteriaUnavailable, ",") != "volatility" {
		t.Fatalf("unexpected criteria %+v", result.Basis)
	}
	if len(result.MarketStats) != 3 || result.MarketStats[0].Ticker != "BTC-USD" || *result.MarketStats[0].Volume24hUSD != 2.5e9 || result.MarketStats[0].Score != 2.5 || result.MarketStats[0].PriceChange24hPct == nil || result.MarketStats[1].PriceChange24hPct != nil {
		t.Fatalf("unexpected statistics rows %+v", result.MarketStats)
	}
	if result.Rationale != "BTC and ETH lead on volume and open interest; SOL follows." {
		t.Fatalf("unexpected rationale %q", result.Rationale)
	}

	encoded, err := json.Marshal(result)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	for _, want := range []string{`"basis":{"universe_count":5`, `"pairs":[{"market_1":"BTC-USD"`, `"market_stats":[{"ticker":"BTC-USD","volume_24h_usd":2500000000`, `"price_change_24h_pct":null`, `"dropped_count":2`} {
		if !strings.Contains(string(encoded), want) {
			t.Fatalf("expected the JSON to contain %s, got %s", want, encoded)
		}
	}
}

func TestSelectMarketsFallsBackInScoreOrderWhenProviderFails(t *testing.T) {
	grokChatEnv(t)
	attempts := 0
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		attempts++
		return aiJSONResponse(http.StatusNotFound, `{"code":"not-found","error":"The model grok-9 does not exist"}`), nil
	})
	evidence := fixtureMarketEvidence()
	service.SetStrategyEvidenceSource(evidence)
	universe := fixtureMarketUniverse(t, false, nil)
	req := AIMarketSelectionRequest{Provider: "grok", Mode: "most_profitable", Limit: 3, StrategyID: 42}

	result, err := service.SelectMarkets(context.Background(), AIAnalysisActor{UserID: 7}, req, universe)
	if err != nil {
		t.Fatalf("SelectMarkets returned error: %v", err)
	}
	if attempts != 1 {
		t.Fatalf("expected one attempt for a non-retryable status, got %d", attempts)
	}
	if result.Source != aiMarketSourceDeterministic || result.UsedAI || strings.Join(result.SelectedMarkets, ",") != "BTC-USD,ETH-USD,SOL-USD" {
		t.Fatalf("expected the score-ordered fallback, got %+v", result)
	}
	if result.FallbackReason != "Grok rejected the request or the model is not available. Ask an admin to check the AI provider settings." {
		t.Fatalf("expected the fixed non-admin message, got %q", result.FallbackReason)
	}
	if len(result.Pairs) != 2 || result.Pairs[0].Source != aiMarketPairSourceHistory || result.Pairs[1].Source != aiMarketPairSourceCointegration {
		t.Fatalf("expected only the strategy's own pairs in the fallback, got %+v", result.Pairs)
	}
	if len(result.MarketStats) != 3 || result.Basis.UniverseCount != 6 || result.DroppedCount != 0 {
		t.Fatalf("unexpected fallback basis %+v %+v", result.Basis, result.MarketStats)
	}

	admin, err := service.SelectMarkets(context.Background(), AIAnalysisActor{UserID: 2, IsAdmin: true}, req, universe)
	if err != nil {
		t.Fatalf("admin SelectMarkets returned error: %v", err)
	}
	if !strings.Contains(admin.FallbackReason, "Provider detail:") || !strings.Contains(admin.FallbackReason, "grok-9") {
		t.Fatalf("expected the provider detail for an admin, got %q", admin.FallbackReason)
	}
	if evidence.calls[1] != "2/true/42" {
		t.Fatalf("expected the admin flag to reach the evidence source, got %v", evidence.calls)
	}
}

func TestSelectMarketsRejectsThinUniverseAndKeepsBotOrderWithoutStatistics(t *testing.T) {
	grokChatEnv(t)
	var prompt string
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		payload := decodeAIRequest(t, req)
		input, _ := payload["input"].([]any)
		prompt, _ = input[len(input)-1].(map[string]any)["content"].(string)
		return aiJSONResponse(http.StatusOK, xaiCompletedResponse(`{"selected_markets":["ETH-USD","DOGE-USD"],"pairs":[],"rationale":"one valid","confidence":0.5}`)), nil
	})

	universe := fixtureMarketUniverse(t, false, []string{"BTC-USD"})
	if _, err := service.SelectMarkets(context.Background(), AIAnalysisActor{UserID: 7}, AIMarketSelectionRequest{Provider: "grok"}, universe); err == nil || !strings.Contains(err.Error(), "at least two tradable dYdX markets") {
		t.Fatalf("expected a universe of one tradable market to be refused, got %v", err)
	}
	if _, err := service.SelectMarkets(context.Background(), AIAnalysisActor{UserID: 7}, AIMarketSelectionRequest{Provider: "grok"}, nil); err == nil {
		t.Fatal("expected a nil universe to be refused")
	}

	stats, _, hasDetails := parseMarketUniverse(map[string]interface{}{"data": map[string]interface{}{"markets": []interface{}{"SOL-USD", "BTC-USD", "ETH-USD"}}})
	namesOnly := &MarketUniverse{Stats: stats, HasDetails: hasDetails, Network: "mainnet", Source: "cache"}
	result, err := service.SelectMarkets(context.Background(), AIAnalysisActor{UserID: 7}, AIMarketSelectionRequest{Provider: "grok", Limit: 2, StrategyID: 9}, namesOnly)
	if err != nil {
		t.Fatalf("SelectMarkets returned error: %v", err)
	}
	if !strings.Contains(prompt, "every numeric cell is n/a") || !strings.Contains(prompt, "1 | SOL-USD | n/a") {
		t.Fatalf("expected the prompt to say no statistics exist and keep the bot's order, got:\n%s", prompt)
	}
	// The reply named two tickers of which only one exists: too few after
	// validation, so the fallback answers in the bot's order, never
	// alphabetically.
	if result.Source != aiMarketSourceDeterministic || strings.Join(result.SelectedMarkets, ",") != "SOL-USD,BTC-USD" || result.FallbackReason != "AI response did not include enough valid dYdX markets." {
		t.Fatalf("expected the bot-order fallback, got %+v", result)
	}
	if strings.Join(result.Basis.CriteriaUnavailable, ",") != "volume,liquidity,tradeability,risk,momentum,volatility,cointegration,tradability" || len(result.Basis.CriteriaUsed) != 0 {
		t.Fatalf("expected every criterion unavailable without statistics or evidence, got %+v", result.Basis)
	}
	if result.Basis.Source != "cache" || result.Pairs == nil || len(result.Pairs) != 0 {
		t.Fatalf("expected the cache source echoed and an empty pairs list, got %+v", result)
	}
}

// TestSelectMarketsCutOffRepliesFallBackToScoreOrder: a Chat Completions or
// Messages API reply that stopped at the token limit is partial JSON, never
// parsed; the selection falls back to the score order with the fixed
// cut-off message, and the budget sent is the market-selection one.
func TestSelectMarketsCutOffRepliesFallBackToScoreOrder(t *testing.T) {
	t.Setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
	t.Setenv("DEEPSEEK_MODEL", "")
	t.Setenv("DEEPSEEK_BASE_URL", "")
	t.Setenv("AI_PROVIDER_DEEPSEEK_ENABLED", "")
	t.Setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
	t.Setenv("ANTHROPIC_MODEL", "")
	t.Setenv("ANTHROPIC_BASE_URL", "")
	t.Setenv("AI_PROVIDER_CLAUDE_ENABLED", "")
	universe := fixtureMarketUniverse(t, false, nil)

	deepseek := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		payload := decodeAIRequest(t, req)
		if payload["max_tokens"] != float64(aiMarketSelectionMaxTokens) {
			t.Fatalf("expected max_tokens %d, got %#v", aiMarketSelectionMaxTokens, payload["max_tokens"])
		}
		return aiJSONResponse(http.StatusOK, `{"choices":[{"message":{"content":"{\"selected_markets\":[\"BTC-USD\",\"ETH-USD\",\"SOL-USD\"],\"pairs\":[{\"market_1\":\"BTC-USD\",\"market_2\":\"ETH-U"},"finish_reason":"length"}],"usage":{"prompt_tokens":900,"completion_tokens":2000,"total_tokens":2900}}`), nil
	})
	req := AIMarketSelectionRequest{Provider: "deepseek", Limit: 3}
	result, err := deepseek.SelectMarkets(context.Background(), AIAnalysisActor{UserID: 7}, req, universe)
	if err != nil {
		t.Fatalf("SelectMarkets returned error: %v", err)
	}
	if result.Source != aiMarketSourceDeterministic || result.UsedAI || result.FallbackReason != aiReplyCutOffMessage || strings.Join(result.SelectedMarkets, ",") != "BTC-USD,ETH-USD,SOL-USD" {
		t.Fatalf("expected the score-ordered fallback with the cut-off message, got %+v", result)
	}
	admin, err := deepseek.SelectMarkets(context.Background(), AIAnalysisActor{UserID: 2, IsAdmin: true}, req, universe)
	if err != nil || !strings.HasPrefix(admin.FallbackReason, aiReplyCutOffMessage) || !strings.Contains(admin.FallbackReason, "Provider detail:") {
		t.Fatalf("expected the cut-off message with detail for admins, got %+v %v", admin, err)
	}

	claude := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		payload := decodeAIRequest(t, req)
		if payload["max_tokens"] != float64(aiMarketSelectionMaxTokens) {
			t.Fatalf("expected max_tokens %d, got %#v", aiMarketSelectionMaxTokens, payload["max_tokens"])
		}
		return aiJSONResponse(http.StatusOK, `{"content":[{"type":"text","text":"{\"selected_markets\":[\"BTC-USD\""}],"stop_reason":"max_tokens","usage":{"input_tokens":900,"output_tokens":2000}}`), nil
	})
	result, err = claude.SelectMarkets(context.Background(), AIAnalysisActor{UserID: 7}, AIMarketSelectionRequest{Provider: "claude", Limit: 3}, universe)
	if err != nil {
		t.Fatalf("SelectMarkets returned error: %v", err)
	}
	if result.Source != aiMarketSourceDeterministic || result.UsedAI || result.FallbackReason != aiReplyCutOffMessage {
		t.Fatalf("expected the fallback with the cut-off message for Claude, got %+v", result)
	}
}

func TestAIMarketFallbackReasonHidesProviderDetailFromNonAdmins(t *testing.T) {
	cases := []struct {
		err  error
		want string
	}{
		{context.DeadlineExceeded, "Grok did not answer in time. Try again."},
		{&aiProviderCallError{Timeout: true, Message: "failed to reach AI provider: dial tcp 10.0.0.9:443 i/o timeout"}, "Grok did not answer in time. Try again."},
		{&aiReplyCutOffError{Provider: "grok"}, aiReplyCutOffMessage},
		{&aiProviderCallError{StatusCode: http.StatusTooManyRequests, Message: "AI provider rate limit reached"}, "Grok rate limit reached. Try again in a minute."},
		{&aiProviderCallError{StatusCode: http.StatusServiceUnavailable, Message: "AI provider returned status 503: upstream at https://api.x.ai/v1/responses"}, "Grok is having trouble. Try again."},
		{&aiProviderCallError{StatusCode: http.StatusNotFound, Message: "AI provider returned status 404: The model grok-9 does not exist"}, "Grok rejected the request or the model is not available. Ask an admin to check the AI provider settings."},
		{&aiProviderCallError{Message: "failed to reach AI provider: connection refused"}, "Could not reach Grok. Try again."},
		{errors.New("AI provider returned non-JSON market ranking"), "Grok could not answer. Try again."},
	}
	for _, tc := range cases {
		got := aiMarketFallbackReason(ExternalAPIProviderGrok, tc.err, false)
		if got != tc.want {
			t.Fatalf("for %v expected %q, got %q", tc.err, tc.want, got)
		}
		admin := aiMarketFallbackReason(ExternalAPIProviderGrok, tc.err, true)
		if !strings.HasPrefix(admin, tc.want) || !strings.Contains(admin, "Provider detail: "+tc.err.Error()) {
			t.Fatalf("expected the admin message to add the provider detail, got %q", admin)
		}
	}
}
