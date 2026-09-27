package services

import (
	"encoding/json"
	"errors"
	"math"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// Parsers and aggregators of the bot payloads. Every field is picked by
// name; unknown keys are ignored, missing numbers stay nil where the
// distinction matters (per-trade costs) and are zero otherwise.

// botBacktestTrade is one ledger row of a backtest run.
type botBacktestTrade struct {
	Pair          string
	PnLUSD        float64
	PnLPct        float64
	FeeCost       *float64
	SlippageCost  *float64
	DurationHours float64
	EntryZScore   float64
	Win           bool
	ExitReason    string
}

// botLiveTrade is one closed trade of the runtime.
type botLiveTrade struct {
	Pair          string
	PnLUSD        float64
	PnLPct        *float64
	DurationHours float64
	ClosedAt      time.Time
}

func evidenceNumber(source map[string]interface{}, key string) (float64, bool) {
	value, ok := source[key]
	if !ok || value == nil {
		return 0, false
	}
	switch typed := value.(type) {
	case float64:
		if math.IsNaN(typed) || math.IsInf(typed, 0) {
			return 0, false
		}
		return typed, true
	case float32:
		return float64(typed), true
	case int:
		return float64(typed), true
	case int64:
		return float64(typed), true
	case json.Number:
		parsed, err := typed.Float64()
		return parsed, err == nil
	case string:
		parsed, err := strconv.ParseFloat(strings.TrimSpace(typed), 64)
		if err != nil || math.IsNaN(parsed) || math.IsInf(parsed, 0) {
			return 0, false
		}
		return parsed, true
	default:
		return 0, false
	}
}

func evidenceOptionalNumber(source map[string]interface{}, key string) *float64 {
	value, ok := evidenceNumber(source, key)
	if !ok {
		return nil
	}
	return &value
}

func evidenceOptionalInt(source map[string]interface{}, key string) *int {
	value, ok := evidenceNumber(source, key)
	if !ok {
		return nil
	}
	rounded := int(math.Round(value))
	return &rounded
}

func evidenceString(source map[string]interface{}, key string) string {
	value, ok := source[key].(string)
	if !ok {
		return ""
	}
	return strings.TrimSpace(value)
}

func evidenceBool(source map[string]interface{}, key string) bool {
	switch typed := source[key].(type) {
	case bool:
		return typed
	case string:
		return strings.EqualFold(strings.TrimSpace(typed), "true")
	case float64:
		return typed != 0
	default:
		return false
	}
}

func evidenceList(source map[string]interface{}, key string) ([]interface{}, bool) {
	items, ok := source[key].([]interface{})
	return items, ok
}

// evidenceTicker validates a market ticker copied from a bot payload.
func evidenceTicker(raw string) (string, bool) {
	ticker := strings.ToUpper(strings.TrimSpace(raw))
	if !evidenceTickerPattern.MatchString(ticker) {
		return "", false
	}
	return ticker, true
}

// evidencePairLabel is "A-USD/B-USD" from two validated tickers.
func evidencePairLabel(first, second string) (string, bool) {
	a, okA := evidenceTicker(first)
	b, okB := evidenceTicker(second)
	if !okA || !okB {
		return "", false
	}
	return a + "/" + b, true
}

func evidenceRound(value float64, places int) float64 {
	if math.IsNaN(value) || math.IsInf(value, 0) {
		return 0
	}
	scale := math.Pow(10, float64(places))
	return math.Round(value*scale) / scale
}

func evidenceRoundPtr(value *float64, places int) *float64 {
	if value == nil {
		return nil
	}
	rounded := evidenceRound(*value, places)
	return &rounded
}

func evidencePercent(part, whole int) float64 {
	if whole <= 0 {
		return 0
	}
	return evidenceRound(float64(part)*100/float64(whole), 2)
}

func evidenceParseTime(raw string) (time.Time, bool) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return time.Time{}, false
	}
	for _, layout := range []string{time.RFC3339Nano, time.RFC3339, "2006-01-02T15:04:05.999999", "2006-01-02T15:04:05", "2006-01-02 15:04:05.999999", "2006-01-02 15:04:05"} {
		if parsed, err := time.Parse(layout, raw); err == nil {
			return parsed.UTC(), true
		}
	}
	return time.Time{}, false
}

