package services

import (
	"errors"
	"fmt"
	"net/http"
	"testing"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

const botRiskControlRefusalBody = `{"success":false,"message":"Validation error: max_drawdown_pct is not enforced by the live runtime and is rejected until bot-level drawdown policy is implemented.","data":{"error":"UNSUPPORTED_RISK_CONTROL","unsupported_fields":[{"field":"max_drawdown_pct","value":15,"message":"max_drawdown_pct is not enforced by the live runtime and is rejected until bot-level drawdown policy is implemented."}]}}`

func TestParseBotAPIErrorKeepsCodeAndData(t *testing.T) {
	err := parseBotAPIError(http.StatusUnprocessableEntity, []byte(botRiskControlRefusalBody))

	var apiErr *BotAPIError
	if !errors.As(err, &apiErr) {
		t.Fatalf("expected *BotAPIError, got %T", err)
	}
	if apiErr.Code != "UNSUPPORTED_RISK_CONTROL" {
		t.Fatalf("expected the bot's error code, got %q", apiErr.Code)
	}
	if _, ok := apiErr.Data["unsupported_fields"].([]interface{}); !ok {
		t.Fatalf("expected unsupported_fields to survive parsing, got %#v", apiErr.Data)
	}
}

func TestUnenforcedRiskControlsFromErrorRecognisesOnlyTheRefusal(t *testing.T) {
	refusal := fmt.Errorf("wrapped: %w", parseBotAPIError(http.StatusUnprocessableEntity, []byte(botRiskControlRefusalBody)))
	controls, text, ok := unenforcedRiskControlsFromError(refusal)
	if !ok {
		t.Fatal("expected the wrapped refusal to be recognised")
	}
	if len(controls) != 1 || controls[0]["field"] != "max_drawdown_pct" || controls[0]["value"] != 15.0 {
		t.Fatalf("unexpected controls: %#v", controls)
	}
	if text == "" || text[:len("max_drawdown_pct")] != "max_drawdown_pct" {
		t.Fatalf("expected the refusal text without the transport prefix, got %q", text)
	}

	for name, err := range map[string]error{
		"other 422":       &BotAPIError{StatusCode: http.StatusUnprocessableEntity, Code: "VALIDATION_ERROR", Message: "bad"},
		"same code, 500":  &BotAPIError{StatusCode: http.StatusInternalServerError, Code: botErrorCodeUnsupportedRiskControl},
		"transport error": &BotAPITransportError{StatusCode: http.StatusBadGateway, Message: "down"},
		"plain error":     errors.New("boom"),
	} {
		if _, _, ok := unenforcedRiskControlsFromError(err); ok {
			t.Fatalf("%s must not be treated as a risk-control refusal", name)
		}
	}
}

func TestLiveTradingParamsNeverCarryAnInventedCapitalAllocation(t *testing.T) {
	strategy := &models.BacktestStrategy{
		ID:               7,
		InitialAmount:    1000,
		UsdMinCollateral: 100,
		UsdPerTrade:      10,
		MaxDrawdownPct:   15,
		TrailingStopPct:  1,
		SelectedMarkets:  `["BTC-USD","ETH-USD"]`,
	}

	params := (&StrategyRuntimeService{}).buildTradingParams(strategy, "testnet")

	if got := params["capital_allocation_usd"]; got != 0.0 {
		t.Fatalf("backtest capital must not reach the live runtime as a cap, got %#v", got)
	}
	// Operator-set controls are passed through untouched so the bot stays the
	// one that refuses them; the gateway must not quietly drop them.
	if got := params["max_drawdown_pct"]; got != 15.0 {
		t.Fatalf("max_drawdown_pct must be sent as configured, got %#v", got)
	}
	if got := params["trailing_stop_pct"]; got != 1.0 {
		t.Fatalf("trailing_stop_pct must be sent as configured, got %#v", got)
	}
}

func TestResolveCapitalAllocationIsBacktestCapitalOnly(t *testing.T) {
	if got := resolveCapitalAllocation(&models.BacktestStrategy{InitialAmount: 2500, UsdMinCollateral: 100}); got != 2500 {
		t.Fatalf("expected the backtest capital, got %v", got)
	}
	if got := resolveCapitalAllocation(&models.BacktestStrategy{UsdMinCollateral: 100}); got != 0 {
		t.Fatalf("minimum collateral is not a capital allocation, got %v", got)
	}
	if got := resolveCapitalAllocation(nil); got != 0 {
		t.Fatalf("expected 0 for a nil strategy, got %v", got)
	}
}
