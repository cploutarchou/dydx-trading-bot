package services

import "testing"

// Both controls are enforced by the live runtime (the drawdown limit halts new
// entries, the trailing stop closes pairs), so a strategy created without them
// must not start with either one on.
func TestNewStrategyStartsWithDrawdownLimitAndTrailingStopOff(t *testing.T) {
	strategy := newStrategyWithDefaults(85, "defaults", "", "", false, false)

	if strategy.MaxDrawdownPct != 0 {
		t.Fatalf("max_drawdown_pct default = %v, want 0", strategy.MaxDrawdownPct)
	}
	if strategy.TrailingStopPct != 0 {
		t.Fatalf("trailing_stop_pct default = %v, want 0", strategy.TrailingStopPct)
	}
	if strategy.StopLossPct != 2 || strategy.TakeProfitPct != 5 {
		t.Fatalf("stop loss / take profit defaults changed: %v / %v", strategy.StopLossPct, strategy.TakeProfitPct)
	}
}