// parseBotBacktestTrades reads GET /api/v1/backtests/{run_id}/trades. Rows
// whose tickers do not look like markets are skipped.
func parseBotBacktestTrades(payload map[string]interface{}) ([]botBacktestTrade, error) {
	data := unwrapBotEnvelope(payload)
	items, ok := evidenceList(data, "trades")
	if !ok {
		if data["trades"] == nil {
			return nil, errors.New("bot reply carries no trades list")
		}
		return nil, errors.New("bot reply carries an unreadable trades list")
	}
	trades := make([]botBacktestTrade, 0, len(items))
	for _, item := range items {
		row, ok := item.(map[string]interface{})
		if !ok {
			continue
		}
		pair, ok := evidencePairLabel(evidenceString(row, "market_1"), evidenceString(row, "market_2"))
		if !ok {
			continue
		}
		pnl, _ := evidenceNumber(row, "pnl_usd")
		pnlPct, _ := evidenceNumber(row, "pnl_pct")
		duration, _ := evidenceNumber(row, "duration_hours")
		entryZ, _ := evidenceNumber(row, "entry_zscore")
		win, hasWin := row["win"].(bool)
		if !hasWin {
			win = pnl > 0
		}
		trades = append(trades, botBacktestTrade{
			Pair:          pair,
			PnLUSD:        pnl,
			PnLPct:        pnlPct,
			FeeCost:       evidenceOptionalNumber(row, "fee_cost"),
			SlippageCost:  evidenceOptionalNumber(row, "slippage_cost"),
			DurationHours: duration,
			EntryZScore:   entryZ,
			Win:           win,
			ExitReason:    evidenceExitReason(evidenceString(row, "exit_reason")),
		})
	}
	return trades, nil
}

// evidenceExitReason keeps an exit reason as a short lower-case token.
func evidenceExitReason(raw string) string {
	reason := strings.ToLower(sanitizeStrategyChatText(raw, 32))
	reason = strings.ReplaceAll(reason, " ", "_")
	return reason
}

// pairAccumulator sums one pair's trades.
type pairAccumulator struct {
	stats       EvidencePairStats
	pnlPctSum   float64
	durationSum float64
	fees        float64
	feesKnown   bool
}

func newPairAccumulator(pair string) *pairAccumulator {
	return &pairAccumulator{stats: EvidencePairStats{Pair: pair}, feesKnown: true}
}

func (a *pairAccumulator) add(pnl, pnlPct, durationHours float64, win bool, fee *float64, exitReason string) {
	a.stats.Trades++
	if win {
		a.stats.Wins++
	}
	a.stats.PnLUSD += pnl
	a.pnlPctSum += pnlPct
	a.durationSum += durationHours
	if pnl > a.stats.MaxWinUSD {
		a.stats.MaxWinUSD = pnl
	}
	if pnl < a.stats.MaxLossUSD {
		a.stats.MaxLossUSD = pnl
	}
	if fee == nil {
		a.feesKnown = false
	} else {
		a.fees += *fee
	}
	if exitReason != "" {
		if a.stats.ExitReasons == nil {
			a.stats.ExitReasons = map[string]int{}
		}
		a.stats.ExitReasons[exitReason]++
	}
}

func (a *pairAccumulator) finish() EvidencePairStats {
	stats := a.stats
	stats.WinRatePct = evidencePercent(stats.Wins, stats.Trades)
	stats.PnLUSD = evidenceRound(stats.PnLUSD, 2)
	stats.MaxWinUSD = evidenceRound(stats.MaxWinUSD, 2)
	stats.MaxLossUSD = evidenceRound(stats.MaxLossUSD, 2)
	if stats.Trades > 0 {
		stats.AvgPnLPct = evidenceRound(a.pnlPctSum/float64(stats.Trades), 3)
		stats.AvgDurationHours = evidenceRound(a.durationSum/float64(stats.Trades), 2)
	}
	if a.feesKnown && stats.Trades > 0 {
		fees := evidenceRound(a.fees, 2)
		stats.FeesUSD = &fees
	}
	return stats
}

