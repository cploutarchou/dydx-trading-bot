package services

import (
	"fmt"
	"strings"
	"testing"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

func chatTestStrategy() *models.BacktestStrategy {
	strategy := newStrategyWithDefaults(1, "Pairs", "desc", "pairs_trading", false, false)
	strategy.ID = 101
	strategy.MaxDrawdownPct = 15
	strategy.TrailingStopPct = 0
	return strategy
}

func proposalWith(changes ...strategyChatModelChange) *strategyChatModelProposal {
	return &strategyChatModelProposal{Kind: "update", Title: "Tune", Summary: "s", Changes: changes}
}

func droppedReason(t *testing.T, proposal *StrategyChatProposal, field string) string {
	t.Helper()
	for _, dropped := range proposal.Dropped {
		if dropped.Field == field {
			return dropped.Reason
		}
	}
	t.Fatalf("expected %s to be dropped, got changes=%+v dropped=%+v", field, proposal.Changes, proposal.Dropped)
	return ""
}

func acceptedChange(t *testing.T, proposal *StrategyChatProposal, field string) StrategyChatChange {
	t.Helper()
	for _, change := range proposal.Changes {
		if change.Field == field {
			return change
		}
	}
	t.Fatalf("expected %s to be accepted, got changes=%+v dropped=%+v", field, proposal.Changes, proposal.Dropped)
	return StrategyChatChange{}
}

func TestStrategyChatProposalBounds(t *testing.T) {
	strategy := chatTestStrategy()
	proposal := validateStrategyChatProposal(proposalWith(
		strategyChatModelChange{Field: "zscore_threshold", Value: 0.05, Reason: "too low"},
		strategyChatModelChange{Field: "usd_per_trade", Value: 2_000_000.0},
		strategyChatModelChange{Field: "stop_loss_pct", Value: 3.5, Reason: "wider stop"},
		strategyChatModelChange{Field: "transaction_fee", Value: 0.0},
		strategyChatModelChange{Field: "slippage", Value: 0.0015},
	), strategy)

	if !strings.Contains(droppedReason(t, proposal, "zscore_threshold"), "range") {
		t.Fatal("expected an out-of-range reason for zscore_threshold")
	}
	droppedReason(t, proposal, "usd_per_trade")
	if !strings.Contains(droppedReason(t, proposal, "transaction_fee"), "above 0") {
		t.Fatal("expected transaction_fee to require a value above 0")
	}
	change := acceptedChange(t, proposal, "stop_loss_pct")
	if change.Current != 2.0 || change.Proposed != 3.5 || change.Risk != StrategyChatRiskRiskControl || change.Unit != "%" || change.Label == "" {
		t.Fatalf("unexpected stop_loss_pct change %+v", change)
	}
	slippage := acceptedChange(t, proposal, "slippage")
	if !slippage.BacktestOnly {
		t.Fatal("expected slippage to be marked backtest only")
	}
}

func TestStrategyChatProposalIntegersAndStrings(t *testing.T) {
	strategy := chatTestStrategy()
	proposal := validateStrategyChatProposal(proposalWith(
		strategyChatModelChange{Field: "stats_window", Value: 30.5},
		strategyChatModelChange{Field: "max_positions", Value: 3.0},
		strategyChatModelChange{Field: "zscore_threshold", Value: "2.25"},
		strategyChatModelChange{Field: "close_at_zscore_cross", Value: false},
		strategyChatModelChange{Field: "rebalance_interval_hours", Value: "soon"},
	), strategy)

	if !strings.Contains(droppedReason(t, proposal, "stats_window"), "whole number") {
		t.Fatal("expected a whole-number reason")
	}
	if change := acceptedChange(t, proposal, "max_positions"); change.Proposed != 3 {
		t.Fatalf("expected max_positions as int 3, got %#v", change.Proposed)
	}
	if change := acceptedChange(t, proposal, "zscore_threshold"); change.Proposed != 2.25 {
		t.Fatalf("expected a numeric string to be read as 2.25, got %#v", change.Proposed)
	}
	acceptedChange(t, proposal, "close_at_zscore_cross")
	droppedReason(t, proposal, "rebalance_interval_hours")
}

func TestStrategyChatProposalResolutionAliasAndEnum(t *testing.T) {
	strategy := chatTestStrategy()
	proposal := validateStrategyChatProposal(proposalWith(
		strategyChatModelChange{Field: "resolution", Value: "4h"},
		strategyChatModelChange{Field: "candle_resolution", Value: "15MINS"},
	), strategy)
	change := acceptedChange(t, proposal, "candle_resolution")
	if change.Proposed != "4HOURS" || change.Current != "1HOUR" {
		t.Fatalf("expected resolution alias mapped to candle_resolution 4HOURS, got %+v", change)
	}
	if !strings.Contains(droppedReason(t, proposal, "candle_resolution"), "Duplicate") {
		t.Fatal("expected the second resolution change to be a duplicate")
	}

	unknown := validateStrategyChatProposal(proposalWith(strategyChatModelChange{Field: "candle_resolution", Value: "2HOURS"}), strategy)
	if len(unknown.Changes) != 0 || !strings.Contains(droppedReason(t, unknown, "candle_resolution"), "one of") {
		t.Fatalf("expected an unknown resolution to be refused, not defaulted: %+v", unknown)
	}
}

func TestStrategyChatProposalNeverSwitchesRiskLimitsOff(t *testing.T) {
	strategy := chatTestStrategy() // max_drawdown_pct 15 (on), trailing_stop_pct 0 (off)
	proposal := validateStrategyChatProposal(proposalWith(
		strategyChatModelChange{Field: "max_drawdown_pct", Value: 0.0},
		strategyChatModelChange{Field: "trailing_stop_pct", Value: 0.0},
	), strategy)
	if !strings.Contains(droppedReason(t, proposal, "max_drawdown_pct"), "off") {
		t.Fatal("expected switching the drawdown limit off to be refused")
	}
	if !strings.Contains(droppedReason(t, proposal, "trailing_stop_pct"), "Same") {
		t.Fatal("expected an already-off trailing stop at 0 to be dropped as unchanged")
	}

	turnOn := validateStrategyChatProposal(proposalWith(
		strategyChatModelChange{Field: "trailing_stop_pct", Value: 1.5},
		strategyChatModelChange{Field: "max_drawdown_pct", Value: 10.0},
	), strategy)
	acceptedChange(t, turnOn, "trailing_stop_pct")
	acceptedChange(t, turnOn, "max_drawdown_pct")
}

// A risk limit cannot be switched off through its maximum either: the bounds
// stop before the values at which a limit never triggers, and a limit that is
// on may be loosened at most four-fold per proposal.
func TestStrategyChatProposalRiskLimitBoundsAndLoosening(t *testing.T) {
	strategy := chatTestStrategy() // stop_loss 2, timeout 72
	strategy.MaxDrawdownPct = 10
	strategy.TrailingStopPct = 3
	offByMaximum := validateStrategyChatProposal(proposalWith(
		strategyChatModelChange{Field: "max_drawdown_pct", Value: 100.0},
		strategyChatModelChange{Field: "stop_loss_pct", Value: 100.0},
		strategyChatModelChange{Field: "trailing_stop_pct", Value: 100.0},
		strategyChatModelChange{Field: "position_timeout_hours", Value: 8760.0},
	), strategy)
	for _, field := range []string{"max_drawdown_pct", "stop_loss_pct", "trailing_stop_pct", "position_timeout_hours"} {
		if !strings.Contains(droppedReason(t, offByMaximum, field), "range") {
			t.Fatalf("expected %s at the old maximum to be out of range", field)
		}
	}
	if len(offByMaximum.Changes) != 0 {
		t.Fatalf("expected no accepted changes, got %+v", offByMaximum.Changes)
	}

	tooLoose := validateStrategyChatProposal(proposalWith(
		strategyChatModelChange{Field: "max_drawdown_pct", Value: 50.0},        // 10 -> 50 is within bounds but > 4x
		strategyChatModelChange{Field: "stop_loss_pct", Value: 9.0},            // 2 -> 9
		strategyChatModelChange{Field: "trailing_stop_pct", Value: 12.5},       // 3 -> 12.5
		strategyChatModelChange{Field: "position_timeout_hours", Value: 289.0}, // 72 -> 289
	), strategy)
	for _, field := range []string{"max_drawdown_pct", "stop_loss_pct", "trailing_stop_pct", "position_timeout_hours"} {
		if !strings.Contains(droppedReason(t, tooLoose, field), "four-fold") {
			t.Fatalf("expected %s loosened more than four-fold to be refused", field)
		}
	}

	fourFold := validateStrategyChatProposal(proposalWith(
		strategyChatModelChange{Field: "max_drawdown_pct", Value: 40.0},
		strategyChatModelChange{Field: "stop_loss_pct", Value: 8.0},
		strategyChatModelChange{Field: "trailing_stop_pct", Value: 12.0},
		strategyChatModelChange{Field: "position_timeout_hours", Value: 288.0},
		strategyChatModelChange{Field: "take_profit_pct", Value: 100.0}, // not a risk control: 5 -> 100 is fine
	), strategy)
	for _, field := range []string{"max_drawdown_pct", "stop_loss_pct", "trailing_stop_pct", "position_timeout_hours", "take_profit_pct"} {
		acceptedChange(t, fourFold, field)
	}

	// Tightening and turning a limit on are never limited by the rule.
	strategy.TrailingStopPct = 0
	tighten := validateStrategyChatProposal(proposalWith(
		strategyChatModelChange{Field: "max_drawdown_pct", Value: 1.0},
		strategyChatModelChange{Field: "trailing_stop_pct", Value: 20.0},
		strategyChatModelChange{Field: "position_timeout_hours", Value: 1.0},
	), strategy)
	for _, field := range []string{"max_drawdown_pct", "trailing_stop_pct", "position_timeout_hours"} {
		acceptedChange(t, tighten, field)
	}
}

func TestStrategyChatProposalDropsUnchangedLockedAndUnknown(t *testing.T) {
	strategy := chatTestStrategy()
	proposal := validateStrategyChatProposal(proposalWith(
		strategyChatModelChange{Field: "zscore_threshold", Value: 1.5},
		strategyChatModelChange{Field: "place_trades", Value: false},
		strategyChatModelChange{Field: "runtime_network", Value: "mainnet"},
		strategyChatModelChange{Field: "selected_markets", Value: []any{"BTC-USD"}},
		strategyChatModelChange{Field: "leverage", Value: 20.0},
	), strategy)
	if !strings.Contains(droppedReason(t, proposal, "zscore_threshold"), "Same") {
		t.Fatal("expected an unchanged value to be dropped")
	}
	for _, locked := range []string{"place_trades", "runtime_network", "selected_markets"} {
		if !strings.Contains(droppedReason(t, proposal, locked), "cannot change") {
			t.Fatalf("expected %s to be locked", locked)
		}
	}
	if droppedReason(t, proposal, "leverage") != "Unknown setting" {
		t.Fatal("expected an unknown setting reason")
	}
	for _, dropped := range proposal.Dropped {
		if dropped.Field == "selected_markets" && dropped.Value != nil {
			t.Fatalf("expected a non-scalar value not to be echoed, got %#v", dropped.Value)
		}
	}
	if len(proposal.Changes) != 0 {
		t.Fatalf("expected no accepted changes, got %+v", proposal.Changes)
	}
}

func TestStrategyChatProposalKeepsAtMostEightChanges(t *testing.T) {
	strategy := chatTestStrategy()
	raw := proposalWith(
		strategyChatModelChange{Field: "zscore_threshold", Value: 2.0},
		strategyChatModelChange{Field: "stats_window", Value: 30.0},
		strategyChatModelChange{Field: "max_half_life", Value: 30.0},
		strategyChatModelChange{Field: "usd_per_trade", Value: 12.0},
		strategyChatModelChange{Field: "usd_min_collateral", Value: 150.0},
		strategyChatModelChange{Field: "max_positions", Value: 4.0},
		strategyChatModelChange{Field: "stop_loss_pct", Value: 3.0},
		strategyChatModelChange{Field: "take_profit_pct", Value: 6.0},
		strategyChatModelChange{Field: "rebalance_interval_hours", Value: 12.0},
		strategyChatModelChange{Field: "position_timeout_hours", Value: 48.0},
	)
	proposal := validateStrategyChatProposal(raw, strategy)
	if len(proposal.Changes) != strategyChatMaxChanges {
		t.Fatalf("expected %d changes, got %d", strategyChatMaxChanges, len(proposal.Changes))
	}
	if len(proposal.Dropped) != 2 || !strings.Contains(proposal.Dropped[0].Reason, "More than 8") {
		t.Fatalf("expected the ninth and tenth change dropped, got %+v", proposal.Dropped)
	}
}

func TestStrategyChatProposalCurrentComesFromTheStrategy(t *testing.T) {
	strategy := chatTestStrategy()
	strategy.MaxHalfLife = 24
	proposal := validateStrategyChatProposal(&strategyChatModelProposal{
		Kind:    "new_strategy",
		Changes: []strategyChatModelChange{{Field: "max_half_life", Value: 36.0}},
	}, strategy)
	if proposal.Kind != StrategyChatKindNewStrategy || proposal.Title == "" {
		t.Fatalf("expected kind new_strategy with a default title, got %+v", proposal)
	}
	change := acceptedChange(t, proposal, "max_half_life")
	if change.Current != 24 || change.Proposed != 36 {
		t.Fatalf("expected current 24 read from the strategy, got %+v", change)
	}
	if weird := validateStrategyChatProposal(&strategyChatModelProposal{Kind: "delete_everything"}, strategy); weird.Kind != StrategyChatKindUpdate {
		t.Fatalf("expected an unknown kind to fall back to update, got %q", weird.Kind)
	}
}

// Every object in the reply schema must be closed and list all its
// properties as required, and unions use anyOf rather than type arrays.
func assertStrictSchema(t *testing.T, path string, node any) {
	t.Helper()
	switch typed := node.(type) {
	case map[string]any:
		if _, isArray := typed["type"].([]string); isArray {
			t.Fatalf("%s: type arrays are not allowed", path)
		}
		if typed["type"] == "object" {
			if typed["additionalProperties"] != false {
				t.Fatalf("%s: object must set additionalProperties false", path)
			}
			properties, _ := typed["properties"].(map[string]any)
			required, _ := typed["required"].([]string)
			if len(required) != len(properties) {
				t.Fatalf("%s: every property must be required, got %v for %d properties", path, required, len(properties))
			}
			for _, name := range required {
				if _, ok := properties[name]; !ok {
					t.Fatalf("%s: required %q is not a property", path, name)
				}
			}
		}
		for key, value := range typed {
			assertStrictSchema(t, path+"."+key, value)
		}
	case []any:
		for i, value := range typed {
			assertStrictSchema(t, fmt.Sprintf("%s[%d]", path, i), value)
		}
	}
}

func TestStrategyChatReplySchemaIsStrict(t *testing.T) {
	schema := strategyChatReplySchema()
	assertStrictSchema(t, "$", schema)
	proposal := schema["properties"].(map[string]any)["proposal"].(map[string]any)
	if _, ok := proposal["anyOf"]; !ok {
		t.Fatal("expected proposal to be anyOf null|object")
	}
}

func TestStrategyChatPromptListsEveryAllowlistedField(t *testing.T) {
	lines := strings.Join(strategyChatFieldPromptLines(), "\n")
	for _, field := range strategyChatFields {
		if !strings.Contains(lines, "- "+field.Key+":") {
			t.Fatalf("expected %s in the prompt field list", field.Key)
		}
	}
	for _, expected := range []string{
		"from 0.1 to 10", "whole number from 2 to 2000", "above 0 to 0.1", "never propose 0 while it is on", "1MIN, 5MINS",
		"max_drawdown_pct: Maximum drawdown (%); number from 0 to 50; 0 means off; never propose 0 while it is on; at most four times the current value",
		"stop_loss_pct: Stop loss (%); number from 0.1 to 25; at most four times the current value",
		"trailing_stop_pct: Trailing stop (%); number from 0 to 25;",
		"position_timeout_hours: Position timeout (hours); whole number from 1 to 720; at most four times the current value",
	} {
		if !strings.Contains(lines, expected) {
			t.Fatalf("expected %q in the prompt field list:\n%s", expected, lines)
		}
	}
}
