package handlers

import (
	"testing"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

func TestApplyStrategyPayloadPreservesOmittedFields(t *testing.T) {
	strategy := &models.BacktestStrategy{
		IsPublic:         true,
		IsDefault:        true,
		SelectedMarkets:  `["BTC-USD","ETH-USD"]`,
		StartingBalance:  2500,
		InitialAmount:    2500,
		CandleResolution: "1HOUR",
	}

	applyStrategyPayload(strategy, strategyPayload{
		Name:          "Updated",
		InitialAmount: 5000,
		Resolution:    "M5",
	})

	if !strategy.IsPublic || !strategy.IsDefault {
		t.Fatalf("omitted boolean fields should be preserved, got is_public=%v is_default=%v", strategy.IsPublic, strategy.IsDefault)
	}
	if got := strategy.SelectedMarketList(); len(got) != 2 || got[0] != "BTC-USD" || got[1] != "ETH-USD" {
		t.Fatalf("omitted selected_markets should be preserved, got %#v", got)
	}
	if strategy.StartingBalance != 5000 || strategy.InitialAmount != 5000 {
		t.Fatalf("initial_amount should stay aligned with starting_balance, got starting=%v initial=%v", strategy.StartingBalance, strategy.InitialAmount)
	}
	if strategy.CandleResolution != "5MINS" {
		t.Fatalf("resolution should normalize for dYdX REST candles, got %q", strategy.CandleResolution)
	}
}

func TestApplyStrategyPayloadCanClearSelectedMarkets(t *testing.T) {
	strategy := &models.BacktestStrategy{
		SelectedMarkets: `["BTC-USD","ETH-USD"]`,
	}
	emptyMarkets := []string{}

	applyStrategyPayload(strategy, strategyPayload{SelectedMarkets: &emptyMarkets})

	if got := strategy.SelectedMarketList(); len(got) != 0 {
		t.Fatalf("explicit empty selected_markets should clear market universe, got %#v", got)
	}
}

func TestApplyStrategyPayloadHonoursExplicitZeroForUnenforcedControls(t *testing.T) {
	strategy := &models.BacktestStrategy{MaxDrawdownPct: 15, TrailingStopPct: 1, StopLossPct: 2}
	zero := 0.0

	applyStrategyPayload(strategy, strategyPayload{MaxDrawdownPct: &zero})

	if strategy.MaxDrawdownPct != 0 {
		t.Fatalf("explicit 0 must turn max_drawdown_pct off, got %v", strategy.MaxDrawdownPct)
	}
	if strategy.TrailingStopPct != 1 {
		t.Fatalf("omitted trailing_stop_pct must be preserved, got %v", strategy.TrailingStopPct)
	}

	negative := -5.0
	applyStrategyPayload(strategy, strategyPayload{TrailingStopPct: &negative})
	if strategy.TrailingStopPct != 1 {
		t.Fatalf("a negative value must be ignored, got %v", strategy.TrailingStopPct)
	}
}