// sortPairStats orders pairs by absolute P&L, largest first, ties by name.
func sortPairStats(pairs []EvidencePairStats) {
	sort.SliceStable(pairs, func(i, j int) bool {
		left, right := math.Abs(pairs[i].PnLUSD), math.Abs(pairs[j].PnLUSD)
		if left == right {
			return pairs[i].Pair < pairs[j].Pair
		}
		return left > right
	})
}

// foldPairStats keeps the first keep pairs and folds the rest into one
// "other" aggregate.
func foldPairStats(pairs []EvidencePairStats, keep int) ([]EvidencePairStats, *EvidencePairStats, int) {
	if keep <= 0 || len(pairs) <= keep {
		return append([]EvidencePairStats{}, pairs...), nil, 0
	}
	kept := append([]EvidencePairStats{}, pairs[:keep]...)
	rest := pairs[keep:]
	other := &EvidencePairStats{Pair: "other"}
	feesKnown := true
	fees := 0.0
	pnlPctWeighted := 0.0
	durationWeighted := 0.0
	for _, pair := range rest {
		other.Trades += pair.Trades
		other.Wins += pair.Wins
		other.PnLUSD += pair.PnLUSD
		pnlPctWeighted += pair.AvgPnLPct * float64(pair.Trades)
		durationWeighted += pair.AvgDurationHours * float64(pair.Trades)
		if pair.MaxWinUSD > other.MaxWinUSD {
			other.MaxWinUSD = pair.MaxWinUSD
		}
		if pair.MaxLossUSD < other.MaxLossUSD {
			other.MaxLossUSD = pair.MaxLossUSD
		}
		if pair.FeesUSD == nil {
			feesKnown = false
		} else {
			fees += *pair.FeesUSD
		}
		for reason, count := range pair.ExitReasons {
			if other.ExitReasons == nil {
				other.ExitReasons = map[string]int{}
			}
			other.ExitReasons[reason] += count
		}
	}
	other.WinRatePct = evidencePercent(other.Wins, other.Trades)
	other.PnLUSD = evidenceRound(other.PnLUSD, 2)
	if other.Trades > 0 {
		other.AvgPnLPct = evidenceRound(pnlPctWeighted/float64(other.Trades), 3)
		other.AvgDurationHours = evidenceRound(durationWeighted/float64(other.Trades), 2)
	}
	if feesKnown {
		fees = evidenceRound(fees, 2)
		other.FeesUSD = &fees
	}
	return kept, other, len(rest)
}

// aggregateBacktestPairs groups a ledger by pair, largest |P&L| first.
func aggregateBacktestPairs(trades []botBacktestTrade) []EvidencePairStats {
	accumulators := map[string]*pairAccumulator{}
	order := make([]string, 0)
	for _, trade := range trades {
		acc, ok := accumulators[trade.Pair]
		if !ok {
			acc = newPairAccumulator(trade.Pair)
			accumulators[trade.Pair] = acc
			order = append(order, trade.Pair)
		}
		var fee *float64
		if trade.FeeCost != nil {
			total := *trade.FeeCost
			if trade.SlippageCost != nil {
				total += *trade.SlippageCost
			}
			fee = &total
		}
		acc.add(trade.PnLUSD, trade.PnLPct, trade.DurationHours, trade.Win, fee, trade.ExitReason)
	}
	pairs := make([]EvidencePairStats, 0, len(order))
	for _, pair := range order {
		pairs = append(pairs, accumulators[pair].finish())
	}
	sortPairStats(pairs)
	return pairs
}

