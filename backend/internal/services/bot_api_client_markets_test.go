package services

import "testing"

func TestGetPerpetualMarketsFor_SendsBacktestPurposeOnlyWhenAsked(t *testing.T) {
	backtest := captureUpstreamQuery(t, func(c *BotAPIClient) error {
		_, err := c.GetPerpetualMarketsFor(0, false, true)
		return err
	})
	if backtest.Get("purpose") != "backtest" {
		t.Fatalf("expected purpose=backtest, got %v", backtest)
	}

	runtime := captureUpstreamQuery(t, func(c *BotAPIClient) error {
		_, err := c.GetPerpetualMarkets(25, true)
		return err
	})
	if runtime.Has("purpose") {
		t.Fatalf("runtime market list must not carry a purpose: %v", runtime)
	}
	if runtime.Get("limit") != "25" || runtime.Get("include_settled") != "true" {
		t.Fatalf("existing filters changed: %v", runtime)
	}
}