// aggregateBacktestLedger builds the full ledger (all pairs) of one run.
func aggregateBacktestLedger(run *models.BacktestRun, trades []botBacktestTrade, tradeLimit int) *EvidenceLedger {
	ledger := &EvidenceLedger{
		RunRef:         strategyChatRunRef(run.RunID),
		TradesAnalysed: len(trades),
		TradesTotal:    run.TotalTrades,
		CostsKnown:     len(trades) > 0,
		Pairs:          aggregateBacktestPairs(trades),
	}
	if ledger.TradesTotal < ledger.TradesAnalysed {
		ledger.TradesTotal = ledger.TradesAnalysed
	}
	ledger.Truncated = ledger.TradesTotal > ledger.TradesAnalysed && ledger.TradesAnalysed >= tradeLimit
	if ledger.Truncated {
		ledger.Truncated = true
	}

	fees, slippage := 0.0, 0.0
	durationSum, absEntryZSum, pnl := 0.0, 0.0, 0.0
	durations := make([]float64, 0, len(trades))
	for _, trade := range trades {
		if trade.Win {
			ledger.Wins++
		}
		pnl += trade.PnLUSD
		durationSum += trade.DurationHours
		durations = append(durations, trade.DurationHours)
		absEntryZSum += math.Abs(trade.EntryZScore)
		if trade.FeeCost == nil || trade.SlippageCost == nil {
			ledger.CostsKnown = false
		} else {
			fees += *trade.FeeCost
			slippage += *trade.SlippageCost
		}
		if trade.ExitReason != "" {
			if ledger.ExitReasons == nil {
				ledger.ExitReasons = map[string]int{}
			}
			ledger.ExitReasons[trade.ExitReason]++
		}
	}
	ledger.WinRatePct = evidencePercent(ledger.Wins, len(trades))
	ledger.PnLUSD = evidenceRound(pnl, 2)
	if len(trades) > 0 {
		ledger.AvgDurationHours = evidenceRound(durationSum/float64(len(trades)), 2)
		ledger.AvgAbsEntryZScore = evidenceRound(absEntryZSum/float64(len(trades)), 3)
		sort.Float64s(durations)
		middle := len(durations) / 2
		if len(durations)%2 == 0 {
			ledger.MedianDurationHours = evidenceRound((durations[middle-1]+durations[middle])/2, 2)
		} else {
			ledger.MedianDurationHours = evidenceRound(durations[middle], 2)
		}
	}
	if ledger.CostsKnown {
		fees, slippage = evidenceRound(fees, 2), evidenceRound(slippage, 2)
		ledger.FeesUSD, ledger.SlippageUSD = &fees, &slippage
	}
	return ledger
}

// applyBacktestStatusToLedger copies the drawdown-halt record and the
// market-data network from the run's status overview.
func applyBacktestStatusToLedger(ledger *EvidenceLedger, payload map[string]interface{}) {
	data := unwrapBotEnvelope(payload)
	metadata := nestedMap(data, "metadata")
	if metadata == nil {
		return
	}
	if halt := nestedMap(metadata, "drawdown_halt"); halt != nil {
		limit, _ := evidenceNumber(halt, "limit_pct")
		skipped, _ := evidenceNumber(halt, "trades_skipped")
		ledger.DrawdownHalt = &EvidenceDrawdownHalt{
			LimitPct:      evidenceRound(limit, 2),
			Reached:       evidenceBool(halt, "reached"),
			TradesSkipped: int(skipped),
		}
	}
	if network := evidenceString(metadata, "market_data_network"); network != "" {
		ledger.MarketDataNetwork = sanitizeStrategyChatText(strings.ToLower(network), 16)
	}
}

// foldLedgerPairs returns a copy of a full ledger with at most keep pairs and
// the rest folded into other_pairs. The cached ledger is never modified.
func foldLedgerPairs(full *EvidenceLedger, keep int) *EvidenceLedger {
	if full == nil {
		return nil
	}
	ledger := *full
	if full.ExitReasons != nil {
		ledger.ExitReasons = make(map[string]int, len(full.ExitReasons))
		for reason, count := range full.ExitReasons {
			ledger.ExitReasons[reason] = count
		}
	}
	if full.DrawdownHalt != nil {
		halt := *full.DrawdownHalt
		ledger.DrawdownHalt = &halt
	}
	ledger.Pairs, ledger.Other, ledger.PairsOmitted = foldPairStats(full.Pairs, keep)
	return &ledger
}

// parseBotLiveTrades reads GET /api/v1/bots/{id}/trades: closed trades only,
// newest first by closed_at, plus the bot's total_trades (the matching trades
// before paging) when it reports one.
func parseBotLiveTrades(payload map[string]interface{}) ([]botLiveTrade, *int) {
	data := unwrapBotEnvelope(payload)
	total := evidenceOptionalInt(data, "total_trades")
	items, _ := evidenceList(data, "trades")
	trades := make([]botLiveTrade, 0, len(items))
	for _, item := range items {
		row, ok := item.(map[string]interface{})
		if !ok {
			continue
		}
		if status := strings.ToUpper(evidenceString(row, "status")); status != "" && status != "CLOSED" {
			continue
		}
		pair, ok := evidencePairLabel(evidenceString(row, "pair1"), evidenceString(row, "pair2"))
		if !ok {
			continue
		}
		pnl, hasPnL := evidenceNumber(row, "profit_loss")
		if !hasPnL {
			continue
		}
		seconds, _ := evidenceNumber(row, "duration_seconds")
		closedAt, _ := evidenceParseTime(evidenceString(row, "closed_at"))
		trades = append(trades, botLiveTrade{
			Pair:          pair,
			PnLUSD:        pnl,
			PnLPct:        evidenceOptionalNumber(row, "profit_loss_percentage"),
			DurationHours: seconds / 3600,
			ClosedAt:      closedAt,
		})
	}
	sort.SliceStable(trades, func(i, j int) bool {
		return trades[i].ClosedAt.After(trades[j].ClosedAt)
	})
	return trades, total
}

// aggregateLiveTrades sums the runtime's closed trades (capped at cap newest)
// and groups them by pair. The block is truncated when the cap cut the list
// or when the bot's total says more matching trades exist than it sent.
func aggregateLiveTrades(trades []botLiveTrade, total *int, cap int, keepPairs int) *EvidenceLiveTrades {
	result := &EvidenceLiveTrades{Pairs: make([]EvidencePairStats, 0)}
	if cap > 0 && len(trades) > cap {
		trades = trades[:cap]
		result.Truncated = true
	}
	if total != nil && *total > len(trades) {
		result.Truncated = true
	}
	accumulators := map[string]*pairAccumulator{}
	order := make([]string, 0)
	pnl, durationSum := 0.0, 0.0
	for _, trade := range trades {
		result.Count++
		win := trade.PnLUSD > 0
		if win {
			result.Wins++
		}
		pnl += trade.PnLUSD
		durationSum += trade.DurationHours
		acc, ok := accumulators[trade.Pair]
		if !ok {
			acc = newPairAccumulator(trade.Pair)
			accumulators[trade.Pair] = acc
			order = append(order, trade.Pair)
		}
		pnlPct := 0.0
		if trade.PnLPct != nil {
			pnlPct = *trade.PnLPct
		}
		acc.add(trade.PnLUSD, pnlPct, trade.DurationHours, win, nil, "")
	}
	result.WinRatePct = evidencePercent(result.Wins, result.Count)
	result.RealizedPnLUSD = evidenceRound(pnl, 2)
	if result.Count > 0 {
		result.AvgDurationHours = evidenceRound(durationSum/float64(result.Count), 2)
	}
	pairs := make([]EvidencePairStats, 0, len(order))
	for _, pair := range order {
		pairs = append(pairs, accumulators[pair].finish())
	}
	sortPairStats(pairs)
	if keepPairs > 0 && len(pairs) > keepPairs {
		result.PairsOmitted = len(pairs) - keepPairs
		pairs = pairs[:keepPairs]
	}
	result.Pairs = pairs
	return result
}

// parseBotPositions reads GET /api/v1/bots/{id}/positions/current.
func parseBotPositions(payload map[string]interface{}, now time.Time) []EvidenceOpenPosition {
	data := unwrapBotEnvelope(payload)
	items, _ := evidenceList(data, "positions")
	positions := make([]EvidenceOpenPosition, 0, len(items))
	for _, item := range items {
		row, ok := item.(map[string]interface{})
		if !ok {
			continue
		}
		pair, ok := evidencePairLabel(evidenceString(row, "pair1"), evidenceString(row, "pair2"))
		if !ok {
			continue
		}
		unrealized, _ := evidenceNumber(row, "unrealized_pnl")
		unrealizedPct, _ := evidenceNumber(row, "unrealized_pnl_pct")
		position := EvidenceOpenPosition{
			Pair:             pair,
			UnrealizedPnLUSD: evidenceRound(unrealized, 2),
			UnrealizedPnLPct: evidenceRound(unrealizedPct, 3),
			ZScoreEntry:      evidenceRoundPtr(evidenceOptionalNumber(row, "z_score_entry"), 3),
			ZScoreCurrent:    evidenceRoundPtr(evidenceOptionalNumber(row, "z_score_current"), 3),
		}
		if enteredAt, ok := evidenceParseTime(evidenceString(row, "entered_at")); ok && now.After(enteredAt) {
			position.OpenHours = evidenceRound(now.Sub(enteredAt).Hours(), 2)
		}
		positions = append(positions, position)
	}
	sort.SliceStable(positions, func(i, j int) bool {
		return math.Abs(positions[i].UnrealizedPnLUSD) > math.Abs(positions[j].UnrealizedPnLUSD)
	})
	if len(positions) > evidenceMaxOpenPositions {
		positions = positions[:evidenceMaxOpenPositions]
	}
	return positions
}

// parseBotExposure reads the three computed fields of the realtime stats; the
// daily and drawdown fields there are placeholders and are not read.
func parseBotExposure(payload map[string]interface{}) *EvidenceExposure {
	data := unwrapBotEnvelope(payload)
	stats := nestedMap(data, "stats")
	if stats == nil {
		return nil
	}
	open, _ := evidenceNumber(stats, "total_open_positions")
	unrealized, _ := evidenceNumber(stats, "total_unrealized_pnl")
	unrealizedPct, _ := evidenceNumber(stats, "total_unrealized_pnl_pct")
	return &EvidenceExposure{
		OpenPositions:         int(open),
		TotalUnrealizedPnLUSD: evidenceRound(unrealized, 2),
		TotalUnrealizedPnLPct: evidenceRound(unrealizedPct, 3),
	}
}

// parseEntryHalt reads GET /api/v1/bots/{id}/entry-halt through an allowlist:
// the halt's kind, reason and time, never its address, subaccount, instance
// id or details.
func parseEntryHalt(payload map[string]interface{}) *EvidenceEntryHalt {
	data := unwrapBotEnvelope(payload)
	halt := &EvidenceEntryHalt{
		Halted:     evidenceBool(data, "halted"),
		Unverified: evidenceBool(data, "unverified"),
	}
	if details := nestedMap(data, "halt"); details != nil {
		halt.Kind = sanitizeStrategyChatText(evidenceString(details, "kind"), 40)
		halt.Reason = sanitizeStrategyChatText(evidenceString(details, "reason"), 160)
		if haltedAt, ok := evidenceParseTime(evidenceString(details, "halted_at")); ok {
			halt.HaltedAt = haltedAt.Format(time.RFC3339)
		}
	}
	return halt
}

// parseBotCointegratedPairs reads GET /api/v1/bots/{id}/cointegrated-pairs,
// keeping the keep most confident pairs.
func parseBotCointegratedPairs(payload map[string]interface{}, keep int) *EvidenceCointegration {
	data := unwrapBotEnvelope(payload)
	items, _ := evidenceList(data, "pairs")
	pairs := make([]EvidenceCointegratedPair, 0, len(items))
	for _, item := range items {
		row, ok := item.(map[string]interface{})
		if !ok {
			continue
		}
		pair, ok := evidencePairLabel(evidenceString(row, "base_market"), evidenceString(row, "quote_market"))
		if !ok {
			continue
		}
		entry := EvidenceCointegratedPair{
			Pair:          pair,
			HedgeRatio:    evidenceRoundPtr(evidenceOptionalNumber(row, "hedge_ratio"), 6),
			HalfLife:      evidenceRoundPtr(evidenceOptionalNumber(row, "half_life"), 2),
			PValue:        evidenceRoundPtr(evidenceOptionalNumber(row, "p_value"), 4),
			ZScoreMean:    evidenceRoundPtr(evidenceOptionalNumber(row, "z_score_mean"), 3),
			ZScoreStd:     evidenceRoundPtr(evidenceOptionalNumber(row, "z_score_std"), 3),
			Confidence:    evidenceRoundPtr(evidenceOptionalNumber(row, "confidence_score"), 3),
			ZeroCrossings: evidenceOptionalInt(row, "zero_crossings"),
		}
		if analyzedAt, ok := evidenceParseTime(evidenceString(row, "analysis_timestamp")); ok {
			entry.AnalyzedAt = analyzedAt.Format(time.RFC3339)
		}
		pairs = append(pairs, entry)
	}
	sort.SliceStable(pairs, func(i, j int) bool {
		left, right := -1.0, -1.0
		if pairs[i].Confidence != nil {
			left = *pairs[i].Confidence
		}
		if pairs[j].Confidence != nil {
			right = *pairs[j].Confidence
		}
		if left == right {
			return pairs[i].Pair < pairs[j].Pair
		}
		return left > right
	})
	result := &EvidenceCointegration{Count: len(pairs), Pairs: pairs}
	if analyzedAt, ok := evidenceParseTime(evidenceString(data, "analyzed_at")); ok {
		result.AnalyzedAt = analyzedAt.Format(time.RFC3339)
	}
	if keep > 0 && len(pairs) > keep {
		result.Pairs = pairs[:keep]
		result.PairsOmitted = len(pairs) - keep
	}
	return result
}

// truncateEvidence trims the evidence until its JSON fits limit bytes: the
// folded remainder first, then pairs beyond 8, positions beyond 10, pair-scan
// rows beyond 6. It reports whether anything was dropped.
func truncateEvidence(evidence *StrategyEvidence, limit int) bool {
	size := func() int {
		encoded, err := json.Marshal(evidence)
		if err != nil {
			return 0
		}
		return len(encoded)
	}
	if size() <= limit {
		return false
	}
	steps := []func() bool{
		func() bool {
			if evidence.Backtests.LatestRun != nil && evidence.Backtests.LatestRun.Other != nil {
				evidence.Backtests.LatestRun.Other = nil
				return true
			}
			return false
		},
		func() bool { return trimLedgerPairs(evidence.Backtests.LatestRun, 8) },
		func() bool {
			if evidence.Live != nil && evidence.Live.ClosedTrades != nil && len(evidence.Live.ClosedTrades.Pairs) > 8 {
				trades := evidence.Live.ClosedTrades
				trades.PairsOmitted += len(trades.Pairs) - 8
				trades.Pairs = trades.Pairs[:8]
				return true
			}
			return false
		},
		func() bool {
			if evidence.Live != nil && len(evidence.Live.OpenPositions) > 10 {
				evidence.Live.OpenPositions = evidence.Live.OpenPositions[:10]
				return true
			}
			return false
		},
		func() bool {
			if evidence.Cointegration != nil && len(evidence.Cointegration.Pairs) > 6 {
				evidence.Cointegration.PairsOmitted += len(evidence.Cointegration.Pairs) - 6
				evidence.Cointegration.Pairs = evidence.Cointegration.Pairs[:6]
				return true
			}
			return false
		},
		func() bool { return trimLedgerPairs(evidence.Backtests.LatestRun, 4) },
		func() bool {
			if evidence.Live != nil && evidence.Live.ClosedTrades != nil && len(evidence.Live.ClosedTrades.Pairs) > 4 {
				trades := evidence.Live.ClosedTrades
				trades.PairsOmitted += len(trades.Pairs) - 4
				trades.Pairs = trades.Pairs[:4]
				return true
			}
			return false
		},
	}
	truncated := false
	for _, step := range steps {
		if step() {
			truncated = true
		}
		if size() <= limit {
			break
		}
	}
	return truncated
}

func trimLedgerPairs(ledger *EvidenceLedger, keep int) bool {
	if ledger == nil || len(ledger.Pairs) <= keep {
		return false
	}
	ledger.PairsOmitted += len(ledger.Pairs) - keep
	ledger.Pairs = ledger.Pairs[:keep]
	return true
}
